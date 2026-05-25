# The prove bridge — write Glass, get a zero-knowledge proof

The seam between the language and the prover: a Glass expression is compiled
into a [Frost](../frost/) circuit + witness, then proved correct for a *secret*
input — revealing only the circuit and a commitment.

### The bridge

- [`prove.glass`](prove.glass) — arithmetic expressions → circuit → proof.
- [`prove_lang.glass`](prove_lang.glass) — control flow (`let` / `if` / `==`) via is-zero and multiplexer gadgets.
- [`prove_glass.glass`](prove_glass.glass) — **real Glass source**, parsed by Glass's own front end (`prism`), compiled to a circuit and proved — comparisons and booleans included.

### Closing the loop — source → succinct, zero-knowledge proof (N1)

The four stages that lower the bridge circuit into the cryptographic STARK:

- [`prove_stark.glass`](prove_stark.glass) — PLONK arithmetization (gate trace + selectors).
- [`prove_copy.glass`](prove_copy.glass) — copy constraints via the permutation argument.
- [`prove_quotient.glass`](prove_quotient.glass) — the gate-constraint quotient G/Z_H + low-degree test.
- [`prove_zk.glass`](prove_zk.glass) — **the loop closes**: blinded quotient → FRI over F_{p⁴}. Honest ACCEPT, tampered REJECT, two blindings reveal different openings (zero-knowledge).

### Widening the bridge (N2 / N4)

- [`prove_calls.glass`](prove_calls.glass) — function calls (`EApp`, by inlining).
- [`prove_match.glass`](prove_match.glass) — scalar `match` via a selector-multiplexer.
- [`prove_adt.glass`](prove_adt.glass) — structured `match` over ADT values (`(tag, fields)` wire-tuples).
- [`prove_zperm.glass`](prove_zperm.glass) — the succinct permutation as a FRI'd z-accumulator.
- [`prove_full.glass`](prove_full.glass) — the unified bridge: arithmetic + `==` + `if` + `let` + `EApp` + `EMatch` over real prism programs.

### Pane ⊕ Frost — a zero-knowledge query (H1)

The founding vision: *Frost is the zero-knowledge extension of [Pane](../pane/).*
Commit a *private* table, then prove the result of a query — revealing only the
commitment, the query, and the answer, never a row.

- [`prove_query.glass`](prove_query.glass) — the idea, end to end and self-contained: `SELECT SUM(salary) WHERE dept = target` over a private salary table. A binding fingerprint commitment (C = Σ flatᵢ·γⁱ) ties the witness to the public commitment; the query is a circuit; honest ACCEPT, lying about the result or the table REJECTs.
- [`prove_pane.glass`](prove_pane.glass) — **Frost as a second backend over the real Pane query algebra.** Take an actual Pane `Query` value (`SumQ`, `CountQ`, `AvgQ`, `MinQ`, `MaxQ`, `GroupByQ`, `Where(…)`) and lower it gadget-for-gadget into a circuit — equality, booleans (`And`/`Or`/`Not`), arithmetic, **order comparisons** (`<`/`>`, via a 17-bit range gadget), the full **aggregate set** (SUM, COUNT, AVG as proven `sum`+`count`, MIN/MAX as a proven bound + presence), and **`GROUP BY`** — each proven over the same committed table. One AST, two evaluators: `run_query` *interprets* it, `prove_pane` *proves* it — and the discipline is that they agree, the circuit ACCEPTing exactly when its answer equals `run_query`'s.
- [`prove_query_zk.glass`](prove_query_zk.glass) — **the payoff: a committed-table query in *zero-knowledge*.** A SUM over a committed private column — and a `SUM … WHERE` *filtered* query — lowered to the blinded F_{p⁴} FRI STARK (the `prove_zk` backend), so the proof is succinct and leaks nothing. The universal gate identity gains a `qassert·(l−r)` selector so the binding/result assertions and the filter's is-zero gadget are enforced inside the low-degree quotient. Honest ACCEPT; lying about the sum, the table, or a filtered result REJECTs; two blinding seeds verify with different openings (zero-knowledge).

### Toward recursion — a verifier inside a circuit (H3)

- [`prove_recursion.glass`](prove_recursion.glass) — the seed of recursive proofs (a proof that another proof verifies). A STARK verifier's algebraic core is the FRI **fold check** — `fold(f(x), f(-x)) = (f(x)+f(-x))/2 + β(f(x)−f(-x))/(2x)`. This expresses that check as a *circuit* (division by an inverse-witness with a `w·inv == 1` gate) and proves it: an honest fold path ACCEPTs, any tampered value REJECTs. Run it over a whole fold path and you've verified, in-circuit, that a codeword folds to a constant — the FRI low-degree test, recursively.
- [`prove_recursion_zk.glass`](prove_recursion_zk.glass) — **that fold step, in zero-knowledge.** The fold circuit is lowered through the blinded F_{p⁴} FRI STARK (the `prove_zk` backend), so the verifier's own step is succinct and *blind* — the opened values stay private. The `(2x)·inv == 1` division check rides as a `qassert` gate with the inverse on an input wire. Honest ACCEPT, tampered REJECT, two blinding seeds give different openings (ZK). Composed with frost_zk's in-circuit Merkle membership, that's a recursive STARK verifier. (It's deep enough that running it natively — `run_native.sh`, ~1.1s vs ~46s interpreted — is the point.)
