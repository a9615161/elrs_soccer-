"""Plots + summary for N4 (reads parquet only). Full new-mechanism stack, M links, N=79.

  (A) per-drone PDR vs field size M, with and without adjacent-channel leakage.
  (B) friendly loss vs shared-base offset (M=10): orthogonal until the offset passes the guard,
      then it degrades gracefully; leakage sets a floor that motivates the gap transform.
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
from analysis.common import RESULTS  # noqa: E402

INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3de"
plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "lines.linewidth": 2,
    "lines.markersize": 7, "legend.frameon": False, "savefig.dpi": 200,
})
OFF = "#1baf7a"   # leakage off
ON = "#eb6834"    # leakage on


def _latest():
    fs = sorted((RESULTS / "n4_multidrone").glob("*.parquet"), key=lambda p: p.stat().st_mtime)
    return fs[-1]


def main():
    df = pd.read_parquet(_latest())
    out = RESULTS / "n4_multidrone" / "plots"
    out.mkdir(exist_ok=True)
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11.5, 4.4))

    # (A) PDR vs M (aligned), leakage off / on; min and mean over drones
    al = df[df.offset_frac == 0.0]
    for leak, col, lab in [(False, OFF, "no leakage"), (True, ON, "adjacent leakage")]:
        g = al[al.leakage == leak].groupby("M")["pdr"]
        axA.plot(g.mean().index, g.mean().values * 100, color=col, marker="^", label=f"{lab} (mean)")
        axA.plot(g.min().index, g.min().values * 100, color=col, marker="v", ls="--", alpha=0.7,
                 label=f"{lab} (worst drone)")
    axA.set_xlabel("drones in the field  M")
    axA.set_ylabel("per-drone PDR (%)")
    axA.set_ylim(80, 101)
    axA.set_title("A. Per-drone PDR vs field size (aligned)", loc="left", color=INK)
    axA.legend(fontsize=8, loc="lower left")

    # (B) friendly loss vs offset (M=10)
    os_ = df[df.offset_frac > 0]
    P_us = 2000.0
    for leak, col, lab in [(False, OFF, "no leakage"), (True, ON, "adjacent leakage")]:
        g = os_[os_.leakage == leak].groupby("offset_frac")["friendly_loss"].mean()
        axB.plot(g.index * 100, g.values * 100, color=col, marker="o", label=lab)
    guard = (2000.0 - 1507.0) / P_us * 100   # (P - TOA)/P as % of a slot
    axB.axvline(guard, color=MUTED, ls=":", lw=1)
    axB.text(guard + 1, axB.get_ylim()[1] * 0.5, "guard  (P−TOA)/P", fontsize=7.5, color=MUTED, rotation=90)
    axB.set_xlabel("shared-base offset  (% of a slot)")
    axB.set_ylabel("friendly loss per drone per slot (%)")
    axB.set_title("B. Friendly loss vs slot-base offset  (M=10)", loc="left", color=INK)
    axB.legend(fontsize=8, loc="upper left")

    fig.tight_layout()
    p = out / "n4_multidrone.png"
    fig.savefig(p)
    print("wrote", p)

    rows = []
    for leak in (False, True):
        for M in sorted(al.M.unique()):
            s = al[(al.leakage == leak) & (al.M == M)]
            rows.append({"leakage": leak, "M": int(M), "pdr_mean": round(s.pdr.mean(), 5),
                         "pdr_worst": round(s.pdr.min(), 5), "friendly_loss": round(s.friendly_loss.mean(), 5)})
    pd.DataFrame(rows).to_csv(out / "n4_summary.csv", index=False)
    print("wrote", out / "n4_summary.csv")


if __name__ == "__main__":
    main()
