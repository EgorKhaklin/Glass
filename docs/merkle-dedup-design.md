# Merkle-path deduplication — GO/NO-GO + design (2026-06-05)

*The next proof-size lever after the v5.122 denser hash encoding. Designed + adversarially red-teamed
read-only (no code), with the dedup ratio measured against the live corpus. Research-grade, UNAUDITED —
nothing here changes that.*

## TL;DR — **GO (conditional, staged)**

- **Measured saving: 65% / 2.86× smaller proof** on the representative comparison proof `a<b`
  (448,003 → ~157k tokens, −291k); `a/b` 61% / 2.59×. The proof is **~93% sibling-digest data**, and a
  batch-opening removes **~⅔ of it** (sibling-digest dedup ratio 3.32× / 2.93×).
- **The ~10× headline was wrong** — it was a small-domain saturation artifact (`a+b`: 82 queries
  saturate a 128-leaf tree → 8.71×). The real, validated number for the proofs that drive cost is **~3×
  on paths, ~2.6–2.9× on the whole proof.** Solid, not transformative.
- **Unlike LogUp, this is monotone and unconditional** — a batch proof is *never larger* than
  independent paths and is strictly smaller whenever opened leaves share any node (guaranteed for the
  ~164 opened leaves per tree in a 32k-leaf tree). **No break-even, no workload trigger; it helps every
  proof**, including the single-comparison headline LogUp can never touch.
- **It is invasive and soundness-critical:** a deliberate proof-*format* break that changes the
  `ProofB3` shape, **both verifiers' logic** (this time `verify_b3` IS in the lockstep), both
  serializers, all 8 corpus fixtures, and the Name. **Multi-session; execute the 3-stage plan with full
  lockstep discipline — not one changeset.**

## 1 · What it is

The 82 FRI queries each open a leaf + its sibling **path** to the layer root, and `verify_b3` re-folds
each path independently (`fold_path_g` / pentecost `fold_path`). Across the ~164 opened leaves in a tree,
the paths **share** sibling/ancestor nodes — every internal node above the opened-leaf frontier is sent
once per path that crosses it. A **sorted-index batch Merkle proof** sends each distinct node *once* and
the verifier *reconstructs* every query's path from the shared node set.

## 2 · The measured win (validated: modeled sent-count == actual proof, all 3 fixtures)

| fixture | proof tokens | sibling-digest tokens | dedup ratio | tokens saved | proof shrink |
|---|---|---|---|---|---|
| **`a<b`** (the headline) | 448,003 | 417,216 (93.1%) | **3.32×** | **291,360 (65.0%)** | **2.86×** |
| `a/b` | 501,328 | 467,072 (93.2%) | 2.93× | 307,712 (61.4%) | 2.59× |
| `a+b` | 126,606 | 112,832 (89.1%) | 146.9× | 112,064 (88.5%) | 8.71× *(small-domain artifact)* |

Per-FRI-layer (a<b): the top ~7 of 15 levels collapse (sparse leaves → shared ancestors), the small
lower layers **saturate to zero** auth nodes (every leaf opened). Trace trees dedup weakest (~2.25×) —
3 trees opened once at full height over the same sparse 82-index set. The ~35% residual after dedup is
irreducible by this change (opened leaf *values* feeding the FRI fold + deep checks, the 14 `ProofB3`
header items, `broots`/`bfinal`, the gate stream) and stays byte-identical.

## 3 · Scheme — per-tree sorted-index batch proof, canonical bottom-up reconstruction

Chosen over octopus/indexed-dedup because the 82 query positions are **Fiat-Shamir-derived**
(`sample_queries_g` over the transcript), so **both verifiers already know every opened index** and
consume the co-path nodes in a **fixed canonical order with zero transmitted index tokens**. It also
reuses the existing fold's even=left / odd=right (`index%2`) orientation verbatim — only the *driver*
changes from "fold one path" to "reconstruct the union tree level-by-level."

**One `BatchOpen` block per tree** (6 trees: 3 trace — root1-LRO, root2-Z, root3-quotient — + one per
FRI layer). Each block = the distinct opened leaves (canonical order) + the minimal co-path node set
(canonical order). **Reconstruction (byte-identical both sides):** leaf-hash each opened leaf at its
FS-known index; sweep levels bottom-up in increasing-position order; for each parent, if both children
known → hash them, if one known → consume the next co-path node as the sibling (orient by LSB); compare
the single reconstructed root to the committed root. One comparison per tree replaces 82 path-folds.
Leaf-*value* binding (`fold_pair2`/`deep_batch_b3` `geq2` checks) is untouched — only path material is
shared.

## 4 · Soundness obligations + guards (red-teamed)

