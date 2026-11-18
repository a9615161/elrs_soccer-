"""E3 plots: measured forgery rate vs theory; replay acceptance vs delay."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result  # noqa: E402
from scripts.plot_e1 import INK, MUTED  # noqa: E402

TCOL = {8: "#2a78d6", 12: "#eb6834", 14: "#eda100", 16: "#1baf7a"}


def main():
    f = latest_result("e3_forgery", "_forgery")
    out = f.parent / "plots"
    out.mkdir(exist_ok=True)
    df = pd.read_parquet(f)
    p = df[df.scheme == "proposed"]
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ws = np.array([1, 2, 4, 8, 16, 32, 64])
    for t, g in p.groupby("t"):
        ax.plot(ws, 1 - (1 - 2.0**-t) ** ws, color=TCOL[t], linestyle="--", linewidth=1.2)
        ax.errorbar(g.W, g.rate, yerr=[g.rate - g.ci99_lo, g.ci99_hi - g.rate], fmt="o", color=TCOL[t],
                    markeredgecolor="white", capsize=3, label=f"t = {t} bit (measured, 99% CI)")
    ax.plot([], [], color=MUTED, linestyle="--", label="theory 1-(1-2^-t)^W")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Nonce window W")
    ax.set_ylabel("Random forgery acceptance rate")
    ax.set_title("E3 forgery rate vs window", color=INK, loc="left")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "e3_forgery_vs_W.png")
    plt.close(fig)

    r = pd.read_parquet(f.with_name(f.name.replace("_forgery", "_replay")))
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    s = r[r.scheme == "stock"].groupby("d")[["acc_locked", "acc_sync"]].mean()
    ax.plot(s.index, s.acc_locked, "o", color="#2a78d6", label="Stock RC packet", markeredgecolor="white")
    ax.plot(s.index, s.acc_sync * 0.97, "s", color="#eb6834", markersize=4, label="Stock SYNC packet")
    for w, c in ((16, "#1baf7a"), (64, "#008300")):
        g = r[(r.scheme == "proposed") & (r.W == w)].groupby("d")[["acc_locked", "acc_lost"]].mean()
        ax.plot(g.index, g.acc_lost, "^", color=c, markeredgecolor="white",
                label=f"Proposed, RX in LOST, W={w}")
    g = r[r.scheme == "proposed"].groupby("d").acc_locked.mean()
    ax.plot(g.index, g.values, "v", color="#6250d6", markeredgecolor="white", label="Proposed, RX LOCKED (any W)")
    ax.set_xscale("log")
    ax.set_xlabel("Replay delay d (slots)")
    ax.set_ylabel("Fraction of replays accepted")
    ax.set_title("E3 replay acceptance", color=INK, loc="left")
    ax.legend(fontsize=7, loc="center right")
    fig.tight_layout()
    fig.savefig(out / "e3_replay.png")
    print(f"plots -> {out}")


if __name__ == "__main__":
    main()
