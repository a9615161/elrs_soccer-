"""Plots + summary table for E1 (reads parquet only; never re-runs the experiment)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result, wilson  # noqa: E402

EXP = "e1_orthogonality"
# Fixed categorical order (dataviz reference palette, slots 1-7); markers give a non-color cue.
# "proposed" is the earlier name of prp_r4 (same scheme, same colour).
STYLE = {
    "stock": dict(color="#2a78d6", marker="o", label="Stock ELRS"),
    "random": dict(color="#eb6834", marker="s", label="Independent random"),
    "prp_r4": dict(color="#1baf7a", marker="^", label="PRP Feistel 4 rounds"),
    "proposed": dict(color="#1baf7a", marker="^", label="Proposed PRP"),
    "prp_r8": dict(color="#eda100", marker="v", label="PRP Feistel 8 rounds"),
    "gap2": dict(color="#e87ba4", marker="D", label="Gap transform g=2"),
    "gap3": dict(color="#008300", marker="P", label="Gap transform g=3"),
    "proposed_g2": dict(color="#6250d6", marker="X", label="PRP + parity, spacing ≥2"),
}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3de"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "lines.linewidth": 2,
    "lines.markersize": 7, "legend.frameon": False, "savefig.dpi": 200,
})


def _line(ax, x, y, lo, hi, scheme):
    st = STYLE[scheme]
    ax.plot(x, y, color=st["color"], marker=st["marker"], label=st["label"],
            markeredgecolor="white", markeredgewidth=1.5, zorder=3)
    ax.fill_between(x, lo, hi, color=st["color"], alpha=0.15, linewidth=0)


def main():
    pairs_path = latest_result(EXP, "_pairs")
    pairs = pd.read_parquet(pairs_path)
    drone = pd.read_parquet(str(pairs_path).replace("_pairs", "_drone"))
    out = pairs_path.parent / "plots"
    out.mkdir(exist_ok=True)

    agg = pairs.groupby(["scheme", "M"], sort=False).sum(numeric_only=True).reset_index()
    agg["theory_any_collision"] = pairs.groupby(["scheme", "M"], sort=False)["theory_any_collision"].first().values
    agg["p_any"] = agg.slots_any_collision / agg.n_slots
    agg["p_any_lo"], agg["p_any_hi"] = wilson(agg.slots_any_collision, agg.n_slots)
    agg["p_pair"] = agg.collision_pairs / agg.pair_slots
    agg["p_adj"] = agg.adjacent_pairs / agg.pair_slots
    agg["p_adj_lo"], agg["p_adj_hi"] = wilson(agg.adjacent_pairs, agg.pair_slots)
    agg["p_le1"] = (agg.collision_pairs + agg.adjacent_pairs) / agg.pair_slots
    if "pred_01_hits" in agg:
        agg["pred_01"] = agg.pred_01_hits / agg.n_slots
        agg["pred_pool"] = agg.pred_pool_hits / agg.pred_pool_trials
    n_ch = len(drone.counts.iloc[0])

    # 1. Friendly collision probability vs M
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    th = agg[agg.scheme == "random"]
    ax.plot(th.M, th.theory_any_collision, color=MUTED, linestyle="--", linewidth=1.5,
            label=r"Theory $1-\prod_{k<M}(1-k/N)$", zorder=2)
    for s in STYLE:
        d = agg[agg.scheme == s]
        if len(d):
            _line(ax, d.M, d.p_any, d.p_any_lo, d.p_any_hi, s)
    ax.set_xlabel("Number of drones M")
    ax.set_ylabel("P(slot has ≥1 friendly collision)")
    ax.set_title(f"E1 friendly collisions (N={n_ch} channels)", color=INK, loc="left")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "e1_collision_vs_M.png")
    plt.close(fig)

    # 2. Adjacent-channel (|Δ|=1, same slot) ratio vs M
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.axhline(2 * (n_ch - 1) / n_ch**2, color=MUTED, linestyle="--", linewidth=1.5,
               label="Uniform-random theory 2(N−1)/N²")
    for s in STYLE:
        d = agg[agg.scheme == s]
        if len(d):
            _line(ax, d.M, d.p_adj, d.p_adj_lo, d.p_adj_hi, s)
    ax.set_xlabel("Number of drones M")
    ax.set_ylabel("Fraction of drone pairs on adjacent channels")
    ax.set_title("E1 adjacent-channel risk (same slot, |Δch| = 1)", color=INK, loc="left")
    ax.set_ylim(0, None)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "e1_adjacent_vs_M.png")
    plt.close(fig)

    # 2b. Leakage: see drone 0's channel, guess drone 1's (best fixed offset)
    if "pred_01" in agg:
        agg["pred_01_lo"], agg["pred_01_hi"] = wilson(agg.pred_01_hits, agg.n_slots)
        fig, ax = plt.subplots(figsize=(6.4, 4.2))
        ax.axhline(1 / (n_ch - 1), color=MUTED, linestyle="--", linewidth=1.5,
                   label="Ideal permutation 1/(N−1)")
        for s in STYLE:
            d = agg[agg.scheme == s]
            if len(d):
                _line(ax, d.M, d.pred_01, d.pred_01_lo, d.pred_01_hi, s)
        ax.set_xlabel("Number of drones M")
        ax.set_ylabel("P(guess drone 1 | drone 0 seen)")
        ax.set_title("E1 leakage: best fixed-offset guess, pair (0,1)", color=INK, loc="left")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out / "e1_leakage_vs_M.png")
        plt.close(fig)

    # 3. Channel usage histogram (drone 0, pooled over trials) as small multiples
    schemes = [s for s in STYLE if s in set(drone.scheme)]
    fig, axes = plt.subplots(len(schemes), 1, figsize=(7.2, 1.9 * len(schemes)), sharex=True, sharey=True)
    for ax, s in zip(np.atleast_1d(axes), schemes):
        c = np.sum(np.stack(drone[(drone.scheme == s) & (drone.drone == 0)].counts.to_numpy()), axis=0)
        frac = c / c.sum()
        ax.bar(np.arange(n_ch), frac, width=0.8, color=STYLE[s]["color"])
        ax.axhline(1 / n_ch, color=MUTED, linestyle="--", linewidth=1)
        ax.set_title(STYLE[s]["label"], color=INK, loc="left", fontsize=10)
        ax.grid(axis="x", visible=False)
    np.atleast_1d(axes)[-1].set_xlabel("Channel index")
    fig.supylabel("Usage fraction (dashed = 1/N)", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "e1_channel_usage.png")
    plt.close(fig)

    # Summary tables
    ds = drone.groupby("scheme", sort=False).agg(
        chi2_p_median=("chi2_p", "median"),
        chi2_p_frac_lt_0_05=("chi2_p", lambda p: float((p < 0.05).mean())),
        self_repeat=("self_repeat", "sum"), self_adjacent=("self_adjacent", "sum"),
        self_steps=("self_steps", "sum"))
    ds["self_repeat_rate"] = ds.self_repeat / ds.self_steps
    ds["self_adjacent_rate"] = ds.self_adjacent / ds.self_steps
    ds = ds.drop(columns=["self_repeat", "self_adjacent", "self_steps"])
    cols = ["scheme", "M", "p_any", "theory_any_collision", "p_pair", "p_adj", "p_le1"]
    cols += [c for c in ("pred_01", "pred_pool") if c in agg]
    summary = agg[cols]
    summary.to_csv(out / "e1_summary_pairs.csv", index=False)
    ds.to_csv(out / "e1_summary_drone.csv")
    with pd.option_context("display.width", 140, "display.float_format", "{:.5f}".format):
        print(summary.to_string(index=False))
        print()
        print(ds.to_string())
    print(f"\nplots -> {out}")


if __name__ == "__main__":
    main()
