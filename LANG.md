# Glass — Language Specification

**Version:** 4.0.0
**Status:** Reference implementation, pre-alpha. Installable via
`pip install -e .` from the repo root; the `glass` console script runs
files or starts a REPL.

Glass is a pure functional language designed for transparent local reasoning.

## Design axioms

1. **Semantic types over structural ones.** `NonEmpty<String>` not `string`;
   `Int where (x > 0)` not just `Int`.
2. **Immutability and explicit effects by default.** (v0.5.)
3. **Locality of reasoning.** Functions understood from signature + body alone.
4. **No indexed iteration.** Transformations are `map`/`filter`/`fold`.
5. **First-class uncertainty.** Probabilistic values are a primitive. (Future.)
6. **Errors are values, not exceptions.** (v0.1.)
7. **Match is total.** Non-exhaustive matches are a type error. (v0.1.)
8. **Domain constraints belong in the signature.** Refinement types. (v0.4.)
9. **Side-effects belong in the signature.** Algebraic effects. (v0.5.)
   Effects are **polymorphic** — higher-order fns adapt to their callbacks. (v0.7.)
10. **The language must be expressive enough to describe itself.** Self-hosting
    is v1.0. v0.6 made mutual recursion work; v0.7 made effect-polymorphic
    higher-order fns work; v0.8 added records (the natural shape for AST
    nodes in self-hosted Glass-in-Glass). Closes the last load-bearing
    structural gap for v1.0.

## Influences

Glass takes the Rust experience seriously without adopting Rust's solution.
Rust's central insight is that safety can come from compiler-enforced
visibility at every dangerous-operation site (mutation, lifetime, send/sync).
Glass takes the dual route: safety through type-system-tracked semantics —
no mutation in the pure core, and the operations that DO matter (IO,
randomness, model inference, eventually quantum measurement, eventually
private data flow) are visible at every call site through effect labels.

Absorbed: sum types + exhaustive matching (v0.1), errors as values (v0.1),
safe stdlib defaults (v0.2), parametric polymorphism (v0.3), refinement
types (v0.4), effect tracking (v0.5), tuples (v0.6), effect polymorphism (v0.7),
**records with named fields (v0.8)**.

Deliberately not taken: ownership/borrowing, lifetimes, C++-adjacent syntax.

## Glass and the AI era

This section is the substantive one. Glass isn't an "AI language" in the sense
of having a tensor library or autodiff baked in; those are libraries. What
Glass has that the AI era needs is a type system that takes seriously the
fact that **a non-trivial fraction of any post-AI codebase will call into
opaque, untrusted, probabilistic black boxes**, and the type system should
make that fact visible, contained, and auditable.

### Inference as an effect

v0.7 ships an `!{Inference}` effect label and a `model_call` built-in:

```glass
fn ask(prompt: String) : String !{Inference} = model_call(prompt)
fn ask_and_show(prompt: String) : String !{IO, Inference} =
  let answer : String = model_call(prompt) in
  print("answer: " ++ answer)
```

The label is the load-bearing part. The runtime detail of `model_call` —
which model, how it's hosted, whether it's local or remote — is configurable;
the type-system fact is permanent. Every function that touches a model
declares so. Every caller of such a function picks up the effect or
declares it themselves. The audit question "does this code path call a
model?" is a textual search over signatures, not a runtime trace.

The same machinery distinguishes `!{Inference}` from `!{IO}`, `!{Random}`,
and any future label (`!{TrustedModel}`, `!{Sampled}`, `!{Private}`).
Conflating them loses signal; keeping them separate keeps audit questions
answerable. See `examples/ai.glass`.

### Refinement types as trust boundary

Model output is untrusted by default. A refinement type on the let-binding
that receives model output makes the contract explicit:

```glass
fn ask_nonempty(prompt: String) : String !{Inference} =
  let answer : String where (string_length(answer) >= 1) = model_call(prompt) in
  answer
```

If the model returns a value violating the refinement, the program raises
at the boundary — not 50 functions later when a downstream parse fails on
something unexpected. The refinement is the **contract**; the model is the
**supplier**; Glass **enforces**. SMT integration (post-v0.7) lets the
compiler statically discharge refinements that follow from the program's
own reasoning, leaving only model-output checks at runtime.

This is the substantive type-system answer to "untrusted AI output":
not a parsing schema (which catches shape but not semantics), and not a
runtime guard (which is just a check buried in code) — but a **type-level
contract** that travels with the value through every fn that handles it.

### Effect polymorphism and AI batching

v0.7's effect-polymorphic `map`/`filter`/`fold` mean that batching model
calls is the obvious code, not a separate abstraction:

```glass
fn batch_ask(prompts: List<String>) : List<String> !{Inference} =
  map(prompts, fn(p: String) -> model_call(p))
```

The same `map` works for pure transformations, `!{IO}` callbacks, and
`!{Inference}` callbacks. The signature of `batch_ask` correctly inherits
`!{Inference}` from its lambda. No "async map" / "io map" / "model map"
proliferation; one generic primitive that adapts.

### Capability typing for trust levels

Effect labels are just identifiers. Different trust levels are different
labels:

- `!{TrustedModel}` — output of a model the program is willing to take
  semantic content from
- `!{UntrustedModel}` — output that must pass refinements before use
- `!{HumanReviewed}` — output that has been audited by a person
- `!{Sandbox}` — execution in a restricted environment

