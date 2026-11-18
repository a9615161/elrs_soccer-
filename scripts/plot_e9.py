"""E9 plot: friendly loss and PDR vs number of drones, leakage off / on."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result, wilson  # noqa: E402
from scripts.plot_e1 import INK  # noqa: E402

SCHEME = {"stock": dict(color="#2a78d6", marker="o", label="Stock"),
          "random": dict(color="#eb6834", marker="s", label="Independent random"),
          "proposed": dict(color="#1baf7a", marker="^", label="Proposed (gap g=2)")}


def main():
    f = latest_result("e9_multidrone", "")
    out = f.parent / "plots"
    out.mkdir(exist_ok=True)
    d = pd.read_parquet(f)
    base = d[(d.offset_frac == 0) & (d.rate == "500Hz")]
    keys = ["scheme", "M", "leakage", "jammer"]
    g = base.groupby(keys).agg(friendly=("friendly_loss", "mean"), cochannel=("cochannel_loss", "mean"),
                               pdr=("pdr", "mean"), failsafe_ms=("failsafe_ms", "mean"),
                               worst_failsafe_count=("failsafe_count", "max"),
                               sync_share=("sync_channel_share", "mean"),
                               sync_loss=("sync_channel_loss", "mean")).reset_index()
    g.to_csv(out / "e9_summary.csv", index=False)
    off = d[(d.scheme == "proposed") & (d.jammer == "none") & (d.M == 10)].groupby(
        ["rate", "leakage", "offset_frac"]).agg(friendly=("friendly_loss", "mean"), cochannel=("cochannel_loss", "mean"),
                                                pdr=("pdr", "mean")).reset_index()
    off.to_csv(out / "e9_offset_summary.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 400):
        print(g[g.M == 10].round(4).to_string(index=False))
        print(off[off.leakage].pivot(index="offset_frac", columns="rate", values="friendly").round(4).to_string())
        print(off[~off.leakage].pivot(index="offset_frac", columns="rate", values="friendly").round(4).to_string())
    g = g[g.jammer == "none"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, leak in zip(axes, (False, True)):
        for s, st in SCHEME.items():
            d = g[(g.scheme == s) & (g.leakage == leak)].sort_values("M")
            ax.plot(d.M, d.friendly * 100, color=st["color"], marker=st["marker"], label=st["label"],
                    markeredgecolor="white")
        ax.set_title("adjacent-channel leakage " + ("on (p_adj = 0.5)" if leak else "off"), color=INK,
                     loc="left", fontsize=10)
        ax.set_xlabel("Number of drones M")
        ax.set_xticks([1, 2, 5, 10])
    axes[0].set_ylabel("Packets lost to friendly drones (%)")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "e9_friendly_loss.png")
    plt.close(fig)

    rates = list(off.rate.unique())
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#6b6a64"]
    for ax, leak in zip(axes, (False, True)):
        for rate, color in zip(rates, colors):
            s = off[(off.rate == rate) & (off.leakage == leak)].sort_values("offset_frac")
            ax.plot(s.offset_frac * 100, s.friendly * 100, color=color, marker="o", markersize=4, label=rate)
        ax.set_title("adjacent-channel leakage " + ("on" if leak else "off"), color=INK, loc="left", fontsize=10)
        ax.set_xlabel("Max slot offset between drones (% of period)")
    axes[0].set_ylabel("Packets lost to friendly drones (%)")
    axes[1].legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out / "e9_offset.png")
    print(f"plots -> {out}")


if __name__ == "__main__":
    main()
