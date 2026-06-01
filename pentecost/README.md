# Pentecost — let the verifier be two

> *"By the mouth of two or three witnesses shall every word be established."* — Deut 19:15

Glass's **compiler** has two witnesses: the reference interpreter `glass.py` and the
self-hosted `native_glassc`, forced to agree byte-for-byte (the bootstrap fixpoint).
But its **cryptographic verifier** — `verify_b3` in
[`../examples/prove/prove_source_goldilocks_zk.glass`](../examples/prove/prove_source_goldilocks_zk.glass)
— stood **alone**. The crown-jewel soundness guarantee was two-witnessed everywhere
except at the verdict itself.

Pentecost is the second tongue: a **from-scratch, independent re-implementation of
the same zk-STARK verification algorithm in Python**, sharing *no code* with the
Glass prover. It reads a serialized proof + public gate list, re-derives every
Fiat-Shamir challenge, re-checks the per-row gate identity, the PLONK grand product,
the FRI low-degree test, and the Merkle openings — and returns ACCEPT / REJECT.
Differential agreement with the in-Glass `verify_b3` on the proof corpus is what
*"let the verifier be two"* means. (See [`../docs/revelation.md`](../docs/revelation.md).)

The independence is genuine, not cosmetic: Glass represents a Goldilocks element as a
base-2¹⁶ limb list; Pentecost uses plain Python `int mod p`. Two different
representations, two different languages, one verdict that must coincide.

## Status

| Piece | State |
|---|---|
| **End-to-end differential** | ✅ **LANDED (v5.64.0).** Glass's native prover emits a real `ProofB3` as a token stream (`emit_proofb3`, byte-for-byte with `parse()`); this verifier checks it. **Honest → ACCEPT (agreeing with Glass's own `verify_b3`); tampered root / wrong claim / tampered opening → REJECT.** Reproduce: `bash pentecost/difftest.sh` (exits 0 iff honest ACCEPT and every tamper REJECTs). The deepest soundness caveat — "`verify_b3` is reasoned, not machine-checked" — is retired for the B3 path. |
| **Poseidon2 (the cryptographic keystone)** | ✅ **byte-exact**, validated against Plonky3's published vector — the **full 12-lane** `perm([0..11])` (lane 0 `== 0xf292ab67c0f14b03`), the *same* vector Glass's native `poseidon2_perm` is checked against. This is the hardest, riskiest part, and it is grounded against a third party (Plonky3). As of **v5.70.0** the live bridge hash is Poseidon2 and Pentecost matches it in lock-step. See `test_poseidon.py` (now gated by the regression suite). |
| **Honest scope** | The second verifier is built from **public specs**, not a trusted third-party oracle — it catches implementation bugs in `verify_b3`, not a shared spec misreading. A truly independent oracle (the "Third Witness") and an external audit remain the standing boundary; *do not protect real value*. |

> **Poseidon2 (Plonky3), as of v5.70.0.** The bridge's `hashg` and this verifier both use
> Poseidon2 over Goldilocks (t=12, cheaper linear layers — the modern Plonky3/Stwo hash),
> migrated in **lock-step** so the two witnesses never disagree. Both are validated against
> Plonky3's published permutation vectors (`goldilocks/src/poseidon2.rs`); Pentecost re-derives
> the permutation **independently** in plain `int mod p` — sharing no code with Glass's native
> `poseidon2_perm` — and matches only at the vector. (The pre-v5.70 Plonky2 v1 perm survives only
> as the readable reference + `poseidon_difftest.glass` spec in the bridge.)
| **Goldilocks field + F_{p²} extension** | ✅ written (plain `int mod p`; `u²=7`) |
| **The full verifier** (`verify_b3`: FS transcript, INTT-interpolated public/permutation columns, out-of-domain gate identity, grand product, FRI fold + Merkle query check, query sampling, grind) | ✅ written, faithful to the verified port spec (`pentecost_verify.py`) |
| **End-to-end differential validation** (honest proof → ACCEPT; tampered → REJECT; agrees with Glass) | ⏳ **the remaining step** — see below |

## What remains, and why

Full differential validation needs a *serialized proof* to feed Pentecost. Two
findings gate it:

1. **No proof-emit path yet.** `glass prove` proves-and-verifies in-process; the
   `ProofB3` object is never written out. A small Glass serializer driver (sketched
   in the port spec) must emit `(gates, proof)` in the length-prefixed token format
   `pentecost_verify.parse` reads. The proof is ~115k integers even for a tiny
   circuit (82 FRI queries × Merkle paths) — large but parseable.

2. **Generating a proof is slow** — the very bottleneck the speed-cut targets: a
   single proof takes minutes-to-hours through the interpreter and >15 min native,
   because Goldilocks arithmetic is boxed base-2¹⁶ limb-lists. The companion
   "unbox the field" cut (roadmap item P) makes proof generation fast, which
   unblocks Pentecost's end-to-end loop directly. *The two North-Star directions
   converge: a faster prover both lands comparisons and lets the second witness
   speak.*

A third, incidental finding: the **Goldilocks bridge contains a non-exhaustive list
match** that `glass.py`'s v5.55.0 exhaustiveness checker rejects (the bridge is
normally compiled by the looser `native_glassc`, so it never surfaced). Same class
as the v5.56.0 baby-bear fix — worth closing so the bridge can be type-checked by
either front end.

## Run

```bash
bash pentecost/difftest.sh                   # the FULL differential: emit a Glass proof, check it,
                                             #   tamper it — exits 0 iff honest ACCEPT + every tamper REJECT
python3 -m pentecost.test_poseidon           # the Poseidon keystone gate
python3 -m pentecost.pentecost_verify <serialized_proof_file>   # verify a proof emitted by `emit_proofb3`
```

The full differential is **green** (v5.64.0): the second, independent verifier ACCEPTs honest
Glass proofs and REJECTs tampered ones. What it is *not* yet: a **trusted** second opinion in the
audit sense — both verifiers are built from the same public specs, so a shared *spec* misreading
would fool both. It catches implementation divergence in `verify_b3` (the bug class `gen1 == gen2`
cannot), which is the deepest in-repo soundness upgrade available; a third witness that does **not**
descend from the spec, plus an external audit, stay the standing boundary. *Do not protect real value.*
