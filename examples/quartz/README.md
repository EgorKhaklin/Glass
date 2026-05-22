# Quartz examples (v3.5)

These programs demonstrate the v3.5 Quartz subset: primitives,
arithmetic and comparisons, if/else, let bindings, top-level functions,
string concatenation, ADTs and pattern matching, records and field
access, generic ADTs and records, **generic functions (v3.5)**.
Compile each with `glass-build`:

```
$ glass-build examples/quartz/hello.glass     -o hello   && ./hello
hello from native Glass

$ glass-build examples/quartz/fib.glass       -o fib     && ./fib
6765

$ glass-build examples/quartz/tree.glass      -o tree    && ./tree
3

$ glass-build examples/quartz/geometry.glass  -o geo     && ./geo
2073600

$ glass-build examples/quartz/lookup.glass    -o lookup  && ./lookup
78

$ glass-build examples/quartz/generic.glass   -o generic && ./generic
117
```

Add `-v` to see the generated C source. Use `--cc gcc` (or `--cc clang`)
to choose a different C compiler.

## What's NEW in v3.5

- **Generic functions**: `fn id<T>(x: T) : T = x` — compiles to one C
  function via type erasure. Each call site computes the substitution
  and casts args/result around the int64_t boundary.
- **Same generic fn, multiple instantiations**: `id(42)`, `id("hello")`,
  `id(Some(7))` all call the same C function with different casts.
- **Generic-calling-generic**: `fn through<A>(x: A) : A = id(x)` works
  via the same uniform int64_t representation.

## What's STILL NOT supported

**Closures** (lambdas with captured variables), lists, tuples, record
update syntax, field renaming in patterns, effects beyond pure,
explicit print(). The Glass concrete + generic language subset is
otherwise fully covered. See `docs/quartz.md` for the v3.x roadmap.

## What's next

Stage 5: port Quartz itself to Glass (`quartz.py` → `prism.glass`), so
prism can self-compile via Quartz to native binaries. After that,
performance and platforms (WASM target, runtime refinement checks,
modules, FFI).
