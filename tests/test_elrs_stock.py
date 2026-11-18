import json
from pathlib import Path

import numpy as np

from sim.baselines import elrs_stock

GOLDEN = json.loads((Path(__file__).parent / "data" / "elrs_fhss_golden.json").read_text())


def test_matches_elrs_cpp():
    for v in GOLDEN["vectors"]:
        seq = elrs_stock.build_sequence(v["seed"], GOLDEN["freq_count"], GOLDEN["sync_channel"])
        assert seq.tolist() == v["seq"], f"seed={v['seed']}"


def test_each_block_is_permutation_with_sync_first():
    seq = elrs_stock.build_sequence(0x01020304)
    for b in range(3):
        block = seq[80 * b: 80 * (b + 1)]
        assert block[0] == 40
        assert sorted(block.tolist()) == list(range(80))


def test_uid_seed():
    uid = bytes([0, 0, 0x12, 0x34, 0x56, 0x78])
    assert elrs_stock.uid_seed(uid) == 0x1234567C  # 0x78 ^ OTA_VERSION_ID(4)


def test_ota_crc_roundtrip_and_nonce():
    from sim.baselines import elrs_ota as O
    init = O.crc_init(0x12, 0x34)
    p = O.seal(bytes([1, 9, 8, 7, 6, 5, 4, 0]), init, nonce=17)
    assert O.valid(p, init, 17)
    assert not O.valid(p, init, 18)
    assert O.valid(p, init, 17 + 256)  # nonce is 8-bit: wraps every 256 slots
    s = O.seal(bytes([2, 1, 2, 3, 4, 5, 6, 0]), init, nonce=99)  # SYNC: nonce not bound
    assert O.valid(s, init, 0) and O.valid(s, init, 200)
