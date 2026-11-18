"""N1: coordination cost vs friendly collision for four hopping schemes.

Reframes E1/E9's "0 vs 10.7%" into a cost-vector-vs-collision comparison (revised plan,
part 三 N1 詳細設計). Four schemes, each reporting a cost vector that is NOT collapsed to a
single score; instead we mark which schemes are dominated.

  C0 獨立跳頻   stock-4 / independent random, no coordination, N=80 set, ~10.7% co-channel
  C1 靜態分頻   each drone a fixed disjoint subset (~N/M channels), hops within it, 0 collision
  C2 Proposed   shared small-domain PRP table over N=79, ground-station beacon aligns the slots
  C3 機上 PRP   same channels as C2 (identical collision), on-board K_hop: differs only in cost

The collision test is E9's (overlap |(k-m)P + Δoff| < TOA and same channel), so numbers stay
consistent with e9_multidrone. The K/ε sweep adds a per-slot drift offset that resets every K
slots at the beacon: relative offset between two drones ramps to 2·ε·1e-6·P·K over an interval,
and once it passes the guard P-TOA the PRP's same-slot orthogonality no longer prevents a
neighbour-slot co-channel hit, so C2/C3 collision rises toward C0.

Run:  make lib && .venv/bin/python analysis/n1_coordination_cost.py [--config configs/n1_coordination.yaml]
Out:  data/results/n1_coordination/<commit>.parquet          (collision vs M / K / ε, per scheme)
      data/results/n1_coordination/<commit>_cost.parquet     (cost vector per scheme, M=10)
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

from analysis.common import RESULTS, git_commit, load_yaml, result_dir  # noqa: E402
from sim import phy, proto_ffi  # noqa: E402
from sim.baselines import elrs_stock  # noqa: E402

N_FULL = 80   # C0/C1: full ISM2G4 set
N_PROP = 79   # C2/C3: Proposed excludes the one critical channel
SCHEMES = ["c0_stock", "c0_random", "c1_static", "c2_proposed", "c3_onboard"]
ALIGN_ONCE = 0  # sentinel for "beacon only once at the start" (K = whole run)


def _h(*parts) -> int:
    return int.from_bytes(hashlib.sha256(repr(parts).encode()).digest()[:8], "little")


def gen_channels(scheme: str, M: int, n: int, H: int, rng) -> np.ndarray:
    """Per-slot channel of every drone, shape (M, n). Channels change every H slots (a hop)."""
    hops = n // H + 2
    idx = np.arange(n) // H
    if scheme == "c0_random":
        h = rng.integers(0, N_FULL, size=(M, hops), dtype=np.uint8)
        return h[:, idx]
    if scheme == "c0_stock":
        ch = np.empty((M, n), np.uint8)
        for i in range(M):
            uid = rng.integers(0, 256, 6, dtype=np.uint8).tobytes()
            seq = elrs_stock.build_sequence(elrs_stock.uid_seed(uid), N_FULL)
            s0 = int(rng.integers(len(seq)))
            ch[i] = seq[(s0 + idx) % len(seq)]
        return ch
    if scheme == "c1_static":
        perm = rng.permutation(N_FULL)
        size = N_FULL // M
        ch = np.empty((M, n), np.uint8)
        for i in range(M):
            sub = perm[i * size:(i + 1) * size] if i < M - 1 else perm[i * size:]
            ch[i] = sub[rng.integers(0, len(sub), size=hops)][idx]
        return ch
    # c2_proposed / c3_onboard: identical channels (same PRP), differ only in cost
    p = proto_ffi.Proto(rng.integers(0, 256, 16, dtype=np.uint8).tobytes(), b"field-n1")
    h0 = int(rng.integers(0, 2**40))
    h = np.empty((M, hops), np.uint8)
    for i in range(M):
        h[i] = p.hop_sequence(h0, hops, i, N_PROP)
    return h[:, idx]


def drift_offsets(scheme: str, M: int, n: int, P: float, eps_ppm: float, K: int, rng) -> np.ndarray:
    """Per-slot time offset o[M, n] (µs). Aligned schemes reset to ~0 every K slots and drift
    at ±eps between beacons; unaligned schemes keep a fixed random phase."""
    if scheme == "c0_random" or scheme == "c1_static":
        return np.zeros((M, n))                       # aligned grid / disjoint: offset irrelevant
    if scheme == "c0_stock":
        return np.repeat(rng.uniform(0, P, M)[:, None], n, axis=1)  # independent phase, never aligned
    # c2 / c3: beacon every K slots (K=0 -> align once), then drift at sign·eps ppm
    sign = rng.choice([-1.0, 1.0], size=M)
    k = np.arange(n)
    since = k % K if K else k                         # slots since last beacon
    rate = eps_ppm * 1e-6 * P                         # µs of offset gained per slot
    return sign[:, None] * (since[None, :] * rate)


def cochannel(ch: np.ndarray, off: np.ndarray, P: float, toa: float) -> np.ndarray:
    """E9's collision test, generalised to per-slot offsets. Returns per-drone-per-slot collided."""
    M, n = ch.shape
    k = np.arange(n)
    coll = np.zeros((M, n), bool)
    for i, j in itertools.permutations(range(M), 2):
        doff = off[i] - off[j]                         # (n,)
        base = np.floor(doff / P).astype(int)
        for dm in (base, base + 1):
            m = k + dm
            valid = (m >= 0) & (m < n)
            mc = np.clip(m, 0, n - 1)
            dt = (k - m) * P + doff
            same = valid & (np.abs(dt) < toa) & (ch[i] == ch[j, mc])
            coll[i] |= same
    return coll


