# Soundness: what Glass's proofs actually guarantee

Glass makes a lot of claims with the words *proof*, *zero-knowledge*, and
*sound*. This document is the honest ledger: **which of those claims are
rigorous, which are educational, and where the real edges are.** You should never
have to take the code's word for it.

The short version:

> **Glass is a from-scratch, self-hosted, differential-tested *demonstration* of a
> complete zk-STARK and a ZK-native language. The structure is real and checked.
> The cryptography is research/educational-grade and UNAUDITED. Do not use Glass
> to protect real value.**

There are two very different kinds of guarantee in this repository, and conflating
them is the main way to be misled. Keep them separate.

---

## 1. The differential-testing guarantee: strong and real

This is the guarantee Glass delivers rigorously, and it has nothing to do with
cryptography. Every layer is a **reference semantics** plus a **compiler**, and
they are forced to agree **bit for bit**:

- `dogfood.sh <file>` runs a program on the reference interpreter (`glass.py`) and
  on the self-hosted compiler (`native_glassc`, Glass to C to native) and checks the
  output is **byte-identical**.
- `bootstrap_fixpoint.sh` checks that `native_glassc` compiles **itself** and
  `prism` byte-identically, with no Python in the loop (the fixpoint).
- CI runs the fixpoint and a dogfood check on every push to `main`.

When a change "dogfoods byte-identical", a different implementation of the same
semantics produced the same answer. **This is a correctness/consistency guarantee
about the implementation, not a cryptographic one.** It catches divergence between
implementations, not an error they share.

---

## 2. The cryptographic guarantee: research-grade, with specific caveats

Glass builds, from scratch and in Glass, every structural piece of a zk-STARK:
finite field and extension field, a hash, Merkle trees, PLONK arithmetization, the
gate-constraint quotient, FRI low-degree testing, Fiat-Shamir, query amplification,
grinding, a permutation argument, and ZK blinding. **The structure is demonstrated**:
honest proofs verify, tampered proofs are rejected, and blinding makes two proofs of
the same statement reveal different openings.

What is **not** production-grade is the assurance around the primitives and
parameters:

| Component | What is built | The honest caveat |
|---|---|---|
| **Base field** | The default `glass prove` proves real prism-parsed source over **Goldilocks** (p = 2⁶⁴ − 2³² + 1): multiple named private inputs, claim binding (`output == R`), ADTs and `match`, comparisons, division, strings, records. Trace domain N = next power of two ≥ the gate count. `--baby-bear` keeps the legacy 2³¹ path. | Goldilocks closes the 2³¹ brute-force gap for the default (a private input is no longer guessable from the value range). The default runs **natively** (needs a C compiler and `libgc`). The Baby Bear path's 2³¹ value space is still brute-forceable and results wrap above ~2.1·10⁹. |
| **Challenge space** | F_{p²} ≈ 2¹²⁸ (`x² − 7`) on the default path; F_{p⁴} ≈ 2¹²⁴ on Baby Bear | Cryptographic width. Irreducibility of `x² − 7` and the field arithmetic are not independently validated in-repo. |
| **Hash** | **Poseidon2 over Goldilocks**, byte-exact to Plonky3 (t=12, R_F=8, R_P=22, x⁷), checked against Plonky3's published permutation vector (`poseidon2_difftest.glass`, `lens/test_poseidon.py`) and dogfooded. It drives every Merkle commitment, Fiat-Shamir challenge, and query sample, through a **4-lane sponge** (~256-bit output, ~128-bit collision binding). The earlier Plonky2-exact Poseidon (`frost_goldilocks_poseidon.glass`) remains as a vector-checked reference. | Matching a reference is **not an audit**, and Poseidon2 is not cryptanalyzed here. The whole bound assumes it behaves as a random oracle. The Baby Bear path still uses an educational MiMC hash. |
| **Fiat-Shamir** | Statement-seeded transcript: `stmt_seed_of` binds the gate list, the claimed result, and the protocol parameters; the final folded codeword is absorbed before query sampling; `verify_b3` re-derives every challenge witness-free; the 12-bit grind is re-checked. (`frost_goldilocks_fiat.glass` is a separate, domain-separated transcript module, not wired into the prover.) | Fiat-Shamir in the random-oracle model is a standard heuristic. No machine-checked transcript-separation proof. |
| **Queries** | ρ = 1/8 (coset 32N), 82 queries sampled without replacement, 12-bit grind | ~80-bit provable / ~135-bit list-decoding. The ~135 figure is **conjectural** (proximity gaps); treat ~80 as the security level. See [`parameters.md`](parameters.md). |
| **Zero-knowledge** | The default `glass prove` is **sound but not hiding**: the witness columns are opened in the clear. `--zk` pads the trace with at least 256 random dummy rows (more than the ~170 opened values), so the openings reveal only random rows. | HVZK / NIZK-in-ROM hiding is reasoned, not machine-checked. The mask derivation is an idealized PRG. |

