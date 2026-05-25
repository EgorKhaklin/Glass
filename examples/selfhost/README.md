# Self-hosting — Glass compiles Glass

The proof that Glass stands on its own: the front end and the compiler are
themselves written in Glass, and the compiler reproduces itself exactly with no
Python in the loop.

**The two artifacts:**
- [`prism.glass`](prism.glass) — the Glass front end (lexer, parser, type inference, evaluator), in Glass.
- [`glassc.glass`](glassc.glass) — a Glass → C compiler, in Glass (it imports and reuses `prism`).

**Reproduce the fixpoint:**
```bash
bash examples/selfhost/bootstrap_fixpoint.sh
```
`quartz.py` compiles `glassc` once; from there `native_glassc` compiles itself
and `prism` byte-for-byte identically — the bootstrap closes.

**Verify any file self-hosts:**
```bash
bash examples/selfhost/dogfood.sh examples/prove/prove_zk.glass
# DOGFOOD PASS: … — native_glassc == glass.py (self-hosted, byte-identical)
```
`dogfood.sh` runs a file on both `glass.py` and the self-hosted compiler and
checks they agree bit-for-bit — the Glass differential-testing discipline as one
command (it handles `import` inlining and the cosmetic output differences).

The remaining files are the milestones and supporting passes from the road
there (`parser`, `typecheck`, `eff_infer`, `prism_lexer`, `bootstrap`, …).
