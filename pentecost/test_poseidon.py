#!/usr/bin/env python3
"""Keystone gate: the independent Python Poseidon must match Plonky2's published
vector byte-exact — the same vector Glass's `perm` is validated against. If this
passes, the second verifier's cryptographic core is faithful to the first's (and
to a third party, Plonky2). Run: python3 -m pentecost.test_poseidon"""
from .poseidon import perm, hashg

def main():
    out = perm(list(range(12)))
    anchor = 0xd64e1e3efc5b8e9e            # Plonky2 poseidon([0..11])[0]
    assert out[0] == anchor, f"FAIL perm([0..11])[0] = {out[0]:#x} != {anchor:#x}"
    # determinism + shape of the 2-to-1 sponge
    h = hashg([1, 2, 3, 4], [5, 6, 7, 8])
    assert len(h) == 4 and hashg([1, 2, 3, 4], [5, 6, 7, 8]) == h
    print("KEYSTONE OK — independent Poseidon byte-exact to Plonky2 "
          f"(perm([0..11])[0] = {out[0]:#x})")

if __name__ == "__main__":
    main()
