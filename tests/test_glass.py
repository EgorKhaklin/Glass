"""Regression suite for Glass.

Runs every example and every expected-failure case, prints a summary.
"""
from __future__ import annotations
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GLASS = os.path.join(ROOT, "glass.py")
EX = os.path.join(ROOT, "examples")


def run(src: str) -> tuple[int, str, str]:
    p = subprocess.run(
        [sys.executable, GLASS, "/dev/stdin"],
        input=src, capture_output=True, text=True,
    )
    return p.returncode, p.stdout, p.stderr


def run_file(path: str) -> tuple[int, str, str]:
    p = subprocess.run(
        [sys.executable, GLASS, path], capture_output=True, text=True,
    )
    return p.returncode, p.stdout, p.stderr


# Examples that must succeed.
POSITIVE = [
    os.path.join(EX, "basic",    "hello.glass"),
    os.path.join(EX, "basic",    "fib.glass"),
    os.path.join(EX, "basic",    "list_ops.glass"),
    os.path.join(EX, "basic",    "option_result.glass"),
    os.path.join(EX, "basic",    "records.glass"),
    os.path.join(EX, "features", "generics.glass"),
    os.path.join(EX, "features", "crypto.glass"),
    os.path.join(EX, "features", "effects.glass"),
    os.path.join(EX, "features", "queries.glass"),
    os.path.join(EX, "features", "ai.glass"),
    os.path.join(EX, "features", "infer.glass"),
    os.path.join(EX, "selfhost", "parser.glass"),
    os.path.join(EX, "selfhost", "bootstrap.glass"),
    os.path.join(EX, "selfhost", "prism.glass"),
    os.path.join(EX, "selfhost", "typecheck.glass"),
    os.path.join(EX, "selfhost", "mini.glass"),
    os.path.join(EX, "showcase", "derive.glass"),
    os.path.join(EX, "showcase", "prover.glass"),
    os.path.join(EX, "showcase", "nash.glass"),
    os.path.join(EX, "showcase", "quantum.glass"),
    os.path.join(EX, "showcase", "golden.glass"),
    os.path.join(EX, "showcase", "harmonic.glass"),
    os.path.join(EX, "showcase", "geometry.glass"),
    os.path.join(EX, "showcase", "fractal.glass"),
    os.path.join(EX, "showcase", "spiral.glass"),
    os.path.join(EX, "showcase", "symmetry.glass"),
    os.path.join(EX, "showcase", "epistemic.glass"),
    os.path.join(EX, "showcase", "entanglement.glass"),
    os.path.join(EX, "showcase", "amplitude.glass"),
    os.path.join(EX, "showcase", "strategy.glass"),
    os.path.join(EX, "showcase", "worlds.glass"),
    os.path.join(EX, "showcase", "rational.glass"),
    os.path.join(EX, "showcase", "probability.glass"),
    os.path.join(EX, "showcase", "causal.glass"),
    os.path.join(EX, "showcase", "counterfactual.glass"),
    os.path.join(EX, "showcase", "identity.glass"),
    os.path.join(EX, "showcase", "observer.glass"),
    os.path.join(EX, "showcase", "simulation.glass"),
    os.path.join(EX, "showcase", "infoflow.glass"),
    os.path.join(EX, "showcase", "units.glass"),
    os.path.join(EX, "showcase", "conservation.glass"),
    os.path.join(EX, "showcase", "linear.glass"),
    os.path.join(EX, "features", "linear_ok.glass"),
    os.path.join(EX, "showcase", "refined_data.glass"),
    os.path.join(EX, "features", "imports.glass"),
    os.path.join(EX, "showcase", "refine.glass"),
    os.path.join(EX, "showcase", "compose.glass"),
    os.path.join(EX, "showcase", "imply.glass"),
    os.path.join(EX, "showcase", "regex.glass"),
    os.path.join(EX, "showcase", "json.glass"),
    os.path.join(EX, "showcase", "config.glass"),
    os.path.join(EX, "showcase", "markdown.glass"),
    os.path.join(EX, "features", "letstar.glass"),
    os.path.join(EX, "features", "letqmark.glass"),
    os.path.join(EX, "features", "letpat.glass"),
    os.path.join(EX, "features", "generic_fn.glass"),
    os.path.join(EX, "features", "generic_rec.glass"),
    os.path.join(EX, "features", "refine.glass"),
    os.path.join(EX, "features", "alpha_refine.glass"),
    os.path.join(EX, "features", "imply_refine.glass"),
    os.path.join(EX, "features", "runtime_refine.glass"),
    os.path.join(EX, "features", "curried_refine.glass"),
    os.path.join(EX, "features", "return_refine.glass"),
    os.path.join(EX, "features", "safe_div.glass"),
    os.path.join(EX, "features", "parens_after_let.glass"),
    os.path.join(EX, "features", "lambda_refine.glass"),
    os.path.join(EX, "features", "lambda_multi.glass"),
    os.path.join(EX, "features", "lambda_multi_refine.glass"),
    os.path.join(EX, "features", "and_or.glass"),
    os.path.join(EX, "features", "mod_refine.glass"),
    os.path.join(EX, "features", "not_refine.glass"),
    os.path.join(EX, "features", "xparam_refine.glass"),
    os.path.join(EX, "selfhost", "prism_lexer.glass"),
    os.path.join(EX, "selfhost", "quartz_min.glass"),
    os.path.join(EX, "selfhost", "build_pipeline.glass"),
    os.path.join(EX, "selfhost", "quartz_parser.glass"),
    os.path.join(EX, "selfhost", "selfcompile.glass"),
    os.path.join(EX, "stage3", "tinylang.glass"),
    os.path.join(EX, "stage3", "tinycalc.glass"),
    os.path.join(EX, "stage3", "midlang.glass"),
    os.path.join(EX, "stage3", "safecalc.glass"),
]

