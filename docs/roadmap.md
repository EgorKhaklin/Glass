# Roadmap: raising the temple

Glass and Tiresias are built as one temple. Glass is the foundation and the columns: a language whose programs carry proofs. Tiresias stands on it: answers about private data, each with a proof. The plan follows the order a Greek temple is raised, from the leveling course to the ornament on the roof. Each stage names its exit gate: a stage is finished when its gate passes, not when its work feels done.

The goal is production grade along every dimension: cryptography, the compiler that feeds it, speed, the language, distribution, security process, and for Tiresias, the privacy of the answers themselves. The hard boundary stays where it was: no claim of production-grade cryptography before an external audit. The "do not protect real value" banner comes down in Stage VI and not before.

| Stage | Temple part | In plain words | Status |
|---|---|---|---|
| I | Euthynteria, the leveling course | Housekeeping: one name per thing, 1.0.0, a lean tree | Done |
| II | Stylobate, the platform | Every change cheap to verify, both packages installable | Next |
| III | Peristyle, the columns | The dimensions, raised in parallel | |
| IV | Architrave, the beam | Tiresias end to end on the audited backend, with zero-knowledge | |
| V | Frieze, the carved story | The public face: docs, playground, measured benchmarks | |
| VI | Pediment, the gable | External audit, findings fixed, 2.0.0 | |
| VII | Acroterion, the apex | The frontier: recursion, whole-program proofs | |

## Working rules for every stage

- One verified change at a time. A change ships when its gate is run, not when it is reasoned to be safe.
- The gates for Glass: `python3.12 tests/test_glass.py`, `bash examples/selfhost/bootstrap_fixpoint.sh`, `bash lens/difftest.sh`, `python3.12 fuzz/corpus_check.py`, `python3.12 fingerprint/fingerprint.py --check`. For Tiresias: `python3.12 -m unittest discover -s tests`.
- Every soundness fix ships with the attack that motivated it, as a test that fails before the fix.
- Claims in docs never run ahead of the code. A limit is written in the same place as the claim it limits.
- Changelog entries use the Keep a Changelog groups. No em dashes, no version archaeology in comments.

## Stage I: Euthynteria, the leveling course (done)

- [x] Components renamed to one plain name each: Lens, the fingerprint, the ledger, disclose, `--cross-check`. Glass keeps its name; its parts follow the optical family (Prism, Quartz, Frost, Pane, Lens).
- [x] Tiresias's code renamed from `gpi` to `tiresias` (package, command, settings).
- [x] Version 1.0.0 for both; one release replaces the old release history.
- [x] Changelog in Keep a Changelog form; READMEs rewritten in the house style.
- [x] First debloat: development diary, superseded design records, 23 prover-stage examples and dead sample programs removed; docs grouped under language, compiler and security.

## Stage II: Stylobate, the platform

The platform every column stands on. Nothing here changes what a proof means; all of it makes the next change cheaper and safer.

- [ ] **Quartz's garbage-collection bug.** The compiler Quartz builds (gen1) loses live objects to the Boehm collector on large inputs (Prism, glassc itself) and fails at random; gen2, which Glass compiles itself into, does not. Until it is found, native builds run gen1 once with collection off and use gen2 after that. Gate: gen1 compiles Prism and glassc twenty times each with the collector on, and the fixpoint no longer sets `GC_DONT_GC`.
- [ ] **A fast suite.** The prover is now compiled once and cached, not once per proof: a small proof went from 19.6 s to 0.24 s. What remains is proving itself. Measured on an 8-core, 16 GB laptop: a full run takes 53 minutes, 49 of them in 46 proofs of 20 seconds or more; the in-circuit Poseidon2 proof alone outlasts the 10-minute per-gate limit there (it completes on CI), and the divmod tuple, the string bands and signed division take 3 to 4 minutes each. Running proofs side by side is bounded by memory (one reaches 4 GB), so the gate needs a faster prover (Column 3) or a smaller set of heavy proofs on every change. Gate: a full run under 10 minutes, same verdicts.
- [x] **Second debloat.** Version tags and old milestone names are gone from code comments, stale comments are corrected (a demo that called itself zero-knowledge, verifiers called unshipped), and 20 functions nothing called are removed, along with the bridge's demo narrative, whose soundness cases now run as a gate.
- [ ] **CI on Linux and macOS**, with the fixpoint, difftest and corpus check as required jobs.
- [x] **Glass pinned in Tiresias.** Tiresias pins a Glass release by tag and by the SHA-256 of each Glass file it reads, fetches it on first use, refuses a differing checkout by name, and loads the verified interpreter by path. Gate: `tiresias glass --fetch` plus the engine round trip, in CI.
- [ ] **Glass as a pip-installable package** with a small, versioned proving API (`glass.prove`), so Tiresias no longer slices a demo file at a marker. Needs a package layout for the runtime files (bridge, native compiler, Lens) and a fingerprint re-root.
- [x] **Releases as artifacts.** A tag-driven release job in both repos: the tag must match the package version, the CLI's `--version` and a changelog entry; the entry becomes the release body; the archives carry build-provenance attestations.
- [ ] **Signed tags and an SBOM per release.** Signing needs the owner's key.
- [x] **Configuration validated at boot** for the Tiresias registry: every setting declared once and checked; `tiresias serve` refuses a malformed, unknown or weak setting and names it; docs/configuration.md is generated from the declaration.

