# Security policy & honest scope

> ## ⛔ Do not protect real value with Glass.
> Glass is **research / educational-grade** cryptography and is **UNAUDITED**. Its zero-knowledge
> prover is a from-scratch zk-STARK built to *learn and demonstrate* how these systems work — not to
> secure real assets, secrets, or money. Use it to study, teach, and experiment. **Do not** use it
> where a soundness or zero-knowledge failure would cause real harm.

This file states, plainly, what has and has not been verified, so no one mistakes the project for
something it isn't. It is the honest companion to the marketing in the README.

## What "UNAUDITED" means here (and what would change it)

The banner above is gated on two things that **cannot be produced inside this repository** — not by
the maintainers, not by any automated review:

1. **An independent, external, professional security audit** of the protocol, the soundness
   reduction, the zero-knowledge argument, the implementation, and the parameter choices. A
   self-review — however rigorous — is not an audit.
2. **Cryptanalysis of Poseidon2** by hash-function specialists. The *entire* soundness *and*
   zero-knowledge guarantee is conditional on Poseidon2 behaving as a random oracle (collision- and
   preimage-resistant). If that assumption fails, the security bound is vacuous.

Until **both** are done by qualified external parties, Glass stays research-grade and the banner
stays. See [`docs/security-audit-2026-06.md`](docs/security-audit-2026-06.md) §5 for the full list of
steps to production.

## Threat model — verified vs assumed

**Internally verified** (machine-checked or differentially tested, in-repo):

- An independent, **witness-free verifier** (`verify_b3`) checks per-row gate soundness, PLONK
  grand-product wire consistency, public-input/result pinning, and FRI — re-deriving every
  Fiat-Shamir challenge (no prover-supplied challenge is trusted).
- **A second, independent verifier** (`pentecost/`, plain Python, sharing no Glass code) accepts the
  same proofs and rejects tampers (`pentecost/difftest.sh`) — catching an *implementation* divergence
  in `verify_b3`.
- **The Third Witness** re-runs the source under the reference interpreter (a lineage independent of
  the bridge's evaluator *and* its circuit lowering), catching a source↔circuit lowering gap the two
  circuit-verifiers cannot.
- **Differential fuzzing** across the program families + boundary inputs + 1,600 adversarial tampers,
  with zero wrong-ACCEPTs; a **self-hosting fixpoint** (`native_glassc` reproduces its own source +
  output byte-identically); a content-addressed **Name** over the whole core.
- An **internal adversarial audit** (2026-06): 0 critical, no live soundness hole in the reachable
  prover paths (1 high — a ZK mislabelling in `--zk` — found and fixed in v5.118).

**Assumed / not verifiable in-repo** (the hard boundary):

- **Poseidon2 is a secure hash** (random-oracle model). Not cryptanalyzed here. The byte-exactness to
  the published Plonky3 vectors is verified; the *security* of the parameters is assumed.
- **Fiat-Shamir is sound in the ROM** — a standard heuristic.
- The **~135-bit list-decoding** figure rests on a **conjectural** FRI proximity-gap (decoding-to-
  capacity) bound. The conjecture-free, conservative figure is **~80-bit (unique-decoding)** — treat
  that as the security level. The `glass prove` `security:` line labels the conjectural figure inline.
- **Both verifiers descend from the same public specs**, so they catch an implementation divergence,
  **not** a shared spec misread. A genuinely independent third oracle remains future work.
- Zero-knowledge is **opt-in** (`--zk`); the default `glass prove` is **sound but not hiding** (the
  witness is opened in the clear). The `--zk` masking RNG is an idealization.

## Reporting

This is a research project; please open a GitHub issue for security-relevant findings (there is no
production deployment to protect, so coordinated disclosure is not required). Findings that show a
**wrong-ACCEPT** (a verifier accepting a false statement) or a **ZK leak** are especially valuable —
the project's whole discipline is to *abstain loudly* rather than ever prove something false, and a
counterexample to that is the most useful bug you can file.

## Further reading

- [`docs/security-audit-2026-06.md`](docs/security-audit-2026-06.md) — the internal audit (findings + readiness + external steps)
- [`docs/soundness.md`](docs/soundness.md) — the soundness argument and its honest scope
- [`docs/audit-readiness.md`](docs/audit-readiness.md) — what an external auditor would build on
- [`docs/parameters.md`](docs/parameters.md) — concrete parameters and bit-security
- [`pentecost/`](pentecost/) — the second, independent verifier
