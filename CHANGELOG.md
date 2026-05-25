# Changelog

All notable changes to Glass.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/).
This project follows [Semantic Versioning](https://semver.org/).

---

## [4.94.0] — 2026-05-25 — A hash preimage in zero-knowledge, and the Goldilocks field
- **The canonical ZK statement — knowledge of a hash preimage.** [`prove_preimage_zk.glass`](examples/prove/prove_preimage_zk.glass) proves *"I know a secret x such that Hash(x) = H"* in zero-knowledge. `Hash` is a 2-to-1 compression built from Poseidon's own heart — the x⁷ S-box, round constants, and the MDS mix `[[2,3,1],[1,2,3],[3,1,2]]` — lowered gate-for-gate into a Frost circuit, with the secret preimage on private input wires and a `qassert` forcing the truncated permutation output to the public digest. Proven by the blinded F_{p⁴} FRI STARK: honest ACCEPT, wrong preimage REJECT, two blinding seeds give different openings. Rounds are reduced so the trace dogfoods on the interpreter; the full 30-round Poseidon runs the same way (~1.2s native).
- **The Goldilocks field, from scratch, int64-safe.** [`frost_goldilocks.glass`](examples/frost/frost_goldilocks.glass) builds p = 2⁶⁴ − 2³² + 1 — the field Plonky2/RISC Zero run on — with its signature division-free reduction (2⁶⁴ ≡ 2³² − 1), a real Fermat inverse (p − 2 overflows int64, so the exponent is walked in base-2¹⁶ limbs too), and the 2³²-th root of unity (32 NTT layers). Every step stays inside int64, so it dogfoods byte-identical — the int64 wall is genuinely lifted, not hidden by Python's big ints.

## [4.93.0] — 2026-05-25 — A FRI fold step, verified in zero-knowledge
- **H3 advances: the recursion step is now succinct and blind.** [`prove_recursion_zk.glass`](examples/prove/prove_recursion_zk.glass) takes the FRI fold check — `fold(f(x), f(-x)) = (f(x)+f(-x))/2 + β·(f(x)−f(-x))/(2x)` — and lowers it through the blinded F_{p⁴} FRI STARK (the `prove_zk` backend), so the verifier's own fold step is proven in zero-knowledge: the opened values stay private. Division rides as input-wire inverse hints with `(2x)·inv == 1` `qassert` gates. Honest fold step ACCEPTs, a tampered fold REJECTs, and two blinding seeds verify with different quotient openings. Self-hosted byte-identical; ~1.1s native vs ~46s interpreted (~42×) — the native-substrate payoff on a genuinely heavy circuit.

## [4.92.0] — 2026-05-25 — Top-level functions self-host as values
- A bare top-level function used as a first-class value (`map(xs, inc)`) now self-hosts: `glassc` gains an eta-expansion pre-pass that rewrites it to an arity-saturated lambda (`fn(a) -> inc(a)`) before codegen, which compiles to a proper closure. Call heads and shadowing locals are untouched, so the pass is a no-op on code that doesn't use a bare fn as a value — the bootstrap fixpoint still closes byte-identically (972 lines of C, gen1 == gen2); suite 381/381.
- **This closes the last self-hosting divergence.** The reference interpreter and the self-hosted compiler now agree on the entire practical language — the culmination of the parser-parity audit (v4.89–v4.92).

## [4.91.0] — 2026-05-25 — Record patterns self-host
- Record patterns in `match` (`Point { x, y } => …`) now parse in `prism` and compile through `glassc` — they previously ran on the reference interpreter and Quartz but not the self-hosted native compiler. With this, the parser-parity audit has closed **every practical divergence**: the reference, Quartz, and the self-hosted compiler now agree on the whole language. Bootstrap fixpoint byte-identical (972 lines of C, gen1 == gen2); suite 381/381.

## [4.90.0] — 2026-05-25 — The prelude self-hosts
- The entire standard prelude now compiles through the **self-hosted** compiler, not just the reference: `fst`, `snd`, `reverse`, `map_option`, `bind_option`, and `map_result` join `bind_result`/`string_contains` — all emitted by `glassc` (Pair field access, a `q_reverse` list walker, and closure-applying Option/Result mappers built on `q_apply1`). Every prelude function now runs identically on the interpreter, Quartz, and the self-hosted compiler. Bootstrap fixpoint byte-identical (963 lines of C, gen1 == gen2); suite 381/381.

## [4.89.0] — 2026-05-25 — Parser parity: reference ⟷ self-hosted front end
- A parser-parity audit aligned the reference interpreter (`glass.py`) with the self-hosted front end (`prism`), so a program that runs on `glass` is one that self-hosts:
  - **chained comparison** (`a == b == c`) is now a parse error in the reference too — comparison operators don't associate; write `(a == b) == c`.
  - **negative integer literals** (`-5`) now lex in prism, matching the reference's `-?\d+` — examples that used them (`quartz/lookup`, `basic/option_result`) now self-host.
  - **fixed-length list patterns** (`[a, b]`) now parse in the reference, matching prism, alongside the `[x, ...rest]` cons form.
- Documented the two remaining self-hosting gaps honestly in [`docs/self-hosting.md`](docs/self-hosting.md): record patterns in `match` (interpreter + Quartz, not prism) and a bare top-level function used as a value (interpreter only — wrap it in a lambda). Bootstrap fixpoint re-verified byte-identical; suite 381/381.

## [4.88.0] — 2026-05-25 — Poseidon: a permutation-based hash
- Frost gains **Poseidon**, the hash production STARKs actually use, built from scratch: an `x⁷` S-box (a real *permutation* on Baby Bear — MiMC's `x⁵` is not, since 5 ∣ p−1), full + partial rounds, and an MDS mixing layer. It even proves the S-box is a bijection — `(x⁷)^d == x` for `d = 7⁻¹ mod (p−1)` — and powers a Poseidon Merkle root. A genuine upgrade over the toy MiMC. (`examples/frost/frost_poseidon.glass`)
- Frost's README gains a **"Sharper primitives"** section gathering the drop-in upgrades: Poseidon, the recursive O(n log n) NTT, and the 128-bit bignum field.

## [4.87.0] — 2026-05-25 — A faster reference interpreter
- The reference interpreter (`glass.py`) runs the heavy STARK demos **~24% faster** — `dataclass(slots=True)` on the runtime value classes (Python 3.10+, graceful on 3.9), plus inlining the leaf-operand cases (`Ident` / `IntLit` / `BinOp`) in the binop, function-call, and tail-call paths to skip millions of `eval_expr` dispatch calls. Output is byte-identical: suite 381/381, dogfoods unchanged, Python 3.9 ≡ 3.12.
- **MIN/MAX now support `WHERE`**, so every aggregate (SUM, COUNT, AVG, MIN, MAX, GROUP BY) filters uniformly — each proven over the same committed table. (`examples/prove/prove_pane.glass`)

## [4.86.0] — 2026-05-25 — The complete aggregate set
- Pane's query algebra (and its Frost proof backend) now covers the full analytics surface over a committed private table: **SUM, COUNT, AVG, MIN, MAX, and GROUP BY**, on top of equality / boolean / arithmetic / `<`–`>` range filters. (`examples/pane/pane.glass`, `examples/prove/prove_pane.glass`)
- **AVG** is revealed as a proven `sum` + `count` (a finite field has no exact division, so the verifier forms the average); **MIN/MAX** claim a value and prove it is both a *bound* (via the range gadget) and *present* (via an inverse hint); **GROUP BY** decomposes into per-group filtered sums — each proven over the *same* committed table.
- `run_query` and the prover stay in lockstep: the circuit ACCEPTs exactly when its answer equals the reference interpreter's.

## [4.85.0] — 2026-05-25 — Pane ⊕ Frost: zero-knowledge queries
- The founding vision, realized: commit a **private table**, then prove the result of a query — revealing only the commitment, the query, and the answer, never a row. (`examples/prove/prove_query`)
- **Frost as a second backend over the real Pane query algebra**: a genuine Pane `Query` value (`SumQ`/`CountQ`/`Where`) is *lowered* into a Frost circuit — equality, booleans, arithmetic, and `<`/`>` range comparisons — with one AST and two evaluators (`run_query` interprets, `prove_pane` proves) kept honest by their agreement. (`examples/prove/prove_pane`)
- **A committed-table query in zero-knowledge**: a SUM, and a `WHERE`-filtered SUM, over a committed private column — lowered to the blinded F_{p⁴} FRI STARK, succinct and leaking nothing. The PLONK gate identity gains a `qassert` selector so the binding/result assertions and the filter's is-zero gadget ride inside the low-degree quotient. (`examples/prove/prove_query_zk`)
- The reference interpreter now **rejects uppercase value bindings** — an uppercase name is a constructor, and binding one as a value silently miscompiled — closing a glass.py ⟷ compiler divergence.

## [4.84.0] — 2026-05-25 — A 128-bit bignum field, a hardened runtime, and a written semantics
- A **production-width field**: a 128-bit prime (2¹²⁸ − 159) built from base-2¹⁶ bignum limbs — arithmetic that overflows a single int64 now works limb-by-limb, and self-hosts byte-for-byte. (`examples/frost/frost_field`)
- **Hardened the native runtime**: the emitted `run_command` uses process-unique temp files with cleanup (no more fixed-`/tmp` clobber); the bootstrap fixpoint still closes byte-identically.
- **Tooling**: `dogfood.sh` runs the self-host differential check in one command, and `docs/semantics.md` writes down Glass's big-step operational semantics.

## [4.83.0] — 2026-05-25 — Structured match, a unified bridge, and self-host tooling
- The prove bridge compiles structured **`match` on ADTs** — a value becomes a `(tag, fields…)` wire-tuple, dispatched by tag and bound by field. (`examples/prove/prove_adt`)
- A **unified front end** proves real multi-function Glass programs — function calls, `match`, `if`, `==`, and arithmetic all interacting. (`examples/prove/prove_full`)
- **`dogfood.sh`** runs any file on both `glass.py` and the self-hosted compiler and checks byte-identical output — the differential-testing discipline as one command; plus a `glass --quiet` flag that suppresses declaration echoes. (`examples/selfhost/dogfood.sh`)

## [4.82.0] — 2026-05-25 — The prove bridge closes the loop: Glass source → a succinct, zero-knowledge proof
- Write a Glass function, get a STARK proof of its execution that is sound, succinct, *and* zero-knowledge — the circuit is lowered through a PLONK arithmetization, copy constraints (a z-accumulator permutation), a gate-constraint quotient, and a blinded FRI over F_{p⁴}. (`examples/prove/prove_stark`, `prove_copy`, `prove_quotient`, `prove_zk`, `prove_zperm`)
- The bridge now also handles **function calls** (by inlining) and **`match`** (scalar dispatch), over real prism-parsed Glass. (`prove_calls`, `prove_match`)
- Developer experience: a standard **prelude** (`examples/lib/prelude.glass` — `nth`, `take`/`drop`, `zip`, Option/Result helpers), a `glass --version` flag, and parser/type diagnostics that *explain* the common gotchas (uppercase = constructor, tuple-vs-`Pair`).
- Performance: a recursive **O(n log n) NTT** replaces the O(n²) transform under evaluate/interpolate/FRI. (`frost_ntt`)

## [4.81.0] — 2026-05-24 — Docs & repo: a cinematic pass
- README rewritten around the macro idea — transparency, carried from a type signature to a zero-knowledge proof.
- Examples reorganized so the repo reads itself: Frost split into its own folder, per-folder guides, a navigation index.
- Changelog condensed from ~11k lines to a couple of bullets per version.

## [4.80.0] — 2026-05-24 — The prove bridge: write Glass, get a proof
- A Glass expression compiles to a Frost circuit + witness and is proved correct for a secret input.
- `prove_glass` parses REAL Glass source with Glass's own front end (prism) and proves it — arithmetic, comparisons, booleans, `if`/`let`.

## [4.79.0] — 2026-05-24 — Frost goes cryptographic, and zero-knowledge
- An extension field F_{p⁴} (~2¹²⁴) built in int64; FRI fold challenges and a permutation argument drawn from it.
- Amplified Fiat-Shamir query sampling and trace blinding — cryptographic soundness and the actual zero-knowledge property.
- The capstone: one end-to-end zk-STARK proving a computation that is sound, succinct, *and* zero-knowledge.

## [4.78.0] — 2026-05-24 — Frost: a zk-STARK from scratch
- Own finite field, MiMC hash, Merkle trees, and arithmetic-circuit arithmetization.
- Polynomial interpolation, the FRI low-degree test, and an AIR that proves a computation via a low-degree quotient.

## [4.77.0] — 2026-05-24 — Pane: a query language in Glass
- A small, total, deterministic query algebra + reference interpreter, shaped so the same AST can be lowered into a zero-knowledge circuit (Frost).

## [4.76.0] — 2026-05-24 — Self-hosting: the bootstrap fixpoint closes
- Glass self-hosts.

## [4.75.0] — 2026-05-24 — Glass compiles Glass: native_glassc compiles prism.glass identically
- The self-hosting payoff.

## [4.74.0] — 2026-05-24 — A native Glass compiler (Phase B/C: glassc.glass)
- Glass now compiles Glass, natively.

## [4.73.0] — 2026-05-24 — Quartz Phase A4: prism.glass RUNS identically (keystone milestone)
- The asterisk is gone.

## [4.72.0] — 2026-05-24 — Quartz Phase A4: prism.glass compiles and links
- The keystone compile milestone — with an honest asterisk.

## [4.71.0] — 2026-05-24 — Quartz Phase A1/A2: effects compile, prism is now the target
- First release of the off-Python migration

## [4.70.0] — 2026-05-24 — A module system: `import`, and the end of copy-pasted cores
- The most practical feature on the table, and one I kept hitting.

## [4.69.0] — 2026-05-24 — Field-level refinements: data that carries its own invariant
- The gap units.glass hit, closed.

## [4.68.0] — 2026-05-24 — Linear types in prism: Glass self-hosts its own substructural check
- Parity, and a self-hosting milestone.

## [4.67.0] — 2026-05-24 — Linear / resource types: the first feature the type checker had to grow for
- The phase change.

## [4.66.0] — 2026-05-24 — Physical types: dimensional analysis and conservation laws
- My additions to the backlog, and the last showcase-style bundle.

## [4.65.0] — 2026-05-24 — Information & Observation: who's looking, how deep, and what leaks
- Second Tier-2 bundle.

## [4.64.0] — 2026-05-24 — Time & Causality: partial-order time, intervention, identity-over-time
- First Tier-2 bundle (now unblocked).

## [4.63.0] — 2026-05-24 — Rationals & Probability: the no-floats decision, made well
- The architectural fork I'd been flagging, resolved.

## [4.62.0] — 2026-05-24 — Strategy & Worlds: the Dilemma's tragedy and many-worlds nondeterminism
- Last unblocked Tier-1 bundle.

## [4.61.0] — 2026-05-24 — Quantum II: entanglement and the interference that isn't classical
- Fourth bundle, and the deepest physics so far.

## [4.60.0] — 2026-05-24 — Epistemic-games & Symmetry: groups as data, knowledge as worlds
- Third bundle from the buildable cluster.

## [4.59.0] — 2026-05-24 — Self-Similarity & Spirals: the same shape, all the way down
- Second bundle from the buildable cluster.

## [4.58.0] — 2026-05-24 — Proportion & Form: refinements that encode mathematical truths
- First bundle from the "exotic types" backlog.

## [4.57.0] — 2026-05-24 — Quantum-inspired measurement: the first of the "exotic types" backlog
- A new direction begins.

## [4.56.0] — 2026-05-24 — Cross-parameter refinements: a later param's predicate can reference an earlier one
- Closing the v4.55 carve-out.

## [4.55.0] — 2026-05-24 — Quartz refinement predicates: recursive compiler replaces the shape-matcher
- Retiring the growing match cascade.

## [4.54.0] — 2026-05-24 — Logical NOT `!` — the boolean operator trio is complete
- Closing the boolean operator set.

## [4.53.0] — 2026-05-24 — Modulo `%` lands — parity / divisibility refinements compile
- Glass couldn't lex %.

## [4.52.0] — 2026-05-23 — `&&` and `||` in prism — host/prism parity restored
- Closing v4.51's deferred work.

## [4.51.0] — 2026-05-23 — `&&` and `||` land — range refinements compile through Quartz
- A long-standing language gap closes.

## [4.50.0] — 2026-05-23 — Quartz refinement coverage: let-bindings + lambda params
- v4.49 follow-on, scoped exactly to the two carve-outs that release named.

## [4.49.0] — 2026-05-23 — Refinements reach Quartz: param + return runtime checks in compiled C
- Refinement-type story finally crosses the native boundary.

## [4.48.0] — 2026-05-23 — Multi-param lambdas in prism close the host parity gap
- Follow-on to v4.47.

## [4.47.0] — 2026-05-23 — Refined-param lambdas: predicates fire on every apply
- Fourth and final step of the staged lambdas plan.

## [4.46.0] — 2026-05-23 — Quartz multi-arg lambdas + map / filter / fold
- Third step of the lambdas arc. Map/filter/fold compile end-to-end.

## [4.45.0] — 2026-05-23 — Quartz capturing closures: free-variable analysis + capture marshalling
- Second step of the lambdas arc.

## [4.44.0] — 2026-05-23 — Quartz lambdas (first cut): non-capturing closures compile to native
- The biggest open Quartz item starts landing.

## [4.43.0] — 2026-05-23 — Carry-forward bundle: range builtin, wrap_int64, cast-bridge factored
- Three small open carry-forward items, closed together.

## [4.42.0] — 2026-05-23 — Bitwise ops batch lands in host + Quartz
- Six builtins, identical semantics through host and Quartz.

## [4.41.0] — 2026-05-23 — char_at resolves: codepoint semantics in host + Quartz, prism's String version preserved as internal
- The longest-standing item from the carry-forward list closes.

## [4.40.0] — 2026-05-23 — string_to_upper / string_to_lower land in BOTH host and Quartz
- The first v4.x release that adds to the host's builtin surface.

## [4.39.0] — 2026-05-23 — Quartz builtins batch 2: len, head, tail, reverse, string_index_of
- Five more host-prelude builtins land.

## [4.38.0] — 2026-05-23 — Quartz gains three string builtins: string_length, substring, int_to_string
- New arc begins.

## [4.37.0] — 2026-05-23 — Quartz structural `==` complete: generic sum types (Option, Result, user-declared)
- The structural-eq arc closes.

## [4.36.0] — 2026-05-23 — Quartz structural `==` capstone: records and concrete sum types
- The structural-eq arc closes for every type Quartz can construct except generic sum types.

## [4.35.0] — 2026-05-23 — Quartz structural `==` recurses through nested List and Tuple
- The smallest release in the structural-eq arc.

## [4.34.0] — 2026-05-23 — Quartz structural `==` extends to primitive-element List and Tuple
- Building on v4.33's loud-error scaffolding.

## [4.33.0] — 2026-05-23 — Quartz `==` sweep: Strings get content-eq, boxed types fail loudly
- The silent-miscompilation sweep flagged in v4.32 — closed for ==.

## [4.32.0] — 2026-05-23 — Quartz `++` becomes type-polymorphic — list-concat lands
- A silent-miscompilation bug closed.

## [4.31.0] — 2026-05-23 — Quartz lists: cons-chain in q_value_t
- Second step in the resumed Quartz arc.

## [4.30.0] — 2026-05-23 — Quartz arc resumed: tuples compile to native
- The Quartz arc was last touched at v4.20.

## [4.29.0] — 2026-05-23 — Honest perf release: ChainMap experiment failed, findings recorded
- A release whose headline deliverable is a calibrated finding, not a feature.

## [4.28.0] — 2026-05-23 — Tail-call elimination in the host — unbounded tail recursion
- Switched arcs from prism-parity to host performance.

## [4.27.0] — 2026-05-23 — Parens-after-let parser fix ports to prism
- v4.21's host fix, finally mirrored in prism.

## [4.26.0] — 2026-05-23 — Division `/` lands in prism — textbook safe_div finally runs
- The canonical refinement-types demo, end-to-end in prism.

## [4.25.0] — 2026-05-23 — Return-type refinement runtime checks land in prism
- v4.24's queued item, closed.

## [4.24.0] — 2026-05-23 — Refinement runtime checks reach all curried params via VRefinedClos
- v4.23's deferred item, closed.

## [4.23.0] — 2026-05-23 — Refinement runtime checks land in prism (first-param top-level fns)
- The refinement story in prism gets its missing chunk.

## [4.22.0] — 2026-05-23 — Quartz monomorphization fix — generic fns over ADTs round-trip cleanly
- The 2 baseline-failing Quartz tests, flagged honestly in v4.21, now pass.

## [4.21.0] — 2026-05-23 — Parens-after-let parser fix + drift catch on misdiagnosed AGENT.md §5
- One real parser bug closed. One mis-documented language gotcha retired.

## [3.17.0] — 2026-05-22 — Parser extends: ADTs + match
- Glass-side parser handles algebraic data types and pattern matching.

## [4.20.0] — 2026-05-22 — calc with parens + djb2 hash (zero compiler changes, pure proof points)
- Two real algorithms in compiled Glass, no compiler changes.

## [4.19.0] — 2026-05-22 — typed parameters + parameter-type-aware return inference (chronic foot-gun gone)
- The recurring foot-gun across v4.12, v4.13 is fixed.

## [4.18.0] — 2026-05-22 — division `/` + calculator demo (a real interpreter in compiled Glass)
- The strongest end-to-end proof point yet.

## [4.17.0] — 2026-05-22 — hex literals (`0xFF`, `0xcafe`)
- Hex literals close the readability gap from v4.16.

## [4.16.0] — 2026-05-22 — bitwise builtins (direction #2 advances)
- Direction #1 was symbolic strings. Direction #2 is numeric — v4.16 lands its first installment.

## [4.15.0] — 2026-05-22 — `string_index_of` (symbolic-string vocabulary complete)
- Search closes the symbolic-string toolkit.

## [4.14.0] — 2026-05-22 — `substring` + `string_at` (palindrome checker compiles)
- The slicing toolkit completes the symbolic-string vocabulary.

## [4.13.0] — 2026-05-22 — `string_length`, `string_to_upper`, `string_to_lower` (focused stdlib for symbolic strings)
- Three idiomatic string builtins.

## [4.12.0] — 2026-05-22 — `>=`, `<=` + `int_to_char` (Caesar cipher compiles)
- Caesar cipher in pure Glass, compiled to native.

## [4.11.0] — 2026-05-22 — `char_at` builtin (symbolic string processing foundation)
- Compiled Glass programs can now inspect strings character-by-character.

## [4.9.0] — 2026-05-22 — Two foot-guns closed: string semantic equality + identifier mangling
- Both lurking quirks fixed in one release.

## [4.8.0] — 2026-05-22 — Inequality (`!=`) + block comments (`/* ... */`)
- Two surgical small wins.

## [4.7.0] — 2026-05-22 — Equality + logical operators (primality test compiles)
- ==, &&, || work end-to-end.

## [4.6.0] — 2026-05-22 — Unary minus + modulo (Euclidean GCD compiles)
- Two small operator additions unlock real number-theory programs.

## [4.5.0] — 2026-05-22 — Line comments + honest performance roadmap
- Source files can now have # comments.

## [4.4.0] — 2026-05-22 — Direct file read in selfcompile + newlines as whitespace
- Real .glass files on disk now self-compile.

## [4.3.0] — 2026-05-22 — Nested PCtor sub-patterns + nullary ctor fix
- Patterns can now descend into nested ADT structure.

## [4.2.0] — 2026-05-22 — Fn-chain return-type inference via fixed-point
- Chains of string-returning fns now propagate correctly.

## [4.1.0] — 2026-05-22 — String escape sequences in parser
- Parser handles \n, \", \\ escapes.

## [4.0.0] — 2026-05-22 — Stage 5 endpoint — `selfcompile.glass` drives full self-compile pipeline
- Glass compiles Glass via Glass-side scripts, end to end.

## [3.20.0] — 2026-05-22 — Parser reaches feature parity — generics + multi-type fields + fn return-type tracking
- The Glass-side parser now handles every AST shape quartz_min handles.

## [3.19.0] — 2026-05-22 — Parser extends: string literals + concatenation
- Glass-side parser handles strings.

## [3.18.0] — 2026-05-22 — Parser extends: records + field access
- Glass-side parser handles records.

## [3.17.0] — 2026-05-21 — Parser extends: ADTs + match
- Glass-side parser handles algebraic data types and pattern matching.

## [3.16.0] — 2026-05-21 — Parser extends: fn decls, ECall, if/else, comparison
- Recursive factorial parses end-to-end through Glass.

## [3.15.0] — 2026-05-21 — Parser extends: identifiers + let bindings
- Glass-side parser handles let.

## [3.14.0] — 2026-05-21 — Source to native, all in Glass — `quartz_parser.glass`
- Glass parses Glass source.

## [3.13.0] — 2026-05-21 — Glass drives cc — `write_file`, `run_command`, end-to-end build pipeline
- Glass can now compile and run native binaries from inside Glass.

## [3.12.0] — 2026-05-21 — Quartz-in-Glass: multi-type fields + generics (via boundary discipline)
- Two big roadmap items close with one small codegen fix.

## [3.11.0] — 2026-05-21 — Quartz-in-Glass: strings (EStr, EConcat, String results)
- Quartz-in-Glass handles strings.

## [3.9.0] — 2026-05-21 — Quartz-in-Glass: records + field access
- Quartz-in-Glass handles records.

## [3.8.0] — 2026-05-21 — Quartz-in-Glass: ADTs + pattern matching
- Quartz-in-Glass handles algebraic data types.

## [3.7.0] — 2026-05-21 — Quartz-in-Glass: identifiers, let, fn calls
- Quartz-in-Glass grows.

## [3.6.0] — 2026-05-21 — Quartz, written in Glass (first piece)
- The Stage 5 piece arrives.

## [3.5.0] — 2026-05-21 — Quartz: generic functions
- Generic functions compile to native C.

## [3.4.0] — 2026-05-21 — Quartz: generic ADTs and generic records
- Generic types compile to native C.

## [3.3.0] — 2026-05-21 — Quartz: records
- Records compile to native C.

## [3.2.0] — 2026-05-21 — Quartz: ADTs + pattern matching
- Sum types compile to native C.

## [3.1.0] — 2026-05-21 — Quartz: functions
- Top-level functions compile to native C.

## [3.0.0] — 2026-05-21 — Quartz (first prototype)
- Quartz arrives.

## [2.16.0] — 2026-05-21
- Quartz design document.

## [2.15.0] — 2026-05-21
- Stage 4.5 — the self-host milestone.

## [2.14.0] — 2026-05-21
- Refinements port chunk 3: implication discharge in prism.

## [2.13.0] — 2026-05-21
- Refinements port chunk 2a: alpha-equivalence discharge in prism.

## [2.12.0] — 2026-05-21
- Refinement types port to prism — chunk 1: parsing + constant-fold discharge.

## [2.11.0] — 2026-05-21 — *v2.10 skipped per version contract*
- Parameterized record literal type inference in prism — the second gap from v2.9's Stage 4.5 attempt closed.

## [2.9.0] — 2026-05-21
- Generic fn declarations in prism, surfaced by a Stage 4.5 attempt.

## [2.8.0] — 2026-05-21
- Markdown-to-HTML converter library in Glass.

## [2.7.0] — 2026-05-21
- Plain let with patterns.

## [2.6.0] — 2026-05-21
- Config-file parser library in Glass — let* and let? paying off in real code.

## [2.5.0] — 2026-05-21
- let? syntactic sugar for Option threading.

## [2.4.0] — 2026-05-21
- let* syntactic sugar for Result threading.

## [2.3.1] — 2026-05-21
- Patch release.

## [2.3.0] — 2026-05-21
- AGENT.md.

## [2.2.0] — 2026-05-21
- A real Glass library: JSON parser.

## [2.1.0] — 2026-05-21
- Browser playground.

## [2.0.0] — 2026-05-21
- Maturity release.

## [1.9.0] — 2026-05-21
- Real interactive REPL.

## [1.8.0] — 2026-05-21
- Pair and Result pre-declared in prism.glass.

## [1.8.0] — 2026-05-21
- Scaling up Stage 4: midlang.glass — a Glass-in-Glass interpreter with closures, lambdas, let-bindings, and recursion.

## [1.7.0] — 2026-05-21
- Interpreter performance pass.

## [1.6.0] — 2026-05-21
- Reflexive feature coverage expansion.

## [1.5.0] — 2026-05-21
- Meta-circular evaluation.

## [1.4.0] — 2026-05-21
- Implication-based subsumption and dual licensing.

## [1.3.0] — 2026-05-21
- Refinement composition.

## [1.2.0] — 2026-05-21
- Static refinement discharge.

## [1.1.0] — 2026-05-21
- Showcase release.

## [1.0.0] — 2026-05-21
- Stage 3 self-host achieved.

## [0.9.7] — internal release
- - Function types (A) -> B in parse_type (split into parse_type and parse_type_atom, with optional effect on the arrow).

## [0.9.6] — internal release
- - print builtin with !{IO} effect.

## [0.9.5]
- - Top-level fn declarations with mutual recursion via VMutRecClos(name, body_expr, all_decls, outer_env).

## [0.9.4]
- - First-class String type (TyStr, VStr, EStr).

## [0.9.0 – 0.9.3] — internal releases
- Records with named fields, generic ADTs (TyAdt with type params), pattern matching with exhaustiveness checking, recursion via let rec, subtraction/multiplication/comparisons, tuples, list literals [...] with spread [h, ...t].

## [0.0 – 0.8] — early development
- Initial language design: pure functional core, Hindley-Milner type inference, ADTs, pattern matching, immutability, effect rows.
