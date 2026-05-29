# Parameters & concrete soundness

`docs/soundness.md` says, plainly, that Glass's cryptographic parameters are
*educational-grade*. This document makes that precise: it writes down every
parameter of the two proving paths, the standard FRI soundness bound, and the
**actual bit-security those parameters give** — then the recipe to reach a real
target. No hand-waving: every number below is read from the code, and where the
answer is "weak," it says so.

> **Bottom line.** The *challenge space* is already cryptographic-width
> (≈2¹²⁴–2¹²⁸). The historical weak link was the **FRI query phase** — too few
> queries at too high a rate. The **Goldilocks path is now hardened**: a 1/8 rate
> (blowup 8) + 64 queries + a 12-bit grind give **~65-bit provable / ~108-bit
> list-decoding** query soundness (up from ~3–4 bits raw, ~25–28 after the first
> pass). The **default Baby Bear path** is now **also ρ=1/8** (~53 provable / ~96
> list-decoding bits, v5.43) — but its **2³¹ value space** (a secret is brute-forceable
> independent of the proof) is the binding weakness there, not the FRI. Neither path
> yet uses a vetted in-STARK hash (still MiMC), and an external audit remains; §4 has
> the recipe.

---

## 1. The parameters, as built

| Parameter | Default (`glass prove`) | `glass prove --goldilocks` |
|---|---|---|
| Base field | Baby Bear, p = 2³¹−2²⁷+1 | Goldilocks, p = 2⁶⁴−2³²+1 |
| **Value space** | **~2³¹ (secrets brute-forceable; wraps >2.1·10⁹)** | **~2⁶⁴** |
| Trace domain | n (gate count) | 16 |
| FRI domain (coset) | 16·n (blowup 8 over the degree-2n bound) | 256 (blowup 8 over the degree-32 bound) |
| Tested degree | < 2n (deg-3 gate ÷ Z_H; fold stops at len 8) | < 32 (fold fixed at 5 rounds, stop at domain/32) |
| **Rate ρ = deg/domain** | **= 1/8** | **= 1/8** |
| **FRI queries ℓ** | **64** | **64** |
| Fold challenge (Fiat-Shamir) | F_{p⁴} ≈ 2¹²⁴ | F_{p²} ≈ 2¹²⁸ |
| Hash | MiMC, 16 rounds (x⁵) | MiMC, 4 rounds (x⁷) |
| ZK blinding | random low-degree mask | degree-16 mask |
| Grinding (PoW) | none | **12 bits** |

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

**Default path — Baby Bear, ρ = 1/8, ℓ = 64.** (Until v5.43 this path folded to
length 2 over a 4n coset, which — since the quotient has degree ~2n, the `qm·l·r`
gate ÷ Z_H — certified only degree < 2n at rate 2n/4n = **1/2** (~10–12 bits), *not*
the 1/4 the table once claimed. v5.43 grew the coset to 16n and stops the fold at
length 8, certifying degree < 2n at rate 2n/16n = **1/8**, and raised queries 24 → 64.)
- Unique decoding: survival (1+ρ)/2 = 9/16 → ε_query ≤ (9/16)⁶⁴ ≈ **2⁻⁵³**.
- List decoding: survival √ρ ≈ 0.354 → ε_query ≤ 0.354⁶⁴ = **2⁻⁹⁶**.
- → **~53 bits provable / ~96 bits list-decoding** of query soundness (no grinding on
  this path). **But the *value space is 2³¹*** — a private input can simply be
  enumerated in ~2³¹ work, independent of the proof — so *that*, not the FRI, is now
  the binding weakness of the default path (→ the Goldilocks-ADT migration is the fix).

**Goldilocks path — ρ = 1/8, ℓ = 64, + 12-bit grinding.**
- Unique decoding: survival (1+ρ)/2 = 9/16 → (9/16)⁶⁴ ≈ 2⁻⁵³·¹; **+12 grind → ~2⁻⁶⁵**.
- List decoding: survival √ρ = √(1/8) ≈ 0.354 → 0.354⁶⁴ = 2⁻⁹⁶; **+12 grind → ~2⁻¹⁰⁸**.
- → **~65 bits provable / ~108 bits list-decoding** of query soundness, up from
  ~25–28 (ρ=1/2, 32 q) and ~4 (8 q, no grind). This spends **two cheap levers
  together**: (1) a **lower rate** — the FRI coset grew 64 → 256 (blowup 8), with the
  fold fixed at 5 rounds stopping at domain/32 so the *tested degree stays 32* while
  ρ drops to 1/8 (folding all the way to length 2 would instead leave ρ pinned at
  1/2 — no gain); and (2) **more queries** — 32 → 64, nearly free since v5.41
  **memoized** the FRI layer Merkle trees (built once in `commit_g`, paths read from
  the stored levels). The rate lever costs ~4× the quotient/commit work (the
  interpreter-dogfood gate); the query lever is the cheap one — which is why the
  conservative *provable* bound climbs fastest by spending queries.

The **Goldilocks path now reaches a cryptographic target by the list-decoding
standard** modern STARKs use: ρ=1/8 + 64 queries + 12-bit grind ≈ **2⁻¹⁰⁸**, past
80 bits. By the conservative *provable* (unique-decoding) bound it is **~65 bits** —
strong, not yet 80. The **default Baby Bear path is now also ρ=1/8** (~53 provable /
~96 list-decoding, v5.43); its remaining weakness is the **2³¹ value space**, not the
FRI. The honest one-line summary: **both query phases are now hardened (ρ=1/8) — but the
in-STARK hash is still educational MiMC, the default path's values are still 2³¹, and
there is no external audit.**

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
or **~40 queries + 20-bit grinding**. The Goldilocks path now **ships at blowup 8
(ρ=1/8) + 64 queries + 12-bit grind** — past 80 bits by the list-decoding standard
(~108), ~65 by the conservative provable one. 128-bit scales the query count by ~1.6×.
Each step multiplies FRI work (bigger coset → more NTT/quotient/hashing), which is
why the demos ship at low parameters: the reference interpreter would otherwise
take hours per proof. The levers, in priority order:

1. **Lower the rate** (bigger blowup) — the most efficient bits-per-query (but the
   priciest: the cost is the quotient evaluation over the bigger coset). **Applied on
   both paths: ρ 1/2 → 1/8** — Goldilocks (coset 64 → 256, fold stops at domain/32) and
   Baby Bear (coset 4n → 16n, fold stops at length 8). The fold round count is fixed in
   both, so the tested degree is unchanged while ρ drops.
2. **More queries** — linear in soundness, and the *cheapest* lever. On Goldilocks it's
   cheap because the committed Merkle trees are **memoized** (built once in `commit_g`,
   paths read from stored levels); on Baby Bear it's cheap because its layer trees are
   now **memoized too** (v5.43, the same technique ported over — the dogfood went
   ~32 min → ~2.5 min, 13×). **Applied: Goldilocks 8 → 32 → 64; Baby Bear 24 → 64.**
3. **Grinding** — a flat `+g` bits for `2^g` prover hashes (standard in
   production STARKs); cheap on proof size and verification. **Applied (g=12) on the
   Goldilocks path.**
4. **A vetted hash** (the verified Goldilocks Poseidon, already built — see
   `frost_goldilocks_poseidon.glass`) wired into the Merkle/transcript, so the
   commitments rest on a standard permutation rather than the educational MiMC.

None of this changes the **differential-testing** guarantee (which is rigorous and
independent of these parameters). And none of it replaces an **external audit**.

*(See `docs/soundness.md` for the full ledger, and `docs/roadmap.md` Track R.)*