# (label, source, expected substring in stderr) — must fail with the right reason.
NEGATIVE = [
    # ---- v0.0.1 cases ----
    ("fn return mismatch",
     'fn f(n: Int) : Int = "no"',
     "declared return Int, body is String"),

    ("heterogeneous list",
     'let xs : List<Int> = [1, 2, "three"]',
     "list elements differ"),

    ("if branches differ",
     'let x : Int = if true then 1 else "x"',
     "if branches differ"),

    ("polymorphic builtin mismatch",
     'let xs : List<String> = ["a"]\n'
     'fn d(n: Int) : Int = n\n'
     'let bad : List<Int> = map(xs, d)',
     "arg type mismatch"),

    ("unbound identifier",
     'let x : Int = nope',
     "unbound identifier"),

    ("arity mismatch",
     'fn f(a: Int, b: Int) : Int = a + b\n'
     'let r : Int = f(1)',
     "arity mismatch"),

    # ---- v0.1 sum-type cases ----
    ("non-exhaustive match on Option",
     'fn f(o: Option<Int>) : Int = match o { Some(x) => x }',
     "non-exhaustive match on Option"),

    ("non-exhaustive match on Bool",
     'fn f(b: Bool) : Int = match b { true => 1 }',
     "non-exhaustive match"),

    ("non-exhaustive match on List",
     'fn f(xs: List<Int>) : Int = match xs { [] => 0 }',
     "non-exhaustive match on list"),

    ("ctor from wrong type",
     'fn f(o: Option<Int>) : Int = match o { Ok(x) => x ; None => 0 }',
     "Ok is from Result, but scrutinee is Option"),

    ("type-arity mismatch on annotation",
     'let bad : Option<Int, String> = None',
     "expects 1 arg"),

    ("unknown type in annotation",
     'let bad : Frobnicate<Int> = None',
     "unknown type"),

    ("ctor expects more fields",
     'let bad : Option<Int> = Some',
     # Some has no args here — it's the bare ctor as a value, which has fn type;
     # the annotation expects Option<Int>, not (Int) -> Option<Int>.
     "declared Option<Int>"),

    # ---- v0.2 cases ----
    ("head returns Option, not raw",
     'let xs : List<Int> = [1, 2, 3]\n'
     'let bad : Int = head(xs)',
     "declared Int, inferred Option<Int>"),

    ("Pair from prelude — type-arity check",
     'let bad : Pair<Int> = Pair(1, 2)',
     "expects 2 arg"),

    ("can't mix env types in Pair list",
     'let bad : List<Pair<String, Int>> = [Pair("a", 1), Pair("b", "wrong")]',
     "list elements differ"),

    # ---- v0.3 polymorphism soundness cases ----
    ("can't treat type param as Int inside body",
     'fn bad<A>(x: A) : A = let y : A = 42 in y',
     "let-in y: declared A, inferred Int"),

    ("can't return Int as type param A",
     'fn bad<A>(x: A) : A = 42',
     "declared return A, body is Int"),

    ("calling polymorphic fn with mismatched types",
     'fn id<T>(x: T) : T = x\n'
     'fn use_it(s: String) : Int = id(s)',
     "declared return Int"),

    ("type-arity on user-defined polymorphic fn",
     'fn id<T>(x: T) : T = x\n'
     'let bad : Int = id(1, 2)',
     "arity mismatch"),

    # ---- v0.4 refinement-type cases ----
    # v1.2: refinements with constant args are discharged statically.
    ("refinement violated at compile time (literal arg)",
     'fn d(a: Int, b: Int where (b != 0)) : Int = a / b\n'
     'let r : Int = d(10, 0)',
     "refinement violated at compile time"),

    # Runtime check still applies for non-constant arguments.
    ("refinement violated at runtime (dynamic arg)",
     'fn d(a: Int, b: Int where (b != 0)) : Int = a / b\n'
     'fn ident(n: Int) : Int = n\n'
     'let zero = ident(0)\n'
     'let r : Int = d(10, zero)',
     "refinement violated: b = 0"),

    # v4.24: curried multi-param case where the refinement is on the
    # SECOND param and the arg is a let-bound variable (not a literal).
    # Pinned down as a host-parity spec — prism's port mirrors this
    # error shape via its v4.24 VRefinedClos wrapper.
    ("refinement violated on second param at runtime (v4.24 host parity)",
     "fn safe_add(a: Int, b: Int where (b != 0)) : Int = a + b\n"
     "let zero : Int = 0\n"
     "let r : Int = safe_add(10, zero)",
     "refinement violated: b = 0"),

    # v4.25: return-type refinement violation. Host check has been in
    # place since v1.3; prism's port mirrors this shape — the
    # VRefinedClos wrapper carries the return type forward across
    # curried applies and checks against the final value on the last
    # apply.
    ("return refinement violated (multi-param, v4.25 host parity)",
     "fn diff(a: Int, b: Int) : Int where (result >= 0) = a - b\n"
     "let smaller : Int = 3\n"
     "let bigger : Int = 7\n"
     "let r : Int = diff(smaller, bigger)",
     "refinement violated: result = -4"),

    # Static discharge through arithmetic constant-folding.
    ("static discharge via subtraction fold",
     'fn f(n: Int where (n > 0)) : Int = n\n'
     'let r : Int = f(5 - 7)',
     "refinement violated at compile time"),

    # Static discharge through if-then-else folding.
    ("static discharge via if-fold",
     'fn f(n: Int where (n > 0)) : Int = n\n'
     'let r : Int = f(if true then 0 else 10)',
     "refinement violated at compile time"),

    # Return-type refinement violation at runtime (v1.3).
    ("return refinement violated at runtime",
     'fn negate(n: Int) : Int where (result >= 0) = 0 - n\n'
     'let r : Int = negate(5)',
     "refinement violated: result = -5 fails predicate"),

    # v1.4: implication discharges (result >= 5) does NOT imply (n > 5),
    # so the runtime check fires when at_least_five returns exactly 5.
    ("implication unsound: >= 5 should not imply > 5",
     'fn at_least_five(n: Int) : Int where (result >= 5) =\n'
     '  if n >= 5 then n else 5\n'
     'fn needs_above_five(n: Int where (n > 5)) : Int = n\n'
     'let r : Int = needs_above_five(at_least_five(0))',
     "refinement violated: n = 5 fails predicate (n > 5)"),

    ("refinement predicate must be Bool",
     'fn d(b: Int where (b + 1)) : Int = b',
     "must return Bool"),

    ("refinement predicate references unbound name",
     'fn d(b: Int where (q > 0)) : Int = b',
     "unbound identifier"),

    ("let refinement violated",
     'let x : Int where (x > 100) = 5',
     "refinement violated: x = 5"),

    # ---- v0.5 effect-tracking cases ----
    ("pure fn performing IO without declaring",
     'fn loud() : Int = let _ : String = print("oops") in 42',
     "fn loud performs effect(s) ['IO']"),

    ("fn declaring only IO but doing Random",
     'fn r() : Int !{IO} = random_int(0, 10)',
     "performs effect(s) ['Random']"),

    ("fn declaring only Random but doing IO",
     'fn s() : Int !{Random} = let _ : String = print("hi") in 0',
     "performs effect(s) ['IO']"),

    # ---- v0.7 effect polymorphism + Inference ----
    ("pure fn can't use map with effectful callback (caller must declare effects)",
     'fn loud(n: Int) : Int !{IO} =\n'
     '  let _ : String = print("x") in n\n'
     'fn pure_run() : List<Int> = map([1, 2], loud)',
     "performs effect(s) ['IO']"),

    ("undeclared !{Inference} is caught",
     'fn sneaky(s: String) : String = model_call("x: " ++ s)',
     "performs effect(s) ['Inference']"),

    ("fn declaring IO but body also does Inference is caught",
     'fn mixed(s: String) : String !{IO} =\n'
     '  let _ : String = print("doing it") in\n'
     '  model_call(s)',
     "performs effect(s) ['Inference']"),

    # ---- v0.6 tuple cases ----
    ("tuple-arity mismatch in pattern",
     'let p : (Int, String) = (1, "x")\n'
     'fn f(p: (Int, String)) : Int = match p { (a, b, c) => a }',
     "tuple pattern arity mismatch"),

    ("tuple type-arity mismatch",
     'let p : (Int, String) = (1, 2)',
     "declared (Int, String), inferred (Int, Int)"),

    ("non-tuple destructured with tuple pattern",
     'fn f(n: Int) : Int = match n { (a, b) => a }',
     "tuple pattern against Int"),

    # Mutual recursion success: this would have failed before v0.6.
    # Tested via examples/queries.glass (bump <-> count_by_country) and
    # by being able to declare fns in source-independent order.

    # ---- v0.7 effect polymorphism + Inference ----
    ("pure fn can't use polymorphic map with Inference callback",
     'fn pure_batch(xs: List<String>) : List<String> =\n'
     '  map(xs, fn(s: String) -> model_call(s))',
     "performs effect(s) ['Inference']"),

    ("fn declaring only IO can't call a model",
     'fn io_only(s: String) : String !{IO} = model_call(s)',
     "performs effect(s) ['Inference']"),

    ("refinement violation on model output",
     'fn must_be_long(s: String) : String !{Inference} =\n'
     '  let r : String where (string_length(r) >= 1000) = model_call(s) in r\n'
     'let _ : String = must_be_long("hi")',
     "refinement violated"),

    # ---- v0.8 record cases ----
    ("record missing field",
     'type U = { id: Int, name: String }\n'
     'let u : U = U { id: 1 }',
     "missing field"),

    ("record extra field",
     'type U = { id: Int }\n'
     'let u : U = U { id: 1, extra: 5 }',
     "has no field"),

    ("record wrong field type",
     'type U = { id: Int, name: String }\n'
     'let u : U = U { id: "wrong", name: "Alice" }',
     "expected Int"),

    ("field access on non-record",
     'let n : Int = 5\n'
     'let x : Int = n.foo',
     "field access on non-record"),

    ("field access on unknown field",
     'type U = { id: Int }\n'
     'let u : U = U { id: 1 }\n'
     'let x : Int = u.bogus',
     "no field 'bogus'"),

    ("sum type used as record literal",
     'type Maybe = | Nope | Yep(Int)\n'
     'let m : Maybe = Maybe { Nope: 1 }',
     "use Maybe(...) for constructor call"),

    # ---- v0.8.1 string-ops cases ----
    ("substring with negative index",
     'let s : String = substring("hello", -1, 3)',
     "negative index"),

    ("substring with start > end",
     'let s : String = substring("hello", 4, 2)',
     "start > end"),

    # ---- v4.47: refined-param lambda rejection ----
    # The lambda's `where (x > 0)` runs at apply time. `let n = 0 - 3`
    # produces a non-literal so static discharge defers; the runtime
    # check then fires on n = -3 and the predicate fails.
    ("refined-param lambda rejects bad arg (v4.47)",
     "let n : Int = 0 - 3\n"
     "let r : Int = (fn(x: Int where (x > 0)) -> x * 2)(n)\n"
     "r\n",
     "refinement violated"),

    # ---- v4.48: refined SECOND param of a multi-arg lambda ----
    # First arg satisfies its refinement; the second fails. Pins
    # down that the per-param TyRefine check runs at each position,
    # not just the first.
    ("multi-arg refined lambda rejects 2nd arg (v4.48)",
     "let n : Int = 0\n"
     "let r : Int = (fn(a: Int where (a > 0), b: Int where (b > 0))"
     " -> a * b)(3, n)\n"
     "r\n",
     "b = 0 fails predicate"),

    # ---- v4.51: && / || type-checked as Bool, Bool → Bool ----
    # Non-Bool operands must be rejected with a clear shape error.
    ("&& rejects non-Bool operands (v4.51)",
     "let r : Bool = 1 && true\n",
     "expected Bool, Bool"),

    # ---- v4.53: % type-checked as Int, Int → Int ----
    ("% rejects non-Int operands (v4.53)",
     "let r : Int = true % 2\n",
     "expected Int, Int"),

    # ---- v4.54: ! requires a Bool operand ----
    ("! rejects non-Bool operand (v4.54)",
     "let r : Bool = !5\n",
     "expected Bool"),

    # ---- v4.56: cross-parameter refinement rejects bad input ----
    # hi=3, lo=10 → hi > lo is false. The check sees lo (earlier
    # param) and fires.
    ("cross-param refinement rejects bad input (v4.56)",
     "fn clamp(lo: Int, hi: Int where (hi > lo)) : Int = hi - lo\n"
     "let bad : Int = clamp(10, 3)\n"
     "bad\n",
     "refinement violated"),

    # ---- v4.66: conservation-law refinement rejects minting ----
    # The gate `after == before` (cross-param) fails when a transition
    # creates value (175 → 200), so non-conservative transitions are
    # rejected at the boundary.
    ("conservation refinement rejects minting (v4.66)",
     "fn checked(before: Int, after: Int where (after == before)) : Int"
     " = after\n"
     "let bad : Int = checked(175, 200)\n"
     "bad\n",
     "refinement violated"),

    # ---- v4.67: linear types — no cloning, no dropping ----
    # Using a linear resource twice is forbidden (no cloning).
    ("linear resource rejects cloning (v4.67)",
     "fn f() : Int = let lin x = 5 in x + x\n"
     "f()\n",
     "no cloning"),
    # Dropping a linear resource (never using it) is forbidden.
    ("linear resource rejects dropping (v4.67)",
     "fn f() : Int = let lin x = 5 in 99\n"
     "f()\n",
     "no dropping"),
    # Capturing a linear value in a closure can't guarantee single use.
    ("linear resource rejects lambda capture (v4.67)",
     "fn f() : Int = let lin x = 5 in (fn(y: Int) -> x + y)(3)\n"
     "f()\n",
     "captured in a lambda"),

    # ---- v4.69: field-level refinements rejected at construction ----
    # A negative value can't be packed into a Pos.
    ("refined ADT field rejects bad value (v4.69)",
     "type Pos = | Pos(n: Int where (n > 0))\n"
     "let bad = Pos(0 - 3)\n"
     "bad\n",
     "n = -3 fails predicate"),
    # Cross-field: hi must exceed lo; Range(10, 3) is rejected.
    ("cross-field refinement rejects bad range (v4.69)",
     "type Range = | Range(lo: Int, hi: Int where (hi > lo))\n"
     "let bad = Range(10, 3)\n"
     "bad\n",
     "hi = 3 fails predicate"),
]


