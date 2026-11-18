#include "proto/kdf.h"

#include <string.h>

/* msg = FieldID || label || block, block in {0,1} selects which 64-bit half. */
int proto_kdf(const proto_key_t *session_key, const uint8_t *field_id,
              size_t field_id_len, proto_label_t label, proto_key_t *out)
{
    uint8_t msg[PROTO_FIELD_ID_MAX + 2];
    uint8_t blk;

    if (field_id_len > PROTO_FIELD_ID_MAX)
        return -1;
    memcpy(msg, field_id, field_id_len);
    msg[field_id_len] = (uint8_t)label;
    for (blk = 0; blk < 2; blk++) {
        msg[field_id_len + 1] = blk;
        proto_prf(session_key, msg, field_id_len + 2, out->b + 8 * blk);
    }
    return 0;
}

int proto_kdf_all(const proto_key_t *session_key, const uint8_t *field_id,
                  size_t field_id_len, proto_subkeys_t *out)
{
    if (proto_kdf(session_key, field_id, field_id_len, PROTO_LABEL_HOP, &out->k_hop) ||
        proto_kdf(session_key, field_id, field_id_len, PROTO_LABEL_MAC, &out->k_mac) ||
        proto_kdf(session_key, field_id, field_id_len, PROTO_LABEL_RESYNC, &out->k_resync))
        return -1;
    return 0;
}
