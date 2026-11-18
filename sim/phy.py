"""SX1280 time-on-air and baseline parameter loading.

LoRa: ToA = (Npre + 6.25 + ceil(8*PL*(4+CR)/4 / SF)) * 2^SF / BW   (implicit header, no radio CRC,
      long-interleaved coding rates). This reproduces the TOA column of ExpressLRS 4.1.0
      (common.cpp L94-103) to < 0.1 % for 5 of 6 LoRa rates and 0.85 % for 250 Hz
      (ExpressLRS lists a rounded 3300 us). Still to cross-check against the SX1280
      datasheet formula (section on LoRa time-on-air).
FLRC: ToA = (preamble + 32 sync + 2*(8 header + 8*PL + 16 crc + 6 tail)) / bitrate, CR 1/2.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_CR_DEN = {"LI_4_5": 5, "LI_4_6": 6, "LI_4_8": 8, "4_5": 5, "4_6": 6, "4_7": 7, "4_8": 8}


def time_on_air_us(mode: str, payload_bytes: int, *, sf: int = 0, bw_khz: float = 812.5,
                   cr: str = "LI_4_8", preamble: int = 12, bitrate_kbps: float = 650,
                   preamble_bits: int = 32) -> float:
    if mode == "lora":
        ts = (2**sf) / (bw_khz * 1e3) * 1e6
        coded_bits = 8 * payload_bytes * _CR_DEN[cr] / 4
        n_payload = math.ceil(coded_bits / sf)
        return (preamble + 6.25 + n_payload) * ts
    if mode == "flrc":
        bits = preamble_bits + 32 + 2 * (8 + 8 * payload_bytes + 16 + 6)
        return bits / (bitrate_kbps * 1e3) * 1e6
    raise ValueError(mode)


def _v(x):
    return x["value"] if isinstance(x, dict) and "value" in x else x


@lru_cache(maxsize=None)
def baseline() -> dict:
    with open(_ROOT / "configs" / "elrs_baseline.yaml") as f:
        return yaml.safe_load(f)


def rate(name: str) -> dict:
    """Flattened parameters of one packet rate (source annotations dropped)."""
    b = baseline()
    for r in b["packet_rates"]:
        if r["name"] == name:
            out = {k: _v(v) for k, v in r.items()}
            out["num_channels"] = _v(b["fhss"]["num_channels"])
            out["sync_channel"] = _v(b["fhss"]["sync_channel"])
            out["lq_window"] = _v(b["link_quality"]["window_packets"])
            hn = out["hop_interval"] * out["num_channels"]
            out["min_lq_connect"] = out["hop_interval"] * ((hn + 99) // hn)  # minLqForChaos
            out["tock_slack_us"] = max(out["period_us"] - 2 * out["airtime_us"],
                                       _v(b["rx_state_machine"]["tock_slack_min_us"]))
            out["pfd_initial_offset_us"] = _v(b["assumptions"]["pfd_initial_offset_us"])
            out["tx_rx_lost_ms"] = max(512, out["tlm_ratio"] * out["period_us"] // 200) + 2
            out["fixed_overhead_us"] = _v(b["assumptions"]["fixed_overhead_us"])
            out["isr_jitter_us"] = _v(b["assumptions"]["isr_jitter_us"])
            return out
    raise KeyError(name)


def all_rates() -> list[str]:
    return [r["name"] for r in baseline()["packet_rates"]]


def rf_cycle_dwell_ms(n_channels: int = 80) -> list[float]:
    """cycleInterval of every rate in firmware table order (rx_main.cpp L354)."""
    return [(11 * n_channels * h * p) // (10 * 1000) for p, h in _v(baseline()["rf_cycle_table"])]


def rate_airtime(r: dict, payload_bytes: int | None = None) -> float:
    pl = r["payload_bytes"] if payload_bytes is None else payload_bytes
    if r["mode"] == "lora":
        return time_on_air_us("lora", pl, sf=r["sf"], bw_khz=r["bw_khz"], cr=r["cr"],
                              preamble=r["preamble"])
    return time_on_air_us("flrc", pl, bitrate_kbps=r["bitrate_kbps"], preamble_bits=r["preamble_bits"])
