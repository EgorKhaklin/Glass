# Changelog

All notable changes to Glass.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/).
This project follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] — 2026-05-21

**Stage 3 self-host achieved.** prism.glass reads `.glass` files from disk and interprets them end-to-end.

### Added
- **`read_file` builtin** with signature `String -> Result<String, String> !{File}`. Returns file contents wrapped in `Ok`, or an error message in `Err`. The `!{File}` effect propagates through every caller.
- **Literal patterns** in `match` arms: `PInt(Int)`, `PBool(Bool)`, `PStr(String)`. Literals can appear at the top level of an arm or nested inside constructor patterns: `match Filled(0) { Filled(0) => "zero cell"; Filled(_) => "nonzero"; Empty => "empty" }`.
- **Function types `(A) -> B` in signatures.** Required for higher-order functions like `bind_result(r, k: (Value) -> Result<Value, String>)`. Effect annotations `!{...}` may appear on the arrow.
- **The let-vs-let-in disambiguation** in `parse_main_expr`. After parsing a top-level `let name = value`, peek for `TIn` — if present, it's an inline let-in expression; if absent, it's a top-level statement.
- **The Stage-3 capstone demo** in `examples/selfhost/prism.glass`: loads `examples/stage3/tiny.glass` and `examples/stage3/poly.glass`, compiles each through prism.glass's own pipeline, prints the typed result.
- Token-named error messages in `parse_atom` ("unexpected 'in' in atom" rather than the generic message).
- **Organized GitHub-ready structure**: assets, docs, examples organized into basic/features/selfhost/stage3, tests directory, CHANGELOG, LICENSE.

### Changed
- prism.glass now reads from `examples/stage3/*` (relative paths) rather than `/tmp/*`.
- Project layout reorganized for GitHub: examples by category, dedicated docs and tests directories.

### Self-host counts
- `examples/selfhost/prism.glass`: **3,984 lines**
- Total Glass-in-Glass: **6,462 lines** — 274% of host

---

## [0.9.7] — internal release

### Added
- Function types `(A) -> B` in `parse_type` (split into `parse_type` and `parse_type_atom`, with optional effect on the arrow).
- The HM-interpreter demo inside prism.glass — `(fn(x) -> x*x+1)(5) ==> Ok(VInt(26))`.

---

## [0.9.6] — internal release

### Added
- `print` builtin with `!{IO}` effect.
- `TBang` token + `parse_optional_effect` parsing `!{Label1, Label2}` after return types.
- Effect annotations on the final arrow of curried function types.

---

## [0.9.5]

### Added
- Top-level `fn` declarations with mutual recursion via `VMutRecClos(name, body_expr, all_decls, outer_env)`.
- `#` line comments.
- Top-level `let _ = ...` statements that desugar to nested ELets.
- Tuple types in signatures.
- Multi-arg call syntax: `f(a, b, c)` desugars to `f(a)(b)(c)`.
- Optional `: Type` annotation in `let` bindings.

### Fixed
- `build_mutrec_env` no longer narrows `decls` through recursion; mutual recursion now works correctly.

---

## [0.9.4]

### Added
- First-class `String` type (`TyStr`, `VStr`, `EStr`).
- `++` concatenation operator.
- String inspection builtins: `string_length`, `char_at`, `int_to_str`, `string_eq`.
- `VBuiltin(name, arity, accumulated_args)` for currying host primitives.

---

## [0.9.0 – 0.9.3] — internal releases

Records with named fields, generic ADTs (`TyAdt` with type params), pattern matching with exhaustiveness checking, recursion via `let rec`, subtraction/multiplication/comparisons, tuples, list literals `[...]` with spread `[h, ...t]`.

---

## [0.0 – 0.8] — early development

Initial language design: pure functional core, Hindley-Milner type inference, ADTs, pattern matching, immutability, effect rows. See `LANG.md` for the full philosophical foundation.

---

[1.0.0]: https://github.com/EgorKhaklin/Glass/releases/tag/v1.0.0
