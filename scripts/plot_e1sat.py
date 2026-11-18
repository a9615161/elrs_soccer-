"""Plots + summary for E1 saturation sweep (load M/N up to 1.0 over several N)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result, wilson  # noqa: E402
from scripts.plot_e1 import INK, MUTED, STYLE, _line  # noqa: E402  (also applies rcParams)

EXP = "e1_saturation"
DOMAIN = {13: "EU868", 20: "AU915", 40: "FCC915", 80: "ISM2G4"}


def main():
    pairs_path = latest_result(EXP, "_pairs")
    pairs = pd.read_parquet(pairs_path)
    out = pairs_path.parent / "plots"
    out.mkdir(exist_ok=True)

    keys = ["scheme", "N", "M"]
    agg = pairs.groupby(keys, sort=False).sum(numeric_only=True).reset_index()
    first = pairs.groupby(keys, sort=False)[["load", "theory_any_collision", "theory_drone_clean"]].first()
    agg[first.columns] = first.values
    agg["p_clean"] = agg.drone_slots_clean / agg.drone_slots
    agg["p_clean_lo"], agg["p_clean_hi"] = wilson(agg.drone_slots_clean, agg.drone_slots)
    agg["p_any"] = agg.slots_any_collision / agg.n_slots
    agg["p_any_lo"], agg["p_any_hi"] = wilson(agg.slots_any_collision, agg.n_slots)
    agg["p_adj"] = agg.adjacent_pairs / agg.pair_slots
    agg["p_adj_lo"], agg["p_adj_hi"] = wilson(agg.adjacent_pairs, agg.pair_slots)
    agg["pred_01"] = agg.pred_01_hits / agg.n_slots
    agg["pred_01_lo"], agg["pred_01_hi"] = wilson(agg.pred_01_hits, agg.n_slots)
    agg["pred_pool"] = agg.pred_pool_hits / agg.pred_pool_trials
    agg["pred_pool_lo"], agg["pred_pool_hi"] = wilson(agg.pred_pool_hits, agg.pred_pool_trials)
    agg["ideal_pred"] = 1 / (agg.N - 1)
    agg["busy_frac"] = agg.channels_busy / (agg.n_slots * agg.N)

    ns = sorted(agg.N.unique())
    rows = [
        ("p_clean", "theory_drone_clean", "Drone-slots free of\nfriendly collision"),
        ("p_adj", None, "Pairs on adjacent\nchannels (|Δch|=1)"),
        ("pred_01", "ideal_pred", "Guess drone 1 from\ndrone 0, pair (0,1)"),
        ("pred_pool", "ideal_pred", "Guess another drone,\npooled over pairs"),
    ]
    fig, axes = plt.subplots(len(rows), len(ns), figsize=(3.0 * len(ns), 2.6 * len(rows)),
                             sharex=True, sharey="row", squeeze=False)
    for j, n in enumerate(ns):
        for i, (col, theory, ylabel) in enumerate(rows):
            ax = axes[i, j]
            if theory:
                th = agg[(agg.scheme == "random") & (agg.N == n)]
                ax.plot(th.load, th[theory], color=MUTED, linestyle="--", linewidth=1.5,
                        label="Theory (random / ideal PRP)", zorder=2)
            for s in STYLE:
                d = agg[(agg.scheme == s) & (agg.N == n)]
                if len(d):
                    _line(ax, d.load, d[col], d[f"{col}_lo"], d[f"{col}_hi"], s)
            if i == 0:
                ax.set_title(f"N={n} ({DOMAIN.get(n, '')})", color=INK, loc="left", fontsize=10)
            if j == 0:
                ax.set_ylabel(ylabel)
            if i == len(rows) - 1:
                ax.set_xlabel("Load M/N")
    axes[0, 0].set_ylim(0, 1.03)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out / "e1sat_grid.png")
    plt.close(fig)

    cols = ["scheme", "N", "M", "load", "p_clean", "p_any", "p_adj", "pred_01", "pred_pool",
            "ideal_pred", "busy_frac"]
    summary = agg[cols]
    summary.to_csv(out / "e1sat_summary.csv", index=False)
    with pd.option_context("display.width", 180, "display.float_format", "{:.4f}".format):
        for title, sel in (("Full load (M = N)", summary.load >= 0.999),
                           ("Load ~0.3", summary.load.between(0.25, 0.35))):
            print(title + ":")
            print(summary[sel].sort_values(["N", "scheme"]).to_string(index=False))
            print()
    print(f"\nplots -> {out}")


if __name__ == "__main__":
    main()
