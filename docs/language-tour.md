# Language tour

A walkthrough of Glass's features. This document assumes you've read [`getting-started.md`](getting-started.md).

---

## Primitive types

Glass has four primitive types:

```glass
let n   : Int    = 42
let b   : Bool   = true
let s   : String = "hello"
let f   : Float  = 3.14
```

Type annotations on `let` are optional — Hindley-Milner inference will figure them out — but they're encouraged for documentation.

---

## Algebraic data types

Type declarations introduce new sum types with named constructors:

```glass
type Direction = | North | South | East | West

type Shape =
  | Circle(Float)
  | Rectangle(Float, Float)
  | Triangle(Float, Float, Float)
```

Constructors with no arguments don't need parentheses when used:

```glass
let d = North
let s = Circle(3.0)
```

---

## Pattern matching

`match` destructures values by constructor. **It is exhaustive** — the compiler refuses to compile if you miss a case.

```glass
fn area(s: Shape) : Float =
  match s {
    Circle(r)         => 3.14159 * r * r;
    Rectangle(w, h)   => w * h;
    Triangle(a, b, c) =>
      let s = (a + b + c) / 2.0 in
      sqrt(s * (s - a) * (s - b) * (s - c))
  }
```

You can match on multiple things at once via tuples:

```glass
fn combine(d1: Direction, d2: Direction) : String =
  match (d1, d2) {
    (North, South) => "opposite";
    (South, North) => "opposite";
    (East, West)   => "opposite";
    (West, East)   => "opposite";
    (a, b)         => "same axis or identical"
  }
```

Literal patterns (since v1.0):

```glass
fn classify(n: Int) : String =
  match n {
    0 => "zero";
    1 => "one";
    _ => "many"
  }
```

Wildcards `_` match anything and bind nothing. Variables bind whatever's there.

---

## Recursion

Glass is pure functional — there are no loops. Recursion is the iteration construct.

```glass
fn fib(n: Int) : Int =
  if n < 2 then n
  else fib(n - 1) + fib(n - 2)

fib(10)
==> 55 : Int
```

Top-level `fn` declarations can reference each other (mutual recursion):

```glass
fn even(n: Int) : Bool =
  if n == 0 then true
  else odd(n - 1)

fn odd(n: Int) : Bool =
  if n == 0 then false
  else even(n - 1)

even(7)
==> false : Bool
```

---

## Generic types

Type parameters let you write polymorphic data structures and functions:

```glass
type Tree<A> =
  | Leaf
  | Node(A, Tree<A>, Tree<A>)

fn map_tree<A, B>(t: Tree<A>, f: (A) -> B) : Tree<B> =
  match t {
    Leaf          => Leaf;
    Node(v, l, r) => Node(f(v), map_tree(l, f), map_tree(r, f))
  }
```

The type system instantiates `<A, B>` automatically at each call site.

---

## Option and Result

Failure is part of the type system. There are no exceptions, no null pointers, no `nil`.

```glass
type Option<A> = | None | Some(A)
type Result<A, E> = | Ok(A) | Err(E)
```

A function that *might* fail returns `Option` or `Result`:

```glass
fn safe_divide(a: Int, b: Int) : Result<Int, String> =
  if b == 0 then Err("division by zero")
  else Ok(a / b)

match safe_divide(10, 0) {
  Ok(n)  => "result: " ++ int_to_string(n);
  Err(e) => "error: " ++ e
}
==> "error: division by zero" : String
```

The caller is forced to handle both cases — the match would be incomplete otherwise.

---

## Records

Named-field types for when constructor positions get confusing:

```glass
type User = { id: Int, name: String, email: String }

let u : User = { id: 42, name: "Alice", email: "alice@example.com" }
u.name
==> "Alice" : String
```

Field access uses `.`. Records are immutable.

---

## Higher-order functions

Functions are first-class values. Glass discourages indexed iteration; `map`, `filter`, `fold` replace `for` loops.

```glass
let xs = [1, 2, 3, 4, 5]

map(xs, fn(x: Int) -> x * x)
==> [1, 4, 9, 16, 25] : List<Int>

filter(xs, fn(x: Int) -> x > 2)
==> [3, 4, 5] : List<Int>

fold(xs, 0, fn(acc: Int, x: Int) -> acc + x)
==> 15 : Int
```

`map`, `filter`, `fold`, `len`, `head`, `tail` are built-in.

---

## Effects

Glass tracks side effects in the type system. Functions that perform I/O, randomness, AI inference, etc. carry effect rows in their signatures.

```glass
fn print(s: String) : String !{IO}
fn read_file(path: String) : Result<String, String> !{File}
fn random_int(lo: Int, hi: Int) : Int !{Random}
fn model_call(prompt: String) : String !{Inference}
```

The `!{...}` clause is an *effect row* — a set of labels for the side effects this function performs. Calling an effectful function propagates the effect up:

```glass
fn read_config(path: String) : Result<Config, String> !{File} =
  match read_file(path) {            # !{File} — inherited
    Ok(content) => parse_config(content);
    Err(msg)    => Err("could not read config: " ++ msg)
  }

fn main(path: String) : String !{File, IO} =  # !{File, IO} — combined
  match read_config(path) {
    Ok(cfg) => print("loaded config");
    Err(e)  => print("error: " ++ e)
  }
```

If `main` were declared as `: String !{IO}` (forgetting `File`), the compiler would reject it. **Every side effect is visible at every call site.**

---

## Function types

Higher-order signatures use the function-type syntax `(A, B) -> C`:

```glass
fn apply_twice<A>(f: (A) -> A, x: A) : A =
  f(f(x))

apply_twice(fn(n: Int) -> n + 1, 5)
==> 7 : Int
```

Function types may carry effect annotations on the arrow:

```glass
fn with_logging(f: (Int) -> Int !{IO}) : Int !{IO} =
  let _ = print("calling f") in
  f(42)
```

---

## Pure functional discipline

There are no:
- Mutable variables (`var`, `mut`)
- Loops (`for`, `while`)
- Exceptions (`throw`, `try/catch`)
- Null / `nil` / `None` outside of explicit `Option`
- Implicit conversions
- Hidden side effects

There are:
- Immutable bindings (`let`)
- Recursion + higher-order functions
- `Result<A, E>` for failures
- `Option<A>` for absence
- Explicit effect rows for I/O, randomness, inference
- Exhaustive pattern matching

The trade is verbosity for transparency. Every signature tells the truth about what a function does.

---

## What's next

- [`self-hosting.md`](self-hosting.md) — how Glass implements itself
- [`../LANG.md`](../LANG.md) — full specification with the Stage 3 audit
- [`../examples/`](../examples/) — many more example programs by category
