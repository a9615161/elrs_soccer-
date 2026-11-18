/* Host micro-benchmark of one MAC (SipHash-2-4 over the 18-byte MAC input) - a reference
 * point only; ESP32 numbers must come from the hardware phase. */
#include <stdio.h>
#include <time.h>
#include "proto/packet.h"
int main(void) {
    proto_link_t l = {{{1, 2, 3}}, 1, 0, 14};
    uint8_t p[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    struct timespec a, b;
    volatile uint32_t sink = 0;
    long i, n = 5000000;
    clock_gettime(CLOCK_MONOTONIC, &a);
    for (i = 0; i < n; i++) sink += proto_tag_compute(&l, (uint64_t)i, p);
    clock_gettime(CLOCK_MONOTONIC, &b);
    printf("host MAC: %.1f ns per call\n", ((b.tv_sec - a.tv_sec) * 1e9 + (b.tv_nsec - a.tv_nsec)) / n);
    return (int)(sink & 0);
}
