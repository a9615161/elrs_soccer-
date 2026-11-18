#include "proto/packet.h"

/* Tag bit i lives at TAG_POS[i] = byte * 8 + bit. First 14 = ExpressLRS CRC14 bits. */
static const uint8_t TAG_POS[PROTO_TAG_MAX] = {
    /* byte0 bits 2..7 */ 2, 3, 4, 5, 6, 7,
    /* byte7 */ 56, 57, 58, 59, 60, 61, 62, 63,
    /* byte6 */ 48, 49, 50, 51, 52, 53, 54, 55,
    /* byte5 */ 40, 41, 42, 43, 44, 45, 46, 47,
    /* byte4 bits 0..1 */ 32, 33,
};

unsigned proto_payload_bits(unsigned tag_bits)
{
    return tag_bits <= PROTO_TAG_NATIVE ? 48u : 48u - (tag_bits - PROTO_TAG_NATIVE);
}

static unsigned clamp_tag(unsigned t)
{
    return t < PROTO_TAG_MIN ? PROTO_TAG_MIN : (t > PROTO_TAG_MAX ? PROTO_TAG_MAX : t);
}

uint32_t proto_tag_extract(const proto_link_t *l, const uint8_t pkt[PROTO_PKT_LEN])
{
    unsigned i, t = clamp_tag(l->tag_bits);
    uint32_t tag = 0;

    for (i = 0; i < t; i++)
        tag |= (uint32_t)((pkt[TAG_POS[i] >> 3] >> (TAG_POS[i] & 7)) & 1u) << i;
    return tag;
}

static void tag_insert(unsigned t, uint8_t pkt[PROTO_PKT_LEN], uint32_t tag)
{
    unsigned i;

    for (i = 0; i < t; i++) {
        uint8_t mask = (uint8_t)(1u << (TAG_POS[i] & 7));
        if ((tag >> i) & 1u)
            pkt[TAG_POS[i] >> 3] |= mask;
        else
            pkt[TAG_POS[i] >> 3] &= (uint8_t)~mask;
    }
}

uint32_t proto_tag_compute(const proto_link_t *l, uint64_t slot, const uint8_t pkt[PROTO_PKT_LEN])
{
    uint8_t msg[2 + 8 + PROTO_PKT_LEN], out[PROTO_PRF_LEN];
    unsigned i, t = clamp_tag(l->tag_bits);
    uint32_t v;

    msg[0] = l->drone_id;
    msg[1] = l->dir;
    for (i = 0; i < 8; i++)
        msg[2 + i] = (uint8_t)(slot >> (8 * i));
    for (i = 0; i < PROTO_PKT_LEN; i++)
        msg[10 + i] = pkt[i];
    tag_insert(t, msg + 10, 0);
    proto_mac_prf(&l->k_mac, msg, sizeof msg, out);
    v = (uint32_t)out[0] | ((uint32_t)out[1] << 8) | ((uint32_t)out[2] << 16) | ((uint32_t)out[3] << 24);
    return t == 32 ? v : (v & ((1u << t) - 1));
}

void proto_seal(const proto_link_t *l, uint64_t slot, uint8_t pkt[PROTO_PKT_LEN])
{
    tag_insert(clamp_tag(l->tag_bits), pkt, proto_tag_compute(l, slot, pkt));
}

int proto_open(const proto_link_t *l, uint64_t slot, const uint8_t pkt[PROTO_PKT_LEN])
{
    return proto_tag_compute(l, slot, pkt) == proto_tag_extract(l, pkt);
}

int proto_open_window(const proto_link_t *l, uint64_t center, uint32_t window,
                      uint64_t last_accepted, const uint8_t pkt[PROTO_PKT_LEN],
                      int64_t *offset, uint32_t *tries)
{
    uint32_t tag = proto_tag_extract(l, pkt), k;
    uint32_t n = 0;

    for (k = 0; k < window; k++) {
        /* k = 0, 1, 2, 3, ... -> d = 0, +1, -1, +2, -2, ... */
        int64_t d = (k & 1) ? (int64_t)(k + 1) / 2 : -(int64_t)(k / 2);
        uint64_t s = center + (uint64_t)d;

        if ((d < 0 && (uint64_t)(-d) > center) || (last_accepted != PROTO_NO_SLOT && s <= last_accepted))
            continue;
        n++;
        if (proto_tag_compute(l, s, pkt) == tag) {
            if (offset) *offset = d;
            if (tries) *tries = n;
            return 1;
        }
    }
    if (tries) *tries = n;
    return 0;
}
