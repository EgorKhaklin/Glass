# Lens: let the verifier be two

Glass's **compiler** has two implementations, the reference interpreter `glass.py` and the
self-hosted `native_glassc`, forced to agree byte for byte (the bootstrap fixpoint). Its
**cryptographic verifier**, `verify_b3` in
[`../examples/prove/prove_source_goldilocks_zk.glass`](../examples/prove/prove_source_goldilocks_zk.glass),
would otherwise stand alone.

Lens is the second verifier: a **from-scratch, independent re-implementation of the same
zk-STARK verification algorithm in Python**, sharing *no code* with the Glass prover. It reads
a serialized proof and the public gate list, re-derives every Fiat-Shamir challenge, re-checks
the per-row gate identity, the PLONK grand product, the FRI low-degree test, the Merkle
openings, query sampling, and the grind, and returns ACCEPT or REJECT. Differential agreement
with the in-Glass `verify_b3` is what *"let the verifier be two"* means.

The independence is in representation and language: Glass represents a Goldilocks element as
a base-2¹⁶ limb list; Lens uses plain Python `int mod p` (with the F_{p²} extension `u² = 7`).

## Status

| Piece | State |
|---|---|
| **End-to-end differential** | Done. Glass's native prover emits a real `ProofB3` as a token stream (`gprove_emit`, exposed as `glass prove --emit`); Lens checks it. Honest proof: ACCEPT, agreeing with `verify_b3`. Tampered root, wrong claim, or tampered opening: REJECT. `bash lens/difftest.sh` exits 0 iff the honest proof ACCEPTs and every tamper REJECTs. |
| **Poseidon2** | Byte-exact to Plonky3's published vector: the full 12-lane `perm([0..11])` (lane 0 `== 0xf292ab67c0f14b03`), the same vector Glass's native `poseidon2_perm` is checked against. Lens derives the permutation independently from the published constants (`_gold_constants.py`) and shares no code with Glass. Gated by `test_poseidon.py` in the regression suite. |
| **Proof corpus** | Committed, gzipped fixtures in `corpus/` (`a+b`, `a*b`, `a*a+b`, `a<b`, `a/b`, a record, a string equality, a string-valued result) are checked honest-ACCEPT and tamper-REJECT by `fuzz/corpus_check.py`. |

## Run

```bash
bash lens/difftest.sh                            # emit a Glass proof, check it, tamper it
python3 -m lens.test_poseidon                    # the Poseidon2 vector gate
python3 -m lens.verify <serialized_proof_file>   # verify a proof from `glass prove --emit`
glass verify <serialized_proof_file>             # the same, via the CLI
```

## Honest scope

Both verifiers are built from the same public specs, so a shared *spec* misreading would fool
both. Lens catches implementation divergence in `verify_b3` (a bug class the compiler fixpoint
cannot see). It does not make the soundness reduction machine-checked; that reduction remains
pen-and-paper ([`soundness-proof.md`](../docs/security/soundness-proof.md)). A check that does
not descend from the spec, plus an external audit, remain the standing boundary.
Research/educational-grade, UNAUDITED: *do not protect real value*.
