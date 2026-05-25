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

## Shipped (through v4.84)

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

## Success criteria (the Glass discipline)

Every item ships a differential-tested, self-hosting artifact: the reference and
the compiled/proved result agree, and `native_glassc` reproduces it byte-for-byte.
Nothing is "done" until the interpreter and the self-hosted compiler give the
same answer.
