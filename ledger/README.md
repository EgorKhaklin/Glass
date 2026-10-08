# The ledger: an append-only ledger of proof verdicts

A `glass prove` verdict is a moment in time. The ledger makes it a **record**:
each verdict is appended to `ledger/LEDGER` and committed into a Poseidon2-Merkle root
(`ledger/ROOT`). The root commits the whole history, so **no past entry can be altered,
reordered, or dropped without changing the root**, and an **inclusion proof** shows a
given verdict is in the ledger at a committed root.

Each line is `seq <TAB> statement <TAB> result <TAB> verdict`. It hashes with
`lens/poseidon.py`, the **same Poseidon2 (Plonky3-exact)** the prover and the second
verifier use: the ledger binds verdicts that already exist; it adds no new trust.

```bash
glass ledger append "<statement>" <result> <verdict>   # record a verdict, recommit the root
glass ledger root                                       # the current committed root
glass ledger list                                       # the entries
glass ledger prove <i>                                  # inclusion path for entry i
glass ledger verify <i>                                 # is entry i committed in ROOT?
glass ledger --selftest                                 # determinism + inclusion + tamper-evidence
```

The seeded `LEDGER` records early verdicts for the comparison gadget and an out-of-range
ABSTAIN. The test suite runs `--selftest` (determinism, inclusion
proofs verify, a forged entry does **not**, and tampering a past entry changes the root).

**Honest scope.** The ledger attests *what was claimed and how it was judged*, with
tamper-evidence over the history: it does not re-prove anything (that is `verify_b3` and
the Lens differential). Research/educational-grade, UNAUDITED: *do not protect real value*.
