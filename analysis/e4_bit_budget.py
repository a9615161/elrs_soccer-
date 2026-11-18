"""E4: OTA4 / OTA8 / SYNC bit budget of Stock / ExpCtr / Proposed (ExpressLRS 4.1.0 layouts), and the
airtime cost of moving to OTA8 instead. Pure calculation (no simulation)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import RESULTS  # noqa: E402
from scripts.plot_e1 import INK, MUTED  # noqa: E402
from sim import phy  # noqa: E402

# (label, kind, [(field, bits)], packet_bytes, auth_tag_bits, nonce_bits_on_air, note)
# Field layouts: ExpressLRS 4.1.0 OTA_Packet4_s / OTA_Packet8_s / OTA_Sync_s (lib/OTA/OTA.h).
LAYOUTS = [
    ("Stock OTA4 RC", "rc", [("type", 2), ("CRC14", 14), ("4 ch x 10 bit", 40), ("switch+arm", 8)], 8, 0, 0,
     "CRC init = UID4/UID5 (public in SYNC) -> no authentication"),
    ("ExpCtr OTA4", "rc", [("type", 2), ("ctr", 8), ("tag", 6), ("4 ch x 10 bit", 40), ("switch+arm", 8)], 8, 6, 8,
     "8-bit counter on air leaves a 6-bit tag"),
    ("ExpCtr OTA4, 8-bit ch", "rc", [("type", 2), ("ctr", 8), ("tag", 14), ("4 ch x 8 bit", 32), ("switch+arm", 8)],
     8, 14, 8, "keeps a 14-bit tag by cutting channel resolution to 8 bit"),
    ("ExpCtr OTA8", "rc", [("type", 2), ("ctr", 8), ("tag", 14), ("4 ch x 10 bit", 40), ("switch+arm", 8),
                           ("free", 32)], 13, 14, 8,
     "keeps tag and resolution; the only longer packet the firmware has is OTA8 (13 B)"),
    ("Proposed OTA4 t=14", "rc", [("type", 2), ("tag", 14), ("4 ch x 10 bit", 40), ("switch+arm", 8)], 8, 14, 0,
     "implicit nonce = slot index, tag in the CRC14 bits"),
    ("Proposed OTA4 t=24", "rc", [("type", 2), ("tag", 24), ("4 ch x 9 bit", 36), ("arm+sw", 2)], 8, 24, 0,
     "10 more tag bits from the payload: 9-bit channels, arm + 1 switch"),
    ("Stock OTA8 RC", "rc", [("type", 2), ("flags", 6), ("8 ch x 10 bit", 80), ("CRC16", 16)], 13, 0, 0,
     "stubbornAck, uplinkPower, isHighAux, isArmed; CRC16"),
    ("Proposed OTA8 t=16", "rc", [("type", 2), ("flags", 6), ("8 ch x 10 bit", 80), ("tag", 16)], 13, 16, 0,
     "tag in the CRC16 bits"),
    ("Stock OTA4 SYNC", "sync", [("type", 2), ("CRC14", 14), ("fhss", 8), ("nonce", 8), ("rate", 8), ("flags", 8),
                                 ("UID4", 8), ("UID5", 8)], 8, 0, 8,
     "UID4/UID5 in clear; CRC does not bind the nonce"),
    ("Proposed OTA4 SYNC", "sync", [("type", 2), ("tag", 30), ("fhss", 8), ("nonce", 8), ("rate", 8), ("flags", 8)],
     8, 30, 8, "UID bytes + CRC14 become a 30-bit tag"),
    ("Proposed beacon", "sync", [("type", 2), ("tag", 30), ("ctr", 32)], 8, 30, 32,
     "libproto beacon as simulated: rate/flags fixed before the match, 32-bit slot counter"),
]
FIELD_COLOR = {"type": "#b9b8b0", "CRC14": "#2a78d6", "CRC16": "#2a78d6", "ctr": "#eda100", "tag": "#1baf7a",
               "4 ch x 10 bit": "#e87ba4", "4 ch x 9 bit": "#e87ba4", "4 ch x 8 bit": "#e87ba4",
               "8 ch x 10 bit": "#e87ba4", "switch+arm": "#6250d6", "arm+sw": "#6250d6", "flags": "#6250d6",
               "free": "#e4e3de", "fhss": "#eb6834", "nonce": "#eb6834", "rate": "#eb6834",
               "UID4": "#008300", "UID5": "#008300"}

RATES = phy.all_rates()


def main():
    out = RESULTS / "e4_bit_budget"
    (out / "plots").mkdir(parents=True, exist_ok=True)

    rows = []
    for label, kind, fields, nbytes, tag, nonce, note in LAYOUTS:
        ch = next((f for f, _ in fields if " ch x " in f), None)
        ch_bits = int(ch.split(" x ")[1].split()[0]) if ch else None
        assert sum(b for _, b in fields) == 8 * nbytes, label
        row = {"scheme": label, "kind": kind, "bytes": nbytes, "tag_bits": tag, "nonce_on_air_bits": nonce,
               "channel_bits": ch_bits, "note": note}
        for rname in RATES:
            r = phy.rate(rname)
            toa = phy.rate_airtime(r, nbytes)
            base = phy.rate_airtime(r)  # the packet size this rate uses in the firmware
            slack = r["period_us"] - toa - r["fixed_overhead_us"]
            row[f"{rname}_toa_us"] = round(toa, 1)
            row[f"{rname}_toa_increase_pct"] = round(100 * (toa / base - 1), 1)
            row[f"{rname}_slack_us"] = round(slack, 1)
            row[f"{rname}_fits_slot"] = bool(slack > 0)
            row[f"{rname}_max_rate_hz"] = round(1e6 / (toa + r["fixed_overhead_us"]), 1)
            row[f"{rname}_forge_expected_s"] = (2.0**tag / (1e6 / r["period_us"])) if tag else 0.0
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(out / "plots" / "e4_bit_budget.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 40):
        print(df[["scheme", "bytes", "tag_bits", "nonce_on_air_bits", "channel_bits"] +
                 [f"{r}_toa_us" for r in RATES] + [f"{r}_toa_increase_pct" for r in RATES] +
                 [f"{r}_slack_us" for r in RATES]].to_string(index=False))
    assert all(sum(b for _, b in lay[2]) == 8 * lay[3] for lay in LAYOUTS)

    fig, ax = plt.subplots(figsize=(10, 5.0))
    for i, (label, _kind, fields, nbytes, *_rest) in enumerate(LAYOUTS):
        x = 0
        y = len(LAYOUTS) - 1 - i
        for f, b in fields:
            ax.barh(y, b, left=x, color=FIELD_COLOR[f], edgecolor="white", linewidth=2, height=0.7)
            if b >= 6:
                ax.text(x + b / 2, y, f if b >= 14 else f.split()[0], ha="center", va="center", fontsize=7,
                        color=INK if f in ("type", "free") else "white")
            x += b
    ax.set_yticks(range(len(LAYOUTS)))
    ax.set_yticklabels([lay[0] for lay in reversed(LAYOUTS)], fontsize=8)
    ax.set_xticks(range(0, 105, 8))
    ax.set_xlabel("bit position (OTA4 = 64 bits, OTA8 = 104 bits)")
    ax.axvline(64, color=MUTED, linestyle="--", linewidth=1)
    ax.axvline(104, color=MUTED, linestyle="--", linewidth=1)
    ax.grid(axis="y", visible=False)
    ax.set_title("E4 OTA packet field layout", color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out / "plots" / "e4_layout.png")
    print(f"wrote {out}/plots")


if __name__ == "__main__":
    main()
