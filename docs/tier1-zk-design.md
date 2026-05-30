# Re-adding zero-knowledge to the sound path — design + implementation plan (WIP, branch)

> **Status: design only (WIP on `tier1-soundness-wip`); not yet implemented.**
> Adversarially reviewed (workflow `wq66j2t9d`, GO-WITH-FIXES). The construction is
> correct; the open item is implementation under a real perf trade-off and a
> *silent-failure trap*. Research-grade, audit-pending; do not protect real value.

The sound path (`verify_b3`) currently opens the witness columns `l,r,o`, the
grand-product `Z`, and the quotient `Q` in the clear at ~164 query points + the OOD
point. This restores zero-knowledge by **trace randomization**, without touching the
validated on-H soundness.

## Construction (low-degree masking)

Blind the **witness-derived** columns only — `l, r, o` (root1) and `Z` (root2):

    T'(x) = T(x) + Z_H(x)·R_T(x),   Z_H(x) = x^n − 1

applied at the coset-codeword level (`l'_cw[i] = lcw[i] + (coset[i]^n − 1)·R_l(coset[i])`).
`R_l, R_r, R_o` are fresh random polynomials of degree ≥ **165** (164 query rows + 1
OOD eval); `R_Z` (in `F_{p²}`, paired real/imag masks) of degree ≥ **166** (Z is
opened at `z` *and* `ωz`). **Do not** independently blind `Q` — it is
`build_q_b3(l',r',o',Z')` and inherits the randomization; an additive non-`Z_H·R`
mask on Q would break the `id_ok` identity at `z`. Selectors / const / σ stay public
and unblinded.

**Soundness preserved (byte-identical on H):** `Z_H` vanishes on H, so `l'=l`,
`r'=r`, `o'=o`, `Z'=Z` on H — every gate, the permutation recurrence (both `x` and
`ωx` lie in H), and the boundary `Z(1)=1` are unchanged. `G' = G(l',r',o')` is still
divisible by `Z_H` (it agrees with G on H), so `Q' = G'/Z_H` is a genuine
polynomial, and the soundness reduction (Links 1–3) goes through verbatim with primes.

## The degree / parameter trade-off (the decisive practical point)

The binding degree is the **permutation-recurrence quotient** (`Z' × 3` linear
perm-factors): `deg(Q'_recur) ≈ 3n + 657` for `deg(R)=165` (`Z_H·R_l` has degree
`n+165`, so `l'` is degree `n+164`, not `2n+…`).

- **Real circuits (`n > 657`, i.e. ng ≥ 1024):** `3n+657 < 4n`, so the blinded
  quotient **already fits the current 4N tested bound** — ZK is *free* (no parameter
  change, ρ=1/8 and the ~80-bit soundness untouched; only the mask computation is added).
- **The demo (`n=8`):** the ~165-evaluation leak surface is *larger than n itself*,
  so the trace must be padded to `n ≳ 256` (next_pow2 over ~165 blinding rows, added
  as σ fixed-points like the GHint inactive-cell pattern) to carry the masking — which
  makes the demo native run ~hours (the FRI coset scales with n). The demo is the
  pathological small case; ZK is cheap exactly where it matters (large circuits).

### ⚠️ The silent-failure trap (do NOT trip)

If you raise the tested degree bound to fit the blinded degree but **do not grow the
coset proportionally**, ρ rises from 1/8 toward `(deg bound)/(coset)`, per-query
survival `(1+ρ)/2` rises, and `(survival)^82 · 2⁻¹²` **silently drops below 2⁻⁸⁰
while the proof still verifies.** Re-adding ZK would then break the headline
soundness as a side effect, undetected by any ACCEPT/REJECT test. **Mitigation
(non-negotiable):** keep ρ=1/8 as the invariant (coset = 8 × tested bound), and
**re-run the soundness arithmetic** `(9/16)^82 · 2⁻¹² ≤ 2⁻⁸⁰` as a gate at every
parameter change.

## Implementation order (each step gated by the soundness REJECT cases staying green)

0. **Baseline:** record the soundness gates green (`verify_b3` ACCEPT; cross / evil /
   wiring / tamper REJECT) as the regression gate.
1. **Param plumbing, `deg_R=0`:** parameterize `fri_dsize`/`fri_log`/`fri_layers` by
   `deg_R`; at `deg_R=0` it collapses to the current values byte-identically. Re-run
   the soundness arithmetic check. (Isolates the param change from masking.)
2. **Blind `l,r,o`** (`Z_H·R`, `deg_R=165`); confirm ACCEPT + all REJECT cases.
3. **Blind `Z`** (`F_{p²}`, `deg_R_Z=166`); confirm the boundary + recurrence on H,
   ACCEPT + REJECT. No independent Q mask.
4. **Demo sizing:** pad ng (or append ~165 σ-fixed-point blinding rows) so the coset
   multiplier is ~1.75× not 32×; confirm a sane native time + green gates.
5. **ZK self-check:** two proofs of the SAME statement with different mask seeds —
   assert both ACCEPT and the opened `l,r,o,Q,Z` + 6 OOD evals DIFFER (the
   witness-independence smoke test, the hiding analogue of the soundness REJECT gates).
6. **Docs:** the honest ZK claim + do-not-claim; fix the stale `parameters.md`
   (64→82 queries, 16N→32N) and the soundness.md ZK row.

## The honest claim (ZK flavor)

Achieved (by design): **honest-verifier zero-knowledge (HVZK), computational**,
Fiat-Shamir-compiled to a **computational NIZK in the ROM** (BCS transform). The
opened values are statistically HVZK *under an ideal mask RNG* (the `Z_H·R` masks
make the ≤166 revealed evaluations information-theoretically uniform); overall
**computational**, because the Merkle roots are only computationally hiding (like
every Merkle-based STARK — ethSTARK, Plonky2). With the live Poseidon-seeded mask
PRG it is "statistical under ideal-RNG, computational with the PRG." **No new trust
assumption beyond Poseidon-as-RO**, which soundness already relies on.

**Do NOT claim:** bare "zero-knowledge" (always HVZK / NIZK-in-ROM); "perfect" or
"statistical" ZK overall (it's computational); "malicious-verifier ZK"; "the proof
reveals nothing" (it reveals public metadata — trace length n, gate structure, query
count); "ZK is proven / machine-checked" (pen-and-paper); "ZK without degrading
soundness" unless the coset was grown and the soundness gate re-run; "production-ready".

## Honest in-repo end-state (with ZK added)

ZK closes the "witness opened in clear" line, but it is **not** the finish line. The
external audit is the *final* boundary, **not the sole one** — three in-repo gaps
remain independent of ZK: (1) pin the witness to the CLI inputs / ensure the analyzed
`verify_b3`/OOD-DEEP path is the one used (not a self-checking path); (2) retire the
PRG-mask ideal-RNG idealization; (3) **machine-check** both the soundness and the ZK
reductions. Honest end-state: *"sound + ZK on the analyzed path, reasoned not
machine-checked, unaudited; the right technique at the right flavor; remaining in-repo
= verifier-path + machine-check + retire the PRG idealization; external audit +
cryptanalysis is the final, never-in-repo boundary."*
