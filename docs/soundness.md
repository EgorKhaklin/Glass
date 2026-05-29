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
| **Base field** | **`glass prove --goldilocks`** proves real prism-parsed source over **Goldilocks (2⁶⁴)** — a full cryptographic STARK (gate quotient `Q=G/Z_H`, embedded in F_{p²}, blinded, Merkle-committed, F_{p²}-challenged Fiat-Shamir, query-verified), with **multiple named private inputs** and **claim-binding** (asserts `output == result`). Covers `+ - * let calls == if` (`prove_source_goldilocks_zk.glass`; `prove_circuit_goldilocks_zk.glass` for hand-built circuits). | The Goldilocks path covers the **arithmetic/comparison subset** and is **heavier on the interpreter** (bignum). The **default `glass prove` still uses Baby Bear** (`prove_source_adt_zk`) for the full `match`/ADT/refinement feature set — there values are capped near 2³¹. Extending the Goldilocks path to `match`/ADTs is the remaining step. |
| **Challenge space** | FRI challenges live in **F_{p⁴} ≈ 2¹²⁴** | This part *is* cryptographic-width: a cheating prover guesses a fold challenge with prob ~2⁻¹²⁴. The "toy" is the value range, not the challenge space. |
| **Hash** | **Poseidon over Goldilocks, byte-identical to Plonky2** — the de-facto standard Goldilocks ZK hash — verified against **Plonky2's own published test vectors** (all four pass): t=12, R_F=8, R_P=22, S-box x⁷, Plonky2's exact MDS and all 360 round constants (the Poseidon reference's "hadeshash" Grain-LFSR constants), reproduced in `frost_goldilocks_poseidon.glass` and dogfooded byte-identical. It is also **load-bearing**: `frost_goldilocks_merkle.glass` builds a real Merkle commitment on it (Plonky2's exact `two_to_one` + `hash_no_pad`, inclusion proofs, tamper-rejection). (Also `frost_grain.glass`: a from-scratch Grain-LFSR generator + domain-separated transcript over Baby Bear.) | This settles "is it the standard hash" for the **primitive**: it matches a production reference exactly, and now drives a commitment. **But it is not yet integrated into the STARKs** — their Merkle + Fiat-Shamir still use the educational MiMC (Poseidon is ~300× heavier per call, so the full FRI integration is the heavier follow-on). And matching a reference is **not an audit**: the hash itself is unaudited here. |
| **Fiat-Shamir** | Transcript-bound challenges + query amplification (soundness ~2⁻ᴷ); a **domain-separated transcript over the vector-verified Goldilocks Poseidon** (`frost_goldilocks_fiat.glass` — `tr_init`/`tr_absorb`/`tr_challenge` tag every message/squeeze by role; demonstrated determinism, role separation, history-binding) | The transcript now runs on the **standard, vector-verified hash** (not the toy MiMC) — a real upgrade. Still: **no formal transcript-separation proof**, and it isn't yet wired into the actual proving STARK's challenges (those still use MiMC). |
| **Goldilocks stack** | A complete sound + committed + zero-knowledge FRI over Goldilocks (`frost_goldilocks_zk`), int64-safe via limbs | A degree-2 extension F_{p²} ≈ 2¹²⁸ challenge space; reduced rounds in the standalone hash. This `frost_goldilocks_zk` is the from-scratch reference; the **bridge's own Goldilocks STARK** (`prove_source_goldilocks_zk`, R1c — now **ρ=1/8**, see the Base field row) carries the actual source→ZK path. |
| **ZK / blinding** | Trace/codeword blinding genuinely randomizes openings; two seeds → different openings | Demonstrates the *zero-knowledge property mechanism*; not a formal simulator-based proof of ZK. |

**The parameters are now analyzed** — see [`parameters.md`](parameters.md) for the
concrete bit-security of both paths. The short version: the challenge space is
cryptographic-width ≈2¹²⁴–2¹²⁸, and the FRI *query phase* on the **Goldilocks path
is now hardened** to **~65-bit provable / ~108-bit list-decoding** query soundness
(ρ=1/8 via a blowup-8 coset + 64 queries + a 12-bit grind — past 80 bits by the
list-decoding standard modern STARKs use, ~65 by the conservative provable one; up
from ~25–28, and ~4 raw). The **default Baby Bear path** is now **also ρ=1/8** (~53
provable / ~96 list-decoding bits, v5.43); its remaining weakness is the **2³¹ value
space** (a secret is brute-forceable independent of the proof), not the FRI. §4 there
gives the recipe to 80/128-bit across the board.
Still **no external audit and no constant-time guarantees.**
Several demos run *reduced rounds/queries* explicitly so they dogfood on the
interpreter; the full-strength versions run the same way, just heavier.

---

## 3. The `glass prove` command, specifically

`glass prove <file>` emits a succinct, zero-knowledge proof that a Glass function
produced its result. The **arithmetization is faithful** (the circuit computes what
the function means — checked because the reference evaluator and the circuit agree),
the **proof structure is a real blinded FRI STARK**, and a wrong claim or a violated
refinement is **rejected**. Two fields are available:

- **default (Baby Bear, 2³¹):** the full feature set — `match`/ADTs/refinements — over
  an F_{p⁴} ≈ 2¹²⁴ challenge extension. The *value range* is toy (a secret < 2³¹ is
  brute-forceable; results wrap above ~2.1·10⁹).
- **`--goldilocks` (2⁶⁴):** the production field for the arithmetic/comparison subset
  with multiple private inputs (F_{p²} ≈ 2¹²⁸ challenge). Heavier on the interpreter.

The **hash is still educational** (MiMC inside the proving STARK; the vector-verified
Poseidon is built and load-bearing in a Merkle commitment + transcript, but not yet
wired into the prove bridge). So the *cryptographic* strength is demonstration-grade.
It proves the *idea* end to end; it is not a tool for protecting secrets in production.

---

## 4. What it would take to be production-sound

Roughly, in order:

1. **Real field through the bridge** — swap Baby Bear for Goldilocks end-to-end so
   values aren't capped at 2³¹ (roadmap **R1b**). *Underway:* `glass prove --goldilocks`
   already proves the arithmetic/comparison subset (multi-input, claim-bound) over
   Goldilocks; remaining is `match`/ADTs/refinements over the bignum field so the
   **default** path can move off Baby Bear.
2. **A vetted hash** — Poseidon with standard constants, MDS, and round counts
   (roadmap **R2**). *Largely done at the primitive level:* `frost_goldilocks_poseidon.glass`
   is **byte-identical to Plonky2's Goldilocks Poseidon** and verified against its
   published test vectors — a real, standard instance, not a hand-rolled one. Still
   to do: **wire it into the prove/frost STARKs** (they still hash with MiMC), and
   note that matching a reference is not a substitute for an audit.
3. **Fiat-Shamir rigor** — transcript domain separation (done: `frost_goldilocks_fiat.glass`)
   and a formal soundness argument (still to do).
4. **Parameter analysis** — ✅ *done:* [`parameters.md`](parameters.md) gives the
   concrete bit-security and the recipe to 80/128-bit (lower rate + more queries +
   grinding). What remains is *applying* those parameters (which costs prover time).
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
