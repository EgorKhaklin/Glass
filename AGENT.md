# AGENT.md

> Instructions for AI agents (Claude, others) and human contributors picking up work on the Glass language. This file is the single source of truth for "how this project thinks." Read it once at the start of a session.

---

## 1. What Glass is

Glass is a pure functional programming language. The reference implementation is a tree-walking interpreter in Python (`glass.py`, ~3,500 lines). **Glass self-hosts**: the frontend (`examples/selfhost/prism.glass`, ~6,600 lines) and a Glass→C compiler (`examples/selfhost/glassc.glass`) are written in Glass, and the compiler reproduces itself with no Python in the loop — the bootstrap fixpoint, closed at v4.76. The language is at v4.x. Recent work builds *on top of* it: **Pane** (a query language) and **Frost** (a from-scratch zero-knowledge proof system), both written in Glass.

Core design choices, all load-bearing:

- **Pure functional.** No mutation. No statements. Everything is an expression that returns a value.
- **Semantic types over structural.** Type annotations carry meaning, not just shape.
- **Immutability + explicit effects.** Functions that touch the outside world declare it on their arrow: `fn print_it(s: String) : String !{IO}`.
- **No indexed iteration.** Use `map`/`filter`/`fold`, never `for i in 0..len`. Recursion is the fallback.
- **First-class uncertainty.** `Option<A>` and `Result<T, E>` are pre-declared and standard.
- **Errors as values, not exceptions.** Functions that can fail return `Result`, not throw.
- **Total matching.** Every `match` must cover every constructor; the type-checker enforces it.
- **Domain constraints in the signature.** Refinement types: `fn fib(n: Int where (n >= 0)) : Int`.
- **Effects in the signature.** Effect rows on function arrows.
- **The language describes itself.** prism.glass is a Glass interpreter written in Glass — run by glass.py, and also compiled to native code by the Glass-written compiler (the bootstrap fixpoint, v4.76).

If a proposed feature violates one of these, surface it before implementing.

---

## 2. File layout

```
glass/
├── glass.py                          # The host (Python, single file, ~2900 lines)
├── pyproject.toml                    # Packaging: glass-lang, SPDX Apache-2.0 OR MIT
├── playground.html                   # Browser playground (Pyodide-based, ~17KB)
├── README.md                         # User-facing intro
├── LANG.md                           # Language spec + per-version audit sections
├── CHANGELOG.md                      # Every released version, chronologically
├── AGENT.md                          # This file
├── LICENSE / LICENSE-MIT / LICENSE-APACHE
├── docs/
│   ├── getting-started.md
│   ├── language-tour.md
│   ├── self-hosting.md
│   ├── repl.md
│   ├── playground.md
│   └── migration.md                  # The host→Glass migration plan + status
├── examples/
│   ├── basic/                        # hello, fib, etc. — single-feature demos
│   ├── features/                     # effects, refinements, types
│   ├── showcase/                     # full programs: regex, json, derive, prover, ...
│   ├── stage3/                       # programs run BY prism.glass from disk
│   └── selfhost/
│       ├── prism.glass               # The Glass-in-Glass self-host
│       ├── typecheck.glass           # Older typechecker prototype
│       └── tokens.glass              # Older lexer prototype
├── tests/
│   └── test_glass.py                 # Single regression suite, plain Python
└── .github/workflows/
    └── tests.yml                     # CI on Python 3.10/3.11/3.12
```

Where things go when adding new work:

- **New Glass programs** → `examples/showcase/` (if a full library/demo) or `examples/stage3/` (if intended to run *through* prism.glass).
- **New language features** → modify `glass.py`, then port to `prism.glass`. Tests in `tests/test_glass.py`.
- **New documentation** → `docs/` for guides; `LANG.md` for spec-level material; `CHANGELOG.md` for per-version entries.

---

## 3. Build & test commands

Memorize these. They're fast.

