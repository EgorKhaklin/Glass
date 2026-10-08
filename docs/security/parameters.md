# Parameters & concrete soundness

> **Default = Goldilocks + Poseidon2.** The default `glass prove` proves over Goldilocks
> (p = 2⁶⁴−2³²+1) with the Poseidon2 hash (byte-exact to Plonky3) and verifies with the
> witness-free `verify_b3`. The legacy Baby Bear + MiMC path remains behind `--baby-bear` for
> comparison. Security level: **~80-bit (unique decoding)**; the ~135-bit list-decoding figure is
> **conjectural** (proximity gaps). Proof size: a comparison proof `a<b` is ~154k stream tokens
> (a denser hash encoding plus Merkle-path deduplication). Nothing here lifts the UNAUDITED /
> do-not-protect-real-value banner. See the [internal audit](internal-audit-2026-06.md).

[`soundness.md`](soundness.md) says the cryptography is research/educational-grade. This
document makes that precise: every parameter of the two proving paths, the standard FRI
soundness bound, the **bit-security those parameters give**, and the recipe for a higher
target. Every number is read from the code, and where the answer is weak, it says so.

---

## 1. The parameters, as built

| Parameter | `--baby-bear` (legacy) | **Default `glass prove` (Goldilocks)** |
|---|---|---|
| Base field | Baby Bear, p = 2³¹−2²⁷+1 | Goldilocks, p = 2⁶⁴−2³²+1 |
| **Value space** | **~2³¹ (secrets brute-forceable; wraps >2.1·10⁹)** | **~2⁶⁴** |
| Trace domain | n (gate count) | N = next power of two ≥ gate count |
| FRI domain (coset) | 16n | 32N (coset generator 7) |
| Tested degree | < 2n (fold stops at length 8) | < 4N (the permutation quotient has degree ~3N; fold stops at 32N/4N = 8) |
| **Rate ρ = deg/domain** | **1/8** | **1/8** |
| **FRI queries ℓ** | **64** | **82, sampled without replacement** |
| Fold challenge (Fiat-Shamir) | F_{p⁴} ≈ 2¹²⁴ | F_{p²} ≈ 2¹²⁸ |
| Hash | MiMC, 16 rounds (x⁵); one field element per node | **Poseidon2 (t=12, R_F=8/R_P=22, x⁷; byte-exact to Plonky3)**, 4-lane output (~256-bit, ~128-bit collision binding) |
| Zero-knowledge | random low-degree mask on the quotient codeword | none by default (not hiding); `--zk` adds ≥256 random dummy trace rows |
| Grinding (PoW) | none | **12 bits** |

(Source: `examples/prove/prove_source_adt_zk.glass` and
`examples/prove/prove_source_goldilocks_zk.glass`. The Goldilocks protocol parameters are also
bound into the statement seed, so a verifier with different parameters derives different
challenges.)

---

## 2. The soundness bound

A FRI-based STARK proof can be forged in two ways; the soundness error is the sum.

**(a) Commit phase: guessing the Fiat-Shamir fold challenges.** Each fold
challenge is derived (Fiat-Shamir) from the Merkle roots and lives in the
extension field. A prover who tries to grind a favorable challenge succeeds with
probability bounded by roughly

  ε_commit ≈ (number of rounds · max degree) / |F_ext|.

With |F_ext| ≈ 2¹²⁴ (Baby Bear, F_{p⁴}) or 2¹²⁸ (Goldilocks, F_{p²}) and a handful
of rounds, ε_commit ≈ 2⁻¹¹⁵ or smaller. **This part is cryptographic-width.**

**(b) Query phase: a codeword that is *not* low-degree slipping past the spot
checks.** If the committed codeword is δ-far (relative Hamming distance) from the
rate-ρ Reed–Solomon code, each of the ℓ independent queries catches it with
probability ≥ δ, so

  ε_query ≤ (1 − δ)^ℓ.

How large δ can be taken depends on the decoding regime:

- **Unique decoding (provable):** δ ≤ (1 − ρ)/2, so the per-query *survival*
  factor is (1 − δ) = (1 + ρ)/2.
- **List decoding / proximity gaps (the bound modern STARKs use):** δ up to
  1 − √ρ, survival factor √ρ. Conjectured to capacity; the proximity-gap results of
  Ben-Sasson et al. justify it in practice. Both are quoted so nothing is hidden.

