#!/usr/bin/env python3
# =============================================================================
# Opening the Seals — selective disclosure over a blinded Poseidon commitment.
#
# Seal a record of named fields; each field is committed as a BLINDED leaf
# leaf_i = Poseidon(field || value || nonce_i) with a per-field nonce derived
# from a secret seed. The commitment is a Poseidon-Merkle root over the leaves.
# Later, REVEAL any subset of fields: a "presentation" carries (field, value,
# nonce, inclusion-path) for each revealed field. A verifier confirms every
# revealed field is bound to the root — the unrevealed fields stay hidden (their
# blinded leaves disclose nothing, resting on Poseidon's preimage/hiding).
#
# This is the "prove you're over 21 without revealing your birthdate" primitive,
# generalized: open one field of a committed record, prove nothing else moved.
# Uses the SAME Plonky2-exact Poseidon the prover + the second verifier use
# (pentecost/poseidon.py). Research/educational-grade, UNAUDITED — the hiding
# rests on Poseidon, which is NOT audited. Do not protect real value.
#
#   python3 seal/reveal.py commit name=Alice dob=1990 country=US id=42 --seed s3cr3t
#   python3 seal/reveal.py reveal /tmp/sealed.json country     # disclose only `country`
#   python3 seal/reveal.py verify /tmp/presentation.json       # bind revealed -> root
#   python3 seal/reveal.py --selftest
# =============================================================================
import sys, os, json

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
from pentecost.poseidon import perm, hashg, P  # the validated Plonky2-exact Poseidon

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

def nonce_for(seed: str, field: str):
    """Per-field blinding nonce — unpredictable without the seed (the hiding lever)."""
    return lanes_hex(h_bytes(("nonce\x00" + seed + "\x00" + field).encode()))

def leaf(field: str, value: str, nonce: str):
    return h_bytes(("leaf\x00" + field + "\x00" + value + "\x00" + nonce).encode())

def build(leaves):
    """Poseidon-Merkle over leaves (odd nodes duplicate-last); returns (root, levels)."""
    level = leaves[:]
    levels = [level]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(hashg(a, b))
        levels.append(nxt); level = nxt
    return (level[0], levels)

def incl_path(levels, idx):
    p = []
    for lvl in levels[:-1]:
        sib = idx ^ 1
        s = lvl[sib] if sib < len(lvl) else lvl[idx]
        p.append([lanes_hex(s), idx & 1])
        idx //= 2
    return p

def verify_path(leaf_dig, path, root_hex):
    cur = leaf_dig
    for sib_hex, is_right in path:
        sib = [int(sib_hex[i:i+16], 16) for i in range(0, 64, 16)]
        cur = hashg(sib, cur) if is_right else hashg(cur, sib)
    return lanes_hex(cur) == root_hex

def seal(record: dict, seed: str):
    """record: {field: value}. Returns the sealed object (fields sorted, blinded)."""
    fields = sorted(record.keys())
    nonces = {f: nonce_for(seed, f) for f in fields}
    leaves = [leaf(f, str(record[f]), nonces[f]) for f in fields]
    root, _ = build(leaves)
    return {"root": lanes_hex(root),
            "fields": fields,
            "values": {f: str(record[f]) for f in fields},
            "nonces": nonces}

def present(sealed: dict, disclose: list):
    """Build a presentation that reveals only `disclose`; binds them to the root."""
    fields = sealed["fields"]
    leaves = [leaf(f, sealed["values"][f], sealed["nonces"][f]) for f in fields]
    _, levels = build(leaves)
    items = []
    for f in disclose:
        i = fields.index(f)
        items.append({"field": f, "value": sealed["values"][f],
                      "nonce": sealed["nonces"][f], "path": incl_path(levels, i)})
    return {"root": sealed["root"], "revealed": items}

def verify_presentation(pres: dict):
    for it in pres["revealed"]:
        lf = leaf(it["field"], it["value"], it["nonce"])
        if not verify_path(lf, it["path"], pres["root"]):
            return False
    return True

def _selftest():
    ok = True
    rec = {"name": "Alice", "dob": "1990", "country": "US", "id": "42"}
    s = seal(rec, "s3cr3t")
    # 1. reveal a subset -> verifies, and carries ONLY the disclosed fields
    pres = present(s, ["country"])
    v1 = verify_presentation(pres) and [x["field"] for x in pres["revealed"]] == ["country"]
    ok &= v1; print(f"  {'OK ' if v1 else 'FAIL'}  reveal one field -> verifies, discloses only that field")
    # 2. tampering the revealed value breaks the binding
    bad = json.loads(json.dumps(pres)); bad["revealed"][0]["value"] = "CA"
    v2 = not verify_presentation(bad)
    ok &= v2; print(f"  {'OK ' if v2 else 'FAIL'}  a tampered revealed value does NOT verify")
    # 3. tampering the path breaks it
    bad2 = json.loads(json.dumps(pres)); bad2["revealed"][0]["path"][0][0] = "0" * 64
    v3 = not verify_presentation(bad2)
    ok &= v3; print(f"  {'OK ' if v3 else 'FAIL'}  a tampered inclusion path does NOT verify")
    # 4. binding/hiding: changing a HIDDEN field (dob) changes the root (so the root commits all)
    s2 = seal({**rec, "dob": "1980"}, "s3cr3t")
    v4 = (s2["root"] != s["root"])
    ok &= v4; print(f"  {'OK ' if v4 else 'FAIL'}  changing a hidden field changes the commitment root")
    # 5. the nonce is unpredictable without the seed (different seed -> different blinding -> root)
    s3 = seal(rec, "other-seed")
    v5 = (s3["root"] != s["root"]) and (s3["nonces"]["country"] != s["nonces"]["country"])
    ok &= v5; print(f"  {'OK ' if v5 else 'FAIL'}  a different seed re-blinds (root and nonces differ)")
    print("CHECK seal " + ("T" if ok else "F"))
    return 0 if ok else 1

def main():
    a = sys.argv[1:]
    if a and a[0] == "--selftest":
        sys.exit(_selftest())
    if not a:
        print("usage: reveal.py [commit k=v…|reveal <sealed> f…|verify <pres>|--selftest]"); sys.exit(2)
    if a[0] == "commit":
        seed = "seed"; pairs = []
        i = 1
        while i < len(a):
            if a[i] == "--seed": seed = a[i + 1]; i += 2; continue
            k, v = a[i].split("=", 1); pairs.append((k, v)); i += 1
        s = seal(dict(pairs), seed)
        out = "/tmp/sealed.json"; open(out, "w").write(json.dumps(s, indent=1))
        print("sealed %d fields -> %s\ncommitment root: %s" % (len(s["fields"]), out, s["root"]))
    elif a[0] == "reveal":
        s = json.load(open(a[1])); pres = present(s, a[2:])
        out = "/tmp/presentation.json"; open(out, "w").write(json.dumps(pres, indent=1))
        print("revealed %s -> %s\n  (the root binds them; unrevealed fields stay hidden)" % (", ".join(a[2:]), out))
    elif a[0] == "verify":
        pres = json.load(open(a[1])); ok = verify_presentation(pres)
        for it in pres["revealed"]:
            print("  %s = %s" % (it["field"], it["value"]))
        print("presentation %s the commitment %s" % ("BINDS to" if ok else "does NOT bind to", pres["root"][:16] + "…"))
        sys.exit(0 if ok else 1)
    else:
        print("unknown subcommand"); sys.exit(2)

if __name__ == "__main__":
    main()
