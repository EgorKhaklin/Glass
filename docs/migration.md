# Stage 4 — the path off Python

> 📜 **Historical record.** The migration is complete (see [self-hosting](self-hosting.md)). This file is kept for the story of how it got there.

This document is the honest assessment of where Glass stands on the migration from `glass.py` (the Python host) to a Python-free implementation. It exists because the question keeps coming up: *"how far are we from fully migrating from py?"*

> **✓ DONE (v4.76).** The migration is complete at the bootstrap level. A Glass-written Glass→C compiler (`examples/selfhost/glassc.glass`) is compiled to native **once** by `quartz.py` (Python), then **compiles itself** with no Python involved; the second-generation compiler compiles `prism.glass` byte-identically to the reference, and the two generations emit byte-identical C. Reproduce it with `bash examples/selfhost/bootstrap_fixpoint.sh`. The original framing below ("structurally close, computationally distant") described the *interpretation* path; the answer turned out to be **compilation** via Quartz — the perf wall is gone because the toolchain runs as native code.

---

## The staging

| Stage | Description | Status |
|-------|-------------|--------|
| 1 | Interpreter SHAPE exists in Glass | ✓ (v0.5) |
| 2 | Real working pipeline (lex/parse/check/eval) in Glass | ✓ (v0.9.5) |
| 3 | Interpret arbitrary Glass files from disk | ✓ **v1.0** |
| 4 | **Meta-circular: a Glass interpreter running inside prism.glass** | **✓ v1.5** (proved on `tinylang.glass`) |
| 4.5 | prism.glass interpreting prism.glass (the fixed point) | possible but slow |
| 5 | **Replace `glass.py`: a Glass-written compiler, bootstrapped to native, compiles Glass (incl. itself)** | **✓ v4.76 — self-hosting bootstrap fixpoint** |

The key insight that unlocked Stage 5: don't chase fast self-*interpretation* (the perf wall). **Compile** the toolchain to native via Quartz, one time, then run at C speed. `glass.py` now serves only as the one-time bootstrap compiler and a differential-testing oracle.

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

| Optimization | Estimated speedup | Difficulty | Status |
|---|---|---|---|
| Switch env from `{**dict}` to a parent-chain frame | 5–10× (original estimate) | medium | **tried v4.29, REVERTED** — see findings below |
| Cache lookups for builtins/ctors (hot constants) | 2× | low | not yet attempted |
| Avoid re-validating types in pass 2 (cache pass 1 results) | 1.5× | low | not yet attempted |
| Compile pattern matches to decision trees | 3–5× | medium | not yet attempted |
| Tail-call elimination for direct recursion | 2× | low | **✓ v4.28** — measured ~10% on prism, unbounded depth |
| Memoize sibling env construction in `VMutRecClos` | 5–10× | medium | not yet attempted (prism-side) |
| Inline `TyRefine` check in `apply_fn` param-bind loop | <1.5× | trivial | **✓ v4.29** — within noise on benchmarks; kept anyway |
| **Combined target** | **100–500×** (original) | a few weeks of work | revised below |

A 100× speedup brings prism-of-prism on the 7s benchmark down to ~700s (12 minutes). Tolerable for a one-time bootstrap demo. A 500× speedup brings it to ~14s. Practical.

### Calibrated findings from v4.28–v4.29

The "5–10× from parent-chain env frames" estimate was for an idealized implementation. In practice on CPython 3.12, **`collections.ChainMap` lost 78% to `dict.copy()`** on the tail-recursion benchmarks (v4.29 attempt — see CHANGELOG for full numbers). The reason: CPython's `dict.copy()` is C-implemented and extremely fast, while `ChainMap.__getitem__` walks a Python-level list of mappings on every lookup. For typical Glass workloads the lookup count vastly outweighs the construction count, so the trade-off goes the wrong way.

This doesn't kill the parent-chain idea — a hand-rolled C extension or a Cython implementation could win. But the cheap Python-stdlib version of "parent-chain frames" doesn't pay off, and the original 5–10× estimate was optimistic.

