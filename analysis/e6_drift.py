"""E6: clock drift during an outage and the nonce window needed to re-lock.

Timing model (per packet rate), ExpressLRS 4.1.0: TX slot s starts at s*P (true time). A locked
  RX hops and advances its nonce at TOCK, `tock` after the packet end (tock = max(P - 2*TOA,
  200 us), rx_main.cpp L73, L1124), so local slot k spans
      [(k-1)*P + TOA + tock + err, k*P + TOA + tock + err)
  During an outage of L slots the RX free-runs with relative frequency error delta = 2 * ppm * 1e-6
  (TX and RX crystals off in opposite directions = worst case): err = delta * s * P + jitter.
  The RX listens on hop(k // H) during its local slot k. A packet is received only if its
  whole airtime falls inside local slots of the same hop index as the TX hop (s // H).
  The RX's nonce estimate is the local slot containing the end of the packet; the offset
  o = s - est must be inside the window order 0, +1, -1, +2, ... (libproto open_window), so the
  minimum window for that packet is 2o (o > 0), 2|o| + 1 (o < 0), or 1 (o = 0).
Outputs, for each (rate, ppm, L): distribution of o at the first received packet, minimum W
covering all trials, and the fraction of trials where no packet is received within K slots
(clock error too large for any window -> resync beacon needed).
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
from sim import phy, proto_ffi  # noqa: E402


def min_window(o: int) -> int:
    return 1 if o == 0 else (2 * o if o > 0 else 2 * -o + 1)


def first_relock(P, toa, tock, H, delta, L, jitter_us, rng, k_search):
    """Return (offset of first received packet, slots after outage) or (None, None)."""
    jit = rng.normal(0, jitter_us)
    for s in range(L + 1, L + 1 + k_search):
        err = delta * s * P + jit
        k0 = int(np.floor((s * P - toa - tock - err) / P)) + 1
        k1 = int(np.floor((s * P - tock - err) / P)) + 1
        if k0 // H != k1 // H or k1 // H != s // H:
            continue  # RX hopped mid-packet or listens on another hop's channel
        return s - k1, s - L
    return None, None


def counter_bits_table(rates, ppm=50, bits=(8, 12, 16, 20, 24, 32)):
    """Beacon counter of c bits: the RX resolves the high bits from its own clock.

    Unambiguous while the clock error stays under half the counter span; a rebooted RX has no
    clock, so the span itself must exceed the session length."""
    rows = []
    for rate in rates:
        P = phy.rate(rate)["period_us"]
        for c in bits:
            rows.append({"rate": rate, "bits": c,
                         "max_clock_age_s_at_ppm": 2 ** (c - 1) / (2 * ppm * 1e-6) * P / 1e6,
                         "reboot_session_span_h": 2**c * P / 1e6 / 3600})
    return pd.DataFrame(rows)


def verify_with_libproto(rng, offsets, windows):
    """Cross-check min_window() with the real libproto window search."""
    link = proto_ffi.Link(rng.integers(0, 256, 16, dtype=np.uint8).tobytes(), 0, 14)
    for o in offsets:
        pkt = link.seal(10_000 + o, rng.integers(0, 256, 8, dtype=np.uint8).tobytes())
        for w in windows:
            ok = link.open_window(10_000, w, proto_ffi.NO_SLOT, pkt)[0]
            assert ok == (w >= min_window(o)), (o, w, ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/e6_drift.yaml")
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    rng = np.random.default_rng(cfg["seed"])
    verify_with_libproto(rng, range(-6, 7), range(1, 16))

    rows = []
    for rate in cfg["rates"]:
        r = phy.rate(rate)
        P, toa, H, tock = r["period_us"], r["airtime_us"], r["hop_interval"], r["tock_slack_us"]
        for ppm in cfg["ppm"]:
            delta = 2 * ppm * 1e-6
            for L in tqdm(cfg["outage_slots"], desc=f"{rate} {ppm}ppm", mininterval=5):
                for trial in range(cfg["trials"]):
                    sign = 1 if trial % 2 == 0 else -1  # RX fast or slow
                    o, after = first_relock(P, toa, tock, H, sign * delta, L, cfg["jitter_us"], rng, cfg["search_slots"])
                    rows.append({"rate": rate, "ppm": ppm, "L": L, "outage_ms": L * P / 1000, "sign": sign,
                                 "trial": trial, "offset": o, "relock_after_slots": after,
                                 "min_w": None if o is None else min_window(o),
                                 "drift_slots": sign * delta * L})
    out = result_dir(cfg["name"], cfg)
    pd.DataFrame(rows).to_parquet(out / f"{git_commit()}.parquet", index=False)
    (out / "plots").mkdir(exist_ok=True)
    counter_bits_table(cfg["rates"]).to_csv(out / "plots" / "e6_counter_bits.csv", index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
