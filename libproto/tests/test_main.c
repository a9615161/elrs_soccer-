/* libproto unit tests. Usage: test_proto [prp_slots]  (default 1000000) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "proto/crypto_backend.h"
#include "proto/hop.h"
#include "proto/hop_gap.h"
#include "proto/kdf.h"
#include "proto/packet.h"
#include "proto/resync.h"

static int g_fail;

#define CHECK(cond, ...)                                       \
    do {                                                       \
        if (!(cond)) {                                         \
            g_fail++;                                          \
            printf("  FAIL %s:%d: ", __FILE__, __LINE__);      \
            printf(__VA_ARGS__);                               \
            printf("\n");                                      \
        }                                                      \
    } while (0)

/* SipHash-2-4 reference vectors: key = 00..0f, msg = 00..(len-1). */
static const struct { size_t len; uint8_t out[8]; } SIP_KAT[] = {
    {0,  {0x31, 0x0e, 0x0e, 0xdd, 0x47, 0xdb, 0x6f, 0x72}},
    {1,  {0xfd, 0x67, 0xdc, 0x93, 0xc5, 0x39, 0xf8, 0x74}},
    {2,  {0x5a, 0x4f, 0xa9, 0xd9, 0x09, 0x80, 0x6c, 0x0d}},
    {3,  {0x2d, 0x7e, 0xfb, 0xd7, 0x96, 0x66, 0x67, 0x85}},
    {4,  {0xb7, 0x87, 0x71, 0x27, 0xe0, 0x94, 0x27, 0xcf}},
    {5,  {0x8d, 0xa6, 0x99, 0xcd, 0x64, 0x55, 0x76, 0x18}},
    {6,  {0xce, 0xe3, 0xfe, 0x58, 0x6e, 0x46, 0xc9, 0xcb}},
    {7,  {0x37, 0xd1, 0x01, 0x8b, 0xf5, 0x00, 0x02, 0xab}},
    {15, {0xe5, 0x45, 0xbe, 0x49, 0x61, 0xca, 0x29, 0xa1}}, /* paper App. A */
    {63, {0x72, 0x45, 0x06, 0xeb, 0x4c, 0x32, 0x8a, 0x95}},
};

static void test_siphash_kat(void)
{
    uint8_t key[16], msg[64], out[8];
    size_t i;

    printf("[siphash_kat]\n");
    for (i = 0; i < 16; i++) key[i] = (uint8_t)i;
    for (i = 0; i < 64; i++) msg[i] = (uint8_t)i;
    for (i = 0; i < sizeof SIP_KAT / sizeof SIP_KAT[0]; i++) {
        proto_siphash24(key, msg, SIP_KAT[i].len, out);
        CHECK(memcmp(out, SIP_KAT[i].out, 8) == 0, "len=%zu", SIP_KAT[i].len);
    }
}

static void test_kdf(void)
{
    proto_key_t sk;
    proto_subkeys_t a, b;
    const uint8_t fid[] = "field-01";
    int i;

    printf("[kdf]\n");
    for (i = 0; i < 16; i++) sk.b[i] = (uint8_t)(0xA0 + i);
    CHECK(proto_kdf_all(&sk, fid, sizeof fid - 1, &a) == 0, "kdf_all");
    CHECK(proto_kdf_all(&sk, fid, sizeof fid - 1, &b) == 0, "kdf_all 2");
    CHECK(memcmp(&a, &b, sizeof a) == 0, "deterministic");
    CHECK(memcmp(&a.k_hop, &a.k_mac, 16) != 0, "hop != mac");
    CHECK(memcmp(&a.k_mac, &a.k_resync, 16) != 0, "mac != resync");
    CHECK(memcmp(a.k_hop.b, a.k_hop.b + 8, 8) != 0, "halves differ");
    CHECK(proto_kdf_all(&sk, fid, PROTO_FIELD_ID_MAX + 1, &b) == -1, "oversize field id");
    CHECK(proto_kdf_all(&sk, (const uint8_t *)"field-02", 8, &b) == 0 &&
              memcmp(&a.k_hop, &b.k_hop, 16) != 0, "field id separates keys");
}

static uint64_t xorshift64(uint64_t *s)
{
    *s ^= *s << 13; *s ^= *s >> 7; *s ^= *s << 17;
    return *s;
}

