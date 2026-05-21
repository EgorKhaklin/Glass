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
    ("refinement violated at runtime",
     'fn d(a: Int, b: Int where (b != 0)) : Int = a / b\n'
     'let r : Int = d(10, 0)',
     "refinement violated: b = 0"),

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

    total = len(POSITIVE) + len(NEGATIVE)
    passed = total - failures
    print(f"\n{passed}/{total} passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
