"""Slot-stepped discrete-event simulation of one TX->RX control link.

Every protocol event (TX start, RX window, sync, telemetry, state-machine timeout)
falls on a packet-slot boundary, so the simulator advances slot by slot in integer
slots (time = slot * period_us); sub-slot quantities (airtime, CPU deadline, clock
error) are evaluated analytically within the slot.

Protocols (same interface: channel schedule + per-slot RX logic):
  stock    - ExpressLRS 4.1.0 RX/TX state machines (configs/elrs_baseline.yaml), including
             the PFD connect condition and the RF-mode cycle when the rate is not locked
  expctr   - stock + explicit counter and MAC; identical timing/resync behaviour
             (sync packets on the public sync channel), differs in security and bit budget
  proposed - libproto: gap-transform hopping (g=2), implicit-nonce MAC, window search, the
             LOCKED/SUSPECT/LOST state machine, and authenticated beacons on key-derived
             rotating rendezvous channels for a receiver whose clock cannot be trusted
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from sim import phy, proto_ffi
from sim.baselines import elrs_stock
from sim.channel import gilbert_elliott, iid_loss, jammer_fn

STOCK, EXPCTR, PROPOSED = "stock", "expctr", "proposed"
STOCKSYNC = "stocksync"  # N3 baseline: stock with SyncPktIntervalConnected = Disconnected


@dataclass
class Scenario:
    protocol: str = PROPOSED
    rate: str = "500Hz"
    duration_s: float = 30.0
    seed: int = 0
    per: float = 0.0                      # i.i.d. packet error rate
    ge: tuple | None = None               # (mean burst slots, steady-state error rate)
    jammer: dict | None = None
    blackout: dict | None = None          # {start_s, dur_s}: all channels lost
    reboot: dict | None = None            # {start_s, dur_s}: RX powered off, clock lost
    extra_loss: np.ndarray | None = None  # e.g. friendly collisions (E9)
    tx_channels: np.ndarray | None = None # override channel schedule (E9)
    nonce0: int = 0                       # stock: TX nonce at t = 0 when tx_channels is given
    window: int = 8                       # proposed: nonce window in SUSPECT / LOST (E6)
    suspect_after: int = 2
    tag_bits: int = 14
    drone_id: int = 0
    n_drones: int = 1
    gap: int = 2
    drift_ppm: float = 0.0                # per crystal; TX and RX opposite (worst case)
    lock_on_first: bool = True            # stock: firmware default LOCK_ON_FIRST_CONNECTION
    beacon_every: int = 8                 # proposed: TX beacon period while telemetry is lost
    rdv_epoch_ms: float = 250.0           # proposed: rendezvous channel rotation
    rdv_list: int = 4                     # proposed: rendezvous channels in rotation
    park_ppm: float = 50.0                # proposed: crystal spec the RX trusts its clock against
    cost_c_us: float | None = None        # E10: time per MAC/PRF; None = free
    worst_case_tries: bool = False        # E10: every packet in SUSPECT/LOST costs W MACs
    record: bool = False                  # E5: keep per-slot trace
    min_gap_slots: int = 2                # control gaps shorter than this are not events
    # Revised-plan resync (N3/N4): single fixed critical channel, per-frame TX sync, COAST.
    crit_channel: int | None = None       # None = old rendezvous mechanism; int = new mechanism
    n_sync: int = 1                       # TX sync slots per 256-slot frame (n_s = 1/2/4)
    tx_reboot: dict | None = None         # {start_s, dur_s}: TX powered off (RX coasts)


@dataclass
class Result:
    metrics: dict
    gaps: list = field(default_factory=list)   # (gap_ms, excess_ms, failsafe)
    trace: dict | None = None


def schedule_channels(sc: Scenario, r: dict, rng, n_slots: int):
    """Channel of every slot's packet. Returns (ch, extra) where extra holds keys/seq."""
    h_cnt = n_slots // r["hop_interval"] + 2
    n_ch = r["num_channels"]
    if sc.tx_channels is not None:
        extra = {}
        if sc.protocol == PROPOSED:
            sk = rng.integers(0, 256, size=16, dtype=np.uint8).tobytes()
            extra = {"proto": proto_ffi.Proto(sk, b"field-sim"), "hop_prf": 3.0}
        return sc.tx_channels[:n_slots], extra
    if sc.protocol in (STOCK, EXPCTR, STOCKSYNC):
        uid = rng.integers(0, 256, size=6, dtype=np.uint8).tobytes()
        seq = elrs_stock.build_sequence(elrs_stock.uid_seed(uid), n_ch)
        # The TX resets FHSS index and nonce together (tx_main.cpp L494-495), so telemetry slots
        # keep a fixed phase to the sync channel; only the time since TX start is random.
        s0 = int(rng.integers(r["hop_interval"] * len(seq)))
        hops = seq[((s0 + np.arange(n_slots)) // r["hop_interval"]) % len(seq)]
        return hops, {"seq": seq, "uid": uid, "nonce0": s0}
    sk = rng.integers(0, 256, size=16, dtype=np.uint8).tobytes()
    p = proto_ffi.Proto(sk, b"field-sim")
    h0 = int(rng.integers(0, 2**40))
    proto_ffi.op_counts_reset()
    n_hop = n_ch - 1 if sc.crit_channel is not None else n_ch  # new mechanism: exclude critical ch
    hops = p.hop_gap_block(h0, h_cnt, n_hop, sc.n_drones, sc.gap)[sc.drone_id]
    if sc.crit_channel is not None:
        hops = hops + (hops >= sc.crit_channel).astype(hops.dtype)  # map 0..78 onto non-critical chs
    hop_prf = proto_ffi.op_counts()["prf"] / h_cnt  # PRF calls per hop, measured
    return hops[np.arange(n_slots) // r["hop_interval"]], {"proto": p, "hop_prf": hop_prf}


def _window_slots(w: dict | None, period_us: float, n: int):
    """(start, end) slots of a {start_s, dur_s} event, or None."""
    if not w:
        return None
    a = int(w["start_s"] * 1e6 // period_us)
    return a, min(n, a + int(round(w["dur_s"] * 1e6 / period_us)))


def run(sc: Scenario) -> Result:
    r = phy.rate(sc.rate)
    # Separate streams so every protocol sees the same channel / jammer realisation
    # for a given seed (paired comparison); keys/UIDs come from their own stream.
    rng = np.random.default_rng([sc.seed, 2])
    period = r["period_us"]
    n = int(sc.duration_s * 1e6 // period)
    ch, extra = schedule_channels(sc, r, np.random.default_rng([sc.seed, 1]), n)
    lost_any = np.zeros(n, dtype=bool)  # loss that hits every channel
    if sc.per > 0:
        lost_any |= iid_loss(rng, n, sc.per)
    if sc.ge is not None:
        lost_any |= gilbert_elliott(rng, n, *sc.ge)
    blackout = _window_slots(sc.blackout, period, n)
    if blackout:
        lost_any[blackout[0]:blackout[1]] = True
    jam = jammer_fn(rng, sc.jammer, n, period, r["airtime_us"], r["num_channels"],
                    sc.protocol, r["sync_channel"])
    lost = lost_any | jam(np.arange(n), ch)
    if sc.extra_loss is not None:
        lost |= sc.extra_loss[:n]
    ok = ~lost  # packet on ch[t] would survive the channel
    nonce0 = extra.get("nonce0", sc.nonce0)  # slots since the TX reset its nonce
    tlm = ((np.arange(n) + nonce0 + 1) % r["tlm_ratio"]) == 0
    reboot = _window_slots(sc.reboot, period, n)
    if sc.protocol in (STOCK, EXPCTR, STOCKSYNC):
        out = _run_stock(sc, r, n, ch, ok, tlm, reboot, nonce0)
    elif sc.crit_channel is not None:
        out = _run_proposed_critical(sc, r, n, ch, ok, tlm, extra, rng, lost_any, jam, reboot)
    else:
        out = _run_proposed(sc, r, n, ch, ok, tlm, extra, rng, lost_any, jam, reboot)
    end = (blackout or reboot or (None, None))[1]
    return _finish(sc, r, n, ok, tlm, end, *out)


class _Lpf:
    """include/LowPassFilter.h with FP_Shift 5, after init(0)."""

    def __init__(self, beta: int):
        self.beta, self.fp = beta, 0

    def update(self, x: int) -> int:
        self.fp = ((self.fp << self.beta) - self.fp + (x << 5)) >> self.beta
        return self.fp >> 5


def _run_stock(sc, r, n, ch, ok, tlm, reboot, nonce0):
    period_ms = r["period_us"] / 1000.0
    H, sync_ch = r["hop_interval"], r["sync_channel"]
    disc_slots = r["disconnect_timeout_ms"] / period_ms
    lock_slots = r["rx_lock_timeout_ms"] / period_ms
    tx_lost_slots = r["tx_rx_lost_ms"] / period_ms
    sync_conn = r["sync_interval_connected_ms"] / period_ms
    sync_disc = r["sync_interval_disconnected_ms"] / period_ms
    lqw, min_lq = r["lq_window"], r["min_lq_connect"]
    pfd_rng = np.random.default_rng([sc.seed, 4])
    pfd_sd, isr_sd = r["pfd_initial_offset_us"], r["isr_jitter_us"]
    dwell_ms, rf_idx = phy.rf_cycle_dwell_ms(r["num_channels"]), r["rf_index"]

    CONN, TENT, DISC = 0, 1, 2
    state = CONN
    last_valid = last_sync_rx = 0
    last_tlm = 0
    tx_last_sync = -10**9
    sync_slot = 0
    lq_ring = np.zeros(lqw, dtype=np.int8)
    lq = 0
    lq_pos = 0
    delivered = np.zeros(n, dtype=bool)
    rx_state = np.empty(n, dtype=np.int8)
    is_sync = np.zeros(n, dtype=bool)
    lq_trace = np.zeros(n, dtype=np.int16)
    connect_slots = []  # slots from entering tentative to connected
    tent_at = 0
    lock_rf = sc.lock_on_first  # LockRFmode: the run starts already connected
    scan, dwell_end = rf_idx, 0
    pfd_err = 0.0
    lpf_off, lpf_dx, prev_raw = _Lpf(2), _Lpf(4), 0

    def disconnect(t, multiplier):
        nonlocal state, lq, scan, dwell_end
        state, lq = DISC, 0
        lq_ring[:] = 0
        scan, dwell_end = rf_idx, t + multiplier * dwell_ms[rf_idx] / period_ms

    for t in range(n):
        rx_off = reboot is not None and reboot[0] <= t < reboot[1]
        if reboot is not None and t == reboot[0]:
            disconnect(t, 5)
        if reboot is not None and t == reboot[1]:
            lock_rf = False  # LockRFmode resets on boot; first dwell is slow / 2 (rx_main.cpp L1603)
            disconnect(t, 5)
        if state == DISC and not lock_rf and t >= dwell_end:
            scan = (scan + 1) % len(dwell_ms)
            dwell_end = t + dwell_ms[scan] / period_ms
        on_rate = lock_rf or scan == rf_idx
        # LQ window advances with the RX timer (stopped when disconnected), but not on slots
        # where the RX sent telemetry (rx_main.cpp L662 `if (!alreadyTLMresp) LQCalc.inc()`)
        if state != DISC and not tlm[t]:
            lq_pos = (lq_pos + 1) % lqw
            lq -= lq_ring[lq_pos]
            lq_ring[lq_pos] = 0
        if tlm[t]:
            if state != DISC and ok[t]:
                last_tlm = t
        else:
            tx_conn = (t - last_tlm) <= tx_lost_slots
            # stocksync (N3 baseline): TX sends sync every sync-channel pass even when connected
            interval = sync_disc if sc.protocol == STOCKSYNC else (sync_conn if tx_conn else sync_disc)
            if ch[t] == sync_ch and (sync_slot // 2) <= ((t + nonce0) % H) and (t - tx_last_sync) > interval:
                is_sync[t] = True
                tx_last_sync = t
                sync_slot = (sync_slot + 1) % (2 * H)
            rx_ch = ch[t] if state != DISC else sync_ch
            if not rx_off and on_rate and rx_ch == ch[t] and ok[t]:
                if is_sync[t]:
                    if state == DISC:
                        state = TENT
                        tent_at = t
                        pfd_err = pfd_rng.normal(0, pfd_sd)
                        lpf_off, lpf_dx, prev_raw = _Lpf(2), _Lpf(4), 0
                    last_sync_rx = t
                    last_valid = t
                    lq += 1 - lq_ring[lq_pos]
                    lq_ring[lq_pos] = 1
                elif state != DISC:
                    last_valid = t
                    lq += 1 - lq_ring[lq_pos]
                    lq_ring[lq_pos] = 1
                    delivered[t] = state == CONN
                if state == TENT:  # updatePhaseLock (rx_main.cpp L609-632)
                    raw = int(pfd_err + pfd_rng.normal(0, isr_sd))
                    lpf_off.update(raw)
                    lpf_dx.update(raw - prev_raw)
                    prev_raw = raw
                    pfd_err -= raw >> 1
        if state == TENT and (t - last_sync_rx) > lock_slots:
            disconnect(t, 10)
        elif state == CONN and (t - last_valid) > disc_slots:
            disconnect(t, 10)
        elif (state == TENT and abs(lpf_dx.fp >> 5) <= 10 and (lpf_off.fp >> 5) < 100 and lq > min_lq):
            state = CONN
            lock_rf = sc.lock_on_first
            connect_slots.append(t - tent_at)
        rx_state[t] = state
        lq_trace[t] = lq
    sent = ~tlm & ~is_sync
    failsafe = rx_state == DISC
    return delivered, sent, failsafe, {"rx_state": rx_state, "is_sync": is_sync, "lq": lq_trace,
                                       "ch": ch, "deadline_miss": 0, "connect_slots": connect_slots, "nonce0": nonce0,
                                       "mac_ops": int((~tlm).sum()) if sc.protocol == EXPCTR else 0}


def _run_proposed(sc, r, n, ch, ok, tlm, extra, rng, lost_any, jam, reboot):
    proto = extra["proto"]
    P = r["period_us"]
    period_ms = P / 1000.0
    H, toa, tock = r["hop_interval"], r["airtime_us"], r["tock_slack_us"]
    n_ch = r["num_channels"]
    lost_after = int(round(r["disconnect_timeout_ms"] / period_ms))
    tx_lost_slots = r["tx_rx_lost_ms"] / period_ms
    link_tx = proto_ffi.Link(proto.k_mac, sc.drone_id, sc.tag_bits)
    link_rx = proto_ffi.Link(proto.k_mac, sc.drone_id, sc.tag_bits)
    mk_rs = lambda now=0: proto_ffi.Resync(sc.suspect_after, lost_after, sc.window, sc.window, now)
    rs = mk_rs()
    slack = P - toa - r["fixed_overhead_us"]
    hop_prf = extra.get("hop_prf", 3.0)
    payload = rng.integers(0, 256, size=(n, 8), dtype=np.uint8)
    payload[:, 0] = (payload[:, 0] & 0xFC) | 1
    delivered = np.zeros(n, dtype=bool)
    is_beacon = np.zeros(n, dtype=bool)
    rx_state = np.empty(n, dtype=np.int8)
    deadline_miss = mac_ops = beacons_ok = 0
    jitter = np.abs(rng.normal(0, r["isr_jitter_us"], n)) if sc.cost_c_us is not None else None

    # Clock: the RX re-phases on every accepted packet and free-runs otherwise.
    sign = 1 if np.random.default_rng([sc.seed, 3]).random() < 0.5 else -1
    delta_us = sign * 2 * sc.drift_ppm * 1e-6 * P  # clock error gained per slot
    err_us = 0.0
    last_lock = 0
    # Past this age the worst-case crystal could have moved the RX onto another hop.
    trust_slots = (H - 1) * 0.75 / (2 * sc.park_ppm * 1e-6)
    epoch_slots = max(1, int(round(sc.rdv_epoch_ms / period_ms)))
    rdv = [proto.rendezvous_channel(i, n_ch) for i in range(sc.rdv_list)]
    dwell_slots = (sc.rdv_list + 1) * epoch_slots  # RX dwell covers the whole TX rotation
    parked, park_start = False, 0
    last_tlm = 0
    # Nothing ties an outage or a reboot to the TX rotation or the RX's first guess.
    phase = np.random.default_rng([sc.seed, 5])
    rot0 = int(phase.integers(sc.rdv_list * epoch_slots))
    list0 = int(phase.integers(sc.rdv_list))
    beacon0 = int(phase.integers(sc.beacon_every))

    for t in range(n):
        rx_off = reboot is not None and reboot[0] <= t < reboot[1]
        if reboot is not None and t == reboot[0]:
            rs.force_lost()
        if reboot is not None and t == reboot[1]:
            rs = mk_rs(t)
            rs.force_lost()
            err_us, parked, park_start = 0.0, True, t
        err_us += delta_us
        if tlm[t]:
            if not rx_off and not parked and rs.state != proto_ffi.LOST and ok[t]:
                last_tlm = t
            rx_state[t] = rs.state
            continue
        accepted = False
        beacon = (t - last_tlm) > tx_lost_slots and (t + beacon0) % sc.beacon_every == 0
        is_beacon[t] = beacon
        if parked and not rx_off:
            bch = rdv[((t + rot0) // epoch_slots) % sc.rdv_list]
            listen = rdv[(list0 + (t - park_start) // dwell_slots) % sc.rdv_list]
            if beacon and bch == listen and not lost_any[t] and not jam(t, bch):
                slot = proto.beacon_open(rs, sc.drone_id, proto.beacon_seal(sc.drone_id, t))
                mac_ops += 1
                busy_ok = sc.cost_c_us is None or (2 * sc.cost_c_us + jitter[t]) <= slack
                if slot is not None and busy_ok:
                    beacons_ok += 1
                    err_us, parked, last_lock = 0.0, False, t  # clock set; LOST until data passes MAC
                elif not busy_ok:
                    deadline_miss += 1
        elif not rx_off and ok[t] and not beacon:
            # Local slot k spans [(k-1)P + toa + tock + err, kP + toa + tock + err): the RX hops
            # and advances the nonce at TOCK, `tock` after the packet end (rx_main.cpp L1124).
            k0 = int((t * P - toa - tock - err_us) // P) + 1
            k1 = int((t * P - tock - err_us) // P) + 1
            if k0 // H == t // H and k1 // H == t // H:
                pkt = link_tx.seal(t, payload[t].tobytes())
                w = rs.window()
                good, off, tries = link_rx.open_window(k1, w, rs.last_accepted, pkt)
                if sc.worst_case_tries and w > 1:
                    tries = w
                mac_ops += tries
                if sc.cost_c_us is not None:
                    busy = (tries + (hop_prf if t % H == 0 else 0.0)) * sc.cost_c_us + jitter[t]
                    if busy > slack:
                        deadline_miss += 1
                        good = False
                if good:
                    accepted = True
                    delivered[t] = True
                    err_us, last_lock = 0.0, t
                    rs.on_slot(t, True, k1 + off)
        if not accepted:
            rs.on_slot(t, False)
        if not parked and rs.state == proto_ffi.LOST and (t - last_lock) > trust_slots:
            parked, park_start = True, t
        rx_state[t] = rs.state
    sent = ~tlm & ~is_beacon
    failsafe = rx_state == proto_ffi.LOST
    return delivered, sent, failsafe, {"rx_state": rx_state, "deadline_miss": deadline_miss,
                                       "mac_ops": mac_ops, "is_beacon": is_beacon,
                                       "beacons_ok": beacons_ok}


def _run_proposed_critical(sc, r, n, ch, ok, tlm, extra, rng, lost_any, jam, reboot):
    """Revised-plan resync: single fixed critical channel, per-frame TX sync, COAST state.

    The RX follows the hop table on its own clock (COAST) while packets are missing and only
    falls back to the critical channel (LOST) when its worst-case clock uncertainty exceeds half
    the slot guard, or it rebooted. There it waits for its own TX's sync (every frame at slot r_i,
    n_s times per 256-slot frame) to re-phase, then the first data packet that passes the MAC
    re-locks. TX never changes its schedule for telemetry; the GS/TX sync carries the slot counter
    (modelled with the libproto beacon codec: authentic + monotonic, so replays can't lock it)."""
    proto = extra["proto"]
    P = r["period_us"]
    H, toa, tock = r["hop_interval"], r["airtime_us"], r["tock_slack_us"]
    period_ms = P / 1000.0
    crit = int(sc.crit_channel)
    FRAME, n_s = 256, max(1, int(sc.n_sync))
    r_i = (13 + 24 * sc.drone_id) % FRAME                       # this TX's sync slot in the frame
    sync_set = {(r_i + j * (FRAME // n_s)) % FRAME for j in range(n_s)}
    link_tx = proto_ffi.Link(proto.k_mac, sc.drone_id, sc.tag_bits)
    link_rx = proto_ffi.Link(proto.k_mac, sc.drone_id, sc.tag_bits)
    rs = proto_ffi.Resync(sc.suspect_after, int(round(r["disconnect_timeout_ms"] / period_ms)),
                          sc.window, sc.window, 0)              # beacon-replay bookkeeping only
    slack = P - toa - r["fixed_overhead_us"]
    hop_prf = extra.get("hop_prf", 3.0)
    payload = rng.integers(0, 256, size=(n, 8), dtype=np.uint8)
    payload[:, 0] = (payload[:, 0] & 0xFC) | 1
    delivered = np.zeros(n, bool)
    is_beacon = np.zeros(n, bool)
    rx_state = np.empty(n, np.int8)
    parked_tr = np.zeros(n, bool)
    deadline_miss = mac_ops = beacons_ok = 0
    jitter = np.abs(rng.normal(0, r["isr_jitter_us"], n)) if sc.cost_c_us is not None else None
    sign = 1 if np.random.default_rng([sc.seed, 3]).random() < 0.5 else -1
    delta_us = sign * 2 * sc.drift_ppm * 1e-6 * P
    err_us, last_lock, last_acc = 0.0, 0, proto_ffi.NO_SLOT
    # COAST budget: slots the RX trusts its clock before the worst-case residual drift ε (park_ppm)
    # pushes its slot-time uncertainty past half the guard — ~20 s at 10 ppm, ~4 s at 50 ppm.
    guard = max(1.0, (P - toa) / 2.0)
    coast_slots = guard / max(1e-9, sc.park_ppm * 1e-6 * P)
    tx_reboot = _window_slots(sc.tx_reboot, P, n)
    frame0 = int(np.random.default_rng([sc.seed, 5]).integers(FRAME))
    parked = need_window = False
    last_tlm = 0

    for t in range(n):
        rx_off = reboot is not None and reboot[0] <= t < reboot[1]
        tx_off = tx_reboot is not None and tx_reboot[0] <= t < tx_reboot[1]
        if reboot is not None and t == reboot[0]:
            parked = True
        if reboot is not None and t == reboot[1]:
            parked, err_us, last_lock, need_window = True, 0.0, t, True  # booted: clock lost
        err_us += delta_us
        is_sync = ((t + frame0) % FRAME) in sync_set
        if tlm[t]:
            if not rx_off and not tx_off and not parked and ok[t]:
                last_tlm = t
            rx_state[t] = proto_ffi.LOST if parked else proto_ffi.LOCKED
            parked_tr[t] = parked
            continue
        accepted = False
        if is_sync:
            is_beacon[t] = True                    # TX is on the critical channel, not sending RC
            if not rx_off and not tx_off and parked and not lost_any[t] and not jam(t, crit):
                slot = proto.beacon_open(rs, sc.drone_id, proto.beacon_seal(sc.drone_id, t))
                mac_ops += 1
                busy_ok = sc.cost_c_us is None or (2 * sc.cost_c_us + jitter[t]) <= slack
                if slot is not None and busy_ok:
                    beacons_ok += 1
                    parked, err_us, last_lock, need_window = False, 0.0, t, True
                elif not busy_ok:
                    deadline_miss += 1
        elif not rx_off and not tx_off and not parked and ok[t]:
            k0 = int((t * P - toa - tock - err_us) // P) + 1
            k1 = int((t * P - tock - err_us) // P) + 1
            if k0 // H == t // H and k1 // H == t // H:
                pkt = link_tx.seal(t, payload[t].tobytes())
                w = sc.window if need_window else 1
                good, off, tries = link_rx.open_window(k1, w, last_acc, pkt)
                if sc.worst_case_tries and w > 1:
                    tries = w
                mac_ops += tries
                if sc.cost_c_us is not None:
                    busy = (tries + (hop_prf if t % H == 0 else 0.0)) * sc.cost_c_us + jitter[t]
                    if busy > slack:
                        deadline_miss += 1
                        good = False
                if good:
                    accepted = True
                    delivered[t] = True
                    err_us, last_lock, last_acc, need_window = 0.0, t, k1 + off, False
        if not accepted and not parked and (t - last_lock) > coast_slots:
            parked = True                          # COAST budget exhausted: clock no longer trusted
        rx_state[t] = proto_ffi.LOST if parked else proto_ffi.LOCKED
        parked_tr[t] = parked
    sent = ~tlm & ~is_beacon
    return delivered, sent, parked_tr, {"rx_state": rx_state, "deadline_miss": deadline_miss,
                                        "mac_ops": mac_ops, "is_beacon": is_beacon,
                                        "beacons_ok": beacons_ok}


def _runs(mask: np.ndarray):
    """(start, end_exclusive) of True runs."""
    d = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def _finish(sc, r, n, ok, tlm, event_end, delivered, sent, failsafe, info) -> Result:
    period_ms = r["period_us"] / 1000.0
    rc_slots = ~tlm
    # Control gaps: runs of RC slots without delivered control (TLM slots do not break a gap)
    no_ctrl = ~delivered
    starts, ends = _runs(no_ctrl)
    gaps = []
    deliverable = ok & rc_slots & ~info.get("is_beacon", np.zeros(n, dtype=bool))
    censored_ms = 0.0  # gap still open at end of run (never recovered): counts for max outage
    for s, e in zip(starts, ends):
        if e >= n:
            censored_ms = (e - s) * period_ms
            continue
        if e - s < sc.min_gap_slots:
            continue
        first_ok = s + int(np.argmax(deliverable[s:e])) if deliverable[s:e].any() else e
        gaps.append(((e - s) * period_ms, (e - first_ok) * period_ms, bool(failsafe[s:e].any())))
    fs_starts, fs_ends = _runs(failsafe)
    m = {
        "n_slots": n,
        "rc_sent": int(sent.sum()),
        "rc_delivered": int((delivered & sent).sum()),
        "pdr": float((delivered & sent).sum() / max(1, sent.sum())),
        "channel_ok_frac": float(ok[rc_slots].mean()),
        "failsafe_count": int(len(fs_starts)),
        "failsafe_ms": float(failsafe.sum() * period_ms),
        "max_outage_ms": float(max([g[0] for g in gaps] + [censored_ms], default=0.0)),
        "unrecovered_at_end_ms": censored_ms,
        "deadline_miss": int(info["deadline_miss"]),
        "mac_ops": int(info["mac_ops"]),
        "beacons_ok": int(info.get("beacons_ok", 0)),
    }
    if event_end is not None:  # blackout / reboot: time from its end to the next delivered RC frame
        after = np.flatnonzero(delivered[event_end:])
        m["recovered"] = bool(len(after))
        m["recovery_ms"] = float(after[0] * period_ms) if len(after) else float("nan")
    trace = None
    if sc.record:
        trace = {"delivered": delivered, "sent": sent, "ok": ok, "tlm": tlm, **info}
    return Result(m, gaps, trace)