```bash
# Run the full regression suite (~10–20 sec, 83+ tests)
python tests/test_glass.py

# Run a Glass file
python glass.py FILE.glass
# Or, after `pip install -e .`:
glass FILE.glass

# Start the interactive REPL
glass

# The Stage 4 self-host demo chain — prism.glass interprets .glass files from disk
glass examples/selfhost/prism.glass

# Serve the browser playground
python -m http.server
# Then open http://localhost:8000/playground.html

# Run a specific showcase
glass examples/showcase/regex.glass
glass examples/showcase/json.glass
glass examples/showcase/derive.glass
```

**Always run `python tests/test_glass.py` after every meaningful change.** The suite is fast; there's no excuse to skip it.

---

## 4. Working standards

These come from the project owner and are non-negotiable.

### "Holy shit, that's done"

Never table for later. Never offer a workaround when the real fix exists. Never present a plan when the finished product is within reach. If you can finish the thing in this turn, finish it. Ship.

If a deliverable doesn't fit in one turn, ship the largest possible self-contained chunk and explicitly mark what's deferred. Never silently leave half-built work.

### One headline per release

Each release has exactly one headline deliverable. v1.9 was the REPL. v2.0 was the regex engine (and the version-narrative reset). v2.1 was the playground. v2.2 was the JSON parser. v2.3 was AGENT.md. Don't dilute a release with three half-deliverables — pick the one most important thing and execute it fully.

### Tests before ship

Every release must end with `python tests/test_glass.py` returning **N/N passed**. If a change breaks an existing test, that's the priority — fix it or revert. New features add new tests. No exceptions.

### Honesty in CHANGELOG

The CHANGELOG is for the actual builder/user. Don't hide limitations. v2.2's CHANGELOG explicitly says "prism.glass can't yet parse this file" — that's the standard. If something doesn't work, say so, in the entry where it shipped.

### Migration narrative

prism.glass is the host rewritten in Glass. Don't add host (`glass.py`) features that prism can't easily mirror, and keep the two in lockstep — they're differential-tested against each other. The migration destination (glass.py becomes optional, via Quartz) was **reached at v4.76**; the discipline of keeping prism able to self-host still holds for any new language feature.

---

## 5. Language gotchas

These will bite if you don't know them. They're the kind of thing you only learn by hitting the error message.

### Host parser: list patterns require `[h, ...t]` form

Fixed-arity list patterns don't work. `match xs { [x] => ... }` is a **syntax error**. Use `[h, ...t]` with an empty-tail check:

```glass
match xs {
  []        => "empty";
  [h, ...t] =>
    match t {
      []        => "exactly one: " ++ show(h);
      [_, ..._] => "more than one"
    }
}
```

This is true on both the host and prism.glass.

### Records: nominal on host, structural on prism

Host: declare with `type Point = { x: Int, y: Int }`, construct with `Point { x: 1, y: 2 }`. The name is required.

prism.glass: structural records — `let p = { x: 1, y: 2 }` works directly, no type declaration. The two interpreters have *different* record syntaxes; programs that use records aren't easily cross-runnable.

### Top-level `let` followed by parenthesized expression parses as application — **fixed in v4.21**

Before v4.21 the parser greedily extended postfix calls across newlines:

```glass
let v = f(x)
(g(y))                # used to parse as f(x)(g(y))
```

v4.21's `parse_postfix` declines to treat an LPAREN that begins a new line at column 1 as a call continuation. Indented continuations (`f\n  (x)`) still parse as calls. If you're reading old code that worked around this with `let v = ... in (...)`, the parens are no longer required.

### `substring(s, i, j)`: `j` is exclusive

`substring("hello", 0, 5)` returns `"hello"`. `substring("hello", 0, 3)` returns `"hel"`. Negative indices and `start > end` are runtime errors.

### `char_at` doesn't exist on host

The host has no `char_at` builtin. Use `substring(s, i, i + 1)` to extract a single-character string. prism.glass *does* declare `char_at` in its initial_envs as a built-in, but its host runtime impl is the same `substring` call.

### Effects on the final arrow

Effect annotations sit on the *final* arrow of a curried function:

```glass
fn print_then_return(s: String, n: Int) : Int !{IO} = ...
# parses as: String -> Int -> Int !{IO}
# the IO effect is ONLY on the last arrow, the inner one is pure
```

