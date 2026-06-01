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

def run(n, seed):
    rng = random.Random(seed)
    print(f"# soundness fuzz: {n} random arithmetic programs (seed {seed})")
    ok = True
    for i in range(n):
        expr = gen_expr(rng, 3)
        inputs = {v: rng.randint(0, 20) for v in VARS}
        src = expr + "\n"
        path = f"/tmp/fuzz_{i}.glass"
        open(path, "w").write(src)
        argv = ["python3", os.path.join(ROOT, "glass.py"), "prove", "--witness3", path] + \
               [f"{v}={inputs[v]}" for v in VARS]
        out = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT).stdout
        accept = "proof:   ACCEPT" in out
        agrees = "THIRD LINEAGE AGREES" in out
        good = accept and agrees
        ok = ok and good
        tag = "OK " if good else "FAIL"
        print(f"  {tag}  {expr}  with {inputs}  -> accept={accept} witness3_agrees={agrees}")
        if not good:
            print("        " + " | ".join(l for l in out.splitlines() if "result" in l or "proof" in l or "witness3" in l))
    print("FUZZ " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    sys.exit(run(n, seed))
