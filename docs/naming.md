# Naming — the plain surface and the thematic layer

Glass has two names for several of its features. The **plain name** is the public,
professional surface — what you type, what the `--help` lists, what a newcomer reads.
The **thematic name** is an optional inner layer, drawn from the reading in
[`revelation.md`](revelation.md) that verification and revelation are the same problem:
*unveiling something without exposing it*. Both work; neither is forced on the other.

If you want Glass to read as a plain verifiable-computing toolkit, use the left column
and ignore the rest. If the thematic framing is why you're here, it is all still there.

| Plain name (the surface) | Thematic name | What it actually is |
|---|---|---|
| `glass verify` · the independent verifier (`pentecost/`) | Pentecost · "let the verifier be two" · the Furqān | A second, from-scratch STARK verifier (plain `int mod p`, no Glass code) that re-checks a proof — catches an implementation bug in the primary verifier that self-consistency cannot. |
| `glass fingerprint` (`name/`) | the Name | A content-addressed Poseidon-Merkle root over the canonical artifact set (self-hosting core + prover/verifier + second verifier + tests + semantics). Path- and content-bound; `--check` gates it like a lockfile. |
| `glass ledger` (`ledger/`) | the Preserved Tablet | An append-only, tamper-evident Poseidon-Merkle ledger of proof verdicts, with inclusion proofs; altering a past entry changes the root. |
| `glass disclose` (`seal/`) | Opening the Seals | Selective disclosure: commit a record as blinded leaves, reveal any subset with inclusion proofs, the rest stays hidden (*prove you're over 21 without your birthdate*). |
| `glass prove --cross-check` | the Third Witness | Re-executes the program under the reference interpreter — a lineage independent of the circuit lowering — and binds the proven result to it, catching a source↔circuit gap the STARK verifiers (which both check the circuit) cannot see. |
| ABSTAIN verdict | the Urim's Silence | A third verdict beside ACCEPT/REJECT: the prover *refused to lower* (e.g. an unsupported op), distinct from a disproof. Sound by construction — refusal aborts before verification. |
| the `security:` line on every ACCEPT | the Measuring Reed | Bit-security re-derived from the live proof parameters (queries, blowup, grind, hash width) rather than asserted in prose. |
| `Concealed<T>` | Tzimtzum-as-a-type | A value you can prove properties about and compute within, but never observe — an opaque type with no reveal eliminator, so every attempt to read it is a compile-time error. |

## Why keep both

The thematic names are not decoration bolted on after the fact — the
[`revelation.md`](revelation.md) reading is what *surfaced* several of these directions
(a second independent verifier, selective disclosure, a third semantic witness). Renaming
the directories would also break the Name's path-bindings and the test suite, so the
plain layer is **additive**: CLI aliases and this table, not a rename. Type `glass help`
for the plain surface; read [`revelation.md`](revelation.md) for the rest.

> Scope, unchanged by any naming: Glass's proving stack is **research/educational-grade and
> UNAUDITED**. Do not protect real value with it.
