/* Receiver resynchronisation state machine: LOCKED -> SUSPECT -> LOST -> LOCKED.
 *
 * The receiver keeps its own slot clock at all times. Per slot the caller asks
 * proto_rs_window() how many candidate nonces to try (1 when LOCKED), runs
 * proto_open_window() on a received packet, and reports the outcome with
 * proto_rs_on_slot(). Any authenticated packet re-locks immediately, from any
 * state; the accepted offset is returned so the caller can correct its clock.
 * LOST corresponds to failsafe.
 *
 * Resync beacon (fallback when the clock uncertainty exceeds the window, e.g. after
 * a reboot): carries the low 32 bits of the sender's slot counter with a 30-bit tag under K_resync,
 * sent on a rendezvous channel derived from K_resync and the epoch. Beacons older
 * than the last accepted one are rejected (monotonic counter = slot). */
#ifndef PROTO_RESYNC_H
#define PROTO_RESYNC_H

#include "proto/packet.h"

typedef enum { PROTO_LOCKED = 0, PROTO_SUSPECT = 1, PROTO_LOST = 2 } proto_rs_state_t;

typedef struct {
    uint32_t suspect_after;  /* consecutive missed slots before SUSPECT */
    uint32_t lost_after;     /* slots without a valid packet before LOST (failsafe) */
    uint32_t w_suspect;      /* candidate nonces tried in SUSPECT */
    uint32_t w_lost;         /* candidate nonces tried in LOST */
} proto_rs_cfg_t;

typedef struct {
    proto_rs_state_t state;
    uint64_t last_accepted;  /* PROTO_NO_SLOT if none */
    uint64_t last_valid_local; /* local slot of the last accepted packet */
    uint32_t miss_run;
    uint64_t last_beacon;    /* PROTO_NO_SLOT if none */
} proto_rs_t;

void proto_rs_init(proto_rs_t *rs, uint64_t now_local);
uint32_t proto_rs_window(const proto_rs_t *rs, const proto_rs_cfg_t *cfg);

/* accepted: 1 if a packet was authenticated this slot, with nonce `accepted_slot`.
 * Returns the new state. */
proto_rs_state_t proto_rs_on_slot(proto_rs_t *rs, const proto_rs_cfg_t *cfg, uint64_t now_local,
                                  int accepted, uint64_t accepted_slot);

/* Beacon (type field = 3). Returns 1 on success. */
void proto_beacon_seal(const proto_key_t *k_resync, uint8_t drone_id, uint64_t slot,
                       uint8_t pkt[PROTO_PKT_LEN]);
int proto_beacon_open(proto_rs_t *rs, const proto_key_t *k_resync, uint8_t drone_id,
                      const uint8_t pkt[PROTO_PKT_LEN], uint64_t *slot);

/* Rendezvous channel for an epoch (epoch = slot >> epoch_bits, chosen by the caller). */
uint8_t proto_rendezvous_channel(const proto_key_t *k_resync, uint64_t epoch, uint8_t n_channels);

#endif
