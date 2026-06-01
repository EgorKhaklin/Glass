#!/usr/bin/env python3
# Adversarial fuzz of the INDEPENDENT verifier: a tampered proof must NEVER verify.
# Loads an honest proof (from `glass prove --emit`), applies M random single-token tampers
# and runs pentecost's witness-free verify_b3 on each. A wrong-ACCEPT (a tamper that still
# verifies) would be a verifier soundness hole. Pure Python (no native, no shared /tmp beyond
# a per-seed scratch file) — embarrassingly parallel across seeds.
#   python3 fuzz/tamper_pentecost.py <seed> [M] [proof-file] [--claim]
#
# Two regions, two distinct soundness properties:
#   (default)  PROOF region   — perturb the proof itself; the verifier must still REJECT.
#   --claim    GATES region   — perturb the PUBLIC STATEMENT (the gate list + claimed result).
#              This is statement-binding: a valid proof of "a+b==8" must NOT verify against a
#              tampered claim "a+b==9" or an altered gate. A break here is catastrophic — you
#              could pass a true proof off as proving a false statement — so it is fuzzed too.
#
# proof-file defaults to the committed honest corpus fixture, so the campaign needs no slow
# native re-proof. The honest baseline is asserted to ACCEPT before any tampering — otherwise
# the fuzzer would be vacuously "sound" against a proof nothing accepts.
import sys, os, random
sys.setrecursionlimit(100000)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
from pentecost.pentecost_verify import parse, verify_b3

argv = [a for a in sys.argv[1:] if not a.startswith("--")]
claim = "--claim" in sys.argv          # tamper the public statement instead of the proof
seed = int(argv[0])
M = int(argv[1]) if len(argv) > 1 else 50
proof = argv[2] if len(argv) > 2 else os.path.join(_root, "pentecost", "corpus", "honest_a_plus_b.b3.txt")
P = 2**64 - 2**32 + 1
base = open(proof).read().split()

# Baseline sanity: the untampered proof MUST verify, or the campaign tests nothing.
_g0, _p0 = parse(proof); _r0 = verify_b3(_g0, _p0)
if not (_r0[0] if isinstance(_r0, tuple) else _r0):
    print(f"SEED {seed}: BASELINE FAIL — honest proof did not ACCEPT under Pentecost"); sys.exit(2)
pi = base.index("PROOF")
# PROOF region = numeric tokens after the marker; GATES (claim) region = numeric tokens before it.
if claim:
    numpos = [i for i in range(1, pi) if base[i].lstrip("-").isdigit()]
else:
    numpos = [i for i in range(pi + 1, len(base)) if base[i].lstrip("-").isdigit()]
region = "claim" if claim else "proof"
rng = random.Random(seed)
scratch = f"/tmp/tamper_{region}_seed_{seed}.txt"
wrong = []
for _ in range(M):
    t = base[:]
    pos = rng.choice(numpos)
    v = int(t[pos]); strat = rng.randint(0, 4)
    cand = {0: str(v + 1), 1: str(v - 1), 2: "0",
            3: str((v * 2 + 1) % P), 4: str(rng.randint(0, P - 1))}[strat]
    if cand == t[pos]:
        cand = str((v + 1) % P)   # a no-op "tamper" (e.g. 0->"0") is not a tamper; force a real change
    t[pos] = cand
    open(scratch, "w").write(" ".join(t))
    try:
        g, p = parse(scratch); r = verify_b3(g, p)
        acc = r[0] if isinstance(r, tuple) else r
    except Exception:
        acc = False   # a parse/verify error is a REJECT (sound), never a wrong-ACCEPT
    if acc:
        wrong.append((pos, strat))
print(f"SEED {seed} [{region}]: {M} tampers, {len(wrong)} wrong-ACCEPTs" + (f"  !! {wrong[:5]}" if wrong else ""))
sys.exit(0 if not wrong else 1)
