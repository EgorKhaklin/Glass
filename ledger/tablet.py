#!/usr/bin/env python3
# =============================================================================
# The Preserved Tablet — an append-only, tamper-evident ledger of Glass proof
# verdicts, committed into a Poseidon-Merkle root.
#
# Each line of `ledger/LEDGER` records one verdict: `seq <TAB> statement <TAB>
# result <TAB> verdict`. The committed root in `ledger/ROOT` is a Poseidon-Merkle
# tree over the per-line digests, so no past entry can be altered, reordered, or
# dropped without changing the root. Inclusion proofs show a given verdict is in
# the ledger at a committed root. Uses the SAME Plonky2-exact Poseidon the prover
# and the second verifier use (pentecost/poseidon.py) — it binds existing verdicts,
# adds no new trust. Research/educational-grade, UNAUDITED.
#
#   python3 ledger/tablet.py append "<statement>" <result> <verdict>
#   python3 ledger/tablet.py root                       # the current committed root
#   python3 ledger/tablet.py list                       # the entries
#   python3 ledger/tablet.py prove <i>                  # inclusion path for entry i
#   python3 ledger/tablet.py verify <i>                 # entry i is committed in ROOT?
#   python3 ledger/tablet.py --selftest                 # determinism + inclusion + tamper
# =============================================================================
import sys, os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
from pentecost.poseidon import perm, hashg, P  # the validated Plonky2-exact Poseidon

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "LEDGER")
ROOTF = os.path.join(HERE, "ROOT")
ZERO = [0, 0, 0, 0]

def h_bytes(data: bytes):
    """Poseidon sponge (rate 8 / capacity 4) over bytes -> 4-lane digest."""
    data = data + b"\x01"
    while len(data) % 64 != 0:
        data += b"\x00"
    st = [0] * 12
    for off in range(0, len(data), 64):
        for i in range(8):
            st[i] = (st[i] + int.from_bytes(data[off + i * 8: off + i * 8 + 8], "little")) % P
        st = perm(st)
    return st[:4]

def lanes_hex(l):
    return "".join("%016x" % (x % P) for x in l)

def leaf(line: str):
    return h_bytes(line.encode())

def build(leaves):
    """Poseidon-Merkle over the leaves; returns (root, levels) (odd nodes duplicate-last)."""
    if not leaves:
        return (ZERO, [[ZERO]])
    level = leaves[:]
    levels = [level]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(hashg(a, b))
        levels.append(nxt)
        level = nxt
    return (level[0], levels)

def incl_path(levels, idx):
    """Sibling digests from leaf idx up to the root, each tagged with our side."""
    p = []
    for lvl in levels[:-1]:
        sib = idx ^ 1
        s = lvl[sib] if sib < len(lvl) else lvl[idx]   # odd node: sibling is self
        p.append((s, idx & 1))                          # idx&1 == 1 -> we are the RIGHT child
        idx //= 2
    return p

def verify_incl(leaf_dig, path, root):
    cur = leaf_dig
    for sib, is_right in path:
        cur = hashg(sib, cur) if is_right else hashg(cur, sib)
    return lanes_hex(cur) == lanes_hex(root)

def read_lines():
    if not os.path.exists(LEDGER):
        return []
    return [ln for ln in open(LEDGER).read().splitlines() if ln.strip()]

def recommit(lines):
    leaves = [leaf(ln) for ln in lines]
    root, _ = build(leaves)
    open(ROOTF, "w").write(lanes_hex(root) + "\n")
    return lanes_hex(root)

def main():
    a = sys.argv[1:]
    if a and a[0] == "--selftest":
        ok = True
        entries = [f"{i}\tstmt_{i}\t{i*i}\tACCEPT" for i in range(7)]
        leaves = [leaf(e) for e in entries]
        root, levels = build(leaves)
        # determinism
        root2, _ = build([leaf(e) for e in entries])
        d = (lanes_hex(root) == lanes_hex(root2)); ok &= d
        print(f"  {'OK ' if d else 'FAIL'}  determinism (same entries -> same root)")
        # inclusion for every entry
        inc = all(verify_incl(leaves[i], incl_path(levels, i), root) for i in range(len(entries)))
        ok &= inc
        print(f"  {'OK ' if inc else 'FAIL'}  inclusion proofs verify for all {len(entries)} entries")
        # forged leaf at a real position must fail
        forged = verify_incl(leaf("FORGED\t0\t0\tACCEPT"), incl_path(levels, 3), root)
        ok &= (not forged)
        print(f"  {'OK ' if not forged else 'FAIL'}  a forged entry does NOT verify against the root")
        # tamper a past entry -> root changes
        tamp = entries[:]; tamp[2] = "2\tstmt_2\t999\tACCEPT"
        troot, _ = build([leaf(e) for e in tamp])
        changed = (lanes_hex(troot) != lanes_hex(root)); ok &= changed
        print(f"  {'OK ' if changed else 'FAIL'}  tampering a past entry changes the root")
        print("CHECK tablet " + ("T" if ok else "F"))
        sys.exit(0 if ok else 1)

    lines = read_lines()
    if not a or a[0] == "root":
        print(open(ROOTF).read().strip() if os.path.exists(ROOTF) else recommit(lines))
    elif a[0] == "list":
        for ln in lines:
            print(ln)
    elif a[0] == "append":
        stmt, result, verdict = a[1], a[2], a[3]
        seq = len(lines)
        lines.append(f"{seq}\t{stmt}\t{result}\t{verdict}")
        open(LEDGER, "w").write("\n".join(lines) + "\n")
        print(f"appended #{seq}: {stmt}  result={result}  {verdict}")
        print("new root: " + recommit(lines))
    elif a[0] == "prove":
        i = int(a[1]); leaves = [leaf(ln) for ln in lines]; _, levels = build(leaves)
        for sib, right in incl_path(levels, i):
            print(("R " if right else "L ") + lanes_hex(sib))
    elif a[0] == "verify":
        i = int(a[1]); leaves = [leaf(ln) for ln in lines]; root, levels = build(leaves)
        committed = open(ROOTF).read().strip() if os.path.exists(ROOTF) else lanes_hex(root)
        ok = verify_incl(leaves[i], incl_path(levels, i), root) and lanes_hex(root) == committed
        print(f"entry #{i} {'IS' if ok else 'is NOT'} committed in ROOT\n  {lines[i]}")
        sys.exit(0 if ok else 1)
    else:
        print("usage: tablet.py [append|root|list|prove <i>|verify <i>|--selftest]"); sys.exit(2)

if __name__ == "__main__":
    main()