- **O3 — canonical node order/orientation (the one genuinely NEW obligation).** A fixed canonical sweep
  both sides (level-by-level, increasing-position, over the *sorted FS-derived* index set; even-position
  child = left input to `hashg`; `pad_pow2_g` padding derived from public tree size). **This is the
  green-but-broken trap:** both verifiers reconstructing the same *wrong* way passes difftest/corpus_check
  structurally but rejects all honest proofs (or accepts a forged frontier in both). **Gate with
  witness3/dogfood against a known-honest proof AND a forged-frontier REJECT — difftest alone cannot see
  a matched-wrong reconstruction.**
- **O2 — missing/extra/forged node.** Counts are canonically *derived and checked*, never trusted as a
  stream length (the v5.111 under-binding lesson): reject on co-path under-run mid-sweep AND over-run at
  the end (`ci != len(copath)`). A forged node → wrong parent → wrong root → REJECT.
- **O1 — every queried leaf bound.** Reconstruction is driven by the canonical index set (not proof
  structure); a missing/extra leaf → reconstructed root differs → REJECT.
- **O4 — per-tree isolation.** One block per tree, reconstructed and compared against *that* root only.
- **O5 — FS-independence (preserve, don't break).** **Verified: no path digest enters the transcript** —
  `rederive_betas`/`seed_from_roots`/`sample_queries_g` read roots + OOD scalars + `bfinal` + nonce only.
  So every root, FS challenge, query position, and grind nonce stays **byte-identical**; the prover
  can't choose a convenient index set. The change is "where siblings come from," not the fold or the FS
  chain.

## 5 · Staged plan (mirrors the v5.122 serializer-change discipline)

0. **GO gate (done):** the dedup-ratio measurement (distinct-union 7,866 vs 26,076 sent on `a<b`) is the
   recorded GO — cross-checked MATCH against the actual proof. GREEN.
1. **Trace trees only (`topen`, ~28%, simplest — fixed index set, no FRI recursion).** Change
   `TOpenB`→`ttrace`, the emit/parse, and the trace-tree checks in both verifiers. **Loud-break first:**
   the new verifiers MUST REJECT every v5.122-format fixture (old per-query paths can't parse as
   `ttrace`) — prove it before regenerating. **Forged-node REJECT in both verifiers.** Regen via
   `regen_corpus.py` (emit-then-verify) → `corpus_check` → in-suite difftest (v5.123) + suite + fixpoint.
   **Do not re-root the Name yet.**
2. **FRI `bopen` per layer (~72%, the headline).** `bopen : List<List<QOpen>>` → `List<BatchOpen>`;
   restructure `vq` to per-layer reconstruct; verify the FRI fold chain still ties layer *i*'s output to
   layer *i+1*'s opened value by canonical index. Same gate sequence (Stage-1 fixtures now reject under
   the Stage-2 verifier).
3. **Re-root the Name LAST** — after Stages 1+2 are green end-to-end and all 8 fixtures round-trip. Ship
   as one verified version bump.

**Lockstep sites** (cannot be one changeset): bridge `QOpen`/`TOpenB` ADTs, `extract_*`,
`vq`/`vb3_q1`/`vb3_qs`/`verify_b3`, `emit_path`/`emit_qopen`/`emit_bopen`/`emit_topenb`/`emit_topen`;
pentecost `fold_path`/`vq`/`vb3_*`/`verify_b3` + `rd_path`/`rd_qopen`/`rd_layerlist`/`rd_bopen`/
`rd_topenb`/`rd_topen`/`parse`. **UNCHANGED anchors (must stay verbatim):** `merkle_root_g`/
`root_of_levels`, the entire FS chain, `fold_pair2`, `deep_batch_b3`, `qcombined_z` — roots, query
positions, and the grind nonce are path-encoding-independent.

## 6 · Ordering vs the other frontiers

- **vs LogUp (deferred):** independent + complementary. LogUp shrinks the *circuit*; this shrinks the
  *opening encoding*. Merkle dedup is the better near-term lever — monotone, no trigger, and it helps the
  single-comparison proof LogUp can't.
- **vs H3 (recursive verifier):** Merkle dedup should **precede** serious H3 work — a 2.86×-smaller proof
  is ~⅓ the Merkle-path hashing to re-execute in-circuit, directly lowering H3's dominant cost. Building
  H3 against the un-deduplicated proof would bake in 3× the recursion.
- **vs substrate perf:** orthogonal (prover speed vs proof size).

## Verdict

**GO** — the dominant buildable proof-size frontier: a monotone, every-proof, ~2.86× shrink of the
system's single largest cost, with one new (guard-able) soundness obligation and zero regression. It is
invasive and soundness-critical, so it is executed as the gated 3-stage plan above in a dedicated
session (the green-but-broken O3 trap is caught by witness3/dogfood + forged-frontier REJECT, not
difftest alone). The research/educational-grade, UNAUDITED, do-not-protect-real-value banner is
unaffected throughout.
