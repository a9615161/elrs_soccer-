import struct

from hypothesis import given, settings, strategies as st

from sim import proto_ffi


def _siphash24_py(key: bytes, msg: bytes) -> bytes:
    """Independent pure-Python SipHash-2-4 for cross-checking the C code."""
    M = (1 << 64) - 1
    rotl = lambda x, b: ((x << b) | (x >> (64 - b))) & M
    k0, k1 = struct.unpack("<QQ", key)
    v = [k0 ^ 0x736F6D6570736575, k1 ^ 0x646F72616E646F6D, k0 ^ 0x6C7967656E657261, k1 ^ 0x7465646279746573]

    def rnd():
        v[0] = (v[0] + v[1]) & M; v[1] = rotl(v[1], 13) ^ v[0]; v[0] = rotl(v[0], 32)
        v[2] = (v[2] + v[3]) & M; v[3] = rotl(v[3], 16) ^ v[2]
        v[0] = (v[0] + v[3]) & M; v[3] = rotl(v[3], 21) ^ v[0]
        v[2] = (v[2] + v[1]) & M; v[1] = rotl(v[1], 17) ^ v[2]; v[2] = rotl(v[2], 32)

    tail = len(msg) % 8
    for i in range(0, len(msg) - tail, 8):
        m = struct.unpack_from("<Q", msg, i)[0]
        v[3] ^= m; rnd(); rnd(); v[0] ^= m
    b = (len(msg) << 56) & M | int.from_bytes(msg[len(msg) - tail:], "little")
    v[3] ^= b; rnd(); rnd(); v[0] ^= b
    v[2] ^= 0xFF
    for _ in range(4):
        rnd()
    return struct.pack("<Q", v[0] ^ v[1] ^ v[2] ^ v[3])


@given(st.binary(min_size=16, max_size=16), st.binary(max_size=100))
def test_siphash_matches_python(key, msg):
    assert proto_ffi.siphash24(key, msg) == _siphash24_py(key, msg)


@settings(max_examples=200)
@given(st.binary(min_size=16, max_size=16), st.binary(min_size=1, max_size=32),
       st.integers(0, 2**64 - 1), st.integers(1, 128))
def test_hop_is_permutation(sk, fid, slot, n):
    p = proto_ffi.Proto(sk, fid)
    chans = [p.hop_channel(slot, d, n) for d in range(n)]
    assert sorted(chans) == list(range(n))


def test_sequence_matches_channel():
    p = proto_ffi.Proto(bytes(range(16)), b"field")
    seq = p.hop_sequence(1000, 50, 7, 80)
    assert seq.tolist() == [p.hop_channel(1000 + i, 7, 80) for i in range(50)]


def test_op_counts():
    p = proto_ffi.Proto(bytes(16), b"f")
    proto_ffi.op_counts_reset()
    p.prp7(0, 0)
    assert proto_ffi.op_counts()["prf"] == 4
