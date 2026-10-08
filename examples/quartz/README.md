# Quartz examples

Small programs compiled by Quartz (`quartz.py`), the Python back end that turns
Glass into C. They cover primitives, arithmetic and comparisons, `if`, `let`,
top-level functions, string concatenation, ADTs and pattern matching, records and
field access, generic ADTs and records, and generic functions. Quartz itself
compiles much more: its main job is building the self-hosted compiler
`glassc.glass` once (see [self-hosting](../../docs/compiler/self-hosting.md)).

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

Add `-v` to print the generated C. Use `--cc gcc` (or `--cc clang`) to choose the
C compiler. The native build needs `libgc` (Boehm GC).

`generic.glass` shows type erasure: each generic function (`id<T>`,
`unwrap_or<T>`) compiles to one C function, and each call site casts its
arguments and result around the `int64_t` boundary. See
[`docs/compiler/quartz.md`](../../docs/compiler/quartz.md) for the value
representation and design.
