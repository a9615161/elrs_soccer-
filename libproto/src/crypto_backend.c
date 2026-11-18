#include "proto/crypto_backend.h"

static const proto_crypto_backend_t *g_backend = &proto_backend_siphash24;
static proto_opcount_t g_ops;

void proto_set_backend(const proto_crypto_backend_t *be)
{
    g_backend = be ? be : &proto_backend_siphash24;
}

const proto_crypto_backend_t *proto_get_backend(void) { return g_backend; }

void proto_prf(const proto_key_t *key, const uint8_t *msg, size_t len,
               uint8_t out[PROTO_PRF_LEN])
{
    g_ops.prf++;
    g_backend->prf(key, msg, len, out);
}

void proto_mac_prf(const proto_key_t *key, const uint8_t *msg, size_t len,
                   uint8_t out[PROTO_PRF_LEN])
{
    g_ops.mac++;
    g_backend->prf(key, msg, len, out);
}

void proto_opcount_get(proto_opcount_t *out) { *out = g_ops; }

void proto_opcount_reset(void)
{
    g_ops.prf = g_ops.mac = g_ops.block = 0;
}
