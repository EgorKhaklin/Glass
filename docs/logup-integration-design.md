# LogUp in-circuit range integration — design

> **STAGE 0 OUTCOME (2026-06-04): DEFER.** The design below is sound and ready (Stages 1–3), but a
> measured cost analysis (§0) shows the integration would **regress every routine workload** and is
> not worth its multi-session, soundness-critical cost **yet**. The bridge's range-checks are too few
> to amortize the lookup table. Keep `range_k`. **Trigger to build:** a workload that emits **&gt; ~20
> range-checks in one proof** (batched multi-statement proofs; wide-range arithmetic at scale; an H3
> recursive verifier that accumulates many range-checked values). This document is the executable plan
> for that day. See §0 for the numbers.

*Status: DESIGN (no code yet) — Stage-0 GO/NO-GO complete (DEFER). Grounded in a read-only survey of the live bridge + an
adversarial red-team (multi-agent). The standalone LogUp arc — [`frost_logup.glass`](../examples/frost/frost_logup.glass)
(identity), [`…_air.glass`](../examples/frost/frost_logup_air.glass) (running-sum/AIR),
[`…_committed.glass`](../examples/frost/frost_logup_committed.glass) (Fiat-Shamir β) — is the
math this wires into the prover. This document is the de-risked plan; it deliberately records
what the red-team **broke** so the implementation never re-discovers it in soundness-critical code.*

> **TL;DR.** A LogUp range-lookup *can* replace the bit-decomposition range gadget, but it is an
> **amortized** win, not a drop-in single-comparison speedup, and it is a **multi-session, staged**
> build — not one changeset. The red-team found the naive "dense table as trace rows + delete
> `range_k` + one commit" design **unsound and a performance regression**. The viable design keeps
> `range_k` as the large-`k` fallback, adds the lookup behind a `k`-sizing guard, materializes the
> table at a feasible limb width (≤ 2¹⁶), keeps the comparison's sound sign-bit, and lands in
> ordered stages each of which is independently green (suite + `pentecost/difftest.sh` + Name + fixpoint).

---

## 0 · Stage-0 GO/NO-GO — the measured cost analysis (outcome: DEFER)

The design's §6 mandates a Stage-0 measurement before any code, because the whole integration's value
is a *performance* claim. Here it is, with real numbers from the live prover.

**Measured proof sizes** (`glass prove --emit`, Goldilocks, base-2¹⁶, current bridge):

| circuit | range-checks | proof tokens |
|---------|--------------|--------------|
| `a + b` (baseline, arithmetic) | 0 | **154,842** |
| `a < b` (one comparison) | 1 | **552,366** |

One comparison's range gadget (`lt_build`: two `range_k(·,32)` ≈ 454 gates + a 33-bit
`decompose_capture` ≈ 234 gates ≈ **~693 gates**) takes the proof from 155k → 552k tokens — a **3.6×**
blow-up, **+397k tokens**. The cost is the gadget pushing the trace size `n = next_pow2(#gates)` up
(proof ∝ the coset `m = 32n`).

**The break-even.** A LogUp lookup replaces the per-value bit gadget with a table lookup, but the
dense range table `{0..2^k−1}` is **2^k trace rows** (one gate = one row), paid **once** and amortized
across all `N` range-checks sharing it. LogUp's trace beats `range_k`'s when `693·N > 2^k`, i.e.

> **break-even `N ≈ 2^k / 693`** range-checks (more precisely, limb-lookups).

| limb width `k` | table rows | break-even `N` | covers operands |
|----------------|-----------|----------------|-----------------|
| 32 | 2³² (infeasible) | ~6.2 million | full `[0,2³²)` directly |
| 16 | 65,536 | ~95 | 16-bit limbs (2 limbs / 32-bit value) |
| 12 | 4,096 | ~6 (≈18 effective, 3 limbs/value) | 12-bit limbs |
| 8 | 256 | <1 | bytes only (rarely the operand width) |

**Two hard conclusions:**

1. **The single comparison — the headline ~552k proof — is never helped.** It is `N = 1`, far below
   any break-even at any usable `k`; the table overhead dwarfs the one gadget it removes. The
   single/few-comparison case (which is essentially *every* current `glass prove`) **stays on
   `range_k`**, full stop. LogUp is the wrong tool for the headline proof-size problem.
