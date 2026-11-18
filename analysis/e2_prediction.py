"""E2: hop-sequence prediction.

Attackers (success = predicting the channel of the next hop):
  stock_sync    - NCC-Group-style: one captured SYNC packet gives fhssIndex, UID4, UID5
                  (OTA.h L28-39). The seed is UID[2..5] (OTA.cpp L41-45), so 2^16 candidates
                  remain; each observed hop prunes them. Prediction = plurality vote.
  block_excl    - channel-only attacker exploiting stock's structure: every 80-hop block is
                  a permutation starting with the sync channel, so guess uniformly among
                  channels not yet seen in the current block.
  markov        - generic channel-only attacker: first-order transition counts learned online
                  (falls back to least-recently-used channel).
Targets: stock (UID-derived) and proposed (gap transform g=2, attacker knows the algorithm
and Field ID but not the session key).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import git_commit, load_yaml, result_dir  # noqa: E402
from sim import proto_ffi  # noqa: E402
from sim.baselines import elrs_stock  # noqa: E402

N, SYNC, L = 80, 40, 240


def build_sequences_batch(seeds: np.ndarray) -> np.ndarray:
    """Vectorised FHSSrandomiseFHSSsequenceBuild for many seeds -> (len(seeds), 240) uint8."""
    k = len(seeds)
    base = np.array([SYNC if i % N == 0 else (0 if i % N == SYNC else i % N) for i in range(L)], np.uint8)
    seq = np.tile(base, (k, 1))
    st = seeds.astype(np.uint64)
    rows = np.arange(k)
    for i in range(L):
        if i % N == 0:
            continue
        st = ((np.uint64(214013) * st + np.uint64(2531011)) & np.uint64(0xFFFFFFFF)) % np.uint64(2147483648)
        r = ((st >> np.uint64(16)) % np.uint64(N - 1)).astype(np.int64) + 1
        j = (i // N) * N + r
        a = seq[:, i].copy()
        seq[:, i] = seq[rows, j]
        seq[rows, j] = a
    return seq


def attack_stock_sync(rng, cand_cache, k_max):
    """Returns (success[k] for k = 0..k_max observed hops after the sync, hops to unique seed)."""
    uid = rng.integers(0, 256, 6, dtype=np.uint8)
    true = elrs_stock.build_sequence(elrs_stock.uid_seed(bytes(uid)))
    low16 = (int(uid[4]) << 8) | (int(uid[5]) ^ elrs_stock.OTA_VERSION_ID)
    if low16 not in cand_cache:
        hi = np.arange(65536, dtype=np.uint64) << np.uint64(16)
        cand_cache.clear()
        cand_cache[low16] = build_sequences_batch(hi | np.uint64(low16))
    cands = cand_cache[low16]
    p = int(rng.integers(L))  # fhssIndex in the captured sync
    alive = np.ones(len(cands), bool)
    succ = np.zeros(k_max + 1, bool)
    unique_at = -1
    for k in range(k_max + 1):
        nxt = (p + k + 1) % L
        votes = np.bincount(cands[alive, nxt], minlength=N)
        succ[k] = votes.argmax() == true[nxt]
        alive &= cands[:, nxt] == true[nxt]  # attacker now observes hop p+k+1
        # LCG works mod 2^31, so seeds differing only in bit 31 (UID2 bit 7) give the same
        # sequence: "recovered" = every remaining candidate yields the true sequence
        if unique_at < 0 and (cands[alive] == true).all():
            unique_at = k + 1
            succ[k + 1:] = True
            break
    return succ, unique_at


def predictor_hits(seq: np.ndarray, kind: str) -> np.ndarray:
    """hit[i] = predictor guessed seq[i] from seq[:i]."""
    hit = np.zeros(len(seq), bool)
    if kind == "block_excl":
        seen = np.zeros(N, bool)
        rng = np.random.default_rng(int(seq[:8].sum()))
        for i in range(len(seq)):
            if i > 0 and seq[i - 1] == SYNC:  # sync channel marks a block start
                seen[:] = False
                seen[SYNC] = True
            cand = np.flatnonzero(~seen)
            guess = rng.choice(cand) if len(cand) else rng.integers(N)
            hit[i] = guess == seq[i]
            seen[seq[i]] = True
    elif kind == "markov":
        trans = np.zeros((N, N), np.int32)
        last_used = np.full(N, -1)
        for i in range(len(seq)):
            if i > 0:
                row = trans[seq[i - 1]]
                guess = row.argmax() if row.max() > 0 else int(last_used.argmin())
                hit[i] = guess == seq[i]
                trans[seq[i - 1], seq[i]] += 1
            last_used[seq[i]] = i
    return hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/e2_prediction.yaml")
    ap.add_argument("--trials", type=int)
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    trials = args.trials or cfg["trials"]
    rng = np.random.default_rng(cfg["seed"])
    k_max = cfg["sync_attack_max_hops"]

    rows, unique = [], []
    cache = {}
    for t in tqdm(range(trials), desc="stock_sync"):
        succ, u = attack_stock_sync(rng, cache, k_max)
        unique.append(u)
        rows += [{"target": "stock", "attacker": "stock_sync", "trial": t, "k": k, "hit": bool(s)}
                 for k, s in enumerate(succ)]

    n_hops = cfg["observe_hops"]
    for t in tqdm(range(trials), desc="generic"):
        uid = rng.integers(0, 256, 6, dtype=np.uint8).tobytes()
        stock_seq = elrs_stock.hop_channels(uid, n_hops, start_ptr=int(rng.integers(L)))
        p = proto_ffi.Proto(rng.integers(0, 256, 16, dtype=np.uint8).tobytes(), cfg["field_id"].encode())
        prop_seq = p.hop_gap_block(int(rng.integers(0, 2**40)), n_hops, N, cfg["n_drones"], 2)[0]
        for target, seq in (("stock", stock_seq), ("proposed", prop_seq)):
            for kind in ("block_excl", "markov"):
                hit = predictor_hits(seq, kind)
                # aggregate into observation-length bins to keep the table small
                for k in cfg["k_bins"]:
                    if k < n_hops:
                        rows.append({"target": target, "attacker": kind, "trial": t, "k": k,
                                     "hit": bool(hit[k])})
                rows.append({"target": target, "attacker": kind, "trial": t, "k": -1,
                             "hit_rate_all": float(hit[1:].mean())})

    out = result_dir(cfg["name"], cfg)
    df = pd.DataFrame(rows)
    df.to_parquet(out / f"{git_commit()}.parquet", index=False)
    pd.DataFrame({"unique_after_hops": unique}).to_parquet(out / f"{git_commit()}_unique.parquet", index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
