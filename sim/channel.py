"""Per-slot packet loss models: Gilbert-Elliott bursts, i.i.d. PER, and jammers.

All functions return a boolean array `lost[t]` for the packet sent in slot t on
channel ch[t] (start time t * period_us, duration airtime_us).
"""

from __future__ import annotations

import numpy as np


def gilbert_elliott(rng, n_slots: int, burst_len: float, err_rate: float,
                    p_loss_good: float = 0.0, p_loss_bad: float = 1.0) -> np.ndarray:
    """Two-state Markov chain. burst_len = mean Bad run (slots); err_rate = steady-state
    P(Bad). p_BG = 1/burst_len, p_GB = err_rate * p_BG / (1 - err_rate)."""
    if err_rate <= 0:
        bad = np.zeros(n_slots, dtype=bool)
    else:
        p_bg = 1.0 / burst_len
        p_gb = min(1.0, err_rate * p_bg / (1 - err_rate))
        bad = np.empty(n_slots, dtype=bool)
        state = rng.random() < err_rate
        t = 0
        while t < n_slots:  # draw geometric run lengths
            run = int(rng.geometric(p_bg if state else p_gb))
            bad[t:t + run] = state
            t += run
            state = not state
    u = rng.random(n_slots)
    return np.where(bad, u < p_loss_bad, u < p_loss_good)


def ge_steady_state(burst_len: float, err_rate: float) -> float:
    return err_rate


def iid_loss(rng, n_slots: int, per: float) -> np.ndarray:
    return rng.random(n_slots) < per


def _on_periods(rng, t_us, duty, period_us):
    """Long on/off cycle with random phase: on for duty*period of every period."""
    if duty <= 0:
        return np.zeros(t_us.shape, dtype=bool)
    phase = rng.uniform(0, period_us)
    return ((t_us + phase) % period_us) < duty * period_us


def jammer_fn(rng, jam: dict | None, n: int, period_us: float, airtime_us: float,
              n_ch: int, protocol: str, sync_channel: int):
    """jam = {type, duty, coverage, cycle_s}. Returns lost(t, ch) for slot(s) t on channel(s) ch.

    constant   : fixed random channel set (coverage*N), on duty*cycle of every cycle_s
    sweep      : contiguous block of coverage*N channels sweeping the band every 8 ms,
                 on duty*cycle of every cycle_s
    duty_cycle : covered set, on/off in independent 50 ms blocks with P(on) = duty
    reactive   : detects a packet on a covered channel and jams it with P = duty
                 (reaction time assumed shorter than the airtime)
    selective  : broadband (coverage) bursts on duty*cycle like `constant`, and in between
                 parks on the channel it believes carries resynchronisation: the sync
                 channel for stock/expctr (public), a random guess for proposed (the
                 rendezvous channels are key-derived)
    sync_only  : parks on that same channel only, no broadband bursts
    """
    if not jam or jam.get("type") in (None, "none") or (
            jam.get("duty", 0) <= 0 and jam["type"] not in ("selective", "sync_only")):
        return lambda t, c: False
    kind, duty, cov = jam["type"], float(jam.get("duty", 0)), float(jam.get("coverage", 1.0))
    cycle_us = float(jam.get("cycle_s", 10.0)) * 1e6
    t_us = np.arange(n) * period_us
    k = max(1, int(round(cov * n_ch)))
    covered = np.zeros(n_ch, dtype=bool)
    covered[rng.choice(n_ch, size=k, replace=False)] = True

    if kind == "constant":
        on = _on_periods(rng, t_us, duty, cycle_us)
        return lambda t, c: covered[c] & on[t]
    if kind == "sweep":
        sweep_us = 8000.0
        start = rng.uniform(0, n_ch)
        # block position at packet mid-time; packet hit if its channel is inside the block
        pos = (start + (t_us + airtime_us / 2) / sweep_us * n_ch) % n_ch
        on = _on_periods(rng, t_us, duty, cycle_us)
        return lambda t, c: (((c - pos[t]) % n_ch) < k) & on[t]
    if kind == "duty_cycle":
        block = (t_us // 50_000).astype(np.int64)
        on_block = rng.random(block.max() + 1) < duty
        return lambda t, c: covered[c] & on_block[block[t]]
    if kind == "reactive":
        hit = rng.random(n) < duty
        return lambda t, c: covered[c] & hit[t]
    if kind in ("selective", "sync_only"):
        burst = _on_periods(rng, t_us, duty, cycle_us) if kind == "selective" else np.zeros(n, dtype=bool)
        target = sync_channel if protocol in ("stock", "expctr") else int(rng.integers(n_ch))
        return lambda t, c: (burst[t] & covered[c]) | (c == target)
    raise ValueError(kind)
