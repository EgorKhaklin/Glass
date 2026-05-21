# Glass — Language Specification

**Version:** 1.0.0
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
- `map`, `filter`, `fold` — all effect-polymorphic.

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