The Glass type system doesn't pick which labels matter for a given
deployment. It provides the machinery; a security team or a deployment
defines the policy by which labels callers must declare and how they
combine. Forbidden combinations (calling `!{UntrustedModel}` from a code
path that hasn't `!{HumanReviewed}` the result) become declarable
type-system errors.

### Differentiable subsets

A pure functional core is naturally differentiable. The subset of Glass
without effects, without refinements that introduce nondifferentiable
discontinuities, and over a numeric type (Float, post-v0.8) is a
differentiable function. The compiler can extract that subset for
autodiff backends. This isn't unique to Glass — Dex, JAX-like systems,
and others have explored this — but the combination with effect typing
means the differentiable-vs-effectful boundary is **machine-checkable**,
not convention.

### LLM-readable documentation

A Glass signature carries more information than most:

```glass
fn validate_kyc<E>(
  doc: String,
  reviewer: (String) -> Bool !{E}
) : Result<Identity, ValidationError> !{IO, Inference, E}
```

The reader (human or LLM) sees: takes a document string and a
reviewer callback; the reviewer may do whatever effects E; returns either
an Identity or a ValidationError; the overall fn does IO, calls a model,
and propagates whatever the reviewer does. No reading of the body required
to answer "what does this fn touch?"

This makes Glass a candidate lingua franca for human–AI–audit
collaboration. The signature is the spec; the body is the implementation;
the LLM can read either without confusing them.

## What comes after ML/AI

The honest answer is nobody knows. The useful version of the question is:
what languages will be useful for **whatever** comes after, in the
direction that already seems to be forming?

The direction that seems to be forming:

- **Verified AI.** Models that come with formal guarantees on their outputs.
  Refinement types are the type-system anchor for "this output satisfies
  property P," whether the proof of P comes from training, from a verifier
  network, or from runtime checking.
- **Hybrid symbolic/neural.** Programs where some functions are neural
  black boxes and others are formal logic. The type system mediates the
  trust boundary — what the formal side is willing to assume about the
  neural side's outputs.
- **Multi-agent systems.** Programs that orchestrate multiple autonomous
  agents. Capability typing describes which agents may be invoked from
  where, with what privileges, and what trust relationships exist between
  them. Effect labels for inter-agent communication, message provenance,
  and authorization.
- **Programs that explain themselves.** Types carry enough semantics that
  an LLM can answer "what does this code do?" from signatures alone. The
  documentation is the type; the type is checked by the compiler.
- **The end of code as a separate artifact.** What humans write becomes
  intent (in restricted natural language or in formal logic); the AI
  produces implementations in a formal language like Glass; the type
  system mediates trust. The artifact a human reviews and the artifact a
  machine executes are derivable from each other.

The bet behind Glass: **the formal artifact that all three audiences
(humans, AI, verification tools) read the same way is what matters.**
Glass's transparency axiom — readable from local context alone, semantic
types in signatures, effects in signatures — is precisely the requirement
for that artifact. Not because Glass is special; because the requirement
is real.

## Brand glossary

Glass tries to name new concepts with **Glass-native vocabulary** rather
than echo existing ones (e.g. SQL, lenses, prisms-as-optics). Names that
echo existing things make people search for the wrong reference. New
concepts deserve new names, even when the new names are unfamiliar.

- **Glass.** The language itself. Transparent local reasoning.
- **Pane.** The future query layer (replaces what older docs called the
  "Glass query language"). A pane of glass — a typed view into data,
  declarative, composable, descended directly from the Glass primitives
  `filter`/`map`/`fold`. See "Pane" section below.
- **Frost.** The ZK extension of Pane (replaces "ZK-SQL"). Frosted glass
  preserves structure while obscuring contents — exactly the right
  metaphor for zero-knowledge queries: the auditor reads the query
  shape, the verifier checks the constraint, the witness data stays
  private.
- **Quartz.** The v2.0+ native compiler (currently a code name). Glass
  crystallized: compiled, optimized, with linear types for one-time-use
  values and constant-time codegen as a typed effect.

Core PL terminology (effects, refinements, polymorphism, sum types,
exhaustive matching) is kept as industry-standard. There's nothing
gained by renaming "effect" to something Glass-flavored; effects are a
known concept and Glass uses them the standard way.

## Thinking from the future

### Pane: a Glass-native query layer

Glass already expresses much of SQL's declarative spirit using existing
primitives — `filter` is `WHERE`, `map` is `SELECT`, `fold` is `GROUP BY`
aggregation. See `examples/queries.glass` for working code. The future
**Pane** layer makes this first-class.

**Design goals for Pane:**

- **Pure-functional from the ground up.** No mutable cursor abstraction
  or implicit table state. Queries are values; running them is a function
  application.
- **Types describe schemas.** A table is `List<Row>` where `Row` is a
  user-defined record type (records arrive post-v0.7; today, tuples).
  Joins are statically type-checked.
- **Refinements describe constraints.** "Every age in this column is ≥ 0"
  is `Column<Int where (age >= 0)>`, enforced at insert time.
- **Effects describe what queries do.** A read-only query is pure. A
  query that modifies storage carries `!{Storage}`. A randomised
  sampling query carries `!{Random}`. A query that consults a model
  carries `!{Inference}`. The signature describes what the query CAN
  do before you run it.

### Frost: ZK queries

Frost is Pane with privacy. Some columns are private witnesses; the
query result is a zero-knowledge proof that the result was correctly
computed from the private data.

- Columns marked `!{Private}` are witness data — flow into the query but
  never out to the result.
- A query function returning `Result<T, E> !{Private}` describes
  "computes T from private inputs"; the compiler can lower it to a ZK
  circuit where the verifier sees only T and E.
- Refinement predicates on output rows become the statement the proof
  attests. `SELECT name FROM users WHERE balance >= 100` becomes
  `result : List<String> where (each_balance_ge_100(result))`, and the
  ZK backend proves the predicate without revealing balances.

**The position to aim at:** a query the auditor reads in Glass syntax
*is* the spec the ZK proof attests, *is* the circuit the prover runs,
*is* the constraint the verifier checks. One artifact, three audiences.
This is the inverse of the current state, where each role gets a
different artifact and they may not even agree.

### Quantum

`!{Measure}` for quantum measurement. Linear types (Quartz) for no-cloning.
`Uncertain<T>` (post-v1.0) for probabilistic outcomes.

### Cryptography and post-quantum

Refinement types put preconditions in signatures (`m > 1`, `exp >= 0`,
`x in field`). Effects mark `!{CryptoRandom}`, `!{ConstantTime}`. Linear
types (Quartz) handle one-time-use values like nonces. SMT integration
(post-v0.7) closes the static verification loop for refinements.

## On the host language

Python is the v0.x bootstrap. The transition is gated on the rate of
language change, not on a version number:

- **v0.0 – v0.7 (current): Python.** Fast iteration while the type system
  grew weekly. v0.7 stabilises effect polymorphism, which was the last
  load-bearing structural addition for the v0.x era.
- **v0.8 – v0.9: OCaml.** Z3 bindings for SMT discharge of refinements,
  proper pattern matching, ADTs. The bugs Python's lack of type system
  has been letting through get caught by the host's own type system.
- **v1.0: Glass-in-Glass.** Self-host the type checker and interpreter.
- **v2.0+: Quartz.** Native compilation to a low-level IR — the Lean /
  Idris / Roc strategy. Constant-time codegen as a capability-typed effect.
  Linear types for one-time-use values. A ZK-circuit backend for the
  Frost fragment.

## Lexical structure

Keywords: `let`, `fn`, `in`, `if`, `then`, `else`, `match`, `true`,
`false`, `type`, `where`.

Comments `#`, identifiers (lowercase-start for bindings, uppercase-start
for types/constructors/effects), integer/string/bool literals, list
literals `[...]`, tuple literals `(a, b, c)`.

## Operators

`*`, `/`, `+`, `-`, `++`, `==`, `!=`, `<`, `>`, `<=`, `>=`, `|>`.

## Declarations

```glass
let NAME : TYPE = EXPR
fn NAME(p1: T1) : TR = EXPR
fn NAME(p1: T1) : TR !{Eff1, Eff2} = EXPR
fn NAME<T1>(p1: T1) : TR = EXPR
fn NAME<T1, Eff>(p1: (T1) -> T1 !{Eff}) : T1 !{Eff} = EXPR    # effect-polymorphic
type NAME<T1> = | Variant1 | Variant2(T1)
```

## Types

- `Int`, `String`, `Bool`
- `List<T>`
- Tuple: `(T1, T2, T3)`
- Function: `(T1, T2) -> TR` or `(T1, T2) -> TR !{Eff1, Eff2}`
- User ADT (sum): `Name<T1>` — multiple variants
- User record: `Name<T1>` — single shape with named fields
- Refined: `BaseType where (predicate)` — at fn-param and let-binding sites

### Records (v0.8)

```glass
type User = {
  id: Int,
  name: String,
  age: Int
}

let alice : User = User { id: 1, name: "Alice", age: 30 }
let n : String = alice.name                     # field access
fn greet(u: User) : String =                    # destructuring in patterns
  match u { User { name, age } => "hi " ++ name }
```

Records are nominal — two record types with identical field shapes but
different names are distinct types. The field set in a literal must
match the declaration exactly: no missing, no extras. Record patterns
in v0.8 bind all named fields by their declared names; renaming and
"rest" syntax (`User { name, .. }`) are post-v0.8.

Records compose with polymorphism: `type Container<T> = { item: T, count: Int }`
gives `Container<Int>` and `Container<String>` as distinct instantiations,
with type parameters propagating through field access.

The macro role records play: in Glass-in-Glass at v1.0, the AST of the
language will be represented by records (one per node kind) plus sum
types (for kind discrimination). Records and effects together make every
data flow visible at signature level, which is the v1.0+ self-hosting
requirement.

## Patterns

- `_`, lowercase ident, literal patterns
- `[]`, `[h, ...t]` list patterns
- `Ctor`, `Ctor(p1, ...)` constructor patterns
- `(p1, p2, p3)` tuple patterns
- `Name { field1, field2 }` record patterns (v0.8)

## Effects

`fn name(...) : T !{IO, Random}` declares side-effects. Body effects must
be a subset of declared. Effects propagate through call chains. Effects
are part of `TyFn`, so an effectful fn cannot be passed where a pure one
is expected.

### Effect polymorphism (v0.7)

A type parameter appearing in an effect-row position is an
**effect-row variable**. A fn that declares `!{E}` where `E` is a type
parameter is polymorphic over its effects:

```glass
fn map<A, B, E>(xs: List<A>, f: (A) -> B !{E}) : List<B> !{E}
```

At each call site, `E` is bound to whatever the callback's effects
actually are. `map(xs, double)` (pure callback) gives a pure `map`;
`map(xs, print)` (`!{IO}` callback) gives `map !{IO}`;
`map(xs, model_call)` (`!{Inference}` callback) gives `map !{Inference}`.

Built-ins `map`, `filter`, `fold` are effect-polymorphic. Prelude
helpers `map_option`, `bind_option`, `map_result`, `bind_result` are
effect-polymorphic. The same primitive composes through pure,
effectful, and mixed code without proliferation.

Built-in effect labels: `IO` (print), `Random` (random_int),
`Inference` (model_call). Custom effect labels are just identifiers —
no declaration needed.

## Refinement types

`BaseType where (predicate)`. Predicates type-check as Bool with the binder
in scope; runtime-checked at fn entry, let binding, and let-in. SMT
discharge of obligations is post-v0.7.

## Polymorphism

`fn name<A, B>(...)`. Rigid type variables inside the body, fresh
instantiation at call sites. Same machinery for type vars and effect
vars: rigid inside, instantiated outside.

## Mutual recursion (v0.6)

Two-pass type checker. Pass 1 registers types and fn signatures; pass 2
checks fn bodies and runs let initializers. Top-level fns can reference
each other in either order.

## Prelude

```glass
type Option<T>    = | None | Some(T)
type Result<T, E> = | Ok(T) | Err(E)
type Pair<A, B>   = | Pair(A, B)

# All effect-polymorphic — propagate callback effects through monadic chains.
fn map_option<A, B, Eff>(o, f)         : Option<B>     !{Eff}
fn bind_option<A, B, Eff>(o, k)        : Option<B>     !{Eff}
fn map_result<A, B, Err, Eff>(r, f)    : Result<B,Err> !{Eff}
fn bind_result<A, B, Err, Eff>(r, k)   : Result<B,Err> !{Eff}
fn fst<A, B>(p) : A
fn snd<A, B>(p) : B

fn string_contains(s: String, needle: String) : Bool   # v0.8.1
```

## Built-in functions

- `print(s: String) -> String !{IO}`
- `random_int(lo: Int, hi: Int) -> Int !{Random}`
- `model_call(prompt: String) -> String !{Inference}`
- `len`, `head` (Option), `tail` (Option), `reverse`, `range`,
  `string_length`, `int_to_string` — all pure.
- **`substring(s: String, start: Int, end: Int) -> String`** — extract
  chars `[start, end)`; clamps at end-of-string; raises on negative
  indices or `start > end`. (v0.8.1)
- **`string_index_of(s: String, needle: String) -> Option<Int>`** —
  first occurrence, or `None`. (v0.8.1)
- **`read_file(path: String) -> Result<String, String> !{File}`** —
  read a file's contents; returns `Err` with the OS message on
  failure. The `!{File}` effect makes every file read visible at
  every call site. (v0.8.3)
- **`write_file(path: String, content: String) -> Result<Int, String> !{File}`** —
  write `content` to `path`; returns the byte count in `Ok` or the OS
  message in `Err`. Same `!{File}` effect as `read_file`. Pairs with
  `read_file` to enable Glass-side build pipelines. (v3.13)
- **`run_command(cmd: String, args: List<String>) -> Result<(Int, String, String), String> !{Process}`** —
  invoke an external program with arguments; returns
  `Ok((exit_code, stdout, stderr))` or `Err(message)`. Distinct
  `!{Process}` effect — process spawning is its own capability,
  strictly more powerful than file I/O. 30-second timeout enforced.
  (v3.13)
- `map`, `filter`, `fold` — all effect-polymorphic.

## Pre-declared Pair and Result (v1.8 audit)

v1.6 pre-declared `Option<A>` in prism.glass's initial type environment. v1.8 completes the standard-library trio with `Pair<A, B>` and `Result<T, E>` — the same set the host's PRELUDE provides. Glass programs that use any of these for tuple-like data or typed error handling now compile and run through prism.glass without re-declaring them.

### The TyVar reservation table

Pre-declared types use closed type-variable IDs at the bottom of the numbering space. The id allocator (`build_ctor_env_at`) starts at a fixed offset to avoid colliding with these:

| TyVar ID | Reserved for |
|----------|--------------|
| 0 | `List<A>` (its A) |
| 1 | `Option<A>` (its A) |
| 2 | `Pair<A, B>`'s A |
| 3 | `Pair<A, B>`'s B |
| 4 | `Result<T, E>`'s T |
| 5 | `Result<T, E>`'s E |
| 6+ | user-declared types |

`build_ctor_env_at(decls, 6)` numbers user constructors from 6 onward. The same pattern that worked for Option in v1.6 scales to multi-parameter ADTs — the only constraint is reserving enough IDs.

### What this unlocks

A Glass program that previously needed inline `type Pair<A, B> = | Pair(A, B)` and `type Result<T, E> = | Ok(T) | Err(E)` declarations to run through prism.glass can now drop them, matching the host's behaviour exactly. The same source compiles to the same output on either interpreter.

### safecalc.glass — the v1.8 showcase

A safe calculator that returns `Result<Int, String>` instead of crashing on bad input. The grammar parses sequential `number op number op number ...` expressions with `+` and `*`, no precedence (purely sequential). Unknown operators return `Err`. Five test cases:

| Input | Result |
|-------|--------|
| `"1 + 2 + 3"` | `Ok(6)` |
| `"10 * 5 + 2"` | `Ok(52)` (sequential, no precedence) |
| `"100 + 23"` | `Ok(123)` |
| `"7 + 3 + 11 + 21"` | `Ok(42)` |
| `"5 ? 3"` | `Err("unknown operator: ?")` |

The output is `List<Result<Int, String>>` — a generic ADT parameterised by two type variables, holding instances of another generic ADT. Both prism.glass and the host produce identical output.

### Cross-compatibility note

safecalc.glass deliberately uses `string_index_of` for all character comparisons (via `is_char(target, c)`) rather than `string_eq` or `==`. The host doesn't have `string_eq`; prism.glass's eval doesn't yet handle `==` on strings. Routing through `string_index_of` — which both interpreters implement identically since v1.6 — keeps the file portable.

This is a temporary asymmetry. A future release should add `==` for strings to prism.glass's eval, at which point `string_eq` and the cross-compatibility wrapper become unnecessary.

### Migration distance update

| Metric | v1.6 | v1.7 | v1.8 |
|--------|------|------|------|
| Feature parity with glass.py | ~78% | ~78% | **~82%** |
| Pre-declared ADTs | 2 (List, Option) | 2 | **4** (+ Pair, Result) |
| Stage 3 demo programs | 4 | 4 | **5** (+ safecalc) |
| Wall clock on prism.glass | ~7s | ~5.8s | ~5.8s |

The trajectory: each release closes ~1% per substantive feature added to prism.glass. Records (~200 lines) and refinements (~800 lines) remain. At this rate the v1.x line reaches ~95% feature parity, sufficient to start v2.0's Quartz translation work.

## Maturity release — regex engine and the v1.10 problem (v2.0 audit)

v1.9 shipped a real REPL. The next planned release was v1.10 — records in prism.glass, ~200 lines of work. But v1.9 → v1.10 is visually confusing: the decimal-parsing instinct reads "v1.9 → v1.10" as "v1.9 → v1.1", because humans see `1.9` and `1.10` as decimal numbers, not as version components. Rust hit this in 2016 with its 1.10 release; Python hit it in 2021 with 3.10. Both languages got past it eventually, but their developers and users spent months explaining "no, it's one-point-ten, not one-point-one".

Glass is small enough that the version numbering can carry narrative weight instead of footnotes. v1.9 → v2.0 sidesteps the visual issue and lets the version itself say something. **v2.0 = the language is matured. v3.0 = Quartz, native compilation.** Each major version means something now; that contract holds going forward.

### Substance to match the bump

A version bump without a substantive release is renumbering. So v2.0 ships a real new artifact: **a working regex engine in pure functional Glass.**

`examples/showcase/regex.glass` is ~210 lines and implements:

- Literal characters, `.` (any single character)
- Alternation `a|b`
- Concatenation `ab` (implicit, by position)
- Kleene star `a*`, one-or-more `a+`, optional `a?`
- Grouping `(...)` with nested patterns

The architecture is the classic Russ-Cox-style recursive matcher, expressed in Glass:

1. **AST.** A `Regex` ADT with one constructor per operator: `RChar`, `RAny`, `RAlt`, `RSeq`, `RStar`, `RPlus`, `ROpt`, `REmpty`.
2. **Parser.** Recursive descent with three precedence levels: `alt → seq → atom (with quantifiers)`. Each parser returns `(Regex, Int)` — the parsed sub-pattern and the new cursor position. A return value of `-1` for the position signals parse failure.
3. **Matcher.** Continuation-passing. `match_at(r, s, i, k)` tries to match `r` against `s` starting at position `i`. On success, it calls `k(j)` with the new position. The continuation `k` returns `true` if the rest of the pattern also matches all the way to end-of-string.

The continuation-passing style is what makes backtracking work cleanly. `RSeq(a, b)` matches `a`, and its continuation is "match `b` from where `a` left off, with the original final continuation". `RAlt(a, b)` matches `a`; if that returns false at any point, it tries `b`. `RStar(inner)` greedily matches `inner` repeatedly, with each iteration's continuation being "match RStar(inner) again from here, then the rest"; if that fails, fall through to `k(i)` (zero matches).

29 self-tests in the file exercise every operator and combination:

```
OK    a ~ "a"            -> true
OK    a|b ~ "c"          -> false
OK    a* ~ "aaaa"        -> true
OK    a+ ~ ""            -> false
OK    a?b ~ "aab"        -> false
OK    a.c ~ "abbc"       -> false
OK    (ab)+ ~ "abab"     -> true
OK    (a|b)*c ~ "ababbc" -> true
OK    a(bc)*d ~ "abcbcd" -> true
```

All 29 pass. The engine is small but real — every operator and quantifier interacts correctly with every other.

### What 2.0 means going forward

The contract for major-version semantics:

- **v2.0** — the language has matured. Hindley-Milner with effect rows, refinement types with three subsumption strategies, ADTs with generics, pattern matching, closures, structural and nominal records, equality and concatenation working across types and collections. Real REPL. Five-program Stage 4 demo chain. ~80% feature parity between host and prism.glass. Dual-licensed Apache-2.0 OR MIT. CI on Python 3.10/3.11/3.12.
- **v2.x** — incremental closing of remaining migration gaps. Records in prism.glass, refinements in prism.glass, SMT-backed refinement checking. Stage 4.5 (prism interprets itself, slow but real).
- **v3.0** — Quartz. Native compilation of prism.glass. The release where glass.py becomes optional, where the answer to "how far from migrating off Python" is *zero*.
- **v3.x and beyond** — Pane (query layer), Frost (ZK extension of Pane).

The version numbers carry the project's roadmap. Anyone reading "v2.0" should immediately understand: stable, mature, but the destination is v3.0.

## Interactive REPL (v1.9 audit)

v1.0 through v1.8 focused on the language and the self-host. v1.9 turns to **product surface**: how someone first encounters Glass. The previous `glass` command with no arguments dropped you into a one-line stub that read a single line, tokenised it, parsed it, installed it, and looped. Useful for testing but not a real product.

v1.9 replaces it with a real REPL:

### Multi-line input via parser-error introspection

When a user types `fn fact(n: Int) : Int =` and hits Enter, the parser raises a `SyntaxError` about unexpected EOF. A naive REPL would print that error and clear the buffer. v1.9's REPL inspects the error message: if it matches one of the "incomplete input" markers (`unexpected token EOF`, `expected RBRACE`/`RBRACKET`/`RPAREN`, `expected then`/`else`/`in`/`=>`/`IDENT`), the REPL knows the user is mid-input and keeps reading. The continuation prompt switches from `glass> ` to `    ...`.

A multi-line `fn fact` definition (header → if branch → else branch → call) flows naturally:

```
glass> fn fact(n: Int) : Int =
    ...   if n < 2 then 1
    ...   else n * fact(n - 1)
  fact : (Int) -> Int

glass> fact(5)
  : Int = 120
```

Any parse error that *doesn't* match the incomplete-input markers (genuine syntax mistakes, unknown tokens) surfaces immediately and the input buffer is cleared. This is heuristic — a more principled approach would be a parser that explicitly distinguishes "want more input" from "this is wrong" — but the heuristic catches every case in practice and stays out of the way otherwise.

### Commands

| Command | Behavior |
|---------|----------|
| `:help` | Show available commands. |
| `:quit` / `:q` | Exit the REPL (or `Ctrl-D`). |
| `:type EXPR` | Print the inferred type of `EXPR` without evaluating it. |
| `:env` | List user-defined bindings (filtered against an initial snapshot). |
| `:reset` | Re-create checker and env, clear all user definitions. |
| `:load PATH` | Read a `.glass` file and install its declarations into the current session. |

`:type` is the fastest way to explore inference. `:env` filters against an initial-names snapshot taken at REPL start (and refreshed on `:reset`), so the host's PRELUDE doesn't clutter the listing. `:load` is the bridge between file-based development and REPL exploration — work on a `.glass` file in your editor, `:load` it, then explore interactively.

### readline integration

When Python's `readline` module is available (Linux and macOS by default), arrow keys navigate command history within a session and history persists across sessions in `~/.glass_history`. The module is imported in a try/except so Windows or minimal Python environments degrade gracefully to plain `input()`.

### Error recovery

`SyntaxError`, `TypeError_`, and `RuntimeError` are all caught around the install loop. Failed input prints `! TypeName: message` and the session continues. Previously installed bindings are unaffected:

```
glass> let x = 42
  x : Int = 42

glass> undefined_y
  ! TypeError_: unbound identifier 'undefined_y'

glass> x + 1
  : Int = 43
```

This is the same forgiving-shell behavior as Python's REPL, ipython, ghci, ocaml's toplevel — the language ecosystem people are used to. Not having it was a real barrier to using Glass interactively.

### Test coverage

`tests/test_glass.py` gained six REPL session cases. Each one:

1. Spawns `python glass.py` as a subprocess (no args → REPL mode).
2. Feeds a scripted session through stdin (multiple lines, terminated by `:quit`).
3. Captures stdout.
4. Checks that an expected substring (`": Int = 120"`, `": Int = 2"`, etc.) appears.

The six cases cover: simple expression evaluation, `let` binding persisted across iterations, multi-line `fn` definition, `:type` command output format, error recovery (an expression after a type error still works), and `:reset` clearing state (a previously bound name becomes unbound). **81/81 passing**.

### Why the REPL belongs in v1.x not v2.0

v2.0 will be Quartz — native compilation, replacing glass.py. At that point the REPL becomes a question: do you have one for the compiled form? Most languages do (Rust's `evcxr`, Haskell's GHCi, OCaml's toplevel, even rustc's mini-REPL). Building the REPL now, on top of the interpreted host, means the UX is settled. Quartz will inherit the same command set and behavior, with whatever interpreter shim it needs.

## Stage 4 scale-up: closures, recursion, and three real bugs (v1.8 audit)

v1.5 proved meta-circular evaluation on tinylang.glass (60 lines, integers + booleans + if). v1.6 added substring/string_index_of/Option, scaling to tinycalc.glass (a string-processing calculator). v1.8 scales further: **midlang.glass — a 150-line Glass-in-Glass interpreter with first-class functions, closures, let-bindings, and recursion via let-rec.**

### What midlang.glass implements

```
type MExpr =
  | EInt(Int) | EBool(Bool) | EVar(String)
  | EAdd | EMul | ELt | EIf
  | ELet(String, MExpr, MExpr)
  | ELam(String, MExpr)
  | EApp(MExpr, MExpr)
  | ELetRec(String, String, MExpr, MExpr)
```

The values include `MClos(param, body, env)` and `MRecClos(name, param, body, env)`. Eval handles environment threading, closure capture, and recursive-binding self-reference exactly as prism.glass itself does — at one-fifth the scale.

The midlang program embedded in the file is:

```
let rec fact = fn(n) ->
  if n < 2 then 1 else n * fact(n - 1)
in fact(5)
```

plus a curried-add demonstration `((fn(x) -> fn(y) -> x + y)(10))(20)`. Both run through prism.glass:

```
examples/stage3/midlang.glass ==> (MInt(120), MInt(30)) : (MValue, MValue)
```

### The three bugs the scale-up surfaced

**1. prism.glass had no `==` operator.** The lexer at line 257 emitted `TEq` for `=`, then checked the next character only for `>` (to make `=>`). It never produced a distinct token for `==`. Consequently the parser had no `parse_compare` case for equality, the AST had no `EEq`, the inferer had no rule, and eval had no handler. Programs using `==` would fail at parse time with "expected then" — because `if k == name then v else ...` parsed as `if k`, then encountered `=` where `then` was expected.

The fix added:
- New tokens `TEqEq` and `TNeq` in the Token ADT
- Lexer dispatch for `=` checks `=` (`==`) and `>` (`=>`) before defaulting to `=`
- Lexer dispatch for `!` checks `=` (`!=`) before defaulting to `!`
- AST variants `EEq(Expr, Expr)` and `ENeq(Expr, Expr)`
- `parse_compare` cases for both new tokens
- Polymorphic inferer rule — both sides unify with each other, result is `TyBool`. Unlike `</>/<=/>=` which force `TyInt`, equality should work on any type whose values can be compared. No type-class constraint (Glass doesn't have those yet); the runtime decides.
- Eval handler dispatching to a new `value_eq(a, b)` helper that pattern-matches on Value variants and uses the host's primitive `==` for Int/Bool/String. Closures, ctors, tuples, records compare as not-equal — adequate for the demo, extensible later if needed.

**2. `++` rejected list concatenation in the type-checker.** prism.glass's `EConcat` inferer forced both sides to unify with `TyStr`. midlang's env extension uses `[Pair(name, v)] ++ env` — a `List<Pair<String, MValue>>` ++ `List<Pair<String, MValue>>` — which is exactly what the host accepts. The inferer rejected it with "can't unify List with String".

The fix changed `EConcat` inference to: infer both sides, unify them with each other, return that common type. No constraint on the type being specifically String or List. This defers the concatenability check to runtime — same pragmatic approach the host uses, just without the host's deeper type-class infrastructure.

**3. `++` runtime had no list path.** Even after the type-check accepted list ++ list, eval raised `"++ lhs not a string"`. prism.glass represents lists as `VCtor("Cons", [head, tail])` / `VCtor("Nil", [])` chains, not as a separate `VList` variant. The original eval only matched `VStr`.

Added `list_concat_val(va, vb)`:
```
fn list_concat_val(va: Value, vb: Value) : Value =
  match va {
    VCtor(name, args) =>
      if name == "Nil" then vb
      else match args {
        [h, t, ...rest] => VCtor("Cons", [h, list_concat_val(t, vb)]);
        _ => va
      };
    _ => va
  }
```

`EConcat`'s eval now dispatches: `VStr` → string concat via `++` (host evaluates), `VCtor` → `list_concat_val(va, vb)`.

### Why these were invisible until midlang

Each prior demo used a careful subset:
- `tiny.glass` — no equality, no concat
- `poly.glass` — no equality, no concat
- `tinylang.glass` — no equality (used `if-then-else` on booleans only), no concat
- `tinycalc.glass` — used `string_index_of` returning `Option<Int>` and pattern-matched `Some(i)`/`None`, but never used `==` or `++`. The arithmetic was `+` not `==`.

midlang has `lookup_var` needing `if k == name then v else recurse` for string-keyed env lookup. AND it has `[Pair(name, v)] ++ env` for env extension. The combination exposed both gaps in one demo.

This is the predicted pattern from `docs/migration.md`: feature gaps surface as the demo workload grows. Static review of prism.glass wouldn't have noticed — at 4000 lines of dense code, asking "does this implement `==`?" is harder than just running a program that needs it and seeing what breaks.

### Migration distance update

| Metric | v1.6 | v1.7 | v1.8 |
|--------|------|------|------|
| Feature parity with glass.py | ~78% | ~78% | **~80%** |
| Builtins in prism.glass | 8 | 8 | 8 |
| Pre-declared ADTs | 2 (List, Option) | 2 | 2 |
| Comparison operators | `< > <= >=` | `< > <= >=` | **`< > <= >= == !=`** |
| `++` polymorphism | String only | String only | **String + List** |
| Stage 3 demo programs | 4 | 4 | **5** |
| Demo richness | calculator | calculator | **interpreter with closures + recursion** |

What remains for full feature parity: refinement types in prism.glass (~800 lines), records (~200 lines), additional builtins (`map`/`filter`/`fold`/`range`/`random_int`/`model_call` — ~300 lines combined). The structural shape is done.

## Interpreter performance (v1.7 audit)

cProfile on the v1.6 host running prism.glass + all four Stage 3/4 demos showed the hot path was identity dispatch overhead — 43.6 million calls to `isinstance` consuming about half the CPU time. The Glass AST and value type hierarchies are flat (no subclassing past the abstract `Node` and `Value` bases), so `type(x) is X` is functionally equivalent to `isinstance(x, X)` but skips the method call through `__instancecheck__` and just does a C-level pointer comparison.

### Changes

1. **`eval_expr`** — `isinstance` chain replaced with `type(e) is X`. Branches reordered by frequency: `Ident`, `Call`, `BinOp`, `If` go first because they account for ~80% of evaluations on prism.glass.
2. **`apply_fn`** — same treatment for the `FnV`/`BuiltinV`/`CtorV` dispatch; `{**env}` replaced with `env.copy()` (slightly faster, no kwargs-unpacking overhead).
3. **`pat_match`** — `type(v) is X` for value-type checks inside the existing `p.kind == "..."` dispatch.
4. **`check_refinement_runtime`** — `while type(ty) is TyRefine` for the runtime refinement walk; on a non-refined parameter the function now returns after one fast comparison.
5. **`eval_binop` + `_eq`** — same idea.

### Measurements

Five-run minimum, prism.glass full pipeline (reads + interprets tiny.glass, poly.glass, tinylang.glass, tinycalc.glass):

| Region | v1.6 (self time) | v1.7 | Reduction |
|--------|------------------|------|-----------|
| `eval_expr` | 9.97s | 5.38s | 46% |
| `apply_fn` | 2.69s | 1.68s | 38% |
| `pat_match` | 1.81s | 1.58s | 13% |
| `check_refinement_runtime` | 0.35s | 0.20s | 43% |
| Total `isinstance` calls | 43.6M | 2.3M | 95% |
| **Wall clock** | **7.05s** | **5.78s** | **18%** |

### Why this was the right move

The original target from v1.6's closing notes was env-chain frames + sibling-env caching, with a stated 25-100× combined target. cProfile told a different story: the env dict copy was only 0.5s out of 7.05s, not a 5× win opportunity. The real bottleneck was Python-level isinstance overhead — invisible from reading the code, but obvious from the profile. The 18% achieved was less than the optimistic projection, but it's grounded in measured reality.

### What's left

The remaining time in eval_expr (5.38s self time on 4.5M calls = ~1.2μs per call) is at Python's floor for function-call + dispatch overhead. Going faster requires structural change:

- **Flat instruction array** instead of tree-walking — saves the recursive call overhead, lets the interpreter prefetch the next op. 3-5× speedup typically.
- **Bytecode compilation** — Glass AST → custom bytecode → tight VM loop. 5-10× on top.
- **Native compilation (Quartz)** — emit Python AST or C code from typed Glass programs. 10-100× depending on workload.

These belong to v2.0+ work. For v1.x, the host is fast enough that all demos run in seconds, the test suite passes in ~10s, and prism.glass's full pipeline (read + interpret 4 files) finishes in under 6 seconds.

## Reflexive feature coverage (v1.6 audit)

v1.5 proved meta-circular evaluation on tinylang.glass. v1.6 expands the *feature surface* of prism.glass so larger Glass programs can run from disk through the self-host pipeline. Three additions:

### substring builtin

`substring(s, start, end)` — curried `String -> Int -> Int -> String`. Pure (no effects). When prism.glass interprets a call to substring, the host's substring implementation is invoked via `apply_builtin`, preserving exact semantic equivalence with native execution.

### string_index_of builtin

`string_index_of(haystack, needle)` — `String -> String -> Option<Int>`. Returns `Some(i)` at the first match, `None` otherwise. The signature matches the host's exactly, so a single Glass file using `match string_index_of(...) { Some(i) => ... ; None => ... }` runs identically on both interpreters.

### Option pre-declared in initial_envs

`Option<A>` is now baked into prism.glass's initial type environment, alongside `List<A>`. Both constructors (`None` and `Some`) are registered as schemes with proper type-parameter quantification. User code no longer needs to repeat the `type Option<A> = | None | Some(A)` declaration to run through prism.glass.

### The bug exposed by adding string_index_of

Adding a non-constructor function (`string_index_of`) whose return type is an ADT (`Option<Int>`) broke prism.glass's exhaustiveness checker. The original `ctors_of_adt` walked every scheme in the type env, peeled `TyFn`s, and collected names whose final type was the target ADT. This misclassified `string_index_of` as an Option constructor. Subsequent exhaustiveness checks tried to verify that `match` arms covered "Some, None, and string_index_of" — and failed.

The fix is a one-liner: filter by initial-letter case. Glass uses the convention that constructors start with an uppercase letter (`None`, `Some`, `Cons`) and regular functions start with lowercase (`string_index_of`, `print`). The `starts_uppercase(s)` predicate now gates the constructor classification. It's a heuristic, but it matches Glass's actual naming convention and is the same approach Haskell uses to distinguish constructors from regular identifiers.

### tinycalc.glass — the v1.6 showcase

A calculator that tokenises and sums strings like `"1+2+3+4"` using the new builtins. Recursive walk over the source string, character-by-character: digits are read into integers, non-digits are treated as separators, the running total accumulates. Four test inputs produce `[10, 132, 42, 1107]` on both host and prism.glass.

```
$ glass examples/selfhost/prism.glass
examples/stage3/tinycalc.glass ==> [10, 132, 42, 1107] : List<Int>
```

The program exercises every feature added in v1.6 — substring slicing, string_index_of pattern matching, Option discrimination, List<Int> construction, recursion over strings. All compiled and evaluated by prism.glass.

### Migration distance update

| Metric | v1.5 | v1.6 |
|--------|------|------|
| Feature parity with glass.py | ~75% | ~78% |
| Builtins in prism.glass | 6 | 8 |
| Pre-declared ADTs | 1 (List) | 2 (List, Option) |
| Stage 3 demo programs | 2 (tiny, poly) | 4 (tiny, poly, tinylang, tinycalc) |

Three of the four migration-blocker categories from `docs/migration.md` — refinements (~800 lines), records (~200 lines), full builtin coverage (~300 lines) — remain. v1.6 chips off ~30 lines of the third. The path is incremental: each release adds another piece of host coverage to prism.glass, and the demo chain in `examples/stage3/` grows to exercise it.

## Refinement types: implication-based subsumption (v1.4 audit)

v1.3 discharged refinements when the actual's predicate was alpha-equivalent to the formal's. v1.4 adds **implication discharge** for simple comparisons: when the actual's refinement is *strictly stronger* than the formal's, the call site discharges at compile time even though the predicates aren't textually identical.

### The motivating examples

```glass
fn ensure_positive(n: Int) : Int where (result > 0)  = ...
fn safe_div(a: Int, b: Int where (b != 0))           : Int = a / b

safe_div(100, ensure_positive(7))
# Discharged: (result > 0) ⟹ (b != 0)
# Every integer strictly greater than 0 is also nonzero. The compiler
# proves this and skips the runtime check.
```

```glass
fn min_one(n: Int)         : Int where (result >= 1) = ...
fn needs_positive(n: Int where (n > 0)) : Int = ...

needs_positive(min_one(3))
# Discharged: (result >= 1) ⟹ (n > 0)
# Over integers, n >= 1 and n > 0 describe the same set.
```

### The implication core

`_comparison_implies(op1, k1, op2, k2)` decides whether `(n op1 k1) ⟹ (n op2 k2)` over integer arithmetic, using set-inclusion semantics:

| Predicate     | Set                  |
|---------------|----------------------|
| `n > k`       | `[k+1, ∞)`           |
| `n >= k`      | `[k, ∞)`             |
| `n < k`       | `(-∞, k-1]`          |
| `n <= k`      | `(-∞, k]`            |
| `n == k`      | `{k}`                |
| `n != k`      | `Z \ {k}`            |

Implication `S1 ⟹ S2` is true iff `S1 ⊆ S2`. All 36 combinations of operators are enumerated explicitly. The implementation handles:

- **Same-direction comparisons.** `(n > 5) ⟹ (n >= 0)` because `[6, ∞) ⊆ [0, ∞)`.
- **Mixed `>=` and `>`.** `(n >= 1) ⟹ (n > 0)` because for integers `[1, ∞) = (0, ∞)`.
- **Strict comparison implies non-equality.** `(n > 0) ⟹ (n != 0)` because 0 is not in `[1, ∞)`.
- **Equality implies anything compatible.** `(n == 5) ⟹ (n >= 0)` because the singleton `{5}` is in `[0, ∞)`.

### What `_extract_comparison` accepts

The implication only runs when both predicates are simple comparisons of the binder against an integer constant. The predicate can be either `binder OP constant` or `constant OP binder` (the latter gets the operator flipped). Compound predicates, function calls inside the predicate, or comparisons against non-constants fall through to `None` and the runtime check is retained.

### Soundness guarantee

The implication core is sound: it returns `True` only when the implication provably holds. The test suite includes a negative case where `(result >= 5)` is fed into a parameter requiring `(n > 5)` — the integer 5 satisfies the first but fails the second, so the compiler refuses to discharge and the runtime check correctly catches the violation.

### Empirical impact

`examples/showcase/imply.glass` defines four producers with strictly-positive returns (`> 0`, `>= 1`, `>= 5`, `> 10`) feeding into three consumers with weaker preconditions (`!= 0`, `>= 0`, `> 5`). Nine call sites:

- `safe_div(100, ensure_positive(7))` — `(result > 0) ⟹ (b != 0)`
- `safe_div(50, min_one(3))` — `(result >= 1) ⟹ (b != 0)`
- `safe_div(36, at_least_five(2))` — `(result >= 5) ⟹ (b != 0)`
- `safe_div(120, more_than_ten(0))` — `(result > 10) ⟹ (b != 0)`
- `sqrt_floor(ensure_positive(15))` — `(result > 0) ⟹ (n >= 0)`
- `sqrt_floor(min_one(8))` — `(result >= 1) ⟹ (n >= 0)`
- `needs_above_five(more_than_ten(0))` — `(result > 10) ⟹ (n > 5)`
- `sqrt_floor(at_least_five(20))` — `(result >= 5) ⟹ (n >= 0)`
- `needs_above_five(more_than_ten(min_one(15)))` — chained, `(result > 10) ⟹ (n > 5)`

**All nine discharge at compile time.** Zero runtime checks fire.

### What's still not handled

- **Cross-variable predicates.** `Int where (b > a)` where both `a` and `b` are parameters in scope. The current extractor only recognises predicates that compare against a closed constant.
- **Compound predicates.** Anything joined by `if-then-else` in the predicate body. Even though const-eval can fold these, the implication check requires a single comparison.
- **Strict arithmetic identities.** `(n >= 2 * m)` against `(n >= m)` where m is known positive — true but requires multi-variable reasoning.
- **Reasoning across functions.** No "every call to `f` returns a value with property P" unless P is declared in `f`'s return type.

These are exactly the cases where a real SMT solver (Z3 via z3-py, or a homemade arithmetic decision procedure) becomes necessary. That work is the v1.x SMT track.

### Implementation surface area

| File | Addition |
|------|----------|
| `glass.py` | `_extract_comparison` (~20 lines); `_comparison_implies` (~50 lines, exhaustive case analysis); `predicate_implies` wrapper (~10 lines); one-line hook in `try_static_discharge`'s subsumption loop |
| `tests/test_glass.py` | 2 new tests (implication showcase + negative soundness check) |
| `examples/showcase/imply.glass` | Flagship implication demo (~90 lines) |

~80 lines added on top of the v1.3 alpha-equivalence infrastructure. **71/71 regression tests pass.** Stage 3 self-host still works.

## Refinement types: composition (v1.3 audit)

v1.3 extends refinement types in two directions: **return-type refinements** (refinements on the right side of a function's `:`) and **subsumption discharge** (a refinement-typed call's return propagates as the expression's type, and matches against a receiving parameter's refinement by alpha-equivalence). Together these let refinements *compose* through the call graph.

### Return-type refinements

```glass
fn abs(n: Int) : Int where (result >= 0) =
  if n >= 0 then n else 0 - n
```

The binder for a return refinement is the conventional name `result`. The predicate is evaluated in an env where `result` maps to the just-computed return value, with all params still in scope (so a predicate like `result > a` can reference an earlier param `a`).

At runtime, `apply_fn` checks the predicate at every exit point — at the end of the body, before returning. A failing predicate raises:
```
refinement violated: result = -5 fails predicate (result >= 0)
```

At call sites, the return type of the call inherits the refinement. So:
```glass
let r = abs(0 - 7)
# r is inferred as: Int where (result >= 0)
```

### Subsumption discharge

When the actual argument at a call site is *itself* a call to a function whose return type carries a refinement, `try_static_discharge` attempts a second strategy after constant-folding fails: it checks whether the expected refinement's predicate is alpha-equivalent to any predicate in the actual type's refinement chain.

Alpha-equivalence is the structural-equality test after renaming both binders to a fresh name. The implementation is in `predicate_alpha_equiv` and recognises the AST subset that the constant evaluator handles: literals, identifiers, binary operations, and `if-then-else`.

```glass
fn abs(n: Int) : Int where (result >= 0) = ...
fn sqrt_floor(n: Int where (n >= 0)) : Int = ...

sqrt_floor(abs(0 - 17))
# Discharged at compile time:
#   abs returns Int where (result >= 0)
#   sqrt_floor needs Int where (n >= 0)
#   predicate_alpha_equiv("result >= 0", "result", "n >= 0", "n") = true
```

### The two-strategy discharge

`try_static_discharge` tries the strategies in order:

1. **Constant-fold discharge.** Try to const-eval the actual argument. If it folds to a value V, substitute V into the predicate and check it.
2. **Subsumption discharge.** If the inferred type of the actual carries refinements, check each formal-refinement predicate against the actual's predicates via alpha-equivalence.

Either strategy can yield `ok` (skip runtime check), `fail` (compile error), or `unknown` (fall back to the next strategy or to runtime).

### What's still not handled

The pass is sound but not complete. Cases that stay `unknown` (runtime check retained):

- **Different but equivalent predicates.** `(n >= 0)` and `(n > -1)` are not alpha-equivalent at the syntactic level, even though they denote the same set of integers. A real SMT solver would normalize.
- **Weakening.** `(n > 5)` is strictly stronger than `(n >= 0)` — the first should subsume the second, but alpha-equivalence doesn't reason about implication.
- **Refinements involving other parameters.** `Int where (b > a)` where `a` is bound earlier — subsumption needs the binder environment to be richer than just one name.
- **Refinements with predicates outside the supported AST subset.** A predicate using `match` or a function call falls through.

These are the next horizon — likely a v1.4 with a sigma-formula simplifier, or a v2.x SMT integration.

### Empirical impact

`examples/showcase/compose.glass` defines four non-negativity-preserving functions (`abs`, `square`, `add_nn`, `max_nn`) and one consumer (`sqrt_floor`) with the matching precondition. Four call sites with composed expressions:

- `sqrt_floor(abs(0 - 7))` → 2
- `sqrt_floor(square(6))` → 6
- `sqrt_floor(add_nn(abs(0 - 5), square(3)))` → 3
- `sqrt_floor(max_nn(0 - 12, 0 - 4))` → 2

All four discharge at compile time. **6 of 6 refinement checks discharged. Zero runtime checks fire.**

### Implementation surface area

| File | Addition |
|------|----------|
| `glass.py` | `predicate_alpha_equiv` + `_alpha_rename` + `_ast_equal` (~40 lines); subsumption strategy in `try_static_discharge` (~30 lines); `FnV.ret` field; return-refinement check in `apply_fn`; `parse_fn_decl` allows `accept_refinement=True` on return type |
| `tests/test_glass.py` | 2 new tests (return-refinement runtime violation, compose.glass showcase) |
| `examples/showcase/compose.glass` | Flagship composition demo (~80 lines) |

The whole pass is ~70 lines added to `glass.py` on top of the v1.2 discharge infrastructure. **69/69 regression tests pass.** Stage 3 self-host still works.

## Refinement types: static discharge (v1.2 audit)

Refinement types are part of Glass since v0.4. The syntax — `Int where (n > 0)` — declares a base type plus a Bool-typed predicate that must hold of every inhabitant. The predicate refers to the binder's name (a fn parameter, a let binding) and is evaluated against an environment where that name maps to the bound value.

Through v1.1 every refinement check ran **at runtime**, at the moment a value was bound to a refined name. v1.2 adds **static discharge** for the common case where the argument is constant-foldable.

### The discharge pipeline

At every call site, for each formal parameter whose type carries a refinement:

1. **Try to constant-fold the actual argument.** `try_const_eval` handles integer/bool/string literals, integer arithmetic, comparisons, equality, string concatenation, `if-then-else` with a constant condition, and identifier lookup against a known-constant environment. Returns `None` for anything else.

2. **If folding succeeded, evaluate the predicate.** Walk the refinement chain. For each layer, substitute the constant value into the predicate's binder name and try to constant-fold the predicate. The predicate must reduce to a closed `Bool`.

3. **Three outcomes:**
   - `'ok'` — all layers proved True. Record this argument position in the `Call` node's `discharged_args` set. The runtime check will be skipped here.
   - `'fail'` — some layer proved False. Raise a compile-time error: `refinement violated at compile time: <name> = <value> fails predicate (<pred>)`.
   - `'unknown'` — anything that couldn't be folded. Leave the runtime check in place (status quo from v0.4).

4. **At evaluation time**, `eval_expr` for a `Call` reads `discharged_args` off the AST node and passes it to `apply_fn(f, args, skip_refinement_indices=...)`. `apply_fn` skips `check_refinement_runtime` for the indicated positions.

### What this catches

```glass
fn safe_div(a: Int, b: Int where (b != 0)) : Int = a / b

let r1 = safe_div(100, 4)              # ✓ discharged: 4 != 0
let r2 = safe_div(50, 3 + 4)           # ✓ discharged: const-fold 3+4 = 7, 7 != 0
let r3 = safe_div(10, 5 - 5)           # ✗ compile error: b = 0 fails (b != 0)
let r4 = safe_div(36, if true then 6 else 0)  # ✓ discharged via if-fold to 6
```

The constant-folding pass evaluates literal arguments and propagates through arithmetic and conditional expressions. Anything that can be reduced to a closed value before the program runs is checked at compile time.

### What this doesn't catch (yet)

The pass is conservative. It returns `'unknown'` (fall back to runtime check) for any of:

- **Arguments that depend on a non-constant identifier.** `safe_div(10, parse_int(input))` — the runtime check stays.
- **Arguments that come from function calls (other than const-foldable builtins).** `safe_div(10, double(5))` — runtime check.
- **Refinements with predicates involving multi-step abstract reasoning.** A real SMT solver would prove that `n >= 0` is preserved by `+`, `*` on non-negatives. The current pass doesn't try.
- **Refinements that need cross-argument reasoning.** A predicate `b > a` where neither is constant is left to runtime.

These cases stay correct — they're just enforced later. A future v1.x release will add SMT-backed verification for symbolic arguments.

### Empirical impact

On `examples/features/crypto.glass`, Glass's most refinement-heavy file (modular arithmetic with non-negativity preconditions throughout), **12 of 28 refinement checks discharge at compile time — 43%**. The remaining 16 stay as runtime checks where the argument flows from a computation whose result the const-evaluator can't determine.

### Implementation surface area

| File | Addition |
|------|----------|
| `glass.py` | `try_const_eval` (~50 lines), `try_static_discharge` (~40 lines), `_discharge_stats` global counter, `fn_decls` registry on `Checker`, hook in `check_call`, `apply_fn` signature accepts `skip_refinement_indices`, `eval_expr` for `Call` passes `discharged_args` through |
| `tests/test_glass.py` | 4 new tests (3 negative, 1 positive showcase) |
| `examples/showcase/refine.glass` | Flagship demo (~80 lines) |

The whole pass is ~120 lines added to `glass.py`. 67/67 regression tests pass after the change. Stage 3 self-host still works (`prism.glass` runs `tiny.glass` and `poly.glass` from disk).

## Self-hosting: Stage 3 achieved (v1.0 audit)

**prism.glass reads Glass files from disk and interprets them.**

```
$ cat /tmp/tiny.glass
type IntList = | INil | ICons(Int, IntList)
fn sum_list(xs: IntList) : Int =
  match xs {
    INil => 0;
    ICons(h, t) => h + sum_list(t)
  }
sum_list(ICons(10, ICons(20, ICons(30, INil))))

$ glass examples/prism.glass
...
/tmp/tiny.glass ==> 60 : Int
/tmp/poly.glass ==> 78 : Int
```

prism.glass calls `read_file("/tmp/tiny.glass")` (host builtin,
`!{File}` effect), which returns `Result<String, String>`. The Ok
branch passes the source to prism.glass's own `compile()`. `compile`
lexes (string -> tokens), parses (tokens -> Program AST), type-checks
+ infers (Program AST -> Type + EffRow), and evaluates (AST + env ->
Value). The triple `(t, eff, v)` is matched out and `show_value(v)
++ " : " ++ show_type(t)` produces `60 : Int`.

Two levels of interpretation: glass.py interprets prism.glass, which
interprets the contents of tiny.glass / poly.glass. Same answers as
the host gives directly.

Glass-in-Glass: **6462 lines — 274% of `glass.py`**.

| File | Lines | Scope |
|------|-------|-------|
| `examples/prism.glass`     | **3984** | v1.0 shape, strings, top-level fns, comments, top-level lets, effect annotations, function types, literal patterns, file I/O. |
| `examples/eff_infer.glass` | 787  | Standalone HM + effects |
| `examples/infer.glass`     | 552  | Standalone HM |
| `examples/bootstrap.glass` | 481  | source -> value pipeline |
| `examples/typecheck.glass` | 361  | monomorphic type checker |
| `examples/mini.glass`      | 168  | closure-based interpreter |
| `examples/parser.glass`    | 129  | tokenizer |
| **total**                  | **6462** | |

### What v0.9.8 added

**Literal patterns.** The `Pattern` AST gained three variants —
`PInt(Int)`, `PBool(Bool)`, `PStr(String)`. `parse_pattern` recognizes
`TInt`, `TTrue`/`TFalse`, and `TStr` tokens as literal patterns.
`match_pattern` compares the runtime value for equality and returns
`Some([])` on match or `None` on mismatch (no bindings since literals
don't bind). `check_pattern` unifies the scrutinee type with `TyInt`,
`TyBool`, or `TyStr`.

```
match Filled(0) {
  Filled(0) => "zero cell";    // literal inside ctor
  Filled(_) => "nonzero";
  Empty     => "empty"
}
==> "zero cell"

match "foo" {
  "foo" => 1;                  // string literal pattern
  "bar" => 2;
  _     => 0
}
==> 1
```

**`read_file` builtin.** Signature: `read_file: String -> Result<String, String> !{File}`.
Inside `apply_builtin`, the `"read_file"` case unwraps the path
argument (a `VStr`), calls the host's `read_file`, and matches on
the returned `Result`:
```
VStr(path) =>
  match read_file(path) {
    Ok(content) => Ok(VStr(content));
    Err(msg)    => Err("read_file: " ++ msg)
  }
```

Registered in `initial_envs` with effect row `["File"]` on the arrow.
The `!{File}` effect now propagates upward through `eval`,
`eval_int_bin`, `eval_args`, `eval_match_arms`, `eval_record_fields`,
`apply_builtin`, `compile`, and `report` — all marked `!{IO, File}`
to permit calls into the dispatch chain that might hit `print` or
`read_file`.

### The Stage 3 chain end-to-end

1. glass.py reads `examples/prism.glass` from disk.
2. glass.py compiles + types + evaluates prism.glass.
3. prism.glass's evaluation reaches a top-level `let _ = match read_file("/tmp/poly.glass") { ... }`.
4. Host's `read_file` opens `/tmp/poly.glass`, reads its content, returns `Ok(StringV(content))`.
5. The match binds `src` to the file content. Calls prism.glass's `compile(src)`.
6. prism.glass's `compile`:
   - calls prism.glass's `lex(src)` — produces tokens
   - calls prism.glass's `parse_program(tokens)` — produces a Program AST
   - calls prism.glass's `check_program(prog)` — infers/checks types
   - calls prism.glass's `eval(prog.body, env)` — produces the value
7. Returns `Ok((TyInt, pure_eff, VInt(78)))`.
8. The match destructures the triple, formats with `show_value` and `show_type`, calls host `print`, which outputs `/tmp/poly.glass ==> 78 : Int`.

prism.glass is now a working Glass implementation. The remaining work
is making it fast enough and complete enough to be the primary
implementation (the eventual Quartz transition path).

### The Stage 3 audit table (v0.9.8)

| Stage 3 blocker | Status |
|-----------------|--------|
| String type | ✓ v0.9.4 |
| String inspection builtins + VBuiltin | ✓ v0.9.4 |
| `#` line comments | ✓ v0.9.5 |
| Top-level `fn` declarations + mutual recursion | ✓ v0.9.5 |
| Top-level `let _ = ...` statements | ✓ v0.9.5 |
| Tuple types in signatures | ✓ v0.9.5 |
| Multi-arg call syntax | ✓ v0.9.5 |
| `print` builtin | ✓ v0.9.6 |
| Effect annotations `!{IO}` in fn signatures | ✓ v0.9.6 |
| Let / let-in disambiguation | ✓ v0.9.7 |
| Function types `(A) -> B` in signatures | ✓ v0.9.7 |
| Literal patterns `VBool(true)`, `EInt(0)` | ✓ v0.9.8 |
| `read_file` builtin with `!{File}` | ✓ v0.9.8 |
| **End-to-end Stage 3: prism.glass interprets Glass from disk** | **✓ v0.9.8** |

### What's NEXT, post-Stage 3

Stage 3 reached doesn't mean Stage 3 done. The empirical pass works on
small files. To make prism.glass the primary implementation, what
remains:

- Reading prism.glass through prism.glass (the fixed-point).
  prism.glass is ~4000 lines; lexing + parsing would work but
  performance is the binding constraint.
- Performance — host `eval` rebuilds the sibling environment for
  mutual recursion on every call. For files with many decls this is
  O(n) per call. A real implementation needs proper closures captured
  at fn-definition time.
- Module / namespace system. Currently all decls share one global
  scope. Importing files would require namespacing.
- The Quartz transition: a native compiler back-end, replacing
  prism.glass's tree-walking interpreter with bytecode or LLVM IR.

These are big projects. Stage 3 was the unblocking move.


## Roadmap

- **v0.8 (this release):** Records with named fields — DONE.
  `glass` console script for installable workflow — DONE. Pending:
  `Map<K, V>` prelude type with O(log n) operations; string prelude
  (substring, split, find); `!{File}` effect with read/write builtins.
  Stays in Python — these are library additions, not engine work.
- **v0.9 (OCaml + SMT):** Migrate the engine to OCaml. SMT-discharged
  refinements via Z3 bindings. The bugs Python's lack of type system has
  been letting through get caught by the host's own type system.
- **v1.0 (Glass-in-Glass):** Rewrite the type checker and interpreter in
  Glass itself. The v0.8 stdlib and v0.9 SMT make this tractable.
  `typecheck.glass` is the seed; v1.0 grows it to handle full Glass.
- **v2.0+ (Quartz):** Native compilation. Linear types for one-time-use
  values. Constant-time codegen as a capability-typed effect. ZK-circuit
  backend for the Frost fragment.
