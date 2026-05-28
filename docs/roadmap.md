# Glass Roadmap — toward the verifiable frontier language

*(written thinking as Glass)*

## What Glass is

- A pure functional language: ADTs, records, tuples, HM inference, refinement
  types, effect rows, linear types, pattern matching.
- **Self-hosting**: `native_glassc` compiles itself and `prism` byte-identically,
  with no Python in the loop (the bootstrap fixpoint).
- **Proven in anger**: Pane (a query algebra) and Frost (a from-scratch zk-STARK
  — field, MiMC hash, Merkle trees, arithmetization, FRI, AIR) — all written in
  Glass, all self-hosted.
- **A discipline, not just a language**: every layer is a *reference semantics*
  plus a *compiler* that must agree bit-for-bit, kept honest by differential
  testing. glass.py ⟷ quartz/glassc. eval ⟷ circuit. run_query ⟷ Frost.

## The frontier bet

Most languages optimize for one of: expressiveness, performance, or proof.
Glass's distinctive position is the *seam* it already lives on — reference ⟷
compiler agreement — generalized to: **spec, implementation, and proof in one
self-hosting language.**

The unique edge: **ZK-native computation** — write a Glass function, get a
zero-knowledge proof of its execution. No mainstream functional language does
this. Glass already built the whole STARK toolkit; the bet is to make it a
language feature, not a library you assemble by hand.

> **Thesis — Glass, the verifiable functional language.** You write what a
> program *means*, what it *does*, and you get a machine-checkable proof it did.

## Honestly de-prioritized (and why)

- **Dependent types / full theorem proving** — enormous; refinement types plus
  ZK proofs already give a real verification story. Revisit once the bridge lands.
- **Performance (the int64 type-erased backend)** — real, but not what makes
  Glass distinctive yet. Correctness and the ZK bridge come first.
- **Mainstream DX (package manager, IDE plugins)** — matters for adoption, not
  for the frontier edge. A partial DX pass (prelude, diagnostics) is Phase 4.

## Shipped (through v5.33)

- **Self-hosting** — the bootstrap fixpoint (`prism` + `glassc`, no Python).
- **Pane** — a query language in Glass.
- **Frost** — a from-scratch zk-STARK toolkit: finite field + an **F_{p⁴}
  extension** (cryptographic challenge space), hashes (MiMC, and a proper
  **Poseidon** — `x⁷` permutation S-box, full/partial rounds, MDS), Merkle trees,
  arithmetization, FRI (with Fiat-Shamir query sampling + amplification),
  AIR, **ZK blinding**, a **permutation argument** (copy constraints), and an
  **end-to-end zk-STARK** that's sound, succinct, and zero-knowledge.
- **The prove bridge** — write *real Glass source* (parsed by prism), get a
  proof: arithmetic, comparisons, booleans, `if`/`let`. *(Today this emits a
  sound RLC proof, not yet the succinct ZK STARK — see N1.)*

## What's next

- **N1 — Close the loop: source → succinct ZK proof. ✅ DONE.** The prove-bridge
  circuit is lowered into the cryptographic STARK backend: PLONK arithmetization
  (`prove_stark`) → copy constraints via the permutation argument (`prove_copy`)
  → gate-constraint quotient (`prove_quotient`) → blinded + FRI over F_{p⁴}
  (`prove_zk`). `write Glass → a *succinct, zero-knowledge* proof` is now real and
  self-hosted (honest ACCEPT / tampered REJECT / two blindings reveal different
  openings). Remaining rigor: fold the permutation into a FRI'd z-accumulator
  quotient so the wiring is succinct too (tracked under N4).
- **N2 — Widen the bridge. ✅ DONE.** Function calls (`EApp`, by inlining —
  `prove_calls`) and `match` (scalar dispatch via a selector-multiplexer —
  `prove_match`). The bridge now covers arithmetic, comparisons, booleans,
  `if`/`let`, calls, and `match` over real prism-parsed Glass. Remaining:
  structured patterns (`PCtor`/`PTuple` → multi-wire tagged values), tracked under N4.
