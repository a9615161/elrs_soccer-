"""cffi (ABI mode) binding for libproto.so."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from cffi import FFI

_CDEF = """
typedef struct { uint8_t b[16]; } proto_key_t;
typedef struct { uint64_t prf; uint64_t mac; uint64_t block; } proto_opcount_t;
typedef struct { proto_key_t k_hop; proto_key_t k_mac; proto_key_t k_resync; } proto_subkeys_t;

void proto_siphash24(const uint8_t key[16], const uint8_t *msg, size_t len, uint8_t out[8]);
void proto_opcount_get(proto_opcount_t *out);
void proto_opcount_reset(void);
int proto_kdf_all(const proto_key_t *session_key, const uint8_t *field_id,
                  size_t field_id_len, proto_subkeys_t *out);
uint8_t proto_hop_prp7(const proto_key_t *k_hop, uint64_t slot, uint8_t x);
uint8_t proto_hop_channel(const proto_key_t *k_hop, uint64_t slot, uint8_t drone_id, uint8_t n_channels);
int proto_hop_sequence(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                       uint8_t drone_id, uint8_t n_channels, uint8_t *out);
uint8_t proto_hop_channel_spaced(const proto_key_t *k_hop, uint64_t slot,
                                 uint8_t drone_id, uint8_t n_channels, uint8_t spacing);
int proto_hop_sequence_spaced(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                              uint8_t drone_id, uint8_t n_channels, uint8_t spacing,
                              uint8_t *out);
int proto_hop_sequence_r(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                         uint8_t drone_id, uint8_t n_channels, uint8_t rounds, uint8_t *out);
int proto_hop_gap_slot(const proto_key_t *k_hop, uint64_t slot, uint8_t n_channels,
                       uint8_t n_drones, uint8_t gap, uint8_t *out);
typedef struct { proto_key_t k_mac; uint8_t drone_id; uint8_t dir; uint8_t tag_bits; } proto_link_t;
typedef struct { uint32_t suspect_after; uint32_t lost_after; uint32_t w_suspect; uint32_t w_lost; } proto_rs_cfg_t;
typedef struct { int state; uint64_t last_accepted; uint64_t last_valid_local; uint32_t miss_run;
                 uint64_t last_beacon; } proto_rs_t;
unsigned proto_payload_bits(unsigned tag_bits);
void proto_seal(const proto_link_t *l, uint64_t slot, uint8_t pkt[8]);
int proto_open(const proto_link_t *l, uint64_t slot, const uint8_t pkt[8]);
int proto_open_window(const proto_link_t *l, uint64_t center, uint32_t window, uint64_t last_accepted,
                      const uint8_t pkt[8], int64_t *offset, uint32_t *tries);
void proto_rs_init(proto_rs_t *rs, uint64_t now_local);
uint32_t proto_rs_window(const proto_rs_t *rs, const proto_rs_cfg_t *cfg);
int proto_rs_on_slot(proto_rs_t *rs, const proto_rs_cfg_t *cfg, uint64_t now_local, int accepted,
                     uint64_t accepted_slot);
void proto_beacon_seal(const proto_key_t *k_resync, uint8_t drone_id, uint64_t slot, uint8_t pkt[8]);
int proto_beacon_open(proto_rs_t *rs, const proto_key_t *k_resync, uint8_t drone_id, const uint8_t pkt[8],
                      uint64_t *slot);
