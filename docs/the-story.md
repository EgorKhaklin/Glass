# Glass, end to end

*One principle — that you should never have to take the code's word for it —
carried from a type signature all the way to a zero-knowledge proof: of what a
program computed, the types it promised, and the effects it touched — over data
you never reveal.*

This is the whole arc in one read. Every claim below is a command you can run.

---

## 1 — It tells the truth

A Glass signature is the entire contract. It says what a function takes, what it
returns, what it can fail with, and what it touches. The compiler enforces that
you can understand a function by reading it and only it.

```glass
fn safe_divide(a: Int, b: Int) : Result<Int, String> =
  if b == 0 then Err("cannot divide by zero")
  else Ok(a / b)
```

That return type *is* the contract — the caller must handle both cases; there is
no silent failure, no exception, no hidden path. Refinement types push it
further (`x: Int where x > 0`), effects are declared in the signature
(`!{IO}`), and matches must be exhaustive.

```bash
glass examples/basic/hello.glass
glass examples/showcase/          # browse what the language can express
```

## 2 — It compiles itself

Glass's compiler is written in Glass. `native_glassc` — itself compiled from
Glass source — compiles **itself** and the `prism` front end, and reproduces
them *byte-for-byte*, with no other language in the loop. A language honest
about what code does is honest enough to stand on its own.

```bash
bash examples/selfhost/bootstrap_fixpoint.sh
# native_glassc compiles glassc.glass -> native_glassc_2; both emit
# byte-identical C for prism. The fixpoint closes.
```

## 3 — It proves itself

Built from scratch, in Glass: **Frost**, a zero-knowledge proof system
(zk-STARK). A finite field and an F_{p⁴} extension, a hash, Merkle trees,
arithmetization, a FRI low-degree test, AIR, Fiat-Shamir, ZK blinding, a
permutation argument — none of it imported, all of it in Glass, all self-hosting.

The **prove bridge** turns that toolkit into a language feature: write a real
Glass expression, get a proof that it ran correctly — sound, succinct, and
zero-knowledge — revealing only the circuit and a commitment.

```bash
glass examples/prove/prove_zk.glass
# f(x) = x*x + x + 5, secret x = 3 -> a blinded F_{p^4} FRI proof.
# honest witness -> ACCEPT;  tampered -> REJECT;  two blindings, openings differ.
```

## 4 — It proves *queries over private data*

