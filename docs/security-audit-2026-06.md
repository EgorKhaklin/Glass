# Glass — internal security audit (2026-06-04)

**Verdict: the "research/educational-grade · UNAUDITED · do-not-protect-real-value" banner STAYS.**
This was an *internal* adversarial review. An internal review — however thorough — is not an
external audit, and it cannot perform the Poseidon cryptanalysis the soundness assumption rests on.
Both are **irreducibly external** (see §5). What this audit *did* do: independently re-derive the
math, hunt for soundness/ZK/implementation bugs across 10 dimensions, fix the one real
mislabelling it found, and produce the audit-readiness picture below.

## Method

A 10-agent read-only adversarial review (one reviewer per dimension), each instructed to *break* the
construction and grounded in the actual code (`prove_source_goldilocks_zk.glass`, `pentecost/`,
`examples/frost/frost_goldilocks*.glass`, `glass.py`, the docs). Reviewers re-derived results
independently (e.g. confirming `7` generates `F_p*` via the full factorization of `p−1`, that
`root_pow2(k)` is a primitive 2ᵏ-th root, that the LDE coset is disjoint from the trace domain) rather
than trusting the in-repo references. Two dimensions (the lowering gadgets; the Third Witness +
fuzzing) are covered by the project's existing suite gates + the other reviewers' cross-coverage.

## Findings — severity tally

| Severity | Count | Disposition |
|----------|-------|-------------|
| CRITICAL | 0 | — |
| HIGH | 1 | **fixed v5.118** |
| MEDIUM | 4 | 1 fixed, 3 documented/roadmapped |
| LOW | 16 | doc hygiene + defensive guards — fixed/roadmapped |
| INFO | 27 | confirmations of honest scope + posture |

**No live soundness hole was found in the reachable prover paths.** The arithmetization, grand-product
permutation, Fiat-Shamir ordering, statement-binding, grinding, and field/NTT math were each judged
internally sound by independent re-derivation. The issues are a ZK mislabelling (now fixed), latent
landmines behind implicit invariants, conjecture-dependent headline numbers, and stale documentation.

### HIGH — `--zk` hiding silently failed on circuits larger than ~90 gates (FIXED, v5.118)

`build_claim_zk` padded the trace with `k = targetN − glen(gs)` random "dummy" rows, and
`zk_dummy_gates` short-circuits `if k <= 0 then []`. With the CLI's hardcoded `targetN = 256`, any
circuit with **≥ 256 gates got zero hiding rows** — yet the proof was still labelled
"SOUND + zero-knowledge". The hiding argument requires the dummy-row count to exceed the ~170-value
opening surface (`2·fri_queries + OOD/trace openings`); below that, the openings can reveal witness
rows. **Fix:** `zk_pad_k` floors the dummy-row count at **256 (> the opening surface, with margin)**
for *any* circuit size, so a `--zk` proof is genuinely hiding regardless of circuit size (a larger
circuit gets a larger — but actually-hiding — proof). Verified: `glass prove --zk` on a comparison
(~700 gates, previously 0 hiding rows) now ACCEPTs with ≥256 random rows. *(The default `glass prove`
is, and was always honestly documented as, **not** zero-knowledge — the witness is opened in the clear;
ZK is the opt-in `--zk`. The mislabelling was only within `--zk`.)*

### MEDIUM

- **`q_gold_comb` truncates a non-canonical (>4-limb) limb list mod 2⁶⁴ while the Python oracle reduces
  mod p** — an unguarded interp/native divergence. *Not reachable* in honest paths (every field element
  is canonical by construction via `glit`/`q_gold_split`), but the canonical-form precondition is
  implicit and unguarded — exactly the silent-desync class. **Roadmapped:** assert the canonical-form
  invariant at the `gold_*` boundary (touches bootstrap `glassc.glass`, so deferred to a dedicated
  fixpoint-gated change) + add a non-canonical fuzz case.
- **The ~135-bit list-decoding headline rests on a conjectural FRI proximity-gap (decoding-to-capacity)
  assumption.** Already disclosed in `docs/audit-readiness.md` and `docs/parameters.md`. The
  conjecture-free **80-bit (unique-decoding)** figure is the one to trust as the security level.
  **Documented** here and in the refreshed `parameters.md`.