This matters because a partially applied `print_then_return("hi")` has type `(Int) -> Int !{IO}` — the effect rides along with the final invocation.

### `Pair<A, B>`, `Option<A>`, `Result<T, E>` are pre-declared

You don't need to `type Option<A> = | None | Some(A)`. It exists at startup in both host and prism. Same for Pair and Result. Don't re-declare them — name collision.

### `match` pattern variables shadow outer bindings

```glass
let x = 5 in
match some_option {
  Some(x) => x + 1;   # this x is the matched inner value, NOT the outer 5
  None    => 0
}
```

This is standard ML semantics but trips people coming from imperative languages.

### Sequential top-level lets + generic fns — **misdiagnosis retired in v4.21**

Earlier versions of this guide claimed sequential top-level lets calling the same generic fn at different types failed because "the scheme doesn't refresh." That diagnosis was wrong. The actual symptom in the documented repro:

```glass
fn id<A>(x: A) : A = x
let n = id(42)
let s = id("hello")
(n, s)
```

…was the **separate** parens-after-let parser bug above. `id("hello")\n(n, s)` was being eaten as `id("hello")(n, s)`. The type checker has always re-instantiated generic schemes correctly at each `Ident` lookup via `instantiate_fresh`. With the v4.21 parser fix the original program runs as expected.

Regression tests live in `tests/test_glass.py` under "inline regression cases."

### Plain `let` with patterns (v2.7+)

Since v2.7, plain `let` supports tuple, list, and constructor patterns. The right-hand side of `let` can be any pattern; the dispatch happens at parse time based on the token after `let`:

```glass
# Tuple destructure:
let (a, b) = pair in a + b

# Nested:
let (x, (y, z)) = triple in x + y + z

# Constructor pattern (must be exhaustive — won't compile if Option/Result with single-arm):
let Pair(k, v) = p in k                  # works — Pair has only one variant
let Some(x) = optional in x              # FAILS — non-exhaustive (None unhandled)
```

Pattern-lets desugar at parse time to `match EXPR { PAT => BODY }`. Exhaustiveness is enforced by the standard match checker. Identifier-only `let x = ... in body` keeps the traditional let-polymorphism generalization path; only non-identifier patterns route through the desugar.

Before v2.7, the workaround was explicit `match`. Existing code using `match` continues to work; pattern-let is just shorter.

### `==` and `++` are polymorphic but not universal

`==` works on primitives (Int, Bool, String) and ADT values (since v1.8). It does NOT work on closures (`VClos == VClos` returns `false` always). `++` works on String and `List<A>` (since v1.8). It does NOT cross types — `"hello" ++ [1, 2]` is a type error.

### String escape sequences are real

Both host and prism lexers handle `\"`, `\\`, `\n`, `\t`, `\r` inside string literals (since v2.3.1). Unknown escapes pass through literally. If you're writing a Glass file with a literal `\n` that should NOT be interpreted, escape the backslash: `"\\n"`. This was a real bug in v2.0–v2.3 where prism's lexer didn't handle `\` escape sequences and JSON-parser-like programs that used `"\""` failed with confusing "expected then" errors three tokens downstream.

### Refinement subsumption strategies

Three independent paths for the type-checker to discharge a refinement:
1. **Constant folding** — if `n` is a literal, evaluate `n != 0` directly.
2. **Alpha equivalence** — if the call's actual refinement is the same predicate (modulo variable renaming) as the formal's, accept.
3. **Implication** — for simple comparisons against integer constants (`<`, `>`, `<=`, `>=`, `==`, `!=`), prove `actual ⟹ expected` via exhaustive case analysis.

Anything outside these falls through to a runtime check (still sound).

### Performance ceiling

eval_expr at ~1.2μs/call is at Python's floor for function-call + dispatch overhead. Further speedup needs structural change (flat instruction array, bytecode, native compilation — v3.0 Quartz territory). Don't try to micro-optimize the tree-walker further; the next 10× comes from native compilation, not from Python tweaks.

---

