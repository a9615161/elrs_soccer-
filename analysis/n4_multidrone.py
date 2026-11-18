"""N4 (= F7 no-jammer part): M links in one field with the full new-mechanism stack.

N1 showed the hopping is orthogonal at alignment and priced the coordination; N4 runs the whole
link (PRP channels over N=79 + implicit-nonce MAC + critical-channel resync) for M drones and
reports per-drone PDR as M grows and as the shared slot base drifts, with and without adjacent-
channel leakage. Friendly collisions use E9's overlap test so the numbers tie back to N1/E9.

Run:  make lib && .venv/bin/python analysis/n4_multidrone.py [--config configs/n4_multidrone.yaml]
Out:  data/results/n4_multidrone/<commit>.parquet  (per trial x M x leakage x offset x drone)
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.common import git_commit, load_yaml, result_dir  # noqa: E402
from sim import phy, proto_ffi  # noqa: E402
from sim.linksim import Scenario, run  # noqa: E402

CRIT = 49       # critical channel (excluded from the hop set)
N_PROP = 79     # Proposed hop set


def _h(*parts) -> int:
    return int.from_bytes(hashlib.sha256(repr(parts).encode()).digest()[:8], "little")


def schedules(M: int, n: int, r: dict, rng, offset_frac: float):
    """PRP channels over N=79 for M drones sharing one key/base, plus per-drone slot offsets."""
    H = r["hop_interval"]
    hops = n // H + 2
    p = proto_ffi.Proto(rng.integers(0, 256, 16, dtype=np.uint8).tobytes(), b"field-n4")
    h0 = int(rng.integers(0, 2**40))
    ch = np.empty((M, n), np.uint8)
    idx = np.arange(n) // H
    for i in range(M):
        h = p.hop_sequence(h0, hops, i, N_PROP)         # PRP: orthogonal across drones per hop
        h = h + (h >= CRIT).astype(h.dtype)             # map 0..78 onto the non-critical channels
        ch[i] = h[idx]
    off = rng.uniform(0, offset_frac * r["period_us"], M)
    return ch, off


def friendly_loss(ch, off, r, leakage, p_adj, rng):
    """E9's collision test: lost[i, k] (same-channel + optional adjacent leakage) and co-channel."""
    M, n = ch.shape
    P, toa = r["period_us"], r["airtime_us"]
    lost = np.zeros((M, n), bool)
    cochan = np.zeros((M, n), bool)
    k = np.arange(n)
    for i, j in itertools.permutations(range(M), 2):
        base = int(np.floor((off[i] - off[j]) / P))
        for dm in (base, base + 1):
            m = k + dm
            valid = (m >= 0) & (m < n)
            dt = (k - m) * P + off[i] - off[j]
            overlap = valid & (np.abs(dt) < toa)
            mc = np.clip(m, 0, n - 1)
            d = np.abs(ch[i].astype(int) - ch[j, mc].astype(int))
            cochan[i] |= overlap & (d == 0)
            lost[i] |= overlap & (d == 0)
            if leakage:
                lost[i] |= overlap & (d == 1) & (rng.random(n) < p_adj)
    return lost, cochan


def run_trial(args) -> list[dict]:
    cfg, rate, M, leak, frac, trial = args
    r = phy.rate(rate)
    n = int(cfg["duration_s"] * 1e6 // r["period_us"])
    rng = np.random.default_rng(_h(cfg["seed"], rate, M, leak, frac, trial))
    jseed = _h(cfg["seed"], rate, M, trial)
    ch, off = schedules(M, n, r, rng, frac)
    lost, cochan = friendly_loss(ch, off, r, leak, cfg["p_adj"], rng)
    rows = []
    for i in range(M):
        res = run(Scenario(protocol="proposed", crit_channel=CRIT, n_sync=1, rate=rate,
                           duration_s=cfg["duration_s"], seed=jseed, tx_channels=ch[i],
                           extra_loss=lost[i], drone_id=i, n_drones=M, window=cfg["window"]))
        mr = res.metrics
        rows.append({"rate": rate, "M": M, "leakage": leak, "offset_frac": frac, "trial": trial,
                     "drone": i, "pdr": mr["pdr"], "friendly_loss": float(lost[i].mean()),
                     "cochannel": float(cochan[i].mean()), "failsafe_count": mr["failsafe_count"],
                     "max_outage_ms": mr["max_outage_ms"]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "n4_multidrone.yaml"))
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    cfg = load_yaml(a.config)

    tasks = []
    for rate in cfg["rates"]:
        for M in cfg["drones"]:
            for leak in cfg["leakage"]:
                for t in range(cfg["trials"]):
                    tasks.append((cfg, rate, M, leak, 0.0, t))                 # aligned
        for leak in cfg["leakage"]:
            for frac in cfg["offset_fracs"]:
                for t in range(cfg["trials"]):
                    tasks.append((cfg, rate, cfg["offset_drones"], leak, frac, t))  # offset sweep

    with Pool(a.workers) as pool:
        out = []
        for rows in tqdm(pool.imap_unordered(run_trial, tasks, chunksize=2), total=len(tasks),
                         desc="n4", mininterval=5):
            out.extend(rows)
    df = pd.DataFrame(out)
    d = result_dir("n4_multidrone", cfg)
    commit = git_commit()
    df.to_parquet(d / f"{commit}.parquet")

    pd.set_option("display.width", 200)
    al = df[(df.offset_frac == 0.0)]
    print("\n== aligned: per-drone PDR (min over drones) and friendly loss vs M ==")
    g = al.groupby(["leakage", "M"]).agg(pdr_min=("pdr", "min"), pdr_mean=("pdr", "mean"),
                                         friendly=("friendly_loss", "mean")).round(5)
    print(g.to_string())
    print("\n== offset sweep (M=%d): friendly loss & PDR vs offset_frac ==" % cfg["offset_drones"])
    os_ = df[df.offset_frac > 0]
    g2 = os_.groupby(["leakage", "offset_frac"]).agg(friendly=("friendly_loss", "mean"),
                                                     pdr_mean=("pdr", "mean")).round(5)
    print(g2.to_string())
    print("\nwrote", d / f"{commit}.parquet")


if __name__ == "__main__":
    main()
