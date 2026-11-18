"""E10: feasibility heat maps (deadline-miss rate vs MAC cost c and packet rate) and the
largest c with <= 1 % misses, per window W."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result  # noqa: E402
from scripts.plot_e1 import INK  # noqa: E402
from sim import phy  # noqa: E402

RATES = phy.all_rates()
HOST_MAC_US = 0.25  # tools/bench_siphash.c on the simulation host (Xeon 6140); NOT an ESP32 value


def main():
    f = latest_result("e10_cost", "")
    out = f.parent / "plots"
    out.mkdir(exist_ok=True)
    d = pd.read_parquet(f)
    d["miss_rate"] = d.deadline_miss / (d.rc_sent * d.channel_ok_frac).clip(lower=1)
    g = d.groupby(["ge.err", "window", "rate", "cost_c_us"]).agg(
        miss=("miss_rate", "mean"), pdr=("pdr", "mean"), fs_ms=("failsafe_ms", "mean")).reset_index()
    g.to_csv(out / "e10_summary.csv", index=False)

    # largest c with miss <= 1 %
    thr = []
    for (err, w, rate), s in g.groupby(["ge.err", "window", "rate"]):
        ok = s[s.miss <= 0.01].cost_c_us
        r = phy.rate(rate)
        thr.append({"scenario": "normal" if err == 0 else "resync (GE 200, 20 %)", "W": w, "rate": rate,
                    "slack_us": r["period_us"] - r["airtime_us"] - r["fixed_overhead_us"],
                    "max_c_us_at_1pct": ok.max() if len(ok) else np.nan})
    thr = pd.DataFrame(thr)
    thr.to_csv(out / "e10_threshold.csv", index=False)
    with pd.option_context("display.width", 160):
        print(thr.pivot_table(index=["scenario", "W"], columns="rate", values="max_c_us_at_1pct").to_string())

    panels = [(0.0, 1, "Normal operation (LOCKED)")] + [(0.2, w, f"Resync, W = {w}") for w in (8, 16, 64)]
    fig, axes = plt.subplots(1, len(panels), figsize=(13, 3.4), sharey=True)
    cs = sorted(g.cost_c_us.unique())
    for ax, (err, w, title) in zip(axes, panels):
        m = g[(g["ge.err"] == err) & (g.window == (16 if err == 0 else w))]
        grid = m.pivot(index="rate", columns="cost_c_us", values="miss").reindex(RATES)[cs]
        im = ax.imshow(grid.values, aspect="auto", cmap="Blues", vmin=0, vmax=1, origin="lower")
        ax.set_xticks(range(0, len(cs), 3))
        ax.set_xticklabels([f"{c:g}" for c in cs[::3]])
        ax.set_yticks(range(len(RATES)))
        ax.set_yticklabels(RATES)
        ax.set_xlabel("c = time per MAC/PRF (µs)")
        ax.set_title(title, color=INK, loc="left", fontsize=10)
        # host reference (not ESP32)
        ax.axvline(np.interp(np.log(HOST_MAC_US), np.log(cs), range(len(cs))), color="#e34948", linestyle=":")
    axes[0].set_ylabel("Packet rate")
    fig.colorbar(im, ax=axes, label="Deadline-miss rate", shrink=0.9)
    fig.savefig(out / "e10_feasibility.png", bbox_inches="tight")
    print(f"plots -> {out}")


if __name__ == "__main__":
    main()
