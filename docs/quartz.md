# Quartz: native compilation for Glass (v3.0 design)

This document captures the blocking design decisions for Quartz — Glass's native compiler back-end and the headline of v3.0. As of v2.15, the migration phase is complete: every language feature prism needs to interpret itself is in place, and Stage 4.5 demonstrates prism evaluating a 320-line subset of its own source. The remaining work is engineering a runtime that doesn't depend on Python interpretation.

This is a design doc, not an implementation plan. The goal is to surface the decisions that have to be made before code starts.

---

## Why Quartz exists

prism (the Glass-in-Glass interpreter) currently runs on top of glass.py (the Python reference implementation). Interpretation is multiplicative: every Glass operation goes through ~10x Python overhead in the host, then another ~10x in prism. For 5300 lines of prism source running through itself, the C stack overflows after ~28 seconds before completing.

Stage 4.5 (v2.15) proved the self-host works in principle. **Stage 5** — prism running its full self — needs a runtime that doesn't add interpretation overhead. That's Quartz.

Quartz is a code generator: takes prism's typed AST and emits native code that runs without interpretation. The Glass language doesn't change; what changes is what runs it.

---

## Decision 1: Compile target

The four serious candidates:

### LLVM IR

**Pros:** mature, multi-platform, decades of optimization. Direct path to native code on every platform Glass cares about (Linux, macOS, Windows, ARM, x86_64, WASM via wasm32-unknown-unknown).

**Cons:** the LLVM tooling is a heavy dependency. Building an LLVM IR generator in Glass (or having Glass emit `.ll` files and shell out) adds complexity. LLVM's C++ ABI doesn't compose well with a pure-functional language without an intermediate layer.

**Bootstrap cost:** the Glass-side code generator targets `.ll` text. Then `llc` / `clang` produces native binaries. Adds an external toolchain dependency to the build path.

### C

**Pros:** universal. Every platform has a C compiler. The output is human-readable and debuggable. Closures, ADTs, and pattern matching all have well-known C lowerings. Garbage collection via the Boehm GC (libgc) gives memory management for free.

**Cons:** generated C is ugly — closures become structs with function pointers, tail calls require Manual Hacks (computed goto, trampolines, or just hope the C compiler does TCO). Generic functions either monomorphize (code bloat) or use type erasure (runtime overhead).

**Bootstrap cost:** modest. The Glass-side code generator emits `.c` files. `gcc` or `clang` produces binaries. Boehm GC adds one library dependency.

### WebAssembly

**Pros:** modern, well-specified, runs in browsers AND server-side via Wasmtime/Wasmer. The Glass playground (v2.1) already runs in browser via Pyodide; emitting WASM directly would be vastly faster than that path. WASM's structured control flow maps cleanly to functional code.

**Cons:** less mature than LLVM/C for native execution. WASM-GC (the proposal that adds garbage collection) is still being standardized; without it, Glass would need to ship its own GC (additional ~2000 lines of work). Tail calls are spec'd but inconsistently supported.

**Bootstrap cost:** medium. Need a WASM text-format (`.wat`) generator OR direct binary emission. Then `wasmtime` / browser to execute.

### Custom bytecode + interpreter

**Pros:** full control. Can be tuned exactly for Glass semantics. No external dependencies. A bytecode VM written in C is ~1000 lines and would be far faster than prism-on-prism (zero Python overhead). Reasonable performance ceiling (maybe 2-5x slower than native).

**Cons:** doesn't reach "native" performance. Still an interpreter, just a fast one. Doesn't unlock the killer features (browser-side execution, ahead-of-time compilation, FFI to existing native code).

**Bootstrap cost:** lowest. The VM is one C file plus a Glass-side bytecode emitter.

### Recommendation: **C, with WASM as a v3.x follow-on**

