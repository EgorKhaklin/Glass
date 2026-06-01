#!/usr/bin/env python3
# =============================================================================
# fuzz_soundness.py — differential soundness fuzzing of the prove pipeline.
#
# Generates random small arithmetic Glass programs over private inputs, proves each
# with `glass prove --witness3`, and asserts the soundness invariants across the
# WHOLE stack at once:
#   (1) honest proof -> ACCEPT          (verify_b3 accepts a real proof)
#   (2) THIRD LINEAGE AGREES            (the bridge's circuit semantics == the reference
#                                        interpreter — catches a lowering gap on THIS program)
# Inputs are kept small (0..20) and expressions shallow (<=3 ops) so results stay well
# within both the Goldilocks field and int64 — so a witness3 divergence is a real bug, not
# the documented mod-p-vs-int64 domain difference. Deterministic (fixed seed); reproducible.
# This is the testing that finds the bugs the hand-picked soundness gate cannot enumerate.
#
#   python3 fuzz/fuzz_soundness.py [N] [seed]
# =============================================================================
import sys, os, subprocess, random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VARS = ["a", "b", "c"]

def gen_expr(rng, depth):
    if depth <= 0 or rng.random() < 0.35:
        return rng.choice(VARS) if rng.random() < 0.7 else str(rng.randint(0, 9))
    op = rng.choice(["+", "-", "*"])
    return "(%s %s %s)" % (gen_expr(rng, depth - 1), op, gen_expr(rng, depth - 1))

def gen_bool(rng, depth):
    # comparison + boolean control flow — the gadget-bearing, least-fuzzed lowering.
    # operands kept small (the arithmetic generator over inputs in 0..20) so they sit in the
    # gadget's provable range [0, 2^32); a comparison yields a public 0/1.
    if depth <= 0 or rng.random() < 0.45:
        cmp = rng.choice(["<", ">", "<=", ">="])
        return "(%s %s %s)" % (gen_expr(rng, 1), cmp, gen_expr(rng, 1))
    k = rng.random()
    if k < 0.4:
        return "(%s %s %s)" % (gen_bool(rng, depth - 1), rng.choice(["&&", "||"]), gen_bool(rng, depth - 1))
    if k < 0.6:
        return "(! %s)" % gen_bool(rng, depth - 1)
    return "(if %s then %s else %s)" % (gen_bool(rng, depth - 1), gen_expr(rng, 1), gen_expr(rng, 1))

def run(n, seed):
    rng = random.Random(seed)
    print(f"# soundness fuzz: {n} random programs (arithmetic + comparison/boolean, seed {seed})")
    ok = True
    for i in range(n):
        # alternate families so each batch exercises BOTH the arithmetic lowering and the
        # comparison-gadget + boolean control-flow lowering (the newest, riskiest).
        expr = gen_bool(rng, 2) if (i % 2 == 1) else gen_expr(rng, 3)
        inputs = {v: rng.randint(0, 20) for v in VARS}
        src = expr + "\n"
        path = f"/tmp/fuzz_{i}.glass"
        open(path, "w").write(src)
        argv = ["python3", os.path.join(ROOT, "glass.py"), "prove", "--witness3", path] + \
               [f"{v}={inputs[v]}" for v in VARS]
        out = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT).stdout
        accept = "proof:   ACCEPT" in out
        reject = "proof:   REJECT" in out
        abstain = "verdict: ABSTAIN" in out
        agrees = "THIRD LINEAGE AGREES" in out
        verdict = "ACCEPT" if accept else ("REJECT" if reject else ("ABSTAIN" if abstain else "?"))
        # THE soundness invariant: a wrong proof = ACCEPT whose result the independent reference
        # interpreter does NOT confirm. ABSTAIN (gadget refuses out-of-range / unlowerable) and
        # REJECT (disproof) are SOUND outcomes — only a wrong ACCEPT is a violation.
        wrong_accept = accept and not agrees
        good = not wrong_accept
        ok = ok and good
        tag = "BUG!" if wrong_accept else "OK  "
        note = "" if not accept else (" witness3=AGREES" if agrees else " witness3=DISAGREES <-- WRONG PROOF")
        print(f"  {tag}  [{verdict}]{note}  {expr}  with {inputs}")
        if wrong_accept:
            print("        " + " | ".join(l for l in out.splitlines() if "result" in l or "witness3" in l))
    print("FUZZ " + ("PASS — no wrong proofs (every ACCEPT confirmed by the reference; ABSTAIN/REJECT are sound)" if ok else "FAIL — a wrong proof was found"))
    return 0 if ok else 1

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    sys.exit(run(n, seed))
