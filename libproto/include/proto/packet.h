/* Compact authenticated OTA packet with an implicit nonce.
 *
 * Layout follows ExpressLRS OTA_Packet4_s (8 bytes): byte0 bits 0-1 = type,
 * the 14 bits ExpressLRS spends on CRC (byte0 bits 2-7 + byte7) carry the tag.
 * Tags longer than 14 bits borrow payload bits from the packet tail (byte6,
 * byte5, byte4 bits 0-1), so up to 32 bits. The nonce is the 64-bit slot index;
 * it is never sent.
 *
 * tag = trunc_t( MAC(K_mac, drone_id || dir || slot || packet with tag bits zeroed) )
 */
#ifndef PROTO_PACKET_H
#define PROTO_PACKET_H

#include "proto/crypto_backend.h"

#define PROTO_PKT_LEN 8
#define PROTO_TAG_MIN 1
#define PROTO_TAG_MAX 32
#define PROTO_TAG_NATIVE 14 /* bits available without touching the payload */

typedef struct {
    proto_key_t k_mac;
    uint8_t drone_id;
    uint8_t dir; /* 0 = uplink (TX->RX), 1 = downlink */
    uint8_t tag_bits;
} proto_link_t;

/* Payload bits left for control data at a given tag length (48 at <= 14). */
unsigned proto_payload_bits(unsigned tag_bits);

uint32_t proto_tag_compute(const proto_link_t *l, uint64_t slot, const uint8_t pkt[PROTO_PKT_LEN]);
uint32_t proto_tag_extract(const proto_link_t *l, const uint8_t pkt[PROTO_PKT_LEN]);

/* Writes the tag for `slot` into pkt (type/payload already filled; tag bits overwritten). */
void proto_seal(const proto_link_t *l, uint64_t slot, uint8_t pkt[PROTO_PKT_LEN]);

/* 1 if the tag is valid for `slot`, else 0. */
int proto_open(const proto_link_t *l, uint64_t slot, const uint8_t pkt[PROTO_PKT_LEN]);

/* Window search for a receiver whose slot estimate may be off.
 * Tries slots center, center+1, center-1, center+2, ... (window candidates in total),
 * skipping any slot <= last_accepted (replay protection; pass UINT64_MAX-style
 * sentinel PROTO_NO_SLOT when nothing has been accepted yet).
 * Returns 1 and sets *offset (accepted slot - center) on success, else 0.
 * *tries counts MAC verifications performed. */
#define PROTO_NO_SLOT ((uint64_t)-1)
int proto_open_window(const proto_link_t *l, uint64_t center, uint32_t window,
                      uint64_t last_accepted, const uint8_t pkt[PROTO_PKT_LEN],
                      int64_t *offset, uint32_t *tries);

#endif
