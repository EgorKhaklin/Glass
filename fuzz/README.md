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
python3 fuzz/tamper_pentecost.py [seed] [M] --claim       # statement-binding: tamper the PUBLIC CLAIM
                                                          #   (gate list + claimed result), confirm REJECT
python3 fuzz/corpus_check.py                              # multi-shape: every committed proof fixture
                                                          #   ACCEPTs honest + REJECTs proof/claim tampers
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

**`--claim` mode (v5.80.0)** tampers the *public statement* instead of the proof — the gate list and
the claimed result. This is **statement-binding**: a valid proof of `a+b==8` must NOT verify against a
tampered claim `a+b==9` or an altered gate. A break here is the most dangerous kind (a true proof
passed off as proving a false statement), so it is fuzzed too — a 640-tamper/8-seed campaign was clean.
(A "tamper" that doesn't change the token — e.g. setting an already-`0` token to `0` — is forced to a
real change, so a no-op is never miscounted as a wrong-ACCEPT; this also hardened the proof-region mode.)

**`corpus_check.py` (v5.82.0)** runs the differential + tamper checks across every committed proof
fixture in `pentecost/corpus/` (`a+b`, `a*b`, `a*a+b`, and `a<b` — the **comparison gadget**, the
riskiest lowering, 696 gates), not just one — honest must ACCEPT, a proof-region or claim-region tamper
must REJECT. This catches a `verify_b3` bug that only manifests on certain circuit shapes (more gates,
different gate kinds), which a single-fixture gate would miss. Suite-gated. The fixtures are stored
**gzipped** (token streams compress ~3-5x); `corpus_check.py` and `tamper_pentecost.py` read either form.

This is the testing that finds bugs the enumerated gate cannot. Its first run did exactly that —
it surfaced an over-strict equality in the Third Witness (a negative result like `-560` false-
diverged from its field form `p-560`; fixed by reconciling mod p, v5.75.0). Broadening it to the
comparison gadget (v5.76.0) confirmed the gadget is sound under random operands — every ACCEPT
reference-confirmed, out-of-range operands correctly ABSTAINed, zero wrong proofs.
Research/educational-grade, UNAUDITED.
