# Quartz: the Glass to C back end

Quartz (`quartz.py`) compiles a Glass program to C and invokes the system C
compiler to produce a native binary. The binary prints the program's final value.
Its main job is the bootstrap: it compiles the self-hosted compiler
`examples/selfhost/glassc.glass` once into `native_glassc`, after which Glass
compiles itself with no Python in the loop (see [self-hosting](self-hosting.md)).

```bash
glass-build examples/quartz/fib.glass -o fib && ./fib   # 6765
glass-build file.glass -o out -v                        # also print the generated C
glass-build file.glass -o out --cc gcc                  # choose the C compiler
```

## Pipeline

1. Parse with the reference front end in `glass.py`, and expand `import "file"`
   (paths resolve relative to the source file).
2. Type-check with the `glass.py` checker. Quartz reads the checker's inferred
   types where its own lightweight typing cannot recover them.
3. Add the prelude functions the program uses, transitively. A user definition
   with the same name wins.
4. Emit C and compile it with `cc -O2 -Wno-int-conversion -lgc`. The build first
   tries the Clang-only `-fbracket-depth=100000` (the generated C nests deeply) and
   retries without it, so GCC works too.

## Design decisions

**Target: C.** Every platform has a C compiler, the output is readable and
debuggable, and closures, ADTs, and pattern matching have well-known C lowerings.
LLVM IR, WebAssembly, and a bytecode VM were considered; C needs the least new
infrastructure.

**Memory: Boehm GC.** Every allocation is `GC_malloc` (`#include <gc.h>`,
`GC_INIT()` in `main`, linked with `-lgc`). Generated code never frees. This makes
`libgc` a prerequisite of the native path (`brew install bdw-gc` or
`apt-get install libgc-dev`).

**Value representation.**

| Glass | C |
|---|---|
| `Int` | `int64_t` |
| `Bool` | `bool` |
| `String` | `const char*` (NUL-terminated, GC-allocated) |
| ADT, record, tuple, list, closure | `q_value_t*`: `{ int tag; int num_fields; int64_t fields[]; }` |

Every field is an `int64_t`-wide slot; pointers are stored through `intptr_t`
casts, which is why the build passes `-Wno-int-conversion`. Constructor and record
tags are small integers assigned at compile time, and `match` compiles to tag
tests plus field projections. A list is a cons chain (`Nil` has 0 fields, `Cons`
has 2), dispatched on `num_fields`. A closure stores the lifted function pointer
in `fields[0]` and its captured values after it; lambdas are lifted to static C
functions, with captures found by free-variable analysis.

**Generics: type erasure.** A generic function compiles to one C function. Type
variables become `int64_t`, and each call site casts arguments in and the result
out. There is no monomorphization.

**Integers.** Arithmetic uses C's operators on `int64_t`, so `/` and `%` truncate
toward zero. The reference interpreter uses the same 64-bit semantics (`+ - *`
wrap at 64 bits, `/ %` truncate toward zero), so the two agree. `quartz.py` does
not pass `-fwrapv`, so a program that overflows relies on the C compiler's
handling of signed overflow.

**Refinements: runtime checks.** Refinements are stripped from the C type and
enforced by emitted guards: on each refined parameter at function entry, on a
refined `let`, and on a refined return type. A failed guard prints
`refinement violated: <name> fails predicate (<pred>)` and exits with status 1,
matching the interpreter's message. Static discharge (constant folding,
alpha-equivalence, implication) lives in the `glass.py` checker, which lets the
interpreter skip a call-site check it has proven; Quartz's callee-side guards are
always emitted.

**Effects: erased at codegen.** An effect row such as `!{IO, File}` is a
type-level annotation with no runtime representation. An effectful function
lowers exactly like a pure one; the effectful builtins (`print`, `read_file`, and
the rest) emit the C that performs the effect.

## Scope

Quartz shares the reference parser, so it accepts the reference surface language,
but it compiles only what it has lowerings for; anything else raises a compile-time
error (for example `Quartz does not support type: ...`). It does not
carry `glassc`'s eta-expansion pass, so a bare top-level function used as a value
(`map(xs, inc)`) needs an explicit lambda. Nothing in the bootstrap uses that form.
The small programs in [`examples/quartz/`](../../examples/quartz/) show the back end
on its own.