- **`--zk` uses a fixed CLI seed (11111)**, so re-proving a statement yields an identical proof — the
  "two seeds → two different valid proofs" re-randomization property fails in practice (single-proof
  hiding still holds with the v5.118 row-count fix). **Roadmapped:** draw the `--zk` mask seed from a
  CSPRNG per invocation. The mask-RNG-as-ideal remains a disclosed honest-scope caveat.
- **Docs presented "~240 dummy rows ≫ openings" as universal** — it was an artifact of the tiny demo at
  the fixed `targetN`. The v5.118 floor makes the dummy-row count ≥256 > openings for all sizes, so the
  claim now holds generally; the docs are corrected.

### LOW (16) — doc hygiene + defensive guards

Stale documentation contradicting live parameters (`docs/parameters.md` listed Baby Bear + MiMC as the
default — the live default is Goldilocks + Poseidon2; `with-` vs `without-replacement` query comments;
`blowup 16` vs `32`; version/test-count drift across surfaces; the `pentecost/README.md` dual status).
The misleading ones are **corrected in v5.118**; the rest are tracked. Defensive guards (an explicit
ABSTAIN if trace size exceeds Goldilocks 2-adicity `fri_log(n) > 32`, ~2²⁷ gates, practically
unreachable; an explicit OOD-point-outside-domain assertion; documenting the `finv(0)=0` convention as
"not a field inverse") are **roadmapped** — defense-in-depth, not live holes.

### INFO (27) — confirmations

The gate identity enforces every gate variant; every `GHint` advice wire is pinned by a downstream
enforced gate; the grand-product boundary + cyclic transition correctly force the telescoping product
to 1; commit-then-challenge ordering holds throughout (no challenge derivable before its commitment);
the statement (gate list + claimed result) is fully bound into the transcript; grinding correctly
raises the query-sampling cost; the Poseidon2 parameters are the standard Plonky3 secure set (not
reduced) across all three implementations; the random-oracle assumption is stated honestly and
prominently; the two-verifier scope (catches implementation divergence, *not* a shared-spec misread)
is honestly represented; both verifiers re-derive every challenge.

## What is internally hardened (the audit-readiness story)

- **Two independent verifiers** (`verify_b3` in Glass; `pentecost/` in plain Python int-mod-p, sharing
  no Glass code) agree on every emitted proof via `difftest.sh` — catching an implementation divergence
  the compiler fixpoint cannot.
- **The Third Witness** re-runs the source under the reference interpreter (a lineage independent of the
  bridge's evaluator *and* its circuit lowering), catching a source↔circuit lowering gap the two
  circuit-verifiers structurally cannot.
- **Differential fuzzing** across 6 program families + boundary inputs + 1,600 adversarial tampers, all
  with zero wrong-ACCEPTs.
- **The self-hosting fixpoint** (`native_glassc` reproduces its own source + program output
  byte-identically) and the **Name** (a content-addressed Poseidon-Merkle root over the whole core),
  both suite-gated.
- Machine-checkable reductions retired the "reasoned-not-machine-checked" caveat for the B3 path.

These materially raise confidence and are exactly what an external auditor would build on. **They are
not a substitute for the external audit.**

## §5 — What it would take to lift the banner (irreducibly external)

1. **An independent, external, professional security audit** of the construction and the implementation
   (the protocol soundness reduction, the ZK proof, the implementation, the parameter choices). A
   self-review is not an audit by definition.
2. **Poseidon2 cryptanalysis** by hash-function specialists. The entire soundness *and* ZK bound is
   conditional on Poseidon2 behaving as a random oracle / being collision- and preimage-resistant. If
   that assumption fails, the bound is vacuous. This cannot be produced in-repo.
3. Discharging the conjectural FRI proximity-gap assumption to the capacity bound (or pricing security
   at the proven unique-decoding bound — already the conservative headline).
4. Retiring the remaining idealizations (the mask RNG; per-invocation `--zk` randomness).

Until (1) and (2) — the hard, external requirements — are met, the construction stays **research /
educational-grade, UNAUDITED**, and the **do-not-protect-real-value** banner remains. That is not a
formality: it is the honest statement of what has and has not been verified, and removing it would be a
false security claim.
