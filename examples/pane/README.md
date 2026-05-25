# Pane — a query language in Glass

A small, total, deterministic query algebra over typed data, with a reference
interpreter (`run_query`). It's shaped deliberately: the same `Query` AST that
Pane interprets can also be compiled into a zero-knowledge circuit — that's
[Frost](../frost/), Pane's cryptographic backend.

- [`pane.glass`](pane.glass) — the query algebra (`Query` / `PExpr` ADTs) and its interpreter.
