#include "proto/hop_gap.h"

#define GAP_STREAM_TAG 0xFD

/* Bit stream from PRF(K, slot || tag || ctr16), consumed LSB-first. */
typedef struct {
    const proto_key_t *k;
    uint64_t slot;
    uint16_t ctr;
    uint64_t buf;
    unsigned avail;
} bitstream_t;

static void refill(bitstream_t *s)
{
    uint8_t msg[11], out[PROTO_PRF_LEN];
    int i;

    for (i = 0; i < 8; i++)
        msg[i] = (uint8_t)(s->slot >> (8 * i));
    msg[8] = GAP_STREAM_TAG;
    msg[9] = (uint8_t)s->ctr;
    msg[10] = (uint8_t)(s->ctr >> 8);
    s->ctr++;
    proto_prf(s->k, msg, sizeof msg, out);
    s->buf = 0;
    for (i = 0; i < 8; i++)
        s->buf |= (uint64_t)out[i] << (8 * i);
    s->avail = 64;
}

static unsigned take_bits(bitstream_t *s, unsigned bits)
{
    unsigned v;

    if (s->avail < bits)
        refill(s); /* discard the remainder; keeps draws independent of block edges */
    v = (unsigned)(s->buf & ((1u << bits) - 1));
    s->buf >>= bits;
    s->avail -= bits;
    return v;
}

/* Uniform in [0, n), n >= 1, by rejection on the smallest covering power of two. */
static unsigned uniform(bitstream_t *s, unsigned n)
{
    unsigned bits = 0, v;

    if (n <= 1)
        return 0;
    while ((1u << bits) < n)
        bits++;
    do {
        v = take_bits(s, bits);
    } while (v >= n);
    return v;
}

int proto_hop_gap_slot(const proto_key_t *k_hop, uint64_t slot, uint8_t n_channels,
                       uint8_t n_drones, uint8_t gap, uint8_t *out)
{
    uint8_t pool[PROTO_HOP_GAP_MAX_CH], pick[PROTO_HOP_GAP_MAX_CH], perm[PROTO_HOP_GAP_MAX_CH];
    unsigned n = n_channels, m = n_drones, g = gap, p, i, j, r;
    bitstream_t s = {k_hop, slot, 0, 0, 0};
    uint8_t t;

    if (n == 0 || n > PROTO_HOP_GAP_MAX_CH || m == 0 || g == 0 || m * g > n)
        return -1;
    p = n - m * (g - 1);

    /* 1. M distinct values from [0, P): partial Fisher-Yates */
    for (i = 0; i < p; i++)
        pool[i] = (uint8_t)i;
    for (i = 0; i < m; i++) {
        j = i + uniform(&s, p - i);
        t = pool[i]; pool[i] = pool[j]; pool[j] = t;
    }
    /* 2. sort (insertion; M is small) and spread */
    for (i = 0; i < m; i++) {
        t = pool[i];
        for (j = i; j > 0 && pick[j - 1] > t; j--)
            pick[j] = pick[j - 1];
        pick[j] = t;
    }
    for (i = 0; i < m; i++)
        pick[i] = (uint8_t)(pick[i] + i * (g - 1));
    /* 3. assign to drones: uniform permutation */
    for (i = 0; i < m; i++)
        perm[i] = (uint8_t)i;
    for (i = m - 1; i > 0; i--) {
        j = uniform(&s, i + 1);
        t = perm[i]; perm[i] = perm[j]; perm[j] = t;
    }
    /* 4. rotate */
    r = uniform(&s, n);
    for (i = 0; i < m; i++)
        out[i] = (uint8_t)((pick[perm[i]] + r) % n);
    return 0;
}

uint8_t proto_hop_gap_channel(const proto_key_t *k_hop, uint64_t slot, uint8_t drone_id,
                              uint8_t n_channels, uint8_t n_drones, uint8_t gap)
{
    uint8_t out[PROTO_HOP_GAP_MAX_CH];

    if (drone_id >= n_drones || proto_hop_gap_slot(k_hop, slot, n_channels, n_drones, gap, out))
        return 0xFF;
    return out[drone_id];
}

int proto_hop_gap_block(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                        uint8_t n_channels, uint8_t n_drones, uint8_t gap, uint8_t *out)
{
    size_t t;

    for (t = 0; t < count; t++)
        if (proto_hop_gap_slot(k_hop, slot0 + t, n_channels, n_drones, gap,
                               out + t * n_drones))
            return -1;
    return 0;
}
