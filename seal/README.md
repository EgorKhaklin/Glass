# Opening the Seals — selective disclosure over a blinded commitment

A `glass prove` proof reveals only its result. Opening the Seals does the dual: it lets you
**commit a record of named fields and later reveal any subset**, proving the revealed fields
are bound to the commitment while the rest stay hidden. This is the canonical ZK move —
*prove you are over 21 without revealing your birthdate* — generalized to arbitrary records.

Each field is committed as a **blinded** leaf `Poseidon(field ‖ value ‖ nonce)`, the nonce
derived from a secret seed; the commitment is a Poseidon-Merkle root over the leaves. A
**presentation** carries `(field, value, nonce, inclusion-path)` for each revealed field; a
verifier recomputes the blinded leaf and its path to the root. The unrevealed fields never
leave the seal — their blinded leaves disclose nothing (resting on Poseidon's preimage/hiding).

```bash
glass seal commit name=Alice dob=1990 country=US id=42 --seed s3cr3t   # -> commitment root
glass seal reveal /tmp/sealed.json country                             # disclose ONLY country
glass seal verify /tmp/presentation.json                               # revealed -> binds to root
glass seal --selftest                                                  # bind + hide + tamper-evidence
```

Same Plonky2-exact Poseidon as the prover, the second verifier (`pentecost/`), the Name, and
the Preserved Tablet. The suite runs `--selftest`: a revealed field binds to the root, a
tampered value or path does **not**, changing a hidden field moves the root, and a different
seed re-blinds.

**Honest scope.** Binding comes from the Merkle root; **hiding rests on Poseidon**, which is
UNAUDITED. This demonstrates the selective-disclosure shape — it is not a hardened credential
system. Research/educational-grade — *do not protect real value*.
