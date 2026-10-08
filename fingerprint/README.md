# The fingerprint: Glass's content-addressed canonical identity

The bootstrap fixpoint shows the **compiler** agrees across two implementations; the Lens
differential shows the **verifier** does. The fingerprint binds *all of it* into one number: a
single Poseidon2-Merkle root over the artifacts that **are** Glass:

- the self-hosting core: `examples/selfhost/glassc.glass`, `examples/selfhost/prism.glass`, `glass.py`, `quartz.py`
- the prover + `verify_b3` bridge: `examples/prove/prove_source_goldilocks_zk.glass`
- the second, independent verifier: `lens/verify.py`, `lens/poseidon.py`, `lens/_gold_constants.py`
- the test suite: `tests/test_glass.py`
- the language semantics: `LANG.md`

Recompute it and match `fingerprint/FINGERPRINT`, and you have attested, byte for byte, that this
is the same Glass. It hashes with `lens/poseidon.py`, the same Poseidon2 over Goldilocks
(Plonky3-exact) the prover and the second verifier use.

```bash
python3 fingerprint/fingerprint.py            # print the fingerprint + per-artifact leaf digests
python3 fingerprint/fingerprint.py --check    # recompute and compare to fingerprint/FINGERPRINT  (exit 0/1)
python3 fingerprint/fingerprint.py --write    # regenerate fingerprint/FINGERPRINT for the current tree
glass fingerprint [--check|--write]          # same, via the CLI
```

`fingerprint/FINGERPRINT` is kept current **lockfile-style**: any edit to a canonical artifact changes the
fingerprint, so a canonical change must be accompanied by `--write`. The test suite runs `--check`,
so a stale `FINGERPRINT` fails the gate: drift cannot pass silently. The path **and** the content of
each artifact are bound (a rename changes the fingerprint).

**Honest scope.** The fingerprint is an integrity/identity primitive: it attests *which* Glass you
have, not that that Glass is *correct* (that is the fixpoint, the soundness gate, and the
Lens differential). It adds no new trust; it binds what is already there. Built on the
same UNAUDITED, research-grade construction: *do not protect real value*.