2. **No current workload reliably crosses break-even.** Surveying what the bridge emits: a comparison
   (1), the capstone `private_eligibility` (2), signed `sdiv` (a few), `gcd` at fuel-8 (~8–16, and it
   is already *semantics-gated*, not routinely proven natively). The heaviest realistic circuit has a
   few dozen range-checks — below even the `k=12` effective break-even (~18), and `gcd`'s ~16 is at
   best marginal. Building the integration now would make **every routine proof larger** for **no
   workload that benefits today.**

**Decision: DEFER (NO-GO for now).** The architecture (§2–§5) is sound and the staged plan (§6) is
ready, but the ROI is negative against the current workload mix, and the cost is a multi-session,
soundness-critical, ~12-lockstep-site build. Spending it now would violate "don't ship a regression."

**Trigger to execute Stages 1–3:** a workload that emits **&gt; ~20 range-checks in a single proof** —
e.g. batched multi-statement proofs (many comparisons per proof), wide-range arithmetic at scale, a
table shared *across* proofs, or H3's recursive verifier if it accumulates many range-checked values.
When such a workload is real, this design executes against it directly (the math is validated, the
hazards are closed on paper, the lockstep surface is enumerated). Until then, the honest lever for the
single-comparison proof is elsewhere (a smaller base proof / fewer FRI queries at equal security — a
separate frontier), not a range lookup.

*(This is "search before building": the design phase + a measured Stage-0 turned a roadmap headline
into a precise, deferred, ready-to-fire plan — and avoided a large effort that would currently regress
performance.)*

---

## 1 · Goal and the honest value proposition

Today every range-checked value pays `range_k` — a bit-decomposition costing ~7 gates/bit (~224
gates for `k=32`). A single comparison (`lt_build`) range-proves both operands (~448 gates) plus a
33-bit sign decomposition of `d = wx − wy + 2³²`, which is what makes comparison/division proofs
~600k tokens vs ~150k for pure arithmetic.

A LogUp (log-derivative) lookup replaces the per-value bit gadget with a **table lookup**: prove
`v ∈ {0..2^k−1}` by showing `v` appears in a dense literal table, via the identity
`Σ_j 1/(β − a_j) == Σ_i m_i/(β − i)` (sound by Schwartz–Zippel + partial-fraction uniqueness).

**The crucial reframing (red-team, feasibility lens).** In the bridge **one gate = one trace row**
(`n = next_pow2(#gates)`, coset `m = 32·n`). A dense table `{0..2^k−1}` *materialized as trace rows*
is **2^k rows**. For the real 32-bit contract that is 2³² rows (`m ≈ 2³⁷` leaves — categorically
infeasible); even 16-bit limbs (2¹⁶ rows) make a **single** comparison ~64× *worse*. The table cost
is paid **once** and amortized across all lookups sharing it. Therefore:

- LogUp **helps** a circuit with **many** range-checks sharing one table — deep recursive `divmod`
  / `gcd`, many comparisons, H3's per-node hashing. There the one-time table dominates nothing.
- LogUp **hurts** a **single** comparison — bit-decomposition (~458 gates) is cheaper than a
  2¹⁶-row table. So `range_k` **stays** as the fallback; the lookup is gated on a `k`-sizing /
  lookup-count heuristic, not a blanket replacement.

This is the opposite of the original "shrinks every comparison proof" framing, and it is the single
most important thing to internalize before writing code.

---

## 2 · Architecture — the running-sum S as "a second Z"

The decisive structural find: the PLONK grand-product **Z is already a committed F_{p²} column**
(`zcw : List<G2>`, Merkle **root2**), with the quotient `qcombined_z = qgate + α·qrec + α²·qbnd`
(see `recur_at_z`, `qcombined_z`, `build_q_b3_go` in [`prove_source_goldilocks_zk.glass`](../examples/prove/prove_source_goldilocks_zk.glass)).
The LogUp running-sum **S is structurally a second Z**: another committed F_{p²} column with a
transition + boundary, folded into the same quotient.

New committed columns:

