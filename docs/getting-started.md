# Getting started

This document walks you from a fresh clone to a working Glass program in five minutes.

## Install

Glass requires Python 3.10+.

```bash
git clone https://github.com/<you>/glass.git
cd glass
pip install -e .
```

`pip install -e .` installs Glass in editable mode and creates a `glass` command in your PATH.

Verify the install:

```bash
glass --version
# Glass 5.49.0
```

### Native compiler (optional)

Everything above — the interpreter, every bundled example, `glass prove`, the
REPL — needs only Python. The **self-hosted native compiler**
(`examples/selfhost/run_native.sh`, `bootstrap_fixpoint.sh`) additionally needs a
C compiler and the Boehm garbage collector, because it emits C and links `libgc`:

```bash
# macOS
brew install bdw-gc

# Linux (Debian/Ubuntu)
sudo apt-get install libgc-dev
```

Clang and GCC both work — the build retries without the Clang-only
`-fbracket-depth` flag when `cc` is GCC. You only need this for the native path;
the interpreter has no dependency beyond Python.

## Your first program

Create `hello.glass`:

```glass
fn greet(name: String) : String =
  "Hello, " ++ name ++ "!"

greet("Glass")
```

Run it:

```bash
$ glass hello.glass
"Hello, Glass!" : String
```

The output shows both the value (`"Hello, Glass!"`) and its inferred type (`String`).

## Running the bundled examples

```bash
glass examples/basic/hello.glass            # The classic
glass examples/basic/fib.glass              # Fibonacci with pattern matching
glass examples/basic/list_ops.glass         # map, filter, fold
glass examples/basic/option_result.glass    # First-class uncertainty
glass examples/basic/records.glass          # Records with named fields

glass examples/features/generics.glass      # Generic types and functions
glass examples/features/effects.glass       # The effect system in action
glass examples/features/queries.glass       # Pane-style queries (preview)
glass examples/features/crypto.glass        # Type-level guarantees for crypto
glass examples/features/ai.glass            # !{Inference} effect for model calls
glass examples/features/infer.glass         # Type inference walkthrough

glass examples/selfhost/prism.glass         # Glass-in-Glass (the self-host)
```

## Prove a function (zero-knowledge)

Glass can compile a function into an arithmetic circuit and emit a **succinct,
zero-knowledge proof of its result** — names passed on the command line are
*private inputs* that stay in the witness:

```bash
glass prove examples/prove/hello_prove.glass inp=9
#   result:  86
#   proof:   ACCEPT  (succinct, zero-knowledge)
```

The proof reveals only the result (`86`), not `inp`. Supported today: arithmetic,
`let`, function calls, `==`/`if`, and `match` over (nested) algebraic data types.
The prover is written in Glass itself — see [the prove bridge](../examples/prove/).

## The shape of a Glass program

A Glass file contains, in order:

1. Type declarations (`type Name<Params> = | Ctor1(...) | Ctor2(...) | ...`)
2. Function declarations (`fn name(params) : ReturnType = body`)
3. Top-level let bindings (`let name = value`)
4. A final expression — the program's result

```glass
type Status = | Active | Pending | Closed

fn describe(s: Status) : String =
  match s {
    Active  => "in progress";
    Pending => "waiting";
    Closed  => "done"
  }

let current = Active
describe(current)
```

Output: `"in progress" : String`

## What to read next

- [`language-tour.md`](language-tour.md) — a full tour of the language's features
- [`self-hosting.md`](self-hosting.md) — how Glass is implemented in Glass
- [`../LANG.md`](../LANG.md) — the formal specification + Stage 3 audit
