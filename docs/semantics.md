# Glass — operational semantics

This is the explicit semantics of Glass's core. The executable version is
`glass.py` (the reference interpreter) and `examples/selfhost/prism.glass` (the
same semantics, written in Glass); the two are differential-tested to agree.
This document writes the rules down so the language is defined, not just
implemented.

Glass is a **pure, eagerly-evaluated, expression-oriented** language. Evaluation
is big-step: an expression in an environment reduces to a value, while
performing a set of effects.

## Values

```
v ::= n                      integer
    | b                      boolean (true | false)
    | s                      string
    | ⟨λx. e, ρ⟩              closure (parameter, body, captured environment)
    | C(v₁, …, vₖ)            constructor value (a tag C with k field values)
    | (v₁, …, vₙ)            tuple
    | { ℓ₁ = v₁, …, ℓₘ = vₘ } record (named fields)
```

An **environment** `ρ` maps names to values. There is no mutable state: `ρ` is
extended, never updated in place.

## The judgment

```
ρ ⊢ e ⇓ v ! ε
```

reads: in environment `ρ`, expression `e` evaluates to value `v`, performing the
effects `ε` (a set of labels like `{IO}`, `{Inference}`). Effects accumulate as
the union of the effects of sub-evaluations; the type system tracks them
statically (the effect row on a function's arrow), and evaluation actually
performs them. Pure expressions have `ε = ∅`; we drop `! ∅` for brevity.

## Core rules

**Literals and variables.**
```
ρ ⊢ n ⇓ n            ρ ⊢ b ⇓ b            ρ ⊢ s ⇓ s

x ∈ dom(ρ)
─────────────
ρ ⊢ x ⇓ ρ(x)
```

**Functions and application.** A lambda captures its environment; application is
call-by-value (the argument is evaluated before the call).
```
ρ ⊢ λx. e ⇓ ⟨λx. e, ρ⟩

ρ ⊢ e₁ ⇓ ⟨λx. e, ρ'⟩ ! ε₁     ρ ⊢ e₂ ⇓ v₂ ! ε₂     ρ'[x ↦ v₂] ⊢ e ⇓ v ! ε₃
──────────────────────────────────────────────────────────────────────────
ρ ⊢ e₁ e₂ ⇓ v ! (ε₁ ∪ ε₂ ∪ ε₃)
```
Multi-argument functions are curried lambdas; `fn f(a, b) = e` is
`λa. λb. e`. Mutual recursion binds the sibling group's closures in the
environment before evaluating any body.

**Let.** Binding is non-recursive (`let`) or recursive (`let rec`); the bound
value extends the environment for the body.
```
ρ ⊢ e₁ ⇓ v₁ ! ε₁     ρ[x ↦ v₁] ⊢ e₂ ⇓ v₂ ! ε₂
───────────────────────────────────────────────
ρ ⊢ (let x = e₁ in e₂) ⇓ v₂ ! (ε₁ ∪ ε₂)
```

**Conditionals.** Only the taken branch is evaluated (short-circuit).
```
ρ ⊢ c ⇓ true ! ε₁    ρ ⊢ t ⇓ v ! ε₂          ρ ⊢ c ⇓ false ! ε₁    ρ ⊢ f ⇓ v ! ε₂
───────────────────────────────────────      ────────────────────────────────────────
ρ ⊢ (if c then t else f) ⇓ v ! (ε₁∪ε₂)       ρ ⊢ (if c then t else f) ⇓ v ! (ε₁∪ε₂)
```

**Operators.** `+ - * / %` are integer arithmetic; `==` is structural equality
on primitives and constructor values (never on closures); `++` concatenates
strings or lists; `&& || !` are boolean with short-circuit `&&`/`||`. Each
evaluates its operands and applies the primitive.

**Constructors.** A constructor builds a value from its evaluated arguments.
```
ρ ⊢ eᵢ ⇓ vᵢ ! εᵢ   (for each i)
──────────────────────────────────
ρ ⊢ C(e₁,…,eₖ) ⇓ C(v₁,…,vₖ) ! ⋃ εᵢ
```

**Pattern matching.** Arms are tried in order; the **first** pattern that
matches wins. Matching binds pattern variables into the environment for that
arm's body. Matching is **total** — the type checker rejects a `match` that
doesn't cover every constructor, so a stuck match cannot occur in a
well-typed program.
```
ρ ⊢ e ⇓ v ! ε₀     match(pᵢ, v) = θ   (i least such that pᵢ matches v)
ρ·θ ⊢ bodyᵢ ⇓ v' ! εᵢ
──────────────────────────────────────────────────────────────────────
ρ ⊢ (match e { p₁ ⇒ body₁; … }) ⇓ v' ! (ε₀ ∪ εᵢ)
```
where `match(p, v)` returns a binding `θ` or fails: a variable/wildcard
matches anything; a literal matches an equal value; `C(p₁,…)` matches
`C(v₁,…)` when each `pⱼ` matches `vⱼ`; a tuple pattern matches a tuple
componentwise.

## Refinement types

A refinement `T where (φ)` is a runtime contract checked at fn entry, `let`
binding, and `let … in`. An obligation the compiler can discharge by
**implication** (constant folding, alpha-equivalence, interval reasoning) emits
no runtime check; the rest are checked, and a violation aborts at the boundary.
This is a *typing/elaboration* concern layered over the rules above; it never
changes the value an expression computes, only whether it is admitted.

## What this does not cover

Type inference (Hindley–Milner with effect rows), the refinement subsumption
algorithm, and module/`import` resolution are elaboration steps that run before
evaluation; see [`LANG.md`](../LANG.md) and [`design-notes.md`](design-notes.md).
The rules here define what a *well-typed* Glass program *means* once elaborated —
and `glass.py` is their executable transcription.
