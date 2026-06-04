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
- [`prove_adt_zk.glass`](prove_adt_zk.glass) — **that structured match, in zero-knowledge.** `prove_adt` proved an ADT match with a sound RLC argument; this lowers it to the blinded F_{p⁴} FRI STARK, so the ADT value stays private. `area(s) = match s { Circle(r) => 3·r·r; Rect(w, h) => w·h }` over a *secret* `s`: the value is a tagged tuple `(tag, f0, f1)`, the match dispatches on the tag (is-zero gadget, inverse hint on an input wire), binds the fields, and multiplexes the bodies; a `qassert` binds the result to a public claim `R`. Proves "I know an `s` with `area(s) = R`" (R = 27) — honest ACCEPT, lying REJECT, two blinding seeds give different openings (ZK). Self-hosted byte-identical. (Hand-shaped `(tag, f0, f1)`; wiring prism's real `ECtor`/`PCtor` through the source bridge — multi-wire values everywhere — is the larger follow-on.)
- [`prove_zperm.glass`](prove_zperm.glass) — the succinct permutation as a FRI'd z-accumulator.
- [`prove_full.glass`](prove_full.glass) — the unified bridge: arithmetic + `==` + `if` + `let` + `EApp` + `EMatch` over real prism programs.
- [`prove_source_adt_zk.glass`](prove_source_adt_zk.glass) — **real Glass source *with algebraic data types* → a zero-knowledge proof.** Where `prove_source_zk` made every circuit value a single wire, this makes a value **multi-wire** — a list `[tag, f0, f1, …]` (a scalar is `[w]`, an ADT `Ctor(a,b)` is `[tag, wa, wb]`, the tag = the constructor's index in its type). Real prism `ECtor` builds such a value; a `match` with `PCtor(C, vars)` dispatches on wire 0 (is-zero(tag − ctor_tag), inverse hint on an input wire) and binds the pattern variables to the field wires. A match may also **return** an ADT (the result mux is element-wise over the body's wires), and a field may itself be an **ADT** (*nested*): a **type-directed layout** computes each value's wire-width from the type declarations (a sum type padded to its widest constructor), so `ECtor` pads fields to width and `PCtor` slices them out of the flat wire list. **Tuples** work too (`ETuple`/`PTuple`): `(a, b)` is a tagless multi-wire value, a function may return one, and `(x, y)` patterns bind positionally — e.g. `fn swap(p) = match p { (x, y) => (y, x) }`. Patterns also **nest to arbitrary depth**: `match l { L(P(x, y), b) => x + y }` destructures the inner `Point` directly — the arm selector is the product of is-zeros down the pattern tree (tag = L *and* field 0's tag = P), and binders slice nested sub-values by type width. Demo: `type Point = P(Int,Int); type Line = L(Point, Point); fn endx(l) = match l { L(P(x, y), b) => x + y }; endx(L(P(inp, 7), P(2, 3)))` with a *private* `inp` proves the result = 12 (honest ACCEPT, lying REJECT, ZK). Self-hosted byte-identical. (Bounded to non-recursive types.) This completes structured pattern matching: the source→ZK bridge now covers the full first-order pure-functional core over real prism Glass.
- [`prove_source_zk.glass`](prove_source_zk.glass) — **the thesis, unified end to end: real Glass source → a succinct, *zero-knowledge* proof.** Earlier the two halves lived apart — `prove_glass`/`prove_calls` parse real source but prove with the sound *RLC* argument; `prove_zk`/`prove_query_zk` are the blinded F_{p⁴} FRI STARK but over hand-built circuits. This joins them: a real multi-function program (`fn sq … fn cube … fn f … f(inp)`, parsed by prism) is lowered to a circuit (calls inlined, arithmetic → gates) with a `qassert` binding the output to a public claim `R`, then proven with the blinded FRI STARK. With a *private* input `inp`, it proves "I know an input with `f(input) = R`" — honest ACCEPT, lying about R REJECTs, two blinding seeds give different openings (ZK). **Scope: arithmetic, `let`, calls, `==`/`!=`, `&&`/`||`/`not`, `if`, and scalar `match`** — a real branching language subset. The control-flow gadgets (is-zero, multiplexer, and `match`'s first-match selector-mux) need an inverse *hint* that can't be a gate output, so a pre-pass (`heval`) evaluates the program to compute the hints and lays them on input wires in the exact order `cgen` consumes them. Demos: `fn classify(x) = if x == 7 then 100 else x * x` and `fn grade(x) = match x { 7 => 100; k => k * k }`, each proven for a private `inp`. Order comparisons `<`/`>` would add a ~17-bit range gadget (heavy for the trace) and stay in the RLC bridge (`prove_pane`); structured patterns (`PCtor`/`PTuple`) are the next step. Self-hosted byte-identical.

### Strings in zero-knowledge (v5.101)

Prove a predicate over a **private string** without revealing it. The cut: a string is already a
**multi-wire value** — one codepoint wire per character, the same layout ADTs and tuples use — so it
needs **no new gate type and no verifier change**. `++` (`EConcat`) is structural wire concatenation;
`==`/`!=` is the per-codepoint is-zero gadget AND-folded to one 0/1 wire (unequal lengths → a constant
0, decided at build time); `string_length` is the static wire count; `substring(s, lo, hi)` a static
wire slice (literal **or** computed-static bounds like `string_length(s)-14`). A literal's codepoints
come from `string_index_of` into the printable-ASCII table (the native dialect has no `ord`); a char
outside 32..126 ABSTAINs. Private string inputs ride a **unified multi-wire input model** (an Int is the
1-wire case, a string its codepoints), so every all-int proof stays byte-identical. Three independent
lineages confirm each proof: the witness-free `verify_b3`, the Third Witness (`glass.py`, `--cross-check`),
and the independent [Pentecost](../../pentecost/) verifier (`glass prove --emit` → `glass verify`).

- [`private_prefix.glass`](private_prefix.glass) — **the headline: a private-credential predicate in ZK.** `glass prove private_prefix.glass key="sk-live-…"` proves `substring(key, 0, 8) == "sk-live-"` — the key is a private witness, only the public prefix and the 0/1 verdict are revealed. A non-matching prefix proves 0; a false `--claim` REJECTs.
- [`private_email.glass`](private_email.glass) — **prove a private email is at an organization's domain.** `substring(email, string_length(email)-14, string_length(email)) == "@setonhill.edu"` — the suffix slice's offset folds to a build-time constant (`string_length` is the wire count). The address never appears; the verifier learns only domain membership.
- [`string_eq.glass`](string_eq.glass) — the lowering end to end: `("Hello, " ++ "World") == "Hello, World"` → 12 codepoint wires per side, compared by the AND-folded is-zero gadget → R = 1.
### Records in zero-knowledge (v5.103)

A named record (`type Stats = { lo: Int, hi: Int }`) lowers exactly like a tuple — a multi-wire value
with the fields in **declaration order**, each twidth-padded (so any field width works) — but with **no
tag** (a record is a single-variant product). Construction (`Stats { lo: a, hi: b }`, `ENamedRec`)
mirrors a constructor minus the tag; a `match s { Stats { lo, hi } => … }` pattern (`PRecord`)
destructures by binding each field at its declaration offset. The type-helpers and `twidth` were
extended to handle the `RecordDecl` variant. No new gate, no verifier change.

- [`record_stats.glass`](record_stats.glass) — `order(a, b)` returns a `Stats` record holding the sorted bounds of two **private** values; `span` destructures it (`match s { Stats { lo, hi } => hi - lo }`) to prove the gap. The record is structured data flowing between functions, the inputs never revealed. `x=3 y=8` → 5 ACCEPT; a false claim REJECTs.
- [`record_field.glass`](record_field.glass) — **direct field access `r.field` (v5.104): records complete.** `fn solvent(a: Account) = a.balance >= 100` over a **private** account proves solvency by reading the field directly — revealing only the 0/1 verdict, never the balance or owner. `a.balance` resolves via a record type-env (reusing the `fenv` slot: a record var binds as `name → "@rec:Account"`, which `resolve_fn` ignores) and desugars to the v5.103 pattern form `match a { Account { balance } => balance }`. An `e.field` whose type can't be inferred ABSTAINs.

- [`private_allowlist.glass`](private_allowlist.glass) — **`match` over a private string (v5.102): provable allowlist membership / dispatch.** `match cmd { "deploy" => 1; "rollback" => 2; "status" => 3; _ => 0 }` over a private `cmd` proves which action a hidden command maps to. Each `"literal" =>` arm is the multi-wire per-codepoint equality gadget; `cgen_match`'s first-match mux returns the matched body. Prove "my command is allowed, mapping to action N" without disclosing it; a non-listed command falls through `_` to 0. `cmd="deploy"` → 1 ACCEPT, a false dispatch claim REJECTs.
- [`private_eligibility.glass`](private_eligibility.glass) — **the capstone (v5.108): the whole arc composed into one private access-policy decision.** Prove a private applicant meets a policy — `type Applicant = { age, region }`, `(a.age >= 18) && (a.region <= 5) && (tier == "gold" || tier == "platinum")` — combining **records + field access + ordering comparison + string dispatch** in a single proven circuit, revealing only the allow/deny verdict. age/region/tier are private inputs; an end-to-end test that the arc's features compose through the bridge (a record param *and* a string param, field access feeding comparisons, a helper inlined, booleans combining all). `age0=29 region0=3 tier0=gold` → 1 ACCEPT (witness3 confirms); a false claim REJECTs.

### String-valued results (v5.110)

A proven function can **return a string**, not just a number or a yes/no. A string is a multi-wire value (one field wire per codepoint), so the proof binds **every output wire** as the public claim (`build_claim_mw` — the same is-zero gadget the scalar claim and public-input pinning use, so **no `verify_b3` / Pentecost change**) and **decodes** the codepoints back to text. Two silent-truncation hazards are closed: an `if` returning strings of **different** widths ABSTAINs (the multi-wire `muxw` recurses to the shorter, which would corrupt the value — pad them instead), and a multi-wire **non-string** result (tuple/record/ADT) ABSTAINs rather than publish only its first wire. The Third Witness (glass.py) re-checks the revealed string. Scalar results stay byte-identical.

- [`reveal_prefix.glass`](reveal_prefix.glass) — **selective disclosure of a secret.** `substring(key, 0, 8)` proves + reveals only the first 8 characters of a **private** API key (`key=sk-live-…` → `"sk-live-"`), the rest staying in the witness — verifiable provenance without exposing the credential.
- [`private_verdict.glass`](private_verdict.glass) — **a verdict word chosen by a private comparison.** `if score >= 750 then "PASS" else if score >= 600 then "WAIT" else "FAIL"` reveals the classification of a **private** number while hiding the number (`820 → "PASS"`, `640 → "WAIT"`, `500 → "FAIL"`). The equal-width branches mux wire-by-wire; the Third Witness confirms the circuit selected the verdict the source dictates.

A string result is also **assertable** (v5.111): `glass prove --claim "PASS" private_verdict.glass score=820` binds the *claimed* codepoints, so a false string claim makes the circuit unsatisfiable and the independent `verify_b3` **REJECTs** (`--claim "FAIL"` → REJECT), and a wrong-length claim **ABSTAINs** (never bound as a matching prefix) — the string-result soundness property, made testable end to end. And it is **portable** (v5.112): `glass prove --emit p.b3 reveal_prefix.glass key=sk-live-…` writes a string-valued proof that the independent Pentecost verifier checks (`glass verify p.b3` → `PENTECOST: ACCEPT`) — the "let the verifier be two" guarantee now covers the multi-wire output shape.

### Pane ⊕ Frost — a zero-knowledge query (H1)

The founding vision: *Frost is the zero-knowledge extension of [Pane](../pane/).*
Commit a *private* table, then prove the result of a query — revealing only the
commitment, the query, and the answer, never a row.

- [`prove_query.glass`](prove_query.glass) — the idea, end to end and self-contained: `SELECT SUM(salary) WHERE dept = target` over a private salary table. A binding fingerprint commitment (C = Σ flatᵢ·γⁱ) ties the witness to the public commitment; the query is a circuit; honest ACCEPT, lying about the result or the table REJECTs.
- [`prove_pane.glass`](prove_pane.glass) — **Frost as a second backend over the real Pane query algebra.** Take an actual Pane `Query` value (`SumQ`, `CountQ`, `AvgQ`, `MinQ`, `MaxQ`, `GroupByQ`, `Where(…)`) and lower it gadget-for-gadget into a circuit — equality, booleans (`And`/`Or`/`Not`), arithmetic, **order comparisons** (`<`/`>`, via a 17-bit range gadget), the full **aggregate set** (SUM, COUNT, AVG as proven `sum`+`count`, MIN/MAX as a proven bound + presence), and **`GROUP BY`** — each proven over the same committed table. One AST, two evaluators: `run_query` *interprets* it, `prove_pane` *proves* it — and the discipline is that they agree, the circuit ACCEPTing exactly when its answer equals `run_query`'s.
- [`prove_query_zk.glass`](prove_query_zk.glass) — **the payoff: a committed-table query in *zero-knowledge*.** A SUM over a committed private column — and a `SUM … WHERE` *filtered* query — lowered to the blinded F_{p⁴} FRI STARK (the `prove_zk` backend), so the proof is succinct and leaks nothing. The universal gate identity gains a `qassert·(l−r)` selector so the binding/result assertions and the filter's is-zero gadget are enforced inside the low-degree quotient. Honest ACCEPT; lying about the sum, the table, or a filtered result REJECTs; two blinding seeds verify with different openings (zero-knowledge).

### Onto the real field — Goldilocks (R1)

- [`prove_circuit_goldilocks.glass`](prove_circuit_goldilocks.glass) — **a Glass circuit proven over the production field.** Every other bridge proof computes over toy Baby Bear (values mod 2³¹, which wrap); this proves `f(x) = x*x + 5` over **Goldilocks** (2⁶⁴ − 2³² + 1, the field Plonky2/RISC Zero use) — real 64-bit-range values, no wraparound. The sound RLC: commit the witness (a Goldilocks MiMC hash), derive a challenge γ ∈ F_{p²} ≈ 2¹²⁸ (Fiat-Shamir), check `Σ residualᵢ·γⁱ == 0` (Schwartz–Zippel). Honest ACCEPT, lying about the result REJECT; int64-safe, dogfoods. The first step of making bridge proofs *mean* something cryptographically; succinct + ZK over Goldilocks is the heavier follow-on.

### Toward recursion — a verifier inside a circuit (H3)

- [`prove_recursion.glass`](prove_recursion.glass) — the seed of recursive proofs (a proof that another proof verifies). A STARK verifier's algebraic core is the FRI **fold check** — `fold(f(x), f(-x)) = (f(x)+f(-x))/2 + β(f(x)−f(-x))/(2x)`. This expresses that check as a *circuit* (division by an inverse-witness with a `w·inv == 1` gate) and proves it: an honest fold path ACCEPTs, any tampered value REJECTs. Run it over a whole fold path and you've verified, in-circuit, that a codeword folds to a constant — the FRI low-degree test, recursively.
- [`prove_recursion_zk.glass`](prove_recursion_zk.glass) — **that fold step, in zero-knowledge.** The fold circuit is lowered through the blinded F_{p⁴} FRI STARK (the `prove_zk` backend), so the verifier's own step is succinct and *blind* — the opened values stay private. The `(2x)·inv == 1` division check rides as a `qassert` gate with the inverse on an input wire. Honest ACCEPT, tampered REJECT, two blinding seeds give different openings (ZK). Composed with frost_zk's in-circuit Merkle membership, that's a recursive STARK verifier. (It's deep enough that running it natively — `run_native.sh`, ~1.1s vs ~46s interpreted — is the point.)

### The canonical ZK statement — knowledge of a hash preimage (H3′)

- [`prove_preimage_zk.glass`](prove_preimage_zk.glass) — **"I know a secret `x` such that `Hash(x) = H`"**, proven in zero-knowledge. `Hash` is a 2-to-1 compression built from the same cryptographic heart as Glass's [Poseidon](../frost/frost_poseidon.glass) — the **x⁷ S-box** (a permutation on Baby Bear, `gcd(7, p−1) = 1`), round constants, and the **MDS mix** `[[2,3,1],[1,2,3],[3,1,2]]` — lowered gate-for-gate into a Frost circuit. The secret preimage `(a, b)` sits on private input wires; the circuit truncates the permutation output to one lane (that truncation is what makes it one-way) and a `qassert` gate forces it to equal the public digest `H`. The whole circuit is proven by the blinded F_{p⁴} FRI STARK, so the proof is succinct and reveals nothing about `(a, b)`. Honest ACCEPT; a wrong preimage with the same claimed `H` REJECTs; two blinding seeds verify with different openings (ZK). Rounds are reduced (full → partial) so the trace dogfoods on the reference interpreter — the full 30-round Poseidon is structurally identical and runs the same way, just heavier (`run_native.sh`, ~1.2s).
