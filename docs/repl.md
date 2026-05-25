# The Glass REPL

Glass ships with an interactive read-eval-print loop. Run `glass` with no arguments to start it:

```
$ glass
Glass v4.91 — interactive REPL
Type :help for commands, :quit to exit.

glass>
```

## Expressions

Type any Glass expression and press Enter. The result is printed with its type.

```
glass> 1 + 1
  : Int = 2

glass> [1, 2, 3] ++ [4, 5]
  : List<Int> = [1, 2, 3, 4, 5]

glass> "hello, " ++ "world"
  : String = "hello, world"
```

## Declarations

Top-level `let`, `fn`, and `type` declarations persist for the rest of the session.

```
glass> let x = 42
  x : Int = 42

glass> fn double(n: Int) : Int = n + n
  double : (Int) -> Int

glass> double(x)
  : Int = 84
```

## Multi-line input

The REPL detects when input is incomplete and keeps reading. The continuation prompt shows `...`:

```
glass> fn fact(n: Int) : Int =
    ...   if n < 2 then 1
    ...   else n * fact(n - 1)
  fact : (Int) -> Int

glass> fact(5)
  : Int = 120
```

Any parse error involving an unexpected end-of-input — missing closing brace, missing `then`, missing `in`, etc. — triggers continuation. Other parse errors are reported immediately and the buffer is cleared.

## Commands

Commands start with `:`.

| Command | Behavior |
|---------|----------|
| `:help` | Show available commands. |
| `:quit` (or `:q`) | Exit the REPL. `Ctrl-D` also works. |
| `:type EXPR` | Show the type of `EXPR` without evaluating. |
| `:env` | List user-defined bindings. |
| `:reset` | Clear all user definitions and start fresh. |
| `:load PATH` | Read a `.glass` file and install its declarations. |

```
glass> :type fn(n: Int) -> n + 1
  fn(n: Int) -> n + 1 : (Int) -> Int

glass> :load examples/showcase/derive.glass
  Polynomial : ...
  derive : ...
  ...

glass> :env
  derive : ...
  Polynomial : ...
```

## History

If the Python `readline` module is available (Linux and macOS by default), arrow keys navigate command history. History persists across sessions in `~/.glass_history`.

## Error recovery

The REPL catches all parse, type, and runtime errors and keeps the session alive:

```
glass> undefined_name
  ! TypeError_: unbound identifier 'undefined_name'

glass> 1 + true
  ! TypeError_: +: expected Int, Int — got Int, Bool

glass> 1 + 1
  : Int = 2
```

Previously installed bindings are unaffected by failed input.

## When to use it

The REPL is for exploring the language interactively — testing whether a refinement predicate parses, checking what type an expression has, sketching a small calculation. For programs you want to keep, save them in a `.glass` file and run with `glass path/to/file.glass`.
