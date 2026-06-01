# Soundness fuzzing — differential testing the prove pipeline at scale

The hand-picked soundness gate (13 cases) and the Pentecost differential check *specific*
proofs. The fuzzer checks *random* ones: it generates small arithmetic Glass programs over
private inputs, proves each with `glass prove --witness3`, and asserts the soundness invariants
across the whole stack at once —

1. **honest proof → ACCEPT** (`verify_b3` accepts a real proof), and
2. **THIRD LINEAGE AGREES** — the bridge's circuit semantics equal the reference interpreter's,
   reconciled modulo the Goldilocks prime (a lowering gap on *this* program would diverge).

Inputs are small and expressions shallow, so results stay in the range where field and int64
coincide (mod p) and a divergence is a *real* bug, not the documented domain difference.

```bash
python3 fuzz/fuzz_soundness.py [N] [seed]     # N random programs (default 4), deterministic
```

This is the testing that finds bugs the enumerated gate cannot. Its first run did exactly that —
it surfaced an over-strict equality in the Third Witness (it compared a field element to an int64
*exactly*, so a negative result like `-560` false-diverged from its field form `p-560`); the fix
(reconcile modulo p) shipped in v5.75.0. Research/educational-grade, UNAUDITED.
