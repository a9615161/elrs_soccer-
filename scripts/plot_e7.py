"""E7 plots: reacquisition delay after failsafe outages, failsafe time vs burst length."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result  # noqa: E402
from scripts.plot_e1 import INK, MUTED  # noqa: E402  (applies rcParams)

PROTO = {"stock": dict(color="#2a78d6", marker="o", label="Stock"),
         "expctr": dict(color="#eb6834", marker="s", label="ExpCtr", linestyle="--"),
         "proposed": dict(color="#1baf7a", marker="^", label="Proposed")}
RATES = ["F1000Hz", "F500Hz", "500Hz", "333HzFull", "250Hz", "150Hz", "100HzFull", "50Hz"]


def excess_samples(g, failsafe_only=True):
    out = [np.asarray(e)[np.asarray(f, bool)] if failsafe_only else np.asarray(e)
           for e, f in zip(g.excess_ms, g.gap_failsafe) if len(e)]
    return np.concatenate(out) if out else np.array([])


def bootstrap_ci(x, q, n=1000, rng=np.random.default_rng(0)):
    if len(x) == 0:
        return np.nan, np.nan
    b = [np.percentile(rng.choice(x, len(x)), q) for _ in range(n)]
    return np.percentile(b, 2.5), np.percentile(b, 97.5)


def reacq_summary(df):
    rows = []
    for (rate, proto), g in df.groupby(["rate", "protocol"]):
        x = excess_samples(g)
        lo50, hi50 = bootstrap_ci(x, 50)
        lo99, hi99 = bootstrap_ci(x, 99)
        rows.append({"rate": rate, "protocol": proto, "failsafe_events": len(x),
                     "p50_ms": np.percentile(x, 50) if len(x) else np.nan, "p50_ci": f"[{lo50:.0f}, {hi50:.0f}]",
                     "p99_ms": np.percentile(x, 99) if len(x) else np.nan, "p99_ci": f"[{lo99:.0f}, {hi99:.0f}]",
                     "max_ms": x.max() if len(x) else np.nan,
                     "failsafe_s_total": g.failsafe_ms.sum() / 1000, "runs": len(g)})
    return pd.DataFrame(rows)


def main(exp="e7_burst", group_col="ge.burst", fixed=None, xlabel="Mean burst length (slots)"):
    path = latest_result(exp, "")
    df = pd.read_parquet(path)
    out = path.parent / "plots"
    out.mkdir(exist_ok=True)

    s = reacq_summary(df)
    s.to_csv(out / f"{exp}_reacq_summary.csv", index=False)
    with pd.option_context("display.width", 200):
        print(s.round(1).to_string(index=False))

    # 1. CDF of reacquisition delay after failsafe outages
    fig, axes = plt.subplots(2, 4, figsize=(12, 5.6), sharey=True)
    axes = axes.ravel()
    for ax, rate in zip(axes, RATES):
        for p, st in PROTO.items():
            x = np.sort(excess_samples(df[(df.rate == rate) & (df.protocol == p)]))
            if len(x):
                ax.step(np.concatenate(([0], x)), np.concatenate(([0], np.arange(1, len(x) + 1) / len(x))),
                        where="post", color=st["color"], linestyle=st.get("linestyle", "-"), label=st["label"])
        ax.set_xscale("symlog", linthresh=10)
        ax.set_title(rate, color=INK, loc="left", fontsize=10)
        ax.set_xlabel("Extra delay after channel recovers (ms)")
    axes[0].set_ylabel("CDF over failsafe outages")
    axes[4].set_ylabel("CDF over failsafe outages")
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(out / f"{exp}_reacq_cdf.png")
    plt.close(fig)

    # 2. Failsafe time per 30 s run vs burst length (or other group column)
    sub = df if fixed is None else df.query(fixed)
    fig, axes = plt.subplots(2, 4, figsize=(12, 5.6), sharey=True)
    axes = axes.ravel()
    for ax, rate in zip(axes, RATES):
        for p, st in PROTO.items():
            g = sub[(sub.rate == rate) & (sub.protocol == p)].groupby(group_col).failsafe_ms.mean() / 1000
            ax.plot(g.index, g.values, color=st["color"], marker=st["marker"], linestyle=st.get("linestyle", "-"),
                    label=st["label"], markeredgecolor="white")
        ax.set_title(rate, color=INK, loc="left", fontsize=10)
        ax.set_xlabel(xlabel)
        if group_col == "ge.burst":
            ax.set_xscale("log")
    axes[0].set_ylabel("Failsafe time per 30 s run (s)")
    axes[4].set_ylabel("Failsafe time per 30 s run (s)")
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(out / f"{exp}_failsafe_time.png")
    plt.close(fig)
    print(f"plots -> {out}")


if __name__ == "__main__":
    main(fixed="`ge.err` == 0.3")