This is the founding vision, and it now closes: **Frost is the zero-knowledge
extension of Pane** (Glass's query language). You commit a private table, then
prove the answer to a query over it — revealing only the commitment, the query,
and the answer. Never a row.

`prove_pane` lowers a *real Pane query* (`SumQ`/`CountQ`/`AvgQ`/`MinQ`/`MaxQ`/
`GroupByQ`, with equality / boolean / arithmetic / `<`–`>` range filters) into a
Frost circuit. One AST, two evaluators — `run_query` *interprets* it, the prover
*proves* it — kept honest by the rule that they must agree:

```text
$ glass examples/prove/prove_pane.glass

SELECT SUM(salary) WHERE dept=eng            : run_query = 250 | proof(honest) ACCEPT | proof(wrong 251) REJECT | Frost==Pane: yes
SELECT COUNT(*)    WHERE dept=sales          : run_query = 2   | ...ACCEPT | ...REJECT | yes
SELECT SUM(salary) WHERE salary > 85         : run_query = 340 | ...ACCEPT | ...REJECT | yes
SELECT dept, SUM(salary) GROUP BY dept       : eng -> 250 ACCEPT, sales -> 170 ACCEPT
AVG(salary) WHERE dept=eng                   : sum=250 count=2 (avg = 125)  proven
MIN/MAX(salary)                              : 80 / 150  honest ACCEPT, lies REJECT
```

And the headline, in zero-knowledge — a committed-table query lowered to the
blinded F_{p⁴} FRI STARK, succinct and leaking nothing:

```text
$ glass examples/prove/prove_query_zk.glass

public: commitment C = 185185150,  sum R = 250   (values stay private)
honest proof (R = 250):    ACCEPT
lying about the sum (R = 999):  REJECT
lying about the table (wrong C): REJECT
ZERO-KNOWLEDGE: two blinding seeds both verify: ACCEPT / ACCEPT; quotient opening #5 differs: yes
```

Revealed: the commitment, the query, the answer. Hidden: every row.

## 5 — It proves what you *wrote* — and what you *promised*

The prove bridge is not limited to a hand-picked expression. It takes **real Glass
source** — parsed by `prism`, the Glass-in-Glass front end — and lowers it to a
proof: arithmetic, `let`, function calls, `match`, **bounded recursion**, **linked
lists** (`type IntList = Nil | Cons(Int, IntList)`), and **higher-order functions**
(passing a function — or a lambda — as an argument). Recursion is unrolled and the
higher-order program is beta-reduced to a first-order, call-free circuit; you write
ordinary Glass, you get a proof of its result.

```bash
glass prove examples/prove/hello_prove.glass inp=9     # f(x)=sq(x)+5 -> result 86, proof ACCEPT
# and (see examples/prove/): fact_prove (recursion), list_sum_prove (a fold over a
# list), map_prove (higher-order map), all lowered to the same blinded FRI STARK.
```

And the type system's own promises become part of the proof. A function's
refinement — the `where (P)` on its return — is extracted and **asserted inside the
circuit**, so the type is not merely *checked* at compile time; it becomes a
*cryptographic guarantee* about the result. A function that lies about its declared
type is **unprovable**:

```text
fn fact(n) : Int where (result != 0) = if n == 0 then 1 else n * fact(n - 1)
  fact(5) = 120, refinement (result != 0) proven in-circuit -> ACCEPT
fn ident(x) : Int where (result == 0 || result == 1) = x
  ident(5) = 5, violates the refinement -> REJECT  (the in-circuit assertion fails)
```

The `where`-clause is the contract; the proof is the enforcement. *(This is the **default**
for `glass prove` now: real source is proven over the production **Goldilocks** field —
2⁶⁴, the field real provers use, no toy-field wraparound — including ordering comparisons
`< > <= >=`. The toy Baby Bear field, `--baby-bear`, remains for full `match`-over-your-own-types.)*

## 6 — It proves what your code *touches*

A Glass signature already declares its effects — `!{Inference}`, `!{Random}`,
`!{State}`. The frontier closes the loop: **the effect row generates the proof.**
Each effect becomes a committed, checkable trace entry — an LLM call pinned to a
committed answer, a random draw bound so it can't be ground, a memory trace where
every read is forced to equal the last write — and the proof's obligations are *read
straight off the signature*.

```text
$ glass examples/prove/prove_effects_zk.glass

fn analyze(x) : Int !{Inference, Random, State}
  declared effect row -> 3 obligations: committed-oracle; transcript-bound draw; memory-consistency
  discharge every obligation with its gadget: ACCEPT
  change the row, the schema changes  (pure fn -> no obligations; !{Random} -> one)
```

Read the signature, and you know what the proof proves. The most striking case is
the AI one: `prove_inference_zk` proves a computation **used a committed model answer
faithfully** — *"the model's answer is one of the allowed options, committed in C"* —
while revealing nothing about which. You don't prove the model is correct; you prove
your program used its output honestly. The untrusted-AI-output problem, answered with
a proof.

```bash
glass examples/prove/prove_inference_zk.glass   # LLM-in-the-loop, in zero-knowledge
glass examples/prove/prove_random_zk.glass      # a provably-fair, un-grindable draw
glass examples/prove/prove_state_zk.glass       # mutable state, read-after-write consistency
```

## 7 — It checks the proof twice

A proof you can only check with the program that made it is a closed loop. So the
verifier is **two**. Beside Glass's own witness-free verifier (`verify_b3`) stands
**Pentecost** — a second, from-scratch re-implementation of the *same* verification
algorithm in a different language, with a different number representation, sharing
**no code** with the prover. A proof is portable: emit it on one side, check it on the
other — separate programs, separate lineages, one verdict that must agree.

```bash
glass prove --emit /tmp/p.txt examples/prove/hello_prove.glass inp=9
glass verify /tmp/p.txt          # -> PENTECOST: ACCEPT   (a separate program, no shared code)
```

Honest proofs ACCEPT in both. A tampered proof — or one re-pointed at a false claim —
is REJECTed by the independent verifier; it has been thrown thousands of forged and
tampered proofs across several circuit shapes, and rejected every one. And when the
prover *can't* faithfully lower a program to a circuit, it returns a third verdict —
**ABSTAIN** — instead of bluffing, so a refusal is never mistaken for a disproof.

The same proofs compose with a small suite of primitives built on the one hash: a
content-addressed fingerprint of the whole toolchain (`glass fingerprint`), an
append-only tamper-evident ledger of verdicts (`glass ledger`), and selective
disclosure over a commitment (`glass disclose`). The plain names map to their branded
ones in [naming.md](naming.md).

---

## The discipline that makes it true

Glass is not just a language; it's a *method*. Every layer is computed two
independent ways and forced to agree bit-for-bit — checked by differential
testing. `glass.py` ⟷ `native_glassc`. `eval` ⟷ circuit. `run_query` ⟷ Frost.
And now the cryptographic verifier itself: `verify_b3` ⟷ Pentecost. One command
runs the check on any file:

```bash
bash examples/selfhost/dogfood.sh examples/prove/prove_pane.glass
# native_glassc == glass.py, byte-identical.  422/422 suite, every example.
```

Nothing here is "done" until the interpreter and the self-hosted compiler give
the *same answer*. That is the whole point: **you never have to take the code's
word for it.**

And the same honesty applies to the proofs themselves: the differential-testing
guarantee is rigorous, but the cryptography is *educational-grade* — a real,
from-scratch zk-STARK, not an audited one. What is real and what is a
demonstration is written down, per component, in the **[soundness ledger](soundness.md)**.
You should never have to take *that* on the code's word either.

— Continue at the [roadmap](roadmap.md), or read the [language tour](language-tour.md).