static void test_prp7_permutation(void)
{
    proto_key_t k;
    uint64_t rng = 0x9E3779B97F4A7C15ULL, slot;
    int t, x;

    printf("[prp7_permutation]\n");
    for (x = 0; x < 16; x++) k.b[x] = (uint8_t)(x * 7 + 1);
    for (t = 0; t < 1000; t++) {
        uint8_t seen[PROTO_HOP_DOMAIN] = {0};
        slot = xorshift64(&rng);
        for (x = 0; x < (int)PROTO_HOP_DOMAIN; x++) {
            uint8_t y = proto_hop_prp7(&k, slot, (uint8_t)x);
            CHECK(y < PROTO_HOP_DOMAIN, "range");
            if (y < PROTO_HOP_DOMAIN) seen[y]++;
        }
        for (x = 0; x < (int)PROTO_HOP_DOMAIN; x++)
            CHECK(seen[x] == 1, "slot=%llu y=%d count=%d", (unsigned long long)slot, x, seen[x]);
        if (g_fail) return;
    }
}

/* For every slot, drone_id 0..N-1 must map to a permutation of 0..N-1.
 * This covers both "bijection" (distinct, < N) and "full permutation" rows. */
static void test_hop_bijection(long slots, uint8_t n)
{
    proto_key_t k;
    uint64_t rng = 0xD1B54A32D192ED03ULL, slot;
    long t, bad = 0;
    int d;

    printf("[hop_bijection] N=%u slots=%ld\n", n, slots);
    for (d = 0; d < 16; d++) k.b[d] = (uint8_t)(0x30 + d);
    for (t = 0; t < slots; t++) {
        uint8_t seen[PROTO_HOP_DOMAIN] = {0};
        slot = (t & 1) ? xorshift64(&rng) : (uint64_t)t; /* mix sequential + random */
        for (d = 0; d < n; d++) {
            uint8_t c = proto_hop_channel(&k, slot, (uint8_t)d, n);
            if (c >= n || seen[c]++) { bad++; break; }
        }
    }
    CHECK(bad == 0, "%ld slots with collision/out-of-range", bad);
}

/* All n/spacing drones: distinct channels, pairwise |delta| >= spacing, all < n. */
static void test_hop_spaced(long slots, uint8_t n, uint8_t spacing)
{
    proto_key_t k;
    uint64_t rng = 0x2545F4914F6CDD1DULL;
    uint8_t m = (uint8_t)(n / spacing), ch[PROTO_HOP_DOMAIN];
    long t, bad = 0, offset_hist[8] = {0};
    int a, b;

    printf("[hop_spaced] N=%u spacing=%u M=%u slots=%ld\n", n, spacing, m, slots);
    for (a = 0; a < 16; a++) k.b[a] = (uint8_t)(0x55 ^ a);
    for (t = 0; t < slots && !bad; t++) {
        uint64_t slot = xorshift64(&rng);
        for (a = 0; a < m; a++) {
            ch[a] = proto_hop_channel_spaced(&k, slot, (uint8_t)a, n, spacing);
            if (ch[a] >= n) bad++;
        }
        offset_hist[ch[0] % spacing]++;
        for (a = 0; a < m && !bad; a++)
            for (b = a + 1; b < m; b++)
                if (abs((int)ch[a] - (int)ch[b]) < spacing) { bad++; break; }
    }
    CHECK(bad == 0, "spacing violated");
    for (a = 0; a < spacing; a++)
        CHECK(offset_hist[a] > slots / spacing * 9 / 10, "offset %d underused", a);
    CHECK(proto_hop_channel_spaced(&k, 0, m, n, spacing) == 0xFF, "drone_id >= N/spacing");
}

/* Circular spacing >= gap for every pair, all channels < n. */
static void test_gap_spacing(long slots, uint8_t n, uint8_t m, uint8_t gap)
{
    proto_key_t k;
    uint8_t ch[PROTO_HOP_GAP_MAX_CH];
    long t, bad = 0;
    int a, b, d;

    printf("[gap_spacing] N=%u M=%u gap=%u slots=%ld\n", n, m, gap, slots);
    for (a = 0; a < 16; a++) k.b[a] = (uint8_t)(0x77 + 3 * a);
    for (t = 0; t < slots && !bad; t++) {
        if (proto_hop_gap_slot(&k, (uint64_t)t * 0x9E3779B97F4A7C15ULL, n, m, gap, ch)) { bad++; break; }
        for (a = 0; a < m && !bad; a++) {
            if (ch[a] >= n) bad++;
            for (b = a + 1; b < m; b++) {
                d = abs((int)ch[a] - (int)ch[b]);
                if (d > n - d) d = n - d;
                if (d < gap) { bad++; break; }
            }
        }
    }
    CHECK(bad == 0, "gap violated");
}

/* N=8, M=2, gap=2: 8 * 5 = 40 valid ordered (ch0, ch1) pairs, each must have
 * probability 1/40 (uniform over valid configurations). */
