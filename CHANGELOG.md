# Changelog

Externally observable changes to Glass, research software whose prover is unaudited.
The reasoning behind each change, with its tests and measurements, is in its commit message.
Entries use the [Keep a Changelog](https://keepachangelog.com/) groups: Security, Fixed, Added, Changed, Removed.
Version numbering restarted at 1.0.0 when development resumed; the earlier 0.x to 5.x line is in the git history.

---

## Unreleased

## v1.0.0 - 2026-10-08 (development resumes; everything before it is one release)

### Added

- A pure functional language with Hindley-Milner inference, declared effect rows, refinement types, exhaustive pattern matching, linear types, records, modules, and a REPL.
- A self-hosted compiler: `glassc`, written in Glass, compiles itself to C, and two generations emit byte-identical output (the bootstrap fixpoint, gated in CI).
- `glass prove`: compiles a function over private inputs to a circuit and proves its result with Frost, a from-scratch zk-STARK over Goldilocks with Poseidon2 (about 80 bits provable, 82 queries, blowup 32, 12-bit grind). `--zk` adds hiding through a randomized trace.
- Three judges for every proof: `verify_b3`, a witness-free verifier in Glass; Lens, an independent verifier in Python that shares no code with the prover (`glass verify`); and `--cross-check`, which re-executes the source under the reference interpreter.
- A machine-readable verdict: `glass prove` exits 0 accept, 1 abstain, 2 reject, 3 cross-check divergence.
- `glass fingerprint`, one Poseidon-Merkle root over the compiler, prover, verifiers, tests and spec; `glass ledger`, an append-only ledger of proof verdicts; `glass disclose`, selective disclosure over a commitment.
- Soundness fuzzers, a tamper-checked proof corpus, and a malicious prover in the test suite whose forged proof must be rejected.
- Pushing a tag `vX.Y.Z` publishes a release: the job checks the tag against the package version, `glass --version` and the changelog, takes the release body from the changelog entry, and attaches a source archive of the tagged tree with a build-provenance attestation.
- CI runs the bootstrap fixpoint, the dogfood check, the Lens difftest and the proof corpus on macOS as well as Linux.

### Changed

- Each component has one name. The second verifier lives in `lens/` and prints `LENS:`; the project identity is `glass fingerprint` (`fingerprint/FINGERPRINT`); the ledger is `glass ledger`; selective disclosure is `glass disclose` (`disclose/`); the source re-execution is `--cross-check`.
- Documentation is grouped by subject under `docs/language`, `docs/compiler` and `docs/security`.
- The README is rewritten around what can be checked today, with the limits stated in the same place as the claims.
- Prose, comments and messages no longer use em dashes or carry the old version numbers.

### Removed

- The command aliases `name`, `tablet` and `seal`, and the `--witness3` flag.
- The development diary, superseded design records and the 135-entry changelog; they remain in the git history.
- 23 superseded prover-stage examples, the unused sample programs under `examples/selfhost/programs`, three one-line Quartz examples, `eff_infer.glass`, and a Merkle-batching prototype.

### Fixed

- `examples/selfhost/bootstrap.glass` read its sample sources from an absolute path that existed on no machine, so its read-from-disk demo never ran; it reads them from the repository.
- The prover's demo said full zero-knowledge was unbuilt; it is built and runs with `glass prove --zk`.
- The README implied default proofs hide private inputs; default proofs are sound but not zero-knowledge, and `--zk` adds hiding.
- `glass prove` said the same on the default path ("the proof reveals only the result") and its help called every proof zero-knowledge. The default path now says the proof is not zero-knowledge and names `--zk`; the help lists `--zk`. The demo programs under `examples/prove` carry the same qualification.
- `glass prove` exited 0, the ACCEPT code, when it refused before proving: an ill-typed program, a claim of the wrong type, a flag the chosen field cannot honour, or no file. A script reading the exit code took those refusals for proofs. They now exit 1, the ABSTAIN code.
- `glass prove --baby-bear` labelled its proofs zero-knowledge and said they reveal only the result; the 2^31 path blinds with a fixed seed, so it hides nothing. It now says so, and refuses `--zk`, which it used to ignore.
- `hello_prove.glass` said refinement types are proven in-circuit; the Goldilocks bridge does not lower refinements.
- The ledger, fingerprint and disclose modules described their hash as Plonky2's Poseidon; they use Plonky3's Poseidon2, through Lens.
- The playground showed an old version number, and the Quartz module docstring described a subset from before functions and ADTs compiled.
- Quartz bound a lambda's free variable to a global function of the same name when an enclosing local shadowed it, so two lambdas in Prism called the wrong function. Enclosing locals now win.
- The bootstrap fixpoint could pass on output left by an earlier step. Each step now starts from a clean slate and must report a successful compile.
- The native compiler built by Quartz (gen1) loses live objects to the garbage collector on large inputs, so big native compiles failed at random. Native builds now run gen1 once, with collection off, to build gen2, the compiler Glass compiles itself into, and use gen2 from then on. The bug in Quartz's output is open (roadmap, Stage II).
- Concurrent native builds (two proves, a gate, the fixpoint) wrote the same fixed paths under /tmp and could overwrite each other; they now hold a shared lock. A gate that timed out in the suite could leave its children running; the whole process group is now stopped.
