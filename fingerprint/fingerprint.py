#!/usr/bin/env python3
# =============================================================================
# The fingerprint: Glass's content-addressed canonical identity.
#
# One Poseidon-Merkle root over the artifacts that ARE Glass: the self-hosting
# core (glassc.glass, prism.glass, glass.py, quartz.py), the prover+verifier
# bridge, the second independent verifier (lens/), the test suite, and the
# language semantics (LANG.md). Recompute it and match `fingerprint/FINGERPRINT` and you have
# attested, byte-for-byte, that this is the same Glass: the bootstrap fixpoint
# turned into a single publicly-checkable fingerprint.
#
# Uses the SAME Poseidon-over-Goldilocks the prover and the second verifier use
# (lens/poseidon.py, byte-exact to Plonky3 Poseidon2). No new trust: it binds what is
# already there. Research/educational-grade, UNAUDITED.
#
#   python3 fingerprint/fingerprint.py            # print the fingerprint (and per-file leaf digests)
#   python3 fingerprint/fingerprint.py --check    # recompute and compare to fingerprint/FINGERPRINT (exit 0/1)
#   python3 fingerprint/fingerprint.py --write     # (re)write fingerprint/FINGERPRINT to the current root
# =============================================================================
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lens.poseidon import perm, hashg, P  # the validated Plonky3-exact Poseidon2

# The canonical artifact set: "this is Glass". Order is fixed (it is bound into
# the Merkle tree); paths are bound too, so a rename changes the fingerprint.
CANON = [
    "examples/selfhost/glassc.glass",            # the self-hosted compiler
    "examples/selfhost/prism.glass",             # the self-hosted parser
    "glass.py",                                  # the reference interpreter (the spec)
    "quartz.py",                                 # the bootstrap compiler
    "examples/prove/prove_source_goldilocks_zk.glass",  # the prover + verify_b3 bridge
    "examples/prove/prove_job.glass",            # the driver glass prove runs it with
    "lens/verify.py",             # the second, independent verifier
    "lens/poseidon.py",
    "lens/_gold_constants.py",
    "tests/test_glass.py",                       # the test suite
    "LANG.md",                                   # the language semantics
]

def hash_bytes(data: bytes):
    """Poseidon sponge over arbitrary bytes -> a 4-lane (256-bit) Goldilocks digest.
    Rate 8 / capacity 4 over t=12; 10*1-style pad; absorb 8 little-endian u64 lanes
    per permutation, squeeze the first 4 lanes. Deterministic and reproducible."""
    data = data + b"\x01"
    while len(data) % 64 != 0:
        data += b"\x00"
    st = [0] * 12
    for off in range(0, len(data), 64):
        for i in range(8):
            st[i] = (st[i] + int.from_bytes(data[off + i * 8: off + i * 8 + 8], "little")) % P
        st = perm(st)
    return st[:4]

def leaf_digest(rel: str):
    """Bind the path AND the content, so neither a rename nor an edit goes unseen."""
    content = open(os.path.join(ROOT, rel), "rb").read()
    return hash_bytes(rel.encode() + b"\x00" + content)

def merkle(leaves):
    if len(leaves) == 1:
        return leaves[0]
    nxt = []
    for i in range(0, len(leaves), 2):
        a = leaves[i]
        b = leaves[i + 1] if i + 1 < len(leaves) else leaves[i]
        nxt.append(hashg(a, b))   # Poseidon 2-to-1
    return merkle(nxt)

def lanes_to_hex(lanes):
    """4 Goldilocks lanes -> a 256-bit hex string (16 hex chars per 64-bit lane)."""
    return "".join("%016x" % (l % P) for l in lanes)

def compute_fingerprint():
    leaves = [leaf_digest(p) for p in CANON]
    return lanes_to_hex(merkle(leaves)), leaves

def main():
    fp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FINGERPRINT")
    root, leaves = compute_fingerprint()
    if "--check" in sys.argv:
        if not os.path.exists(fp_file):
            print("fingerprint: no fingerprint/FINGERPRINT on record: run with --write first", file=sys.stderr)
            sys.exit(2)
        want = open(fp_file).read().strip()
        if root == want:
            print("fingerprint: OK\n  " + root)
            sys.exit(0)
        print("fingerprint: MISMATCH (a canonical artifact changed)\n  recomputed: %s\n  on record:  %s" % (root, want), file=sys.stderr)
        sys.exit(1)
    if "--write" in sys.argv:
        open(fp_file, "w").write(root + "\n")
        print("fingerprint: wrote fingerprint/FINGERPRINT\n  " + root)
        sys.exit(0)
    # default: print the fingerprint + per-artifact leaf digests
    print("The Glass fingerprint (Poseidon-Merkle over the canonical artifacts):")
    print("  " + root)
    print("\nLeaves:")
    for p, lf in zip(CANON, leaves):
        print("  %s  %s" % (lanes_to_hex(lf)[:16] + "…", p))

if __name__ == "__main__":
    main()