C maximizes platform reach with minimum new infrastructure. Generated C is debuggable, the toolchain is universal, and Boehm GC eliminates memory management as a v3.0 problem. WASM (with Glass shipping its own minimal GC or waiting for WASM-GC) is a natural v3.1 — same code generator, different lowering rules. LLVM IR can come later if a specific performance need arises.

This decision is the most important and should be reviewed when v3.0 work actually starts. If WASM-GC ships meaningfully before then, WASM may become the better first target.

---

## Decision 2: IR shape

Quartz needs an intermediate representation between prism's AST and the target. The IR's job: be lower-level than the AST (decisions like closure conversion already made) but higher-level than the target (so the same IR can lower to C, WASM, or LLVM IR without backend-specific work).

The candidates:

### Continuation-passing style (CPS)

Every function takes an explicit continuation. Makes control flow uniform — there's only function calls, no returns. Well-suited for languages with first-class continuations (Glass doesn't have those, so this is overkill).

### A-normal form (ANF)

Every intermediate computation gets a name. Sub-expressions are either values or named variables. Maps cleanly to SSA-style backends.

### Direct-style with closure conversion

Functions remain functions (with returns). Closures get explicit environment parameters. Pattern matching is lowered to switch statements with explicit field projections.

### Recommendation: **direct-style ANF with explicit closure conversion**

ANF for the local form (every computation named, no nested side-effect-producing expressions in arguments) — this maps cleanly to both C and WASM. Direct-style for control flow (functions return values; no CPS contortions). Closure conversion makes the environment explicit before the backend sees it, eliminating one backend-specific concern.

The IR's specific shape:

```
Decl   = FnDecl(name, [(param, ty)...], body, return_ty)
Block  = [Stmt...] + Terminator
Stmt   = Let(name, Expr) | Effect(EffOp)
Expr   = Atom | Apply(fn_atom, [atom...]) | AllocClosure(fn, [captured...])
       | AllocRec(name, [(field, atom)...]) | Project(atom, field)
       | Ctor(name, [atom...]) | Match(atom, arms)
Atom   = Const(int|bool|string) | Var(name) | Global(name)
Terminator = Return(atom) | Jump(block_id) | If(atom, then_block, else_block)
```

Three passes from prism's AST to this IR:
1. **Closure conversion** — every lambda becomes (fn_decl, captured_env). Calls become AllocClosure + Apply.
2. **ANF transformation** — every non-atomic sub-expression gets a Let-binding name.
3. **Pattern lowering** — match expressions become if-chains over constructor tags + projections.

---

## Decision 3: Runtime model

The runtime is the small C library (or WASM module) that the generated code links against. It handles:

### Garbage collection

**Mark-sweep with Boehm GC.** libgc is mature, well-tested, conservative, and requires zero changes to generated code (allocations just call `GC_malloc`). It's slightly slower than generational GC but far less work to integrate. v3.x can add a custom precise GC if the performance gap matters.

### Closure representation

A closure is `struct { fn_ptr, env_size, env[]... }`. Apply takes the closure and an argument; reads the fn_ptr; passes (env, arg) to the C function. No need for type tags because Glass is statically typed — the generated code knows what each closure expects.

### ADT representation

A constructor value is `struct { tag, field_count, fields[]... }`. Tags are interned strings or small ints (decided at compile time). Pattern matching does `tag == X ? read_fields : try_next_arm`.

### Records

Structurally identical to ADTs but tag is the record name. Field access is positional after compile-time field-name → index resolution.

### Primitives

`Int` is `int64_t`, `Bool` is `bool`, `String` is `struct { len, ptr }`. No boxing — these are stack values until they enter an ADT or get captured by a closure.

### Effects

For v3.0, effects are a STATIC annotation only — they affect type-checking but not codegen. `!{IO}` and `!{}` produce identical native code. v3.1 can revisit if effects need handler-based runtime support.

### Refinement checks

