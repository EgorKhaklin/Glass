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

## Roadmap

- **Phase 0 — DONE (this arc).** Self-hosting fixpoint; Pane; the Frost STARK
  toolkit (commitment, FRI, AIR), all self-hosted and differential-tested.
- **Phase 1 — THE PROVE BRIDGE v0 (executing now).** Compile a Glass arithmetic
  expression into a Frost constraint system + witness, then produce and verify a
  zero-knowledge proof that `y = f(secret x)`. The seam between the language and
  the prover. Differential-tested: the reference evaluator and the compiled
  circuit agree on every input.
- **Phase 2 — FULL EXPRESSION BRIDGE.** Extend the compiler to the real Glass
  AST via prism (let / if / match / calls over a bounded domain), so ordinary
  Glass functions become provable, not just a toy arithmetic AST.
- **Phase 3 — CRYPTOGRAPHIC HARDENING.** 64-bit Goldilocks or an extension field
  for a ~100-bit soundness margin; Fiat-Shamir query sampling; ZK blinding of the
  trace polynomial. Turns the educational STARK into a cryptographic one.
- **Phase 4 — DEVELOPER EXPERIENCE.** A curated prelude (stop rewriting
  `nth`/`fold`/`map` in every file); parser/type diagnostics that *explain* the
  gotchas (uppercase = constructor, tuple-vs-Pair) instead of misfiring; a formatter.
- **Phase 5 — SPEC & TOOLING.** A written operational semantics (glass.py is the
  de-facto spec — make it explicit); `glass test` as a first-class differential
  harness; `glass prove` as a CLI over Phase 1–2.

## Success criteria (verifiable, per the Glass discipline)

Every phase ships a differential-tested, self-hosting artifact: the reference and
the compiled/proved result agree, and `native_glassc` reproduces it byte-for-byte.
No phase is "done" until the interpreter and the self-hosted compiler give the
same answer.
