# Selective disclosure over a blinded commitment

`glass prove` proves a computation's result. `glass disclose` does something simpler: it lets
you **commit a record of named fields and later reveal any subset**, proving the revealed fields
are bound to the commitment while the rest stay hidden. It reveals chosen fields; it does not
prove predicates over hidden ones (for that, prove the predicate with `glass prove --zk`).

Each field is committed as a **blinded** leaf `Poseidon2(field ‖ value ‖ nonce)`, the nonce
derived from a secret seed; the commitment is a Poseidon2-Merkle root over the leaves. A
**presentation** carries `(field, value, nonce, inclusion-path)` for each revealed field; a
verifier recomputes the blinded leaf and its path to the root. The unrevealed fields stay
hidden: their blinded leaves disclose nothing (resting on Poseidon2's preimage resistance).

```bash
glass disclose commit name=Alice dob=1990 country=US id=42 --seed s3cr3t   # -> commitment root
glass disclose reveal /tmp/committed.json country                             # disclose ONLY country
glass disclose verify /tmp/presentation.json                               # revealed -> binds to root
glass disclose --selftest                                                  # bind + hide + tamper-evidence
```

It hashes with `lens/poseidon.py`: the same Poseidon2 as the prover, the second verifier, the
fingerprint, and the ledger. The suite runs `--selftest`: a revealed field binds to the root, a
tampered value or path does **not**, changing a hidden field moves the root, and a different
seed re-blinds.

**Honest scope.** Binding comes from the Merkle root; **hiding rests on Poseidon2**, which is
UNAUDITED. This demonstrates the selective-disclosure shape: it is not a hardened credential
system. Research/educational-grade: *do not protect real value*.