## 6. When to write Glass vs. Python

A real distinction, with a real heuristic.

**Write Python when** the deliverable is an *interface to the outside world*:
- Performance work on the interpreter (must be in Python — that's what's running)
- REPL implementation (needs `readline`, `subprocess`, `stdin`/`stdout`)
- Web playground (HTML + JS + Pyodide)
- Test runner integration (subprocess + stdin)
- New language features (modify glass.py, then port to prism.glass)
- Anything touching the filesystem, network, OS

**Write Glass when** the deliverable is *a program*:
- A library someone might import (regex engine, JSON parser, …)
- A demonstration of the language's capability (Stage 4 demos)
- A useful utility that operates on Glass values
- Anything you'd put in `examples/showcase/`

**Honest accounting across ten releases (as of v2.3):**

| Version | Headline | Code lived in |
|---------|---------------------|---------------------|
| v1.4 | Implication subsumption | Python |
| v1.5 | tinylang Stage 4 demo | Glass |
| v1.6 | More builtins | Python |
| v1.7 | Performance pass | Python |
| v1.8 | midlang + ==/++ fixes | Glass + Python |
| v1.9 | Interactive REPL | Python |
| v2.0 | Regex engine | Glass |
| v2.1 | Browser playground | HTML + JS + Pyodide |
| v2.2 | JSON parser | Glass |
| v2.3 | AGENT.md | Markdown |

4 Glass, 5 Python+JS, 1 Markdown. The ratio should tilt further toward Glass over time. The migration goal is structural: every Glass library that works is one more thing the user can do without touching the host.

---

## 7. Version semantics

Major versions carry explicit narrative weight. The full contract is **major.minor.patch**:

- **major** = paradigm shift. The project is in a categorically different state.
- **minor** = big step. A new library, a real product surface, a migration milestone.
- **patch** = small fix or alignment. Mechanically small change-set; the version number is honest about the code even when the implication is big.

| Major | Meaning |
|-------|---------|
| v0.x  | Pre-release. Language was being figured out. |
| v1.x  | Self-host alive (Stage 3/4), refinement types working. |
| v2.x  | **Matured.** Stable language surface, real REPL, browser playground, real libraries. |
| v3.x  | Module system, exotic-type showcases, and the run-up to native compilation. |
| v4.x  | **Quartz + self-hosting** (the bootstrap fixpoint, v4.76), then **Pane** (query language, v4.77) and **Frost** (zero-knowledge prover, v4.78+) built on top. |

The original plan reserved separate major versions for Quartz (v3), Pane (v4), and Frost (v5); in practice they all landed within the 4.x line as the work compressed together. The destinations were reached — the numbering just didn't spread out the way it was first sketched.

**Never use v1.10.** v1.9 → v2.0 was a deliberate skip to avoid the "v1.10 looks like v1.1" visual-parsing problem that hit Rust and Python. The numbering is part of the project's narrative; don't break it for a half-point version bump that no one will read correctly.

When in doubt: a **minor** bump is a headline deliverable (a new library, a migration milestone, a built-in-Glass system); a **patch** is a fix or small alignment.

---

## 8. Aesthetic

When producing visual output — README badges, the playground, documentation, slides:

- **Dark slate base**: `#0a0d12` to `#14192a` range. Never pure black.
- **Refractive cyan accent**: `#00bcd4` (the Material cyan-500). The single brand color.
- **Geometric primitives**: octahedron (the project logo), triangles, hexagons. Never illustrative/cartoon imagery.
- **Monospace throughout**: SF Mono, Monaco, Consolas, Roboto Mono. No display fonts.
- **No emoji as decoration.** Emoji is for transient status (✓, ✗) only, and only when it adds information.
- **Minimal motion.** Slow rotation, fade-in. Nothing flashy.

The reference is intelligence-agency / think-tank visual language: deliberate, restrained, geometric. Not Silicon Valley playful.

---

## 9. CHANGELOG conventions

Every release gets an entry. The structure:

