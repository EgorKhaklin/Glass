# TIER-1 sound prover/verifier — concrete soundness budget (WIP, branch only)

> **Status: WIP on branch `tier1-soundness-wip`. NOT shipped, NOT on `main`, NOT
> audited.** These are *reasoned pen-and-paper* bounds, not machine-checked or
> audited. The "do not protect real value" boundary stands.
>
> **HASH-WIDTH NOTE (2026-05-30): caught, then FIXED.** The audit-readiness pass found
> the end-to-end soundness was **capped at ~32-bit** by the hash width (`hashg` returned
> one ~64-bit lane → ~2⁻³² Merkle/transcript binding). **Fixed:** `hashg` now outputs 4
> lanes (~128-bit binding), so the ~80-bit figures below are no longer hash-capped
> (validated native). Residual: with-replacement query sampling → effective distinct < 82.
> See [`audit-readiness.md`](audit-readiness.md) and [`tier1-soundness-proof.md`](tier1-soundness-proof.md).

This note records the re-derived concrete soundness budget for the
`A + B1 + B2 + B3` sound path in `examples/prove/prove_source_goldilocks_zk.glass`,
after the B3 copy/permutation argument grew the FRI coset to 32N (tested degree
`< 4N`). It was produced by an adversarial three-lens review with independent
synthesis (workflow `war1fs5ob`), then the load-bearing precondition (a genuinely
witness-free verifier that re-derives **every** Fiat-Shamir challenge) was checked
against the source.

## The construction (what each layer buys)

| Layer | Soundness it adds |
|---|---|
| TIER-0 statement-seeding | challenges depend on the statement; cross-statement proofs REJECT |
| A — independent `verify(gates, proof)` | re-derives all FS challenges from public gates + proof commitments; never touches the witness; forged openings/roots/nonce REJECT |
| B1+B2 — OOD-`z` identity + DEEP-batched FRI | the committed quotient is tied to the gate constraints on a committed trace → **per-row gate soundness** (P=0 / any unrelated low-degree codeword REJECTS) |
| B3 — PLONK grand-product copy constraint | the committed trace is a **consistent wire assignment** (one value per wire) → a per-row-valid but wire-inconsistent trace REJECTS |

A native run demonstrates each: honest **ACCEPT**; `P=0`, cross-statement,
tampered-trace, and **wiring-inconsistent** all **REJECT**.

## The bit budget (union bound over additive error terms; all challenges in F_{p²}, log₂(p²) ≈ 128)

Parameters: rate **ρ = 1/8** (coset 32N, tested degree `< 4N` ⇒ 4N/32N = 1/8 —
deliberately preserved from the pre-B3 16N/2N), **82 queries**, real **12-bit
grind**, `fri_final = 8`.

**Dominant term — FRI query phase:**
- *Provable* (unique-decoding, δ = (1−ρ)/2 = 7/16): per-query survival 9/16 ⇒
  `−log₂(9/16) = 0.830` bits/query; `82 × 0.830 = 68.0` + 12 grind = **~80-bit
  provable** (`ε ≈ 2⁻⁸⁰`).
- *List-decoding* (δ up to `1−√ρ = 0.646`): `1.50` bits/query ⇒ `82 × 1.5 = 123`
  + 12 = **~135-bit list-decoding** — **CONJECTURAL**, leaning on the FRI
  proximity-gap / decoding-to-capacity line (Ben-Sasson, Bentov, Horesh,
  Riabzev *et al.*); the same assumption modern STARKs make, but not a proven
  bound at this δ. Never quote it without that caveat.

**Negligible structural / commit terms** (each ≥ 27 bits below the FRI floor for
any realistic N; sized at trace size N):
- FRI commit phase (`log₂(4N)` rounds × 32N domain / p²): ≈ 2⁻⁹⁸ at N = 2²⁰.
- Permutation grand-product Schwartz-Zippel (3N factors in β, γ_p): `3N/p²` ≈ 2⁻¹⁰⁶ at N = 2²⁰.
- OOD constraint identity at z (committed degree ~4N): `4N/p²` ≈ 2⁻¹⁰⁶ at N = 2²⁰.
- α constraint-combination (3 families, deg-2 in α): ≤ `3/p²` ≈ 2⁻¹²⁶.
- γ DEEP-batch binding (6 quotients {Q,l,r,o,Z@z,Z@ωz}): `6/p²` ≈ 2⁻¹²⁵.

So `ε_total ≈ ε_FRI_query ≈ 2⁻⁸⁰`; the bit-count is governed by ρ and the query
count, **not** by N. **B3 adds wire-consistency soundness without degrading the
bit-count.** (At the prior 64 queries the figure is ~65-bit provable / ~108
list-decoding; 82 queries was chosen for a conjecture-free 80-bit provable
headline, at 1.28× proof size / query-extraction cost — cheap given the v5.41
memoized Merkle trees.)

## What may and may NOT be claimed

**May:** "complete structural soundness *design* (statement-seeding, independent
witness-free verifier, per-row gate soundness via OOD+DEEP-FRI, B3 grand-product
wire-consistency) with a re-derived **~80-bit provable** / ~135-bit list-decoding
(conjectural) query-phase soundness; reasoned pen-and-paper bounds."

**Must NOT:**
- not "soundness axis complete" / "in-repo-complete" — the malicious-prover
  soundness is **reasoned, not proven**; a formal soundness reduction is the
  biggest remaining in-repo gap.
- not "out of research grade" / "audit-ready" / "production" as settled fact —
  the external audit is the gate. Only "research-grade, audit-pending."
- not any bit number as "machine-verified" / "proven" / "formally verified."
- not the list-decoding number **bare** (always the conjectural caveat).
- not "80-bit" for the CLI `glass prove` **default** — that is the
  Baby-Bear-retired Goldilocks per-row path at 64 queries; the ~80-bit figure
  is for `verify_b3` (the v5.48.0 sound+ZK construction), not the CLI default.

ZK is now **implemented** on this path via a randomized trace (`build_claim_zk`,
v5.48.0) — the earlier "ZK suspended" caveat no longer applies; hiding is HVZK /
NIZK-in-ROM, reasoned-not-machine-checked (see [`tier1-zk-design.md`](tier1-zk-design.md)).

## Remaining in-repo work toward production-readiness (none of which is the audit)

1. ✅ A **pen-and-paper soundness reduction** now exists —
   [`tier1-soundness-proof.md`](tier1-soundness-proof.md) reduces soundness to named
   theorems (FRI proximity, DEEP, PLONK permutation, FS-in-ROM) + stated assumptions.
   Remaining: a **machine-checked** reduction (Lean/Coq) — not producible quickly
   in-repo, and arguably the audit's job.
2. **Re-add ZK** (trace randomization) so the sound path stops opening the witness.
3. ✅ Fiat-Shamir gaps **closed**: the protocol **parameters are now absorbed into
   `stmt_seed_of`** (gen 7, blowup 32, fold-stop 8, queries 82, grind 12), and the
   **final folded codeword is absorbed before query sampling** (`absorb_final`). Out
   of scope for this theorem (separate obligations): **compiler correctness** (that
   prism/cgen lowers the source faithfully) and **pinning the witness to the CLI
   inputs** (it proves "R is *some* valid output," not "R = f(*these* inputs)").

And then the **hard boundary, never producible in-repo**: an external
professional audit + community cryptanalysis of the composed construction
(including the conjectural list-decoding regime and a constant-time review of the
limb field). Until that exists, this is educational/research-grade and must not
protect real value.
