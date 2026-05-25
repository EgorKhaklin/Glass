# Frost — a zero-knowledge proof system, built in Glass

Frost is a zk-STARK written from scratch in Glass: its own finite field, hash,
Merkle trees, arithmetization, polynomial machinery, low-degree test, and the
two ingredients of cryptographic security — a real extension field and
amplified Fiat-Shamir queries — ending in **a proof that a computation ran
correctly, that is sound, succinct, *and* zero-knowledge.**

No libraries. No elliptic curves. Every file runs on the interpreter and
compiles identically through the self-hosted toolchain.

## Read it as a journey

**Arithmetize — turn computation into algebra**
1. [`frost.glass`](frost.glass) — finite field, arithmetic circuits, lowering predicates to gates.
2. [`frost_commit.glass`](frost_commit.glass) — a hash (MiMC) and Merkle trees: how to commit to data.
3. [`frost_query.glass`](frost_query.glass) — a whole query compiled to a circuit (the range/comparison gadget).
4. [`frost_zk.glass`](frost_zk.glass) — one circuit proving *membership ∧ a query result*.

**Prove — convince a verifier without re-running everything**
5. [`frost_prove.glass`](frost_prove.glass) — Fiat-Shamir + random linear combination: a sound, non-interactive proof.
6. [`frost_pcs.glass`](frost_pcs.glass) — polynomial interpolation: the bridge from data to polynomials.

**FRI — the low-degree test at the heart of a STARK**
7. [`frost_fri.glass`](frost_fri.glass) — folding: a low-degree polynomial collapses to a constant.
8. [`frost_stark.glass`](frost_stark.glass) — commit every round + a query phase that catches a cheating prover.
9. [`frost_air.glass`](frost_air.glass) — a full AIR: prove a *computation* via a low-degree quotient.

**Make it cryptographic**
10. [`frost_fiat.glass`](frost_fiat.glass) — Fiat-Shamir query sampling + amplification (soundness → 2⁻ᴷ).
11. [`frost_ext.glass`](frost_ext.glass) — an extension field F_{p⁴} (~2¹²⁴), all in int64.
12. [`frost_fri_ext.glass`](frost_fri_ext.glass) — folding with extension-field challenges.
13. [`frost_crypto.glass`](frost_crypto.glass) — the two soundness axes composed into one FRI.

**Make it zero-knowledge**
14. [`frost_zk_blind.glass`](frost_zk_blind.glass) — blinding: openings reveal nothing about the witness.
15. [`frost_perm.glass`](frost_perm.glass) — the permutation argument (copy constraints).

**The capstone**
16. [`frost_starkzk.glass`](frost_starkzk.glass) — one end-to-end zk-STARK: sound, succinct, zero-knowledge.

> Honest note: the field and parameters are real enough to be *correct* and to
> demonstrate every property; the sizes are kept small so each file reads in one
> sitting. It's a working zk-STARK to learn from, not a hardened production prover.
