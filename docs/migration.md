# Stage 4 — the path off Python

This document is the honest assessment of where Glass stands on the migration from `glass.py` (the Python host) to a Python-free implementation. It exists because the question keeps coming up: *"how far are we from fully migrating from py?"*

The answer has three numbers: **structurally close, computationally distant, and architecturally tractable**.

---

## The staging

| Stage | Description | Status |
|-------|-------------|--------|
| 1 | Interpreter SHAPE exists in Glass | ✓ (v0.5) |
| 2 | Real working pipeline (lex/parse/check/eval) in Glass | ✓ (v0.9.5) |
| 3 | Interpret arbitrary Glass files from disk | ✓ **v1.0** |
| 4 | **Meta-circular: a Glass interpreter running inside prism.glass** | **✓ v1.5** (proved on `tinylang.glass`) |
| 4.5 | prism.glass interpreting prism.glass (the fixed point) | possible but slow |
| 5 | Replace `glass.py` entirely | future — needs Quartz |

---

## What v1.5 proves

```
$ glass examples/selfhost/prism.glass
examples/stage3/tiny.glass     ==> 60 : Int
examples/stage3/poly.glass     ==> 78 : Int
examples/stage3/tinylang.glass ==> VInt(17) : Value
```

That last line is the v1.5 achievement. `tinylang.glass` is itself a Glass interpreter for a tiny expression language. prism.glass read it from disk, compiled it through its own pipeline, and ran it — producing the `VInt(17)` that tinylang's eval function returns. Three levels of interpretation deep, in a single invocation. **The meta-circular capability is structurally present.**

`tinylang.glass` is small (~60 lines) so the demo finishes in a few seconds. The same chain on prism.glass itself (~4,000 lines) would work in principle — same evaluator, same primitives — but would take impractically long with the current tree-walking implementation. That's the perf wall.

---

## What's actually missing for full migration

### Feature gap (prism.glass missing host features)

prism.glass implements every structural piece of the language — types, ADTs, generics, effects, patterns, closures, mutual recursion, the full compile pipeline. The features it doesn't have are extensions that the *host's own source* would also need:

| Missing in prism.glass | Used by prism.glass's own source? | Est. lines to add |
|------------------------|-----------------------------------|-------------------|
| Refinement types (TyRefine + parsing + static discharge) | No | ~800 |
| Records (named-field types) | No | ~200 |
| Builtins: `map`, `filter`, `fold`, `random_int`, etc. | No (user-implementable) | ~300 |
| **Total feature gap** | | **~1,300 lines of Glass** |

**Critical observation:** prism.glass's own source uses only the features prism.glass implements. The 1,300 lines aren't blocking Stage 4/4.5 — they're blocking a *different* migration goal, which is "rewrite glass.py's host responsibilities in Glass."

For Stage 4.5 (true self-interp), the feature gap is **zero**. For Stage 5 (no host), the gap is ~1,300 lines plus the performance work.

### Performance gap (the real blocker)

```
host runs prism.glass:       ~7s
host runs prism.glass + 3 read_file/compile demos: ~7s
prism.glass running tinylang.glass on disk: included in the 7s
```

The host (glass.py) interprets prism.glass at roughly 100× slowdown vs hand-written Python. If prism.glass interprets *another* Glass program, that's another 100× factor. Stacked:

```
glass.py → prism.glass → arbitrary Glass program: 100 × 100 = 10,000× slowdown
```

For tinylang.glass (~10 evaluator calls), 10,000× of a few microseconds is still seconds — tractable. For prism.glass interpreting itself parsing+typing+evaluating something nontrivial, the constant is multiplied by the work prism.glass does on its own source (~millions of operations). The wall clock blows up.

**The performance work needed for practical Stage 4.5:**

| Optimization | Estimated speedup | Difficulty |
|--------------|-------------------|------------|
| Switch env from `{**dict}` to a parent-chain frame | 5–10× | medium |
| Cache lookups for builtins/ctors (hot constants) | 2× | low |
| Avoid re-validating types in pass 2 (cache pass 1 results) | 1.5× | low |
| Compile pattern matches to decision trees | 3–5× | medium |
| Tail-call elimination for direct recursion | 2× | low |
| Memoize sibling env construction in `VMutRecClos` | 5–10× | medium |
| **Combined target** | **100–500×** | a few weeks of work |

A 100× speedup brings prism-of-prism on the 7s benchmark down to ~700s (12 minutes). Tolerable for a one-time bootstrap demo. A 500× speedup brings it to ~14s. Practical.

### The full migration (Stage 5)

Stage 5 means glass.py exists only as a tiny bootloader, or doesn't exist at all. To reach it:

