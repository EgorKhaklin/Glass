# Self-hosting

This document explains what Glass means by "self-hosting" — and Glass now fully self-hosts: the bootstrap fixpoint closed at **v4.76** (Stage 4 below).

---

## The three stages

| Stage | Description | Status |
|-------|-------------|--------|
| **Stage 1** | Compiler/interpreter shape exists in the target language | ✓ v0.7 |
| **Stage 2** | Real working pipeline (lex → parse → type-check → eval) in the target language | ✓ v0.9.5 |
| **Stage 3** | The target-language implementation can read source files from disk and run them | ✓ **v1.0** |
| **Stage 4** | The target-language implementation compiles *itself* and bootstraps (fixpoint) | ✓ **v4.76** |

**Stage 4 is done.** `examples/selfhost/glassc.glass` is a Glass→C compiler written in Glass. `quartz.py` compiles it to a native binary *once*; that binary (`native_glassc`) then compiles glassc.glass itself into `native_glassc_2`, with no Python in the loop. `native_glassc_2` compiles `prism.glass` byte-identically to `glass.py prism.glass` (all 191 demo lines), and `native_glassc` and `native_glassc_2` emit byte-identical C — exact self-reproduction. Reproduce the whole chain with `bash examples/selfhost/bootstrap_fixpoint.sh`.

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

## Running at native speed

Glass has two execution paths, and they are *not* interchangeable in cost:

- **`glass.py`** — the reference interpreter. Readable, the spec, the differential-testing oracle. But a tree-walker in Python: heavy programs (the from-scratch zk-STARK, large circuits) take tens of seconds.
- **`native_glassc`** — the self-hosted compiler: Glass → C → a native binary. **~50–100× faster**, and bit-for-bit identical to the interpreter (that's exactly what `dogfood.sh` guarantees).

One command compiles and runs through the fast path:

```bash
bash examples/selfhost/run_native.sh examples/prove/prove_query_zk.glass
# the full zero-knowledge query demo: ~0.4s native vs ~38s interpreted (~95×).
```

So the working rhythm is: **prototype and verify on the interpreter** (small inputs, `dogfood.sh` for the reference⟷compiler check), then **run at scale natively**. The interpreter is the meaning; the compiler is the engine — and they agree.

---

## Why this is worth doing

The traditional reason to self-host a language is performance: a native compiler produces faster code than an interpreter. That's not Glass's reason — performance is a v2.0 problem.

The reason Glass self-hosts is **specification convergence**. When you can write the language's semantics *in the language itself*, the specification stops being a separate artifact from the implementation. There's a single source of truth — the prism.glass file. Anyone who reads prism.glass is reading both how Glass works and a working implementation of those rules.

For a language designed around transparent local reasoning, this matters. The fewer hidden translations between "the spec" and "the code", the better.

---

## Known divergences (the honest edge)

Three implementations are kept in lockstep by differential testing: the reference interpreter (`glass.py`), the Quartz C back end (`quartz.py`, which shares the reference's parser), and the self-hosted front end (`prism.glass`). [`dogfood.sh`](../examples/selfhost/dogfood.sh) checks that any file runs identically on `glass.py` and the self-hosted `native_glassc`.

A parser-parity audit closed **every** case where they had drifted: the reference now **rejects chained comparisons** (`a == b == c`) and **uppercase value bindings** (matching prism); **both** sides accept **negative literals** (`-5`) and **fixed-length list patterns** (`[a, b]`); `prism` + `glassc` parse and compile **record patterns** (`Point { x, y } => …`); the **whole standard prelude** self-hosts (`fst`/`snd`/`reverse` and the `map_option`/`bind_option`/`map_result` family); and a **bare top-level function used as a value** (`map(xs, inc)`) self-hosts via an eta-expansion pass in `glassc` that rewrites it to `fn(a) -> inc(a)` before codegen.

**The reference interpreter and the self-hosted compiler now agree on the entire practical language** — there are no known self-hosting divergences. (One auxiliary note: the Python *Quartz* backend still wants an explicit lambda for a bare fn-as-value; it shares the reference's parser and is used to bootstrap `glassc`, but doesn't carry the eta pass — and nothing in the bootstrap or test suite exercises that case.)

The principle held throughout: every layer is a reference semantics plus a compiler, and they must agree bit-for-bit — checked by `dogfood.sh` and the bootstrap fixpoint on every change.

---

## See also

- [`../examples/selfhost/prism.glass`](../examples/selfhost/prism.glass) — the full implementation
- [`../examples/stage3/`](../examples/stage3/) — the Glass files prism.glass reads from disk
- [`../LANG.md`](../LANG.md) — formal specification with detailed audit
