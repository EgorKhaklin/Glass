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

    total = len(POSITIVE) + len(NEGATIVE) + len(repl_cases)
    passed = total - failures
    quartz_failures = run_quartz_tests()
    failures += quartz_failures
    total += 33  # quartz cases (v3.0 + v3.1 + v3.2 + v3.3 + v3.4 + v3.4.1)
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
    return failures


if __name__ == "__main__":
    sys.exit(main())
