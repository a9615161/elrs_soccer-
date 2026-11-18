"""E6 plot: minimum nonce window vs outage length, and where re-lock becomes impossible."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result  # noqa: E402
from scripts.plot_e1 import INK  # noqa: E402

PPM = {10: dict(color="#2a78d6", marker="o"), 20: dict(color="#eb6834", marker="s"),
       50: dict(color="#1baf7a", marker="^")}


def main():
    f = latest_result("e6_drift", "")
    out = f.parent / "plots"
    out.mkdir(exist_ok=True)
    d = pd.read_parquet(f)
    g = d.groupby(["rate", "ppm", "L"]).agg(outage_s=("outage_ms", lambda x: x.iloc[0] / 1000),
                                            no_relock=("offset", lambda x: x.isna().mean()),
                                            min_w=("min_w", "max")).reset_index()
    g.to_csv(out / "e6_summary.csv", index=False)
    rates = ["F1000Hz", "F500Hz", "500Hz", "333HzFull", "250Hz", "150Hz", "100HzFull", "50Hz"]
    fig, axes = plt.subplots(2, len(rates), figsize=(20, 5.4), sharex="col", sharey="row")
    for j, rate in enumerate(rates):
        for ppm, st in PPM.items():
            s = g[(g.rate == rate) & (g.ppm == ppm)]
            ok = s[s.no_relock == 0]
            axes[0, j].step(ok.outage_s, ok.min_w, where="post", color=st["color"], label=f"±{ppm} ppm")
            axes[0, j].plot(ok.outage_s, ok.min_w, st["marker"], color=st["color"], markersize=4)
            axes[1, j].plot(s.outage_s, s.no_relock, marker=st["marker"], color=st["color"], markersize=4,
                            markeredgecolor="white", label=f"±{ppm} ppm")
        axes[0, j].set_title(rate, color=INK, loc="left", fontsize=10)
        axes[1, j].set_xscale("log")
        axes[1, j].set_xlabel("Outage length (s)")
    axes[0, 0].set_ylabel("Minimum window W\n(all trials re-lock)")
    axes[1, 0].set_ylabel("Fraction of trials that\ncannot re-lock (wrong hop)")
    axes[0, 0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "e6_min_window.png")
    print(f"plots -> {out}")


if __name__ == "__main__":
    main()
