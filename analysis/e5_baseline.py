"""E5: does the simulator reproduce ExpressLRS 4.1.0 timing and state logic?

Checks (each compared against configs/elrs_baseline.yaml / the cited source lines):
  1. slot period and hop points: channel changes only every hop_interval packets and follows
     the FHSS sequence built from the UID
  2. SYNC packets: only on the sync channel; spacing >= SyncPktIntervalConnected while connected
  3. LQ = valid packets in the last 100 slots; mean LQ vs i.i.d. PER 0..90 %
  4. failsafe: full blackout -> disconnect exactly DisconnectTimeoutMs after the last valid
     packet; no failsafe under i.i.d. PER <= 90 % in 60 s
  5. reconnect after blackout needs a SYNC on the sync channel (TX switches to the fast sync
     interval after tx_rx_lost_ms without telemetry)
  6. tentative -> connected passes the PFD filters and LQ > minLqForChaos (rx_main.cpp L2118)
  7. with the rate not locked the RX cycles RF modes while disconnected (rx_main.cpp L1622-1651)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import RESULTS  # noqa: E402
from sim import phy  # noqa: E402
from sim.linksim import Scenario, run  # noqa: E402


def check_rate(rate: str, seeds: int) -> dict:
    r = phy.rate(rate)
    H, P = r["hop_interval"], r["period_us"]
    res = run(Scenario(protocol="stock", rate=rate, duration_s=60, seed=1, record=True))
    tr = res.trace
    ch, sync = tr["ch"], tr["is_sync"]
    n = len(ch)
    change = np.flatnonzero(np.diff(ch.astype(int)) != 0) + 1
    hop_ok = bool(np.all((change + tr["nonce0"]) % H == 0))
    sync_slots = np.flatnonzero(sync)
    sync_on_sync_ch = bool(np.all(ch[sync_slots] == r["sync_channel"]))
    spacing_ms = np.diff(sync_slots) * P / 1000
    out = {
        "rate": rate, "slots_60s": n, "expected_slots": int(60e6 // P),
        "hop_changes_only_on_boundary": hop_ok,
        "sync_count_60s": int(len(sync_slots)), "sync_only_on_sync_channel": sync_on_sync_ch,
        "sync_min_spacing_ms": float(spacing_ms.min()) if len(spacing_ms) else None,
        "sync_interval_connected_ms": r["sync_interval_connected_ms"],
        "failsafe_clean": res.metrics["failsafe_count"],
    }

    # LQ vs PER
    lq_rows = []
    for per in np.round(np.arange(0, 1.0, 0.1), 2):
        lqs, fs = [], 0
        for s in range(seeds):
            rr = run(Scenario(protocol="stock", rate=rate, duration_s=60, seed=100 + s, per=float(per), record=True))
            lq = rr.trace["lq"]
            lqs.append(lq[r["lq_window"]:].mean())
            fs += rr.metrics["failsafe_count"]
        lq_rows.append({"rate": rate, "per": float(per), "lq_mean": float(np.mean(lqs)),
                        "lq_expected": 100 * (1 - per) * (1 - 1 / r["tlm_ratio"]), "failsafe_total": fs,
                        "runs": seeds})

    # Full blackout from 10 s to 20 s
    t0, t1 = int(10e6 // P), int(20e6 // P)
    extra = np.zeros(n, bool)
    extra[t0:t1] = True
    rr = run(Scenario(protocol="stock", rate=rate, duration_s=60, seed=3, extra_loss=extra, record=True))
    delivered, st = rr.trace["delivered"], rr.trace["rx_state"]
    last_valid = t0 - 1 - int(np.argmax(delivered[:t0][::-1]))
    disc_at = t0 + int(np.argmax(st[t0:] == 2))
    reconn = t1 + int(np.argmax(delivered[t1:]))
    out.update({
        "blackout_disconnect_after_ms": (disc_at - last_valid) * P / 1000,
        "disconnect_timeout_ms": r["disconnect_timeout_ms"],
        "blackout_reconnect_delay_ms": (reconn - t1) * P / 1000,
        "first_sync_after_blackout_ms": (int(np.flatnonzero(rr.trace["is_sync"][t1:])[0]) * P / 1000
                                          if rr.trace["is_sync"][t1:].any() else None),
    })
    # Tentative -> connected and the RF-mode cycle, over repeated blackouts
    blk = {"start_s": 5, "dur_s": r["disconnect_timeout_ms"] / 1000 + 1}
    locked, unlocked, tent = [], [], []
    for s in range(seeds * 4):
        a = run(Scenario(protocol="stock", rate=rate, duration_s=45, seed=200 + s, blackout=blk, record=True))
        b = run(Scenario(protocol="stock", rate=rate, duration_s=45, seed=200 + s, blackout=blk, lock_on_first=False))
        locked.append(a.metrics["recovery_ms"])
        unlocked.append(b.metrics["recovery_ms"])
        tent += a.trace["connect_slots"]
    out.update({
        "min_lq_connect": r["min_lq_connect"], "tentative_to_connected_slots_min": int(min(tent)),
        "tentative_to_connected_slots_median": float(np.median(tent)),
        "reconnect_locked_ms_median": float(np.nanmedian(locked)),
        "reconnect_unlocked_ms_median": float(np.nanmedian(unlocked)),
        "reconnect_unlocked_never": int(np.isnan(unlocked).sum()),
    })
    return out, lq_rows


def main():
    out = RESULTS / "e5_baseline"
    (out / "plots").mkdir(parents=True, exist_ok=True)
    checks, lq = [], []
    for rate in phy.all_rates():
        c, l = check_rate(rate, seeds=5)
        checks.append(c)
        lq += l
        print(json.dumps(c, indent=1))
    pd.DataFrame(checks).to_csv(out / "plots" / "e5_checks.csv", index=False)
    pd.DataFrame(lq).to_csv(out / "plots" / "e5_lq_vs_per.csv", index=False)
    print(pd.DataFrame(lq).pivot(index="per", columns="rate", values="lq_mean").round(1))
    print(pd.DataFrame(lq).groupby("rate").failsafe_total.sum())


if __name__ == "__main__":
    main()
