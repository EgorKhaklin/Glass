#!/usr/bin/env python3
# Adversarial fuzz of the INDEPENDENT verifier: a tampered proof must NEVER verify.
# Loads an honest proof (from `glass prove --emit`), applies M random single-token tampers
# to the PROOF region, and runs pentecost's witness-free verify_b3 on each. A wrong-ACCEPT
# (a tamper that still verifies) would be a verifier soundness hole. Pure Python (no native,
# no shared /tmp beyond a per-seed scratch file) — embarrassingly parallel across seeds.
#   python3 fuzz/tamper_pentecost.py <seed> [M] [proof-file]
# proof-file defaults to the committed honest corpus fixture, so the campaign needs no
# slow native re-proof. The honest baseline is asserted to ACCEPT before any tampering —
# otherwise the fuzzer would be vacuously "sound" against a proof nothing accepts.
import sys, os, random
sys.setrecursionlimit(100000)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
from pentecost.pentecost_verify import parse, verify_b3

seed = int(sys.argv[1])
M = int(sys.argv[2]) if len(sys.argv) > 2 else 50
proof = sys.argv[3] if len(sys.argv) > 3 else os.path.join(_root, "pentecost", "corpus", "honest_a_plus_b.b3.txt")
P = 2**64 - 2**32 + 1
base = open(proof).read().split()

# Baseline sanity: the untampered proof MUST verify, or the campaign tests nothing.
_g0, _p0 = parse(proof); _r0 = verify_b3(_g0, _p0)
if not (_r0[0] if isinstance(_r0, tuple) else _r0):
    print(f"SEED {seed}: BASELINE FAIL — honest proof did not ACCEPT under Pentecost"); sys.exit(2)
pi = base.index("PROOF")
numpos = [i for i in range(pi + 1, len(base)) if base[i].lstrip("-").isdigit()]
rng = random.Random(seed)
scratch = f"/tmp/tamper_seed_{seed}.txt"
wrong = []
for _ in range(M):
    t = base[:]
    pos = rng.choice(numpos)
    v = int(t[pos]); strat = rng.randint(0, 4)
    t[pos] = {0: str(v + 1), 1: str(v - 1), 2: "0",
              3: str((v * 2 + 1) % P), 4: str(rng.randint(0, P - 1))}[strat]
    open(scratch, "w").write(" ".join(t))
    try:
        g, p = parse(scratch); r = verify_b3(g, p)
        acc = r[0] if isinstance(r, tuple) else r
    except Exception:
        acc = False   # a parse/verify error is a REJECT (sound), never a wrong-ACCEPT
    if acc:
        wrong.append((pos, strat))
print(f"SEED {seed}: {M} tampers, {len(wrong)} wrong-ACCEPTs" + (f"  !! {wrong[:5]}" if wrong else ""))
sys.exit(0 if not wrong else 1)
