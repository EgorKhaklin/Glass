# The Preserved Tablet — an append-only ledger of proof verdicts

A `glass prove` verdict is a moment in time. The Preserved Tablet makes it a **record**:
each verdict is appended to `ledger/LEDGER` and committed into a Poseidon-Merkle root
(`ledger/ROOT`). The root commits the whole history, so **no past entry can be altered,
reordered, or dropped without changing the root** — and an **inclusion proof** shows a
given verdict is in the ledger at a committed root.

Each line is `seq <TAB> statement <TAB> result <TAB> verdict`. It uses the **same
Plonky2-exact Poseidon** the prover and the second verifier (`pentecost/`) use — the
Tablet binds verdicts that already exist; it adds no new trust.

```bash
glass tablet append "<statement>" <result> <verdict>   # record a verdict, recommit the root
glass tablet root                                       # the current committed root
glass tablet list                                       # the entries
glass tablet prove <i>                                  # inclusion path for entry i
glass tablet verify <i>                                 # is entry i committed in ROOT?
glass tablet --selftest                                 # determinism + inclusion + tamper-evidence
```

The seeded `LEDGER` records the verdicts validated in v5.62–v5.64 (the comparison gadget
and the out-of-range ABSTAIN). The test suite runs `--selftest` (determinism, inclusion
proofs verify, a forged entry does **not**, and tampering a past entry changes the root).

**Honest scope.** The Tablet attests *what was claimed and how it was judged*, with
tamper-evidence over the history — it does not re-prove anything (that is `verify_b3` and
the Pentecost differential). Research/educational-grade, UNAUDITED — *do not protect real value*.
