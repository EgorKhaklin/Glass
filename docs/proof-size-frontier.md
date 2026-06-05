# Proof-size frontier — design verdict (2026-06-05)

*Why a single comparison proof is ~552k tokens while `a+b` is ~155k, what can shrink it, and what
can't. Grounded in the live FRI/security code + an adversarial red-team. Research-grade, UNAUDITED —
nothing here changes that.*

> **Update (v5.122):** the **first serialization increment shipped** — a denser hash encoding (fixed
> 16 base-2^16 limbs per digest, dropping the always-`"4"` per-lane count). Measured: `a<b` 552k →
> **448k tokens (−18.9%)**, soundness-neutral, `emit_hash`⇄`rd_hash` only. The next levers are
> Merkle-path deduplication (the ~10× structural win) and wiring `difftest.sh` into the suite as a
> permanent native-round-trip gate. See §3 and `docs/roadmap.md` item 7.

## TL;DR

- **The grind/query *parameter* lever is NO-GO** as a proof-size play: it buys at most ~4–5%, sits at
  a zero-slack 80-bit wall, is capped by a latent 16-bit grinding ceiling, and carries a
  soundness-sensitive dual-verifier + corpus + Name ripple. Not worth it.
- **The current `82q / 12g` parameters are honestly ≥ 80-bit** (the red-team verified: queries are
  sampled *without* replacement → strictly better than the iid model; the `0.83 bit/query` constant
  is conservative, real value `0.83007`). Two honest-scope defects were found and fixed (below).
- **The real lever is serialization, not cryptography.** ~**94.9%** of a proof is Merkle-path hash
  data (FRI openings alone are ~71.6%). A denser hash/field-element encoding + Merkle-path
  deduplication is **soundness-neutral** and is the genuine proof-size frontier — a careful,
  dedicated lockstep change (roadmapped, §3).

## 1 · The grind/query parameter lever (NO-GO)

Security is `provable_bits = ⌊0.83·q⌋ + g` (unique-decoding, the headline). At `q=82, g=12` → 80.
The lever: raise grind `g`, drop queries `q`, keep `⌊0.83q⌋ + g ≥ 80`, shrink the per-query openings.

It doesn't pay:

- **Capped at 16 grind bits.** `pow_ok` tests `x % grind_modulus == 0` where `x` is the **first
  base-2¹⁶ limb** of the digest, `x ∈ [0, 2¹⁶)`. For `grind_modulus > 2¹⁶`, `x % 2^g == x` (zero only
  when `x==0`) — the actual proof-of-work **saturates at 2⁻¹⁶**. So the most grind can buy is `g=16`,
  i.e. `q ≥ (80−16)/0.83 = 77.1 → q=78`: a **~4.85%** query cut, the realistic ceiling.
- **Zero slack + brittle.** `q=78, g=16` sits at exactly 80 with the grind at its hard 16-bit wall and
  the query floor binding — strictly *less* robust to any future re-pricing than today's `q=82, g=12`
  (which keeps 4 bits of grind headroom). Spending all the headroom for ~5% is a bad trade.
- **Soundness-sensitive ripple.** `fri_queries`/`grind_modulus` are constants mirrored in **both**
  `verify_b3` and `pentecost_verify.py` (which hardcodes `82`, `% 4096`, `struct_ok queries==82`),
  and changing them regenerates **every** committed corpus fixture and re-roots the Name — exactly
  the gate-coverage-desync class the project guards against, for a ~5% win.

A bigger grind (`g=20–28 → q=63–73`, ~15–23%) would require **widening `pow_ok`** to consume more
limbs — a soundness-sensitive change to the grinding mechanism, separate from this verdict.

## 2 · Two honest-scope defects found + fixed (v5.120)

- **Latent grind overstatement (fixed).** `grind_bits = ilog2(grind_modulus)` was **uncapped** while
  `pow_ok` saturates at 16 bits. So setting `grind_modulus > 2¹⁶` would make the Measuring Reed
  *print* (e.g.) `20-bit grind → 84 provable` while the prover delivered only `2⁻¹⁶` → a silent ~4-bit
  **overstatement**. Today's `g=12` is unaffected (`12 < 16`), but the cliff was one edit away. Fixed:
  `grind_bits = min(ilog2(grind_modulus), 16)`, so the printed security can never exceed the grinding
  the prover actually does. (Widening `pow_ok` is the prerequisite to raising it honestly.)
- **Backward "with-replacement" comment (fixed).** The `fri_queries` note claimed queries are sampled
  *with* replacement so "effective distinct queries < 82 (margin erosion)". The sampler is verifiably
  *without* replacement (`sample_distinct` dedups); without-replacement draws are negatively
  correlated → effective queries `≥` the iid-82 model. The `0.83·q` form is therefore **conservative,
  not eroded.** Comment corrected.

## 3 · The real lever: serialization (roadmapped)

A proof's token stream is **~94.9% Merkle-path hash data** (the FRI `bopen` section alone is ~71.6%);
the gate-list and per-query leaf values are a rounding error (~0.5%). So proof size is set almost
entirely by **how hash digests are encoded** and **how many path nodes are sent** — both
**soundness-neutral** (the proof *data* is identical; only its encoding/redundancy changes):

- **Denser field-element encoding.** `emit_fe` encodes each Goldilocks element as `count` + its
  base-2¹⁶ limbs; a hash digest is 4 such lanes ≈ **~20 tokens / 256-bit digest**. Dropping the
  always-`4` per-lane count for fixed-width hash lanes, or using base-2³¹ (3 limbs/lane), trims this
  ~20–40%. **Hard limit (int64):** a u64 lane **cannot** be one token — base-2¹⁶ limbs exist precisely
  because a Goldilocks element exceeds signed int64. So the per-element win is bounded (~20–40%), not
  the naive 5×.
- **Merkle-path deduplication (the bigger win).** The 82 queries open overlapping paths in each FRI
  layer tree; sibling/ancestor nodes repeat across paths. A batch-opening / multiproof encoding sends
  each shared node once — estimated ~10× the query-knob's effect.

**Why it's roadmapped, not done here:** it is a change to the **portable proof format**, so it must
land byte-for-byte in lockstep across `emit_proofb3`/`emit_fe`/`emit_hash` (Glass) **and**
`pentecost_verify.py`'s `parse`/`rd_fe`/`rd_hash`, then **regenerate all 8 committed corpus fixtures**
(no regen script exists yet — currently manual) and **re-root the Name**, with `pentecost/difftest.sh`
and the fixpoint staying green. The "4-lane-digest vs 16-limb-fe" rep trap the docs already warn about
makes this exactly the kind of careful, single-purpose change that earns its own focused session — not
a tail-of-session edit.

## Verdict

The proof-size problem is a **serialization** problem, not a cryptographic-parameter one. The param
lever is closed (NO-GO, ~5%, brittle); the serialization lever (denser fe encoding + Merkle-path
dedup, ~20–40%+ and soundness-neutral) is the real frontier and is **roadmapped as a dedicated proof-
format change**. The grind-overstatement guard and the corrected query comment ship now (v5.120). The
research/educational-grade, UNAUDITED, do-not-protect-real-value banner is unaffected throughout.
