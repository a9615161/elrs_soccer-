/* Guard-gap hopping via the gap transformation.
 *
 * Per slot, all M drones' channels are drawn jointly so that any two are at least
 * `gap` channels apart (circularly), uniformly over all such configurations:
 *   1. L = N - (gap-1) positions (leaves a wrap-around guard), pool P = N - M*(gap-1)
 *   2. draw M distinct values from [0, P) (partial Fisher-Yates), sort,
 *      c_j = b_j + j*(gap-1)                 -> spacing >= gap within [0, L)
 *   3. random permutation assigns c_j to drones
 *   4. random rotation r in [0, N): ch = (c + r) mod N  -> each drone exactly 1/N per channel
 * Randomness: SipHash(K_hop, slot || 0xFD || ctr16) stream, rejection-sampled.
 * Every drone computes the whole assignment, so M and drone IDs must be fixed
 * at provisioning time (with the session key). gap = 1 is a uniformly random
 * injection (ideal-PRP reference). */
#ifndef PROTO_HOP_GAP_H
#define PROTO_HOP_GAP_H

#include "proto/crypto_backend.h"

#define PROTO_HOP_GAP_MAX_CH 128
#define PROTO_HOP_GAP_DEFAULT 2 /* guard gap used by the Proposed protocol */

/* out[d] = channel of drone d, d < n_drones. Returns 0, or -1 if
 * n_channels > 128, n_drones == 0, gap == 0 or n_drones * gap > n_channels. */
int proto_hop_gap_slot(const proto_key_t *k_hop, uint64_t slot, uint8_t n_channels,
                       uint8_t n_drones, uint8_t gap, uint8_t *out);

/* Channel of one drone; 0xFF on bad arguments. */
uint8_t proto_hop_gap_channel(const proto_key_t *k_hop, uint64_t slot, uint8_t drone_id,
                              uint8_t n_channels, uint8_t n_drones, uint8_t gap);

/* out[t * n_drones + d] for slots slot0 .. slot0+count-1. Returns 0/-1. */
int proto_hop_gap_block(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                        uint8_t n_channels, uint8_t n_drones, uint8_t gap, uint8_t *out);

#endif