uint8_t proto_rendezvous_channel(const proto_key_t *k_resync, uint64_t epoch, uint8_t n_channels);
int proto_hop_gap_block(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                        uint8_t n_channels, uint8_t n_drones, uint8_t gap, uint8_t *out);
"""

_ROOT = Path(__file__).resolve().parents[1]
_LIB_PATH = Path(os.environ.get("LIBPROTO_PATH", _ROOT / "build" / "libproto.so"))

ffi = FFI()
ffi.cdef(_CDEF)
lib = ffi.dlopen(str(_LIB_PATH))


def siphash24(key: bytes, msg: bytes) -> bytes:
    out = ffi.new("uint8_t[8]")
    lib.proto_siphash24(key, msg, len(msg), out)
    return bytes(out)


def _key(b: bytes):
    if len(b) != 16:
        raise ValueError("key must be 16 bytes")
    k = ffi.new("proto_key_t *")
    ffi.memmove(k.b, b, 16)
    return k


class Proto:
    """Proposed protocol handle bound to one (session key, field id)."""

    def __init__(self, session_key: bytes, field_id: bytes):
        self._sk = _key(session_key)
        self._sub = ffi.new("proto_subkeys_t *")
        if lib.proto_kdf_all(self._sk, field_id, len(field_id), self._sub) != 0:
            raise ValueError("field_id too long")
        self.k_hop = bytes(self._sub.k_hop.b)
        self.k_mac = bytes(self._sub.k_mac.b)
        self.k_resync = bytes(self._sub.k_resync.b)

    def hop_channel(self, slot: int, drone_id: int, n_channels: int) -> int:
        c = lib.proto_hop_channel(ffi.addressof(self._sub, "k_hop"), slot, drone_id, n_channels)
        if c == 0xFF:
            raise ValueError("bad drone_id / n_channels")
        return c

    def hop_sequence(self, slot0: int, count: int, drone_id: int, n_channels: int) -> np.ndarray:
        out = np.empty(count, dtype=np.uint8)
        rc = lib.proto_hop_sequence(ffi.addressof(self._sub, "k_hop"), slot0, count,
                                    drone_id, n_channels, ffi.from_buffer("uint8_t[]", out))
        if rc != 0:
            raise ValueError("bad drone_id / n_channels")
        return out

    def hop_sequence_spaced(self, slot0: int, count: int, drone_id: int, n_channels: int,
                            spacing: int) -> np.ndarray:
        out = np.empty(count, dtype=np.uint8)
        rc = lib.proto_hop_sequence_spaced(ffi.addressof(self._sub, "k_hop"), slot0, count, drone_id,
                                           n_channels, spacing, ffi.from_buffer("uint8_t[]", out))
        if rc != 0:
            raise ValueError("bad drone_id / n_channels / spacing")
        return out

    def hop_sequence_rounds(self, slot0: int, count: int, drone_id: int, n_channels: int,
                            rounds: int) -> np.ndarray:
        out = np.empty(count, dtype=np.uint8)
        rc = lib.proto_hop_sequence_r(ffi.addressof(self._sub, "k_hop"), slot0, count, drone_id,
                                      n_channels, rounds, ffi.from_buffer("uint8_t[]", out))
        if rc != 0:
            raise ValueError("bad drone_id / n_channels / rounds")
        return out

    def hop_gap_block(self, slot0: int, count: int, n_channels: int, n_drones: int,
                      gap: int) -> np.ndarray:
        """Channels of all drones, shape (n_drones, count)."""
        out = np.empty(count * n_drones, dtype=np.uint8)
        rc = lib.proto_hop_gap_block(ffi.addressof(self._sub, "k_hop"), slot0, count, n_channels,
                                     n_drones, gap, ffi.from_buffer("uint8_t[]", out))
        if rc != 0:
            raise ValueError("bad n_channels / n_drones / gap")
        return out.reshape(count, n_drones).T.copy()

    def rendezvous_channel(self, epoch: int, n_channels: int) -> int:
        return lib.proto_rendezvous_channel(ffi.addressof(self._sub, "k_resync"), epoch, n_channels)

    def beacon_seal(self, drone_id: int, slot: int) -> bytes:
        buf = ffi.new("uint8_t[8]")
        lib.proto_beacon_seal(ffi.addressof(self._sub, "k_resync"), drone_id, slot, buf)
        return bytes(buf)

    def beacon_open(self, rs: "Resync", drone_id: int, pkt: bytes) -> int | None:
        """Slot carried by an authentic, non-replayed beacon, else None."""
        out = ffi.new("uint64_t *")
        ok = lib.proto_beacon_open(rs.rs, ffi.addressof(self._sub, "k_resync"), drone_id, pkt, out)
        return int(out[0]) if ok else None

    def prp7(self, slot: int, x: int) -> int:
        return lib.proto_hop_prp7(ffi.addressof(self._sub, "k_hop"), slot, x)


NO_SLOT = 2**64 - 1
LOCKED, SUSPECT, LOST = 0, 1, 2


class Link:
    """One direction of one drone's link (sealing / opening packets)."""

    def __init__(self, k_mac: bytes, drone_id: int, tag_bits: int = 14, direction: int = 0):
        self._l = ffi.new("proto_link_t *")
        ffi.memmove(self._l.k_mac.b, k_mac, 16)
        self._l.drone_id = drone_id
        self._l.dir = direction
        self._l.tag_bits = tag_bits
        self._buf = ffi.new("uint8_t[8]")
        self._off = ffi.new("int64_t *")
        self._tries = ffi.new("uint32_t *")

    def seal(self, slot: int, pkt: bytes) -> bytes:
        ffi.memmove(self._buf, pkt, 8)
        lib.proto_seal(self._l, slot, self._buf)
        return bytes(self._buf)

    def open(self, slot: int, pkt: bytes) -> bool:
        return bool(lib.proto_open(self._l, slot, pkt))

    def open_window(self, center: int, window: int, last_accepted: int, pkt: bytes):
        """Returns (ok, offset, tries)."""
        ok = lib.proto_open_window(self._l, center, window, last_accepted, pkt, self._off, self._tries)
        return bool(ok), int(self._off[0]), int(self._tries[0])


class Resync:
    """Receiver state machine (libproto resync.c)."""

    def __init__(self, suspect_after: int, lost_after: int, w_suspect: int, w_lost: int, now: int = 0):
        self.cfg = ffi.new("proto_rs_cfg_t *", [suspect_after, lost_after, w_suspect, w_lost])
        self.rs = ffi.new("proto_rs_t *")
        lib.proto_rs_init(self.rs, now)

    @property
    def state(self) -> int:
        return self.rs.state

    @property
    def last_accepted(self) -> int:
        return self.rs.last_accepted

    def force_lost(self) -> None:
        """Receiver rebooted: no clock and no last_accepted until the next beacon."""
        self.rs.state = LOST

    def window(self) -> int:
        return lib.proto_rs_window(self.rs, self.cfg)

    def on_slot(self, now: int, accepted: bool, accepted_slot: int = 0) -> int:
        return lib.proto_rs_on_slot(self.rs, self.cfg, now, int(accepted), accepted_slot)


def op_counts() -> dict:
    c = ffi.new("proto_opcount_t *")
    lib.proto_opcount_get(c)
    return {"prf": c.prf, "mac": c.mac, "block": c.block}


def op_counts_reset() -> None:
    lib.proto_opcount_reset()