## Stage III: Peristyle, the columns

Seven columns, raised in parallel. Each has its own gate; the beam in Stage IV rests on all of them.

### Column 1: the audited prover (Glass)

The proving backend moves from Frost, written here and unaudited, to an audited library. Frost stays as the readable reference prover and as a differential oracle.

What an audited backend does and does not buy, so the plan is honest:
- It replaces the field, hash, commitment and FRI code with code that professionals have reviewed.
- It does not cover Glass's compiler bridge, the layer that turns a program into constraints. The wrong proofs Glass has found in practice all lived in that layer. Column 2 exists for that reason.
- Audits are scoped and dated. Plonky3's public audit (Least Authority, 2024) is verifier-centric and predates a 2026 Fiat-Shamir advisory fixed in 0.4.3 and 0.5.3. SP1's newest audit covered its verifier, not its prover. RISC Zero's covered prover and verifier, in 2024 and 2025. "Audited" means a pinned version inside an audit's scope, never a library name.

Steps:
- [ ] **Spike, then decide.** Prove the same three circuits (`a+b`, `a<b`, `gcd`) on Plonky3 (AIR route) and on RISC Zero (Glass's C compiled to a RISC-V guest). Measure proving time, proof size, memory, and what each needs for zero-knowledge. Gate: a written decision with the numbers. The expectation, to be confirmed or overturned by the spike: Plonky3 as the primary backend, because Glass already matches its Goldilocks field and Poseidon2 hash byte for byte, it needs no trusted setup, and Lens can verify its proofs independently.
- [ ] **A portable constraint format.** The bridge emits its circuit (gates, selectors, copy constraints, public inputs) as a versioned file, separate from any prover. Gate: Frost proves from the file and its proofs are unchanged.
- [ ] **The backend adapter.** One small Rust crate reads the constraint file and proves it with a pinned, patched Plonky3 release. Rust is needed only for proving; the interpreter stays dependency-free. Gate: `glass prove --backend plonky3` accepts every honest corpus program and rejects every tampered one.
- [ ] **Lens learns the new proof format.** Lens stays the second judge: an independent verifier of the audited backend's proofs, sharing no code with it. Gate: the difftest and the tamper corpus pass on the new format.
- [ ] **Frost as the oracle.** Every corpus program is proven by both backends; their verdicts must agree. Gate: a suite job that fails on any disagreement.
- [ ] **Zero-knowledge on the new backend**, either the backend's own hiding commitments (if inside an audit's scope) or Glass's randomized-trace construction on top. Gate: a written argument plus the hiding test.
- [ ] **The default flips** to the audited backend when all of the above pass; Frost remains available as `--backend frost`.
- [ ] **Gaps go upstream.** Any bug, missing API or documentation gap found in the backend goes back to its project as a focused pull request with a failing test; security findings go through the project's security policy first.

### Column 2: the faithful bridge (Glass)

The part no backend audit covers, and so the part that decides whether a proof means what the source means.

- [ ] **A written lowering specification**: for each construct, the circuit it becomes and the condition under which it is faithful (value ranges, recursion depth), and the refusal when it is not.
- [ ] **Translation validation on every proof.** The cross-check already re-executes the source; make it the default for every `glass prove`, not an option, wherever the reference can evaluate the program.
- [ ] **Per-gadget differential tests**: each gadget (comparison, division, signed arithmetic, strings, records, calls) evaluated as a circuit and as Glass on many random inputs, including the field's edge values.
- [ ] **Mutation testing of the bridge**: a mutated bridge must be caught by some gate. Gate: no surviving mutant in the soundness-critical gadgets. First results (2026-10-08): removing `verify_b3`'s out-of-domain identity is caught by the zero-quotient forgery in the soundness gate; removing its trace-opening Merkle check or its FRI-layer reconstruction is not yet caught by any gate.
- [ ] **Fuzzing at scale in CI**: the seven program families run nightly with a growing seed corpus.

### Column 3: speed (Glass)

The native prover spends 75 to 85 percent of its time in the garbage collector, allocating boxed field elements.

- [ ] **Unbox the field in the bridge's hot paths**: field elements as 64-bit values end to end through the codeword layers. Gate: a measured speedup on `a<b`, byte-identical proofs.
- [ ] **Tag dispatch without string compares** in the emitted C.
- [ ] **Range checks by lookup** once a workload carries more than about 20 range checks in one proof (the LogUp design is ready; below that it is a regression).
- [ ] **A benchmark page** with proving time, verification time and proof size for a fixed set of programs, measured on a named machine, regenerated by a script.

### Column 4: the language (Glass)

