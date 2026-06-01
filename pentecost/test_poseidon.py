#!/usr/bin/env python3
"""Keystone gate: the independent Python Poseidon2 must match Plonky3's published
permutation vector byte-exact — the SAME vector Glass's native poseidon2_perm is
validated against (examples/prove/poseidon2_difftest.glass). If this passes, the
second verifier's cryptographic core is faithful to the first's — and to a third
party, Plonky3. The full 12-lane output is checked (not lane 0 alone: a single
wrong tail constant can leave lane 0 coincidentally correct while corrupting the
transcript). Run: python3 -m pentecost.test_poseidon"""
from .poseidon import perm, hashg

# Plonky3 goldilocks/src/poseidon2.rs, permute([0..11]) — t=12 instance A.
OUT12 = [17479221565885336323, 734915442301621324, 377283858163603678, 216052820910632955, 6347663762129472178, 12730007117582221560, 16792819048661925028, 17643437800019671490, 2573527637616151148, 15146684802819669848, 5692450944251311406, 769909420564152678]

def main():
    out = perm(list(range(12)))
    assert out == OUT12, f"FAIL perm([0..11]) != Plonky3 out12\n  got  {out[:2]}\n  want {OUT12[:2]}"
    # determinism + shape of the 2-to-1 sponge
    h = hashg([1, 2, 3, 4], [5, 6, 7, 8])
    assert len(h) == 4 and hashg([1, 2, 3, 4], [5, 6, 7, 8]) == h
    print("KEYSTONE OK — independent Poseidon2 byte-exact to the full Plonky3 t=12 vector "
          f"(perm([0..11])[0] = {out[0]:#x})")

if __name__ == "__main__":
    main()
