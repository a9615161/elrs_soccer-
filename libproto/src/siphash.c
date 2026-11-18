/* SipHash-2-4, after the reference implementation by Aumasson & Bernstein. */
#include "proto/crypto_backend.h"

#define ROTL(x, b) (uint64_t)(((x) << (b)) | ((x) >> (64 - (b))))

#define SIPROUND                                                     \
    do {                                                             \
        v0 += v1; v1 = ROTL(v1, 13); v1 ^= v0; v0 = ROTL(v0, 32);    \
        v2 += v3; v3 = ROTL(v3, 16); v3 ^= v2;                       \
        v0 += v3; v3 = ROTL(v3, 21); v3 ^= v0;                       \
        v2 += v1; v1 = ROTL(v1, 17); v1 ^= v2; v2 = ROTL(v2, 32);    \
    } while (0)

static uint64_t load64_le(const uint8_t *p)
{
    return (uint64_t)p[0] | ((uint64_t)p[1] << 8) | ((uint64_t)p[2] << 16) |
           ((uint64_t)p[3] << 24) | ((uint64_t)p[4] << 32) |
           ((uint64_t)p[5] << 40) | ((uint64_t)p[6] << 48) |
           ((uint64_t)p[7] << 56);
}

void proto_siphash24(const uint8_t key[16], const uint8_t *msg, size_t len,
                     uint8_t out[8])
{
    uint64_t k0 = load64_le(key), k1 = load64_le(key + 8);
    uint64_t v0 = 0x736f6d6570736575ULL ^ k0;
    uint64_t v1 = 0x646f72616e646f6dULL ^ k1;
    uint64_t v2 = 0x6c7967656e657261ULL ^ k0;
    uint64_t v3 = 0x7465646279746573ULL ^ k1;
    uint64_t b = (uint64_t)len << 56;
    const uint8_t *end = msg + (len - (len % 8));
    const uint8_t *p;
    int i;

    for (p = msg; p != end; p += 8) {
        uint64_t m = load64_le(p);
        v3 ^= m;
        SIPROUND; SIPROUND;
        v0 ^= m;
    }
    for (i = (int)(len & 7) - 1; i >= 0; i--)
        b |= (uint64_t)end[i] << (8 * i);

    v3 ^= b;
    SIPROUND; SIPROUND;
    v0 ^= b;
    v2 ^= 0xff;
    SIPROUND; SIPROUND; SIPROUND; SIPROUND;
    b = v0 ^ v1 ^ v2 ^ v3;
    for (i = 0; i < 8; i++)
        out[i] = (uint8_t)(b >> (8 * i));
}

static void siphash_prf(const proto_key_t *key, const uint8_t *msg, size_t len,
                        uint8_t out[PROTO_PRF_LEN])
{
    proto_siphash24(key->b, msg, len, out);
}

const proto_crypto_backend_t proto_backend_siphash24 = {"siphash24", siphash_prf};
