# Glass — Language Specification

**Version:** 5.6.0
**Status:** Self-hosting research language (not production-hardened). Installable
via `pip install -e .` from the repo root; the `glass` console script runs
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
answerable. See [`examples/features/ai.glass`](examples/features/ai.glass).

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
**supplier**; Glass **enforces**. The compiler statically discharges
refinements that follow by implication from the program's own reasoning,
leaving only the genuinely external checks (like model output) at runtime.

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
- **Pane.** The query layer — a pane of glass: a typed, declarative,
  composable view into data, descended from the Glass primitives
  `filter`/`map`/`fold`. Built in Glass; see [`examples/pane/`](examples/pane/).
- **Frost.** The zero-knowledge extension of Pane. Frosted glass preserves
  structure while obscuring contents — the right metaphor for zero-knowledge:
  the auditor reads the query shape, the verifier checks the constraint, the
  witness stays private. Built from scratch in Glass as a zk-STARK; see
  [`examples/frost/`](examples/frost/).
- **Quartz.** Glass's native back end (`quartz.py`): Glass → C. Built — a
  Glass-written compiler (`glassc.glass`) runs on top of it, and Glass
  self-hosts as of v4.76.

Core PL terminology (effects, refinements, polymorphism, sum types,
exhaustive matching) is kept as industry-standard. There's nothing
gained by renaming "effect" to something Glass-flavored; effects are a
known concept and Glass uses them the standard way.

## Thinking from the future

### Pane: a Glass-native query layer

Glass already expresses much of SQL's declarative spirit using existing
primitives — `filter` is `WHERE`, `map` is `SELECT`, `fold` is `GROUP BY`
aggregation. The **Pane** layer makes this first-class: a small, total query
algebra with a reference interpreter, built in Glass and shaped so the same
query AST can be lowered into a zero-knowledge circuit (Frost). See
[`examples/pane/`](examples/pane/).

**Design goals for Pane:**

- **Pure-functional from the ground up.** No mutable cursor abstraction
  or implicit table state. Queries are values; running them is a function
  application.
- **Types describe schemas.** A table is `List<Row>` where `Row` is a
  user-defined record type (records, since v0.8).
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

`!{Measure}` for quantum measurement. Linear types for no-cloning.
`Uncertain<T>` (a possible future addition) for probabilistic outcomes.

### Cryptography and post-quantum

Refinement types put preconditions in signatures (`m > 1`, `exp >= 0`,
`x in field`). Effects mark `!{CryptoRandom}`, `!{ConstantTime}`. Linear
types handle one-time-use values like nonces, and refinement types put the
verification obligations in the signature, where the compiler discharges what
it can prove and leaves the rest to runtime.

## On the host language

Python was the bootstrap. The plan was always to leave it — and Glass has:
the route taken was **direct self-hosting via native compilation**, not the
OCaml-and-SMT detour this section once projected.

- **The Python era.** `glass.py`, a tree-walking interpreter, grew the type
  system (Hindley-Milner, effect rows, refinement types) and remains the reference.
- **Glass-in-Glass.** `examples/selfhost/prism.glass` reimplements the whole
  front end — lexer, parser, type inference, evaluator — in Glass.
- **Quartz.** `quartz.py` compiles Glass to C; a Glass-written compiler
  (`glassc.glass`) runs on top of it. At **v4.76** the bootstrap fixpoint
  closed: `glass.py` is now only a one-time bootstrap and a differential-testing
  oracle. See [docs/self-hosting.md](docs/self-hosting.md).

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
in scope, and are runtime-checked at fn entry, let binding, and let-in.
Obligations the compiler can prove by **implication / subsumption**
(alpha-equivalence and interval reasoning) are discharged statically — no
runtime check is emitted. A general SMT backend was sketched in early
roadmaps but not pursued; this implication-based discharge is what shipped.

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

## Implementation history

The release-by-release design audits — how refinement subsumption, the
self-hosting stages, the REPL, the regex engine, and the rest were built and
verified — live in [`docs/design-notes.md`](docs/design-notes.md), kept out of
this spec. The terse version log is in [`CHANGELOG.md`](CHANGELOG.md).

## Roadmap

The original roadmap below (records → OCaml+SMT → Glass-in-Glass → Quartz) has
long been overtaken. Glass self-hosts (v4.76), and the work since has built
**Pane** (a query language) and **Frost** (a zero-knowledge prover) on top of it.
The OCaml/SMT step was never taken — self-hosting went straight through native
compilation via Quartz.

The current, forward-looking roadmap lives in [`docs/roadmap.md`](docs/roadmap.md);
the full history is in [`CHANGELOG.md`](CHANGELOG.md).
