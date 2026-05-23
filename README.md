<div align="center">

<img src="assets/glass-logo.png" alt="Glass" width="500"/>

### A pure functional language optimized for transparent local reasoning.

*Every signature tells the truth. Every match is exhaustive. Every effect is declared.*

<br/>

[![Tests](https://github.com/EgorKhaklin/Glass/actions/workflows/tests.yml/badge.svg)](https://github.com/EgorKhaklin/Glass/actions/workflows/tests.yml)
[![Version](https://img.shields.io/badge/version-4.0.0-00bcd4?style=flat-square)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT_OR_Apache--2.0-00bcd4?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-00bcd4?style=flat-square)](pyproject.toml)
[![Tests passing](https://img.shields.io/badge/tests-131%2F131_passing-00bcd4?style=flat-square)](tests/test_glass.py)
[![Self-host](https://img.shields.io/badge/self--host-Stage_4_✓-00bcd4?style=flat-square)](docs/migration.md)

</div>

<br/>

[Quickstart](#quickstart) • [Playground](docs/playground.md) • [REPL](docs/repl.md) • [Language tour](docs/language-tour.md) • [Self-hosting](docs/self-hosting.md) • [Migration](docs/migration.md) • [Showcase](#showcase) • [Spec](LANG.md) • [Agent guide](AGENT.md) • [Changelog](CHANGELOG.md)

<br/>

```glass
fn average(xs: List<Int>) : Result<Int, String> =
  if len(xs) == 0 then Err("empty list")
  else Ok(fold(xs, 0, fn(a: Int, b: Int) -> a + b) / len(xs))

fn classify(score: Int) : String =
  if score == 100      then "perfect"
  else if score >= 90  then "excellent"
  else if score >= 70  then "good"
  else                      "needs work"

let scores = [98, 85, 100, 67, 91]
match average(scores) {
  Ok(n)  => classify(n);
  Err(e) => e
}
==> "good" : String
```

<br/>

Glass is built around six axioms:

| | |
|---|---|
| **Semantic types over structural** | A name carries meaning. `UserId` and `OrderId` are different types even if both are `Int` underneath. |
| **Immutability with explicit effects** | No hidden mutation. Side effects appear in signatures: `read_file: String -> Result<String, String> !{File}`. |
| **No indexed iteration** | `map`, `filter`, `fold`. Off-by-one errors are removed from the language by construction. |
| **First-class uncertainty** | `Option<A>`, `Result<A, E>`, refinement types. Failure modes are part of the type. |
| **Errors as values** | No exceptions. Every fallible operation returns `Result`. The compiler enforces handling. |
| **Total pattern matching** | `match` is exhaustive. The compiler refuses to compile until every case is covered. |

<br/>

## Stage 4 self-host

The interpreter for Glass is written in Glass, and that interpreter can read *other* Glass interpreters off disk and run them.

```bash
$ glass examples/selfhost/prism.glass
...
examples/stage3/tiny.glass     ==>  60 : Int
examples/stage3/poly.glass     ==>  78 : Int
examples/stage3/tinylang.glass ==>  VInt(17) : Value
examples/stage3/tinycalc.glass ==>  [10, 132, 42, 1107] : List<Int>
examples/stage3/midlang.glass  ==>  (MInt(120), MInt(30)) : (MValue, MValue)
examples/stage3/safecalc.glass ==>  [Ok(6), Ok(52), Ok(123), Ok(42), Err("unknown operator: ?")] : List<Result<Int, String>>
```

Five Glass programs of progressively richer feature usage, all read from disk and interpreted by prism.glass in a single invocation. `tinylang.glass` is itself a Glass interpreter (integers + if-then-else). `tinycalc.glass` uses string-processing builtins. `midlang.glass` is a substantially richer Glass-in-Glass interpreter with first-class lambdas, let-bindings, and recursion via let-rec — the inner program computes `factorial(5) = 120` and a curried-add `30`. `safecalc.glass` adds `Pair`, `Option`, and `Result` for typed error handling.

Three levels of interpretation in a single invocation:

```
  glass.py
    │   reads + interprets
    ▼
  prism.glass  (3,984 lines of Glass)
    │   reads + interprets
    ▼
  tinylang.glass  (a Glass-in-Glass interpreter)
    │   evaluates
    ▼
  if (2 + 3) < (4 * 5) then (10 + 7) else 0
    │
    ▼
   17
```

Same answers as glass.py would give. The chain composes. See [`docs/migration.md`](docs/migration.md) for the full assessment of where Glass stands on the migration off Python.

**Glass-in-Glass is 6,462 lines — 274% the size of the Python host.**

<br/>

## Showcase

Three compact programs that demonstrate what Glass feels like to write. Each fits on one screen.

**Symbolic differentiation** ([`examples/showcase/derive.glass`](examples/showcase/derive.glass))

```
x^2 + 2x + 1            :  ((x^2 + 2*x) + 1)   ⟶   (2*x + 2)
x^3 - 3x                :  (x^3 - 3*x)         ⟶   (3*x^2 - 3)
x^5                     :  x^5                 ⟶   5*x^4
x^3 + x^2 - 5x + 4      :  (((x^3 + x^2) - 5*x) + 4)   ⟶   ((3*x^2 + 2*x) - 5)
x^3 -> d/dx -> 3*x^2 -> d/dx -> 6*x
```

An algebraic data type for polynomial expressions, a recursive `diff` that mirrors the calculus rules verbatim, a `simplify` walker that collapses identities. The output reads like a textbook because the code reads like one.

**Propositional logic prover** ([`examples/showcase/prover.glass`](examples/showcase/prover.glass))

```
Excluded middle    :  (P ∨ ¬P)                             ⟶   TAUTOLOGY
Non-contradiction  :  ¬(P ∧ ¬P)                            ⟶   TAUTOLOGY
Modus ponens       :  (((P → Q) ∧ P) → Q)                  ⟶   TAUTOLOGY
Contraposition     :  ((P → Q) ↔ (¬Q → ¬P))                ⟶   TAUTOLOGY
De Morgan          :  (¬(P ∧ Q) ↔ (¬P ∨ ¬Q))               ⟶   TAUTOLOGY
Bare contradiction :  (P ∧ ¬P)                             ⟶   CONTRADICTION
Affirm consequent  :  (((P → Q) ∧ Q) → P)                  ⟶   CONTINGENT
Hypothetical syllog:  (((P → Q) ∧ (Q → R)) → (P → R))      ⟶   TAUTOLOGY
```

Truth-table decision procedure for classical propositional logic. Enumerates all assignments to free variables, evaluates the formula on each, classifies as tautology, contradiction, or contingent. ~150 lines.

**Nash equilibrium for 2×2 games** ([`examples/showcase/nash.glass`](examples/showcase/nash.glass))

```
=== Prisoner's Dilemma ===
  T  (3, 3)   (0, 5)
  B  (5, 0)   (1, 1)
  Nash equilibria: (B, R)

=== Stag Hunt ===
  T  (4, 4)   (0, 3)
  B  (3, 0)   (3, 3)
  Nash equilibria: (T, L), (B, R)

=== Matching Pennies ===
  T  (1, -1)   (-1, 1)
  B  (-1, 1)   (1, -1)
  Nash equilibria: (none — no pure-strategy equilibrium)
```

Best-response analysis for the five canonical 2×2 games — Prisoner's Dilemma, Stag Hunt, Battle of the Sexes, Matching Pennies, Chicken. Demonstrates ADTs, pattern matching on tuples, list filtering, and a decision procedure.

**Refinement types with static discharge** ([`examples/showcase/refine.glass`](examples/showcase/refine.glass))

```glass
fn safe_div(a: Int, b: Int where (b != 0)) : Int = a / b

let r1 = safe_div(100, 4)           # ✓ discharged at compile time
let r2 = safe_div(50, 3 + 4)        # ✓ discharged (constant folds to 7)
let r3 = safe_div(10, 5 - 5)        # ✗ compile error: b = 0 fails (b != 0)
```

Domain constraints declared in the signature, checked at compile time where possible. The constant-folding pass evaluates literal arguments and substitutes them into the predicate. Provably-satisfied refinements skip the runtime check entirely. Provably-violated ones become compile errors. On `crypto.glass`, 43% of refinement checks now discharge statically.

**Refinement composition through return types** ([`examples/showcase/compose.glass`](examples/showcase/compose.glass))

```glass
fn abs(n: Int)    : Int where (result >= 0) = if n >= 0 then n else 0 - n
fn square(n: Int) : Int where (result >= 0) = n * n

fn sqrt_floor(n: Int where (n >= 0)) : Int = ...

# All four discharge statically — the compiler proves each precondition
# by matching the return-type refinement of the inner call (alpha-equivalent
# predicates).
let r1 = sqrt_floor(abs(0 - 7))
let r2 = sqrt_floor(square(6))
let r3 = sqrt_floor(add_nn(abs(0 - 5), square(3)))   # nested composition
let r4 = sqrt_floor(max_nn(0 - 12, 0 - 4))
```

Functions that *preserve* a refinement declare it in their return type. Consumers that *require* the refinement get it for free at the call site. The compiler matches predicates by alpha-equivalence (renaming binders to a common name) and discharges the precondition without any runtime check. On `compose.glass`, **6 of 6 refinement checks discharge at compile time — zero runtime checks fire.**

**Refinement implication: stronger subsumes weaker** ([`examples/showcase/imply.glass`](examples/showcase/imply.glass))

```glass
fn ensure_positive(n: Int) : Int where (result > 0)  = if n > 0 then n else 1
fn min_one(n: Int)         : Int where (result >= 1) = if n >= 1 then n else 1

fn safe_div(a: Int, b: Int where (b != 0)) : Int = a / b
fn sqrt_floor(n: Int where (n >= 0))       : Int = ...

# Compile-time discharges by implication — no alpha-equivalence required:
safe_div(100, ensure_positive(7))     # (result > 0)  ⟹ (b != 0)
safe_div(50,  min_one(3))             # (result >= 1) ⟹ (b != 0)
sqrt_floor(ensure_positive(15))       # (result > 0)  ⟹ (n >= 0)
```

The compiler proves implications between simple comparison predicates over integer arithmetic. `(n > 5) ⟹ (n >= 0)` because every integer greater than 5 is also at least 0. `(n > 0) ⟹ (n != 0)` because nothing positive is zero. Soundness is preserved: implications that *don't* hold (like `(result >= 5) ⟹ (n > 5)` — 5 satisfies the first but fails the second) are correctly refused, and the runtime check stays in place. On `imply.glass`, **9 of 9 refinement checks discharge at compile time.**

**Regex engine** ([`examples/showcase/regex.glass`](examples/showcase/regex.glass))

A complete regex matcher in ~210 lines of pure functional Glass. Supports literal characters, `.`, alternation `a|b`, concatenation, Kleene star `a*`, one-or-more `a+`, optional `a?`, grouping `(...)`. Recursive-descent parser, continuation-passing matcher — the same technique Russ Cox documented for production regex engines, expressed cleanly in Glass's ADT + closure + recursion vocabulary.

```glass
regex_match("(a|b)*c", "ababbc")       # true
regex_match("a(bc)*d", "abcbcd")       # true
regex_match("a+",      "")             # false
regex_match("(ab)+",   "aba")          # false
```

Output:
```
OK    a ~ "a"  -> true
OK    abc ~ "abc"  -> true
OK    a|b ~ "a"  -> true
OK    a* ~ "aaaa"  -> true
OK    (a|b)*c ~ "ababbc"  -> true
OK    a(bc)*d ~ "abcbcd"  -> true
...
```

**29 of 29 test cases pass** — every operator and combination exercised in-file.

**JSON parser** ([`examples/showcase/json.glass`](examples/showcase/json.glass))

A full recursive-descent JSON parser in pure functional Glass. ~280 lines. Handles null/true/false, integers (positive and negative), quoted strings, arrays, objects, arbitrary nesting, and whitespace. Returns `Result<Json, String>` with positional error messages.

```glass
parse_json("[null, true, 42, \"hello\"]")
# Ok(JArr([JNull, JBool(true), JNum(42), JStr("hello")]))

parse_json("{\"nested\": {\"deep\": [1, 2, 3]}}")
# Ok(JObj([Pair("nested", JObj([Pair("deep", JArr([JNum(1), JNum(2), JNum(3)]))]))]))

parse_json("[1, 2,")
# Err("unexpected end of input")
```

21 in-file tests pass: 16 positive parses with round-trip via `show_json`, 5 negative cases with informative error messages. A real library, not a meta-demo.

<br/>

## Try in browser

Glass runs entirely client-side via [Pyodide](https://pyodide.org). No install, no signup, just open the page:

```bash
git clone https://github.com/EgorKhaklin/Glass.git
cd Glass
python -m http.server
# open http://localhost:8000/playground.html
```

The playground includes eight preset examples — Fibonacci with refinement types, ADTs with pattern matching, refinement composition, effect annotations, closures, a tiny regex matcher — and an editable source pane. Ctrl-Enter runs. See [`docs/playground.md`](docs/playground.md) for details.

For public hosting: push the repo to GitHub, enable Pages on the main branch, and the playground is live at `https://<you>.github.io/Glass/playground.html`. The entire page is one self-contained HTML file plus `glass.py`.

<br/>

## Install

```bash
git clone https://github.com/<you>/glass.git
cd glass
pip install -e .
```

Requires Python 3.10+. No other runtime dependencies.

<br/>

## Quickstart

```bash
glass examples/basic/hello.glass
glass examples/basic/fib.glass
glass examples/features/effects.glass
glass examples/selfhost/prism.glass   # the self-host demo
```

Or REPL-style:

```
$ glass
Glass v2.0 — interactive REPL
Type :help for commands, :quit to exit.

glass> 1 + 1
  : Int = 2

glass> fn fact(n: Int) : Int =
    ...   if n < 2 then 1
    ...   else n * fact(n - 1)
  fact : (Int) -> Int

glass> fact(5)
  : Int = 120
```

The REPL supports multi-line input, persistent bindings, `:type`, `:env`, `:load`, `:reset`, and readline-backed history. See [docs/repl.md](docs/repl.md) for the full command reference.

<br/>

## Project layout

```
glass/
├── glass.py                  # The host implementation (~2,500 lines, single file)
├── examples/
│   ├── basic/                # hello, fib, lists, options, records
│   ├── features/             # generics, effects, queries, crypto, ai, type inference
│   ├── showcase/             # derive, prover, nash, refine, compose, imply
│   ├── selfhost/             # prism.glass — Glass written in Glass (3,984 lines)
│   └── stage3/               # tiny.glass, poly.glass — files read by prism.glass
├── tests/
│   └── test_glass.py         # 71/71 regression tests
├── docs/
│   ├── getting-started.md
│   ├── language-tour.md
│   └── self-hosting.md
├── assets/
│   └── glass-logo.png
├── .github/workflows/
│   └── tests.yml             # CI on push & PR
├── LICENSE                   # Dual-license dispatch
├── LICENSE-APACHE            # Apache 2.0 text
├── LICENSE-MIT               # MIT text
├── LANG.md                   # Language specification + Stage 3 audit
├── CHANGELOG.md              # v0.0 → v1.4
├── CONTRIBUTING.md
└── README.md
```

<br/>

## A short tour

**Algebraic data types and exhaustive matching.**

```glass
type Shape =
  | Circle(Float)
  | Rectangle(Float, Float)
  | Triangle(Float, Float, Float)

fn area(s: Shape) : Float =
  match s {
    Circle(r)            => 3.14159 * r * r;
    Rectangle(w, h)      => w * h;
    Triangle(a, b, c)    =>
      let s = (a + b + c) / 2.0 in
      sqrt(s * (s - a) * (s - b) * (s - c))
  }
```

**Generic types.**

```glass
type Tree<A> =
  | Leaf
  | Node(A, Tree<A>, Tree<A>)

fn map_tree<A, B>(t: Tree<A>, f: (A) -> B) : Tree<B> =
  match t {
    Leaf => Leaf;
    Node(v, l, r) => Node(f(v), map_tree(l, f), map_tree(r, f))
  }
```

**Effects in signatures.**

```glass
fn read_config(path: String) : Result<Config, String> !{File} =
  match read_file(path) {
    Ok(content) => parse_config(content);
    Err(msg)    => Err("could not read config: " ++ msg)
  }
```

Calling `read_config` anywhere in your program means `!{File}` shows up in the calling function's signature too. The effect system tracks side effects through the call graph — no hidden I/O.

**Result monad chaining.**

```glass
fn pipeline(input: String) : Result<Int, String> =
  bind_result(parse(input), fn(ast) ->
    bind_result(typecheck(ast), fn(typed) ->
      bind_result(evaluate(typed), fn(value) ->
        Ok(value))))
```

See [`docs/language-tour.md`](docs/language-tour.md) for the full tour.

<br/>

## What's in here

| File | What it is |
|------|------------|
| [`glass.py`](glass.py) | The Python implementation — lexer, parser, HM-with-effects inferer, evaluator. ~2,400 lines, single file. |
| [`examples/selfhost/prism.glass`](examples/selfhost/prism.glass) | **The Glass-in-Glass implementation.** Full pipeline written in Glass: 3,984 lines. |
| [`examples/selfhost/eff_infer.glass`](examples/selfhost/eff_infer.glass) | Standalone Hindley-Milner with effect rows: 787 lines. |
| [`examples/selfhost/infer.glass`](examples/selfhost/infer.glass) | Standalone HM (no effects): 552 lines. |
| [`examples/selfhost/typecheck.glass`](examples/selfhost/typecheck.glass) | Monomorphic type checker: 361 lines. |
| [`examples/selfhost/bootstrap.glass`](examples/selfhost/bootstrap.glass) | source → value pipeline: 481 lines. |
| [`examples/selfhost/mini.glass`](examples/selfhost/mini.glass) | Closure-based interpreter for a small expression language: 168 lines. |
| [`LANG.md`](LANG.md) | Language specification + Stage 3 self-host audit. |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history from v0.0 through v1.0. |

<br/>

## Design philosophy

Glass is built on the premise that **a programming language should make the next reader's job easy**.

Most languages optimize for the writer in the moment of writing. They allow shortcuts, implicit conversions, hidden state, and undeclared side effects because those things make typing faster. Glass refuses these. Every signature must tell the truth. Every match must cover every case. Every effect must be declared. The compiler is a guarantor of transparent local reasoning.

The cost is verbosity. The benefit is that six months later, when you come back to a file you don't remember writing, you can read a function's signature and understand exactly what it does, what it can fail on, and what it touches in the world.

<br/>

## Status

| Milestone                                                              | Status            |
| ---------------------------------------------------------------------- | ----------------- |
| Core language (ADTs, generics, HM types, pattern matching, effects)    | ✓ v1.0            |
| Self-hosting Stage 3 (prism.glass interprets `.glass` files from disk) | ✓ v1.0            |
| Self-hosting Stage 4 (prism.glass interprets a Glass interpreter)      | ✓ v1.5            |
| Refinement types — runtime enforcement                                 | ✓ v0.4            |
| Refinement types — static discharge for constant args                  | ✓ v1.2            |
| Refinement types — return-type refinements + subsumption               | ✓ v1.3            |
| Refinement types — implication for simple comparisons                  | ✓ v1.4            |
| Interactive REPL (multi-line, commands, history)                       | ✓ v1.9            |
| **Maturity release** (regex engine, stable surface)                    | **✓ v2.0**        |
| **Browser playground** (Pyodide, zero-install try-it)                  | **✓ v2.1**        |
| **JSON parser library** (real Glass code, recursive descent)           | **✓ v2.2**        |
| **AGENT.md** (agent + contributor instructions, persistent context)    | **✓ v2.3**        |
| `let*` syntactic sugar for Result threading (host + prism)             | **✓ v2.4**        |
| `let?` syntactic sugar for Option threading (host + prism)             | **✓ v2.5**        |
| Config-file parser library (real Glass code, `let*`+`let?`)            | **✓ v2.6**        |
| Pattern destructuring in plain `let` (host + prism)                    | **✓ v2.7**        |
| Markdown-to-HTML library in Glass (~340 lines)                         | **✓ v2.8**        |
| Records alignment between host (nominal) and prism                     | **✓ v2.9**        |
| Generic fn declarations in prism (`fn foo<A, B>(...)`)                 | **✓ v2.9**        |
| Parameterized record literal type inference in prism                   | **✓ v2.11**       |
| Refinements in prism (chunk 1: parsing + const-fold discharge)         | **✓ v2.12**       |
| Refinements in prism (chunk 2a: alpha-equivalence discharge)           | **✓ v2.13**       |
| Refinements in prism (chunk 3: implication discharge)                  | **✓ v2.14**       |
| Self-hosting Stage 4.5 (prism evaluates 320-line subset of itself)     | **✓ v2.15**       |
| Self-hosting Stage 4.5 extended (parser, type-checker subsets)         | planned — v2.16-x |
| Refinements in prism (runtime check insertion)                         | planned — v2.x    |
| Refinement types — SMT-backed for full arithmetic / compound           | planned — v2.x    |
| **Quartz: native compiler back-end** (Stage 5)                         | **planned — v3.0**|
| Pane: query layer                                                      | planned —         |
| Frost: ZK extension of Pane                                            | planned —         |

<br/>

## License

Glass is dual-licensed under either:

- [Apache License 2.0](LICENSE-APACHE) — includes explicit patent grant
- [MIT License](LICENSE-MIT) — simpler, more permissive

at your option. SPDX expression: `Apache-2.0 OR MIT`.

Most users can pick either freely; pick the one that best fits your project's
other licenses. See [`LICENSE`](LICENSE) for the dispatch.

<br/>

<div align="center">

*Glass — built on the principle that constraints can be load-bearing.*

</div>
