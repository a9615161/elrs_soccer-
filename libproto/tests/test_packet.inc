/* Included from test_main.c: packet + resync tests (Step 2.2 table). */

static void make_link(proto_link_t *l, uint8_t drone, uint8_t tag_bits)
{
    int i;
    for (i = 0; i < 16; i++) l->k_mac.b[i] = (uint8_t)(0xC0 + i);
    l->drone_id = drone;
    l->dir = 0;
    l->tag_bits = tag_bits;
}

static void fill_pkt(uint8_t p[8], uint64_t seed)
{
    int i;
    for (i = 0; i < 8; i++) p[i] = (uint8_t)(xorshift64(&seed) >> 13);
    p[0] = (uint8_t)((p[0] & ~3u) | 1u); /* type RC */
}

static void test_packet_roundtrip_and_tamper(void)
{
    static const uint8_t tags[] = {8, 12, 14, 16, 24, 32};
    proto_link_t l, other;
    uint8_t p[8], q[8];
    uint64_t seed = 0xABCDEF;
    unsigned ti, n, bit, bad_rt = 0, bad_tamper = 0, chance = 0, chance_trials = 0;

    printf("[packet_roundtrip_and_tamper]\n");
    for (ti = 0; ti < sizeof tags; ti++) {
        make_link(&l, 3, tags[ti]);
        for (n = 0; n < 2000; n++) {
            uint64_t slot = xorshift64(&seed);
            fill_pkt(p, seed);
            proto_seal(&l, slot, p);
            if (!proto_open(&l, slot, p)) bad_rt++;
            /* flip each bit: a modified packet passes only by tag collision (prob 2^-t).
             * t >= 24: expect none; t = 14/16: count and compare with the expectation. */
            for (bit = 0; bit < 64 && tags[ti] >= 14; bit++) {
                memcpy(q, p, 8);
                q[bit >> 3] ^= (uint8_t)(1u << (bit & 7));
                if (tags[ti] >= 24) {
                    if (proto_open(&l, slot, q)) bad_tamper++;
                } else if (tags[ti] == 14) {
                    chance_trials++;
                    chance += (unsigned)proto_open(&l, slot, q);
                }
            }
            if (tags[ti] >= 24) {
                if (proto_open(&l, slot + 1, p)) bad_tamper++;          /* wrong slot */
                other = l; other.k_mac.b[0] ^= 1;
                if (proto_open(&other, slot, p)) bad_tamper++;          /* wrong key */
                other = l; other.drone_id ^= 1;
                if (proto_open(&other, slot, p)) bad_tamper++;          /* other drone */
                other = l; other.dir ^= 1;
                if (proto_open(&other, slot, p)) bad_tamper++;          /* reflection */
            }
        }
    }
    CHECK(bad_rt == 0, "roundtrip failures %u", bad_rt);
    CHECK(bad_tamper == 0, "tampered packets accepted %u", bad_tamper);
    /* 128000 trials * 2^-14 = 7.8 expected; Poisson 99.9% range ~ [1, 18] */
    printf("  t=14 bit-flip forgeries: %u / %u (expected %.1f)\n", chance, chance_trials,
           chance_trials / 16384.0);
    CHECK(chance >= 1 && chance <= 18, "t=14 chance forgeries %u outside [1,18]", chance);
    CHECK(proto_payload_bits(14) == 48 && proto_payload_bits(24) == 38 && proto_payload_bits(32) == 30,
          "payload bits");
}