Several demos run *reduced rounds or queries* explicitly so they dogfood on the
interpreter; the full-strength versions run the same way, just heavier.
**No external audit, and no constant-time guarantees.**

---

## 3. The `glass prove` command, specifically

`glass prove <file> [name=value ...]` lowers the file's final expression to a
circuit and proves its result. Names on the command line are private inputs. The
**proof structure is a real FRI STARK**, and a false claim is **rejected**.
Whether the circuit faithfully represents the source is a separate question (see
[`faithful-lowering.md`](faithful-lowering.md)); `--cross-check` tests it per run.

| Mode | What runs | Status |
|---|---|---|
| default | Goldilocks; `gprove_sound` builds the claim circuit and runs the independent, witness-free `verify_b3` | Sound, **not** zero-knowledge. The path an audit would cover. |
| `--zk` | `verify_b3` over a randomized trace; fresh seed per invocation | Sound and hiding. Heavy. |
| `--fast` | The old witness self-check | **Not** a soundness proof. Quick iteration only. |
| `--baby-bear` | The legacy 2³¹ prover, in the interpreter, integer inputs only | Educational. Out of scope for an audit. |
| `--cross-check` | Re-runs the source under `glass.py` and compares the result modulo p | Catches a source/circuit divergence the two verifiers cannot see. |
| `--claim R` | Asserts a specific result | A false claim makes the circuit unsatisfiable, so `verify_b3` REJECTs. |
| `--emit FILE` | Writes a portable proof | `glass verify FILE` checks it with the independent [Lens](../../lens/) verifier. |

The verdict is the exit code: 0 ACCEPT, 1 ABSTAIN (Glass refused to lower the
statement), 2 REJECT, 3 cross-check DIVERGENCE.

`verify_b3` checks per-row gate soundness, inter-row wire consistency (a PLONK
grand product), and FRI, re-deriving every challenge from the statement-seeded
transcript (see [`audit-readiness.md`](audit-readiness.md)). It is still
**research-grade, not production**, for two reasons: (i) **the whole bound rests on
Poseidon2 as a random oracle, unaudited**; every reduction is reasoned, not
machine-checked, and if Poseidon2 has exploitable structure the bound is vacuous;
(ii) the ~80-bit figure is itself a pen-and-paper derivation with a thin margin
(68 query bits + 12 grind bits) that an auditor must re-derive. It proves the idea
end to end on the production field and hash; it is **not** a tool for protecting
secrets.

---

## 4. What it would take to be production-sound

1. **Done: a real field through the bridge.** The default proves over Goldilocks;
   `--baby-bear` keeps the toy field as an opt-in reference.
2. **Done: a vetted hash.** Poseidon2 (Plonky3-exact, vector-checked) is the
   in-STARK hash. Matching a reference is still **not** an audit.
3. **Done: Fiat-Shamir rigor in `verify_b3`.** Statement seeding, protocol
   parameters bound into the seed, the final codeword absorbed before query
   sampling, and every challenge re-derived by the verifier.
4. **Done: a witness-free verifier and a soundness reduction.** `verify_b3`
   commits the execution trace, checks the out-of-domain quotient identity (per-row
   gate binding), and a PLONK grand product (wire consistency). A pen-and-paper
   [soundness reduction](soundness-proof.md) accompanies it. The default
   `glass prove` runs it. Its cost scales with circuit size.
5. **Done: parameters.** ρ = 1/8, 82 queries without replacement, a 12-bit grind,
   and a 4-lane commitment hash: **~80-bit provable** / ~135-bit list-decoding
   (conjectural). See [`parameters.md`](parameters.md).
6. **Done: zero-knowledge, opt-in.** `--zk` gives randomized-trace hiding,
   reasoned, not machine-checked.
7. **Not done: an external audit and community cryptanalysis.** Nothing above
   replaces this. It is the **hard boundary**, never producible in-repo, and the
   "UNAUDITED: do not protect real value" banner stays until it exists.

---

## 5. The bottom line

Glass is a single self-hosting functional language that contains its own
from-scratch zk-STARK and can take real source code to a proof of its result
(and, on the legacy Baby Bear path, a proof of a function's return refinement).
The differential-testing discipline behind it is rigorous.

It is **not production cryptography**, and this document exists so that nobody
mistakes the demonstration for one. Use Glass to *understand* and *verify the
ideas*, not to secure anything that matters.

*(See also: [`LANG.md`](../../LANG.md), "research language, not
production-hardened"; [`roadmap.md`](../roadmap.md); the
[internal audit](internal-audit-2026-06.md).)*
