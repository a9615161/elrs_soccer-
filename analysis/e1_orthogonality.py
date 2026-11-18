"""E1: friendly-collision, uniformity and adjacent-channel statistics of three hop schemes.

stock    - ExpressLRS v4.1.0 UID-derived sequence, one random UID + start phase per drone
random   - each drone draws an i.i.d. uniform channel per slot
proposed - libproto PRP: channel = P_slot(drone_id) under K_hop from the field session key

Outputs data/results/e1_orthogonality/<commit>_pairs.parquet  (per trial x scheme x M)
    and data/results/e1_orthogonality/<commit>_drone.parquet  (per trial x scheme x drone)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.common import git_commit, load_yaml, result_dir  # noqa: E402
from sim import proto_ffi  # noqa: E402
from sim.baselines import elrs_stock  # noqa: E402


def gen_stock(rng, m, n_slots, n_ch, cfg):
    out = np.empty((m, n_slots), dtype=np.uint8)
    for d in range(m):
        uid = rng.integers(0, 256, size=6, dtype=np.uint8).tobytes()
        seq = elrs_stock.build_sequence(elrs_stock.uid_seed(uid), n_ch)
        phase = int(rng.integers(len(seq))) if cfg["stock"]["random_phase"] else 0
        out[d] = seq[(phase + np.arange(n_slots)) % len(seq)]
    return out


def gen_random(rng, m, n_slots, n_ch, cfg):
    return rng.integers(0, n_ch, size=(m, n_slots), dtype=np.uint8)


def gen_proposed(rng, m, n_slots, n_ch, cfg):
    sk = rng.integers(0, 256, size=16, dtype=np.uint8).tobytes()
    p = proto_ffi.Proto(sk, cfg["field_id"].encode())
    slot0 = int(rng.integers(0, 2**62))
    return np.stack([p.hop_sequence(slot0, n_slots, d, n_ch) for d in range(m)])


def gen_proposed_g2(rng, m, n_slots, n_ch, cfg):
    """Guard-spaced PRP (spacing 2). Supports at most N // 2 drones; returns fewer rows
    than requested when m exceeds that, and larger M are skipped."""
    sk = rng.integers(0, 256, size=16, dtype=np.uint8).tobytes()
    p = proto_ffi.Proto(sk, cfg["field_id"].encode())
    slot0 = int(rng.integers(0, 2**62))
    m = min(m, n_ch // 2)
    return np.stack([p.hop_sequence_spaced(slot0, n_slots, d, n_ch, 2) for d in range(m)])


def _proto(rng, cfg):
    sk = rng.integers(0, 256, size=16, dtype=np.uint8).tobytes()
    return proto_ffi.Proto(sk, cfg["field_id"].encode()), int(rng.integers(0, 2**62))


def _gen_prp(rounds):
    def gen(rng, m, n_slots, n_ch, cfg):
        p, slot0 = _proto(rng, cfg)
        return np.stack([p.hop_sequence_rounds(slot0, n_slots, d, n_ch, rounds) for d in range(m)])
    return gen


def _gen_gap(gap):
    """Gap transformation: the joint assignment depends on M, so it is generated per M
    (see PER_M). Returns no rows when M * gap > N."""
    def gen(rng, m, n_slots, n_ch, cfg):
        if m * gap > n_ch:
            return np.empty((0, n_slots), dtype=np.uint8)
        p, slot0 = _proto(rng, cfg)
        return p.hop_gap_block(slot0, n_slots, n_ch, m, gap)
    return gen


GENERATORS = {"stock": gen_stock, "random": gen_random, "proposed": gen_proposed,
              "proposed_g2": gen_proposed_g2,
              "prp_r4": _gen_prp(4), "prp_r8": _gen_prp(8), "gap1": _gen_gap(1),
              "gap2": _gen_gap(2), "gap3": _gen_gap(3)}
PER_M = {"gap1", "gap2", "gap3"}


def theory_any_collision(m: int, n: int) -> float:
    return 1.0 - np.prod([1 - k / n for k in range(m)])


def theory_drone_clean(m: int, n: int) -> float:
    """Independent random: P(a given drone shares its slot's channel with nobody)."""
    return (1 - 1 / n) ** (m - 1)


def pair_stats(seqs: np.ndarray, m: int, n_ch: int) -> dict:
    s = seqs[:m].astype(np.int64)
    n_slots = s.shape[1]
    # occ[t, c] = number of drones on channel c in slot t
    flat = (np.arange(n_slots)[None, :] * n_ch + s).ravel()
    occ = np.bincount(flat, minlength=n_slots * n_ch).reshape(n_slots, n_ch)
    # auto[delta] = ordered drone pairs with ch_b - ch_a == delta (mod N), self pairs removed
    f = np.fft.fft(occ, axis=1)
    auto = np.rint(np.fft.ifft((f * f.conj()).sum(axis=0)).real).astype(np.int64)
    auto[0] -= n_slots * m
    return {
        "n_slots": n_slots,
        "slots_any_collision": int((occ > 1).any(axis=1).sum()),
        "pair_slots": n_slots * m * (m - 1) // 2,
        "collision_pairs": int((occ * (occ - 1) // 2).sum()),
        "adjacent_pairs": int((occ[:, :-1] * occ[:, 1:]).sum()),  # same slot, |ch_a - ch_b| == 1
        "drone_slots": n_slots * m,
        "drone_slots_clean": int((occ == 1).sum()),  # drone alone on its channel
        "channels_busy": int((occ > 0).sum()),
        # Leakage: attacker sees drone a's channel, guesses drone b's as ch_a + delta (mod N)
        # with the best fixed delta. Lower bound on an optimal attacker for non
        # rotation-invariant schemes. Pooled over all ordered pairs, and for pair (0, 1).
        "pred_pool_hits": int(auto.max()),
        "pred_pool_trials": n_slots * m * (m - 1),
        "pred_01_hits": int(np.bincount((s[1] - s[0]) % n_ch, minlength=n_ch).max()),
    }


def drone_stats(seq: np.ndarray, n_ch: int) -> dict:
    counts = np.bincount(seq, minlength=n_ch)
    chi2, p = stats.chisquare(counts)
    step = np.abs(np.diff(seq.astype(np.int16)))
    return {
        "chi2": float(chi2),
        "chi2_p": float(p),
        "self_repeat": int((step == 0).sum()),  # consecutive slots on the same channel
        "self_adjacent": int((step == 1).sum()),  # consecutive slots on neighbouring channels
        "self_steps": int(step.size),
        "counts": counts.tolist(),
    }


def expand_cases(cfg: dict) -> list[tuple[int, list[int]]]:
    """[(N, [M...])]. Either a single `n_channels` + `drones`, or `cases` (list of N)
    + `load` (M/N fractions; M = round(load*N), at least 2, at most N)."""
    if "cases" not in cfg:
        return [(cfg["n_channels"], cfg["drones"])]
    out = []
    for n in cfg["cases"]:
        ms = sorted({min(n, max(2, round(f * n))) for f in cfg["load"]})
        out.append((n, ms))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/e1_orthogonality.yaml")
    ap.add_argument("--trials", type=int, help="override trials (quick runs)")
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    if args.trials:
        cfg["trials"] = args.trials
    n_slots = cfg["n_slots"]
    pair_rows, drone_rows = [], []

    for n_ch, drones in expand_cases(cfg):
        m_max = max(drones)
        for scheme in cfg["schemes"]:
            for trial in tqdm(range(cfg["trials"]), desc=f"N={n_ch} {scheme}"):
                seed = [cfg["seed"], n_ch, cfg["schemes"].index(scheme), trial]
                gen = GENERATORS[scheme]
                seqs = None if scheme in PER_M else gen(np.random.default_rng(seed), m_max, n_slots, n_ch, cfg)
                drone_seqs = seqs  # per-drone stats: largest feasible M for PER_M schemes
                for m in drones:  # ascending
                    if scheme in PER_M:
                        seqs = gen(np.random.default_rng(seed + [m]), m, n_slots, n_ch, cfg)
                        drone_seqs = seqs if len(seqs) else drone_seqs
                    if m > len(seqs):  # scheme cannot host this many drones
                        continue
                    pair_rows.append({"scheme": scheme, "trial": trial, "N": n_ch, "M": m,
                                      "load": m / n_ch,
                                      "theory_any_collision": theory_any_collision(m, n_ch),
                                      "theory_drone_clean": theory_drone_clean(m, n_ch),
                                      **pair_stats(seqs, m, n_ch)})
                for d in range(len(drone_seqs)):
                    drone_rows.append({"scheme": scheme, "trial": trial, "N": n_ch, "drone": d,
                                       **drone_stats(drone_seqs[d], n_ch)})

    out = result_dir(cfg["name"], cfg)
    commit = git_commit()
    pd.DataFrame(pair_rows).to_parquet(out / f"{commit}_pairs.parquet", index=False)
    pd.DataFrame(drone_rows).to_parquet(out / f"{commit}_drone.parquet", index=False)
    print(f"wrote {out}/{commit}_{{pairs,drone}}.parquet")


if __name__ == "__main__":
    main()
