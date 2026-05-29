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
| **Base field** | **`glass prove`** (the default — no flag, v5.46) proves real prism-parsed source over **Goldilocks (2⁶⁴)** — a full cryptographic STARK (variable-N gate quotient `Q=G/Z_H`, embedded in F_{p²}, blinded, **Poseidon**-Merkle-committed, F_{p²}-challenged Fiat-Shamir, query-verified) with **multiple named private inputs**, **claim-binding** (asserts `output == result`), AND **`match` / algebraic data types** (multi-wire `cgen`, variable trace domain N=next_pow2(#gates)). Runs **natively** (~24s at ρ=1/2, ~160s at ρ=1/8 / ~65-bit). `glass prove --baby-bear` opts back into the old small-field path. | The default's value space is now the real **2⁶⁴** — the ~2³¹ brute-force gap (a private input guessable in ~2³¹ work) is **closed** for the default (v5.46). Goldilocks is bignum-heavy, so the default runs **native** (needs a C compiler + `libgc`; the interpreter is ~hours). A few surface forms beyond the arithmetic/`match`/ADT core (e.g. `let`-`where` refinements) may still need `--baby-bear`. This closes the *structural* (value-space) educational gap, not the audit one — see the banner. |
| **Challenge space** | FRI challenges live in **F_{p⁴} ≈ 2¹²⁴** | This part *is* cryptographic-width: a cheating prover guesses a fold challenge with prob ~2⁻¹²⁴. The "toy" is the value range, not the challenge space. |
| **Hash** | **Poseidon over Goldilocks, byte-identical to Plonky2** — the de-facto standard Goldilocks ZK hash — verified against **Plonky2's own published test vectors** (all four pass): t=12, R_F=8, R_P=22, S-box x⁷, Plonky2's exact MDS and all 360 round constants (the Poseidon reference's "hadeshash" Grain-LFSR constants), reproduced in `frost_goldilocks_poseidon.glass` and dogfooded byte-identical. It is also **load-bearing**: `frost_goldilocks_merkle.glass` builds a real Merkle commitment on it (Plonky2's exact `two_to_one` + `hash_no_pad`, inclusion proofs, tamper-rejection). (Also `frost_grain.glass`: a from-scratch Grain-LFSR generator + domain-separated transcript over Baby Bear.) | This settles "is it the standard hash" for the **primitive**: it matches a production reference exactly, and now drives a commitment. **It is now the in-STARK hash** of the Goldilocks prover (v5.45); getting there took two steps. First the *blocker* was removed in **v5.44** — wiring Poseidon in had OOM'd: the no-free native runtime accumulated Poseidon's ~300×-MiMC permutation allocations past 16 GB on even one proof. v5.44 gave the native backend a **conservative GC** (Boehm `GC_malloc`), so that same Poseidon prover now runs at **~10 MB instead of OOMing at 16 GB** — and the bootstrap fixpoint + suite (381/381) hold byte-identical with GC. **v5.45 wired it in:** the Goldilocks prover's Merkle commitment + Fiat-Shamir now hash with the 2-to-1 Poseidon sponge (`perm([a,b,0…])[0]`) — **MiMC is retired from that prover** (honest ACCEPT / wrong-claim REJECT verified native; Poseidon spliced **verbatim** from the dogfooded + vector-verified file above, and the bootstrap fixpoint + suite (381/381) are untouched — only the prover source changed; the full interpreter↔native Poseidon-proof dogfood is native-territory, multi-hour). Honest scope: Poseidon is ~300× MiMC, so the prover runs **native** (`run_native.sh` / `glass prove`): the shipped demo proves at **full strength** (ρ=1/8, coset 16N, 64 queries, real 12-bit grind) + ZK in ~2–3 min, the v5.44 GC keeping it at ~10 MB; the reference interpreter is multi-hour for a Poseidon STARK, so the native path is canonical (it dogfoods byte-identical there). The **default Baby Bear prover's hash is separate and still educational**. And matching a reference is **not an audit**: the hash itself is unaudited here. |
| **Fiat-Shamir** | Transcript-bound challenges + query amplification (soundness ~2⁻ᴷ); a **domain-separated transcript over the vector-verified Goldilocks Poseidon** (`frost_goldilocks_fiat.glass` — `tr_init`/`tr_absorb`/`tr_challenge` tag every message/squeeze by role; demonstrated determinism, role separation, history-binding) | The transcript now runs on the **standard, vector-verified hash** (not the toy MiMC) — a real upgrade. Still: **no formal transcript-separation proof**, and this *rich* transcript module (the `tr_*` API) isn't itself wired into the prover — though as of **v5.45** the Goldilocks prover's own inline Fiat-Shamir challenges (and its Merkle commitment) do hash with the vector-verified Poseidon, not MiMC. |
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

- **default — Goldilocks (2⁶⁴), v5.46:** the full feature set — `match` / ADTs — over the
  production field, with multiple private inputs, an F_{p²} ≈ 2¹²⁸ challenge extension, and
  **Poseidon** as the in-STARK hash (v5.45). A secret is no longer brute-forceable from the
  value range. Runs natively (the bignum field is ~hours in the interpreter).
- **`--baby-bear` (2³¹):** the original educational small-field prover (F_{p⁴} ≈ 2¹²⁴
  challenge), interpreter-only / Python-only — kept as a fast reference. Its *value range*
  is toy (a secret < 2³¹ is brute-forceable; results wrap above ~2.1·10⁹).

The field and hash are now real, but **structural soundness gaps** remain — this is why
it is **research-grade, not production**: (i) the prover's inline Fiat-Shamir transcript is
now **seeded with a digest of the statement** (`stmt_seed_of(gates)` over the gate list —
circuit structure + the `GConst` holding the claimed result R; CLI inputs stay private in
the witness and are never absorbed), threaded through `commit_g` so *every* challenge — the
FRI fold β's and the query positions — is a function of the statement (v5.x). But this is
**prover-side seeding only**: `verify` still reads each layer's *stored* β rather than
re-deriving it, so the binding is enforced only once the independent verifier exists — the
gap is **narrowed, not closed**. (ii) there is **no separate `verify(proof, public)`** —
the prover self-checks over the witness, which does not yet bound a *malicious* prover
(*the biggest structural gap*). It proves the idea end to end on the production field +
hash; it is **not** a tool for protecting secrets in production.

---

## 4. What it would take to be production-sound

Roughly, in order (✅ = done since this list was first written):

1. ✅ **Real field through the bridge (v5.46).** The **default** `glass prove` proves
   `match` / ADTs over **Goldilocks (2⁶⁴)** — values are no longer capped at 2³¹ (a
   variable-N FRI + multi-wire `cgen` + a fast `gold_*` field made it practical;
   `--baby-bear` keeps the toy field as an opt-in reference).
2. ✅ **A vetted hash (v5.45).** **Poseidon** (Plonky2-exact, vector-verified) is the
   in-STARK hash of the Goldilocks prover — Merkle commitment, Fiat-Shamir, query sampling.
   (Matching a reference is still **not** an audit.)
3. ⚠️ **Fiat-Shamir rigor — PARTIAL (v5.x).** The prover's inline transcript is now **seeded
   with a statement digest** (`stmt_seed_of(gates)` — circuit structure + the `GConst` for R),
   threaded through `commit_g` so the fold β's and query positions all depend on it. What
   remains: the **verifier must re-derive** those challenges from the statement-seeded
   transcript (today β is read from the stored layer — coupled to gap 4); the **final folded
   codeword** isn't yet absorbed before query sampling; protocol params aren't transcript-bound;
   and there's no formal transcript-separation / soundness argument. *Prover-side seeding done;
   verifier-side enforcement + the formal argument still to do.*
4. **A real verifier + soundness reduction** — split prover/verifier into a `verify(proof,
   public)` that never touches the witness; commit the **execution trace** (today only the
   quotient codeword is committed) and add the out-of-domain check tying the low-degree
   codeword to a *satisfying* trace. Today `glass prove` self-checks over the witness — it
   does not yet bound a malicious prover. *This is the biggest structural gap.*
5. **Parameters** — ✅ analysed ([`parameters.md`](parameters.md)) and **applied**: ρ=1/8 +
   64 queries + a real 12-bit grind ⇒ ~65-bit provable / ~108 list-decoding (Goldilocks).
   Reaching 80-bit *provable* needs ~82 queries (cheap, post the v5.41 memoization).
6. **An external audit + community cryptanalysis.** None of the above replaces this — the
   **hard boundary**. The "unaudited — do not protect real value" banner stays until it exists.

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
