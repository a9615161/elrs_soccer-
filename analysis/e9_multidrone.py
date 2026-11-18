"""E9: M drones (one TX->RX link each) sharing the band.

Hopping:
  stock    - ExpressLRS sequences from independent UIDs, random start index and random
             time offset per drone (drones are not time-aligned); stock RX/TX logic
  random   - i.i.d. channel per hop per drone, slots aligned; proposed RX logic
  proposed - gap transform (g=2) over the M drones, slots aligned to field time; the offset sweep
             draws each drone's offset uniformly from [0, frac * period]
Every slot each drone's link puts one packet (uplink or telemetry) on its hop channel.
Drone i's packet is lost to a friendly transmission that overlaps it in time and
  - uses the same channel (always lost), or
  - an adjacent channel (|dch| = 1) when leakage is on (lost with p_adj).
The same jammer realisation is applied to every drone. sync_channel_* track the public sync
channel: the share of a drone's packets on it and the loss rate of those packets.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import git_commit, load_yaml, result_dir  # noqa: E402
from sim import phy, proto_ffi  # noqa: E402
from sim.baselines import elrs_stock  # noqa: E402
from sim.linksim import Scenario, run  # noqa: E402


def schedules(scheme, M, n, r, rng, offset_frac=0.0):
    """(channels (M, n), time offsets (M,) in us, TX nonce at t = 0 (M,))."""
    H, N = r["hop_interval"], r["num_channels"]
    hops_needed = n // H + 2
    nonce0 = np.zeros(M, dtype=np.int64)
    if scheme == "stock":
        ch = np.empty((M, n), np.uint8)
        for i in range(M):
            uid = rng.integers(0, 256, 6, dtype=np.uint8).tobytes()
            seq = elrs_stock.build_sequence(elrs_stock.uid_seed(uid), N)
            nonce0[i] = int(rng.integers(H * len(seq)))  # FHSS index and nonce reset together
            ch[i] = seq[((nonce0[i] + np.arange(n)) // H) % len(seq)]
        return ch, rng.uniform(0, r["period_us"], M), nonce0
    if scheme == "random":
        hops = rng.integers(0, N, size=(M, hops_needed), dtype=np.uint8)
        return hops[:, np.arange(n) // H], np.zeros(M), nonce0
    p = proto_ffi.Proto(rng.integers(0, 256, 16, dtype=np.uint8).tobytes(), b"field-e9")
    hops = p.hop_gap_block(int(rng.integers(0, 2**40)), hops_needed, N, M, 2)
    return hops[:, np.arange(n) // H], rng.uniform(0, offset_frac * r["period_us"], M), nonce0


def friendly_loss(ch, off, r, leakage, p_adj, rng):
    """lost[i, k] and same-channel-only collision mask."""
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
            same = overlap & (d == 0)
            cochan[i] |= same
            lost[i] |= same
            if leakage:
                lost[i] |= overlap & (d == 1) & (rng.random(n) < p_adj)
    return lost, cochan


def _h(*parts) -> int:
    """Process-independent seed (built-in hash() of str is salted per process)."""
    return int.from_bytes(hashlib.sha256(repr(parts).encode()).digest()[:8], "little")


def run_trial(args):
    cfg, rate, scheme, M, leak, jam_name, trial, frac = args
    r = phy.rate(rate)
    n = int(cfg["duration_s"] * 1e6 // r["period_us"])
    seed = _h(cfg["seed"], rate, scheme, M, leak, jam_name, trial, frac)
    jseed = _h(cfg["seed"], rate, M, jam_name, trial)  # same jammer realisation for all schemes
    rng = np.random.default_rng(seed)
    ch, off, nonce0 = schedules(scheme, M, n, r, rng, frac)
    lost, cochan = friendly_loss(ch, off, r, leak, cfg["p_adj"], rng)
    protocol = "stock" if scheme == "stock" else "proposed"
    rows = []
    for i in range(M):
        res = run(Scenario(protocol=protocol, rate=rate, duration_s=cfg["duration_s"], seed=jseed,
                           tx_channels=ch[i], extra_loss=lost[i], jammer=cfg["jammers"][jam_name],
                           drone_id=i, n_drones=M, window=cfg["window"], nonce0=int(nonce0[i])))
        m = res.metrics
        on_sync = ch[i] == r["sync_channel"]
        rows.append({"rate": rate, "offset_frac": frac, "scheme": scheme, "M": M, "leakage": leak,
                     "jammer": jam_name, "trial": trial, "drone": i,
                     "sync_channel_share": float(on_sync.mean()),
                     "sync_channel_loss": float(lost[i][on_sync].mean()) if on_sync.any() else 0.0,
                     "pdr": m["pdr"], "friendly_loss": float(lost[i].mean()),
                     "cochannel_loss": float(cochan[i].mean()), "failsafe_count": m["failsafe_count"],
                     "failsafe_ms": m["failsafe_ms"], "max_outage_ms": m["max_outage_ms"],
                     "channel_ok_frac": m["channel_ok_frac"]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/e9_multidrone.yaml")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    tasks = [(cfg, cfg["rate"], s, M, leak, j, t, 0.0) for s in cfg["schemes"] for M in cfg["drones"]
             for leak in cfg["leakage"] for j in cfg["jammers"] for t in range(cfg["trials"])]
    tasks += [(cfg, rate, "proposed", cfg["offset_drones"], leak, "none", t, frac)
              for rate in cfg["offset_rates"] for frac in cfg["offset_fracs"] for leak in cfg["leakage"]
              for t in range(cfg["trials"]) if frac > 0 or rate != cfg["rate"]]
    rows = []
    with Pool(args.workers) as pool:
        for rr in tqdm(pool.imap_unordered(run_trial, tasks), total=len(tasks), mininterval=5):
            rows += rr
    out = result_dir(cfg["name"], cfg)
    pd.DataFrame(rows).to_parquet(out / f"{git_commit()}.parquet", index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
