"""Stock ExpressLRS FHSS sequence (port of v4.1.0 src/lib/FHSS).

Mirrors random.cpp (LCG) and FHSS.cpp::FHSSrandomiseFHSSsequenceBuild bit-for-bit;
tests/test_elrs_stock.py checks it against vectors built from the real C++ sources.
"""

from __future__ import annotations

import numpy as np

FHSS_SEQUENCE_LEN = 256  # FHSS.h
OTA_VERSION_ID = 4  # include/targets.h


class _Lcg:
    """random.cpp: seed = (214013 * seed + 2531011) % 2^31 in uint32 arithmetic."""

    def __init__(self, seed: int):
        self.seed = seed & 0xFFFFFFFF

    def rng(self) -> int:
        self.seed = ((214013 * self.seed + 2531011) & 0xFFFFFFFF) % 2147483648
        return self.seed >> 16

    def rng_n(self, maximum: int) -> int:
        return self.rng() % maximum


def uid_seed(uid: bytes) -> int:
    """OTA.cpp::OtaGetUidSeed (uses UID[2..5])."""
    return (uid[2] << 24) + (uid[3] << 16) + (uid[4] << 8) + (uid[5] ^ OTA_VERSION_ID)


def build_sequence(seed: int, freq_count: int = 80, sync_channel: int | None = None) -> np.ndarray:
    """Return the FHSS index sequence (length = (256 // N) * N)."""
    if sync_channel is None:
        sync_channel = freq_count // 2
    count = (FHSS_SEQUENCE_LEN // freq_count) * freq_count
    seq = np.empty(count, dtype=np.uint8)
    for i in range(count):
        if i % freq_count == 0:
            seq[i] = sync_channel
        elif i % freq_count == sync_channel:
            seq[i] = 0
        else:
            seq[i] = i % freq_count

    lcg = _Lcg(seed)
    for i in range(count):
        if i % freq_count != 0:
            offset = (i // freq_count) * freq_count
            r = lcg.rng_n(freq_count - 1) + 1
            j = offset + r
            seq[i], seq[j] = seq[j], seq[i]
    return seq


def hop_channels(uid: bytes, n_hops: int, start_ptr: int = 0, freq_count: int = 80) -> np.ndarray:
    """Channel for hops start_ptr+1, start_ptr+2, ... (FHSSgetNextFreq pre-increments)."""
    seq = build_sequence(uid_seed(uid), freq_count)
    idx = (start_ptr + 1 + np.arange(n_hops)) % len(seq)
    return seq[idx]
