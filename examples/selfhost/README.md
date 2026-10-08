# Self-hosting: Glass compiles Glass

The proof that Glass stands on its own: the front end and the compiler are
themselves written in Glass, and the compiler reproduces itself exactly with no
Python in the loop.

**The two artifacts:**
- [`prism.glass`](prism.glass): the Glass front end (lexer, parser, type inference, evaluator), in Glass.
- [`glassc.glass`](glassc.glass): a Glass → C compiler, in Glass (it imports and reuses `prism`).

**Reproduce the fixpoint:**
```bash
bash examples/selfhost/bootstrap_fixpoint.sh
```
`quartz.py` compiles `glassc` once; from there `native_glassc` compiles itself
and `prism` byte-for-byte identically: the bootstrap closes.

**Verify any file self-hosts:**
```bash
bash examples/selfhost/dogfood.sh examples/prove/prove_adt.glass
# DOGFOOD PASS: examples/prove/prove_adt.glass: native_glassc == glass.py (self-hosted, byte-identical)
```
`dogfood.sh` runs a file on both `glass.py` and the self-hosted compiler and
checks they agree bit for bit: the Glass differential-testing discipline as one
command (it handles `import` inlining and the cosmetic output differences). Like
the fixpoint, it catches divergence between implementations, not an error they
share.

**Run any file natively:**
```bash
bash examples/selfhost/run_native.sh examples/prove/prove_query_zk.glass
```
Native builds need a C compiler and `libgc` (Boehm GC).

The remaining files are milestones from the road there: `mini` (a small
language interpreted by Glass), `parser`, `typecheck`, `bootstrap`, `prism_lexer`,
`quartz_min` and `quartz_parser` (Quartz written in Glass), `build_pipeline`, and
`selfcompile`. See [self-hosting](../../docs/compiler/self-hosting.md) for the
full story.
