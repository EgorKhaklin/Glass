# H3 — recursive STARK verifier: feasibility GO/NO-GO (2026-06-06)

*Can Glass express `verify_b3` as a provable circuit — a verifier that verifies itself — now that the
Merkle-path dedup (v5.124/125) shrank proofs ~2.9×? Read-only investigation (scaffolding / op-gap / cost),
each cross-checked against live source. Research-grade, UNAUDITED — nothing here changes that.*

## Verdict — **NO-GO for full `verify_b3`-as-circuit; a measured defer (LogUp-Stage-0 discipline)**

- **Expressibility: GREEN.** No refused construct in the recursion surface. Every op is `+`/`*`/comparison
  the bridge already lowers — *except* modular inverse (`finv`, `ginv2`), the routine **inverse-as-advice**
  rewrite (witness `y`, constrain `x·y == 1`). NTT (`ntt_lde`) is **prover-only**: the verifier evaluates
  committed polys by Horner at the single OOD point `z`, which lowers. Poseidon2 is pure `+`/`*` (its
  reference `perm2` is byte-identical to the native intrinsic). **The wall is size, not the language.**
- **Size: RED — ~580× over the practical prover ceiling.** The gate model is flat (`GConst/GAdd/GSub/
  GMul/GHint/GEqZero`): **1 op = 1 trace row, no free linear layer**. One Poseidon2 permutation ≈
  **~1,900 gates** (8 full + 22 partial rounds, x⁷ S-box = 4 muls, two 12-lane linear layers). For the
  representative `a<b` proof, `verify_b3` invokes **~10,100 permutations post-dedup** (~98% are Merkle/FRI
  reconstruction) ≈ **~19M gates**. The practical prover ceiling is ~`m=32,768` coset rows (~1,024 useful
  gates) — it fits **~17 permutations**. So `verify_b3`-as-circuit is **~580× over** (~2⁹·²); expressible,
  un-provable today. (Architectural wall is ~2²⁷ gates at Goldilocks 2-adicity — far above, so it's a
  throughput limit, not a hard wall.)
- **Merkle dedup moved the gate ~2.8× — real groundwork, not the closer.** It cut the dominant Merkle
  term 3.32× (26,076 → 7,866 nodes), turning "~1,600× over" (pre-dedup) into "~580× over". A 2.9×-smaller
  proof = ~⅓ the in-circuit re-hashing — necessary, but it leaves H3 ~2.7 orders of magnitude out.

### The trigger (named, measured — not "someday")
Execute full `verify_b3`-as-circuit when **either** fires:
- **(T1)** substrate raises the provable trace ceiling to **≥ ~2²⁵ rows (~33M gates)** at acceptable prove
  time (headroom for ~19M gates + inverse-advice), **or**
- **(T2)** a **chunked / accumulation substrate** lands that proves ~30k-gate sub-circuits and folds them
  (so "~580 chunks" becomes feasible — itself building block B3 below).

Until one fires, do **not** start full H3 — it would emit a circuit no current prover can execute. This is
a measured number (~580×) and a named trigger, in the LogUp Stage-0 defer discipline.

## H3 waits on substrate perf (#6), NOT on LogUp (#1)
H3's ~19M gates are ~98% Poseidon2 (`GMul`/`GAdd` rows), **not** range-checks. LogUp only amortizes range
gadgets, so it touches the ~1,900-gate permutation essentially not at all. The standing LogUp defer is
correct and **independent** of H3 — do not couple them. Substrate perf (a higher ceiling T1, or chunking
T2) is H3's actual gate.

## The next SHIPPABLE building blocks (feasible now, dogfoolable)
The two half-blocks exist but stand apart: the **FRI fold identity** is full/exact in-circuit
(`prove_recursion*.glass`) but unauthenticated; **in-circuit Merkle membership** is real but uses a reduced
hash (`merkle_member.glass`, t=3/3-round/depth-2, ~150–300 gates). The path forward, each its own session,
none needing the trigger:

- **B1 — `merkle_fold_member.glass` (ship first):** compose the two halves into ONE circuit — authenticate
  two openings `f(x)`, `f(-x)` against a public Merkle root (reduced hash, depth-2) **and** apply the exact
  FRI fold `(f(x)+f(-x))/2 + β·(f(x)-f(-x))/(2x)` to the *authenticated* values, asserting it equals the
  next layer's opening. A few hundred to ~1k gates — under the ceiling. The **first circuit where an
  opening is verified against a commitment AND consumed by the fold in the same proof** — the structural
  heart of recursion, at toy scale.
- **B2 — full Poseidon2 one node in-circuit:** swap the reduced `compress` for the real `perm2` (~1,900
  gates, fits the ceiling). The honest unit-cost anchor for every H3 estimate. (Must keep `%`-reduction
  inline to stay Third-Witness-clean — see the divergence note.)
- **B3 — chunking / accumulation harness (this *is* substrate-perf #6 in H3-shaped form, = trigger T2):**
  prove a ~30k-gate `verify_b3` sub-circuit (one query × one tree) and fold ~580 of them. The only lever
  spanning the ~2.7 orders of magnitude; buildable today as an accumulation scheme over feasible sub-proofs.

## North-Star framing: "a verifier that verifies itself"
The math is **done**; the budget is **~580× short** — and the short part is a known *engineering* lever
(throughput/chunking), not a research unknown. Glass can already **write** its verifier as a circuit; it
cannot yet **prove** that circuit in one shot. The self-verifying verifier is an **engineering distance
(prover throughput), not a soundness or expressibility distance** — the strongest possible position to be
gated from. B1 and B2 make that claim concrete and dogfoolable at toy scale; B3 is the lever that erases
the 580×.

### Note: the reduced-hash showcases are circuit-faithful, not Third-Witness-agreeing
`merkle_member.glass` reports a `witness3: DIVERGENCE` — verified **benign**: the nested x⁷ chains reach
~10⁵-bit intermediates with no inline `%`, so the reference interpreter wraps at int64 while the circuit
reduces mod p at every gate (the circuit result mod p = the true unbounded math). It's the "int64 wraparound
the field does not share" class the witness3 message names, harmless for an opaque Merkle root — but any new
full-Poseidon2 in-circuit showcase should keep `%`-reduction inline to stay Third-Witness-clean where the
result is semantically meaningful.
