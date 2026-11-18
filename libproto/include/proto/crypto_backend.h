/* Pluggable crypto backend + operation counters.
 * Pure C99, no malloc, no clock. */
#ifndef PROTO_CRYPTO_BACKEND_H
#define PROTO_CRYPTO_BACKEND_H

#include <stddef.h>
#include <stdint.h>

#define PROTO_KEY_LEN 16
#define PROTO_PRF_LEN 8

typedef struct {
    uint8_t b[PROTO_KEY_LEN];
} proto_key_t;

/* Per-primitive call counters, read by the simulator's cost model (E10). */
typedef struct {
    uint64_t prf;
    uint64_t mac;
    uint64_t block;
} proto_opcount_t;

typedef struct {
    const char *name;
    /* 64-bit PRF: out = F(key, msg). */
    void (*prf)(const proto_key_t *key, const uint8_t *msg, size_t len,
                uint8_t out[PROTO_PRF_LEN]);
} proto_crypto_backend_t;

extern const proto_crypto_backend_t proto_backend_siphash24;

/* Raw SipHash-2-4 (no op counting), exposed for KAT. */
void proto_siphash24(const uint8_t key[16], const uint8_t *msg, size_t len,
                     uint8_t out[8]);

/* Active backend (default: SipHash-2-4). Calls through here are counted. */
void proto_set_backend(const proto_crypto_backend_t *be);
const proto_crypto_backend_t *proto_get_backend(void);
void proto_prf(const proto_key_t *key, const uint8_t *msg, size_t len,
               uint8_t out[PROTO_PRF_LEN]);

/* Same PRF, counted as a MAC computation (tag generation / verification). */
void proto_mac_prf(const proto_key_t *key, const uint8_t *msg, size_t len,
                   uint8_t out[PROTO_PRF_LEN]);

void proto_opcount_get(proto_opcount_t *out);
void proto_opcount_reset(void);

#endif
