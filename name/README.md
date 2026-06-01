# The Name — Glass's content-addressed canonical identity

> *"To the one who conquers … I will give a white stone, and on the stone a new name
> written, which no one knows except the one who receives it."* — Revelation 2:17

The bootstrap fixpoint proves the **compiler** is the same in two tongues; the Pentecost
differential proves the **verifier** is the same in two tongues. The Name binds *all of it*
into one number: a single Poseidon-Merkle root over the artifacts that **are** Glass —

- the self-hosting core: `examples/selfhost/glassc.glass`, `examples/selfhost/prism.glass`, `glass.py`, `quartz.py`
- the prover + `verify_b3` bridge: `examples/prove/prove_source_goldilocks_zk.glass`
- the second, independent verifier: `pentecost/pentecost_verify.py`, `pentecost/poseidon.py`, `pentecost/_gold_constants.py`
- the test suite: `tests/test_glass.py`
- the language semantics: `LANG.md`

Recompute it and match `name/NAME`, and you have attested — byte-for-byte, with the *same*
Poseidon-over-Goldilocks the prover and the second verifier use (Plonky2-exact) — that this
is the same Glass. The fixpoint, turned into a publicly-checkable fingerprint.

```bash
python3 name/glass_name.py            # print the Name + per-artifact leaf digests
python3 name/glass_name.py --check    # recompute and compare to name/NAME  (exit 0/1)
python3 name/glass_name.py --write    # regenerate name/NAME for the current tree
glass name [--check|--write]          # same, via the CLI
```

`name/NAME` is kept current **lockfile-style**: any edit to a canonical artifact changes the
Name, so a canonical change must be accompanied by `--write`. The test suite runs `--check`,
so a stale `NAME` fails the gate — drift cannot pass silently. The path **and** the content of
each artifact are bound (a rename changes the Name).

**Honest scope.** The Name is an integrity/identity primitive — it attests *which* Glass you
have, not that that Glass is *correct* (that is the fixpoint, the soundness gate, and the
Pentecost differential). It adds no new trust; it binds what is already there. Built on the
same UNAUDITED, research-grade construction — *do not protect real value*.
