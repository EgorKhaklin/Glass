# Documentation

### The language
- [Getting started](language/getting-started.md): install, first programs, the native toolchain.
- [A tour](language/tour.md): every feature, one example at a time.
- [Specification](../LANG.md): the full reference.
- [Semantics](language/semantics.md): the big-step rules that say what a program means.
- [The REPL](language/repl.md) and [the browser playground](language/playground.md).

### The compiler
- [Self-hosting](compiler/self-hosting.md): Glass compiling Glass, and the byte-identical fixpoint.
- [Quartz](compiler/quartz.md): the Glass to C back end.

### Security
- [Soundness](security/soundness.md): what a proof does and does not guarantee, per component. Read this before relying on any proof.
- [Soundness proof](security/soundness-proof.md): the pen-and-paper reduction for the prover.
- [Parameters](security/parameters.md): field, hash, FRI parameters and the bit accounting.
- [Faithful lowering](security/faithful-lowering.md): the compiler-to-circuit layer, the part no soundness proof covers.
- [Audit readiness](security/audit-readiness.md): threat model, assumptions, and where an auditor should start.
- [Internal audit, June 2026](security/internal-audit-2026-06.md): findings and their fixes.

### Direction
- [Roadmap](roadmap.md): the staged plan for Glass and Tiresias.

### The components
| Name | What it is | Where |
|---|---|---|
| Prism | The self-hosted front end: parser, type checker, evaluator | [`examples/selfhost/prism.glass`](../examples/selfhost/prism.glass) |
| Quartz | The native back end, Glass to C | [`quartz.py`](../quartz.py), [`examples/selfhost/glassc.glass`](../examples/selfhost/glassc.glass) |
| Frost | A zk-STARK written from scratch in Glass | [`examples/frost/`](../examples/frost/) |
| Pane | A query algebra | [`examples/pane/`](../examples/pane/) |
| Lens | The independent verifier, in Python | [`lens/`](../lens/) |
| The fingerprint | One Poseidon-Merkle root over the core | [`fingerprint/`](../fingerprint/) |
| The ledger | An append-only record of proof verdicts | [`ledger/`](../ledger/) |
| Disclose | Selective disclosure over a commitment | [`disclose/`](../disclose/) |