**Revised combined target:** the doc's 100–500× estimate assumed each optimization compounded cleanly. v4.28 + v4.29 measured ~10% total on prism (~14.8s → ~13.3s) from the items that landed. The bigger wins (decision-tree match, VMutRecClos memoization) are still untried, but the realistic upper bound for what's achievable in pure-Python on CPython is probably closer to **5–20× combined**, not 100–500×. The 100–500× target requires either:

- A genuinely different evaluator architecture (bytecode + register-based VM written in C/Cython), or
- Moving prism's hot path to a native back-end (Quartz Stage 5 — already in progress).

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
| **v4.1** | **String escape sequences in parser** — `lex_string` accumulator + `escape_char_for` decode `\n`, `\"`, `\\`; `c_escape` re-encodes for C output; `"line1\nline2"` parses → native binary that prints two lines; 10 selfcompile demos total; host quirk documented (`\t` not decoded — Glass tokenizer limitation) |
| **v4.2** | **Fn-chain return-type inference via fixed-point** — ResMap ADT (name → returns-String?); bounded N+1 iteration over `compute_pass`; `fn helper(n) = "..." ++ n  fn greet(n) = helper(n)` now correctly classifies `greet` as String-returning; chain length 3 verified; 12 selfcompile demos total |
| **v4.3** | **Nested PCtor sub-patterns + nullary ctor fix** — path-based pattern codegen (`compile_pattern_test`, `compile_pattern_bindings` take `path: String`); `match Some(Some(42)) { Some(Some(n)) => n + 100; _ => 0 }` → 142; `nest_disc` distinguishes `Some(None)` vs `Some(Some(_))`; bare uppercase ident → nullary ECall; 15 selfcompile demos total |
| **v4.4** | **Direct file read in selfcompile + newlines as whitespace** — `compile_path(label, path)` reads user `.glass` files via `read_file`; 5 new example programs in `examples/selfhost/programs/`; `is_space` extended to recognize `\n`; multi-line .glass files parse correctly; 20 selfcompile demos total (15 inline + 5 file-based) |
| **v4.5** | **Line comments + perf measurement** — `#` to end-of-line comments via `skip_to_newline` + `skip_ws` extension; `commented.glass` exercise; honest timing data published (selfcompile 21 demos: 3.61s; bottleneck is subprocess startup not compilation); v5.0 bootstrap planned (native-compile quartz_parser via quartz_min) |
| **v4.6** | **Unary minus + modulo** — `TPercent` token + `EMod` variant + `parse_term_rest` extension at `*` precedence; unary minus via `ESub(EInt(0), inner)` in `parse_atom`; Euclidean GCD `fn gcd(a, b) = if b < 1 then a else gcd(b, a % b)` now compiles; `gcd(252, 105) = 21`; 25 selfcompile demos total |
| **v4.7** | **Equality + logical operators** — `==`, `&&`, `||` via 3 new tokens + 3 new AST variants + standard C-like precedence layering (`parse_expr → parse_or → parse_and → parse_cmp → ...`); trial-division primality `fn is_prime(n) = ...` now compiles; `is_prime(97) = 1`; 31 selfcompile demos total |
| **v4.8** | **Inequality + block comments** — `!=` via `TNotEq` + `ENeq`; `/* ... */` block comments via `skip_to_block_end` + `/` branch in `skip_ws`; multi-line comment headers in `.glass` files; fizzbuzz counter `fn fizzbuzz_count(n, i, acc) = ...` combining all v4.x features; 35 selfcompile demos total |
| **v4.9** | **Two foot-guns closed** — `string_eq` / `string_neq` builtins emit `strcmp`-based C (was reference equality, broken); `is_c_reserved` + `mangle` prefix user names colliding with C keywords (`double`, `return`, etc.) with `g_`; applied at all 7 name-emission sites; `<string.h>` in C prelude; 40 selfcompile demos total |
| **v4.11** | **`char_at` builtin** — symbolic string primitive; `char_at("hello", 2) = 108`; vowel-counter `count_vowels_from("Programming Glass", 17, 0, 0) = 4`; surfaces `>=`/`<=` operator gap (workaround documented); 44 selfcompile demos total |
| **v4.12** | **`>=` / `<=` + `int_to_char`** — `TLtEq`/`TGtEq` tokens + `ELte`/`EGte` variants; `int_to_char(n)` returns single-char String via `q_int_to_char` runtime helper; Caesar cipher `shift_str("HELLO", 5, 0, 3) = "KHOOR"` compiles end-to-end; direction #1 (symbolic strings) foundational primitives complete; 49 selfcompile demos total |
| **v4.13** | **String stdlib** — `string_length(s)` via strlen wrapper; `string_to_upper(s)` / `string_to_lower(s)` via `q_str_to_upper` / `q_str_to_lower` runtime helpers (ASCII-aware, allocate fresh buffer); titlecase demo `titlecase("hELLO") = "Hello"`; vowel.glass cleaned up to use string_length; 55 selfcompile demos total |
| **v4.14** | **`substring` + `string_at`** — `substring(s, start, end)` via `q_substring` runtime helper (clamps negative start, end<start; fresh buffer); `string_at(s, i)` sugar for one-char slice; palindrome checker `is_palindrome("Racecar") = 1` compiles end-to-end via reverse-and-compare; symbolic-string vocabulary now complete; 60 selfcompile demos total |
| **v4.15** | **`string_index_of`** — returns Int (-1 sentinel for not-found, diverges from host's Option<Int> for pragmatism); uses libc strstr; email-domain extractor `email_domain("vanta@seton-hill.edu") = "seton-hill.edu"` compiles; **symbolic-string vocabulary now complete in compiled Glass**; 65 selfcompile demos total |
| **v4.16** | **Bitwise builtins** — `bit_and`, `bit_or`, `bit_xor`, `bit_not`, `bit_shl`, `bit_shr` as functions (not infix) to avoid `|`/`&` collisions with TPipe / `&&`; pack/unpack two-byte roundtrip compiles (`pack(171, 205) → unpack → 171,205`); direction #2 (numeric) advances; 73 selfcompile demos total |
| **v4.17** | **Hex literals** — `0xFF`, `0xcafe`, case-insensitive; new `hex_digit_value` + `lex_hex` helpers; tokenizer peeks for `0x`/`0X` prefix; bitpack rewritten with hex; surfaced host-Glass syntax limitation (`&&`/`||` not in host) — workaround with nested ifs documented; 78 selfcompile demos total |
| **v4.18** | **Division `/` + calculator demo** — TSlash token, EDiv variant, parser arm at parse_term precedence; calc.glass is a recursive-descent four-function calculator with proper precedence (`eval("2 + 3 * 4") = 14`, `eval("100 - 6 * 2") = 88`, left-associative `*` `/` `+` `-`); strongest end-to-end proof of v4.x toolkit; 83 selfcompile demos total |
| **v4.19** | **Typed parameters + param-type-aware inference** — Params ADT extended `PCons(name, type, rest)`; parse_params reads optional `: TypeName`; `is_string_expr` consults declared types via `param_is_string`; EIf checks BOTH branches now; the chronic v4.12 accumulator pattern + v4.13 `then s` workaround are gone; strict superset (untyped fns still work); titlecase.glass simplified; 88 selfcompile demos total |
| **v4.20** | **Calc with parens + djb2 hash** — pure demo expansion, zero compiler changes; calc.glass gains `(expr)` via mutual recursion (parse_atom → parse_expr); djb2.glass implements Bernstein's string hash via bit_shl + char_at + typed accumulator (`djb2("hello") = 210714636441`, bit-exact match with C reference); 90 selfcompile demos total |
| v4.x (future) | FNV-1a, variable bindings, binary literals |
| **v5.0** (future) | **Bootstrap quartz_parser to native; extend quartz_min with File+Process effects; 50–100× selfcompile speedup** |
| v4.0 (planned) | Full Stage 5: prism self-compiles via Quartz |
| v2.14 (planned) | Refinements chunk 2b — implication discharge (`n > 5` ⟹ `n > 0`) |
| v2.x (planned) | prism.glass running prism.glass — Stage 4.5, slow but real |
| **v3.0**| **Quartz**: native compile of prism.glass, glass.py becomes optional |
| v1.x (planned) | prism.glass running prism.glass — Stage 4.5, slow but real |
| v2.0    | Quartz: native compile of prism.glass, glass.py becomes optional |

Each step is a meaningful end-to-end demo, not just a feature ship. The migration is the trajectory of the demos as much as it is the code.

---

*v1.5 — Meta-circular evaluation, structural completeness.*