For v3.0, refinements are **statically discharged or silently deferred**. The three discharge strategies (const-fold, alpha-equivalence, implication — v2.12-2.14) all happen at compile time. Predicates that don't discharge statically simply don't generate runtime checks. This matches prism's current behavior. v3.1 can add runtime refinement insertion as a separate feature.

---

## Decision 4: Bootstrap path

Quartz needs to come into existence. The question is: how?

### Path A: Write Quartz in Python (in glass.py)

The natural path. glass.py already has the typed AST; add a `compile_to_c(decls)` function that walks the AST and emits C. Build the runtime separately. Glue them via a `glass-build` CLI.

**Pros:** fastest path to a working compiler. Glass continues to be developable in Python; Quartz becomes a Python module within glass.py.

**Cons:** the compiler isn't written in Glass. The self-host story stays at "prism interprets prism." Quartz doesn't extend it.

### Path B: Write Quartz in Glass (in prism.glass)

Add `compile_to_c(prog)` as a Glass function inside prism. Each new Glass program can produce native code by running through prism's now-extended pipeline.

**Pros:** the self-host expands. Once Quartz works, prism can compile programs to native — including itself.

**Cons:** vastly slower to develop. Every Quartz change involves running prism (interpreter overhead). Debugging is harder.

### Path C: Both, in stages

**v3.0:** write Quartz in Python (glass.py). Get it working. Ship a real native compiler.
**v3.1:** port Quartz to Glass (prism.glass). Now prism can self-compile. Stage 5 unlocked.

### Recommendation: **Path C.**

v3.0 is about getting native compilation working at all. Python is the right host for that work — fast iteration, easy debugging, no double-interpretation. v3.1 ports the result to Glass and is when prism becomes self-hosting in the full sense.

---

## What v3.0 delivers

A `glass-build` CLI that takes a `.glass` source file and produces a native binary:

```
$ glass-build hello.glass -o hello
$ ./hello
Hello, Glass!
```

Internally:
1. Parse + type-check via the existing glass.py front-end
2. Lower to Quartz IR (closure-converted, ANF, pattern-lowered)
3. Emit C code linked against the Quartz runtime (libgc + Glass primitives)
4. Invoke `cc` to produce the binary

Expected scope: ~3000 lines of Python (compiler) + ~500 lines of C (runtime). Performance target: within 5x of hand-written C for arithmetic-heavy benchmarks; within 2x for I/O-bound code.

Stage 5 unlocked when prism.glass compiles via Quartz to native and runs prism.glass at usable speed.

---

## What v3.0 doesn't deliver

These are deliberately deferred:

- **Runtime refinement checks.** Static discharge only (which is what prism does now). Predicates that don't discharge at compile time defer silently. Refinement enforcement at runtime is v3.1+.
- **Effect handlers.** Effects remain annotations only. Handler-style effect implementation is v3.1+.
- **Custom GC.** Boehm GC suffices. Precise/generational GC is a v3.2+ exercise if performance demands.
- **WASM target.** v3.1 add-on once the C path is solid.
- **Multi-file projects.** A `.glass` file is a self-contained program in v3.0. Module systems are v3.2+.
- **FFI.** Calling out to C from Glass code (beyond the runtime's primitives) is v3.x.

---

## Open questions

- How does `print` work in Quartz? Probably via a built-in linked from the runtime.
- How are top-level let-bindings sequenced? (prism currently has the sequential-let bug documented in AGENT.md.)
- What's the exact lowering for `let*` / `let?` / pattern-let? They desugar to Match expressions in the AST — Quartz inherits that.
- Generic functions: monomorphize (clone the function for each used type) or boxed? v3.0 probably boxes everything (simpler code generator); v3.1 adds monomorphization for hot types.

These shouldn't block v3.0 work starting; they get resolved during implementation.

---

## Status

This document is the v2.16 deliverable. Quartz implementation begins in v3.0. No Quartz code exists yet.

The four design decisions above are the inputs to that work. If any of them changes (different compile target, different IR shape, etc.), this document should be updated before code is written that assumes the old answer.