- **N3 — Developer experience. ✅ DONE.** A standard prelude
  (`examples/lib/prelude.glass` — `nth`, `take`/`drop`, `zip`, Option/Result
  helpers); parser/type diagnostics that *explain* the gotchas (uppercase =
  constructor; tuple-vs-`Pair`); a `--version` flag. (The "monomorphic length"
  papercut was self-inflicted — `len` is already polymorphic.)
- **N4 — Performance & crypto rigor. ✅ DONE.** Recursive O(n log n) NTT
  (`frost_ntt`), the z-accumulator succinct permutation (`prove_zperm`),
  structured-`match` ADT values in circuits (`prove_adt`), a **128-bit bignum
  field** past the single-int64 cap (`frost_field`, mod 2¹²⁸−159, all int64-safe),
  and hardened emitted C (`run_command` uses process-unique temp files + cleanup).
- **N5 — Tooling. ✅ DONE.** `dogfood.sh` — differential self-host testing as one
  command; a `glass --quiet` flag; and a written
  [operational semantics](semantics.md) making glass.py's de-facto spec explicit.

## Beyond N1–N5 — the next horizon

N1–N5 reached the founding thesis: *write Glass, get a zero-knowledge proof.*
What's next is making that proof matter — moving from "it can prove" to "it
proves the things the project was for."

> **The thesis, unified end to end** ([`prove_source_zk.glass`](../examples/prove/prove_source_zk.glass)):
> real multi-function Glass source, parsed by prism, lowered to a circuit (calls
> inlined, arithmetic → gates, output bound to a public claim via `qassert`), and
> proven with the blinded F_{p⁴} FRI STARK — *succinct and zero-knowledge*. The
> two halves that were apart (real-source front end in `prove_glass`/`prove_calls`,
> the ZK STARK backend in `prove_zk`/`prove_query_zk`) are now one file: write a
> Glass function, get a proof of its result. (Hint-free subset — arithmetic + let +
> calls; `==`/`if` ride the RLC bridge until their inverse-hint wires are added.)

- **H1 — Pane ⊕ Frost: zero-knowledge queries. 🚧 IN PROGRESS.** The founding
  vision (*Frost = the ZK extension of Pane*): commit a private table, run a Pane
  query, prove *"query Q over the committed table yields R"* — revealing only Q,
  the commitment, and R.
  - ✅ **The idea, end to end** ([`prove_query.glass`](../examples/prove/prove_query.glass)):
    `SELECT SUM(salary) WHERE dept = target` over a *private* table, with a binding
    fingerprint commitment (C = Σ flatᵢ·γⁱ, a Reed–Solomon/poly-eval commitment)
    tying the witness to the public commitment. Honest ACCEPT; lying about the
    result or the table REJECTs; differential-tested, byte-identical.
  - ✅ **Frost as a second backend over the real Pane algebra**
    ([`prove_pane.glass`](../examples/prove/prove_pane.glass)): a genuine Pane
    `Query` value (`SumQ`/`CountQ`/`Where` with `EqE`/`AndE`/`OrE`/`NotE`/arith
    gadgets, **and `LtE`/`GtE` order comparisons via a 17-bit range gadget**) is
    *lowered* into a Frost circuit — one AST, two evaluators (`run_query`
    interprets, `prove_pane` proves), with the discipline that they agree.
    pane.glass's stated plan, realized.
  - ✅ **The payoff — a committed-table query in zero-knowledge**
    ([`prove_query_zk.glass`](../examples/prove/prove_query_zk.glass)): a SUM over
    a committed private column — and a `SUM … WHERE` *filtered* query — lowered to
    the blinded F_{p⁴} FRI STARK (the `prove_zk` backend), succinct and leaking
    nothing. The PLONK gate identity gained a `qassert·(l−r)` selector so the
    binding/result assertions *and the filter's is-zero gadget* ride inside the
    low-degree quotient (the gadget's inverse hint is supplied as an input wire,
    not a gate row). Honest ACCEPT, lies REJECT, two blinding seeds give different
    openings (ZK). Self-hosted byte-identical.
  - ✅ **The full aggregate set** (`pane.glass` + `prove_pane.glass`): Pane's
    algebra gains `AvgQ`, `MinQ`, `MaxQ`, and `GroupByQ(keyCol, sumCol, groups, sub)`,
    each proven over the *same committed table*. GROUP BY decomposes to per-group
    filtered sums; AVG is a proven `sum` + `count` (a field has no exact division,
    so the verifier divides); MIN/MAX claim `M` and prove it's a *bound* (`M ≤ sᵢ` /
    `sᵢ ≤ M` for every row via the range gadget) and *present* (`Σ[sᵢ == M] ≠ 0`, by
    an inverse hint). `GROUP BY dept` → eng 250 / sales 170; `AVG(salary) WHERE
    dept=eng` → 250/2 (avg 125); `MIN/MAX(salary)` → 80 / 150 — each ACCEPT (lies
    REJECT), Frost == Pane.
  - **Next:** a bigger field (H2) — but note the FRI challenges already live in
    F_{p⁴}≈2¹²⁴, so the *challenge space* is already cryptographic; the toy part
    is the small base field (value range) and the MiMC hash. Lifting the range
    gadget into the ZK backend (~90 gates/comparison) is feasible but slow.
  - **Hardened the discipline along the way:** glass.py now rejects uppercase
    value bindings (they silently miscompiled — glassc read them as constructors);
    `dogfood.sh`'s build seed was fixed (it was seeding the wrong path).
