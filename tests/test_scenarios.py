"""Step 5.1 scenario tests: fixed seeds, a few seconds each."""

import numpy as np
import pytest
from scipy import stats

from sim import phy, proto_ffi
from sim.baselines import elrs_ota
from sim.channel import gilbert_elliott
from sim.linksim import Scenario, run


def test_replay_rejected():
    link = proto_ffi.Link(bytes(range(16)), 2, 14)
    pkts = [(s, link.seal(s, bytes([1, s % 256, 2, 3, 4, 5, 6, 0]))) for s in range(1000, 1100)]
    last = proto_ffi.NO_SLOT
    for s, p in pkts:  # in-order delivery, LOCKED (W = 1)
        ok, off, _ = link.open_window(s, 1, last, p)
        assert ok
        last = s + off
    replayed = sum(link.open_window(1100 + d, 1, last + d, p)[0] for d, (_, p) in enumerate(pkts))
    assert replayed == 0


def test_zero_friendly_collisions():
    p = proto_ffi.Proto(bytes(16), b"field")
    ch = p.hop_gap_block(0, 30000, 80, 10, 2).astype(int)  # 10 drones, 60 s at 500 Hz / 4
    d = np.abs(ch[:, None, :] - ch[None, :, :])
    off_diag = ~np.eye(10, dtype=bool)
    assert d[off_diag].min() >= 2


def test_forgery_rate_matches_theory():
    rng = np.random.default_rng(5)
    link = proto_ffi.Link(bytes(16), 0, 12)
    n = 100_000
    acc = sum(link.open_window(5000, 16, proto_ffi.NO_SLOT, rng.integers(0, 256, 8, dtype=np.uint8).tobytes())[0]
              for _ in range(n))
    theory = 1 - (1 - 2.0**-12) ** 16
    lo, hi = stats.binom.ppf([0.005, 0.995], n, theory)
    assert lo <= acc <= hi


