"""ExpressLRS 4.1.0 OTA4 CRC14 (lib/CRC/crc.cpp Crc2Byte, lib/OTA/OTA.cpp L28-38, L20-46).

crc init = ((UID4 << 8) | UID5) ^ (OTA_VERSION_ID << 8); per packet xor nonceValidator =
OtaNonce (8-bit) for normal packets and 0 for SYNC. Computed over bytes 0..6 with the
6 crcHigh bits (byte0 bits 2..7) zeroed; crcHigh | crcLow carry the 14-bit result.
"""

from __future__ import annotations

ELRS_CRC14_POLY = 0x2E57
OTA_VERSION_ID = 4
PACKET_TYPE_SYNC = 2


def _table(bits=14, poly=ELRS_CRC14_POLY):
    high = 1 << (bits - 1)
    tab = []
    for i in range(256):
        crc = i << (bits - 8)
        for _ in range(8):
            crc = ((crc << 1) ^ (poly if crc & high else 0)) & 0xFFFF
        tab.append(crc)
    return tab


_TAB = _table()


def crc14(data: bytes, crc: int) -> int:
    for b in data:
        crc = ((crc << 8) ^ _TAB[((crc >> 6) ^ b) & 0xFF]) & 0xFFFF
    return crc & 0x3FFF


def crc_init(uid4: int, uid5: int) -> int:
    return ((uid4 << 8) | uid5) ^ (OTA_VERSION_ID << 8)


def _nonce_validator(pkt: bytes, nonce: int) -> int:
    return 0 if (pkt[0] & 3) == PACKET_TYPE_SYNC else nonce & 0xFF


def seal(pkt: bytes, init: int, nonce: int) -> bytes:
    b = bytearray(pkt[:8])
    b[0] &= 0x03
    c = crc14(bytes(b[:7]), init ^ _nonce_validator(b, nonce))
    b[0] |= (c >> 8) << 2
    b[7] = c & 0xFF
    return bytes(b)


def valid(pkt: bytes, init: int, nonce: int) -> bool:
    b = bytearray(pkt[:8])
    got = ((b[0] >> 2) << 8) | b[7]
    b[0] &= 0x03
    return got == crc14(bytes(b[:7]), init ^ _nonce_validator(b, nonce))
