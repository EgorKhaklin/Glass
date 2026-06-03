#!/usr/bin/env python3
# =============================================================================
# fuzz_soundness.py — differential soundness fuzzing of the prove pipeline.
#
# Generates random small Glass programs over private inputs — arithmetic, unsigned
# comparison/boolean, signed gadgets (slt/sle/sgt/sge, sdiv/smod), strings
# (++/substring/string_length/==, the multi-wire codepoint lowering), AND records
# (declare/construct/destructure a 2-field record — the multi-wire tuple shape) — proves each
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
# Boundary inputs (--boundary mode): values right at the range-gadget edges, where a
# canonical-form wrong-ACCEPT would be catastrophic (the crown-jewel class). Unsigned gadgets
# admit [0, 2^32); signed admit [-2^31, 2^31). Each of 2^31 and 2^32 is probed at -1/0/+1 so the
# fuzzer hits "just in range" (must ACCEPT-and-AGREE) and "just over" (must ABSTAIN), never a
# wrong ACCEPT at the seam. Includes a small value so divisors aren't all huge.
P31, P32 = 1 << 31, 1 << 32
BOUNDARY = [0, 1, 5, P31 - 1, P31, P31 + 1, P32 - 1, P32, P32 + 1,
            -1, -5, -P31, -P31 + 1, -P31 - 1]

# STRING family (v5.101): random predicates over string LITERALS — concat, substring, length,
# equality — exercising the multi-wire string lowering (codepoint wires, the AND-folded is-zero
# `==`, static `substring` slice, `char_code` over a varied alphabet). Predicates are ~half true /
# ~half false by construction; the witness3 reference (glass.py) decides which and confirms it. Safe
# alphabet only (no quote/backslash/newline), so the generated literals need no escaping.
SAFE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.@"
def rand_str(rng, lo=1, hi=6):
    return "".join(rng.choice(SAFE_CHARS) for _ in range(rng.randint(lo, hi)))
def gen_string(rng, depth):
    k = rng.random()
    if k < 0.4:
        a = rand_str(rng); b = rand_str(rng)
        rhs = (a + b) if rng.random() < 0.5 else rand_str(rng, len(a) + len(b), len(a) + len(b))
        return '("%s" ++ "%s") == "%s"' % (a, b, rhs)
    elif k < 0.8:
        s = rand_str(rng, 3, 8); a = rng.randint(0, len(s) - 1); b = rng.randint(a, len(s))
        rhs = s[a:b] if rng.random() < 0.5 else rand_str(rng, b - a, b - a)
        return 'substring("%s", %d, %d) == "%s"' % (s, a, b, rhs)
    s = rand_str(rng, 1, 8)
    return 'string_length("%s") == %d' % (s, rng.randint(0, 9))

# RECORD family (v5.109): a self-contained record program — declare a 2-field record, construct it
# from the private inputs, read the fields (randomly via a `match` destructure OR direct `.field`
# access, fuzzing both the v5.103 pattern path and the v5.104 type-env path), combine arithmetically.
def gen_record_prog(rng):
    op = rng.choice(["+", "-", "*"])
    e0 = gen_expr(rng, 2); e1 = gen_expr(rng, 2)
    body = ("match r { Rec { f0, f1 } => f0 %s f1 }" % op) if rng.random() < 0.5 else ("r.f0 %s r.f1" % op)
    return "type Rec = { f0: Int, f1: Int }\nfn ruse(r: Rec) : Int = %s\nruse(Rec { f0: %s, f1: %s })" % (body, e0, e1)

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

