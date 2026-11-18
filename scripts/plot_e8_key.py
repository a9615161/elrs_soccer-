"""E8 key combinations (200 seeds) and the narrowband sync-channel jammer: summary tables."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result  # noqa: E402


def main():
    k = latest_result("e8_key", "")
    (k.parent / "plots").mkdir(exist_ok=True)
    d = pd.read_parquet(k)
    a = d.groupby(["rate", "jammer.type", "jammer.duty", "protocol"]).agg(
        runs=("pdr", "size"), failsafe_s=("failsafe_ms", lambda x: x.mean() / 1000),
        max_outage_s=("max_outage_ms", lambda x: x.mean() / 1000), pdr=("pdr", "mean"),
        unrecovered=("unrecovered_at_end_ms", lambda x: (x > 0).mean())).reset_index()
    a.to_csv(k.parent / "plots" / "e8_key_summary.csv", index=False)
    s = latest_result("e8_syncjam", "")
    (s.parent / "plots").mkdir(exist_ok=True)
    e = pd.read_parquet(s)
    b = e.groupby(["rate", "protocol"]).agg(
        runs=("pdr", "size"), recovered=("recovered", "mean"), recovery_ms=("recovery_ms", "median"),
        failsafe_s=("failsafe_ms", lambda x: x.mean() / 1000), pdr=("pdr", "mean"),
        beacons_ok=("beacons_ok", "mean")).reset_index()
    b.to_csv(s.parent / "plots" / "e8_syncjam_summary.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 300):
        print(a[a.protocol != "expctr"].round(3).to_string(index=False))
        print(b.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