- **S** (running sum, F_{p²}, `List<G2>`) — `S_0 = 0`, `S_{k+1} = S_k + num_k·1/(β_L − v_k)`. Opened
  at `z` and `ω·z` (the rotation, exactly like Z's `zz`/`zwz`).
- **m** (multiplicity, base field embedded as G2) — `m_i` = how many trace values equal table point
  `i`. A **genuinely separate committed column** (the red-team killed "pack m into S's imaginary
  lane": `S_i` is a full G2, there is no free lane).

Quotient terms (canonical α-powers, **identical** in `qcombined_z`, the prover's `build_q_b3_go`, and
Pentecost's `qcombined_z`):

| term | α-power | meaning |
|------|---------|---------|
| `qgate` | α⁰ | per-row gate constraint (unchanged) |
| `qrec`  | α¹ | grand-product recurrence (unchanged) |
| `qbnd`  | α² | grand-product boundary `Z_0=1` (unchanged) |
| `qLtrans` | α³ | LogUp transition `(S_{k+1}−S_k)(β_L−v_k) = num_k` (cleared denominator, full `gmul2`) |
| `qLbnd0` | α⁴ | LogUp boundary `S_0 = 0` (Lagrange `L_0`) |
| `qLbndN` | α⁵ | LogUp boundary `S_N = 0` (Lagrange `L_{N−1}` — see §4, **mandatory**) |

The trace is value-rows (`num = +1`, `v = a_j`) followed by dense table-rows (`num = −m_i`, `v = i`).
S vanishing at the end (`S_N = 0`) iff the lookup holds.

---

## 3 · The lookup-native range, and why the comparison keeps its sign-bit

`lt_build` does **two** jobs: (a) range-prove the operands `∈ [0,2³²)`, and (b) decompose
`d = wx − wy + 2³²` to read the sign bit (the actual `<` result). **The lookup replaces (a) only.**

The red-team's first CRITICAL hole: deleting the bit-decomposition and making the result a free hint
`wlt = (1 if wx<wy else 0)` is **unsound** — nothing ties the 0/1 to the relation, so a prover emits
`wlt = 1` for a false `5 < 3`. The `(wy−wx−1) ∈ [0,2^k)` trick does not rescue it: the prover is never
*forced* to route the honestly-computed difference into the lookup, and field underflow
(`wy−wx−1 ≡ p−3`) interacts with per-proof `k`-sizing. **You cannot eliminate the arithmetic that
converts "in range" into a boolean.**

Therefore the comparison **keeps one boolean-pinned sign bit** (the top bit of `d`), and the lookup
replaces the *operand* range-proofs (`range_k(wx)`, `range_k(wy)` → two lookups) plus, optionally, the
low limbs of `d`. The win is the ~448 gates of operand decomposition becoming lookups, **not** a
~6-gate comparison. `cmp_ok_g` / `scmp_desugar` / the `cgen` `ELt`/`EGt`/`EDiv` wiring keep their
interface; only the meaning of "range-prove `v ∈ [0,2^k)`" changes (register `v` as a lookup entry
instead of emitting `range_k`). For `k > k_max` (the table is too big), it falls back to `range_k`.

---

## 4 · Soundness obligations (and the adversarial fixes that must be honored)

These are not optional — each is a CRITICAL hole the red-team forged a proof through, with its fix:

1. **Dense table, never sparse.** The table side must enumerate `{0..2^k−1}` by index. A sparse
   "observed values" table lets an out-of-range value be a pole on both sides and cancel at every β.
   (Standalone hazard 1.)
2. **S is a constrained committed column; the transition is mandatory.** A forged `S ≡ 0` satisfies
   any boundary for free; only the per-row transition `(S_{k+1}−S_k)(β_L−v_k) = num_k` catches it
   (row 0: `0 ≠ num_0 = +1`). Never a boundary-only / final-value check. (Standalone hazard 2.)
3. **`S_N = 0` needs an explicit Lagrange boundary, not a bare `1/(z−ω^{N−1})`.** The additive sum
   has **no** free closure analogous to Z's multiplicative wrap (`Z_N = 1` for free). Encode it as a
   real vanishing quotient with a Lagrange `L_{N−1}` selector, with the last-row index exactly right,
   as a **distinct α-power (α⁵)**. The bare reciprocal admits an off-by-one forgery (an S that is zero
   at the checked interpolation point but nonzero at the true final accumulator).
4. **Commit-then-challenge β_L.** β_L is squeezed **off `ts1`** (tags 141/142, joining the
   `beta_p`/`gam_p` fan-out), so it is bound to **root1** which already commits the wire columns.
   The **multiplicity column and the value column must be committed before β_L is known** — keep them
   in root1's leaves (or a root committed before β_L); do **not** move m to a root squeezed after β_L
   (the circularity the minimal-delta design tripped on). β_L ∈ F_{p²} with a **nonzero imaginary
   lane** or **ABSTAIN** (a base-field denominator could vanish): Glass aborts before emitting;
   Pentecost defensively REJECTs.
5. **The value column must be bound to the wires.** Value-rows are witness values, so `v` is not
   "public/gate-derivable" — it must be **copy-constrained to the operand wires** (fold into the
   existing permutation Z, or let `v` *be* the `l/r/o` columns selected at `z`). Otherwise the lookup
   proves nothing about the circuit's operands.
6. **The lookup membership must be reconstructible by both verifiers.** `lookup_k` "emits no gates"
   has no channel telling the verifier which wires are lookup entries. Add a **`GLookup(w)` marker
   opcode** (a 7th gate kind): no arithmetic constraint, but it enters `gate_dig`/`stmt_seed_of` and
   lets `public_cols`/`logup_cols` reconstruct the value-rows identically on both sides.
7. **Degree budget.** The cleared-denominator transition is degree ~2N; prove `max(all quotient
   terms) ≤` the FRI-tested bound, or raise the bound and **re-derive bit-security (the Measuring
   Reed must reflect it)**. Gate it with a `low_degree_quotient`-style check that the combined
   codeword folds to a constant on a circuit *with* a lookup.
8. **Soundness error `(2^k−1)/|field|`** ⇒ F_{p²} ≈ 2¹²⁸ required (base 2⁶⁴ gives only 64−k bits);
   `k ≤ 32`. The 80-bit STARK floor (82 queries) is the binding security parameter, not the field.

---

## 5 · The two-verifier lockstep surface (≈ 12 coupled sites)

Every change lands **byte-for-byte identically** in Glass `verify_b3`/`prove_b3`/`emit_proofb3` **and**
`pentecost/pentecost_verify.py`, or `pentecost/difftest.sh` turns red on an *honest* proof (looking
like a soundness bug but being a serializer/transcript typo). The surface, with canonical decisions:

- **Gate model:** new `GLookup(w)` opcode (#7) in the gate ADT, `emit_gate`, `gate_dig`,
  `stmt_seed_of`, `public_cols`/`logup_cols`, and Pentecost's GATES parse loop.
- **Commitments:** S and m committed. Decision: a **widened root2 leaf** `logup_leaf(z,s,m) =
  hashg(hashg(lhash(z), lhash(s)), lhash(m))` (one path `p2j` authenticates z, s, m together — no
  extra Merkle path), pinned as a named helper in both languages. (Alternative: a 4th root — more
  paths; rejected for surface size.)
- **Transcript:** `betaL_of(ts1) = G2(lane0(hashg(ts1,glit(141))), lane0(hashg(ts1,glit(142))))` in
  Glass; `_chal(ts1,141,142)` in Pentecost. `ts4 = absorb_g2(absorb_g2(absorb6(ts3,…), sz), swz)` —
  sz then swz, strictly after `zwz`, no "OR" alternatives. Whether `mz` is absorbed is **decided once**
  (absorb it iff it enters `id_ok`) and mirrored.
- **OOD header (ProofB3):** 14 → 17 G2 fields — append `sz, swz, mz` after `zwz`, in
  `emit_proofb3`, the `ProofB3` ctor, `parse()`, and both `verify_b3` unpacks.
- **Per-query opening (TOpenB):** 16 → 22 fields — add `mj, sj, p4j?`/half-mirror; one canonical order
  in the `TOpenB` ctor, `emit_topenb`, and Pentecost `rd_topenb`. (Exact list pinned at implementation;
  m as an embedded-G2, `mj` has **no** rotation half.)
- **Identity (`qcombined_z`):** 3 → 5+ terms (α³ `qLtrans`, α⁴ `qLbnd0`, α⁵ `qLbndN`), with the **same
  α-power-to-term table** in `qcombined_z` (verify), `qcombined_z` (prove), and `build_q_b3_go`.
- **Deep-batch (`deep_batch_b3`):** 6 → 9 terms — `ds (γ⁶)`, `dsw (γ⁷)`, `dm (γ⁸)`, the γ-power chain
  extended identically in `deep_batch_b3` (both verifiers) and `build_b_b3_go` (prover).
- **`struct_ok`:** the `lyrs`/`bfinal==8`/`queries==82` constants stay recomputed from `n` on both
  sides (no divergence) — but a larger `n` from table rows changes them in lockstep; confirm the
  deep-batch degree still satisfies `is_const2(bfinal)`.

**Two trap classes the differential gate cannot catch** (both verifiers recompute the *same* wrong
value, so `difftest` stays green while every proof REJECTs): a wrong α-power-to-term assignment, and a
degree-budget overflow. These are caught **only** by the Third Witness / a dogfood end-to-end ACCEPT —
so the dogfood circuit (`frost_logup_incircuit.glass`) is mandatory, not optional.

**Byte-identity of the no-lookup path is non-negotiable.** `comb_lro → comb_lro4` must **not** change
root1 for proofs with no lookups (a sponge does not satisfy `hashg(…,0) == hashg(…)`). Branch the leaf
hash on the **presence of a `GLookup` marker** in the gate list (reconstructible by both verifiers), so
a pure `a+b` proof stays byte-identical — preserving the corpus fixtures, the Name lockfile, and the
bootstrap fixpoint. Confirm a pure `a+b` proof emits an identical token stream *before* landing anything.

---

## 6 · Staged implementation plan (each stage its own verified changeset)

The red-team's unanimous verdict: **this cannot be one changeset.** Ordered so each stage is
independently green (suite + `difftest` + Name re-lock + fixpoint), and the riskiest unknown is
resolved first:

- **Stage 0 — GO/NO-GO (paper + measurement).** Resolve the §1 table-representation crux concretely:
  pick the limb width `k_max`, and *measure* (a throwaway prototype) that a circuit with **N
  range-checks** crosses below the `range_k` cost at some realistic N. If a representative workload
  does not shrink, **stop** — the integration fails its purpose and the honest outcome is "documented,
  not built." Also settle: implicit/structured table vs materialized limb table.
- **Stage 1 — committed S column, hand-driven.** Add the `S` column + its commitment + `betaL` FS +
  the `qLtrans`/`qLbnd0`/`qLbndN` quotient terms + S openings, driven by a **hand-built** test circuit
  (not yet wired to `lt_build`). Gate: honest ACCEPT / out-of-range REJECT / **forged `S ≡ 0` REJECT**,
  in **both** verifiers, plus the `low_degree_quotient` fold check. This is where the soundness math
  becomes real; nothing user-facing changes.
- **Stage 2 — the multiplicity column + `GLookup` marker.** Add `m` (committed, bound), the `GLookup`
  opcode, and `logup_cols` reconstruction on both sides. Pin m to the dense table. Gate the
  multiplicity-lie REJECT.
- **Stage 3 — wire the range gadget.** Rewire `range_k` call sites (`lt_build`/`divmod_build`/
  `cmp_ok_g`) to register lookups **behind the `k`-sizing guard**, keeping `range_k` as the large-`k`
  fallback and keeping the comparison sign-bit (§3). Showcase: a circuit with **many** range-checks
  (deep `divmod` / a small `gcd`) that measurably shrinks; the single-comparison path stays on
  `range_k`. Third-Witness-confirmed; false-claim REJECT.

A standalone dogfood `examples/frost/frost_logup_incircuit.glass` (interp == native + Pentecost ACCEPT)
should accompany Stage 1 and grow through Stage 3 — it is the only thing that catches the green-but-broken
trap class.

---

## 7 · Honest scope

Research/educational-grade, UNAUDITED, like the rest of the prover. This design has been
adversarially red-teamed *on paper* and the standalone arc has validated the math, but neither
replaces the external audit + Poseidon cryptanalysis that the do-not-protect-real-value boundary
requires. The integration's net is a **smaller proof for range-heavy circuits** and the unblocking of
wider ranges + H3's per-node hashing — not a universal speedup, and not a soundness upgrade.
