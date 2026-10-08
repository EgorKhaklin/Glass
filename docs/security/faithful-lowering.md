# Faithful lowering of the prove bridge

**Status: the silent-zero finding below is resolved; one residual (field versus integer
semantics) remains open.** Research/educational-grade, UNAUDITED.

This documents a concrete, reproducible **silent wrong-certification** in `glass prove` on the
Goldilocks default path, how it was closed, and what is still not covered. It is an instance of
the "compiler-bridge faithful lowering" gap that [`audit-readiness.md`](audit-readiness.md)
lists as outside the soundness threat model.

## What the soundness proof does and does not cover

[`soundness-proof.md`](soundness-proof.md) proves (modulo its assumptions) that the **gate
circuit** computes `out = R`. It does **not** prove that the prove bridge
(`examples/prove/prove_source_goldilocks_zk.glass`) lowers a Glass *source program* into a
circuit that faithfully represents the program's semantics under the reference interpreter
`glass.py`. A lowering bug therefore certifies the wrong quantity: a sound proof of a circuit
that is not the program.

## The finding (resolved): unsupported operators lowered silently to 0

The Goldilocks bridge once arithmetized only `EInt, EBool, EVar, EAdd, ESub, EMul, EEq, EIf,
ELet, ECtor, ETuple, EApp(named), EMatch`. Its evaluators and circuit generators (`heval`, the
`seval` guard, `cgen`, `cg`) all ended in a silent fallthrough, `_ => glit(0)`. A program using
any other node (`&&`, `||`, `!`, `!=`, `<`, `/`, `%`, strings, records) parsed and type-checked,
then evaluated as `0` in every stage in lockstep, so `R` (from `heval`) equalled the circuit
output (from `cgen`) and `verify_b3` ACCEPTed: a valid-looking **sound** proof of a value the
program does not compute.

```glass
fn f(x: Int) : Int = if (x == 5) && (x == 5) then 7 else 0
f(5)
```

`glass.py` computes **7**; the bridge proved `R = 0`. The cause: when the default field moved
from Baby Bear to Goldilocks, the Baby Bear bridge's boolean gadgets were not ported, so programs
using them regressed from proven correctly to silently proven as 0 (for example
`age_prove.glass`, whose `&&` chain certified 0).

## Resolution

- The boolean gadgets (`&& || ! !=`) were ported. They are faithful because their operands are
  0/1 (type-enforced).
- Every fallthrough now calls `error`, so the bridge **refuses** (ABSTAIN, exit 1) anything it
  has no faithful lowering for, instead of proving 0.
- Ill-typed source is refused before lowering.
- Recursion is unrolled to a fixed bound; on the CLI path the `seval` guard refuses a program
  whose actual recursion exceeds it, instead of proving a depth-truncated value.

The bridge has since gained faithful gadgets, each refusing out-of-range operands: ordering
comparisons, `/` and `%` (operands in [0, 2³²), divisor non-zero); signed comparison and
`sdiv`/`smod` over [−2³¹, 2³¹); `bit_and`/`bit_or`/`bit_xor` over [0, 2³²); strings as
codepoint wires (`++`, `==`, `!=`, `string_length`, static `substring`, `match` on literals);
records, field access, and tuples; computed callees. Later sweeps found and closed three more
silent wrong-ACCEPT lowerings and an inlining-capture bug (see the
[audit-readiness addendum](audit-readiness.md#addendum-later-findings)).

## Remaining gap: field semantics versus integer semantics

`heval`, `seval`, and `cgen` compute `+ - *` in the field **mod p = 2⁶⁴−2³²+1**. `glass.py`
uses 64-bit signed integers (`+ - *` wrap at 2⁶⁴; `/ %` truncate toward zero). The two agree
when no intermediate or result wraps in either domain. A negative value is the field element
p − |v|, and the CLI prints values above p/2 as negative, so small negative results display
correctly (a genuine unsigned value in (p/2, p) would also print as negative). Where they
diverge:

- **Overflow.** If a product or sum leaves the range where both agree, the circuit certifies
  the value reduced mod p, while `glass.py` wraps mod 2⁶⁴. The certified value differs from
  the source's, with no warning.

There is **no in-circuit overflow guard** for `+ - *`; the comparison, division, and bitwise
gadgets range-check their own operands, but plain arithmetic does not. `glass prove
--cross-check` re-runs the source under `glass.py` and compares the proven result with it
modulo p; a mismatch is a DIVERGENCE (exit 3). That is a per-run check on the result, not a
circuit constraint. **Without it, `glass prove` is faithful to `glass.py` only for programs whose
every intermediate and result stays in the range where field and int64 arithmetic agree.**

## Honest framing

None of this changes the cryptographic soundness boundary or any production claim: it sits
inside the disclosed "faithful lowering is assumed, not proven" caveat. A silent wrong-ACCEPT
is strictly worse than a refusal, and closing it (a faithful gadget **or** a loud refusal,
never a silent 0) shrinks the trusted-lowering surface an external auditor must take on faith.
An ACCEPT can no longer come from a silently dropped operator. The residual is the
field-semantics caveat above.
