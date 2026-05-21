# Self-hosting

This document explains what Glass means by "self-hosting" and what Stage 3 — the v1.0 milestone — actually demonstrates.

---

## The three stages

| Stage | Description | Status |
|-------|-------------|--------|
| **Stage 1** | Compiler/interpreter shape exists in the target language | ✓ v0.7 |
| **Stage 2** | Real working pipeline (lex → parse → type-check → eval) in the target language | ✓ v0.9.5 |
| **Stage 3** | The target-language implementation can read source files from disk and run them | ✓ **v1.0** |

A traditional "Stage 4" — the target-language implementation can compile *itself* and bootstrap — is future work. See "What's next" below.

---

## The cast

Two implementations are involved:

- **`glass.py`** — the **host**. A Python implementation in one file (~2,400 lines). Lexer, parser, Hindley-Milner inferer with effect rows, tree-walking evaluator.
- **`examples/selfhost/prism.glass`** — the **self-host**. A Glass implementation of Glass (3,984 lines). Same architecture as the host but written in the target language.

The two implementations agree. When you give them the same program, they return the same answer.

```
$ cat /tmp/expr.glass
let x = 10 in
let y = 20 in
x * y + 1

$ glass /tmp/expr.glass
201 : Int

# And via the self-host:
$ glass examples/selfhost/prism.glass
...
/tmp/expr.glass  ==>  201 : Int
```

---

## What prism.glass contains

[`examples/selfhost/prism.glass`](../examples/selfhost/prism.glass) is one file, 3,984 lines. Reading top to bottom:

| Lines | Section | What it does |
|-------|---------|--------------|
| 1–200 | Types | AST types (`Expr`, `Type`, `Pattern`, etc.), token types, value types |
| 200–500 | Lexer | `String -> List<Token>` |
| 500–1000 | Parser | `List<Token> -> Result<Program, String>` |
| 1000–2400 | Type inferer | Hindley-Milner with effect rows, mutually recursive |
| 2400–3000 | Evaluator | Tree-walking interpreter over the AST |
| 3000–3500 | Pretty-printing | `show_type`, `show_value`, error formatting |
| 3500–3900 | The `compile` pipeline | wires lex + parse + check + eval together |
| 3900–3984 | Demo block | exercises the pipeline on inline + on-disk programs |

The total Glass-in-Glass body across all `examples/selfhost/` is **6,462 lines — 274% the size of the Python host.**

---

## Reading the Stage 3 chain

Here's the full chain when you run `glass examples/selfhost/prism.glass`:

1. The `glass` shell command invokes `python -m glass examples/selfhost/prism.glass`.
2. `glass.py` reads `prism.glass` from disk.
3. `glass.py`'s lexer turns it into tokens.
4. `glass.py`'s parser turns the tokens into a `Program` AST.
5. `glass.py`'s type checker infers types and effects for every declaration.
6. `glass.py`'s evaluator walks the AST. Among the top-level statements is:
   ```glass
   let _ = match read_file("examples/stage3/poly.glass") {
     Ok(src) =>
       match compile(src) {
         Ok((t, eff, v)) =>
           print("examples/stage3/poly.glass ==> "
                 ++ show_value(v) ++ " : " ++ show_type(t));
         Err(msg) => print("compile error: " ++ msg)
       };
     Err(msg) => print("read error: " ++ msg)
   }
   ```
7. Evaluating this calls the host `read_file` builtin, which reads `poly.glass` from disk and returns `Ok(StringV(content))`.
8. The match destructures `Ok(src)` and calls `compile(src)`. But `compile` here is **prism.glass's** `compile` function — a closure in the runtime environment of prism.glass.
9. **prism.glass's** `compile` lexes the contents of poly.glass (using prism.glass's lexer, which is a Glass function), parses (using prism.glass's parser), type-checks (using prism.glass's inferer), and evaluates (using prism.glass's evaluator).
10. The result is `Ok((TyInt, EffRow([], None), VInt(78)))` — wrapped values in prism.glass's `Value` type.
11. `show_type` and `show_value` (both Glass functions defined in prism.glass) format the triple.
12. The host `print` builtin outputs the string to stdout.
13. Result: `examples/stage3/poly.glass ==> 78 : Int`.

Two interpretation levels. Both produced by the same language semantics. Both giving the same answer the host would give.

---

## What this proves

Stage 3 demonstrates that Glass is **expressive enough to describe itself**. Every feature prism.glass uses — generic ADTs, mutual recursion, pattern matching, Hindley-Milner inference, effect rows, file I/O — is part of the language Glass exposes to its users.

It also demonstrates that the language is **consistent under reflection**. A program written in Glass-the-spec, run by Glass-the-implementation, produces the same answer Glass-the-implementation would produce running natively. No silent semantic drift between the formal definition and the executable.

---

## What's NOT done yet

Stage 3 is not the same as a fully bootstrapping compiler.

- **prism.glass cannot yet read itself.** It can read small Glass files. Reading its own ~4,000-line source through itself is technically possible but slow — the tree-walking evaluator rebuilds environments on each call and would take hours.
- **There is no Glass→native compiler.** prism.glass is an interpreter. Glass is interpreted on top of an interpreter on top of Python.
- **No module system.** All declarations share a single top-level namespace.

These are the **Quartz** roadmap items. See [`../CHANGELOG.md`](../CHANGELOG.md) for the v2.0 plan.

---

## Why this is worth doing

The traditional reason to self-host a language is performance: a native compiler produces faster code than an interpreter. That's not Glass's reason — performance is a v2.0 problem.

The reason Glass self-hosts is **specification convergence**. When you can write the language's semantics *in the language itself*, the specification stops being a separate artifact from the implementation. There's a single source of truth — the prism.glass file. Anyone who reads prism.glass is reading both how Glass works and a working implementation of those rules.

For a language designed around transparent local reasoning, this matters. The fewer hidden translations between "the spec" and "the code", the better.

---

## See also

- [`../examples/selfhost/prism.glass`](../examples/selfhost/prism.glass) — the full implementation
- [`../examples/stage3/`](../examples/stage3/) — the Glass files prism.glass reads from disk
- [`../LANG.md`](../LANG.md) — formal specification with detailed audit
