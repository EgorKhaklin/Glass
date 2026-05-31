# Audit finding — faithful lowering of the prove bridge (UNRESOLVED)

**Status: confirmed, fix scoped, NOT yet fixed.** Research/educational-grade, UNAUDITED.
This documents a concrete, reproducible **silent wrong-certification** in `glass prove` on the
Goldilocks default path, and the planned fix. It is a concrete instance of the
"compiler-bridge faithful lowering" gap that [`docs/audit-readiness.md`](audit-readiness.md)
already lists as out of the soundness threat model — made executable here, and shown to affect
shipped examples.

## What the soundness proof does and does not cover

[`docs/tier1-soundness-proof.md`](tier1-soundness-proof.md) proves (modulo its assumptions) that
the **gate circuit** computes `out = R`. It explicitly does **not** prove that the prove bridge
(`examples/prove/prove_source_goldilocks_zk.glass`) lowers a Glass *source program* into a circuit
that faithfully represents the program's semantics under the reference interpreter `glass.py`. A
lowering bug therefore certifies the wrong quantity: a perfectly sound proof of a circuit that
isn't the program.

## The finding: unsupported operators lower silently to 0

The Goldilocks bridge arithmetizes only `EInt, EBool, EVar, EAdd, ESub, EMul, EEq, EIf, ELet,
ECtor, ETuple, EApp(named), EMatch`. Its evaluators and circuit generators (`heval`, the `seval`
guard, `cgen`, `cg`) all end in a silent fallthrough — `_ => glit(0)` — and `unroll` passes
unhandled nodes through unchanged (`_ => e`).

But `prism`'s parser produces many more `Expr` nodes that the bridge never handles:
`EAnd, EOr, EUNot, ENeq, ELt, EGt, ELe, EGe, EDiv, EMod, EConcat, EStr, ERec, EField, …`.
A program using any of these **parses fine, type-checks fine, and is then silently evaluated as
`0`** by every stage of the bridge in lockstep — so `R` (from `heval`) equals the circuit output
(from `cgen`), and `verify_b3` ACCEPTs. The result is a valid-looking **SOUND** proof of a value
the program does not compute.

This is the exact "silent wrong certification" class that v5.49 set out to eliminate. v5.49 closed
it for parse failure, unresolved calls, higher-order callees, and over-deep recursion — but **not**
for unsupported operators.

### Reproduction (minimal)

```glass
fn f(x: Int) : Int = if (x == 5) && (x == 5) then 7 else 0
f(5)
```

- `glass.py` (the reference semantics): **7**.
- `glass prove <file>` (Goldilocks default): `result: 0` / `proof: ACCEPT (SOUND — independent
  witness-free verify_b3; not zero-knowledge)`.

`&&` (an `EAnd` node) hits the silent fallthrough → `0` → the `if` takes the else branch → the
bridge proves `R = 0`, soundly, against a circuit that is not the program.

## Blast radius: this is a v5.46 regression affecting shipped examples

The **baby-bear** bridge (`prove_source_adt_zk.glass`) *does* handle the boolean operators —
`EAnd → mul`, `EOr → a+b−ab`, `EUNot → 1−a`, `ENeq → 1−eq` (faithful, because boolean operands are
0/1). When v5.46 flipped the default field from baby-bear to Goldilocks, the Goldilocks bridge was
built with a **smaller operator surface** and these gadgets were never ported — so every program
using them silently regressed from "proven correctly" to "silently proven as 0".

`grep` finds **~17 shipped `examples/prove/*.glass` use `&&` in real (non-comment) code**, none of
them passing `--baby-bear` — e.g. `age_prove.glass`, whose documented claim is "R = 1 iff a ≥ 21"
but which now lowers its `&&`-chain to 0 and certifies `R = 0`. (Comparisons `< > <= >=` and
`/ %` are likewise unsupported; unlike booleans they have **no** faithful field gadget — a field has
no order — and must be expressed as range/bit-decomposition gadgets, as `age_prove`'s own comment
explains.)

## The fix (scoped, not yet applied)

A faithful, sound resolution has two parts, both confined to the (non-bootstrap) prove bridge:

1. **Port the faithful boolean gadgets** (`EAnd, EOr, EUNot, ENeq`) from the baby-bear bridge into
   the Goldilocks bridge's `unroll` / `heval` / `seval` / `cgen` / `cg`. These are faithful because
   the operands are boolean 0/1 (type-enforced; produced by `==`/`EBool`). This restores `age_prove`
   and the ~17 affected examples to **correct** behavior.
2. **Refuse loudly** (`error(...)`, as the unresolved-call and deep-recursion guards already do) for
   every operator that has *no* faithful field lowering — ordering (`< > <= >=`), `/`, `%`, string
   `++`, records/fields — instead of silently lowering to 0. A program the bridge cannot faithfully
   arithmetize must be rejected, never silently mis-proved.

This is deliberately deferred to a focused, fully-gated pass rather than rushed: it is a sweeping
edit to soundness-critical code across five functions, and validating it means re-running the ~17
affected examples natively (each ~2–3 min) to confirm they ACCEPT with the **correct** `R` and that
the now-unsupported operators refuse loudly. Gates: `python3.12 tests/test_glass.py` + native
re-validation (this bridge is **not** bootstrap-critical, so no fixpoint dependency).

## Honest framing

This does not change the crypto soundness boundary or any production claim — it is squarely inside
the already-disclosed "faithful lowering is assumed, not proven" caveat. But a silent wrong-ACCEPT
on shipped examples is strictly worse than a refusal, and closing it (faithful gadget **or** loud
refusal, never silent 0) measurably shrinks the trusted-lowering surface an external auditor must
take on faith. Until fixed, treat `glass prove` results for any program using operators outside
`+ - * ==` (and `match`/ADT/`if`/`let`/calls) as **unsound on the Goldilocks default**.
