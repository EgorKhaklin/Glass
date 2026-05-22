# Contributing to Glass

Thanks for your interest in contributing to Glass.

## How to help

There are several productive ways to contribute:

### Run real programs through it

Glass is past its v1.0 milestone but still alpha. The best contribution right now is just **running it and reporting what breaks**. Try writing a Glass program that solves a problem you care about. If you hit a parse error, type error, or runtime error that surprises you, open an issue with the minimal source that triggers it.

### Write example programs

The `examples/showcase/` directory holds compact demonstrations of what Glass can do — symbolic differentiation, propositional logic, Nash equilibria. If you write something striking in Glass, send a PR adding it. Good showcase examples are:

- **Compact** — ideally fit on one screen
- **Pure Glass** — no host extensions
- **Striking output** — the result should make sense to someone who's never seen the code
- **Mathematically honest** — if it claims to do X, it should actually do X

### Improve the standard library

The host's builtins are minimal. Useful additions include: more list operations, more string operations, hashmaps, sets, file-glob utilities. Any new builtin needs:

- A type signature in `glass.py` (with the right effect row if relevant)
- A Python implementation
- A test in `tests/test_glass.py`
- An example in `examples/`

### Work on Stage 4

[Stage 3 is reached](docs/self-hosting.md). prism.glass interprets Glass files from disk. Stage 4 — prism.glass interpreting *itself* — needs performance work first. The bottleneck is `VMutRecClos.apply` rebuilding the sibling environment on every call. A persistent-environment representation (or proper closures captured at definition time) would unblock Stage 4.

### Refinement types

LANG.md promises refinement types — `Int where (x > 0)` and similar. The current implementation:

- ✓ Syntax in fn parameters and let bindings
- ✓ Runtime predicate checks at call sites  
- ✗ Static discharge of constant-foldable refinements
- ✗ Refinement on return types
- ✗ Refinements inside generic args
- ✗ SMT-backed verification

Each of these is a tractable contribution.

## Development setup

```bash
git clone https://github.com/EgorKhaklin/Glass.git
cd Glass
pip install -e .
python tests/test_glass.py
```

The full test suite finishes in under a minute on a modern laptop. The self-host capstone (prism.glass) finishes in about 30 seconds.

## Code style

`glass.py` is a single file deliberately. Don't split it across modules unless there's a strong reason.

Glass source files use:
- 2-space indentation
- `#` for comments
- Total pattern matching (the compiler enforces this)
- Effect annotations on every fn that performs I/O, randomness, file access, or inference
- Type annotations on every top-level fn parameter and return

## Pull request guidelines

1. **One concern per PR.** A new builtin, a parser fix, and a doc rewrite are three separate PRs.
2. **Tests pass.** `python tests/test_glass.py` must show all tests green.
3. **CHANGELOG entry.** Add a line under the next version's `Added`, `Changed`, or `Fixed` section.
4. **Commit message** in the imperative ("add cons builtin", not "added" or "adds").

## Reporting issues

Include:
- A minimal Glass program that reproduces the issue
- The expected output
- The actual output (or error)
- Your Python version (`python --version`)
- Whether it's a regression from a previous version

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