- [ ] **Equality in compiled code.** Types are erased in the emitted C, so `==` is decided at run time. It used to take any two words at or above 2^32 for strings and call `strcmp`, which crashed on two different large Ints; it now reads a word as a string only when it is a heap object or a literal in the program image. What remains: an Int that happens to equal a live string's address is still read as a string. Typed equality (emit Int and String comparisons from the checker's types, keeping the run-time test for polymorphic code) closes it. Gate: the fixpoint, and native results equal to the interpreter's on a corpus of mixed comparisons.
- [ ] **Signed overflow wraps in compiled code.** The interpreter wraps at 64 bits; the emitted C leaves signed overflow undefined. Compile with `-fwrapv` (Quartz and glassc). Gate: the suite, the fixpoint, and an overflow test that agrees in both.
- [ ] **Strings as Unicode code points everywhere.** The interpreter counts code points, the emitted C counts bytes; make the native side match.
- [ ] **A standard library** with a stable surface: lists, maps, strings, results, and a small numeric tower.
- [ ] **Errors with codes**: every type and refinement error carries a stable code and a one-line fix hint.
- [ ] **A formatter and a language server** (diagnostics, hover types, go to definition) built on Prism.
- [ ] **Modules by name**, with a lockfile, replacing path imports.

### Column 5: the engine under Tiresias (Tiresias)

Tiresias proves today through Glass's older Baby Bear path (a 2^31 field, sums capped near 2.1 billion, comparisons below 65,536). It moves twice.

- [ ] **Onto Glass's sound Goldilocks path**: `verify_b3` proofs that Lens can check, 2^64 field, the wider comparison range. Gate: every query type round-trips and Lens verifies the bundle.
- [ ] **Witness-free third-party verification**: a public link verifies the proof math without the data (today a third party checks only the binding). Gate: `tiresias verify <bundle>` with no data and no account.
- [ ] **Onto the audited backend with zero-knowledge** once Column 1 lands. Privacy of the rows is the product; Tiresias never ships a proof mode that is not zero-knowledge.

### Column 6: the privacy of the answer (Tiresias)

A proof that an average is true does not stop the average from leaking a person. Two queries that differ by one row reveal that row.

- [x] **Minimum cohort size**: every answer carries a proven count of its rows; below the dataset's floor a query is refused and a `GROUP BY` group suppressed, and the registry rejects bundles that break the policy.
- [ ] **Query auditing**: refuse a query whose answer, combined with earlier answers on the same dataset, isolates a row (differencing).
- [ ] **A per-dataset privacy budget**, with optional differential-privacy noise whose sampling is itself proven.
- [ ] **A written privacy model**: what an answer can and cannot reveal, next to the soundness model.

### Column 7: the registry as a service (Tiresias)

- [ ] **PostgreSQL** behind the store, with migrations; SQLite stays for local use.
- [ ] **Signed dataset commitments**: the data holder signs each manifest (ML-DSA), so a commitment names who made it.
- [ ] **Versioned datasets**: append a new version without invalidating proofs on the old one.
- [ ] **Operations**: structured audit log, metrics, backup and restore drill, a container image and a Helm chart.
- [x] **A security review of the registry**: authentication, tenant isolation, rate limits, input bounds. It found an unbounded read on a negative `Content-Length`, leaked exception text, and unthrottled public routes; all fixed, recorded in Tiresias's SECURITY.md.

## Stage IV: Architrave, the beam

The columns carry weight only once a beam joins them.

- [ ] Tiresias runs end to end on the audited backend with zero-knowledge, through the Glass package, verified by Lens.
- [ ] One pinned set of versions (Glass, the backend, Tiresias) passes both suites and an interop test between them.
- [ ] Threat models for both projects, and an audit package that scopes the bridge, the constraint format, Lens, and the Tiresias query circuits.

## Stage V: Frieze, the carved story

- [ ] A documentation site built from `docs/`, with the tour, the playground, and the benchmark page.
- [ ] Worked examples that a stranger can run in ten minutes, on both projects.
- [ ] OpenSSF Best Practices and Scorecard for both repositories.
- [ ] A design partner for Tiresias, on notional data first.

## Stage VI: Pediment, the gable

- [ ] An external audit of the bridge, the constraint format, the backend integration, Lens, and the Tiresias circuits.
- [ ] Every finding fixed, each with its regression test, and the report published.
- [ ] 2.0.0. The "do not protect real value" banner is replaced by the audit's stated scope.

## Stage VII: Acroterion, the apex

- [ ] Recursion through the backend: a proof that verifies other proofs, so a Tiresias answer over many datasets is one proof.
- [ ] Whole-program proofs through a zkVM for programs outside the circuit subset.
- [ ] Glass proving its own compiler's steps.

## Known gaps carried forward

- Built-in `List<T>` values cannot be threaded into a proof; declared recursive types can. Proofs refuse rather than mis-lower.
- An `if` or `match` whose branches return a structure holding strings of different lengths abstains.
- Recursion in a proof is bounded by a fuel limit; deeper recursion is refused, not truncated.
- The interpreter counts string length in code points and the emitted C in bytes (Column 4).
