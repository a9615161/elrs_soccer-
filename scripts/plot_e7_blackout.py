"""E7 blackout / reboot plots: time from the end of an outage to the next delivered RC frame."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import latest_result, wilson  # noqa: E402
from scripts.plot_e1 import INK, MUTED  # noqa: E402  (applies rcParams)
from scripts.plot_e7 import PROTO, RATES, bootstrap_ci  # noqa: E402


def summary(d, keys):
    rows = []
    for key, g in d.groupby(keys):
        x = g.recovery_ms.dropna().to_numpy()
        lo, hi = wilson(len(x), len(g))
        l50, h50 = bootstrap_ci(x, 50, n=300)
        l99, h99 = bootstrap_ci(x, 99, n=300)
        rows.append({**dict(zip(keys, key)), "runs": len(g), "recovered_frac": len(x) / len(g),
                     "recovered_lo": lo, "recovered_hi": hi,
                     "p50_ms": np.percentile(x, 50) if len(x) else np.nan, "p50_lo": l50, "p50_hi": h50,
                     "p99_ms": np.percentile(x, 99) if len(x) else np.nan, "p99_lo": l99, "p99_hi": h99,
                     "recovery_over_1s_frac": float((g.recovery_ms.fillna(np.inf) > 1000).mean()),
                     "failsafe_s": g.failsafe_ms.mean() / 1000, "beacons_ok": g.beacons_ok.mean()})
    return pd.DataFrame(rows)


def main():
    path = latest_result("e7_blackout", "")
    out = path.parent / "plots"
    out.mkdir(exist_ok=True)
    d = pd.read_parquet(path)
    s = summary(d, ["rate", "drift_ppm", "blackout.dur_s", "protocol"])
    s.to_csv(out / "e7_blackout_summary.csv", index=False)

    v = s[s.drift_ppm == 50]
    fig, axes = plt.subplots(2, 4, figsize=(12, 5.6), sharex=True, sharey=True)
    axes = axes.ravel()
    for ax, rate in zip(axes, RATES):
        for p, st in PROTO.items():
            g = v[(v.rate == rate) & (v.protocol == p)].sort_values("blackout.dur_s")
            ax.plot(g["blackout.dur_s"], g.p99_ms, color=st["color"], marker=st["marker"],
                    linestyle=st.get("linestyle", "-"), label=st["label"], markeredgecolor="white")
        for x, t in ((1, "1 s"), (phy_disc(rate), "disconnect")):
            ax.axvline(x, color=MUTED, linewidth=1, linestyle=":")
        ax.set_xscale("log")
        ax.set_yscale("symlog", linthresh=10)
        ax.set_title(rate, color=INK, loc="left", fontsize=10)
    for i in (0, 4):
        axes[i].set_ylabel("p99 RC recovery (ms)")
    for ax in axes[4:]:
        ax.set_xlabel("Outage length (s)")
    axes[0].legend(fontsize=8)
    fig.suptitle("E7 recovery after a full-band outage, ±50 ppm. Dotted: 1 s budget, DisconnectTimeout",
                 x=0.01, ha="left", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "e7_blackout_recovery.png")
    plt.close(fig)

    r = latest_result("e7_reboot", "")
    rb = summary(pd.read_parquet(r), ["rate", "protocol"])
    (r.parent / "plots").mkdir(exist_ok=True)
    rb.to_csv(r.parent / "plots" / "e7_reboot_summary.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_rows", 400):
        print(v[v.protocol != "expctr"].pivot_table(index=["rate", "blackout.dur_s"], columns="protocol",
                                                    values=["p50_ms", "p99_ms", "recovered_frac"]).round(1).to_string())
        print(rb.round(2).to_string(index=False))
    print(f"plots -> {out}")


def phy_disc(rate):
    from sim import phy
    return phy.rate(rate)["disconnect_timeout_ms"] / 1000


if __name__ == "__main__":
    main()
