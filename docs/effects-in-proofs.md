# Effects in the proof story (C2) — a design

*A design note / proposal. All four steps are prototyped
([`prove_inference_zk.glass`](../examples/prove/prove_inference_zk.glass),
[`prove_random_zk.glass`](../examples/prove/prove_random_zk.glass),
[`prove_state_zk.glass`](../examples/prove/prove_state_zk.glass),
[`prove_effects_zk.glass`](../examples/prove/prove_effects_zk.glass)). The Inference/trust-boundary
gadget is also lowered to the **full** blinded F_{p⁴} FRI STARK via the bridge
([`trust_prove.glass`](../examples/prove/trust_prove.glass)) and so is `Random`
([`random_prove.glass`](../examples/prove/random_prove.glass)) — as is `State` read-after-write consistency
([`state_prove.glass`](../examples/prove/state_prove.glass)) — all three succinct + ZK via the bridge; the general
`State` case (prover-chosen order + the in-circuit permutation argument) is the remaining work.*

## The tension

A zero-knowledge proof attests a **pure relation** — a circuit is a function of its
inputs. Glass's effects — `IO`, `Random`, `Inference` — are exactly the points where
a computation reaches *outside* itself. You cannot put "called an LLM" inside a
circuit.

## The idea

**Reify every effect as a committed entry in an effect *trace*, and let the effect
row be the trace's schema.** The circuit stays pure — it computes
`step(inputs, trace) = (output, trace')`, treating each effect as reading or writing
a slot in `trace`. The proof attests two things: (1) the pure relation holds (the
existing STARK), and (2) the trace is **consistent with its commitment**. The effect
row — already *mandatory* in every signature — names exactly which slots exist and
how each is bound.

The signature was already the contract; now it is the **proof's statement**. That is
the Track-C convergence: *read the signature, know what the proof proves.*

## Per-effect construction

| Effect | ZK treatment | Already in the repo |
|---|---|---|
| **`Random`** | each `random_int` draw is a witness value **bound to the Fiat-Shamir transcript** (or a prover-committed seed) so it can't be ground | the STARK already derives its own challenges this way — reuse `frost_grain`'s transcript |
| **`IO` read** | an external read = a witness value + a **commitment-opening** constraint; `print` → a committed output log | `prove_query_zk` reads rows from a committed private table and proves the aggregate — that *is* a committed-read effect |
| **`Inference`** | `model_call`'s answer is a **committed oracle**: a private witness pinned by `C = hash(prompt, answer, nonce)`; prove a downstream check over it. You prove the computation used a committed response *faithfully*, not that the model is correct | **prototyped:** [`prove_inference_zk.glass`](../examples/prove/prove_inference_zk.glass) |
| **`Fail` / partiality** | not a label — the `Result` type; prove "`f(inp)` is `Ok`" without revealing `inp` | the ADT + refinement bridge |

## The compile target

A function `(A) -> B !{R}` lowers to a pure circuit `step(A, traceᵢₙ) = (B, traceₒᵤₜ)`
**plus**, per the row `R`, type-directed binding gadgets: commitments for reads,
transcript-binding for `Random`, an output log for `print`. The bridge already
dispatches on **types** to lay out values (`twidth`); C2 dispatches on the **effect
row** to lay out the trace — the same move, one level up. LANG.md's foreshadowed
`Private`/`Commit` effects fall out as the public/witness *partition*, named by the row.

## The genuinely hard part

**Ordering/consistency of a multi-effect trace.** If a computation reads and writes
repeatedly, the proof must enforce that reads see the right prior writes, in order —
a **memory-consistency argument** (sort the trace by `(address, time)`, prove the
sorted trace is consistent *and* a permutation of the original). That is the
machinery zkVMs use, and it leans on the permutation argument Glass already built
(`prove_zperm`). Everything is **bounded** (a fixed trace length), like recursion and
lists. And the bridge must learn to *read* the effect annotations prism already
parses into `EffRow`.

## Steps

1. ✅ **`Inference` as a committed oracle** ([`prove_inference_zk.glass`](../examples/prove/prove_inference_zk.glass)) —
   the model answer is private, pinned by a hiding commitment, and a downstream
   validator is proven over it (sound RLC; ZK STARK is the follow-on). *Headline: a
   proof that an LLM-in-the-loop computation ran faithfully over a pinned answer.*
2. ✅ **`Random` via the transcript** ([`prove_random_zk.glass`](../examples/prove/prove_random_zk.glass)) —
   `random_int` draws are pinned to the Fiat-Shamir transcript (commit first, then the
   randomness falls out): a provably-fair, un-grindable roll, verifiable from public data.
3. ✅ **`State` / memory-consistency** ([`prove_state_zk.glass`](../examples/prove/prove_state_zk.glass)) —
   an access trace, bound program-order-to-address-sorted by a permutation argument (grand
   product), sorted, and read-after-write checked: every read pinned to the last write, the
   log un-fakeable (sound prover-side; FRI z-accumulator + range gadgets add ZK).
4. ✅ **The effect row generates the proof** ([`prove_effects_zk.glass`](../examples/prove/prove_effects_zk.glass)) —
   prism parses a signature, the bridge reads the `!{…}` row off the type, and each label
   becomes an obligation discharged by its gadget. Change the row, the schema changes.

## Why it's the right shape for Glass

The effect row stops being a warning label and becomes the **schema of the proof**:
what's committed, what's witnessed, what's revealed. *"Read the signature, know what
it does"* becomes *"read the signature, know what the proof proves"* — the whole
thesis, completed for effectful code.
