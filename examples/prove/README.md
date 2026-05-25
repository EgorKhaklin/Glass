# The prove bridge — write Glass, get a zero-knowledge proof

The seam between the language and the prover: a Glass expression is compiled
into a [Frost](../frost/) circuit + witness, and proved correct for a *secret*
input — revealing only the circuit and a commitment.

- [`prove.glass`](prove.glass) — arithmetic expressions → circuit → proof.
- [`prove_lang.glass`](prove_lang.glass) — control flow (`let` / `if` / `==`) via is-zero and multiplexer gadgets.
- [`prove_glass.glass`](prove_glass.glass) — **real Glass source**, parsed by Glass's own front end (`prism`), compiled to a circuit and proved — including comparisons and booleans.
