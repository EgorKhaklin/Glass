# Soundness fuzzing: differential testing the prove pipeline at scale

The hand-picked soundness gates and the Lens differential check *specific*
proofs. The fuzzer checks *random* ones: it generates small arithmetic Glass programs over
private inputs, proves each with `glass prove --cross-check`, and checks THE soundness invariant:

> **a wrong proof = an ACCEPT the independent reference interpreter does not confirm.**

So a program PASSES unless it is ACCEPTed *and* the cross-check disagrees (reconciled mod p).
**ABSTAIN** (the gadget refusing an out-of-range/unlowerable program) and **REJECT** (a disproof)
are *sound* outcomes, not failures: only a wrong ACCEPT is a violation. Seven families are
generated: arithmetic expressions, comparison/boolean control flow, the signed gadgets
(`slt`/`sle`/`sgt`/`sge`, `sdiv`/`smod` over negatives), **strings** (`++`/`substring`/
`string_length`/`==`, the multi-wire codepoint lowering), **records** (construct + destructure),
**computed callees** (runtime-chosen / let-aliased fn names), and **capture shapes** (calls whose
later arguments reference an earlier parameter's name: the inlining-capture class, in both
the value and fn namespaces; added because none of the other families ever generated it). Inputs
are small and shallow so results stay where field and int64
coincide mod p: a divergence there is a *real* bug, not the documented domain difference.

```bash
python3 fuzz/fuzz_soundness.py [N] [seed]                 # cross-check mode: no wrong ACCEPT
                                                          #   (arithmetic + unsigned comparison + SIGNED
                                                          #    slt/sle/sgt/sge/sdiv/smod over negatives)
python3 fuzz/fuzz_soundness.py --boundary [N] [seed]      # boundary mode: inputs at the 2^31/2^32
                                                          #   range-gadget seams (the canonical-form
                                                          #   crown-jewel class): in-range ACCEPTs must
                                                          #   AGREE, out-of-range must ABSTAIN, never a
                                                          #   wrong ACCEPT at the edge
python3 fuzz/fuzz_soundness.py --differential [N] [seed]   # two-verifier mode: emit a portable
                                                          #   proof per program, confirm Glass verify_b3
                                                          #   and the independent Lens verifier AGREE
                                                          #   (cycles arithmetic + comparison + SIGNED
                                                          #    slt/sdiv proofs; signed proofs are large,
                                                          #    so emit is the slow step: keep N small)
python3 fuzz/tamper_lens.py [seed] [M] [proof]       # adversarial mode: forge M proofs by random
                                                          #   single-token tampers, confirm the independent
                                                          #   Lens verifier REJECTs every one
python3 fuzz/tamper_lens.py [seed] [M] --claim       # statement-binding: tamper the PUBLIC CLAIM
                                                          #   (gate list + claimed result), confirm REJECT
python3 fuzz/corpus_check.py                              # multi-shape: every committed proof fixture
                                                          #   ACCEPTs honest + REJECTs proof/claim tampers
```

## Adversarial mode: attacking the second verifier

`fuzz_soundness.py` fuzzes *honest* proofs (is an ACCEPT ever unconfirmed?). `tamper_lens.py`
fuzzes the dual property on the independent Lens verifier alone: **a tampered proof must NEVER
verify.** It loads an honest proof (default: the committed corpus fixture
`lens/corpus/honest_a_plus_b.b3.txt.gz`), asserts it ACCEPTs, then applies `M` random
single-token perturbations across the whole `ProofB3` region: `v±1`, `0`, `2v+1`, a uniform field
element, and runs `verify_b3` on each. A **wrong-ACCEPT** (a forged proof that still verifies) is a
verifier soundness hole; anything else (REJECT, parse error → REJECT) is sound. Pure Python with a
per-seed scratch file, so it parallelizes trivially across seeds.

A 16-seed × 100-tamper campaign (**1,600 forged proofs**) was clean, every tamper
rejected. The suite gates a fast slice on every push so a future `verify_b3` regression that lets a
forged proof pass cannot land silently.

**`--claim` mode** tampers the *public statement* instead of the proof: the gate list and
the claimed result. This is **statement-binding**: a valid proof of `a+b==8` must NOT verify against a
tampered claim `a+b==9` or an altered gate. A break here is the most dangerous kind (a true proof
passed off as proving a false statement), so it is fuzzed too: a 640-tamper/8-seed campaign was clean.
(A "tamper" that doesn't change the token: e.g. setting an already-`0` token to `0`: is forced to a
real change, so a no-op is never miscounted as a wrong-ACCEPT; this also hardened the proof-region mode.)

**`corpus_check.py`** runs the differential + tamper checks across every committed proof
fixture in `lens/corpus/` (`a+b`, `a*b`, `a*a+b`, `a/b`, a record, a string equality, a
string-valued result, and `a<b`: the **comparison gadget**, the riskiest lowering, 696 gates),
not just one: honest must ACCEPT, a proof-region or claim-region tamper
must REJECT. This catches a `verify_b3` bug that only manifests on certain circuit shapes (more gates,
different gate kinds), which a single-fixture gate would miss. Suite-gated. The fixtures are stored
**gzipped** (token streams compress ~3-5x); `corpus_check.py` and `tamper_lens.py` read either form.

This is the testing that finds bugs the enumerated gate cannot. Its first run did exactly that:
it surfaced an over-strict equality in the cross-check (a negative result like `-560` false-
diverged from its field form `p-560`; fixed by reconciling mod p). Broadening it to the
comparison gadget confirmed the gadget is sound under random operands, every ACCEPT
reference-confirmed, out-of-range operands correctly ABSTAINed, zero wrong proofs.
Research/educational-grade, UNAUDITED.