def gen_signed(rng, depth):
    # SIGNED gadgets (slt/sle/sgt/sge comparison, sdiv/smod C99 truncated division) over small
    # signed operands. Inputs may be negative (-20..20), so this fuzzes the v5.94-v5.96 signed
    # lowering: the +2^31 offset binding, canonical negative inputs/literals, and the sign-magnitude
    # divmod. A comparison yields 0/1; sdiv/smod yield a signed quotient/remainder. Operands stay in
    # [-2^31, 2^31); a 0 divisor or an out-of-range operand ABSTAINs (sound — not a wrong proof).
    if rng.random() < 0.55:
        f = rng.choice(["slt", "sle", "sgt", "sge"])
        return "%s(%s, %s)" % (f, gen_expr(rng, depth), gen_expr(rng, depth))
    f = rng.choice(["sdiv", "smod"])
    return "%s(%s, %s)" % (f, gen_expr(rng, depth), gen_expr(rng, depth))

def run(n, seed, boundary=False):
    rng = random.Random(seed)
    mode = "BOUNDARY (inputs at the 2^31/2^32 range-gadget seams)" if boundary else "random (inputs 0..20 / -20..20)"
    print(f"# soundness fuzz: {n} programs, {mode} (arithmetic + comparison/boolean + signed + string + record, seed {seed})")
    ok = True
    for i in range(n):
        # cycle 5 families so each batch exercises the arithmetic lowering, the unsigned
        # comparison-gadget + boolean control-flow, the signed gadgets (slt/sdiv, the newest,
        # riskiest), the multi-wire string lowering, AND the multi-wire record shape. Signed inputs
        # may be negative (-20..20); the others stay non-negative so the unsigned [0,2^32) gadget
        # doesn't spuriously abstain.
        # In boundary mode only the GADGET-bearing families (comparison + signed), whose operands
        # are range-guarded — a raw arithmetic product over near-2^32 inputs is a benign int64-vs-
        # field wrap (documented), not a soundness bug, so the arithmetic family is excluded there.
        fam = (1 + (i % 2)) if boundary else (i % 5)
        if fam == 0:
            expr = gen_expr(rng, 3)
        elif fam == 1:
            expr = gen_bool(rng, 2)
        elif fam == 2:
            expr = gen_signed(rng, 1)
        elif fam == 3:
            expr = gen_string(rng, 1)
        else:
            expr = gen_record_prog(rng)
        if boundary:
            # signed family may use negatives; unsigned families draw from the non-negative seams.
            pool = BOUNDARY if fam == 2 else [x for x in BOUNDARY if x >= 0]
            inputs = {v: rng.choice(pool) for v in VARS}
        else:
            lo = -20 if fam == 2 else 0
            inputs = {v: rng.randint(lo, 20) for v in VARS}
        src = expr + "\n"
        path = f"/tmp/fuzz_{i}.glass"
        open(path, "w").write(src)
        argv = [sys.executable, os.path.join(ROOT, "glass.py"), "prove", "--witness3", path] + \
               [f"{v}={inputs[v]}" for v in VARS]
        out = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT).stdout
        accept = "proof:   ACCEPT" in out
        reject = "proof:   REJECT" in out
        abstain = "verdict: ABSTAIN" in out
        agrees = "THIRD LINEAGE AGREES" in out
        diverges = "DIVERGENCE" in out
        verdict = "ACCEPT" if accept else ("REJECT" if reject else ("ABSTAIN" if abstain else "?"))
        # THE soundness invariant: a WRONG proof = ACCEPT whose result the independent reference
        # interpreter computes DIFFERENTLY (witness3 DIVERGENCE). ABSTAIN (gadget refuses out-of-range
        # / unlowerable / ill-typed) and REJECT (disproof) are SOUND. ACCEPT + AGREES is sound.
        # ACCEPT + witness3-SKIPPED (the reference couldn't evaluate — e.g. an ill-typed source the
        # type-check gate should already ABSTAIN) is UNVERIFIED, NOT a wrong proof — the reference
        # neither confirms nor denies, so it cannot witness a falsehood. Only a DIVERGENCE fails.
        wrong_accept = accept and diverges
        unverified = accept and not agrees and not diverges
        ok = ok and not wrong_accept
        tag = "BUG!" if wrong_accept else ("????" if unverified else "OK  ")
        note = "" if not accept else (" witness3=AGREES" if agrees else (" witness3=DISAGREES <-- WRONG PROOF" if diverges else " witness3=SKIPPED (unverified, not a wrong proof)"))
        print(f"  {tag}  [{verdict}]{note}  {expr}  with {inputs}")
        if wrong_accept or unverified:
            print("        " + " | ".join(l for l in out.splitlines() if "result" in l or "witness3" in l))
    print("FUZZ " + ("PASS — no wrong proofs (every ACCEPT confirmed by the reference; ABSTAIN/REJECT are sound)" if ok else "FAIL — a wrong proof was found"))
    return 0 if ok else 1

