/* Orthogonal hopping via a small-domain PRP.
 *
 * For each slot, P_slot is a keyed permutation of the 7-bit domain [0,128)
 * built from a 4-round unbalanced Feistel network (3/4-bit halves) whose
 * round function is PRF(K_hop, slot || round || half) truncated. Cycle-walking
 * restricts it to a permutation of [0,N). Drone d hops on P_slot(d), so drones
 * with distinct IDs never share a channel in the same slot. */
#ifndef PROTO_HOP_H
#define PROTO_HOP_H

#include "proto/crypto_backend.h"

#define PROTO_HOP_DOMAIN_BITS 7
#define PROTO_HOP_DOMAIN (1u << PROTO_HOP_DOMAIN_BITS)
#ifndef PROTO_HOP_ROUNDS
#define PROTO_HOP_ROUNDS 4
#endif

/* Raw 7-bit PRP (no cycle-walking). x < 128. */
uint8_t proto_hop_prp7(const proto_key_t *k_hop, uint64_t slot, uint8_t x);

/* Same with an explicit Feistel round count (1..0xEF; round bytes >= 0xF0 are
 * reserved for domain separation), for comparing round counts at run time. */
uint8_t proto_hop_prp7_r(const proto_key_t *k_hop, uint64_t slot, uint8_t x, uint8_t rounds);
uint8_t proto_hop_channel_r(const proto_key_t *k_hop, uint64_t slot,
                            uint8_t drone_id, uint8_t n_channels, uint8_t rounds);
int proto_hop_sequence_r(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                         uint8_t drone_id, uint8_t n_channels, uint8_t rounds, uint8_t *out);

/* Channel in [0, n_channels) for drone_id at slot.
 * Requires drone_id < n_channels <= 128; returns 0xFF on bad arguments. */
uint8_t proto_hop_channel(const proto_key_t *k_hop, uint64_t slot,
                          uint8_t drone_id, uint8_t n_channels);

/* Fill out[i] = proto_hop_channel(k_hop, slot0 + i, drone_id, n). Returns 0/-1. */
int proto_hop_sequence(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                       uint8_t drone_id, uint8_t n_channels, uint8_t *out);

/* Guard-spaced hopping: ch = spacing * P'_slot(drone_id) + b_slot, where P' is the
 * PRP restricted to [0, n_channels / spacing) and b_slot in [0, spacing) is a keyed
 * per-slot offset shared by all drones. Any two drones in the same slot are then
 * >= spacing channels apart. Requires drone_id < n_channels / spacing; spacing 1
 * equals proto_hop_channel. Returns 0xFF on bad arguments. */
uint8_t proto_hop_channel_spaced(const proto_key_t *k_hop, uint64_t slot,
                                 uint8_t drone_id, uint8_t n_channels, uint8_t spacing);

int proto_hop_sequence_spaced(const proto_key_t *k_hop, uint64_t slot0, size_t count,
                              uint8_t drone_id, uint8_t n_channels, uint8_t spacing,
                              uint8_t *out);

#endif
