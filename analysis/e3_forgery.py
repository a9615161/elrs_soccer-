"""E3: forgery, replay and cross-drone tests.

Proposed (libproto): random forged packets against a receiver searching W candidate
nonces with a t-bit tag; acceptance compared with 1-(1-2^-t)^W ~= W*2^-t (99 % binomial
interval). Replay of recorded packets after d slots, for an RX that did / did not receive
the original. Cross-drone: drone A's packets offered to drone B.
Stock (ExpressLRS CRC14, elrs_ota.py): same tests; the CRC initialiser comes from UID4/UID5,
which every SYNC packet broadcasts, and only an 8-bit nonce is bound.
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
from sim.baselines import elrs_ota, elrs_stock  # noqa: E402


def forgery_proposed(rng, t_bits, window, attempts, center=10_000):
    link = proto_ffi.Link(rng.integers(0, 256, 16, dtype=np.uint8).tobytes(), 1, t_bits)
    pk = rng.integers(0, 256, size=(attempts, 8), dtype=np.uint8)
    acc = 0
    for i in range(attempts):
        ok, _, _ = link.open_window(center, window, proto_ffi.NO_SLOT, pk[i].tobytes())
        acc += ok
    return acc


def forgery_stock_random(rng, attempts):
    init = elrs_ota.crc_init(*rng.integers(0, 256, 2))
    pk = rng.integers(0, 256, size=(attempts, 8), dtype=np.uint8)
    pk[:, 0] = (pk[:, 0] & 0xFC) | 1  # RC packets
    nonce = int(rng.integers(256))
    return sum(elrs_ota.valid(p.tobytes(), init, nonce) for p in pk)


def binom_ci(k, n, conf=0.99):
    lo = stats.beta.ppf((1 - conf) / 2, k, n - k + 1) if k > 0 else 0.0
    hi = stats.beta.ppf(1 - (1 - conf) / 2, k + 1, n - k)
    return lo, hi


def replay_proposed(rng, delays, window):
    """For each delay d: (accepted if RX had received the original, accepted if it had not)."""
    key = rng.integers(0, 256, 16, dtype=np.uint8).tobytes()
    tx, rx = proto_ffi.Link(key, 1, 14), proto_ffi.Link(key, 1, 14)
    out = []
    for d in delays:
        s0 = 100_000
        pkt = tx.seal(s0, rng.integers(0, 256, 8, dtype=np.uint8).tobytes())
        now = s0 + d
        # (a) RX received the original and kept receiving: last_accepted = now - 1, LOCKED (W=1)
        a_locked = rx.open_window(now, 1, now - 1, pkt)[0]
        # (b) RX missed the original and everything since (worst case: LOST, window W,
        #     last accepted long ago)
        b_lost = rx.open_window(now, window, s0 - 10_000, pkt)[0]
        out.append((d, a_locked, b_lost))
    return out


def replay_stock(rng, delays, hop_intervals=(4, 2)):
    """Stock RC packet sealed with nonce n0 replayed d slots later (RX nonce = n0 + d).
    acc_crc: CRC valid regardless of channel. joint[H]: CRC valid and the RX is on the channel the
    packet was recorded on, for a recorder that replays verbatim on that one channel."""
    init = elrs_ota.crc_init(*rng.integers(0, 256, 2))
    n0 = int(rng.integers(256))
    seq = elrs_stock.build_sequence(elrs_stock.uid_seed(rng.integers(0, 256, 6, dtype=np.uint8).tobytes()))
    s0 = int(rng.integers(100_000))
    pkt = elrs_ota.seal(bytes([1]) + rng.integers(0, 256, 7, dtype=np.uint8).tobytes(), init, n0)
    sync = elrs_ota.seal(bytes([2]) + rng.integers(0, 256, 7, dtype=np.uint8).tobytes(), init, n0)
    rows = []
    for d in delays:
        crc = elrs_ota.valid(pkt, init, n0 + d)
        joint = {h: crc and seq[(s0 // h) % len(seq)] == seq[((s0 + d) // h) % len(seq)] for h in hop_intervals}
        rows.append((d, crc, elrs_ota.valid(sync, init, n0 + d), joint))
    return rows


def consecutive_table():
    """Expected time for k consecutive forged frames to pass (one try per slot, W = 1)."""
    rows = []
    for t in (14, 16, 24, 32):
        for k in (1, 2, 3, 4):
            for rate, hz in (("500Hz", 500), ("F1000Hz", 1000)):
                rows.append({"t": t, "k": k, "rate": rate, "per_try": 2.0 ** (-t * k),
                             "expected_s": 2.0 ** (t * k) / hz})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/e3_forgery.yaml")
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    rng = np.random.default_rng(cfg["seed"])
    out = result_dir(cfg["name"], cfg)
    commit = git_commit()

    rows = []
    for t in cfg["tag_bits"]:
        for w in cfg["windows"]:
            n = cfg["attempts"][t]
            acc = forgery_proposed(rng, t, w, n)
            theory = 1 - (1 - 2.0**-t) ** w
            lo, hi = binom_ci(acc, n)
            rows.append({"scheme": "proposed", "t": t, "W": w, "attempts": n, "accepted": acc,
                         "rate": acc / n, "theory": theory, "ci99_lo": lo, "ci99_hi": hi,
                         "theory_in_ci": lo <= theory <= hi})
            print(f"t={t:2d} W={w:2d}: {acc}/{n} = {acc / n:.3e}  theory {theory:.3e}  in99CI={lo <= theory <= hi}")
    n = cfg["attempts_stock"]
    acc = forgery_stock_random(rng, n)
    lo, hi = binom_ci(acc, n)
    rows.append({"scheme": "stock_random", "t": 14, "W": 1, "attempts": n, "accepted": acc, "rate": acc / n,
                 "theory": 2.0**-14, "ci99_lo": lo, "ci99_hi": hi, "theory_in_ci": lo <= 2.0**-14 <= hi})
    pd.DataFrame(rows).to_parquet(out / f"{commit}_forgery.parquet", index=False)

    delays = sorted({int(x) for x in np.unique(np.round(np.logspace(0, 4, 60)))} | {256, 512, 768, 1024, 2560} |
                    {960 * k for k in range(1, 11)} | {480 * k for k in range(1, 21)} |
                    {3840 * k for k in range(1, 3)})
    rep = []
    for trial in tqdm(range(cfg["replay_trials"]), desc="replay"):
        for w in cfg["windows"]:
            for d, a, b in replay_proposed(rng, delays, w):
                rep.append({"scheme": "proposed", "W": w, "trial": trial, "d": d, "acc_locked": a, "acc_lost": b})
        for d, rc, sy, joint in replay_stock(rng, delays):
            rep.append({"scheme": "stock", "W": 1, "trial": trial, "d": d, "acc_locked": rc, "acc_lost": rc,
                        "acc_sync": sy, "acc_joint_h4": joint[4], "acc_joint_h2": joint[2]})
    pd.DataFrame(rep).to_parquet(out / f"{commit}_replay.parquet", index=False)

    # Cross-drone: A's valid packets offered to B (same field key, different drone_id)
    key = rng.integers(0, 256, 16, dtype=np.uint8).tobytes()
    cross = 0
    n_cross = cfg["cross_attempts"]
    for i in range(n_cross):
        a, b = proto_ffi.Link(key, i % 10, 14), proto_ffi.Link(key, (i % 10 + 1) % 10, 14)
        pkt = a.seal(5000 + i, rng.integers(0, 256, 8, dtype=np.uint8).tobytes())
        cross += b.open_window(5000 + i, max(cfg["windows"]), proto_ffi.NO_SLOT, pkt)[0]
    # Stock: drones bound with different UIDs; A's packet passes B's CRC by chance only
    cross_stock = 0
    for i in range(n_cross):
        ia, ib = elrs_ota.crc_init(*rng.integers(0, 256, 2)), elrs_ota.crc_init(*rng.integers(0, 256, 2))
        nn = int(rng.integers(256))
        pkt = elrs_ota.seal(bytes([1]) + rng.integers(0, 256, 7, dtype=np.uint8).tobytes(), ia, nn)
        cross_stock += elrs_ota.valid(pkt, ib, nn)
    pd.DataFrame([{"scheme": "proposed", "attempts": n_cross, "accepted": cross,
                   "window": max(cfg["windows"]), "theory": max(cfg["windows"]) * 2.0**-14},
                  {"scheme": "stock", "attempts": n_cross, "accepted": cross_stock, "window": 1,
                   "theory": 2.0**-14}]).to_parquet(out / f"{commit}_cross.parquet", index=False)
    (out / "plots").mkdir(exist_ok=True)
    consecutive_table().to_csv(out / "plots" / "e3_consecutive.csv", index=False)
    print(f"cross-drone accepted: proposed {cross}/{n_cross}, stock {cross_stock}/{n_cross}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
