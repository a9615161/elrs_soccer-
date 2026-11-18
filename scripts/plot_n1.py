"""Plots + summary for N1 (reads parquet only; never re-runs). Cost-vector vs friendly collision.

  (A) co-channel probability vs drone count M, four schemes (aligned)
  (B) cost-collision: beacon airtime vs co-channel for the aligned Proposed scheme, one drift
      curve per residual ε over the beacon interval K; C0 / C1 placed at the zero-airtime floor,
      each point annotated with its hopping-set size.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.common import RESULTS, git_commit  # noqa: E402

EXP = "n1_coordination"
STYLE = {
    "c0_stock":   dict(color="#2a78d6", marker="o", label="C0 Stock-4"),
    "c0_random":  dict(color="#eb6834", marker="s", label="C0 independent random"),
    "c1_static":  dict(color="#eda100", marker="v", label="C1 static division"),
    "c2_proposed": dict(color="#1baf7a", marker="^", label="C2 Proposed (shared PRP)"),
    "c3_onboard": dict(color="#6250d6", marker="X", label="C3 on-board PRP"),
}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3de"
plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "lines.linewidth": 2,
    "lines.markersize": 7, "legend.frameon": False, "savefig.dpi": 200,
})


def _latest(suffix=""):
    files = sorted((RESULTS / EXP).glob(f"*{suffix}.parquet"), key=lambda p: p.stat().st_mtime)
    files = [f for f in files if "_cost" not in f.name] if not suffix else files
    return files[-1]


def main():
    df = pd.read_parquet(_latest())
    cost = pd.read_parquet(_latest("_cost"))
    hop = cost.set_index("scheme")["hop_set"].to_dict()
    K0 = int(df.K[df.K > 0].min())
    eps0 = int(df.eps_ppm.min())
    out = RESULTS / EXP / "plots"
    out.mkdir(exist_ok=True)

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11.5, 4.4))

    # (A) collision vs M, aligned (K=K0, eps=eps0)
    al = df[(df.K == K0) & (df.eps_ppm == eps0)]
    for s in ["c0_stock", "c0_random", "c1_static", "c2_proposed", "c3_onboard"]:
        d = al[al.scheme == s].sort_values("M")
        if not len(d):
            continue
        st = STYLE[s]
        axA.plot(d.M, d.cochannel * 100, color=st["color"], marker=st["marker"], label=st["label"])
    axA.set_xlabel("drones in the field  M")
    axA.set_ylabel("friendly co-channel per drone per hop (%)")
    axA.set_title("A. Collision vs field size (slots aligned)", loc="left", color=INK)
    axA.legend(fontsize=8)

    # (B) cost-collision: x = beacon airtime (1/K), y = collision; C2 curve per eps across K.
    c2 = df[df.scheme == "c2_proposed"].copy()
    c2 = c2[c2.K > 0]
    c2["airtime"] = 1.0 / c2.K
    al10 = al[al.M == 10].set_index("scheme")["cochannel"] * 100
    xmin, xmax = c2.airtime.min() * 100, c2.airtime.max() * 100
    # C0 needs no airtime but never avoids collision: draw as reference lines across the panel.
    for s in ("c0_stock", "c0_random"):
        axB.axhline(float(al10[s]), color=STYLE[s]["color"], ls="-.", lw=1.3, alpha=0.75)
    axB.text(xmax, float(al10["c0_random"]) + 0.2, "C0 no coordination  (hop set 80)",
             fontsize=8, color=STYLE["c0_random"]["color"], ha="right", va="bottom")
    # C2 drift curves, one per residual eps
    eps_styles = {2: ("#1baf7a", "-"), 10: ("#eda100", "--"), 50: ("#eb6834", ":")}
    for eps, (col, ls) in eps_styles.items():
        d = c2[c2.eps_ppm == eps].sort_values("airtime")
        axB.plot(d.airtime * 100, d.cochannel * 100, color=col, ls=ls, marker="^",
                 label=f"ε = {eps} ppm")
    # C1 at the zero-airtime floor (left band)
    floor = xmin / 5
    axB.axvspan(floor / 2.2, floor * 1.6, color=GRID, alpha=0.6)
    axB.scatter([floor], [0], color=STYLE["c1_static"]["color"], marker="v", zorder=5)
    axB.annotate("C1 static\nhop set 8", (floor, 0), xytext=(floor, 2.0), fontsize=7.5,
                 color=STYLE["c1_static"]["color"], ha="center",
                 arrowprops=dict(arrowstyle="-", color=STYLE["c1_static"]["color"], lw=0.8))
    axB.text(floor, -1.3, "airtime 0", fontsize=7.5, color=MUTED, ha="center")
    axB.set_xscale("log")
    axB.set_xlim(floor / 3, xmax * 1.5)
    axB.set_ylim(-1.8, float(al10["c0_stock"]) + 1.2)
    axB.set_xlabel("beacon airtime  1/K  (%)    — cheaper ←")
    axB.set_ylabel("friendly co-channel per drone per hop (%)")
    axB.set_title("B. Cost vs collision  (M=10, LoRa 500 Hz)", loc="left", color=INK)
    axB.legend(fontsize=8, loc="center right", title="C2 Proposed drift")
    axB.annotate("C2 / C3 reach 0 (hop set 79);\nC3 = 16 B vs C2 26 KB, but leaks whole field",
                 (xmax, 3.3), fontsize=7.5, color=STYLE["c2_proposed"]["color"], ha="right", va="top")

    fig.tight_layout()
    p = out / "n1_cost_collision.png"
    fig.savefig(p)
    print("wrote", p)

    # summary CSV: aligned collision + cost
    summ = al[al.M == 10][["scheme", "cochannel"]].copy()
    summ["cochannel_pct"] = (summ.cochannel * 100).round(3)
    summ = summ.merge(cost[["scheme", "hop_set", "provision_bytes", "needs_gs", "flash_leak"]], on="scheme")
    summ.drop(columns="cochannel").to_csv(out / "n1_summary.csv", index=False)
    print("wrote", out / "n1_summary.csv")


if __name__ == "__main__":
    main()