static void test_open_window(void)
{
    proto_link_t l;
    uint8_t p[8];
    int64_t off = 99;
    uint32_t tries = 0;
    int d;

    printf("[open_window]\n");
    make_link(&l, 1, 32);
    for (d = -5; d <= 5; d++) {
        fill_pkt(p, (uint64_t)(d + 100));
        proto_seal(&l, (uint64_t)(1000 + d), p);
        CHECK(proto_open_window(&l, 1000, 11, PROTO_NO_SLOT, p, &off, &tries) == 1 && off == d,
              "d=%d inside window -> off=%lld", d, (long long)off);
        /* order 0,+1,-1,+2,-2,...: +d needs 2d candidates, -d needs 2d+1 */
        if (d != 0)
            CHECK(proto_open_window(&l, 1000, (uint32_t)(d > 0 ? 2 * d - 1 : -2 * d), PROTO_NO_SLOT,
                                    p, &off, &tries) == 0,
                  "d=%d outside window must reject", d);
    }
    /* replay: last_accepted >= slot -> skipped */
    fill_pkt(p, 7);
    proto_seal(&l, 1000, p);
    CHECK(proto_open_window(&l, 1000, 9, 1000, p, &off, &tries) == 0, "replayed slot accepted");
    CHECK(proto_open_window(&l, 1003, 9, 999, p, &off, &tries) == 1 && off == -3, "fresh slot rejected");
}

static void test_resync_fsm(void)
{
    proto_rs_cfg_t cfg = {2, 10, 8, 32};
    proto_rs_t rs;
    uint64_t t = 0;

    printf("[resync_fsm]\n");
    proto_rs_init(&rs, 0);
    CHECK(proto_rs_window(&rs, &cfg) == 1, "LOCKED window 1");
    CHECK(proto_rs_on_slot(&rs, &cfg, ++t, 1, 1) == PROTO_LOCKED, "stay locked");
    CHECK(proto_rs_on_slot(&rs, &cfg, ++t, 0, 0) == PROTO_LOCKED, "1 miss locked");
    CHECK(proto_rs_on_slot(&rs, &cfg, ++t, 0, 0) == PROTO_SUSPECT, "2 misses suspect");
    CHECK(proto_rs_window(&rs, &cfg) == 8, "SUSPECT window");
    while (t < 10) proto_rs_on_slot(&rs, &cfg, ++t, 0, 0);
    CHECK(rs.state == PROTO_SUSPECT, "t=10 still suspect (9 slots since valid)");
    CHECK(proto_rs_on_slot(&rs, &cfg, ++t, 0, 0) == PROTO_LOST, "10 slots without valid -> LOST");
    CHECK(proto_rs_window(&rs, &cfg) == 32, "LOST window");
    CHECK(proto_rs_on_slot(&rs, &cfg, ++t, 1, 12) == PROTO_LOCKED, "relock from LOST");
    CHECK(rs.last_accepted == 12, "last_accepted");
}

static void test_beacon(void)
{
    proto_key_t kr;
    proto_rs_t rs;
    uint8_t b1[8], b2[8];
    uint64_t s = 0;
    int i, hist[80] = {0}, ok = 1;

    printf("[beacon]\n");
    for (i = 0; i < 16; i++) kr.b[i] = (uint8_t)(0x11 * i);
    proto_rs_init(&rs, 0);
    proto_beacon_seal(&kr, 4, 5000, b1);
    proto_beacon_seal(&kr, 4, 6000, b2);
    CHECK(proto_beacon_open(&rs, &kr, 4, b1, &s) == 1 && s == 5000, "beacon accept");
    CHECK(proto_beacon_open(&rs, &kr, 4, b1, &s) == 0, "beacon replay rejected");
    CHECK(proto_beacon_open(&rs, &kr, 5, b2, &s) == 0, "beacon for other drone rejected");
    CHECK(proto_beacon_open(&rs, &kr, 4, b2, &s) == 1 && s == 6000, "newer beacon accepted");
    b2[3] ^= 0x10;
    CHECK(proto_beacon_open(&rs, &kr, 4, b2, &s) == 0, "tampered beacon rejected");
    for (i = 0; i < 80000; i++) hist[proto_rendezvous_channel(&kr, (uint64_t)i, 80)]++;
    for (i = 0; i < 80; i++) if (hist[i] < 850 || hist[i] > 1150) ok = 0;
    CHECK(ok, "rendezvous channel roughly uniform");
}