def run_point(args) -> dict:
    cfg, scheme, M, eps, K = args
    r = phy.rate(cfg["rate"])
    P, toa, H = r["period_us"], r["airtime_us"], r["hop_interval"]
    n = cfg["n_slots"]
    if K:
        n = int(min(max(3 * K, cfg["n_slots"]), cfg["n_slots_max"]))
    rng = np.random.default_rng(_h(cfg["seed"], scheme, M, eps, K))
    rates = []
    for t in range(cfg["trials"]):
        tr = np.random.default_rng(_h(cfg["seed"], scheme, M, eps, K, t))
        ch = gen_channels(scheme, M, n, H, tr)
        off = drift_offsets(scheme, M, n, P, eps, K, tr)
        rates.append(cochannel(ch, off, P, toa).mean())
    return {"scheme": scheme, "M": M, "eps_ppm": eps, "K": K, "n_slots": n,
            "cochannel": float(np.mean(rates)), "cochannel_sd": float(np.std(rates))}


def cost_vector(cfg: dict) -> pd.DataFrame:
    """Analytic cost vector per scheme at M=10 (does not depend on the drift sim)."""
    r = phy.rate(cfg["rate"])
    P = r["period_us"]
    M = cfg["cost_M"]
    L_min = int(60e6 / P)                              # slots per minute (allocation table length)
    # per-hop PRF cost: C2 table is pre-computed on the ground (0 on-board), C3 computes on-board.
    rows = [
        dict(scheme="c0_stock",   hop_set=N_FULL,        provision_bytes=0,
             runtime_airtime=0.0,  needs_gs=False, onboard_prf_per_hop=0.0,
             tx_reboot_rejoin_s=float("nan"), flash_leak="n/a",
             note="UID-derived LCG; no coordination"),
        dict(scheme="c0_random",  hop_set=N_FULL,        provision_bytes=0,
             runtime_airtime=0.0,  needs_gs=False, onboard_prf_per_hop=0.0,
             tx_reboot_rejoin_s=float("nan"), flash_leak="n/a",
             note="i.i.d. channel; no coordination"),
        dict(scheme="c1_static",  hop_set=N_FULL // M,   provision_bytes=int(np.ceil(N_FULL / M)),
             runtime_airtime=0.0,  needs_gs=False, onboard_prf_per_hop=0.0,
             tx_reboot_rejoin_s=0.0, flash_leak="own subset only",
             note="disjoint subset per drone; no alignment needed"),
        dict(scheme="c2_proposed", hop_set=N_PROP,       provision_bytes=int(np.ceil(L_min * 7 / 8)),
             runtime_airtime=None, needs_gs=True, onboard_prf_per_hop=0.0,
             tx_reboot_rejoin_s=None, flash_leak="own column only",
             note="shared PRP allocation table, ground beacon aligns slots (L=1 min)"),
        dict(scheme="c3_onboard", hop_set=N_PROP,        provision_bytes=16,
             runtime_airtime=None, needs_gs=True, onboard_prf_per_hop=cfg.get("c3_prf_per_hop", 2.89),
             tx_reboot_rejoin_s=None, flash_leak="whole field (K_hop)",
             note="on-board K_hop; one flash read exposes every drone's channels"),
    ]
    df = pd.DataFrame(rows)
    # K-dependent costs for the aligned schemes (airtime 1/K, reboot rejoin K·P)
    ks = [k for k in cfg["beacon_K"] if k]
    extra = []
    for _, row in df[df.needs_gs].iterrows():
        for K in ks:
            extra.append(dict(scheme=row["scheme"], K=K, beacon_airtime=1.0 / K,
                              tx_reboot_rejoin_s=K * P / 1e6, hop_set=row["hop_set"]))
    return df, pd.DataFrame(extra)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "n1_coordination.yaml"))
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    cfg = load_yaml(a.config)

    # (1) collision vs M for every scheme at alignment (K = first beacon interval, ε from first value)
    tasks = [(cfg, s, M, cfg["eps_ppm"][0], cfg["beacon_K"][0]) for s in SCHEMES for M in cfg["drones"]]
    # (2) drift sweep for the aligned Proposed schemes: M=cost_M, K × ε grid
    tasks += [(cfg, s, cfg["cost_M"], eps, K)
              for s in ("c2_proposed", "c3_onboard")
              for eps in cfg["eps_ppm"] for K in cfg["beacon_K"]]
    seen = set()
    uniq = [t for t in tasks if (t[1], t[2], t[3], t[4]) not in seen and not seen.add((t[1], t[2], t[3], t[4]))]

    with Pool(a.workers) as pool:
        rows = list(tqdm(pool.imap(run_point, uniq), total=len(uniq), desc="n1"))
    df = pd.DataFrame(rows)

    out = result_dir("n1_coordination", cfg)
    commit = git_commit()
    df.to_parquet(out / f"{commit}.parquet")
    cost, cost_k = cost_vector(cfg)
    cost.to_parquet(out / f"{commit}_cost.parquet")
    cost_k.to_parquet(out / f"{commit}_cost_k.parquet")

    # console summary
    pd.set_option("display.width", 200)
    al = df[(df.M == cfg["cost_M"]) & (df.K == cfg["beacon_K"][0]) & (df.eps_ppm == cfg["eps_ppm"][0])]
    print(f"\n== aligned co-channel (M={cfg['cost_M']}, per drone per slot) ==")
    print(al.set_index("scheme")["cochannel"].mul(100).round(3).to_string(), " (%)")
    print("\n== C2 drift sweep: co-channel (%) vs K (cols) × ε (rows) ==")
    piv = (df[df.scheme == "c2_proposed"].pivot_table(index="eps_ppm", columns="K", values="cochannel") * 100)
    print(piv.round(3).to_string())
    print("\nwrote", out / f"{commit}.parquet")


if __name__ == "__main__":
    main()
