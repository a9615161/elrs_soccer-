"""Plots + summary for N3 (reads parquet only). New critical-channel resync vs stock / stocksync.

  (A) recovery p99 vs blackout length (500 Hz, FLRC 1000 Hz): proposed COASTs through short
      outages and recovers via per-frame sync beyond its clock-trust budget.
  (B) RX-reboot recovery p99 by rate: stock -> stocksync (sync always) -> proposed, and the
      TX-sync-per-frame n_s = 1/2/4 tradeoff.
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
    "lines.markersize": 6, "legend.frameon": False, "savefig.dpi": 200,
})
PROTO = {"stock": dict(color="#2a78d6", marker="o", label="Stock-4"),
         "stocksync": dict(color="#eda100", marker="s", label="Stock-4-sync"),
         "proposed": dict(color="#1baf7a", marker="^", label="Proposed (new)")}


def _latest(exp, suffix=""):
    fs = sorted((RESULTS / exp).glob(f"*{suffix}.parquet"), key=lambda p: p.stat().st_mtime)
    fs = [f for f in fs if "_cost" not in f.name]
    return fs[-1]


def p99(x):
    x = np.asarray([v for v in x if v == v], float)
    return np.percentile(x, 99) if len(x) else np.nan


def main():
    out = RESULTS / "n3_blackout" / "plots"
    out.mkdir(exist_ok=True)
    bo = pd.read_parquet(_latest("n3_blackout"))
    bo = bo[bo.drift_ppm == 50]
    rb = pd.read_parquet(_latest("n3_reboot"))

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11.5, 4.4))

    # (A) recovery vs blackout length, 500 Hz (solid) and FLRC 1000 Hz (dashed)
    for rate, ls in [("500Hz", "-"), ("F1000Hz", "--")]:
        d = bo[bo.rate == rate]
        for proto, st in PROTO.items():
            g = d[d.protocol == proto].groupby("blackout.dur_s")["recovery_ms"].apply(p99)
            axA.plot(g.index, g.values, color=st["color"], ls=ls, marker=st["marker"],
                     label=f"{st['label']} · {rate}" if rate == "500Hz" else None)
    axA.axvline(2.5, color=MUTED, ls=":", lw=1)
    axA.text(2.55, axA.get_ylim()[1] * 0.9, "DisconnectTimeout", fontsize=7.5, color=MUTED)
    axA.axhline(1000, color="#c0392b", ls=":", lw=1)
    axA.text(0.06, 1080, "1 s tender stop", fontsize=7.5, color="#c0392b")
    axA.set_xlabel("blackout length (s)")
    axA.set_ylabel("RC recovery time p99 (ms)")
    axA.set_title("A. Recovery vs blackout  (solid 500 Hz, dashed FLRC 1000 Hz)", loc="left",
                  color=INK, fontsize=9.5)
    axA.legend(fontsize=7.5, loc="upper left")

    # (B) RX reboot recovery vs rate: stock, stocksync, proposed n_s 1/2/4
    rates = ["F1000Hz", "500Hz", "250Hz", "150Hz", "50Hz"]
    x = np.arange(len(rates))
    base = {p: [p99(rb[(rb.protocol == p) & (rb.n_sync == 1) & (rb.rate == r)]["recovery_ms"]) for r in rates]
            for p in ("stock", "stocksync")}
    axB.plot(x, base["stock"], color=PROTO["stock"]["color"], marker="o", label="Stock-4")
    axB.plot(x, base["stocksync"], color=PROTO["stocksync"]["color"], marker="s", label="Stock-4-sync")
    greens = ["#8fd9bf", "#3fbf93", "#0e7a54"]
    for ns, col in zip((1, 2, 4), greens):
        y = [p99(rb[(rb.protocol == "proposed") & (rb.n_sync == ns) & (rb.rate == r)]["recovery_ms"]) for r in rates]
        axB.plot(x, y, color=col, marker="^", label=f"Proposed n_s={ns}")
    axB.axhline(1000, color="#c0392b", ls=":", lw=1)
    axB.text(0, 1080, "1 s tender stop", fontsize=7.5, color="#c0392b")
    axB.set_xticks(x)
    axB.set_xticklabels(rates, rotation=20)
    axB.set_ylabel("RX-reboot recovery p99 (ms)")
    axB.set_title("B. RX reboot: sync-always + COAST, and the n_s tradeoff", loc="left",
                  color=INK, fontsize=9.5)
    axB.legend(fontsize=7.5, loc="upper left", ncol=2)

    fig.tight_layout()
    p = out / "n3_recovery.png"
    fig.savefig(p)
    print("wrote", p)

    # summary CSV: blackout recovery p99 + reboot n_s sweep
    rows = []
    for rate in ["F1000Hz", "500Hz", "250Hz", "150Hz"]:
        for dur in [1, 2.6, 3, 5, 10]:
            s = bo[(bo.rate == rate) & np.isclose(bo["blackout.dur_s"], dur)]
            rows.append({"metric": "blackout_recovery_p99_ms", "rate": rate, "dur_s": dur,
                         **{p: round(p99(s[s.protocol == p]["recovery_ms"]), 1)
                            for p in ("stock", "stocksync", "proposed")}})
    pd.DataFrame(rows).to_csv(out / "n3_summary.csv", index=False)
    print("wrote", out / "n3_summary.csv")


if __name__ == "__main__":
    main()
