#include "proto/resync.h"

#define BEACON_TYPE 3u
#define BEACON_TAG_BITS 30u
#define BEACON_CTR_BYTES 4
#define RENDEZVOUS_TAG 0xF1

void proto_rs_init(proto_rs_t *rs, uint64_t now_local)
{
    rs->state = PROTO_LOCKED;
    rs->last_accepted = PROTO_NO_SLOT;
    rs->last_valid_local = now_local;
    rs->miss_run = 0;
    rs->last_beacon = PROTO_NO_SLOT;
}

uint32_t proto_rs_window(const proto_rs_t *rs, const proto_rs_cfg_t *cfg)
{
    switch (rs->state) {
    case PROTO_SUSPECT: return cfg->w_suspect;
    case PROTO_LOST: return cfg->w_lost;
    default: return 1;
    }
}

proto_rs_state_t proto_rs_on_slot(proto_rs_t *rs, const proto_rs_cfg_t *cfg, uint64_t now_local,
                                  int accepted, uint64_t accepted_slot)
{
    if (accepted) {
        rs->state = PROTO_LOCKED;
        rs->last_accepted = accepted_slot;
        rs->last_valid_local = now_local;
        rs->miss_run = 0;
        return rs->state;
    }
    rs->miss_run++;
    if (now_local - rs->last_valid_local >= cfg->lost_after)
        rs->state = PROTO_LOST;
    else if (rs->state == PROTO_LOCKED && rs->miss_run >= cfg->suspect_after)
        rs->state = PROTO_SUSPECT;
    return rs->state;
}

/* Beacon: byte0 = type | tag, bytes1..4 = slot (32 bit LE), bytes5..7 = tag (30-bit tag,
 * the same bit budget as a SYNC without UID4/UID5). MAC uses a link with dir = 2 so it
 * never collides with data packets. */
static void beacon_link(proto_link_t *l, const proto_key_t *k_resync, uint8_t drone_id)
{
    l->k_mac = *k_resync;
    l->drone_id = drone_id;
    l->dir = 2;
    l->tag_bits = BEACON_TAG_BITS;
}

void proto_beacon_seal(const proto_key_t *k_resync, uint8_t drone_id, uint64_t slot,
                       uint8_t pkt[PROTO_PKT_LEN])
{
    proto_link_t l;
    int i;

    beacon_link(&l, k_resync, drone_id);
    slot &= 0xFFFFFFFFu;
    pkt[0] = BEACON_TYPE;
    for (i = 0; i < BEACON_CTR_BYTES; i++)
        pkt[1 + i] = (uint8_t)(slot >> (8 * i));
    pkt[5] = pkt[6] = pkt[7] = 0;
    proto_seal(&l, slot, pkt);
}

int proto_beacon_open(proto_rs_t *rs, const proto_key_t *k_resync, uint8_t drone_id,
                      const uint8_t pkt[PROTO_PKT_LEN], uint64_t *slot)
{
    proto_link_t l;
    uint64_t s = 0;
    int i;

    if ((pkt[0] & 3u) != BEACON_TYPE)
        return 0;
    for (i = 0; i < BEACON_CTR_BYTES; i++)
        s |= (uint64_t)pkt[1 + i] << (8 * i);
    beacon_link(&l, k_resync, drone_id);
    if (!proto_open(&l, s, pkt))
        return 0;
    if (rs->last_beacon != PROTO_NO_SLOT && s <= rs->last_beacon)
        return 0; /* replay */
    rs->last_beacon = s;
    if (slot) *slot = s;
    return 1;
}

uint8_t proto_rendezvous_channel(const proto_key_t *k_resync, uint64_t epoch, uint8_t n_channels)
{
    uint8_t msg[9], out[PROTO_PRF_LEN];
    uint64_t v = 0;
    int i;

    for (i = 0; i < 8; i++)
        msg[i] = (uint8_t)(epoch >> (8 * i));
    msg[8] = RENDEZVOUS_TAG;
    proto_prf(k_resync, msg, sizeof msg, out);
    for (i = 0; i < 8; i++)
        v |= (uint64_t)out[i] << (8 * i);
    return n_channels ? (uint8_t)(v % n_channels) : 0; /* 64-bit value: bias < 2^-57 */
}
