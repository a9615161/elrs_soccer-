#include "proto/hop.h"

#define BITS_A 3 /* left half width at round 0 */
#define BITS_B 4 /* right half width at round 0 */

/* F(slot, round, half) truncated to `bits` bits. msg = slot(LE64) || round || half. */
static uint8_t round_fn(const proto_key_t *k, uint64_t slot, uint8_t round,
                        uint8_t half, unsigned bits)
{
    uint8_t msg[10], out[PROTO_PRF_LEN];
    int i;

    for (i = 0; i < 8; i++)
        msg[i] = (uint8_t)(slot >> (8 * i));
    msg[8] = round;
    msg[9] = half;
    proto_prf(k, msg, sizeof msg, out);
    return (uint8_t)(out[0] & ((1u << bits) - 1));
}

/* State (L: wl bits, R: wr bits). Each round: (L, R) -> (R, L ^ F(R)),
 * so the half widths alternate 3/4 -> 4/3 -> 3/4 ... Every round is invertible;
 * with an even round count the final layout is again (3, 4). */
uint8_t proto_hop_prp7_r(const proto_key_t *k_hop, uint64_t slot, uint8_t x, uint8_t rounds)
{
    unsigned wl = BITS_A, wr = BITS_B, tmp;
    uint8_t l = (uint8_t)((x >> BITS_B) & ((1u << BITS_A) - 1));
    uint8_t r = (uint8_t)(x & ((1u << BITS_B) - 1));
    uint8_t nl, nr;
    uint8_t rnd;

    for (rnd = 0; rnd < rounds; rnd++) {
        nl = r;
        nr = (uint8_t)(l ^ round_fn(k_hop, slot, rnd, r, wl));
        l = nl;
        r = nr;
        tmp = wl; wl = wr; wr = tmp;
    }
    return (uint8_t)((l << wr) | r);
}

uint8_t proto_hop_prp7(const proto_key_t *k_hop, uint64_t slot, uint8_t x)
{
    return proto_hop_prp7_r(k_hop, slot, x, PROTO_HOP_ROUNDS);
}

uint8_t proto_hop_channel_r(const proto_key_t *k_hop, uint64_t slot,
                            uint8_t drone_id, uint8_t n_channels, uint8_t rounds)
{
    uint8_t y = drone_id;

    if (n_channels == 0 || n_channels > PROTO_HOP_DOMAIN || drone_id >= n_channels ||
        rounds == 0 || rounds >= 0xF0)
        return 0xFF;
    /* Cycle-walking: terminates because drone_id itself lies in [0, n). */
    do {
        y = proto_hop_prp7_r(k_hop, slot, y, rounds);
    } while (y >= n_channels);
    return y;
}

uint8_t proto_hop_channel(const proto_key_t *k_hop, uint64_t slot,
                          uint8_t drone_id, uint8_t n_channels)
{
    return proto_hop_channel_r(k_hop, slot, drone_id, n_channels, PROTO_HOP_ROUNDS);
}

int proto_hop_sequence_r(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                         uint8_t drone_id, uint8_t n_channels, uint8_t rounds, uint8_t *out)
{
    size_t i;

    for (i = 0; i < count; i++) {
        out[i] = proto_hop_channel_r(k_hop, slot0 + i, drone_id, n_channels, rounds);
        if (out[i] == 0xFF)
            return -1;
    }
    return 0;
}

/* Round byte outside [0, PROTO_HOP_ROUNDS) separates the offset PRF from the Feistel rounds. */
#define OFFSET_ROUND_TAG 0xFE

uint8_t proto_hop_channel_spaced(const proto_key_t *k_hop, uint64_t slot,
                                 uint8_t drone_id, uint8_t n_channels, uint8_t spacing)
{
    uint8_t n_sub, p, b;

    if (spacing == 0 || n_channels == 0 || n_channels > PROTO_HOP_DOMAIN)
        return 0xFF;
    if (spacing == 1)
        return proto_hop_channel(k_hop, slot, drone_id, n_channels);
    n_sub = (uint8_t)(n_channels / spacing);
    if (drone_id >= n_sub)
        return 0xFF;
    p = proto_hop_channel(k_hop, slot, drone_id, n_sub);
    b = (uint8_t)(round_fn(k_hop, slot, OFFSET_ROUND_TAG, 0, 8) % spacing);
    return (uint8_t)(spacing * p + b);
}

int proto_hop_sequence_spaced(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                              uint8_t drone_id, uint8_t n_channels, uint8_t spacing,
                              uint8_t *out)
{
    size_t i;

    for (i = 0; i < count; i++) {
        out[i] = proto_hop_channel_spaced(k_hop, slot0 + i, drone_id, n_channels, spacing);
        if (out[i] == 0xFF)
            return -1;
    }
    return 0;
}

int proto_hop_sequence(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                       uint8_t drone_id, uint8_t n_channels, uint8_t *out)
{
    size_t i;

    if (n_channels == 0 || n_channels > PROTO_HOP_DOMAIN || drone_id >= n_channels)
        return -1;
    for (i = 0; i < count; i++)
        out[i] = proto_hop_channel(k_hop, slot0 + i, drone_id, n_channels);
    return 0;
}