- **H2 — A cryptographic prover. 🚧 IN PROGRESS.** Wire a real field through the
  FRI/quotient so the end-to-end proof has cryptographic security, not the toy
  base field.
  - ✅ **The field STARKs actually use, built from scratch**
    ([`frost_goldilocks.glass`](../examples/frost/frost_goldilocks.glass)):
    **Goldilocks** p = 2⁶⁴ − 2³² + 1 (Plonky2, RISC Zero), with its signature
    division-free reduction (2⁶⁴ ≡ 2³² − 1), a real Fermat inverse (p − 2 overflows
    int64, so the exponent is walked in limbs), and the **2³²-th root of unity**
    that gives radix-2 NTT layers for any practical trace. All int64-safe via
    base-2¹⁶ limbs — so it dogfoods (Python bignum ≡ C int64). (A 128-bit field
    `frost_field` exists too, from N4.)
  - ✅ **FRI over Goldilocks — the core engine on the real field**
    ([`frost_goldilocks_fri.glass`](../examples/frost/frost_goldilocks_fri.glass)):
    the STARK's low-degree test runs over p = 2⁶⁴ − 2³² + 1. The evaluation domain
    is a real 2ᵏ-th-root-of-unity subgroup (using the field's 2-adicity), the fold
    `(f(x)+f(−x))/2 + β·(f(x)−f(−x))/(2x)` uses the limb-walked inverse, and a
    low-degree codeword folds to a constant while a tampered one doesn't — all
    int64-safe, dogfooded. (Base-field β for now; the degree-2 extension challenge
    space + Merkle/Fiat-Shamir are the layers on top, as in the Baby Bear path.)
  - ✅ **F_{p²} ≈ 2¹²⁸ — the cryptographic challenge space**
    ([`frost_goldilocks_ext.glass`](../examples/frost/frost_goldilocks_ext.glass)):
    the degree-2 extension F_{p²} = F_p[X]/(X² − 7) over Goldilocks (W = 7 is a
    non-residue: 7^((p−1)/2) = −1), with norm-based inversion that stays int64-safe
    (a⁻¹ = conj(a)·N(a)⁻¹, N(a) ∈ F_p inverted by the base Fermat inverse). FRI now
    folds with β ∈ F_{p²} (≈2¹²⁸ per-round soundness, not a guessable 2⁶⁴): honest
    codeword folds to a constant, tampered doesn't. Int64-safe, dogfooded.
  - ✅ **A committed, query-verified FRI — the cryptographic STARK core, complete**
    ([`frost_goldilocks_stark.glass`](../examples/frost/frost_goldilocks_stark.glass)):
    every layer's codeword is Merkle-committed (a Goldilocks MiMC hash, x⁷ S-box),
    the fold β ∈ F_{p²} is derived from the root (Fiat-Shamir), and the verifier
    samples query positions from the transcript, opens each (f(x), f(−x)) pair with
    a Merkle path, recomputes the fold, and checks it against the next layer. An
    honest low-degree codeword ACCEPTs (0 faults); a faked final layer REJECTs (the
    queries catch it at every position). All three soundness mechanisms —
    commitment, cryptographic challenge, queries — over Goldilocks, int64-safe,
    dogfooded. The Baby Bear `frost_crypto` capstone, now on the production field.
  - ✅ **Zero-knowledge over Goldilocks — the arc complete**
    ([`frost_goldilocks_zk.glass`](../examples/frost/frost_goldilocks_zk.glass)): the
    codeword is masked with a random low-degree polynomial R (degree below the
    fold-to-constant bound), so f + R still folds to a constant and the proof
    ACCEPTs — but the committed root and every opened value are randomized. Two
    independent blinding seeds give two *different* valid proofs of the same
    statement (both ACCEPT; layer-0 commitment differs; opened value #5 differs):
    the verifier learns only "low-degree", nothing about f. **Sound + committed +
    zero-knowledge, over Goldilocks** — the full zk-STARK shape on the production
    field, int64-safe and dogfooded.
  - **H2 core is complete**: field → FRI fold → F_{p²} challenge → committed +
    query-verified → zero-knowledge, all over Goldilocks. The open follow-on is
    *end-to-end integration* — swapping the prove-bridge's STARK backend
    (`prove_zk`) from Baby Bear to this Goldilocks stack, so a proof of real Glass
    source runs on the production field.
- **H3 — Recursive proofs. 🚧 IN PROGRESS.** A proof that verifies another proof. The
  hard core is expressing a verifier as a circuit; a STARK verifier's algebraic
  heart is the FRI **fold check**.
  - ✅ **The fold check as a sound circuit**
    ([`prove_recursion.glass`](../examples/prove/prove_recursion.glass)): an honest
    fold path ACCEPTs, any tampered value REJECTs, and verifying a whole path is the
    FRI low-degree test re-run inside a circuit (division by an inverse-witness with
    a `w·inv == 1` gate).
  - ✅ **The fold step in zero-knowledge**
    ([`prove_recursion_zk.glass`](../examples/prove/prove_recursion_zk.glass)): that
    fold circuit lowered through the blinded F_{p⁴} FRI STARK (the `prove_zk`
    backend), so the verifier's own step is succinct and blind — opened values stay
    private. The `(2x)·inv == 1` division check rides as a `qassert` gate with the
    inverse supplied on an input wire. Honest ACCEPT, tampered REJECT, two blinding
    seeds give different openings. Self-hosted byte-identical; ~1.1s native vs ~46s
    interpreted (~42×) — exactly why the native path matters.
  - ✅ **The canonical ZK statement — knowledge of a hash preimage**
    ([`prove_preimage_zk.glass`](../examples/prove/prove_preimage_zk.glass)):
    *"I know a secret `x` with `Hash(x) = H`"*, in zero-knowledge. `Hash` is a
    2-to-1 compression from Poseidon's own heart — the **x⁷ S-box**, round
    constants, and the **MDS mix** — lowered gate-for-gate into a circuit, with the
    secret preimage on private input wires and a `qassert` forcing the truncated
    output to the public digest. Proven by the blinded F_{p⁴} FRI STARK: honest
    ACCEPT, wrong preimage REJECT, two seeds give different openings. Reduced rounds
    so it dogfoods on the interpreter; the full 30-round Poseidon runs the same way
    (`run_native.sh`).
  - **Next:** compose the fold-step verifier with `frost_zk`'s in-circuit Merkle
    membership for a full recursive STARK verifier (the opened codeword values
    authenticated against the commitment, in-circuit).
- **H4 — Performance. 🚧 STARTED.** The reference interpreter (`glass.py`) is the
  bottleneck for the heavy STARK demos (the compiled `native_glassc` is ~10× faster).
  Profiling showed the cost is sheer node-visit volume (tens of millions of
  `eval_expr`/`eval_binop`/`apply_fn` calls), not attribute access or dict copies.
  Banked a **~24% speedup** (prove_zk 28.6s → 21.8s on 3.12) with semantics-preserving
  changes: `dataclass(slots=True)` on the runtime value classes (3.10+, graceful on
  3.9), and inlining the leaf-operand cases (`Ident`/`IntLit`/`BinOp`) in `eval_binop`,
  the `Call` argument path, and the tail-call trampoline — skipping millions of
  `eval_expr` dispatch+calls. Suite 381/381, dogfoods byte-identical, 3.9 ≡ 3.12 output.
  *Honest ceiling:* a tree-walker is ~0.4µs/node; a transformative (2–5×) win needs
  closure/bytecode compilation of the AST (a larger, riskier rewrite) — or simply
  leaning on the native path, which already is the fast workhorse.

## The next era (post-v5.6) — from *demonstrated* to *real, usable, unified*

By v5.6 the founding thesis is **realized for first-order pure Glass**: the prove
bridge ([`prove_source_zk`](../examples/prove/prove_source_zk.glass),
[`prove_source_adt_zk`](../examples/prove/prove_source_adt_zk.glass)) compiles real
prism-parsed source — arithmetic, `let`, calls, comparisons/booleans, `if`, and
`match` over (nested) ADTs with (nested) patterns — into a succinct, zero-knowledge
proof of its result. Frost grew a from-scratch zk-STARK over both Baby Bear and the
production **Goldilocks** field (field → FRI → F_{p²} challenge → committed →
zero-knowledge).

The work so far went **deep on expressiveness**. The next era rebalances toward the
three under-invested axes — *realness*, *usability*, and *convergence* — on four tracks:

- **Track R — Realness** (make the proof *mean* something).
  - **R1.** Wire the **Goldilocks** stack *through the bridge* — `prove_source_*` still
    proves over toy Baby Bear F_{p⁴}; the Goldilocks STARK exists but isn't connected.
    Connecting them makes every source proof run on the production field.
    - ✅ **First step (sound, real-field)** ([`prove_circuit_goldilocks.glass`](../examples/prove/prove_circuit_goldilocks.glass)):
      a Glass arithmetic circuit proven over Goldilocks (2⁶⁴ values, no 2³¹ wrap) via
      the sound RLC with an F_{p²} ≈ 2¹²⁸ Fiat-Shamir challenge. Dogfoods byte-identical.
    - ✅ **R1b — succinct + zero-knowledge over Goldilocks** ([`prove_circuit_goldilocks_zk.glass`](../examples/prove/prove_circuit_goldilocks_zk.glass)):
      the gate-constraint quotient (`prove_quotient`'s construction ported to bignum limbs) —
      interpolate the 8 trace columns over H by inverse NTT, lift to `G(x)`, form `Q = G/Z_H`,
      and FRI-fold Q on a coset: honest → folds to a constant; tamper any wire → not low-degree,
      REJECT. Blinded with a random low-degree mask for **zero-knowledge** (two seeds → different
      openings, both ACCEPT). `f(x)=x*x+5` over a private 2⁶⁴-range input; byte-identical. The
      RLC→FRI arc, now on the production field. ✅ **Now the full cryptographic STARK:** the
      quotient codeword is embedded into F_{p²}, blinded, and each FRI layer Merkle-committed; the
      fold challenge β ∈ F_{p²} ≈ 2¹²⁸ is derived from each root (Fiat-Shamir) and sampled queries
      are opened against the commitment (honest → all verify; tampered → caught; two seeds →
      different commitments). Committed, F_{p²}-challenged, query-verified, blinded.
    - ✅ **R1c — real source through the Goldilocks STARK** ([`prove_source_goldilocks_zk.glass`](../examples/prove/prove_source_goldilocks_zk.glass)):
      the source front-end wired into the production-field backend — prism parses real Glass,
      `unroll` inlines calls/HOF, a Goldilocks `cgen` lowers `+`/`-`/`*`/`let` to gates, and the
      R1b STARK proves it. `fn sq(n)=n*n; fn f(x)=sq(x)+5; f(inp)` proves over Goldilocks (honest
      ACCEPT / tampered REJECT / ZK); byte-identical. *Write Glass source, get a proof on the real
      field.* *Next (the full bridge):* comparisons/`match`/ADTs over bignum (is-zero inverse-hint
      wires in the Goldilocks witness), and the heavier circuits (native-primary).
  - **R2. 🚧 IN PROGRESS.** A real hash + Fiat-Shamir hardening. ✅ **Step 1 — Grain-LFSR
    round constants** ([`frost_grain.glass`](../examples/frost/frost_grain.glass)): Poseidon's
    constants now come from the spec's Grain LFSR (80-bit state, taps
    b₀⊕b₁₃⊕b₂₃⊕b₃₈⊕b₅₁⊕b₆₂, 160-round warm-up, rejection sampling) — reproducible and
    nothing-up-my-sleeve, not hand-picked; byte-identical. ✅ **Step 2 — a domain-separated
    Fiat-Shamir transcript** on that Poseidon (`tr_init`/`tr_absorb`/`tr_challenge`, same file):
    every message and squeeze is tagged by role, so a fold challenge can't coincide with a
    query index; demonstrated determinism, domain separation, no (tag,value) collision, and
    history-binding. *Next:* cross-check the constants against the official reference test
    vectors, analyze the MDS/round counts, wire the transcript into the bridge's challenges,
    and give a formal FS-separation argument.
  - **R3. ✅ DONE.** An honest **soundness ledger** ([`soundness.md`](soundness.md)) —
    separates the strong differential-testing guarantee from the educational-grade
    cryptography, per component, with the path to production-soundness and a clear
    "do not use to protect real value" bottom line.
- **Track E — Expressiveness** (past first-order).
  - **E1. ✅ DONE (recursion).** **Bounded recursion** via a source-level **unroll
    pre-pass** (`unroll`/`inline_fn` in [`prove_source_adt_zk.glass`](../examples/prove/prove_source_adt_zk.glass)):
    a self-recursive call is inlined to a fixed depth, each call rewritten as
    `let p = arg in body` (so an argument is evaluated once — no duplicate gates), and
    the unrolled term is call-free, so the circuit generator never recurses. `fn fact(n)
    : Int where (result != 0) = if n == 0 then 1 else n * fact(n - 1)` proves
    `fact(5) = 120` over a private input *and* its own refinement, in ZK; lying REJECTs.
    The same transform runs on glass.py and native (byte-identical). Reachable via
    `glass prove` ([`fact_prove.glass`](../examples/prove/fact_prove.glass)).
  - **E1-next. ✅ DONE (recursive datatypes).** **Bounded linked lists** — `type IntList
    = Nil | Cons(Int, IntList)` — proven in ZK *with no new machinery*: the recursive
    type lays out as a fixed-width buffer (the type-directed `twidth` already bounds a
    recursive type's width by a depth fuel) and the recursive fold unrolls (E1). The two
    bounds compose. `fn suml(l) : Int where (result != 99) = match l { Nil => 0;
    Cons(h,t) => h + suml(t) }` proves `suml [5,2,3] = 10` over a private head *and* its
    refinement, in ZK; lying REJECTs; byte-identical. Via `glass prove`
    ([`list_sum_prove.glass`](../examples/prove/list_sum_prove.glass)). Progress by
    composition — the cleanest kind.
  - **E2. ✅ DONE.** **Higher-order functions** — the `unroll` pass carries an `fenv`
    mapping a function-valued parameter to the top-level fn it was passed; a call
    through such a parameter inlines that fn, so the higher-order program is
    **beta-reduced to a first-order, call-free term** (heval/cgen unchanged — no
    closures in the circuit). `fenv` threads through recursion, so a *recursive* HOF
    works: `suml(map(inc, [5,2,3])) = 13` proves correctly. The demo proves
    `twice(inc, inp) = 7` over a private input + its refinement, in ZK; lying REJECTs;
    byte-identical. Via `glass prove` ([`map_prove.glass`](../examples/prove/map_prove.glass)).
    ✅ **Now also lambda literals** (v5.21): `fenv` maps a parameter to a function *value*
    — a top-level fn or an `ELam` — so `twice(fn(n) -> n + 1, inp)` inlines the lambda
    too (a lambda's captures resolve via the enclosing `let`s). Top-level-fn HOF,
    recursion, and list folds all regression-checked with the generalized `fenv`.
- **Track U — Usability** (a *feature*, not a library you assemble by hand).
  - **U1. ✅ DONE.** **`glass prove <file.glass> [name=value …]`** — compiles the file's
    `main` into a circuit and emits a succinct, zero-knowledge proof of its result;
    command-line names are private inputs (kept in the witness). The prove logic stays
    in Glass (a driver over `prove_source_adt_zk`). `glass prove examples/prove/hello_prove.glass inp=9`
    → `result: 86`, `proof: ACCEPT`. The capability is now a command, not a demo file.
  - **U2. ✅ DONE.** A refreshed end-to-end story ([`the-story.md`](the-story.md)) from type
    signature → proof: extended past "private queries" to cover proving real programs
    (recursion/lists/higher-order) and the type's own `where`-clause in-circuit (§5), and the
    effect row generating the proof (§6) — every shown command runs, the close links the
    soundness ledger. Read the whole arc in one sitting.
- **Track C — Convergence** (the distinctive bet — Glass has types + refinements +
  effects + ZK in one self-hosting language; unify them).
  - **C1. ✅ DONE.** **Prove refinement types** — a function's return `where (P)` is
    extracted (`TyRefine(_, "result", P)`), `result` is bound to the circuit output, and
    `P` is asserted in-circuit, so the refinement *is* a ZK-checkable guarantee, and a
    function that violates its declared refinement is unprovable.
    ([`prove_source_adt_zk.glass`](../examples/prove/prove_source_adt_zk.glass): `classify`
    with `where (result == 0 || result == 1)` proves; a lying `ident` REJECTs.) The
    frontier no one else can reach — type system + prover in one self-hosting language.
  - **C2. 🚧 SEEDED.** Effects in the proof story — *reify each effect as a committed
    trace entry; the effect row is the proof's schema* ([design](effects-in-proofs.md)).
    ✅ **Step 1 — `Inference` as a committed oracle** ([`prove_inference_zk.glass`](../examples/prove/prove_inference_zk.glass)):
    `model_call`'s answer is a private witness pinned by `C = hash(prompt, ans, nonce)`;
    a downstream validator is proven over it, revealing `C` and that it passed — not the
    answer (a faithful, hiding proof of an LLM-in-the-loop computation; sound RLC, ZK STARK
    is the follow-on). ✅ **Step 2 — `Random` via the transcript** ([`prove_random_zk.glass`](../examples/prove/prove_random_zk.glass)):
    `random_int` is a draw pinned to the Fiat-Shamir transcript (commit first, then the randomness
    falls out) — a provably-fair, un-grindable dice roll, verifiable from public `(C, beacon)` while
    the seed stays private. ✅ **Step 3 — `State` via memory consistency** ([`prove_state_zk.glass`](../examples/prove/prove_state_zk.glass)):
    an access trace bound program-order-to-address-sorted by a permutation argument (grand product),
    sorted, and read-after-write checked — every read pinned to the last write, the log un-fakeable
    (the zkVM memory argument, from scratch). ✅ **Step 4 — the effect row generates the proof** ([`prove_effects_zk.glass`](../examples/prove/prove_effects_zk.glass)):
    prism parses a signature, the bridge reads the `!{…}` row off the function type, and each effect
    label becomes a proof obligation discharged by its gadget — *change the row, the schema changes.*
    The effect row IS the proof's statement. ✅ **Lowered to full ZK** (Phase 3): the `Inference`/trust-boundary ([`trust_prove.glass`](../examples/prove/trust_prove.glass)) and `Random` ([`random_prove.glass`](../examples/prove/random_prove.glass)) gadgets are now proven through the blinded F_{p⁴} FRI STARK via the bridge, not just sound RLC. ✅ `State` *read-after-write consistency* ([`state_prove.glass`](../examples/prove/state_prove.glass)) too — a committed fixed-order trace proven consistent in full ZK. ✅ The **range/comparison primitive** the general case needs now exists ([`age_prove.glass`](../examples/prove/age_prove.glass): `a >= k` via bit-decomposition, proven in ZK — *prove you're old enough without revealing your age*). ✅ and the **permutation argument** ([`permutation_prove.glass`](../examples/prove/permutation_prove.glass): a private sequence proven a permutation of a public one via the grand product, γ Fiat-Shamir'd from the witness). All three general-`State` components — permutation, range/sortedness, read-after-write consistency — are now individually ZK-provable through the bridge; ✅ **composed** into one proof ([`general_state_prove.glass`](../examples/prove/general_state_prove.glass)): permutation ⊕ read-after-write consistency over a committed trace, values private, a tampered read caught by one check or the other. The `State` arc is closed end to end.
  - **C3 — the convergence capstone. ✅ DONE.** The trust boundary, proven
    ([`prove_trust_boundary_zk.glass`](../examples/prove/prove_trust_boundary_zk.glass)): C1 ⊕ C2
    fused on LANG.md's AI-era centerpiece. A model classifier `fn classify(prompt) : Int where
    (result == 0 || result == 1) !{Inference}` — its **signature is the contract**: prism parses
    it, the effect row (`!{Inference}`) says commit the model output as an untrusted oracle, the
    return refinement (`where (P)`, predicate read off the type and evaluated) is the trust
    contract. Prove in ZK that the committed model answer satisfied P — valid bit ACCEPTs, an
    answer violating the refinement is *unprovable*, the answer stays hidden. *Untrusted AI
    output, contained by its type, proven* — the thing the type system was designed for, made a
    proof. (Realizes LANG.md §"Refinement types as trust boundary".) ✅ **Now in *full* ZK**
    ([`trust_prove.glass`](../examples/prove/trust_prove.glass)): the same check expressed as source and
    proven through the blinded F_{p⁴} FRI STARK (`glass prove`, succinct + zero-knowledge), not just
    sound RLC — `answer=1` → R=1 ACCEPT, the answer stays a private witness. Phase-3 lowering done for
    the Inference/trust-boundary gadget; `Random`/`State` remain standalone sound-RLC.
- **Substrate — Performance (P).** The interpreter dogfood is now the bottleneck
  (heavy circuits take ~10 min). A faster reference (bytecode/closure compilation) or
  promoting `native_glassc` to a co-equal dogfood oracle unblocks Tracks E and R.

**Recommended sequence:** R1 (Goldilocks through the bridge) → U1 (`glass prove`) →
then the fork C1 (prove refinements — most distinctive) or E1 (bounded recursion —
most expressive), with P whenever the dogfood pain bites. Start at **R1**: concrete,
all components built, and it retires the biggest credibility gap (the toy field).

## Success criteria (the Glass discipline)

Every item ships a differential-tested, self-hosting artifact: the reference and
the compiled/proved result agree, and `native_glassc` reproduces it byte-for-byte.
Nothing is "done" until the interpreter and the self-hosted compiler give the
same answer.
