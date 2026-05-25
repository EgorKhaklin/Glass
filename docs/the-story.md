# Glass, end to end

*One principle — that you should never have to take the code's word for it —
carried from a type signature all the way to a zero-knowledge proof over data
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

---

## The discipline that makes it true

Glass is not just a language; it's a *method*. Every layer is a **reference
semantics** plus a **compiler**, and they must agree bit-for-bit — checked by
differential testing. `glass.py` ⟷ `native_glassc`. `eval` ⟷ circuit.
`run_query` ⟷ Frost. One command runs the check on any file:

```bash
bash examples/selfhost/dogfood.sh examples/prove/prove_pane.glass
# native_glassc == glass.py, byte-identical.  381/381 suite, every example.
```

Nothing here is "done" until the interpreter and the self-hosted compiler give
the *same answer*. That is the whole point: **you never have to take the code's
word for it.**

— Continue at the [roadmap](roadmap.md), or read the [language tour](language-tour.md).