```markdown
## [X.Y.Z] — YYYY-MM-DD

**One-paragraph summary.** What this release is, who it's for, why it matters.

### Added
- Specific addition with file path and ~size.
- Another addition with what it exercises that prior work didn't.

### Why this matters
- The narrative. Why this is the right release at this point.

### Limitations
- Honest list of what doesn't work yet.
- Things that exist but are incomplete.

### Compatibility
- Tests passing count.
- Whether existing code runs unchanged.
- New dependencies, if any.
```

The "Limitations" section is required. Honesty in CHANGELOG is what makes the document trustworthy across versions.

---

## 10. Workflow for adding a new feature

1. **Locate.** Decide where in `glass.py` the change goes — lexer, parser, type-checker, evaluator, builtins, prelude. Search for analogous existing features.
2. **Modify.** Make the change. Keep it small.
3. **Test.** Add a positive case to `tests/test_glass.py` POSITIVE list (or a negative case to NEGATIVE).
4. **Regress.** Run `python tests/test_glass.py`. All N/N must still pass.
5. **Port.** If the feature exists in `glass.py`, consider porting to `prism.glass`. This is the migration track. Not always required in the same release, but always tracked.
6. **Document.** Add an entry to CHANGELOG.md. If the feature is spec-level (new syntax, new type system rule), add an audit section to LANG.md.
7. **Version.** Bump `pyproject.toml` and any version banners.
8. **Ship.** Build a zip in `/mnt/user-data/outputs/`, fresh-install verify, present_files.

---

## 11. Workflow for adding a new Glass program

1. **Decide where.** `examples/showcase/` for standalone libraries; `examples/stage3/` for programs that prism.glass should be able to interpret.
2. **Write it.** Use only features that exist in the language. If you need a feature that doesn't exist, switch to the feature-addition workflow first.
3. **Run it.** `glass examples/path/to/file.glass` — verify it produces the expected output.
4. **Test it.** Add the file path to the POSITIVE list in `tests/test_glass.py`.
5. **Regress.** `python tests/test_glass.py` returns N/N pass.
6. **Optionally**: try running through prism.glass. If it fails, the failure is a feature-gap data point for the migration track — note it in CHANGELOG limitations, don't try to fix prism.glass mid-flight.
7. **Document.** CHANGELOG entry, possibly a README showcase section if the program is significant.
8. **Ship.**

---

## 12. Specific patterns that work

Working idioms that recur across the codebase. Use these.

### Result threading with `let*` (v2.4+) and Option threading with `let?` (v2.5+)

Since v2.4 (for Result) and v2.5 (for Option), the preferred form for chained calls returning these types is the sugar:

```glass
# Result-bind (v2.4):
fn parse(src: String, i: Int) : Result<(Value, Int), String> =
  let* (v1, j) = step1(src, i) in
  let* (v2, k) = step2(src, j) in
  Ok((combine(v1, v2), k))

# Option-bind (v2.5):
fn lookup_three(t: Table, ka: String, kb: String, kc: String) : Option<Int> =
  let? a = find(t, ka) in
  let? b = find(t, kb) in
  let? c = find(t, kc) in
  Some(a + b + c)
```

Both are pure parse-time desugars to nested `match`. Same semantics as the verbose forms. Available in both host and prism.glass. The runtime can't infer which one to use — pick based on what your function's return type is. Reserved desugar variables: `__glass_lse`, `__glass_lso` (for `let*`); `__glass_lqs` (for `let?`) — don't use those names in your own code.

### Result threading (manual — pre-v2.4 style)

```glass
fn parse(src: String, i: Int) : Result<(Value, Int), String> =
  match step1(src, i) {
    Err(msg) => Err(msg);
    Ok(pair1) =>
      match pair1 { (v1, j) =>
        match step2(src, j) {
          Err(msg) => Err(msg);
          Ok(pair2) =>
            match pair2 { (v2, k) =>
              Ok((combine(v1, v2), k))
            }
        }
      }
  }
```

Verbose but explicit. Still valid; use when `let*` would be awkward (e.g., when each step has different error-handling logic). The migration cost from manual to `let*` is mechanical — line-by-line rewrite, no behavior change.

