# Soundness fuzzing — differential testing the prove pipeline at scale

The hand-picked soundness gate (13 cases) and the Pentecost differential check *specific*
proofs. The fuzzer checks *random* ones: it generates small arithmetic Glass programs over
private inputs, proves each with `glass prove --witness3`, and checks THE soundness invariant:

> **a wrong proof = an ACCEPT the independent reference interpreter does not confirm.**

So a program PASSES unless it is ACCEPTed *and* the Third Witness disagrees (reconciled mod p).
**ABSTAIN** (the gadget refusing an out-of-range/unlowerable program) and **REJECT** (a disproof)
are *sound* outcomes, not failures — only a wrong ACCEPT is a violation. Two families are
generated: arithmetic expressions, and comparison/boolean control flow (the gadget-bearing,
least-fuzzed lowering). Inputs are small and shallow so results stay where field and int64
coincide mod p — a divergence there is a *real* bug, not the documented domain difference.

```bash
python3 fuzz/fuzz_soundness.py [N] [seed]                 # witness3 mode: no wrong ACCEPT
python3 fuzz/fuzz_soundness.py --differential [N] [seed]   # two-verifier mode: emit a portable
                                                          #   proof per program, confirm Glass verify_b3
                                                          #   and the independent Pentecost verifier AGREE
python3 fuzz/tamper_pentecost.py [seed] [M] [proof]       # adversarial mode: forge M proofs by random
                                                          #   single-token tampers, confirm the independent
                                                          #   Pentecost verifier REJECTs every one
```

## Adversarial mode — attacking the second witness

`fuzz_soundness.py` fuzzes *honest* proofs (is an ACCEPT ever unconfirmed?). `tamper_pentecost.py`
fuzzes the dual property on the independent Pentecost verifier alone: **a tampered proof must NEVER
verify.** It loads an honest proof (default: the committed corpus fixture
`pentecost/corpus/honest_a_plus_b.b3.txt`), asserts it ACCEPTs, then applies `M` random
single-token perturbations across the whole `ProofB3` region — `v±1`, `0`, `2v+1`, a uniform field
element — and runs `verify_b3` on each. A **wrong-ACCEPT** (a forged proof that still verifies) is a
verifier soundness hole; anything else (REJECT, parse error → REJECT) is sound. Pure Python with a
per-seed scratch file, so it parallelizes trivially across seeds.

A 16-seed × 100-tamper campaign (**1,600 forged proofs**, v5.78.0) was clean — every tamper
rejected. The suite gates a fast slice on every push so a future `verify_b3` regression that lets a
forged proof pass cannot land silently.

This is the testing that finds bugs the enumerated gate cannot. Its first run did exactly that —
it surfaced an over-strict equality in the Third Witness (a negative result like `-560` false-
diverged from its field form `p-560`; fixed by reconciling mod p, v5.75.0). Broadening it to the
comparison gadget (v5.76.0) confirmed the gadget is sound under random operands — every ACCEPT
reference-confirmed, out-of-range operands correctly ABSTAINed, zero wrong proofs.
Research/educational-grade, UNAUDITED.
