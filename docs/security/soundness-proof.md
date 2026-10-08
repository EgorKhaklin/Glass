# Soundness reduction for the Glass Goldilocks STARK (`verify_b3`)

> **Status: a rigorous *pen-and-paper* reduction, NOT machine-checked (no Lean/Coq),
> and NOT an audit.** It reduces soundness to named standard theorems plus
> explicitly stated assumptions that are *not themselves validated in-repo*
> (Poseidon2 as a random oracle, Fiat-Shamir in the ROM for this composition, the
> FRI list-decoding conjecture). Research-grade, audit-pending. Do not protect real
> value.

Checked adversarially and reconciled against the source.

## Theorem (soundness of `verify_b3`)

Fix a public gate-list `gates` (a circuit encoding a claimed result R as a
`GConst`); let `n = ng(gates) = |H|` (H = the n-th roots of unity), and run the
protocol with the live parameters of `prove_source_goldilocks_zk.glass`:
challenges in `F_{p²}` (p = 2⁶⁴−2³²+1, |F_{p²}| ≈ 2¹²⁸), Poseidon2 (4-lane output) for
all commitments and Fiat-Shamir squeezes, FRI coset of size 32N (rate **ρ = 1/8**,
tested degree < 4N), fold-to-8, **82 query repetitions**, real **12-bit grind**.

**Then:** if `verify_b3(gates, proof)` ACCEPTS, then except with probability
`ε_total` over the Fiat-Shamir randomness, there exist committed column
polynomials `l, r, o` (degree < n) and a grand-product column `Z` whose values
form a **consistent wire assignment** (one value per wire index) **satisfying
every gate constraint** encoded by `gates` on H, and in particular the
asserted-output row carries `out = R`, so **R is the genuine output** the circuit
computes on some witness.

`ε_total ≈ 2⁻⁸⁰` in the **unconditional unique-decoding regime (PROVEN,
conjecture-free)**; `≈ 2⁻¹³⁵` in the **list-decoding-to-capacity regime
(CONJECTURAL)**. Holds in the ROM for Poseidon2, under the FS-in-ROM heuristic for
this exact composition.

## Proof (four links, each a reduction to a named theorem)

Every challenge is re-derived **witness-free** by `verify_b3` along the strictly
prefix-monotone transcript `stmt_seed(gates) → ts1=H(·,root1) → (β,γ_p) →
ts2=H(·,root2) → α → ts3=H(·,root3) → z,ωz → ts4=absorb(OOD evals) → γ_deep →
per-FRI-layer βᵢ → grind → 82 query indices`. This staged commit-before-challenge
ordering is load-bearing for every Schwartz-Zippel step.

**Link 1: FRI proximity** (Ben-Sasson–Bentov–Horesh–Riabzev, ICALP 2018; ethSTARK
Thm 6/8; Proximity Gaps, FOCS 2020). The per-query routine Merkle-opens each FRI
layer at `j, j+half`, recomputes the 2-to-1 fold, checks consistency to the next
layer, terminating at `is_const2(bfinal)`; at layer 0 it reconstructs the
DEEP-batched word B from the trace/Q/Z openings and checks it equals the FRI
opening. With 82 repetitions in the **unique-decoding** regime (δ < (1−ρ)/2 =
7/16): per-query survival 9/16, `(9/16)⁸² ≈ 2⁻⁶⁸` × 12-bit grind = **≈ 2⁻⁸⁰** ⇒
B is δ-close to a *unique* codeword P of degree < 4N. (Capacity regime: `≈ 2⁻¹³⁵`,
but accept yields only a bounded *list*: conjectural.)

**Link 2: DEEP-ALI quotient binding** (DEEP-FRI 2019; Schwartz-Zippel over
`γ_deep`). `B = Σ γ_deepᵏ (T_k(x) − v_k)/(x − z)` over `{Q,l,r,o,Z}` (+ Z at ωz).
Each quotient is a polynomial iff `(x−z) | (T_k(x) − v_k)`, i.e. iff the committed
`T_k(z) = v_k`; otherwise a simple pole at z survives. Since z and `γ_deep` are
drawn *after* the three commitments, B's low-degreeness as a function of `γ_deep`
is the zero-set of a nonzero degree-≤5 polynomial ⇒ `Pr ≤ 5/2¹²⁸`. So except
negligibly, every `T_k` is a genuine degree-(<4N) polynomial **and** the sent OOD
evals are their true z-values; `recon` ties the FRI word to the *same* columns
Merkle-committed under `root1/root2/root3`.

**Link 3: identity ⇒ satisfying, wire-consistent assignment** (Schwartz-Zippel ×2
+ PLONK permutation lemma, Gabizon–Williamson–Ciobotaru, ePrint 2019/953). The
accepted check `qz == Qgate(z) + α·Qrecur(z) + α²·Qbound(z)` (public selector/perm
columns recomputed at z by the verifier) lifts: by SZ at the random z (`≈ 5N/2¹²⁸`):
to a **polynomial identity**. Since `l,r,o,Z` are committed *before* α,
α-separation (`≈ n/2¹²⁸`) forces `G_gate ≡ 0` and `G_recur ≡ 0` on H, and the
boundary gives `Z(1)=1`. One-hot public selectors ⇒ **each row's native gate holds**;
the wrap-closed grand product (Z_H has no last-row exclusion, Z genuinely deg < n)
+ the permutation lemma over `(β,γ_p)` (`≈ 3n/2¹²⁸`) ⇒ **cells sharing a wire carry
equal values**. The claim gates (`GConst(R)`, `GSub`, `GEqZero`) chain to
`w[out] = R`.

