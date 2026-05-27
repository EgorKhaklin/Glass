# Documentation

### Start here
- **[Glass, end to end](the-story.md)** — the whole arc in one read: one principle carried from a type signature to a zero-knowledge proof over private data. Every claim is a command you can run.

### Learn the language
- [Getting started](getting-started.md) — install and first programs.
- [A tour of the language](language-tour.md) — the feature walk-through.
- [The REPL](repl.md) — interactive sessions.
- [The browser playground](playground.md) — run Glass with no install.
- [Language specification](../LANG.md) — the full reference.
- [Operational semantics](semantics.md) — the explicit big-step rules (what a program *means*).

### How Glass is built
- [Self-hosting](self-hosting.md) — Glass compiling Glass, and the bootstrap fixpoint.
- [Quartz](quartz.md) — the Glass → C back end.
- [Migration](migration.md) — the road from a Python host to self-hosting *(historical record)*.
- [Design notes](design-notes.md) — release-by-release engineering diary (how features were built and verified).

### Honesty
- [Soundness](soundness.md) — what Glass's proofs *actually* guarantee: the strong differential-testing guarantee vs. the educational-grade cryptography, per component. Read this before trusting any "zero-knowledge" claim.

### Direction
- [Roadmap](roadmap.md) — where Glass is headed.
- [Effects in the proof story](effects-in-proofs.md) — a design: proving effectful (`IO`/`Random`/`Inference`) computations in zero-knowledge.

### Built in Glass
- [Frost](../examples/frost/) — a zero-knowledge proof system (zk-STARK) from scratch.
- [Pane](../examples/pane/) — a query language.
- [The prove bridge](../examples/prove/) — write Glass, get a zero-knowledge proof.