Total: **ε ≈ ε_commit + (1 − δ)^ℓ ≈ (1 − δ)^ℓ.**

---

## 3. Plugging in the actual numbers

**Default path: Goldilocks, ρ = 1/8, ℓ = 82, 12-bit grind.**
- Unique decoding: survival (1+ρ)/2 = 9/16 → (9/16)⁸² ≈ 2⁻⁶⁸; **+12 grind → ~2⁻⁸⁰**.
- List decoding: survival √(1/8) ≈ 0.354 → 0.354⁸² ≈ 2⁻¹²³; **+12 grind → ~2⁻¹³⁵**.
- → **~80 bits provable / ~135 bits list-decoding** of query soundness. `glass prove`
  prints this on its `security:` line, computed from the live parameters (`provable_bits` =
  ⌊82·83/100⌋ + 12, `listdecode_bits` = ⌊82·3/2⌋ + 12); `measure_difftest.glass` pins the
  arithmetic.

The rate comes from a fixed fold: FRI stops at 32N/4N = 8, so the tested degree stays
< 4N while the coset is 32N. Folding all the way to length 2 would test a higher degree and
leave ρ at 1/2, with no gain. The provable margin is thin: 68 query bits + 12 grind bits =
80 exactly, so any erosion drops below 80. The 4-lane hash keeps commitment binding
(~128-bit) above that floor; a single-lane hash would cap the whole proof at ~32 bits.

**Legacy path: Baby Bear, ρ = 1/8, ℓ = 64, no grind.** The coset is 16n and the fold stops
at length 8, so the tested degree is < 2n at rate 2n/16n = 1/8.
- Unique decoding: (9/16)⁶⁴ ≈ **2⁻⁵³**.
- List decoding: 0.354⁶⁴ ≈ **2⁻⁹⁶**.
- → ~53 bits provable / ~96 bits list-decoding of query soundness. **But** the value space
  is 2³¹ (a private input can be enumerated in ~2³¹ work, independent of the proof), and its
  MiMC Merkle hash outputs one ~31-bit field element per node, so commitment binding is far
  weaker than the FRI figures. This is why Goldilocks is the default.

**Summary.** Both query phases run at ρ = 1/8. The default path reaches ~80 bits by the
conservative provable bound and ~135 by the conjectural list-decoding bound. Its hash is
Poseidon2, matched to Plonky3's vectors but not cryptanalyzed here, and there is no external
audit.

---

## 4. The recipe to a higher target

Query soundness is `ℓ · log₂(1/survival) + g` bits, where `g` is grinding bits.
Lowering the rate ρ (a bigger blowup) raises the per-query yield; grinding adds a
flat `g` bits at the cost of `2^g` prover hashes. To reach **~80 bits** by the
list-decoding bound (survival √ρ):

| Rate ρ | Blowup | bits/query | queries ℓ for 80 (no grind) | with g = 20 grind |
|---|---|---|---|---|
| 1/2  | 2×  | 0.50 | 160 | 120 |
| 1/4  | 4×  | 1.00 | 80  | 60  |
| 1/8  | 8×  | 1.50 | ~54 | ~40 |
| 1/16 | 16× | 2.00 | 40  | 30  |

The default path instead targets 80 bits by the *provable* bound (~0.83 bits/query at
ρ = 1/8), which is why it uses 82 queries. 128-bit scales the query count by ~1.6×. Each
step multiplies FRI work (bigger coset, more NTT/quotient/hashing), which is why demos run
at reduced parameters on the interpreter. The levers, in priority order:

1. **Lower the rate** (bigger blowup): the most bits per query, but the priciest (the
   quotient is evaluated over the bigger coset). Applied on both paths: ρ = 1/8.
2. **More queries**: linear in soundness and the cheapest lever, because the committed
   Merkle trees are memoized (built once, paths read from stored levels). Applied: 82
   (Goldilocks), 64 (Baby Bear).
3. **Grinding**: a flat `+g` bits for `2^g` prover hashes; cheap on proof size and
   verification. Applied: g = 12 on Goldilocks. The proof-of-work check reads one 16-bit
   limb, so the printed grind term is capped at 16 bits until that check is widened.
4. **A vetted hash**: applied on the default path (Poseidon2 drives the Merkle commitments
   and the transcript). The Baby Bear path keeps MiMC.

None of this changes the **differential-testing** guarantee (which is independent of
these parameters), and none of it replaces an **external audit**.