**Link 4: Fiat-Shamir in the ROM** (BCS transform, Ben-Sasson–Chiesa–Spooner, TCC
2016; round-by-round soundness, CCH+ STOC 2019). Links 1–3 are interactive; the BCS
theorem transports them to the non-interactive proof with error ≈ the sum of the
per-round (doomed-state) errors, modeling Poseidon2 as a random oracle. The classic
multi-round FS failure (BMMTV) is averted because **each challenge binds the full
running transcript** (the prefix-monotone hash chain, re-derived by the verifier);
the 12-bit grind is re-checked in-circuit (`pow_ok`), soundly adding 12 flat bits.

`ε_total = ε_FRI_query + ε_FRI_commit + ε_γ + ε_OOD + ε_α + ε_perm + ε_z-domain +
ε_RO + ε_bind`; the FRI-query term is `ε_FRI_query ≈ 2⁻⁸⁰` (provable). **Margin note:**
68 query-bits + 12 grind = 80 *exactly*: thin; any erosion drops below 80.

### The hash-width term `ε_bind`

`hashg` outputs **4 Poseidon2 lanes** (~256 bits), so every Merkle node and transcript seed
has ~2⁻¹²⁸ birthday collision resistance and `ε_bind ≈ 2⁻¹²⁸` stays below the ~80-bit FRI
floor. A single ~64-bit lane would cap end-to-end soundness at **~32 bits**; an
audit-readiness pass caught exactly that overclaim in an earlier version, and the hash was
widened. Queries are drawn **without replacement** (`sample_distinct` re-draws on a
collision), so all 82 positions are distinct and the 68+12 margin is not eroded by
duplicates. Both are validated natively (all ACCEPT/REJECT gates hold).

## Ledger

**Proven (reduces to standard theorems, conjecture-free):** the FRI unique-decoding
query bound at 82q/ρ=1/8 + 12-bit grind (≈ 2⁻⁸⁰); DEEP quotient binding; the
identity ⇒ per-row satisfaction; the grand-product ⇒ wire-consistency; the
prefix-monotone, witness-free FS chain (no BMMTV attack); the grind is verifier-rechecked.

**Conjectural:** the ≈ 2⁻¹³⁵ list-decoding headline (FRI proximity-gap /
decoding-to-capacity at δ < 1−√ρ). **Never quote bare.** The conjecture-free figure
is ≈ 2⁻⁸⁰.

**Assumed (not validated in-repo):** Poseidon2 = random oracle (the load-bearing
idealization; the in-repo Poseidon2 is unaudited, un-cryptanalyzed); FS-in-ROM for
this exact 5-phase composition (framework only, not a closed/mechanized theorem);
Merkle/hash collision-resistance; `x²−7` irreducible over F_p; z avoids the coset
(no explicit guard: leans on `|coset|/2¹²⁸ ≈ 2⁻⁸³`); RO query budget ≪ 2¹⁰⁴.

**Gaps a real proof / audit must still close:**
1. **No machine-checked reduction**: the above is pen-and-paper. *(Biggest in-repo gap.)*
2. **Poseidon2 as RO + Poseidon2 cryptanalysis**: the whole bound is vacuous if
   Poseidon2 has exploitable structure. **Hard boundary, never producible in-repo.**
3. **Compiler correctness is out of scope**: the theorem proves "the *gate-circuit's*
   output = R"; that prism/cgen faithfully lowers the *source program* is a separate
   obligation (a bridge bug would faithfully certify the wrong quantity).
4. **Witness/inputs**: for *private* inputs the theorem proves "knowledge of a witness
   yielding R" (the correct ZK semantic). For inputs that should be *public*,
   `build_claim_pub` now pins a chosen input wire to a public value via the is-zero gadget
   (the value lands in a GConst → `stmt_seed`; a wrong public value REJECTs: validated
   native), upgrading "R is *some* valid output" to "R = f(*these* public inputs)."
5. **Zero-knowledge is out of scope**: on the default path `l,r,o` and the grand-product
   `Z` are opened in the clear. `--zk` adds randomized-trace hiding, reasoned separately and
   not machine-checked. This is a soundness-only analysis.

## Two Fiat-Shamir gaps this analysis surfaced, now closed in code

- **Protocol parameters are absorbed into `stmt_seed_of`** (coset generator 7, blowup
  32, fold-stop 8, query count 82, grind 12): a verifier with mismatched parameters
  derives different challenges.
- **The final folded codeword `bfinal` is absorbed before query sampling**
  (`absorb_final`, standard BCS/ethSTARK): the query positions depend on the final
  codeword, so it cannot be adapted after the queries.

Both are validated natively. What remains: a machine-checked reduction, an equally
rigorous argument for the `--zk` hiding, then the external audit, which is the hard
boundary.