1. **Close the feature gap** (~1,300 lines of Glass added to prism.glass).
2. **Move host responsibilities into Glass**: the CLI entry point, the REPL (when it exists), the test runner. ~500 lines of Glass.
3. **Performance work** to make the resulting prism.glass practical to run.
4. **A bootloader** — either:
   - A "Quartz" native compiler that emits a binary from prism.glass, or
   - A `bootstrap.py` of ~200 lines (a minimal interpreter shell that just runs prism.glass), or
   - A pre-compiled bytecode form of prism.glass that ships with the repo.

Option 4 has three sub-tracks, and the choice depends on what we want the steady state to look like. The cleanest is probably Quartz: a one-time compilation pass that produces a self-hosting binary, after which `glass.py` is obsolete.

---

## Where we are today (v1.5)

**Quantified migration distance:**

- Structural completeness of prism.glass relative to "what an interpreter needs": **~100%**.
- Feature parity with glass.py: **~80%** (equality operators, polymorphic `++`, List/Option pre-declared; refinements, records, Pair/Result, remaining builtins still missing).
- Stage 4 capability proven: **yes** — on tractable examples (tinylang.glass, tinycalc.glass).
- Stage 4.5 (prism interprets prism): **possible, slow** — ~hours for full self-interp.
- Stage 5 (no glass.py): **~6 months of dedicated work** — feature gap + perf + Quartz.

**The cleanest answer to "how far from migrating off py":** we're past the structural midpoint. Everything that would *require* Python is now optional. What remains is engineering — closing the feature gap and making the interpreter fast enough to be self-sustaining. The architecture is done. The implementation is the long tail.

---

## The compounding move

Each release closes a piece of the migration:

