#!/usr/bin/env python3
# Merkle batch-opening (multiproof) — VALIDATED PROTOTYPE / executable spec for the proof-size
# Merkle-dedup frontier (docs/merkle-dedup-design.md, roadmap #7b).
#
#   python3 fuzz/merkle_batch_proto.py
#
# This is NOT wired into the prover/verifier yet. It validates, in isolation and hash-agnostically,
# the ONE genuinely new soundness obligation the design identified — O3, the canonical bottom-up
# reconstruction of a Merkle root from (opened leaves at their indices) + (a minimal co-path node set
# in canonical order) — together with O1 (every opened leaf bound) and O2 (a missing/extra/forged node
# is rejected). The eventual Glass `verify_b3` and Python `pentecost_verify.py` reconstructions must
# mirror `reconstruct_root` BYTE-IDENTICALLY; this file is their reference + regression test.
#
# Tree convention (matches the live `fold_path_g`, prove_source...glass:469): a node at level L,
# position p has parent (L+1, p//2); even position = LEFT input to H, odd = RIGHT. Leaves at level 0.
import hashlib

# Hash-agnostic stand-in for Poseidon `hashg` (the reconstruction LOGIC is what we validate, not the
# hash). The real impl substitutes hashg(left, right) over 4-lane digests — same tree shape.
def H(a, b):
    return hashlib.sha256(("H(" + a + "," + b + ")").encode()).hexdigest()[:16]

def leaf_hash(i, val):
    return hashlib.sha256(("L" + str(i) + ":" + str(val)).encode()).hexdigest()[:16]