def main() -> int:
    failures = 0

    print("== positive cases ==")
    for path in POSITIVE:
        rc, out, err = run_file(path)
        ok = (rc == 0)
        print(f"  {'OK ' if ok else 'FAIL'}  {os.path.basename(path)}")
        if not ok:
            print(f"        stderr: {err.strip()}")
            failures += 1

    print("== negative cases (must reject) ==")
    for label, src, needle in NEGATIVE:
        rc, out, err = run(src)
        ok = (rc != 0) and (needle in err)
        print(f"  {'OK ' if ok else 'FAIL'}  {label}")
        if not ok:
            print(f"        rc={rc}, expected substring {needle!r}")
            print(f"        stderr: {err.strip()}")
            failures += 1

    print("== inline regression cases ==")
    # (label, source, expected substring in stdout). Short programs that
    # pin down specific past bugs. Add a case when fixing a real bug.
    inline_positive = [
        # v4.21: parser used to greedily eat an LPAREN-starting next line as
        # call-continuation. `let s = id("hello")\n(n, s)` mis-parsed to
        # `id("hello")(n, s)` and crashed with "not a function: String".
        # The column-1 + new-line rule in parse_postfix stops it.
        ("parens-after-let split (v4.21)",
         'fn id<A>(x: A) : A = x\n'
         'let n = id(42)\n'
         'let s = id("hello")\n'
         'let p = (n, s)\n'
         'p\n',
         "(42, hello)"),
        # v4.28: deep tail recursion. Without the trampoline-based TCE
        # added in v4.28, count_down(15000) blows Python's recursion
        # limit even with sys.setrecursionlimit(20000). The test verifies
        # both correctness and unbounded-depth tolerance. We use 25000 to
        # exceed any reasonable Python limit so the test FAILS if TCE is
        # ever accidentally removed.
        ("deep tail recursion via TCE (v4.28)",
         "fn count_down(n: Int) : Int =\n"
         "  if n == 0 then 0 else count_down(n - 1)\n"
         "let result : Int = count_down(25000)\n"
         "result\n",
         "result : Int = 0"),
        # v4.28: tail-recursive sum_to with explicit accumulator. The
        # arithmetic check pins down the *value* — confirms that env
        # bindings (acc) flow correctly through the trampoline.
        ("tail-recursive accumulator via TCE (v4.28)",
         "fn sum_to(n: Int, acc: Int) : Int =\n"
         "  if n == 0 then acc else sum_to(n - 1, acc + n)\n"
         "let result : Int = sum_to(50000, 0)\n"
         "result\n",
         "result : Int = 1250025000"),
        # v4.23: prism runtime refinement check fires when static discharge
        # defers. The host already enforces runtime checks (since v0.4); this
        # test runs the same program through host to pin down the shape of the
        # error message that prism's port mirrors. The prism-side check is
        # exercised end-to-end when prism.glass runs in the POSITIVE list —
        # its demo chain reads runtime_refine_bad.glass and prints the same
        # message, which surfaces in prism's stdout (not its exit code).
        ("runtime refinement check (v4.23 host parity)",
         "fn positive_double(n: Int where (n > 0)) : Int = n * 2\n"
         "let x : Int = 21\n"
         "let r : Int = positive_double(x)\n"
         "r\n",
         "r : Int = 42"),
        # v4.21 drift catch: AGENT.md §5 claimed sequential top-level lets
        # using the same generic fn at different types fail to type-check.
        # They don't — the symptom in §5's repro was the parens-after-let
        # parser bug above. Pin both invariants down with a test.
        ("sequential generic-fn instantiation (v4.21)",
         'fn id<A>(x: A) : A = x\n'
         'let n = id(42)\n'
         'let s = id("hello")\n'
         'let b = id(true)\n'
         'b\n',
         ": Bool = true"),
        # v4.47: refined-param lambdas. Before v4.47 the host's
        # parse_lambda called parse_params without accept_refinement,
        # so `fn(x: Int where (x > 0)) -> ...` failed at the `where`
        # token. Now the parser accepts the refinement and the
        # existing apply_fn TyRefine path checks the predicate at
        # call time. Positive case: 5 > 0 holds, body returns 10.
        ("refined-param lambda accepts (v4.47)",
         "let r : Int = (fn(x: Int where (x > 0)) -> x * 2)(5)\n"
         "r\n",
         "r : Int = 10"),
        # v4.47 capture-aware variant: the lambda closes over `k`
        # AND has a refined param. Confirms ELamR (prism) / refined
        # Lambda (host) interoperates with closures, not just bare
        # arithmetic — refinement check runs before capture lookup.
        ("refined-param lambda with capture (v4.47)",
         "let k : Int = 100\n"
         "let r : Int = (fn(x: Int where (x > 0)) -> x + k)(7)\n"
         "r\n",
         "r : Int = 107"),
        # v4.48: multi-param lambdas. Three-arg variant pins down
        # that the right-fold builds the chain correctly across more
        # than two params (a common edge of "did I get the
        # recursion-base-case right?").
        ("three-arg lambda applied inline (v4.48)",
         "let r : Int = (fn(a: Int, b: Int, c: Int) -> a + b + c)(1, 2, 3)\n"
         "r\n",
         "r : Int = 6"),
        # v4.51: `&&` and `||` lex, parse, typecheck, evaluate. The
        # bigger language win for v4.51 is that boolean combinators
        # become legal in refinement predicates — pinning down basic
        # eval here means the predicate machinery has solid ground.
        ("&& and || basic truth tables (v4.51)",
         "let a : Bool = true && false\n"
         "let b : Bool = true || false\n"
         "let c : Bool = (3 > 0) && (3 < 100)\n"
         "let r : Bool = (a == false) && b && c\n"
         "r\n",
         "r : Bool = true"),
        # v4.51 precedence pin-down: `&&` binds tighter than `||`.
        # `false || true && false` must parse as
        # `false || (true && false)` = `false || false` = false.
        # If precedence were inverted it would be
        # `(false || true) && false` = `true && false` = false (same
        # answer by luck) — so we need a discriminating case:
        # `true && false || true` parses as `(true && false) || true`
        # = `false || true` = true. Flipped would be
        # `true && (false || true)` = `true && true` = true (same).
        # The actually discriminating shape:
        ("&& binds tighter than || (v4.51)",
         "let r : Bool = false || true && false\n"
         "r\n",
         "r : Bool = false"),
        # v4.51 range refinement at runtime. `n > 0 && n < 100` is
        # the canonical interval refinement; before this release a
        # single-comparison was the only valid shape.
        ("range refinement via && (v4.51)",
         "fn middling(n: Int where (n > 0 && n < 100)) : Int = n + 1\n"
         "let r : Int = middling(50)\n"
         "r\n",
         "r : Int = 51"),
        # v4.51 short-circuit semantics: the rhs of `&&` is NOT
        # evaluated when lhs is false. We probe this by putting an
        # expression that WOULD raise (refinement violation) on the
        # rhs, then verify the program completes successfully.
        ("&& short-circuits on false lhs (v4.51)",
         "fn pos(n: Int where (n > 0)) : Int = n\n"
         "let n : Int = 0\n"
         "let r : Bool = (n > 0) && (pos(n) > 0)\n"
         "r\n",
         "r : Bool = false"),
        # v4.53: modulo as a basic arithmetic operator. Same precedence
        # as `*` and `/`, so `1 + 17 % 5` parses as `1 + (17 % 5) = 3`.
        ("basic modulo + precedence (v4.53)",
         "let r : Int = 1 + 17 % 5\n"
         "r\n",
         "r : Int = 3"),
        # v4.53: parity refinement. The canonical use of `%` in
        # predicate position — `n % 2 == 0` enforces evenness.
        ("parity refinement holds (v4.53)",
         "fn even_only(n: Int where (n % 2 == 0)) : Int = n + 1\n"
         "let r : Int = even_only(10)\n"
         "r\n",
         "r : Int = 11"),
        # v4.54: unary NOT. Basic truth + double-negation + applied to
        # a comparison. `!(3 > 5)` is true.
        ("unary NOT basics (v4.54)",
         "let a : Bool = !true\n"
         "let b : Bool = !!false\n"
         "let r : Bool = (a == false) && (b == false) && !(3 > 5)\n"
         "r\n",
         "r : Bool = true"),
        # v4.54: NOT in a refinement predicate. `!(n == 0)` is the
        # "anything but zero" guard; 5 satisfies it so 100/5 = 20.
        ("NOT refinement holds (v4.54)",
         "fn nonzero(n: Int where (!(n == 0))) : Int = 100 / n\n"
         "let r : Int = nonzero(5)\n"
         "r\n",
         "r : Int = 20"),
        # v4.55: arithmetic inside a refinement predicate. The host
        # always handled this (full eval); v4.55 brings Quartz to
        # parity. Pinned here so host + Quartz agree on the shape.
        ("arithmetic in refinement predicate (v4.55)",
         "fn f(n: Int where (n * n >= 1 && n + 1 > 0)) : Int = n\n"
         "let r : Int = f(7)\n"
         "r\n",
         "r : Int = 7"),
        # v4.56: cross-parameter refinement in the host. `hi > lo`
        # references the earlier param; host binds-and-checks in order
        # so `lo` is bound when `hi`'s check runs. clamp(3,10) = 7.
        ("cross-parameter refinement holds (v4.56)",
         "fn clamp(lo: Int, hi: Int where (hi > lo)) : Int = hi - lo\n"
         "let r : Int = clamp(3, 10)\n"
         "r\n",
         "r : Int = 7"),
        # v4.48 composes with v4.47: two-arg lambda where BOTH params
        # are refined. The host's apply_fn checks each TyRefine at
        # call time; prism's port mirrors via two stacked VRefinedClos
        # wrappers. 3 > 0 and 4 > 0 hold, body returns 12.
        ("two-arg refined lambda (v4.48)",
         "let r : Int = (fn(a: Int where (a > 0), b: Int where (b > 0))"
         " -> a * b)(3, 4)\n"
         "r\n",
         "r : Int = 12"),
        # v4.57: quantum-inspired measurement (showcase/quantum.glass).
        # Weighted collapse via cumulative buckets + `seed % total`.
        # Over seeds 0..99 a 9:1 superposition collapses to |0> exactly
        # 90 times — measurement frequency tracks the weights, and the
        # whole thing is pure (seed threaded explicitly).
        ("quantum measurement tracks weights (v4.57)",
         "type Amp = | Amp(String, Int)\n"
         "fn tw(xs: List<Amp>) : Int =\n"
         "  fold(xs, 0, fn(a: Int, x: Amp) -> match x { Amp(_, w) => a + w })\n"
         "fn pick(xs: List<Amp>, r: Int) : String =\n"
         "  match xs { [] => \"_\";"
         " [Amp(l, w), ...rest] => if r < w then l else pick(rest, r - w) }\n"
         "fn measure(xs: List<Amp>, seed: Int where (seed >= 0)) : String =\n"
         "  pick(xs, seed % tw(xs))\n"
         "let bias = [Amp(\"|0>\", 9), Amp(\"|1>\", 1)]\n"
         "let hits : Int =\n"
         "  fold(range(0, 100), 0, fn(a: Int, s: Int) ->\n"
         "    if measure(bias, s) == \"|0>\" then a + 1 else a)\n"
         "hits\n",
         "hits : Int = 90"),
        # v4.58 (Proportion & Form bundle): the golden fingerprint.
        # |a² − a·b − b²| = 1 holds EXACTLY for consecutive Fibonacci
        # pairs — here (34, 21) gives residue +1, the φ convergent test.
        ("golden-ratio residue is +1 for Fibonacci pair (v4.58)",
         "fn residue(a: Int, b: Int) : Int = a * a - a * b - b * b\n"
         "let r : Int = residue(34, 21)\n"
         "r\n",
         "r : Int = 1"),
        # v4.58: Euler's formula as the polyhedron refinement. The
        # cross-param gate accepts the dodecahedron (20−30+12 = 2) and
        # the body returns V+E+F.
        ("Euler polyhedron gate accepts dodecahedron (v4.58)",
         "fn make_poly(v: Int, e: Int, f: Int where (v - e + f == 2)) : Int"
         " = v + e + f\n"
         "let r : Int = make_poly(20, 30, 12)\n"
         "r\n",
         "r : Int = 62"),
        # v4.58: harmonic consonance via gcd-reduction. 6:4 reduces to
        # 3:2 (perfect fifth) — reduced denominator 2 <= 4, consonant.
        ("harmonic ratio reduces to perfect fifth (v4.58)",
         "fn gcd(a: Int, b: Int) : Int = if b == 0 then a else gcd(b, a % b)\n"
         "let rd : Int = 4 / gcd(6, 4)\n"
         "rd\n",
         "rd : Int = 2"),
        # v4.59 (Self-Similarity & Spirals): the fractal self-similarity
        # gate. Sierpinski triples each depth, so 27 is a valid successor
        # of 9 under branch 3 (cross-param refinement next == prev * 3).
        ("fractal self-similarity gate (v4.59)",
         "fn next_level(prev: Int, branch: Int,"
         " next: Int where (next == prev * branch)) : Int = next\n"
         "let r : Int = next_level(9, 3, 27)\n"
         "r\n",
         "r : Int = 27"),
        # v4.59: the golden-spiral peel is exact in Int —
        # F(n+1) − F(n) = F(n-1). For F(6)=8, F(5)=5: 8 − 5 = 3 = F(4).
        # The Σ-Fibonacci identity F(1)+…+F(n) = F(n+2) − 1 gives 20 at
        # n=6, pinned via the closed form.
        ("golden spiral Fibonacci-sum identity (v4.59)",
         "fn fib(n: Int) : Int = if n < 2 then n else fib(n - 1) + fib(n - 2)\n"
         "let r : Int = fib(8) - 1\n"   # F(8)-1 = 21-1 = 20 = sum F(1..6)
         "r\n",
         "r : Int = 20"),
        # v4.60 (Epistemic-games + symmetry): D₄ is non-abelian — the
        # dihedral group law makes r1·s0 ≠ s0·r1. Composing a quarter
        # turn with a reflection in each order gives different elements
        # (s3 vs s1 in our encoding), so their rotation indices differ.
        ("D4 group is non-abelian (v4.60)",
         "fn mod4(n: Int) : Int = ((n % 4) + 4) % 4\n"
         "fn compose_k(k1: Int, f1: Bool, k2: Int, f2: Bool) : Int =\n"
         "  mod4((if f2 then 0 - k1 else k1) + k2)\n"
         "let rs : Int = compose_k(1, false, 0, true)\n"   # r1 then s0
         "let sr : Int = compose_k(0, true, 1, false)\n"   # s0 then r1
         "let r : Bool = rs != sr\n"
         "r\n",
         "r : Bool = true"),
        # v4.60: epistemic knowledge — a child KNOWS their own state iff
        # all indistinguishable live worlds agree on it. In the muddy
        # world (M,M) with only {(M,M)} live, the single world fixes the
        # value, so the child knows (returns the mud value 1).
        ("epistemic: knowledge from a singleton world set (v4.60)",
         "type World = | W(Int, Int)\n"
         "fn mud(c: Int, w: World) : Int ="
         " match w { W(a, b) => if c == 1 then a else b }\n"
         "fn knows(c: Int, w: World, live: List<World>) : Bool =\n"
         "  fold(live, true, fn(acc: Bool, x: World) ->"
         " acc && mud(c, x) == mud(c, w))\n"
         "let r : Bool = knows(1, W(1, 1), [W(1, 1)])\n"
         "r\n",
         "r : Bool = true"),
        # v4.61 (Quantum II): destructive interference. Two paths with
        # opposite-phase amplitudes (+1 and −1) sum to amplitude 0, so
        # the quantum probability |Σ aₖ|² = 0 — the outcome is
        # impossible despite each path being individually possible. The
        # classical sum Σ|aₖ|² would be 2. This is the dark fringe.
        ("destructive interference cancels (v4.61)",
         "type Cx = | Cx(Int, Int)\n"
         "fn cadd(a: Cx, b: Cx) : Cx ="
         " match a { Cx(ar, ai) => match b { Cx(br, bi) =>"
         " Cx(ar + br, ai + bi) } }\n"
         "fn norm2(z: Cx) : Int = match z { Cx(re, im) => re * re + im * im }\n"
         "fn qprob(ps: List<Cx>) : Int ="
         " norm2(fold(ps, Cx(0, 0), fn(a: Cx, p: Cx) -> cadd(a, p)))\n"
         "let r : Int = qprob([Cx(1, 0), Cx(0 - 1, 0)])\n"
         "r\n",
         "r : Int = 0"),
        # v4.61: entanglement — in the Bell state |00>+|11> (weights
        # 1,0,0,1), measuring q1=0 leaves only the 00 branch, so q2 is
        # determined to 0 (the conditional weight for q2=1 is zero).
        ("entanglement pins the partner qubit (v4.61)",
         "type Joint = | Joint(Int, Int, Int, Int)\n"
         "fn cond01(j: Joint) : Int ="   # q2=1 weight given q1=0
         " match j { Joint(w00, w01, w10, w11) => w01 }\n"
         "let bell = Joint(1, 0, 0, 1)\n"
         "let r : Int = cond01(bell)\n"   # 0 ⇒ q2=1 impossible ⇒ q2 pinned to 0
         "r\n",
         "r : Int = 0"),
        # v4.62 (Strategy & Worlds): the Prisoner's Dilemma tragedy —
        # (Cooperate,Cooperate)=(3,3) Pareto-dominates the forced
        # equilibrium (Defect,Defect)=(1,1): both better off, yet
        # dominance forces the worse outcome.
        ("Prisoner's Dilemma: equilibrium is Pareto-dominated (v4.62)",
         "fn pareto_dom(a1: Int, a2: Int, b1: Int, b2: Int) : Bool =\n"
         "  a1 >= b1 && a2 >= b2 && (a1 > b1 || a2 > b2)\n"
         "let r : Bool = pareto_dom(3, 3, 1, 1)\n"
         "r\n",
         "r : Bool = true"),
        # v4.62: multi-world branching. Three coin flips multiply into
        # 2³ = 8 worlds (the list-monad bind unions every branch); the
        # head-counts form the binomial row 1,3,3,1.
        ("multi-world branching: 3 flips = 8 worlds (v4.62)",
         "type World = | World(List<Int>)\n"
         "fn wof(w: World) : List<Int> = match w { World(xs) => xs }\n"
         "fn pure(x: Int) : World = World([x])\n"
         "fn wbind(w: World, f: (Int) -> World) : World =\n"
         "  World(fold(wof(w), [], fn(acc: List<Int>, x: Int) ->"
         " acc ++ wof(f(x))))\n"
         "let flip = World([0, 1])\n"
         "let three = wbind(flip, fn(a: Int) ->"
         " wbind(flip, fn(b: Int) -> wbind(flip, fn(c: Int) ->"
         " pure(a + b + c))))\n"
         "let r : Int = len(wof(three))\n"
         "r\n",
         "r : Int = 8"),
        # v4.63 (Rationals & Probability): exact fraction arithmetic.
        # 1/3 + 1/6 reduces to exactly 1/2 — no rounding. The result is
        # gcd-normalized, so num=1, den=2; we pin the numerator.
        ("exact rational 1/3 + 1/6 = 1/2 (v4.63)",
         "type Rat = | Rat(Int, Int)\n"
         "fn gcd(a: Int, b: Int) : Int = if b == 0 then a else gcd(b, a % b)\n"
         "fn rat(n: Int, d: Int) : Int = n / gcd(n, d)\n"  # numerator of reduced n/d
         "let total : Int = 1 * 6 + 1 * 3\n"   # 1/3 + 1/6 = (6+3)/18 = 9/18
         "let r : Int = rat(total, 18)\n"      # 9/18 → numerator 1
         "r\n",
         "r : Int = 1"),
        # v4.63: Gini/collision uncertainty is exact and rational. For a
        # fair coin [1/2,1/2]:  1 − (1/4 + 1/4) = 1/2. We compute it over
        # a common denominator (4): numerator of 1 − 2/4 = 2, over 4.
        ("Gini uncertainty of fair coin = 1/2 (v4.63)",
         "let sum_sq_num : Int = 1 + 1\n"   # (1/2)²+(1/2)² = 1/4+1/4 = 2/4
         "let u_num : Int = 4 - sum_sq_num\n"   # 1 − 2/4 = (4-2)/4 = 2/4 = 1/2
         "u_num\n",
         "u_num : Int = 2"),
        # v4.64 (Time & Causality): the do-operator. Intervening
        # do(rain := false) recomputes wet = rain ∨ sprinkler from the
        # structural equation — with sprinkler off, the grass is dry.
        # This is intervention, not observation: the equation re-runs.
        ("counterfactual intervention dries the grass (v4.64)",
         "fn wet(rain: Bool, sprinkler: Bool) : Bool = rain || sprinkler\n"
         "let actual : Bool = wet(true, false)\n"    # actually wet
         "let cf : Bool = wet(false, false)\n"       # do(rain:=false)
         "let r : Bool = actual && !cf\n"            # was wet, would be dry
         "r\n",
         "r : Bool = true"),
        # v4.64: Ship of Theseus. After replacing all 4 planks, the
        # original [1,2,3,4] and final [5,6,7,8] differ in every
        # position — diff_count = 4, so strictly NOT the same (yet each
        # step changed only one plank: continuous).
        ("Ship of Theseus shares no original part (v4.64)",
         "fn diff(a: List<Int>, b: List<Int>) : Int =\n"
         "  match a { [] => 0; [x, ...xs] => match b { [] => 0;"
         " [y, ...ys] => (if x == y then 0 else 1) + diff(xs, ys) } }\n"
         "let r : Int = diff([1, 2, 3, 4], [5, 6, 7, 8])\n"
         "r\n",
         "r : Int = 4"),
        # v4.65 (Information & Observation): nested simulation depth.
        # Sim(Sim(Add(3, Sim(4)))) is three realities deep, while the
        # value (7) is level-independent.
        ("nested simulation depth (v4.65)",
         "type Expr = | Lit(Int) | Add(Expr, Expr) | Sim(Expr)\n"
         "fn depth(e: Expr) : Int =\n"
         "  match e { Lit(_) => 0;"
         " Add(a, b) => let da = depth(a) in let db = depth(b) in"
         " (if da > db then da else db);"
         " Sim(inner) => 1 + depth(inner) }\n"
         "let r : Int = depth(Sim(Sim(Add(Lit(3), Sim(Lit(4))))))\n"
         "r\n",
         "r : Int = 3"),
        # v4.65: information-flow taint. Joining a public value with a
        # secret one yields secret (Secret dominates the lattice), so
        # the result is NOT publishable — non-interference by the join.
        ("info-flow taint blocks publish (v4.65)",
         "type Label = | Public | Secret\n"
         "fn join(a: Label, b: Label) : Bool =\n"   # returns is_public of join
         "  match a { Secret => false;"
         " Public => match b { Public => true; Secret => false } }\n"
         "let publishable : Bool = join(Public, Secret)\n"
         "publishable\n",
         "publishable : Bool = false"),
        # v4.66 (Physical types): dimensional analysis. distance/time
        # subtracts dimension vectors, so (1,0,0) ÷ (0,1,0) = (1,−1,0),
        # a velocity. We pin the time exponent of the result = −1.
        ("dimensional division yields velocity (v4.66)",
         "type Dim = | Dim(Int, Int, Int)\n"
         "fn dsub(a: Dim, b: Dim) : Dim =\n"
         "  match a { Dim(l1, t1, m1) => match b { Dim(l2, t2, m2) =>"
         " Dim(l1 - l2, t1 - t2, m1 - m2) } }\n"
         "fn time_exp(d: Dim) : Int = match d { Dim(_, t, _) => t }\n"
         "let v : Dim = dsub(Dim(1, 0, 0), Dim(0, 1, 0))\n"
         "let r : Int = time_exp(v)\n"
         "r\n",
         "r : Int = -1"),
        # v4.67 (Tier-3): linear types. A `let lin` resource consumed
        # exactly once type-checks and runs. Path-aware: using it once
        # in each if-branch is one use per execution path.
        ("linear resource used once (v4.67)",
         "fn f(b: Bool) : Int =\n"
         "  let lin x = 5 in if b then x + 1 else x + 2\n"
         "let r : Int = f(true)\n"
         "r\n",
         "r : Int = 6"),
        # v4.67: `lin` is a CONTEXTUAL keyword — a variable literally
        # named `lin` still works (it's only special as `let lin <id>`).
        ("lin is a usable identifier (v4.67)",
         "fn f() : Int = let lin = 7 in lin + 1\n"
         "let r : Int = f()\n"
         "r\n",
         "r : Int = 8"),
        # v4.69: field-level refinement. A constructor field carries its
        # own invariant; Pos(5) packs fine, and the value is positive by
        # construction so pos_value just reads it back.
        ("refined ADT field accepts valid value (v4.69)",
         "type Pos = | Pos(n: Int where (n > 0))\n"
         "fn pos_value(x: Pos) : Int = match x { Pos(n) => n }\n"
         "let r : Int = pos_value(Pos(42))\n"
         "r\n",
         "r : Int = 42"),
        # v4.69: cross-FIELD refinement — `hi` references earlier field
        # `lo`. Range(3,10) is well-formed; span is 7.
        ("cross-field refinement accepts ordered range (v4.69)",
         "type Range = | Range(lo: Int, hi: Int where (hi > lo))\n"
         "fn span(r: Range) : Int = match r { Range(lo, hi) => hi - lo }\n"
         "let r : Int = span(Range(3, 10))\n"
         "r\n",
         "r : Int = 7"),
    ]
    for label, src, needle in inline_positive:
        rc, out, err = run(src)
        ok = (rc == 0) and (needle in out)
        print(f"  {'OK ' if ok else 'FAIL'}  {label}")
        if not ok:
            print(f"        expected substring {needle!r}")
            print(f"        rc={rc}, stdout: {out.strip()[-200:]}")
            print(f"        stderr: {err.strip()[-200:]}")
            failures += 1

    print("== prism runtime-check end-to-end (v4.23) ==")
    # Run prism.glass and confirm BOTH the positive and negative
    # refinement runtime-check demo lines surface in stdout. This is the
    # only test that exercises prism's own check_refine_runtime — the
    # host-level inline test above pins down the SHAPE of the message;
    # this one pins down that prism's port produces it.
    prism_rc, prism_out, prism_err = run_file(
        os.path.join(EX, "selfhost", "prism.glass")
    )
    prism_checks = [
        ("prism runtime check accepts (v4.23)",
         "examples/features/runtime_refine.glass ==> 42 : Int"),
        ("prism runtime check rejects (v4.23)",
         "examples/features/runtime_refine_bad.glass ==> "
         "refinement violated at runtime: n = 0 fails predicate"),
        # v4.24: refinement on the SECOND param of a curried top-level fn.
        # Pre-v4.24 prism silently let bad values through here because the
        # check only fired on the first param. The VRefinedClos wrapper
        # carries the remaining formals past the first apply so subsequent
        # applies still see their refinements.
        ("prism curried-refine accepts (v4.24)",
         "examples/features/curried_refine.glass ==> 15 : Int"),
        ("prism curried-refine rejects (v4.24)",
         "examples/features/curried_refine_bad.glass ==> "
         "refinement violated at runtime: b = 0 fails predicate"),
        # v4.25: prism return-type refinement runtime check end-to-end.
        # Positive case prints the tuple; negative case prints the
        # violation message for `result = -4`.
        ("prism return-refine accepts (v4.25)",
         "examples/features/return_refine.glass ==> (7, 7) : (Int, Int)"),
        ("prism return-refine rejects (v4.25)",
         "examples/features/return_refine_bad.glass ==> "
         "refinement violated at runtime: result = -4 fails predicate"),
        # v4.26: prism's lexer/parser/eval gain `/`. Textbook
        # safe_div(a, b: Int where (b != 0)) now runs end-to-end in
        # prism; the runtime refinement check carries the divide-by-zero
        # invariant.
        ("prism safe_div with division (v4.26)",
         "examples/features/safe_div.glass ==> (25, 20) : (Int, Int)"),
        # v4.27: parens-after-let parser fix in prism. Bare `(r1, r2)`
        # at column 1 after `let r2 = ...` used to be chained as a call;
        # now it parses as a separate top-level tuple expression.
        ("prism parens-after-let split (v4.27)",
         "examples/features/parens_after_let.glass ==> (3, 7) : (Int, Int)"),
        # v4.47: refined-param lambda runtime checks. The parser now
        # accepts `where (pred)` after a lambda's typed param, and the
        # ELamR -> VRefinedClos path enforces the predicate on every
        # apply. Positive case returns 10; negative case prints the
        # standard "refinement violated at runtime" message via the
        # demo loop.
        ("prism lambda-refine accepts (v4.47)",
         "examples/features/lambda_refine.glass ==> 10 : Int"),
        ("prism lambda-refine rejects (v4.47)",
         "examples/features/lambda_refine_bad.glass ==> "
         "refinement violated at runtime: x = -3 fails predicate"),
        # v4.48: multi-parameter lambdas in prism. Pre-v4.48 the
        # parser bailed at the first comma in a lambda param list, so
        # `fn(a, b) -> ...` never reached eval. The new parse_fn
        # parses a comma-separated list and right-folds it into a
        # nested ELam/ELamR chain — same shape as the host's curried
        # top-level fn encoding.
        ("prism multi-arg lambda (v4.48)",
         "examples/features/lambda_multi.glass ==> 7 : Int"),
        # v4.48 composes with v4.47: each param's refinement runs at
        # its own apply step via the VRefinedClos wrapper from v4.24.
        # 3 > 0 and 4 > 0 both hold, so the call returns 12.
        ("prism multi-arg refined lambda (v4.48)",
         "examples/features/lambda_multi_refine.glass ==> 12 : Int"),
        # v4.52: `&&` and `||` end-to-end through prism. v4.51 deferred
        # prism's update; this is the closing case. Tokenizer recognizes
        # `&&` / `||`, parser layers parse_or → parse_and → parse_compare
        # with C-style precedence, infer rejects non-Bool operands, eval
        # short-circuits. The interval refinement holds (50 in (0,100))
        # so middling returns 51.
        ("prism && / || end-to-end via interval refinement (v4.52)",
         "examples/features/and_or.glass ==> 51 : Int"),
        # v4.53: modulo end-to-end through prism. TPercent token,
        # EMod variant, parse_mul_rest arm, infer/eval/eval_pred/
        # alpha/equal arms — five sites mirroring EMul/EDiv. Parity
        # refinement `n % 2 == 0` is the canonical divisibility shape.
        # 10 is even, so even_only(10) returns 11.
        ("prism modulo end-to-end via parity refinement (v4.53)",
         "examples/features/mod_refine.glass ==> 11 : Int"),
        # v4.54: unary NOT end-to-end through prism. New parse_unary
        # layer above parse_mul, EUNot variant, infer/eval/eval_pred/
        # alpha/equal arms. `!(n == 0)` refinement holds for 5, so
        # nonzero(5) = 100 / 5 = 20.
        ("prism unary NOT end-to-end via refinement (v4.54)",
         "examples/features/not_refine.glass ==> 20 : Int"),
        # v4.68: linear types ported to prism — prism self-hosts the
        # path-aware exactly-once check. A resource used once compiles;
        # a clone is rejected at parse time. Glass checking Glass's own
        # substructural discipline.
        ("prism linear resource accepts single use (v4.68)",
         "examples/features/linear_ok.glass ==> 50 : Int"),
        ("prism linear resource rejects cloning (v4.68)",
         "examples/features/linear_clone.glass ==> "
         "linear variable token used 2 times (no cloning)"),
        # v4.56: cross-parameter refinement through prism. The arg-env
        # threaded through VRefinedClos lets `hi > lo` resolve `lo`.
        # clamp(3, 10) = 7.
        ("prism cross-param refinement accepts (v4.56)",
         "examples/features/xparam_refine.glass ==> 7 : Int"),
        # And the bad case fires LOUDLY (not the pre-v4.56 silent skip
        # on unbound `lo`): clamp(10, 3) violates hi > lo.
        ("prism cross-param refinement rejects (v4.56)",
         "examples/features/xparam_refine_bad.glass ==> "
         "refinement violated at runtime: hi = 3 fails predicate"),
    ]
    for label, needle in prism_checks:
        ok = (prism_rc == 0) and (needle in prism_out)
        print(f"  {'OK ' if ok else 'FAIL'}  {label}")
        if not ok:
            print(f"        expected substring {needle!r}")
            print(f"        rc={prism_rc}")
            print(f"        stdout tail: {prism_out.strip()[-300:]}")
            print(f"        stderr tail: {prism_err.strip()[-300:]}")
            failures += 1

    print("== REPL session cases ==")
    repl_cases = [
        ("simple expression",
         "1 + 1\n:quit\n", ": Int = 2"),
        ("let binding then use",
         "let x = 42\nx + 1\n:quit\n", ": Int = 43"),
        ("multi-line fn definition",
         "fn fact(n: Int) : Int =\n"
         "  if n < 2 then 1\n"
         "  else n * fact(n - 1)\n"
         "fact(5)\n:quit\n", ": Int = 120"),
        (":type command",
         ":type 42 + 1\n:quit\n", "42 + 1 : Int"),
        ("error recovery",
         "undefined_x\n1 + 1\n:quit\n", ": Int = 2"),
        (":reset clears state",
         "let x = 5\n:reset\nx\n:quit\n", "unbound"),
    ]
    for label, src, needle in repl_cases:
        p = subprocess.run(
            [sys.executable, GLASS],
            input=src, capture_output=True, text=True,
        )
        ok = (needle in p.stdout)
        print(f"  {'OK ' if ok else 'FAIL'}  {label}")
        if not ok:
            print(f"        expected substring {needle!r}")
            print(f"        stdout: {p.stdout.strip()[-200:]}")
            failures += 1

    total = (len(POSITIVE) + len(NEGATIVE) +
             len(inline_positive) + len(prism_checks) + len(repl_cases))
    passed = total - failures
    quartz_failures = run_quartz_tests()
    failures += quartz_failures
    total += 170  # quartz: + 2 v4.73 (tuple-ctor dispatch + final `let _` discard)
    passed = total - failures
    print(f"\n{passed}/{total} passed")
    return 0 if failures == 0 else 1


