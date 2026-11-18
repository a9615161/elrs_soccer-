"""E8 plots: failsafe time and longest outage vs jammer duty cycle, per jammer type."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result  # noqa: E402
from scripts.plot_e1 import INK  # noqa: E402
from scripts.plot_e7 import PROTO, reacq_summary  # noqa: E402

TYPES = ["constant", "sweep", "duty_cycle", "reactive", "selective"]


def main(rate="500Hz", coverage=1.0):
    f = latest_result("e8_jamming", "")
    out = f.parent / "plots"
    out.mkdir(exist_ok=True)
    d = pd.read_parquet(f)
    d["failsafe_s"] = d.failsafe_ms / 1000
    d["max_outage_s"] = d.max_outage_ms / 1000

    agg = d.groupby(["rate", "jammer.type", "jammer.coverage", "jammer.duty", "protocol"]).agg(
        failsafe_s=("failsafe_s", "mean"), max_outage_s=("max_outage_s", "mean"),
        unrecovered=("unrecovered_at_end_ms", lambda x: (x > 0).mean()), pdr=("pdr", "mean")).reset_index()
    agg.to_csv(out / "e8_summary.csv", index=False)
    s = reacq_summary(d[d["jammer.coverage"] == 1.0])
    s.to_csv(out / "e8_reacq_summary.csv", index=False)

    for metric, label, fname in (("failsafe_s", "Failsafe time per 30 s run (s)", "e8_failsafe_vs_duty.png"),
                                 ("max_outage_s", "Longest single outage (s)", "e8_max_outage_vs_duty.png")):
        fig, axes = plt.subplots(1, len(TYPES), figsize=(14, 3.3), sharey=True)
        for ax, jt in zip(axes, TYPES):
            for p, st in PROTO.items():
                g = agg[(agg.rate == rate) & (agg["jammer.type"] == jt) & (agg["jammer.coverage"] == coverage)
                        & (agg.protocol == p)].sort_values("jammer.duty")
                ax.plot(g["jammer.duty"], g[metric], color=st["color"], marker=st["marker"],
                        linestyle=st.get("linestyle", "-"), label=st["label"], markeredgecolor="white")
            ax.set_title(jt, color=INK, loc="left", fontsize=10)
            ax.set_xlabel("Jammer duty cycle")
        axes[0].set_ylabel(label)
        axes[0].legend(fontsize=8)
        fig.suptitle(f"E8 {rate}, coverage {int(coverage * 100)}%", x=0.01, ha="left", color=INK, fontsize=10)
        fig.tight_layout()
        fig.savefig(out / fname)
        plt.close(fig)

    with pd.option_context("display.width", 220):
        t = agg[(agg.rate == rate) & (agg["jammer.coverage"] == coverage)].pivot_table(
            index=["jammer.type", "jammer.duty"], columns="protocol",
            values=["failsafe_s", "max_outage_s", "unrecovered"])
        print(t.round(2).to_string())
        print(agg.groupby(["jammer.coverage", "protocol"]).failsafe_s.mean().unstack().round(3))
        print(s.round(1).to_string(index=False))
    print(f"plots -> {out}")


if __name__ == "__main__":
    main()