static void test_gap_uniform_configs(void)
{
    proto_key_t k = {{9, 8, 7, 6, 5, 4, 3, 2, 1}};
    long cnt[8][8] = {{0}}, t, slots = 400000, valid = 0;
    uint8_t ch[2];
    int a, b, d;

    printf("[gap_uniform_configs]\n");
    for (t = 0; t < slots; t++) {
        proto_hop_gap_slot(&k, (uint64_t)t, 8, 2, 2, ch);
        cnt[ch[0]][ch[1]]++;
    }
    for (a = 0; a < 8; a++)
        for (b = 0; b < 8; b++) {
            d = abs(a - b); if (d > 8 - d) d = 8 - d;
            if (d >= 2) {
                valid++;
                CHECK(labs(cnt[a][b] - slots / 40) < slots / 40 / 20, /* within 5%, ~10 sigma */
                      "(%d,%d) count %ld expected %ld", a, b, cnt[a][b], slots / 40);
            } else {
                CHECK(cnt[a][b] == 0, "invalid (%d,%d) seen", a, b);
            }
        }
    CHECK(valid == 40, "valid=%ld", valid);
}

static void test_gap_args_and_cost(void)
{
    proto_key_t k = {{1}};
    proto_opcount_t ops;
    uint8_t ch[PROTO_HOP_GAP_MAX_CH];
    long t, slots = 20000;

    printf("[gap_args_and_cost]\n");
    CHECK(proto_hop_gap_slot(&k, 0, 80, 41, 2, ch) == -1, "M*gap > N");
    CHECK(proto_hop_gap_slot(&k, 0, 80, 40, 2, ch) == 0, "M*gap == N ok");
    CHECK(proto_hop_gap_slot(&k, 0, 80, 0, 2, ch) == -1, "M == 0");
    CHECK(proto_hop_gap_channel(&k, 5, 3, 80, 10, 2) ==
              (proto_hop_gap_slot(&k, 5, 80, 10, 2, ch), ch[3]), "channel == slot[d]");
    proto_opcount_reset();
    for (t = 0; t < slots; t++)
        proto_hop_gap_slot(&k, (uint64_t)t, 80, 10, 2, ch);
    proto_opcount_get(&ops);
    printf("  N=80 M=10 gap=2: %.2f PRF calls per slot (all drones)\n", (double)ops.prf / slots);
    proto_opcount_reset();
    for (t = 0; t < slots; t++)
        proto_hop_channel_r(&k, (uint64_t)t, 3, 80, 8);
    proto_opcount_get(&ops);
    printf("  Feistel 8 rounds: %.2f PRF calls per slot per drone\n", (double)ops.prf / slots);
}

#include "test_packet.inc"

static void test_hop_args(void)
{
    proto_key_t k = {{0}};
    uint8_t buf[4];

    printf("[hop_args]\n");
    CHECK(proto_hop_channel(&k, 0, 80, 80) == 0xFF, "drone_id >= N");
    CHECK(proto_hop_channel(&k, 0, 0, 129) == 0xFF, "N > 128");
    CHECK(proto_hop_channel(&k, 0, 0, 0) == 0xFF, "N == 0");
    CHECK(proto_hop_sequence(&k, 0, 4, 3, 80, buf) == 0, "sequence ok");
    CHECK(buf[2] == proto_hop_channel(&k, 2, 3, 80), "sequence matches channel");
}

static void test_opcount(void)
{
    proto_key_t k = {{0}};
    proto_opcount_t ops;

    printf("[opcount]\n");
    proto_opcount_reset();
    proto_hop_prp7(&k, 1, 5);
    proto_opcount_get(&ops);
    CHECK(ops.prf == PROTO_HOP_ROUNDS, "prp7 uses %d PRF calls, got %llu",
          PROTO_HOP_ROUNDS, (unsigned long long)ops.prf);
}

int main(int argc, char **argv)
{
    long slots = argc > 1 ? atol(argv[1]) : 1000000;

    test_siphash_kat();
    test_kdf();
    test_prp7_permutation();
    test_hop_args();
    test_opcount();
    test_hop_bijection(slots, 80);
    test_hop_bijection(slots / 10, 128);
    test_hop_bijection(slots / 10, 13);
    test_hop_spaced(slots / 10, 80, 2);
    test_hop_spaced(slots / 10, 80, 3);
    test_hop_spaced(slots / 10, 13, 2);
    test_gap_spacing(slots / 10, 80, 10, 2);
    test_gap_spacing(slots / 10, 80, 40, 2);
    test_gap_spacing(slots / 10, 80, 26, 3);
    test_gap_spacing(slots / 10, 13, 6, 2);
    test_gap_spacing(slots / 10, 80, 80, 1);
    test_gap_uniform_configs();
    test_gap_args_and_cost();
    test_packet_roundtrip_and_tamper();
    test_open_window();
    test_resync_fsm();
    test_beacon();

    printf(g_fail ? "FAILED (%d)\n" : "ALL PASSED\n", g_fail);
    return g_fail ? 1 : 0;
}
