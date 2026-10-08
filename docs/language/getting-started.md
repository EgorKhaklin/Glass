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

Verify the install (this prints the installed version):

```bash
glass --version
```

### Native toolchain

The interpreter, the REPL, and the bundled examples need only Python. The
**self-hosted native compiler** (`examples/selfhost/run_native.sh`,
`bootstrap_fixpoint.sh`) also needs a C compiler and the Boehm garbage collector,
because it emits C and links `libgc`. The default `glass prove` runs on that
native path, so it needs them too:

```bash
# macOS
brew install bdw-gc

# Linux (Debian/Ubuntu)
sudo apt-get install libgc-dev
```

Clang and GCC both work: the build retries without the Clang-only
`-fbracket-depth` flag when `cc` is GCC.

## Your first program

Create `hello.glass`:

```glass
fn greet(name: String) : String =
  "Hello, " ++ name ++ "!"

let message = greet("Glass")
```

Run it:

```bash
$ glass hello.glass
  greet : (String) -> String
  message : String = Hello, Glass!
```

The interpreter prints each top-level binding with its inferred type and value. A
bare top-level expression runs for its effects and is not echoed; bind it with
`let`, or call `print`, to see it.

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

## Prove a function

Glass can compile a function into an arithmetic circuit and emit a **succinct
proof of its result**: names passed on the command line are *private inputs*
that stay in the witness. The default proves over Goldilocks and verifies with the
independent, witness-free **`verify_b3`** (sound, but not hiding); `--zk` adds
zero-knowledge (randomized-trace hiding) and `--fast` is the old witness self-check
(not a soundness proof):

```bash
glass prove examples/prove/hello_prove.glass inp=9
#   result:  86  (over Goldilocks, p = 2^64-2^32+1)
#   proof:   ACCEPT  (SOUND: independent witness-free verify_b3; not zero-knowledge)
```

With `--zk` the proof reveals only the result (`86`), not `inp`; the default proof is sound
but not hiding, so its openings can expose witness values. Supported today: arithmetic
(`+ - *`), integer division and modulo (`/ %`), unsigned comparison (`< > <= >=`),
boolean logic, `let`, function calls, `==`/`if`, and `match` over (nested) algebraic
data types, plus **signed integers** in `[-2³¹, 2³¹)`: `slt`/`sle`/`sgt`/`sge`
(signed comparison) and `sdiv`/`smod` (C99 truncated division), with negative results
shown signed; **bitwise logic** over `[0,2³²)`: `bit_and`/`bit_or`/`bit_xor` (e.g. prove a
private permission set contains the required bits: `bit_and(perms, required) == required`),
and **strings**: `++` (concat), `==`/`!=`, `string_length`, `substring`, and
`match` on string literals, so you can prove a predicate over a *private* string (e.g.
`substring(key,0,8)=="sk-live-"`: prove a credential's prefix without revealing the key) or
dispatch on one (`match cmd { "deploy" => 1; … }`: provable allowlist membership; pass a
string input as `name="..."`), and **records**: declare `type Account = { balance: Int, owner: Int }`,
construct (`Account { balance: b, owner: o }`), destructure (`match a { Account { balance, owner } => … }`),
and read fields directly (`a.balance >= 100`): structured data flowing through a proof, so you can
prove e.g. a private account is solvent without revealing its balance or owner. A proof's result can
itself be a **string** (`fn reveal_prefix(k: String) = substring(k, 0, 8)` reveals only a private key's
prefix; `if score >= 750 then "PASS" else "FAIL"` reveals a verdict word chosen by a private comparison),
bound and decoded faithfully (branches that are string literals, `++`, or `substring` may differ in
width and the shorter is padded; other unequal-width branches abstain), or a **tuple
or record** of scalars (`fn divmod(a, b) = (a / b, a % b)` reveals the `(quotient, remainder)` pair;
a record displays with field names), so what a proof returns is scalar, string, or structured.
An operation the bridge has no faithful lowering for *abstains* loudly instead of being
silently proven. That the bridge lowers the source faithfully is itself outside the soundness
proof; see [faithful lowering](../security/faithful-lowering.md). The prover is research-grade
and unaudited, and it is written in Glass itself: see [the prove bridge](../../examples/prove/).

## The shape of a Glass program

A Glass file contains, in order:

1. Type declarations (`type Name<Params> = | Ctor1(...) | Ctor2(...) | ...`)
2. Function declarations (`fn name(params) : ReturnType = body`)
3. Top-level let bindings (`let name = value`)
4. A final expression: the program's result

```glass
type Status = | Active | Pending | Closed

fn describe(s: Status) : String =
  match s {
    Active  => "in progress";
    Pending => "waiting";
    Closed  => "done"
  }

let current = Active
let result = describe(current)
```

Output, last line: `result : String = in progress`

## What to read next

- [`tour.md`](tour.md): a full tour of the language's features
- [`self-hosting.md`](../compiler/self-hosting.md): how Glass is implemented in Glass
- [`LANG.md`](../../LANG.md): the language specification
