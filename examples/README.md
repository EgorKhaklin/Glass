# Examples

Everything here runs with `python3 glass.py <file>` from the repo root.

### Learn the language
| Folder | What's inside |
|---|---|
| [`basic/`](basic/) | Hello world, recursion, list operations — start here. |
| [`features/`](features/) | One small program per language feature (the tested corpus). |
| [`showcase/`](showcase/) | What the type system can *express* — refinements, effects, exotic types. |
| [`lib/`](lib/) | Reusable Glass libraries. |

### Glass compiles Glass
| Folder | What's inside |
|---|---|
| [`selfhost/`](selfhost/) | The bootstrap: `prism` (frontend) + `glassc` (compiler), both in Glass — and the fixpoint where Glass compiles itself with no Python in the loop. |
| [`quartz/`](quartz/) | The Glass → C compiler, by example. |
| [`stage3/`](stage3/) | Milestone programs from the road to self-hosting. |

### Built in Glass
| Folder | What's inside |
|---|---|
| [`pane/`](pane/) | **Pane** — a small query language, written in Glass. |
| [`frost/`](frost/) | **Frost** — a zero-knowledge proof system (a zk-STARK), built from scratch in Glass. The most involved thing here. |
| [`prove/`](prove/) | **The bridge** — write ordinary Glass, get a zero-knowledge proof of its execution. |
