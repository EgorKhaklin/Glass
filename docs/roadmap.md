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

## Shipped (through v4.87)

- **Self-hosting** — the bootstrap fixpoint (`prism` + `glassc`, no Python).
- **Pane** — a query language in Glass.
- **Frost** — a from-scratch zk-STARK toolkit: finite field + an **F_{p⁴}
  extension** (cryptographic challenge space), MiMC hash, Merkle trees,
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
- **H2 — A cryptographic prover.** Wire the 128-bit bignum field (`frost_field`)
  through the FRI/quotient so the end-to-end proof has real security, not the toy
  base field. The field is built (N4); this is the integration.
- **H3 — Recursive proofs.** A proof that verifies another proof — aggregation,
  the path to scalable and on-chain-style verification.
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

The recommended next step is **H1** — it's concrete, demonstrable, uses pieces
that already exist, and is the literal payoff of the whole project.

## Success criteria (the Glass discipline)

Every item ships a differential-tested, self-hosting artifact: the reference and
the compiled/proved result agree, and `native_glassc` reproduces it byte-for-byte.
Nothing is "done" until the interpreter and the self-hosted compiler give the
same answer.
