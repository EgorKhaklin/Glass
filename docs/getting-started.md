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
# Glass 4.95.0
```

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