### Tuple destructuring in match arms

```glass
match parse_thing(src, i) {
  Ok(pair) =>
    match pair { (v, j) => ... use v, j here ... };
  Err(msg) => Err(msg)
}
```

Note: prism.glass's parser doesn't currently handle this pattern in all positions. If a Glass file uses tuple destructuring in match arms and prism rejects it, that's the known gap, not a bug in your code.

### Recursive walks with explicit accumulator

```glass
fn sum(xs: List<Int>) : Int = sum_acc(xs, 0)

fn sum_acc(xs: List<Int>, acc: Int) : Int =
  match xs {
    []        => acc;
    [h, ...t] => sum_acc(t, acc + h)
  }
```

Tail-recursive form. Glass doesn't optimize TCO yet, so for large lists this still grows the stack. Watch for deep recursion on Stage 4 demos — that's been a real issue.

### Mutual recursion via let-rec

```glass
let is_even = fn(n: Int) -> if n == 0 then true  else is_odd(n - 1) in
let is_odd  = fn(n: Int) -> if n == 0 then false else is_even(n - 1) in
is_even(10)
```

Wait — this doesn't work because `is_even` references `is_odd` which isn't defined yet. Use top-level `fn` declarations instead; they get mutually visible automatically:

```glass
fn is_even(n: Int) : Bool = if n == 0 then true  else is_odd(n - 1)
fn is_odd(n: Int)  : Bool = if n == 0 then false else is_even(n - 1)
is_even(10)
```

---

## 13. What NOT to do

- **Don't add features without tests.** The regression suite is the contract.
- **Don't break the migration narrative.** Adding a host feature that prism.glass fundamentally can't mirror is a red flag.
- **Don't dilute releases.** One headline per version.
- **Don't introduce dependencies lightly.** Glass is "single-file Python + dual-licensed." Adding `numpy` or `pydantic` would be a values violation.
- **Don't use v1.10 or v2.10.** Skip to the next major.
- **Don't optimize without measurement.** v1.7 was profile-guided. Future perf passes follow the same rule: measure first.
- **Don't write 200-line CHANGELOG entries.** Density matters; one paragraph summary + lists of specific additions.
- **Don't apologize in code or docs.** State limitations factually; never use "unfortunately" or "sadly."

---

## 14. Open questions / live tensions

Real things that haven't been resolved:

- **Cross-variable refinements.** `fn between(a: Int, b: Int where (b > a), c: Int where (c > b))` — runtime works (predicates evaluate in the env where bound params exist), static discharge doesn't. Adding it requires symbolic reasoning the implication-checker doesn't currently do. Tractable but not yet done.

- **Float type.** Glass has only `Int`. JSON parser doesn't handle `3.14`. Adding `Float` is a real type-system question (HM with numeric subtyping is awkward). Punted.

- **String escape sequences.** No `\n`, `\t`, `\"` in string literals. Adding them is ~30 lines in the lexer. Punted because no immediate user demand.

- **Records cross-runtime.** Host nominal, prism structural. Either unify or document forever as two distinct surfaces. Currently the second.

- **Stage 4.5.** prism.glass interpreting prism.glass. Conceptually proven (it can interpret any Glass program in principle), but slow enough to not be practical. The win would be symbolic, not utilitarian.

- **LSP server / VSCode extension.** No editor support yet. Would help adoption. Not yet attempted.

- **GitHub Pages docs site.** README + LANG.md + docs/ are markdown; a docs site is straightforward but not yet done.

If you're picking up work and one of these is the obvious next move, do it. If you're not sure, ask.

---

## 15. Contact / context

- **Owner**: Egor Khaklin (VANTA). GitHub: `EgorKhaklin/Glass`.
- **License**: Apache-2.0 OR MIT (SPDX expression in pyproject.toml).
- **CI**: GitHub Actions, Python 3.10/3.11/3.12. See `.github/workflows/tests.yml`.

---

*This file is intentionally long. Read it once, then refer back. Updating it is part of any release that introduces a new convention, gotcha, or workflow. — v2.3, 2026-05-21*