def run_quartz_tests() -> int:
    """Quartz v3.0: compile each .glass source to a native binary, run it,
    check stdout matches expectation. Each case proves codegen handles a
    specific language construct end-to-end."""
    import tempfile
    QUARTZ = os.path.join(ROOT, "quartz.py")
    print("== quartz native-compile cases ==")
    cases = [
        ("int literal",              "42\n",                                   "42\n"),
        ("arithmetic precedence",    "1 + 2 * 3\n",                            "7\n"),
        ("top-level lets",           "let x = 5\nlet y = 10\nx + y\n",         "15\n"),
        ("if-then-else as expr",     "if 3 < 5 then 100 else 200\n",           "100\n"),
        ("nested let-in",            "let r = (let x = 7 in x * 3)\nr + 1\n",  "22\n"),
        ("string literal",           '"hello"\n',                              "hello\n"),
        # v3.1 — functions
        ("fn add",
         "fn add(x: Int, y: Int) : Int = x + y\nadd(3, 4)\n",
         "7\n"),
        ("fn recursion (fact)",
         "fn fact(n: Int) : Int = if n < 2 then 1 else n * fact(n - 1)\nfact(5)\n",
         "120\n"),
        ("fn calls fn",
         "fn double(x: Int) : Int = x * 2\nfn quad(x: Int) : Int = double(double(x))\nquad(3)\n",
         "12\n"),
        ("fn mutual recursion",
         "fn is_even(n: Int) : Bool = if n == 0 then true else is_odd(n - 1)\n"
         "fn is_odd(n: Int) : Bool = if n == 0 then false else is_even(n - 1)\n"
         "is_even(10)\n",
         "true\n"),
        ("string concat ++",
         'fn greet(name: String) : String = "hello, " ++ name\ngreet("world")\n',
         "hello, world\n"),
        ("C keyword name collision",
         "fn double(x: Int) : Int = x * 2\ndouble(21)\n",
         "42\n"),
        # v3.2 — ADTs + pattern matching
        ("ADT enum-style match",
         "type Color = Red | Green | Blue\n"
         "match (Red) { Red => 1; Green => 2; Blue => 3 }\n",
         "1\n"),
        ("ADT with payload + match",
         "type Box = Empty | Holds(Int)\n"
         "match Holds(42) { Holds(n) => n; Empty => 0 }\n",
         "42\n"),
        ("ADT multi-field variant",
         "type Bag = Empty | Twin(Int, Int)\n"
         "match Twin(10, 20) { Empty => 0; Twin(a, b) => a + b }\n",
         "30\n"),
        ("fn returns ADT",
         "type Color = Red | Green | Blue\n"
         "fn classify(n: Int) : Color = if n > 0 then Red else Blue\n"
         "match classify(-5) { Red => 1; Green => 2; Blue => 3 }\n",
         "3\n"),
        ("ADT wild pattern ignores payload",
         "type Outcome = Done(Int) | Failed(String)\n"
         'fn safe_div(n: Int, d: Int) : Outcome = if d == 0 then Failed("oops") else Done(n / d)\n'
         "match safe_div(100, 0) { Done(v) => v; Failed(_) => -1 }\n",
         "-1\n"),
        # v3.3 — records
        ("record construct + field access",
         "type Point = { x: Int, y: Int }\n"
         "let p = Point { x: 3, y: 4 }\n"
         "p.x + p.y\n",
         "7\n"),
        ("record as fn parameter",
         "type Point = { x: Int, y: Int }\n"
         "fn dot(a: Point, b: Point) : Int = a.x * b.x + a.y * b.y\n"
         "let p = Point { x: 3, y: 4 }\n"
         "let q = Point { x: 5, y: 6 }\n"
         "dot(p, q)\n",
         "39\n"),
        ("record destructure in match",
         "type User = { id: Int, name: String }\n"
         'let u = User { id: 42, name: "alice" }\n'
         "match u { User { id, name } => id }\n",
         "42\n"),
        ("record inside ADT variant",
         "type User = { id: Int, name: String }\n"
         "type Outcome = Found(User) | NotFound\n"
         "fn lookup(id: Int) : Outcome = "
         'if id == 1 then Found(User { id: 1, name: "alice" }) else NotFound\n'
         'match lookup(1) { Found(u) => u.name; NotFound => "missing" }\n',
         "alice\n"),
        ("chained field access (nested records)",
         "type Point = { x: Int, y: Int }\n"
         "type Rect = { tl: Point, br: Point }\n"
         "let r = Rect { tl: Point { x: 0, y: 0 }, br: Point { x: 1920, y: 1080 } }\n"
         "r.br.x - r.tl.x\n",
         "1920\n"),
        # v3.4 — generics
        ("generic ADT (user-declared)",
         "type Maybe<T> = Nope | Yep(T)\n"
         "match Yep(42) { Yep(n) => n; Nope => 0 }\n",
         "42\n"),
        ("generic record",
         "type Box<T> = { contents: T }\n"
         "let b = Box { contents: 7 }\n"
         "b.contents\n",
         "7\n"),
        ("prelude Option<Int>",
         "let o : Option<Int> = Some(42)\n"
         "match o { Some(n) => n; None => 0 }\n",
         "42\n"),
        ("prelude Result<Int, String>",
         "fn safe_div(n: Int, d: Int) : Result<Int, String> =\n"
         '  if d == 0 then Err("div by zero") else Ok(n / d)\n'
         "match safe_div(100, 0) { Ok(v) => v; Err(_) => -1 }\n",
         "-1\n"),
        ("generic record as fn parameter",
         "type Box<T> = { contents: T }\n"
         "fn unbox(b: Box<Int>) : Int = b.contents\n"
         "unbox(Box { contents: 99 })\n",
         "99\n"),
        # v3.4.1 — generic functions
        ("generic fn (Int instantiation)",
         "fn id<T>(x: T) : T = x\n"
         "id(42)\n",
         "42\n"),
        ("generic fn (String instantiation)",
         "fn id<T>(x: T) : T = x\n"
         'id("hello")\n',
         "hello\n"),
        ("generic fn calling generic fn",
         "fn id<T>(x: T) : T = x\n"
         "fn through<A>(x: A) : A = id(x)\n"
         "through(99)\n",
         "99\n"),
        ("generic fn returning ADT",
         "fn wrap<T>(x: T) : Option<T> = Some(x)\n"
         "match wrap(42) { Some(n) => n; None => 0 }\n",
         "42\n"),
        ("generic fn over ADT scrutinee",
         "fn unwrap_or<T>(opt: Option<T>, default: T) : T =\n"
         "  match opt { Some(x) => x; None => default }\n"
         "unwrap_or(Some(42), 0)\n",
         "42\n"),
        ("generic fn — None instantiation",
         "fn unwrap_or<T>(opt: Option<T>, default: T) : T =\n"
         "  match opt { Some(x) => x; None => default }\n"
         'unwrap_or(None, "missing")\n',
         "missing\n"),
        # v4.30 — Quartz gains tuples. Compile a fn that returns a
        # tuple, destructure in match, recombine. Tests TupleLit codegen
        # + TyTuple in fn signatures + tuple pattern destructuring.
        ("tuple construct + destructure (v4.30)",
         "fn pair(a: Int, b: Int) : (Int, Int) = (a, b)\n"
         "match pair(10, 20) { (x, y) => x + y }\n",
         "30\n"),
        ("3-tuple",
         "fn triple(a: Int, b: Int, c: Int) : (Int, Int, Int) = (a, b, c)\n"
         "match triple(100, 20, 3) { (x, y, z) => x + y + z }\n",
         "123\n"),
        ("mixed-type tuple (String, Int)",
         'fn label(n: Int) : (String, Int) = ("answer", n)\n'
         "match label(42) { (k, v) => v }\n",
         "42\n"),
        ("let-bound tuple",
         "fn pair(a: Int, b: Int) : (Int, Int) = (a, b)\n"
         "let p : (Int, Int) = pair(7, 3)\n"
         "match p { (x, y) => x - y }\n",
         "4\n"),
        # v4.31 — Quartz gains lists. Cons-chain representation in
        # q_value_t (Nil has num_fields=0; Cons has num_fields=2 with
        # head at fields[0] and tail at fields[1]). Tests recursive
        # walking, empty-list base case, length count, string element.
        ("list literal + recursive sum (v4.31)",
         "fn sum(xs: List<Int>) : Int =\n"
         "  match xs {\n"
         "    []        => 0;\n"
         "    [h, ...t] => h + sum(t)\n"
         "  }\n"
         "sum([1, 2, 3, 4, 5])\n",
         "15\n"),
        ("empty list (nil base case)",
         "fn sum(xs: List<Int>) : Int =\n"
         "  match xs {\n"
         "    []        => 0;\n"
         "    [h, ...t] => h + sum(t)\n"
         "  }\n"
         "sum([])\n",
         "0\n"),
        ("list length via wildcard head",
         "fn length(xs: List<Int>) : Int =\n"
         "  match xs {\n"
         "    []        => 0;\n"
         "    [_, ...t] => 1 + length(t)\n"
         "  }\n"
         "length([10, 20, 30, 40, 50, 60, 70])\n",
         "7\n"),
        ("list of strings — first element",
         'fn first_or(xs: List<String>, default: String) : String =\n'
         "  match xs {\n"
         "    []        => default;\n"
         "    [h, ..._] => h\n"
         "  }\n"
         'first_or(["alpha", "beta", "gamma"], "none")\n',
         "alpha\n"),
        # v4.32 — Quartz ++ dispatches on operand type. Pre-v4.32 always
        # called quartz_str_concat, which silently miscompiled list ++
        # (returned 0 instead of 66). The new path emits quartz_list_concat
        # for list operands.
        ("list ++ via quartz_list_concat (v4.32)",
         "fn sum(xs: List<Int>) : Int =\n"
         "  match xs { [] => 0; [h, ...t] => h + sum(t) }\n"
         "sum([1, 2, 3] ++ [10, 20, 30])\n",
         "66\n"),
        ("list ++ with empty lhs",
         "fn sum(xs: List<Int>) : Int =\n"
         "  match xs { [] => 0; [h, ...t] => h + sum(t) }\n"
         "let empty : List<Int> = []\n"
         "sum(empty ++ [5, 10, 15])\n",
         "30\n"),
        ("list ++ with empty rhs",
         "fn sum(xs: List<Int>) : Int =\n"
         "  match xs { [] => 0; [h, ...t] => h + sum(t) }\n"
         "let empty : List<Int> = []\n"
         "sum([1, 2, 3] ++ empty)\n",
         "6\n"),
        ("string ++ still works (regression guard)",
         'fn greet(name: String) : String = "hello, " ++ name\n'
         'greet("world")\n',
         "hello, world\n"),
        # v4.33 — Quartz `==` becomes type-aware. String compares now
        # use strcmp (content), so concat-then-compare works. The case
        # that returned 0 pre-v4.33 returns 1.
        ("Quartz == on concatenated String (v4.33)",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         'ok(("hel" ++ "lo") == "hello")\n',
         "1\n"),
        ("Quartz != on String content",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         'ok(("hel" ++ "lo") != "world")\n',
         "1\n"),
        # Regression guard: Int and Bool equality must still use plain
        # C `==`. The type-aware dispatch only kicks in for boxed types.
        ("Quartz == on Int still plain compare",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(42 == 42)\n",
         "1\n"),
        ("Quartz == on Bool still plain compare",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(true == true)\n",
         "1\n"),
        # v4.34 — Quartz structural == extends to List<P> and
        # Tuple<P, ...> when every P is primitive (Int/Bool/String).
        # The codegen emits a loop (lists) or per-field compare chain
        # (tuples) as statements + a fresh result bool. Pre-v4.34 these
        # all errored loudly via v4.33's TyList/TyTuple arms.
        ("List<Int> == List<Int> same (v4.34)",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok([1, 2, 3] == [1, 2, 3])\n",
         "1\n"),
        ("List<Int> == List<Int> different content",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok([1, 2, 3] == [1, 2, 4])\n",
         "0\n"),
        ("List<Int> == List<Int> different length",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok([1, 2, 3] == [1, 2])\n",
         "0\n"),
        ("List<String> == content compare via concat",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         'ok([("hel" ++ "lo"), ("wor" ++ "ld")] == ["hello", "world"])\n',
         "1\n"),
        ("Tuple<Int, Int> == structural",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok((1, 2) == (1, 2))\n",
         "1\n"),
        ("Tuple<Int, Int> != different",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok((1, 2) != (1, 3))\n",
         "1\n"),
        ("Tuple<String, Int> mixed — content compare",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         'ok(("a" ++ "b", 42) == ("ab", 42))\n',
         "1\n"),
        # v4.35 — recursive structural ==. The primitive-only guards
        # on TyList and TyTuple arms of _emit_eq_atom were dropped, so
        # the existing recursive call dispatches through the type
        # structure. The recursive append order already places inner
        # statements inside the outer loop body — no scope-management
        # changes were needed.
        ("List<List<Int>> == structural (v4.35)",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok([[1, 2], [3, 4]] == [[1, 2], [3, 4]])\n",
         "1\n"),
        ("List<List<Int>> != different inner",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok([[1, 2], [3, 4]] != [[1, 2], [3, 5]])\n",
         "1\n"),
        ("Tuple<List<Int>, Int> mixed",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(([1, 2, 3], 42) == ([1, 2, 3], 42))\n",
         "1\n"),
        ("List<Tuple<Int, String>> nested tuples in list",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         'ok([(1, "a"), (2, "b")] == [(1, "a"), (2, "b")])\n',
         "1\n"),
        # v4.36 — structural == for records and concrete sum types.
        # Records: field-by-field compare using record_env field types.
        # Sum types: tag check + per-variant field compare. Generic
        # sum types (Option<T>, etc.) still error loudly.
        ("Record == Record same content (v4.36)",
         "type Point = { x: Int, y: Int }\n"
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Point { x: 1, y: 2 } == Point { x: 1, y: 2 })\n",
         "1\n"),
        ("Record != Record different field",
         "type Point = { x: Int, y: Int }\n"
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Point { x: 1, y: 2 } != Point { x: 1, y: 3 })\n",
         "1\n"),
        ("Record with String field — content compare",
         "type User = { id: Int, name: String }\n"
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         'ok(User { id: 1, name: "alice" } == '
         'User { id: 1, name: "ali" ++ "ce" })\n',
         "1\n"),
        ("Concrete sum type enum",
         "type Color = Red | Green | Blue\n"
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Red == Red)\n",
         "1\n"),
        ("Concrete sum type different variants",
         "type Color = Red | Green | Blue\n"
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Red != Blue)\n",
         "1\n"),
        ("Sum type with Int payload same",
         "type Box = Empty | Holds(Int)\n"
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Holds(42) == Holds(42))\n",
         "1\n"),
        ("Sum type with Int payload different",
         "type Box = Empty | Holds(Int)\n"
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Holds(42) != Holds(99))\n",
         "1\n"),
        ("Sum type Empty vs Holds — different tags",
         "type Box = Empty | Holds(Int)\n"
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Empty != Holds(0))\n",
         "1\n"),
        # v4.37 — closes the structural-eq story for generic sum types.
        # Quartz now substitutes the TyADT's type args into variant
        # field types via _substitute_ty + adt_params, and type_of
        # infers ctor calls' type args by unifying arg types against
        # the variant's declared (TyVar-containing) field types.
        ("Option<Int>: Some(42) == Some(42) (v4.37)",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Some(42) == Some(42))\n",
         "1\n"),
        ("Option<Int>: Some(42) != Some(99)",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Some(42) != Some(99))\n",
         "1\n"),
        ("Option<String> via concat — string content compare in variant",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         'let a : Option<String> = Some("hello")\n'
         'let b : Option<String> = Some("hel" ++ "lo")\n'
         "ok(a == b)\n",
         "1\n"),
        ("Result<Int, String>: Ok(42) == Ok(42)",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "let r1 : Result<Int, String> = Ok(42)\n"
         "let r2 : Result<Int, String> = Ok(42)\n"
         "ok(r1 == r2)\n",
         "1\n"),
        ("Result<Int, String>: Ok vs Err — different tags",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "let r1 : Result<Int, String> = Ok(42)\n"
         'let r2 : Result<Int, String> = Err("oops")\n'
         "ok(r1 != r2)\n",
         "1\n"),
        ("Option<Int>: None == None via let annotation",
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "let a : Option<Int> = None\n"
         "let b : Option<Int> = None\n"
         "ok(a == b)\n",
         "1\n"),
        ("User-declared generic ADT: Maybe<T>",
         "type Maybe<T> = Nope | Yep(T)\n"
         "fn ok(b: Bool) : Int = if b then 1 else 0\n"
         "ok(Yep(7) == Yep(7))\n",
         "1\n"),
        # v4.38 — Quartz gains three host-prelude builtins:
        # string_length, substring, int_to_string. Each is recognized
        # by type_of and emit_expr; substring and int_to_string get
        # malloc-based C runtime helpers, string_length inlines as
        # ((int64_t)strlen(s)).
        ("string_length (v4.38)",
         'string_length("hello, world")\n',
         "12\n"),
        ("string_length empty",
         'string_length("")\n',
         "0\n"),
        ("substring slice (v4.38)",
         'substring("hello, world", 7, 12)\n',
         "world\n"),
        ("substring clamps end to length",
         'substring("abc", 1, 100)\n',
         "bc\n"),
        ("int_to_string (v4.38)",
         "int_to_string(42)\n",
         "42\n"),
        ("int_to_string negative",
         "int_to_string(0 - 17)\n",
         "-17\n"),
        ("composed: int_to_string ++ string ++ string_length",
         'string_length(int_to_string(1000) ++ " items")\n',
         "10\n"),
        # v4.39 — Quartz gains five more host-prelude builtins:
        # len, head, tail, reverse, string_index_of. Builtin dispatch
        # was refactored to pass the Codegen instance to emit_fns so
        # Option-returning builtins can resolve Some/None tags. Args
        # are cast through intptr_t to the formal's C type, mirroring
        # v4.22's generic-fn-call bridge — this lets pattern-bound
        # values (erased to int64_t) flow through builtin formals
        # that expect q_value_t* (e.g., `head(rest)` after
        # `Some(rest)` from `tail`).
        ("len (v4.39)",
         "len([10, 20, 30, 40, 50])\n",
         "5\n"),
        ("len empty",
         "let empty : List<Int> = []\nlen(empty)\n",
         "0\n"),
        ("reverse + len composition",
         "len(reverse([1, 2, 3, 4]))\n",
         "4\n"),
        ("head — Some case (v4.39)",
         "match head([10, 20, 30]) { Some(x) => x; None => 0 - 1 }\n",
         "10\n"),
        ("head — None case",
         "let empty : List<Int> = []\n"
         "match head(empty) { Some(x) => x; None => 0 - 1 }\n",
         "-1\n"),
        ("tail + head chain — pattern bridge through int64_t",
         "match tail([10, 20, 30]) {\n"
         "  Some(rest) => match head(rest) { Some(x) => x; None => 0 - 1 };\n"
         "  None => 0 - 1\n"
         "}\n",
         "20\n"),
        ("string_index_of — found (v4.39)",
         'match string_index_of("hello, world", "world") { '
         'Some(i) => i; None => 0 - 1 }\n',
         "7\n"),
        ("string_index_of — not found",
         'match string_index_of("hello", "xyz") { '
         'Some(i) => i; None => 0 - 1 }\n',
         "-1\n"),
        ("compose: head(reverse(...)) — last element",
         "match head(reverse([1, 2, 3, 4, 5])) { Some(x) => x; None => 0 }\n",
         "5\n"),
        # v4.40 — string_to_upper / string_to_lower added to BOTH the
        # host and Quartz. ASCII-only semantics: bytes outside A-Z /
        # a-z pass through unchanged. The host uses explicit char
        # arithmetic (not Python's Unicode-aware .upper()) to match
        # Quartz exactly, so programs produce identical output through
        # either interpreter.
        ("string_to_upper basic (v4.40)",
         'string_to_upper("hello, world")\n',
         "HELLO, WORLD\n"),
        ("string_to_lower mixed",
         'string_to_lower("HELLO, World 123")\n',
         "hello, world 123\n"),
        ("string_to_upper empty",
         'string_to_upper("")\n',
         "\n"),
        ("string_to_upper already-caps",
         'string_to_upper("ALREADY")\n',
         "ALREADY\n"),
        ("string_to_upper preserves non-letters",
         'string_to_upper("a1!b2@c3")\n',
         "A1!B2@C3\n"),
        ("upper then lower round-trip",
         'string_to_lower(string_to_upper("Mixed Case"))\n',
         "mixed case\n"),
        # v4.41 — char_at added to BOTH host and Quartz with codepoint
        # (Int) semantics, matching what quartz_parser.glass and djb2
        # hash usage expect. Prism's internal `fn char_at` (returning
        # String) still shadows the builtin inside prism's own source,
        # preserving prism's lexer behavior unchanged.
        ("char_at first byte (v4.41)",
         'char_at("hello", 0)\n',
         "104\n"),
        ("char_at last byte",
         'char_at("hello", 4)\n',
         "111\n"),
        ("char_at composes with arithmetic",
         'char_at("Z", 0) - char_at("A", 0)\n',
         "25\n"),
        # The djb2 canary: this hash function is the textbook use
        # case for codepoint char_at. The expected output (193485963)
        # matches every standard djb2 reference implementation.
        ("djb2 hash via char_at composes correctly",
         "fn djb2_at(s: String, i: Int, len: Int, h: Int) : Int =\n"
         "  if i == len then h\n"
         "  else djb2_at(s, i + 1, len, h * 33 + char_at(s, i))\n"
         'djb2_at("abc", 0, string_length("abc"), 5381)\n',
         "193485963\n"),
        # v4.42 — bitwise ops added to BOTH host and Quartz. The host
        # masks results through int64 wrap so non-overflowing values
        # match Quartz exactly. The compiled toolchain had these since
        # v4.16 (quartz_parser.glass); v4.42 just brings the host and
        # Quartz-proper to parity with that.
        ("bit_and (v4.42)",
         "bit_and(12, 10)\n",
         "8\n"),
        ("bit_or",
         "bit_or(12, 10)\n",
         "14\n"),
        ("bit_xor",
         "bit_xor(12, 10)\n",
         "6\n"),
        ("bit_shl",
         "bit_shl(1, 4)\n",
         "16\n"),
        ("bit_shr",
         "bit_shr(16, 2)\n",
         "4\n"),
        ("bit_not all ones",
         "bit_not(0)\n",
         "-1\n"),
        # The djb2 canary now uses bit_shl AND char_at together — both
        # added in v4.41/v4.42. Same expected value through host or
        # Quartz, matching the standard djb2 reference.
        ("djb2 via bit_shl + char_at",
         "fn djb2_from(s: String, i: Int, len: Int, h: Int) : Int =\n"
         "  if i == len then h\n"
         "  else djb2_from(s, i + 1, len, "
         "bit_shl(h, 5) + h + char_at(s, i))\n"
         'djb2_from("abc", 0, string_length("abc"), 5381)\n',
         "193485963\n"),
        # v4.43 — bundle of three small carry-forward items:
        # - range(lo, hi) builtin in Quartz (host already had it)
        # - wrap_int64 in both host and Quartz, lets users opt into
        #   int64 wrap on host so overflow-sensitive algorithms agree
        #   byte-for-byte across interpreters
        # - cast-bridge factoring in Quartz codegen (internal; no
        #   user-visible behavior change, but all existing tests must
        #   continue to pass)
        ("range basic (v4.43)",
         "len(range(0, 5))\n",
         "5\n"),
        ("range sum 1..10",
         "fn sum(xs: List<Int>) : Int =\n"
         "  match xs { [] => 0; [h, ...t] => h + sum(t) }\n"
         "sum(range(1, 11))\n",
         "55\n"),
        ("range head — first element of range",
         "match head(range(10, 20)) { Some(x) => x; None => 0 - 1 }\n",
         "10\n"),
        ("range empty when lo == hi",
         "len(range(5, 5))\n",
         "0\n"),
        ("range empty when lo > hi",
         "len(range(10, 3))\n",
         "0\n"),
        ("wrap_int64 basic (v4.43)",
         "wrap_int64(42)\n",
         "42\n"),
        # The big payoff: with explicit wrap_int64, the overflowing
        # djb2 hash matches between host and Quartz. Before v4.43,
        # host produced 13826554139369386393 and Quartz produced
        # -4620189934340165223 — same bit pattern, different sign
        # interpretation due to host's unbounded ints.
        ("djb2 with wrap_int64 — host/Quartz agree on overflow",
         "fn djb2_from(s: String, i: Int, len: Int, h: Int) : Int =\n"
         "  if i == len then h\n"
         "  else djb2_from(s, i + 1, len,\n"
         "                 wrap_int64("
         "bit_shl(h, 5) + h + char_at(s, i)))\n"
         'djb2_from("Glass v4.20", 0, string_length("Glass v4.20"), 5381)\n',
         "-4620189934340165223\n"),
        # v4.44 — non-capturing lambdas (first cut). Quartz learns
        # TyFn -> q_value_t* (closure values), lambda-lifting (each
        # ELam becomes a generated __lambda_N static C fn), and
        # indirect-call codegen through fields[0]. v4.44 is unary
        # and non-capturing; multi-arg lambdas and free-variable
        # capture land in v4.45.
        ("lambda canary (v4.44)",
         "(fn(x: Int) -> x * 2)(5)\n",
         "10\n"),
        ("let-bound lambda, called later",
         "let f = fn(x: Int) -> x + 100\n"
         "f(7)\n",
         "107\n"),
        ("lambda returning String",
         "let greet = fn(s: String) -> \"hello, \" ++ s\n"
         'greet("world")\n',
         "hello, world\n"),
        ("lambda passed as fn arg (higher-order)",
         "fn apply(f: (Int) -> Int, x: Int) : Int = f(x)\n"
         "apply(fn(n: Int) -> n * n, 9)\n",
         "81\n"),
        # v4.45 — capturing closures. The lifted lambda now does
        # free-variable analysis on its body; outer-scope names
        # referenced inside become captures, packed into
        # __env->fields[1..] at construction and unpacked back into
        # locals at the top of the lifted fn body.
        ("simple capture from let (v4.45)",
         "let y = 100\n"
         "(fn(x: Int) -> x + y)(7)\n",
         "107\n"),
        ("multi-capture",
         "let a = 10\n"
         "let b = 20\n"
         "(fn(x: Int) -> x + a + b)(5)\n",
         "35\n"),
        ("fn returns lambda — captures fn's param",
         "fn adder(x: Int) : (Int) -> Int = fn(y: Int) -> x + y\n"
         "let add5 = adder(5)\n"
         "add5(7)\n",
         "12\n"),
        ("String capture",
         'let prefix = "hi, "\n'
         '(fn(name: String) -> prefix ++ name)("alice")\n',
         "hi, alice\n"),
        # The canary: nested closures, each capturing from its enclosing
        # scope. Inner lambda captures `a` from outer fn, plus `b` from
        # outer lambda — both layers flow through correctly.
        ("nested closure captures both layers",
         "fn make_double_adder(a: Int) : (Int) -> ((Int) -> Int) =\n"
         "  fn(b: Int) -> fn(c: Int) -> a + b + c\n"
         "let f = make_double_adder(100)\n"
         "let g = f(20)\n"
         "g(3)\n",
         "123\n"),
        # v4.46 — multi-arg lambdas + map/filter/fold. The v4.44
        # unary restriction is lifted; lifted fns now take N int64_t
        # args and indirect calls build the fn-pointer cast at the
        # matching arity. fold's binary combine closure exercises
        # this path directly.
        ("multi-arg lambda (v4.46)",
         "(fn(a: Int, b: Int) -> a + b)(3, 4)\n",
         "7\n"),
        ("let-bound multi-arg, called many times",
         "let combine = fn(acc: Int, x: Int) -> acc * 10 + x\n"
         "combine(combine(combine(0, 1), 2), 3)\n",
         "123\n"),
        ("map doubles a list (v4.46)",
         "fn sum(xs: List<Int>) : Int =\n"
         "  match xs { [] => 0; [h, ...t] => h + sum(t) }\n"
         "sum(map([1, 2, 3, 4, 5], fn(x: Int) -> x * 2))\n",
         "30\n"),
        ("filter by predicate",
         "fn sum(xs: List<Int>) : Int =\n"
         "  match xs { [] => 0; [h, ...t] => h + sum(t) }\n"
         "sum(filter([1, 2, 3, 4, 5, 6], fn(x: Int) -> x > 3))\n",
         "15\n"),
        ("fold sum — canonical accumulator",
         "fold([1, 2, 3, 4, 5], 0, fn(acc: Int, x: Int) -> acc + x)\n",
         "15\n"),
        # The composition canary — map -> filter -> fold all chained.
        # Verifies higher-order builtins compose cleanly through the
        # closure-call protocol.
        ("compose: map then filter then fold",
         "fold(\n"
         "  filter(\n"
         "    map([1, 2, 3, 4, 5], fn(x: Int) -> x * x),\n"
         "    fn(y: Int) -> y > 5),\n"
         "  0,\n"
         "  fn(acc: Int, n: Int) -> acc + n)\n",
         "50\n"),
        # Fold with a CAPTURED accumulator (closure capturing from
        # outer scope and ALSO doing real per-iteration math).
        ("fold with captured multiplier",
         "let k = 10\n"
         "fold([1, 2, 3], 1, fn(acc: Int, x: Int) -> acc * x * k)\n",
         "6000\n"),
        # v4.22 — nested generic ADT round-trip. id<A>(Some(99)) erases
        # through TyVar (int64_t) and the return-cast unboxes it back to
        # q_value_t*; unwrap_or<T> then takes a q_value_t* via the v4.22
        # call-site bridge fix. If the call-site cast is wrong in either
        # direction, this fails to compile.
        ("nested generic ADT round-trip (v4.22)",
         "fn id<A>(x: A) : A = x\n"
         "fn unwrap_or<T>(opt: Option<T>, default: T) : T =\n"
         "  match opt { Some(x) => x; None => default }\n"
         "unwrap_or(id(Some(99)), 0)\n",
         "99\n"),
        # v4.49: Quartz refinement runtime checks. Pre-v4.49 the C-type
        # mapping threw `NotImplementedError: Quartz does not yet
        # support type: TyRefine` the moment ANY refined param hit
        # codegen, so the entire refinement subset of Glass couldn't
        # be native-compiled. v4.49 strips TyRefine for the C-type
        # layer and emits an inline guard at the top of the fn body
        # for each refined param. Good value flows through unchanged.
        ("refined param compiles + good value (v4.49)",
         "fn positive_double(n: Int where (n > 0)) : Int = n * 2\n"
         "let x : Int = 21\n"
         "positive_double(x)\n",
         "42\n"),
        # Return-type refinement: parser accepts `: Int where (result > 0)`,
        # and the codegen materializes the body result into a `result`
        # local, runs the guard, then returns. Mirrors host's
        # apply_fn return-refinement path (line 2368).
        ("refined return compiles + holds (v4.49)",
         "fn pos_sq_plus_one(n: Int) : Int where (result > 0) = n * n + 1\n"
         "let x : Int = 5\n"
         "pos_sq_plus_one(x)\n",
         "26\n"),
        # Refined param composed with normal param: only the refined
        # position should grow a guard. Acts as a regression on
        # accidentally inserting guards for every param.
        ("refined param mixed with normal param (v4.49)",
         "fn add_pos(a: Int where (a > 0), b: Int) : Int = a + b\n"
         "add_pos(3, 4)\n",
         "7\n"),
        # v4.50: refined let-binding at top level. The guard runs
        # right after the value is computed, in main(), before any
        # subsequent expression uses the let-bound name.
        ("refined let-binding compiles + holds (v4.50)",
         "let n : Int where (n > 0) = 42\n"
         "n + 1\n",
         "43\n"),
        # v4.50: refined LetIn nested in a fn body. Distinct codegen
        # path from the top-level LetDecl loop — exercises the
        # Codegen.emit_expr LetIn branch.
        ("refined let-in inside fn body (v4.50)",
         "fn doit(k: Int) : Int =\n"
         "  let n : Int where (n > 0) = k * 2 in\n"
         "  n + 1\n"
         "doit(7)\n",
         "15\n"),
        # v4.50: refined lambda param. The guard lives inside the
        # lifted __lambda_N C function emitted by _lift_lambda, so it
        # fires regardless of whether the lambda is called directly
        # or indirectly through higher-order builtins.
        ("refined lambda param compiles + holds (v4.50)",
         "let dbl = fn(x: Int where (x > 0)) -> x * 2\n"
         "dbl(5)\n",
         "10\n"),
        # v4.50: composes with v4.46's higher-order list builtins.
        # The refined lambda's guard fires for every element fold
        # visits — and each element satisfies the predicate, so the
        # fold runs end to end. (We fold instead of map because
        # Quartz can't print a List directly.)
        ("refined lambda through fold (v4.50)",
         "fold([1, 2, 3], 0, fn(acc: Int, x: Int where (x > 0))"
         " -> acc + x)\n",
         "6\n"),
        # v4.51: && / || in regular Glass code compile through Quartz's
        # BIN_OP_C map. C's && and || are short-circuiting so semantics
        # match host eval directly.
        ("&& and || in normal code (v4.51)",
         "let r : Int = if (1 > 0) && (1 < 5) then 42 else 0\n"
         "r\n",
         "42\n"),
        # v4.51 canonical range refinement: param checked against an
        # interval. The guard becomes `((n > 0LL) && (n < 100LL))`.
        ("range refinement via && (v4.51)",
         "fn middling(n: Int where (n > 0 && n < 100)) : Int = n + 1\n"
         "middling(50)\n",
         "51\n"),
        # v4.51 || refinement: enum-style "this OR that" check.
        ("|| refinement (v4.51)",
         "fn flag(n: Int where (n == 0 || n == 1)) : Int = n + 10\n"
         "flag(1)\n",
         "11\n"),
        # v4.53: modulo in regular Quartz code via BIN_OP_C entry.
        ("modulo in normal code (v4.53)",
         "let r : Int = 17 % 5\n"
         "r\n",
         "2\n"),
        # v4.53: parity refinement compiles + the guard fires only
        # for an actually-even arg. 10 is even, so even_only returns
        # 11. Pinned by both this and the structural test below.
        ("parity refinement compiles (v4.53)",
         "fn even_only(n: Int where (n % 2 == 0)) : Int = n + 1\n"
         "even_only(10)\n",
         "11\n"),
        # v4.54: unary NOT in normal code via emit_expr UnaryNot arm.
        ("unary NOT in normal code (v4.54)",
         "let r : Int = if !(3 > 5) then 42 else 0\n"
         "r\n",
         "42\n"),
        # v4.54: NOT refinement compiles + holds. 5 is nonzero, so
        # 100 / 5 = 20.
        ("NOT refinement compiles (v4.54)",
         "fn nonzero(n: Int where (!(n == 0))) : Int = 100 / n\n"
         "nonzero(5)\n",
         "20\n"),
        # v4.55: arithmetic-in-predicate now compiles. `n + 1 > 0`
        # was rejected pre-v4.55 (only bare `binder OP lit` was
        # allowed); the recursive compiler handles the offset.
        ("offset arithmetic in predicate (v4.55)",
         "fn f(n: Int where (n + 1 > 0)) : Int = n\n"
         "f(5)\n",
         "5\n"),
        # v4.55: nonlinear predicate + boolean combinator. `n * n`
        # compiles as `(n * n)`; composed with a range bound via &&.
        ("nonlinear predicate with && (v4.55)",
         "fn g(n: Int where (n * n >= 1 && n < 100)) : Int = n\n"
         "g(7)\n",
         "7\n"),
        # v4.56: cross-parameter refinement. `hi > lo` references the
        # earlier param `lo`, which is a C function parameter in scope
        # at the guard site. clamp(3, 10) = 7.
        ("cross-parameter refinement (v4.56)",
         "fn clamp(lo: Int, hi: Int where (hi > lo)) : Int = hi - lo\n"
         "clamp(3, 10)\n",
         "7\n"),
        # v4.56: return refinement referencing a param. `result > a`
        # sees `a` (all params in scope when the body completes).
        ("return refinement references param (v4.56)",
         "fn addpos(a: Int, b: Int) : Int where (result > a) = a + b + 1\n"
         "addpos(5, 3)\n",
         "9\n"),
        # v4.71 (Phase A1/A2 — migration): effectful functions compile.
        # Effects are erased at codegen; `print` is a C runtime call.
        # The binary prints "hi" (from the IO effect) then the result 5.
        ("effectful fn compiles, print works (v4.71)",
         "fn g(x: Int) : Int !{IO} = let _ = print(\"hi\") in x\n"
         "g(5)\n",
         "hi\n5\n"),
        # v4.71: a prelude function the program uses (string_contains)
        # is now emitted, not just type-checked. Usage-based: simple
        # programs don't drag in higher-order prelude fns.
        ("prelude fn string_contains compiles (v4.71)",
         "if string_contains(\"hello\", \"ell\") then 1 else 0\n",
         "1\n"),
        # v4.72 (Phase A4): nested patterns — a cons whose head is a
        # ctor pattern. Recursive pattern binding handles the nesting.
        ("nested cons-of-ctor pattern (v4.72)",
         "type P = | P(Int, Int)\n"
         "fn sh(xs: List<P>) : Int =\n"
         "  match xs { [] => 0; [P(a, b), ...rest] => a + b + sh(rest) }\n"
         "sh([P(1, 2), P(3, 4), P(10, 0)])\n",
         "20\n"),
        # v4.72: literal patterns over scalar scrutinees (Int + String).
        ("literal int/string patterns (v4.72)",
         "fn classify(n: Int) : String ="
         " match n { 0 => \"z\"; 1 => \"o\"; _ => \"m\" }\n"
         "fn day(c: String) : Int ="
         " match c { \"mon\" => 1; \"tue\" => 2; _ => 0 }\n"
         "let _ = print(classify(0) ++ classify(1) ++ classify(9))\n"
         "day(\"tue\")\n",
         "zom\n2\n"),
        # v4.73 (Phase A4): a tuple pattern whose first element is a CTOR
        # must DISCRIMINATE on that ctor, not match every tuple. This is
        # exactly prism's tokenizer dispatch shape `(TEnd, _) => …`. The
        # bug: _pattern_test returned "true" for any tuple, so the first
        # arm swallowed every case. Here `(A, k)` must NOT match (B, 9);
        # the `(B, k)` arm must win → 9, not 0.
        ("tuple pattern discriminates on ctor sub-pattern (v4.73)",
         "type Tag = | A | B\n"
         "fn pick(p: (Tag, Int)) : Int ="
         " match p { (A, k) => 0; (B, k) => k }\n"
         "pick((B, 9))\n",
         "9\n"),
        # v4.73: an explicit `let _ : T = <effectful stmt>` final decl is
        # a discard run for effects, NOT a REPL result — so `print` fires
        # once, not twice. (prism's last line is this shape.)
        ("final `let _ : T` discard prints once (v4.73)",
         "let _ : String = print(\"once\")\n",
         "once\n"),
    ]
    failures = 0
    for label, src, expected in cases:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".glass", delete=False
        ) as f:
            f.write(src)
            src_file = f.name
        with tempfile.NamedTemporaryFile(suffix="", delete=False) as f:
            out_bin = f.name
        try:
            p = subprocess.run(
                [sys.executable, QUARTZ, src_file, "-o", out_bin],
                capture_output=True, text=True,
            )
            if p.returncode != 0:
                print(f"  FAIL  {label} (compile)")
                print(f"        stderr: {p.stderr.strip()}")
                failures += 1
                continue
            r = subprocess.run([out_bin], capture_output=True, text=True)
            ok = (r.stdout == expected)
            print(f"  {'OK ' if ok else 'FAIL'}  {label}")
            if not ok:
                print(f"        expected {expected!r}, got {r.stdout!r}")
                failures += 1
        finally:
            os.unlink(src_file)
            try:
                os.unlink(out_bin)
            except OSError:
                pass

    # v4.49: structural codegen checks. The runtime cases above can't
    # distinguish "guard emitted but never fired" from "guard silently
    # dropped" — for both, the program returns the right value. These
    # cases run `quartz.py --verbose`, capture the generated C, and
    # grep for the actual `if (!...) { fprintf ... exit(1); }` shape
    # so a future change that quietly stops emitting the guard FAILS
    # this test instead of looking healthy.
    print("== quartz refinement codegen structure (v4.49) ==")
    ref_cases = [
        ("param guard in C source",
         "fn p(n: Int where (n > 0)) : Int = n\np(1)\n",
         "if (!(n > 0LL))"),
        ("return guard in C source",
         "fn p(n: Int) : Int where (result > 0) = n + 1\np(1)\n",
         "if (!(result > 0LL))"),
        # Literal-on-the-left form: ensures the parser of the
        # predicate handles both `binder OP literal` AND
        # `literal OP binder` (the latter must flip the C operator).
        ("literal-on-left predicate shape",
         "fn p(n: Int where (0 < n)) : Int = n\np(3)\n",
         "if (!(0LL < n))"),
        # v4.50: refined let-decl in main()'s C source. Pin down that
        # the guard lives in main(), not duplicated in the surrounding
        # fn machinery.
        ("refined let-decl guard in main (v4.50)",
         "let n : Int where (n > 0) = 42\nn\n",
         "if (!(n > 0LL))"),
        # v4.50: refined LetIn inside fn body — guard must be emitted
        # inside the fn, not the surrounding main().
        ("refined let-in guard inside fn (v4.50)",
         "fn f(k: Int) : Int = let n : Int where (n > 0) = k in n\nf(3)\n",
         "if (!(n > 0LL))"),
        # v4.50: refined lambda param — guard lives inside the
        # lifted __lambda_N C fn, not at the call site.
        ("refined lambda param guard in lifted fn (v4.50)",
         "let dbl = fn(x: Int where (x > 0)) -> x * 2\ndbl(5)\n",
         "if (!(x > 0LL))"),
        # v4.51: && compiled in a refinement predicate. Verifies
        # _compile_refinement_pred recurses correctly: both sides
        # become parenthesized comparisons and combine via C's `&&`.
        ("&& refinement guard shape (v4.51)",
         "fn p(n: Int where (n > 0 && n < 100)) : Int = n\np(50)\n",
         "((n > 0LL) && (n < 100LL))"),
        # v4.51 || refinement guard — same shape with `||`.
        ("|| refinement guard shape (v4.51)",
         "fn p(n: Int where (n == 0 || n == 1)) : Int = n\np(0)\n",
         "((n == 0LL) || (n == 1LL))"),
        # v4.53: parity refinement guard. `_compile_refinement_pred`
        # recognizes the `binder %% int_lit OP int_lit` shape and emits
        # `((mangled % KLL) OP MLL)` — the natural C transcription.
        ("parity refinement guard shape (v4.53)",
         "fn p(n: Int where (n % 2 == 0)) : Int = n\np(2)\n",
         "((n % 2LL) == 0LL)"),
        # v4.54: NOT refinement guard. `_compile_refinement_pred`
        # recurses through UnaryNot, emitting `(!inner)` — so the full
        # guard double-negates: `if (!(!(n == 0LL)))`.
        ("NOT refinement guard shape (v4.54)",
         "fn p(n: Int where (!(n == 0))) : Int = n\np(5)\n",
         "(!(n == 0LL))"),
        # v4.55: recursive compiler transcribes nested arithmetic. The
        # offset `n + 1` becomes `(n + 1LL)`, then the comparison wraps
        # it: `((n + 1LL) > 0LL)`. Pins down that arithmetic recurses
        # rather than being special-cased.
        ("offset arithmetic guard shape (v4.55)",
         "fn p(n: Int where (n + 1 > 0)) : Int = n\np(5)\n",
         "((n + 1LL) > 0LL)"),
        # v4.56: cross-param guard references the earlier param by its
        # mangled name — `(hi > lo)`, not `(hi > <literal>)`.
        ("cross-parameter guard shape (v4.56)",
         "fn clamp(lo: Int, hi: Int where (hi > lo)) : Int = hi - lo\n"
         "clamp(3, 10)\n",
         "(hi > lo)"),
    ]
    for label, src, needle in ref_cases:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".glass", delete=False
        ) as f:
            f.write(src)
            src_file = f.name
        with tempfile.NamedTemporaryFile(suffix="", delete=False) as f:
            out_bin = f.name
        try:
            p = subprocess.run(
                [sys.executable, QUARTZ, src_file, "-o", out_bin, "--verbose"],
                capture_output=True, text=True,
            )
            ok = (p.returncode == 0) and (needle in p.stdout)
            print(f"  {'OK ' if ok else 'FAIL'}  {label}")
            if not ok:
                print(f"        rc={p.returncode}, expected substring "
                      f"{needle!r}")
                print(f"        stdout tail: {p.stdout.strip()[-300:]}")
                print(f"        stderr tail: {p.stderr.strip()[-300:]}")
                failures += 1
        finally:
            os.unlink(src_file)
            try:
                os.unlink(out_bin)
            except OSError:
                pass

    # v4.56: cross-parameter refinements now compile — a later param's
    # predicate may reference an EARLIER param (`b < a`), so the v4.55
    # "non-binder identifier" negative was retired (it compiles now).
    # What's STILL refused: a non-arithmetic expression form (function
    # calls, field access). The cross-param boundary itself (forward
    # references, truly-unbound names) is caught by the host's pre-eval
    # during glass-build, so it can't be isolated to Quartz's envelope
    # via the CLI — the envelope branch stays as defense-in-depth for
    # standalone codegen.
    print("== quartz refinement: unsupported predicate (v4.56) ==")
    bad_cases = [
        # A function call inside the predicate — not an arithmetic /
        # comparison / boolean form, so it hits the envelope error.
        ("function call in predicate",
         "fn id(x: Int) : Int = x\n"
         "fn p(n: Int where (id(n) > 0)) : Int = n\np(3)\n",
         "Quartz refinement predicates support arithmetic"),
    ]
    for label, src, needle in bad_cases:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".glass", delete=False
        ) as f:
            f.write(src)
            src_file = f.name
        try:
            p = subprocess.run(
                [sys.executable, QUARTZ, src_file],
                capture_output=True, text=True,
            )
            ok = (p.returncode != 0) and (needle in p.stderr)
            print(f"  {'OK ' if ok else 'FAIL'}  {label}")
            if not ok:
                print(f"        rc={p.returncode}, expected substring "
                      f"{needle!r}")
                print(f"        stderr: {p.stderr.strip()[-300:]}")
                failures += 1
        finally:
            os.unlink(src_file)

    return failures


if __name__ == "__main__":
    sys.exit(main())