| Release | Migration win |
|---------|---------------|
| v1.0    | prism.glass interprets `.glass` files from disk (Stage 3) |
| v1.5    | prism.glass interprets a Glass interpreter from disk (Stage 4) |
| v1.6    | substring + string_index_of + Option pre-declared in prism.glass |
| v1.7    | Interpreter performance pass — 18% wall-clock on prism.glass |
| v1.8    | `==`/`!=` operators, polymorphic `++` (string + list), midlang.glass |
| v1.9    | Interactive REPL — multi-line, `:`-commands, history, error recovery |
| **v2.0**| **Maturity release** — regex engine showcase, stable surface |
| **v2.1**| **Browser playground** — Pyodide + `playground.html`, zero-install try-it |
| **v2.2**| **JSON parser library** — real Glass code, recursive descent + ADTs |
| **v2.3**  | **AGENT.md** — single-source-of-truth instruction file for agents + contributors |
| **v2.3.1**| **JSON parser runs through prism.glass** — lexer escapes + `int_to_string` alias; Stage 4 chain = 7 programs |
| **v2.4**| **`let*` syntactic sugar for Result threading** — both runtimes; JSON parser refactored to demonstrate |
| **v2.5**| **`let?` syntactic sugar for Option threading** — symmetric companion to `let*`; both runtimes |
| **v2.6**| **Config-file parser library** — `let*`+`let?` paying off in real Glass code; Stage 4 chain = 8 programs |
| **v2.7**| **Pattern destructuring in plain `let`** — completes the v2.4-v2.5-v2.7 ergonomic trio |
| **v2.8**| **Markdown-to-HTML library** — fourth substantive Glass library; Stage 4 chain = 9 programs |
| **v2.9**| **Generic fn declarations in prism** — surfaced by Stage 4.5 attempt; records-alignment confirmed already complete |
| **v2.11**| **Parameterized record literal inference in prism** — `Box<A>` literals now type-check correctly; *v2.10 skipped per version contract* |
| **v2.12**| **Refinements chunk 1 in prism** — parsing + constant-fold discharge of `T where (pred)` |
| **v2.13**| **Refinements chunk 2a in prism** — alpha-equivalence discharge for threaded refinements |
| **v2.14**| **Refinements chunk 3 in prism** — implication discharge via set-inclusion on integer intervals |
| **v2.15**| **Stage 4.5 — prism evaluates a 320-line subset of its own source.** Self-host milestone. |
| **v2.16**| **Quartz design document** — `docs/quartz.md` captures the four blocking decisions for v3.0 |
| **v3.0**| **Quartz first prototype** — `glass-build` compiles a v3.0 subset of Glass to native C, then to a binary. End-to-end native compilation works. |
| **v3.1**| **Quartz: functions** — top-level fn declarations, recursion + mutual recursion, string concat `++`, C keyword mangling |
| **v3.2**| **Quartz: ADTs + pattern matching** — sum types lower to tagged unions, `match` to if/else chains over tags |
| **v3.3**| **Quartz: records** — record types via q_value_t reuse, field access, record patterns |
| **v3.4**| **Quartz: generic ADTs + generic records** — Option/Result/Pair from prelude work; user-defined generic types work |
| **v3.5**| **Quartz: generic functions** — type erasure with intptr_t bridging; last big language hole closed |
| **v3.6**| **Stage 5 piece** — `quartz_min.glass` is the first Quartz module written in Glass; prism interprets it, output is C source code, cc produces native binary |
| **v3.7**| **Quartz-in-Glass extends** — adds EVar, ELet, ECall + Program/FnDecl ADTs; recursive `fact(5)` compiles through prism → C → native |
| **v3.8**| **Quartz-in-Glass: ADTs + pattern matching** — TypeDecl/Variant/Pattern/MatchArm; `match Some(42) { Some(n) => n; None => 0 }` compiles through prism → C → native |
| **v3.9**| **Quartz-in-Glass: records + field access** — RecordDecl/ERecord/EField; `Point{x:3,y:4}.x + .y` compiles through prism → C → native; intptr_t bridge eliminates compile warnings |
| **v3.11**| **Quartz-in-Glass: strings** — EStr/EConcat + Program result type (CInt/CString); `"hello, " ++ "world"` compiles to native binary; v3.10 skipped per version contract |
| **v3.12**| **Quartz-in-Glass: multi-type fields + generics (via boundary discipline)** — one-line codegen fix unlocks String in ADT/record fields AND type-erased generic fns. 12 demos, all pass. Coverage parity with quartz.py reached. |
| **v3.13**| **Glass drives cc** — `write_file` + `run_command` builtins; `!{Process}` effect; `examples/selfhost/build_pipeline.glass` runs Quartz-in-Glass → C → cc → binary all from one Glass file |
| **v3.14**| **Source-to-native, all in Glass** — `quartz_parser.glass` lexes + parses arithmetic-subset Glass source → Quartz AST → C → cc → native binary; four end-to-end pipeline cases verified |
| **v3.15**| **Parser extends: identifiers + let** — TIdent + TLet/TIn tokens; EVar + ELet AST; `let x = 5 in x + 10` parses to native; statement-expression codegen for nested lets |
| **v3.16**| **Parser extends: fn decls, ECall, if, comparison** — TFn/TIf/TThen/TElse/TLt/TGt/TComma tokens; Args/Params/FnDecls Cons-style ADTs; recursive `fact(5)` parses Glass source → native binary → 120 |
| **v3.17**| **Parser extends: ADTs + match** — `type`/`match` keywords; TFatArrow/TLBrace/TRBrace/TSemi/TPipe tokens; uppercase identifiers; Pattern/Variant/TypeDecl ADTs; `match Some(42) { Some(n) => n; None => 0 }` parses Glass source → native → 42 |
| **v3.18**| **Parser extends: records + field access** — TDot, TColon tokens; FieldDef/RecordDecl/Field/Fields ADTs; ERecord + EField in Expr; postfix precedence layer; records auto-generate single-variant TypeDecls and reuse q_value_t runtime; `Point { x: 3, y: 4 }.x` parses Glass source → native → 3 |
| **v3.19**| **Parser extends: string literals + concatenation** — TStr, TConcat tokens; EStr + EConcat in Expr; lex_string for `"..."`; q_str_concat runtime helper emitted selectively; result-type detection picks printf format (`%s` vs `%lld`); `"hello" ++ " " ++ "world"` parses Glass source → native → `hello world` |
| **v3.20**| **Parser reaches feature parity with quartz_min** — generic type parameters `<T>` (parsed, erased); multi-type record fields (FieldDef tracks type name); fn return-type tracking (fn_returns_string + extended is_string_expr); `fn greet(n) = "hi, " ++ n  greet("Glass")` → `hi, Glass`; `Person { name: "Alice", age: 30 }.name` → `Alice`; 26 source-to-native sub-cases on every regression run |
| **v4.0** | **Stage 5 endpoint** — `examples/selfhost/selfcompile.glass` drives end-to-end self-compile via subprocess (file-mode dispatch in `quartz_parser.glass`, self-cleanup); 7 demo programs round-trip Glass source → AST → C → cc → binary → captured stdout, all from one user-facing Glass script; full architecture proven |
| v4.x (future) | String escapes, fn-chain return type, nested patterns, prism builtin gap |
| v5.0 (future) | True prism-interpreted self-compile (prism gains File/Process effects) |
| v4.0 (planned) | Full Stage 5: prism self-compiles via Quartz |
| v2.14 (planned) | Refinements chunk 2b — implication discharge (`n > 5` ⟹ `n > 0`) |
| v2.x (planned) | prism.glass running prism.glass — Stage 4.5, slow but real |
| **v3.0**| **Quartz**: native compile of prism.glass, glass.py becomes optional |
| v1.x (planned) | prism.glass running prism.glass — Stage 4.5, slow but real |
| v2.0    | Quartz: native compile of prism.glass, glass.py becomes optional |

Each step is a meaningful end-to-end demo, not just a feature ship. The migration is the trajectory of the demos as much as it is the code.

---

*v1.5 — Meta-circular evaluation, structural completeness.*
