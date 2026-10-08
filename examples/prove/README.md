# The prove bridge: write Glass, get a proof

The seam between the language and the prover: a Glass program is parsed by Glass's own
front end (`prism`), lowered to a circuit and witness, and proved with a from-scratch
STARK. Names passed on the command line are private inputs. The default `glass prove` is
**sound but not zero-knowledge** (its openings can expose witness values); `--zk` adds
hiding. Research/educational-grade, UNAUDITED: do not protect real value. See
[soundness](../../docs/security/soundness.md) for the modes and their guarantees.

```bash
glass prove examples/prove/hello_prove.glass inp=9                # result 86, ACCEPT
glass prove --zk examples/prove/private_prefix.glass key="sk-live-9f3a2c7e1b"
glass prove --cross-check examples/prove/gcd_prove.glass x=48 y=18
glass prove --emit p.b3 examples/prove/reveal_prefix.glass key=sk-live-9f3a2c7e1b && glass verify p.b3
```

Each demo's header comment gives its exact command and expected result.

## The bridge

- [`prove_source_goldilocks_zk.glass`](prove_source_goldilocks_zk.glass): the bridge behind the
  default `glass prove`. Source to `prism` AST, bounded unrolling (calls and higher-order
  arguments inlined), `cgen` to Goldilocks gates, then `prove_b3` / `verify_b3` (and the
  randomized-trace `--zk` path), the security meter, and the serializer for the independent
  [Lens](../../lens/) verifier.
- [`prove_job.glass`](prove_job.glass): the driver `glass prove` appends to the bridge. The
  two are compiled to a native binary once and cached under `/tmp/glass-native/bridge`; each
  proof then runs that binary on a small job file (the program, its inputs, the mode and any
  claim). The first proof after a change to the bridge or the compiler takes about 20 seconds
  to compile; later proofs pay only for proving. `GLASS_PROVE_UNCACHED=1` compiles per proof.
- [`soundness_gate.glass`](soundness_gate.glass): the cases the verifier must get right, run
  natively by the suite: honest proofs, a different statement, a tampered nonce and trace, a
  P=0 proof, a wiring-inconsistent trace, a wrong public input, and a forged proof with a zero
  quotient. Each verdict is asserted.

## Demos for `glass prove`

**Arithmetic, calls, recursion**
- [`hello_prove.glass`](hello_prove.glass): the smallest example, `f(x) = x*x + 5`.
- [`fact_prove.glass`](fact_prove.glass): bounded recursion; an input past the unroll bound is refused, not truncated.
- [`gcd_prove.glass`](gcd_prove.glass): Euclid's GCD: recursion, `%`, and a dead divide-by-zero branch.
- [`list_sum_prove.glass`](list_sum_prove.glass): a fold over a recursive linked list.
- [`map_prove.glass`](map_prove.glass): a higher-order `map` over a recursive list; the heaviest demo.
- [`computed_callee.glass`](computed_callee.glass): the function to call is chosen at runtime by a private flag.
- [`deadbranch_div.glass`](deadbranch_div.glass): a dead `a % 0` branch no longer poisons the circuit.
- [`selfprove.glass`](selfprove.glass): a polynomial hash step, the recurrence Glass's own string hash uses.

**Comparisons and integer operations**
- [`cmp_prove.glass`](cmp_prove.glass): `a < b`.
- [`age_prove.glass`](age_prove.glass): "at least 21" as a hand-written bit-decomposition range proof.
- [`div_prove.glass`](div_prove.glass): `a / b` via `a = b*q + r`, `0 <= r < b`.
- [`signed_cmp.glass`](signed_cmp.glass), [`signed_abs.glass`](signed_abs.glass), [`signed_band.glass`](signed_band.glass), [`signed_div.glass`](signed_div.glass), [`signed_mod.glass`](signed_mod.glass): signed integers in [−2³¹, 2³¹).
- [`private_distance.glass`](private_distance.glass): `|a − b|` of two private values.
- [`private_divmod.glass`](private_divmod.glass): a tuple result, quotient and remainder.
- [`private_bitmask.glass`](private_bitmask.glass): `bit_and` over [0, 2³²): a private permission set contains the required bits.

