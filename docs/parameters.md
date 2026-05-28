# Parameters & concrete soundness

`docs/soundness.md` says, plainly, that Glass's cryptographic parameters are
*educational-grade*. This document makes that precise: it writes down every
parameter of the two proving paths, the standard FRI soundness bound, and the
**actual bit-security those parameters give** — then the recipe to reach a real
target. No hand-waving: every number below is read from the code, and where the
answer is "weak," it says so.

> **Bottom line.** The *challenge space* is already cryptographic-width
> (≈2¹²⁴–2¹²⁸). The weak link is the **FRI query phase**: too few queries at too
> high a rate. At today's demo parameters the query-phase soundness is only
> **~16 bits (Baby Bear)** / **~3–4 bits (Goldilocks)** — fine for a demonstration,
> not for protecting value. Reaching 80–128 bits is a matter of *more queries +
> a lower rate (bigger blowup) + grinding*, all of which cost prover time; the
> recipe is in §4.

---

## 1. The parameters, as built

| Parameter | Default (`glass prove`) | `glass prove --goldilocks` |
|---|---|---|
| Base field | Baby Bear, p = 2³¹−2²⁷+1 | Goldilocks, p = 2⁶⁴−2³²+1 |
| **Value space** | **~2³¹ (secrets brute-forceable; wraps >2.1·10⁹)** | **~2⁶⁴** |
| Trace domain | n (gate count) | 16 |
| FRI domain (coset) | 4·n | 64 |
| Tested degree | < n | < 32 |
| **Rate ρ = deg/domain** | **≈ 1/4** | **= 1/2** |
| **FRI queries ℓ** | **24** | **8** |
| Fold challenge (Fiat-Shamir) | F_{p⁴} ≈ 2¹²⁴ | F_{p²} ≈ 2¹²⁸ |
| Hash | MiMC, 16 rounds (x⁵) | MiMC, 4 rounds (x⁷) |
| ZK blinding | random low-degree mask | degree-16 mask |
| Grinding (PoW) | none | none |

(Source: `examples/prove/prove_source_adt_zk.glass` and
`examples/prove/prove_source_goldilocks_zk.glass`.)

---

## 2. The soundness bound

A FRI-based STARK proof can be forged in two ways; the soundness error is the sum.

**(a) Commit phase — guessing the Fiat-Shamir fold challenges.** Each fold
challenge is derived (Fiat-Shamir) from the Merkle roots and lives in the
extension field. A prover who tries to grind a favorable challenge succeeds with
probability bounded by roughly

  ε_commit ≈ (number of rounds · max degree) / |F_ext|.

With |F_ext| ≈ 2¹²⁴ (Baby Bear, F_{p⁴}) or 2¹²⁸ (Goldilocks, F_{p²}) and a handful
of rounds over a degree < 64 codeword, ε_commit ≈ 2⁻¹¹⁵ or smaller. **This part is
cryptographic-width** — it is not the problem.

**(b) Query phase — a codeword that is *not* low-degree slipping past the spot
checks.** If the committed codeword is δ-far (relative Hamming distance) from the
rate-ρ Reed–Solomon code, each of the ℓ independent queries catches it with
probability ≥ δ, so

  ε_query ≤ (1 − δ)^ℓ.

How large δ can be taken depends on the decoding regime:

- **Unique decoding (provable):** δ ≤ (1 − ρ)/2, so the per-query *survival*
  factor is (1 − δ) = (1 + ρ)/2.
- **List decoding / proximity gaps (the bound modern STARKs use):** δ up to
  1 − √ρ, survival factor √ρ. (Conjectured to capacity; the proximity-gap
  results of Ben-Sasson et al. justify it in practice. We quote both so nothing
  is hidden.)

Total: **ε ≈ ε_commit + (1 − δ)^ℓ ≈ (1 − δ)^ℓ.**

---

## 3. Plugging in the actual numbers

**Default path — Baby Bear, ρ ≈ 1/4, ℓ = 24.**
- Unique decoding: survival (1+ρ)/2 = 5/8 → ε_query ≤ (5/8)²⁴ ≈ **2⁻¹⁶·³**.
- List decoding: survival √ρ = 1/2 → ε_query ≤ (1/2)²⁴ = **2⁻²⁴**.
- → **~16–24 bits** of query soundness. But the *value space is 2³¹* — a private
  input can simply be enumerated, independent of the proof. That is the dominant
  weakness of this path.

**Goldilocks path — ρ = 1/2, ℓ = 8.**
- Unique decoding: survival (1+ρ)/2 = 3/4 → ε_query ≤ (3/4)⁸ ≈ **2⁻³·³**.
- List decoding: survival √ρ ≈ 0.707 → ε_query ≤ 0.707⁸ ≈ **2⁻⁴·⁰**.
- → **~3–4 bits** of query soundness. The field is real (2⁶⁴), but the FRI is
  tuned for *interpreter speed*, not security: high rate (1/2) and only 8 queries.

Neither is cryptographically sound today. The honest one-line summary: **the
challenge space is real; the query phase is a demonstration.**

---

## 4. The recipe to a real target

Query soundness is `ℓ · log₂(1/survival) + g` bits, where `g` is grinding bits.
Lowering the rate ρ (a bigger blowup) raises the per-query yield; grinding adds a
flat `g` bits at the cost of `2^g` prover hashes. To reach **~80 bits** (list-
decoding survival = √ρ):

| Rate ρ | Blowup | bits/query | queries ℓ for 80 (no grind) | with g = 20 grind |
|---|---|---|---|---|
| 1/2  | 2×  | 0.50 | 160 | 120 |
| 1/4  | 4×  | 1.00 | 80  | 60  |
| 1/8  | 8×  | 1.50 | ~54 | ~40 |
| 1/16 | 16× | 2.00 | 40  | 30  |

So a concrete 80-bit configuration: **blowup 8 (ρ=1/8), ~54 queries, no grinding**,
or **~40 queries + 20-bit grinding**. 128-bit scales the query count by ~1.6×.
Each step multiplies FRI work (bigger coset → more NTT/quotient/hashing), which is
why the demos ship at low parameters: the reference interpreter would otherwise
take hours per proof. The levers, in priority order:

1. **Lower the rate** (bigger blowup) — the most efficient bits-per-query.
2. **More queries** — linear, cheap on the verifier, more prover commitment work.
3. **Grinding** — a flat `+g` bits for `2^g` prover hashes (standard in
   production STARKs); cheap on proof size and verification.
4. **A vetted hash** (the verified Goldilocks Poseidon, already built — see
   `frost_goldilocks_poseidon.glass`) wired into the Merkle/transcript, so the
   commitments rest on a standard permutation rather than the educational MiMC.

None of this changes the **differential-testing** guarantee (which is rigorous and
independent of these parameters). And none of it replaces an **external audit**.

*(See `docs/soundness.md` for the full ledger, and `docs/roadmap.md` Track R.)*
