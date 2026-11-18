import pytest

from sim import phy

# (mode, payload, kwargs, ExpressLRS 4.1.0 TOA us, common.cpp line)
ELRS_TOA = [
    ("lora", 8, dict(sf=5, cr="LI_4_6", preamble=12), 1507),   # 500Hz  L98
    ("lora", 13, dict(sf=5, cr="LI_4_8", preamble=12), 2374),  # 333Hz8 L99
    ("lora", 8, dict(sf=6, cr="LI_4_8", preamble=14), 3300),   # 250Hz  L100 (rounded in source)
    ("lora", 8, dict(sf=7, cr="LI_4_8", preamble=12), 5871),   # 150Hz  L101
    ("lora", 13, dict(sf=7, cr="LI_4_8", preamble=12), 7605),  # 100Hz8 L102
    ("lora", 8, dict(sf=8, cr="LI_4_8", preamble=12), 10798),  # 50Hz   L103
    ("flrc", 8, dict(), 389),                                  # F1000  L94
]


@pytest.mark.parametrize("mode,pl,kw,toa", ELRS_TOA)
def test_toa_matches_elrs_within_1pct(mode, pl, kw, toa):
    assert abs(phy.time_on_air_us(mode, pl, **kw) - toa) / toa < 0.01


def test_baseline_has_sources():
    b = phy.baseline()

    def walk(node, path):
        if isinstance(node, dict):
            if "value" in node:
                assert "source" in node, f"{path} lacks source"
                return
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(b, "")


def test_rate_lookup():
    r = phy.rate("500Hz")
    assert r["period_us"] == 2000 and r["hop_interval"] == 4 and r["tx_rx_lost_ms"] == 1282
    assert abs(phy.rate_airtime(r) - r["airtime_us"]) < 15