**Strings and records**
- [`string_eq.glass`](string_eq.glass): string equality over codepoint wires.
- [`private_prefix.glass`](private_prefix.glass): a private key starts with `sk-live-`.
- [`private_email.glass`](private_email.glass): a private email ends with a given domain.
- [`private_allowlist.glass`](private_allowlist.glass): `match` over a private string maps it to an action code.
- [`reveal_prefix.glass`](reveal_prefix.glass): a string result: reveal the first 8 characters of a private key.
- [`private_verdict.glass`](private_verdict.glass), [`private_risk.glass`](private_risk.glass): a verdict word chosen by a private score (equal and unequal word lengths).
- [`record_stats.glass`](record_stats.glass): records built and destructured inside the proof.
- [`record_field.glass`](record_field.glass): direct field access, `a.balance >= 100`.
- [`private_eligibility.glass`](private_eligibility.glass): records, field access, comparisons, and string checks in one policy decision.

**Effects and memory**
- [`random_prove.glass`](random_prove.glass): a committed seed produced a public draw at a public beacon.
- [`trust_prove.glass`](trust_prove.glass): a committed model answer satisfies its refinement contract.
- [`state_prove.glass`](state_prove.glass): read-after-write consistency of a fixed memory trace.
- [`permutation_prove.glass`](permutation_prove.glass): a private sequence is a permutation of a public set (grand product).
- [`general_state_prove.glass`](general_state_prove.glass): permutation plus read-after-write in one proof.

**Building blocks for recursion**
- [`merkle_member.glass`](merkle_member.glass): in-circuit Merkle membership with a reduced toy hash.
- [`merkle_fold_member.glass`](merkle_fold_member.glass): Merkle-authenticated openings fed into a FRI fold step, in one circuit.
- [`poseidon2_node.glass`](poseidon2_node.glass): the full Poseidon2 permutation as a circuit (~1.9k gates). Generated by `fuzz/gen_poseidon2_node.py` and checked against `lens/poseidon.py`; it does not agree with the int64 cross-check, which overflows.

## Legacy small-field bridges

- [`prove_source_adt_zk.glass`](prove_source_adt_zk.glass): the Baby Bear (2³¹) bridge behind
  `glass prove --baby-bear`: ADTs, recursion, higher-order functions, return refinements,
  blinded F_{p⁴} FRI. Runs in the interpreter; integer inputs only; outside the scope an audit would cover.
- [`prove_pane.glass`](prove_pane.glass): Frost as a second backend over the [Pane](../pane/)
  query algebra: a real `Query` value lowered to a circuit over a committed private table and
  proved (field 2³¹ − 1, random-linear-combination argument).

## Standalone demos (run with `glass <file>`)

Self-contained, hand-built circuits from before the source bridge; they dogfood byte-identical.
- [`prove.glass`](prove.glass): an expression to a circuit and a random-linear-combination proof (field 2³¹ − 1).
- [`prove_adt.glass`](prove_adt.glass): `match` over ADT values as tag dispatch plus field wires.
- [`prove_query.glass`](prove_query.glass): `SUM ... WHERE` over a committed private table.
- [`prove_query_zk.glass`](prove_query_zk.glass): the same query as a blinded FRI STARK over Baby Bear. Heavy: run it with `bash examples/selfhost/run_native.sh`.

## Difftests and fixtures

Each prints `CHECK ... T/F` lines and must give identical output under `glass.py` and
`examples/selfhost/run_native.sh`. The test suite runs them.
- [`goldw_difftest.glass`](goldw_difftest.glass): the single-`Int` Goldilocks field agrees with the limb field.
- [`ntt_difftest.glass`](ntt_difftest.glass): the native coset NTT equals naive evaluation.
- [`poseidon_difftest.glass`](poseidon_difftest.glass): the native Poseidon matches Plonky2's known answer and a Glass reference.
- [`poseidon2_difftest.glass`](poseidon2_difftest.glass): the native Poseidon2 matches Plonky3's published vector.
- [`vget_difftest.glass`](vget_difftest.glass): O(1) vector indexing equals list indexing.
- [`measure_difftest.glass`](measure_difftest.glass): the security meter's arithmetic (80 provable / 135 list-decoding bits at 82 queries).
- [`prove_source_goldilocks_bind_test.glass`](prove_source_goldilocks_bind_test.glass): the statement-binding digest changes when the claim or the gate list changes.