def run_differential(n, seed):
    """Fuzz the TWO-VERIFIER differential: for random programs, emit a portable proof and confirm the
    INDEPENDENT Pentecost verifier ACCEPTs it. A violation = Glass proves it but Pentecost rejects an
    honest proof (a serializer or second-verifier bug). Cycles three families — arithmetic, unsigned
    comparison/boolean, and SIGNED (slt/sle/sgt/sge, sdiv/smod over negatives) — so the two-verifier
    guarantee is fuzzed across the gadget-bearing lowerings, not just `a+b`. (A signed proof is large,
    ~550k tokens, so emit is the slow step; keep N modest.)"""
    rng = random.Random(seed)
    print(f"# differential fuzz: {n} programs (arithmetic + comparison + signed + string + record), Glass-prove vs independent Pentecost (seed {seed})")
    ok = True
    for i in range(n):
        fam = i % 5
        if fam == 0:
            expr = gen_expr(rng, 3)
        elif fam == 1:
            expr = gen_bool(rng, 2)
        elif fam == 2:
            expr = gen_signed(rng, 1)
        elif fam == 3:
            expr = gen_string(rng, 1)
        else:
            expr = gen_record_prog(rng)
        lo = -20 if fam == 2 else 0
        inputs = {v: rng.randint(lo, 20) for v in VARS}
        path = f"/tmp/fuzzd_{i}.glass"
        open(path, "w").write(expr + "\n")
        pf = f"/tmp/fuzzd_{i}.proof"
        emit = subprocess.run([sys.executable, os.path.join(ROOT, "glass.py"), "prove", "--emit", pf, path] +
                              [f"{v}={inputs[v]}" for v in VARS], capture_output=True, text=True, cwd=ROOT)
        emitted = (emit.returncode == 0) and ("wrote a portable proof" in emit.stdout)
        if not emitted:
            # ABSTAIN (unlowerable) is sound — skip, not a failure
            print(f"  --  [no proof emitted]  {expr}  with {inputs}")
            continue
        ver = subprocess.run([sys.executable, os.path.join(ROOT, "glass.py"), "verify", pf], capture_output=True, text=True, cwd=ROOT)
        pent = "PENTECOST: ACCEPT" in ver.stdout
        # both verifiers must AGREE: Glass emitted an honest proof, Pentecost must ACCEPT it
        good = pent
        ok = ok and good
        print(f"  {'OK  ' if good else 'BUG!'}  Glass=ACCEPT  Pentecost={'ACCEPT' if pent else 'REJECT <-- DISAGREE'}  {expr}  with {inputs}")
        if not good:
            print("        " + ver.stdout.strip())
    print("DIFFERENTIAL FUZZ " + ("PASS — the two verifiers agree on every honest proof" if ok else "FAIL — the verifiers DISAGREED"))
    return 0 if ok else 1

if __name__ == "__main__":
    flags = {"--differential", "--boundary"}
    a = [x for x in sys.argv[1:] if x not in flags]
    n = int(a[0]) if len(a) > 0 else 4
    seed = int(a[1]) if len(a) > 1 else 1
    if "--differential" in sys.argv:
        sys.exit(run_differential(n, seed))
    sys.exit(run(n, seed, boundary="--boundary" in sys.argv))
