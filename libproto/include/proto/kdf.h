/* K_x = PRF(SessionKey, FieldID || label), expanded to 128 bits. */
#ifndef PROTO_KDF_H
#define PROTO_KDF_H

#include "proto/crypto_backend.h"

#define PROTO_FIELD_ID_MAX 32

typedef enum {
    PROTO_LABEL_HOP = 1,
    PROTO_LABEL_MAC = 2,
    PROTO_LABEL_RESYNC = 3,
} proto_label_t;

typedef struct {
    proto_key_t k_hop;
    proto_key_t k_mac;
    proto_key_t k_resync;
} proto_subkeys_t;

/* Returns 0 on success, -1 if field_id_len > PROTO_FIELD_ID_MAX. */
int proto_kdf(const proto_key_t *session_key, const uint8_t *field_id,
              size_t field_id_len, proto_label_t label, proto_key_t *out);

int proto_kdf_all(const proto_key_t *session_key, const uint8_t *field_id,
                  size_t field_id_len, proto_subkeys_t *out);

#endif
