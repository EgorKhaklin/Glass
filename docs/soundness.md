# Soundness — what Glass's proofs actually guarantee

Glass makes a lot of claims with the words *proof*, *zero-knowledge*, and
*sound*. This document is the honest ledger: **exactly which of those claims are
rigorous, which are educational, and where the real edges are.** It is written in
the same spirit as the language itself — you should never have to take the code's
word for it.

The short version, up front:

> **Glass is a from-scratch, self-hosted, differential-tested *demonstration* of a
> complete zk-STARK and a ZK-native language. The structure is real and checked.
> The cryptographic *parameters and primitives are educational-grade.* Do not use
> Glass to protect real value.**

There are two very different kinds of guarantee in this repository, and conflating
them is the main way to be misled. Keep them separate.

---

## 1. The differential-testing guarantee — *strong and real*

This is the guarantee Glass actually delivers rigorously, and it has nothing to do
with cryptography.

Every layer is a **reference semantics** plus a **compiler**, and they are forced
to agree **bit-for-bit**:

- `dogfood.sh <file>` runs a program on the reference interpreter (`glass.py`) and
  on the self-hosted compiler (`native_glassc`, Glass → C → native) and checks the
  output is **byte-identical**.
- `bootstrap_fixpoint.sh` checks that `native_glassc` compiles **itself** and
  `prism` byte-identically, with no Python in the loop (the fixpoint).
- The suite is **381/381**.

This is real and load-bearing. When a release says "dogfoods byte-identical," it
means a different implementation of the same semantics produced the same answer —
the project's actual crown jewel. **This guarantee is not cryptographic; it is a
correctness/consistency guarantee about the implementation.** It is the part of
Glass you can lean on hardest.

---

## 2. The cryptographic guarantee — *educational-grade, with specific caveats*

Glass builds, from scratch and in Glass, every structural piece of a zk-STARK:
finite field + extension field, a hash, Merkle trees, PLONK arithmetization, the
gate-constraint quotient, FRI low-degree testing, Fiat-Shamir, query amplification,
ZK blinding, and a permutation argument. **The structure is correct and
demonstrated** — honest inputs verify, tampered inputs are rejected, and blinding
makes two proofs of the same statement reveal different openings.

What is **not** production-grade is the **primitives and parameters**:

| Component | What's real | The honest caveat |
|---|---|---|
| **Base field** | Baby Bear (2³¹−2²⁷+1) is a genuine NTT-friendly prime | The prove bridge computes over it, so **values are capped near 2³¹** — real-world integers wrap. (Goldilocks, 2⁶⁴, is built — `frost_goldilocks*` — and demonstrated through FRI, but the bridge still defaults to Baby Bear.) |
| **Challenge space** | FRI challenges live in **F_{p⁴} ≈ 2¹²⁴** | This part *is* cryptographic-width: a cheating prover guesses a fold challenge with prob ~2⁻¹²⁴. The "toy" is the value range, not the challenge space. |
| **Hash** | MiMC (x⁵/x⁷ S-box) and a real-shaped **Poseidon** (x⁷, full/partial rounds, MDS) | **Educational round constants** (a fixed schedule, not the Grain-LFSR the spec mandates) and **unaudited** — not a vetted collision-resistant ZK hash. |
| **Fiat-Shamir** | Transcript-bound challenges + query amplification (soundness ~2⁻ᴷ) | The transcript is hashed with the educational hash above; no formal transcript-separation analysis. |
| **Goldilocks stack** | A complete sound + committed + zero-knowledge FRI over Goldilocks (`frost_goldilocks_zk`), int64-safe via limbs | A degree-2 extension F_{p²} ≈ 2¹²⁸ challenge space, but reduced rounds in the hash and **not wired into the source→ZK bridge** (that's roadmap R1b). |
| **ZK / blinding** | Trace/codeword blinding genuinely randomizes openings; two seeds → different openings | Demonstrates the *zero-knowledge property mechanism*; not a formal simulator-based proof of ZK. |

**No parameter analysis, no external audit, no constant-time guarantees.** Several
demos run *reduced rounds* explicitly so they dogfood on the interpreter; the
full-strength versions run the same way, just heavier.

---

## 3. The `glass prove` command, specifically

`glass prove <file>` emits a succinct, zero-knowledge proof that a Glass function
produced its result. The **arithmetization is faithful** (the circuit computes what
the function means — checked because the reference evaluator and the circuit agree),
the **proof structure is a real blinded F_{p⁴} FRI STARK**, and a wrong claim or a
violated refinement is **rejected**. But the **base field is Baby Bear** and the
**hash is educational**, so the *cryptographic* strength is demonstration-grade. It
proves the *idea* end to end; it is not a tool for protecting secrets in production.

---

## 4. What it would take to be production-sound

Roughly, in order:

1. **Real field through the bridge** — swap Baby Bear for Goldilocks end-to-end so
   values aren't capped at 2³¹ (roadmap **R1b**; the field and FRI exist, the
   integration is the work).
2. **A vetted hash** — Poseidon with the standard Grain-LFSR constants (or a
   reviewed alternative), with the MDS and round counts analyzed (roadmap **R2**).
3. **Fiat-Shamir rigor** — transcript domain separation and a soundness argument.
4. **Parameter analysis** — concrete soundness/ZK bounds for the chosen field,
   extension, query count, and blinding degree.
5. **An external audit.** None of the above replaces this.

---

## 5. The bottom line

Glass is, to our knowledge, a uniquely complete *demonstration*: a single
self-hosting functional language that contains its own from-scratch zk-STARK and
can take real source code to a zero-knowledge proof of its result — including
proving a function's own **refinement types**. That is a genuine and unusual thing,
and the differential-testing discipline behind it is rigorous.

It is **not production cryptography**, and this document is here so that nobody
mistakes the demonstration for one. Use Glass to *understand* and *verify the ideas*
— from a type signature all the way to a zero-knowledge proof — not to secure
anything that matters.

*(See also: [`LANG.md`](../LANG.md) — "research language, not production-hardened";
[`roadmap.md`](roadmap.md) — Track R, the path to real crypto.)*