def test_resync_after_blackout():
    n = int(30e6 // 2000)
    extra = np.zeros(n, bool)
    extra[5000:5250] = True  # 0.5 s full-band blackout at 500 Hz
    r = run(Scenario(protocol="proposed", seed=3, extra_loss=extra, record=True))
    first = 5250 + int(np.argmax(r.trace["delivered"][5250:]))
    assert (first - 5250) * 2 < 2500  # back before the failsafe timeout
    assert r.metrics["failsafe_count"] == 0


def test_hijack_succeeds_on_stock():
    # UID4/UID5 are broadcast in every SYNC packet -> attacker computes valid CRCs
    init = elrs_ota.crc_init(0x5A, 0xC3)
    forged = elrs_ota.seal(bytes([1, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x80, 0]), init, nonce=77)
    assert elrs_ota.valid(forged, init, 77)


def test_hijack_fails_on_proposed():
    victim = proto_ffi.Link(bytes(range(16)), 1, 32)
    attacker = proto_ffi.Link(bytes(range(1, 17)), 1, 32)  # knows algorithm + IDs, not the key
    forged = [attacker.seal(9000 + i, bytes([1, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x80, 0])) for i in range(2000)]
    assert sum(victim.open_window(9000 + i, 16, proto_ffi.NO_SLOT, f)[0] for i, f in enumerate(forged)) == 0


def test_ge_steady_state():
    rng = np.random.default_rng(1)
    lost = gilbert_elliott(rng, 2_000_000, burst_len=20, err_rate=0.3)
    assert abs(lost.mean() - 0.3) < 0.01


def test_determinism():
    sc = dict(protocol="proposed", seed=11, duration_s=5, ge=(50, 0.2))
    a, b = run(Scenario(**sc)), run(Scenario(**sc))
    assert a.metrics == b.metrics and a.gaps == b.gaps


@pytest.mark.parametrize("rate", phy.all_rates())
def test_every_rate_runs_clean(rate):
    for proto in ("stock", "proposed"):
        m = run(Scenario(protocol=proto, rate=rate, duration_s=5, seed=1)).metrics
        assert m["failsafe_count"] == 0 and m["pdr"] > 0.99


def test_min_lq_follows_hop_interval():
    assert phy.rate("500Hz")["min_lq_connect"] == 4
    assert phy.rate("F1000Hz")["min_lq_connect"] == 2


def test_tock_slack_matches_firmware():
    assert phy.rate("500Hz")["tock_slack_us"] == 200          # 2000 - 2*1507 < 200
    assert phy.rate("F500Hz")["tock_slack_us"] == 2000 - 2 * 389


def test_stock_reconnects_through_pfd_and_lq():
    res = run(Scenario(protocol="stock", seed=2, duration_s=20, blackout={"start_s": 5, "dur_s": 4}, record=True))
    assert res.metrics["recovered"] and res.trace["connect_slots"]
    assert min(res.trace["connect_slots"]) > phy.rate("500Hz")["min_lq_connect"] - 1


def test_stock_unlocked_rate_cycle_is_slower():
    sc = dict(protocol="stock", rate="500Hz", duration_s=60, blackout={"start_s": 5, "dur_s": 20})
    locked = np.mean([run(Scenario(seed=s, **sc)).metrics["recovery_ms"] for s in range(5)])
    unlocked = np.mean([run(Scenario(seed=s, lock_on_first=False, **sc)).metrics["recovery_ms"] for s in range(5)])
    assert unlocked > locked


def test_proposed_short_outage_needs_no_beacon():
    m = run(Scenario(protocol="proposed", seed=2, duration_s=15, drift_ppm=50,
                     blackout={"start_s": 5, "dur_s": 2})).metrics
    assert m["recovered"] and m["beacons_ok"] == 0


def test_proposed_beacon_recovers_past_clock_trust():
    # F1000: one hop of margin -> the RX stops trusting its clock after 7.5 s
    m = run(Scenario(protocol="proposed", rate="F1000Hz", seed=2, duration_s=25, drift_ppm=50,
                     blackout={"start_s": 5, "dur_s": 12})).metrics
    assert m["recovered"] and m["beacons_ok"] >= 1


def test_proposed_recovers_after_reboot_only_through_beacon():
    m = run(Scenario(protocol="proposed", seed=2, duration_s=15, reboot={"start_s": 5, "dur_s": 0.5})).metrics
    assert m["recovered"] and m["beacons_ok"] == 1


def test_sync_only_jammer_blocks_stock_rejoin_not_proposed():
    sc = dict(duration_s=25, seed=4, jammer={"type": "sync_only"}, blackout={"start_s": 5, "dur_s": 3})
    assert not run(Scenario(protocol="stock", **sc)).metrics["recovered"]
    assert run(Scenario(protocol="proposed", **sc)).metrics["recovered"]


def test_beacon_budget_and_replay():
    p = proto_ffi.Proto(bytes(16), b"f")
    rs = proto_ffi.Resync(2, 100, 8, 8)
    pkt = p.beacon_seal(0, 123456)
    assert p.beacon_open(rs, 0, pkt) == 123456
    assert p.beacon_open(rs, 0, pkt) is None          # replay
    assert p.beacon_open(proto_ffi.Resync(2, 100, 8, 8), 1, pkt) is None  # other drone


@pytest.mark.parametrize("rate", phy.all_rates())
def test_stock_tx_keeps_sending_sync_at_every_start_phase(rate):
    # Telemetry must never block the sync ladder: FHSS index and nonce reset together on the TX.
    r = phy.rate(rate)
    period_s = r["period_us"] / 1e6
    dur = r["disconnect_timeout_ms"] / 1000 + 1
    # longer than two passes over the sync channel + the tentative LQ window
    run_s = 5 + dur + 2 * 80 * r["hop_interval"] * period_s + 100 * period_s + 5
    for seed in range(12):
        m = run(Scenario(protocol="stock", rate=rate, duration_s=run_s, seed=seed,
                         blackout={"start_s": 5, "dur_s": dur})).metrics
        assert m["recovered"], (rate, seed)


def test_reboot_recovery_is_not_phase_locked():
    x = [run(Scenario(protocol="proposed", seed=s, duration_s=12, reboot={"start_s": 5, "dur_s": 0.5})).metrics["recovery_ms"]
         for s in range(12)]
    assert len(set(x)) > 3
    # TX telemetry timeout left after the reboot + one TX rotation + one beacon period + margin
    assert max(x) <= (phy.rate("500Hz")["tx_rx_lost_ms"] - 500) + 4 * 250 + 8 * 2 + 50