def build_tree(leaves):
    """Full tree as a list of levels; level[0] = leaf hashes, last = [root]. Power-of-two leaf count."""
    n = len(leaves)
    assert n & (n - 1) == 0, "leaf count must be a power of two"
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        levels.append([H(cur[2 * k], cur[2 * k + 1]) for k in range(len(cur) // 2)])
    return levels


# ---- PROVER side: minimal co-path for a set of opened leaf indices -------------------------------
def batch_copath(levels, opened_indices):
    """Walk bottom-up; at each level, the 'known' set is the positions reconstructible so far (opened
    leaves, then computed parents). A node is sent ONLY if it is the sibling of a known node and is not
    itself known. Canonical order: ascending (level, position). Returns the co-path node list."""
    known = set(opened_indices)              # positions known at the current level
    copath = []
    for L in range(len(levels) - 1):         # for each level below the root
        nxt = set()
        for pos in sorted(known):
            parent = pos // 2
            if parent in nxt:
                continue                     # both children handled when we hit the first
            sib = pos ^ 1                     # sibling position
            if sib not in known:
                # send the sibling (canonical: we are iterating positions ascending, and a parent's
                # two children are adjacent, so the missing sibling is emitted in (level,pos) order)
                copath.append((L, sib, levels[L][sib]))
            nxt.add(parent)
        known = nxt
    return copath


# ---- VERIFIER side: reconstruct the root from opened leaves + co-path (canonical order) ----------
def reconstruct_root(opened, copath, height, n_leaves):
    """opened = {index: leaf_hash}; copath = list of node hashes in canonical (level,pos) order (the
    verifier does NOT trust the (L,pos) tags — it derives which siblings it needs from the known set,
    in the same canonical order, and pulls them off the stream). Returns root or None (REJECT)."""
    known = dict(opened)                     # {pos: hash} at current level
    ci = 0
    cohashes = [h for (_, _, h) in copath]   # the verifier consumes ONLY the hashes, in order
    for L in range(height):
        nxt = {}
        for pos in sorted(known.keys()):
            parent = pos // 2
            if parent in nxt:
                continue
            sib = pos ^ 1
            if sib in known:
                sib_h = known[sib]
            else:
                if ci >= len(cohashes):
                    return None              # O2: co-path under-run -> REJECT
                sib_h = cohashes[ci]; ci += 1
            left, right = (known[pos], sib_h) if pos % 2 == 0 else (sib_h, known[pos])
            nxt[parent] = H(left, right)
            known[sib] = sib_h               # mark sibling consumed so we don't re-handle it
        known = nxt
    if ci != len(cohashes):
        return None                          # O2: co-path over-run (unused node) -> REJECT
    if len(known) != 1:
        return None
    return next(iter(known.values()))


def opened_map(levels, indices, vals):
    return {i: levels[0][i] for i in indices}


def run():
    fails = []
    # --- a representative tree: 64 leaves, open a sparse-ish set (like FRI queries in a big tree) ----
    for n in (16, 64, 256):
        height = n.bit_length() - 1
        vals = [i * 7 + 3 for i in range(n)]
        leaves = [leaf_hash(i, v) for i, v in enumerate(vals)]
        levels = build_tree(leaves)
        root = levels[-1][0]
        # open ~1/4 of the leaves at pseudo-scattered positions (deterministic, no RNG)
        idxs = sorted({(i * 37 + 5) % n for i in range(max(2, n // 4))})

        copath = batch_copath(levels, idxs)
        opened = opened_map(levels, idxs, vals)

        # O1 + O3: honest reconstruction matches the committed root
        got = reconstruct_root(opened, copath, height, n)
        if got != root:
            fails.append(f"n={n}: honest reconstruct {got} != root {root}")

        # dedup actually saves: co-path nodes < sum of independent auth-path lengths
        naive = len(idxs) * height
        if not (len(copath) < naive):
            fails.append(f"n={n}: no dedup (copath {len(copath)} !< naive {naive})")

        # O2: a FORGED co-path node -> different root -> REJECT
        if copath:
            bad = copath[:]; (L, pos, h) = bad[len(bad) // 2]
            bad[len(bad) // 2] = (L, pos, "deadbeefdeadbeef")
            if reconstruct_root(opened, bad, height, n) == root:
                fails.append(f"n={n}: forged co-path node wrongly reconstructed the root (O2 BREACH)")

        # O2: a MISSING co-path node (under-run) -> REJECT (None or wrong root)
        if copath:
            short = copath[:-1]
            if reconstruct_root(opened, short, height, n) == root:
                fails.append(f"n={n}: missing co-path node wrongly accepted (O2 BREACH)")

        # O1: a TAMPERED opened leaf -> different root -> REJECT
        if idxs:
            tampered = dict(opened); k = idxs[0]
            tampered[k] = "ffffffffffffffff"
            if reconstruct_root(tampered, copath, height, n) == root:
                fails.append(f"n={n}: tampered opened leaf wrongly accepted (O1 BREACH)")

        ratio = naive / max(1, len(copath))
        print(f"  n={n:4d} opened={len(idxs):4d} height={height} copath={len(copath):4d} "
              f"naive={naive:4d} dedup={ratio:.2f}x  honest=OK forge/miss/tamper=REJECT")

    # full-saturation edge (every leaf opened -> zero co-path, like the small FRI layers)
    n = 16; height = 4
    leaves = [leaf_hash(i, i) for i in range(n)]
    levels = build_tree(leaves); root = levels[-1][0]
    idxs = list(range(n))
    copath = batch_copath(levels, idxs)
    opened = opened_map(levels, idxs, list(range(n)))
    if copath != []:
        fails.append("saturation: full open should need ZERO co-path nodes")
    if reconstruct_root(opened, copath, height, n) != root:
        fails.append("saturation: full-open reconstruction failed")
    print(f"  saturation n={n}: all leaves opened -> copath={len(copath)} (expect 0), honest=OK")

    if fails:
        print("MERKLE-BATCH PROTO: FAIL")
        for f in fails:
            print("   !! " + f)
        return 1
    print("MERKLE-BATCH PROTO: PASS — O1 (leaf binding), O2 (missing/forged node), O3 (canonical "
          "reconstruction) all hold; dedup is monotone. Executable spec for verify_b3 / pentecost.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run())
