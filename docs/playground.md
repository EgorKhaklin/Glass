# The Glass Playground

Glass v2.1 ships a browser-based playground: a single HTML file that runs Glass in your browser via [Pyodide](https://pyodide.org) — Python compiled to WebAssembly.

No install. No package. Open the page, edit Glass on the left, press Run, see the output on the right.

## Trying it

The playground lives at the repo root as `playground.html` and fetches `glass.py` from the same directory. To run it locally:

```bash
git clone https://github.com/EgorKhaklin/Glass.git
cd Glass
python -m http.server
```

Then open `http://localhost:8000/playground.html`. Pyodide takes ~5–10 seconds to load on first visit; the WASM bundle (~10MB) is cached after that.

To host publicly: any static file server works. GitHub Pages is the obvious choice — push the repo, enable Pages on the main branch, and the playground is live at `https://<you>.github.io/Glass/playground.html`.

## What it does

The page is one HTML file. Inside:

- **Pyodide** is loaded from CDN (`https://cdn.jsdelivr.net/pyodide/v0.27.0/`).
- **`glass.py`** is fetched from the same directory and loaded into Pyodide's filesystem.
- The Glass module is imported once at startup.
- Each Run press calls `glass.run_source(src, verbose=True)` with stdout captured into a buffer.
- The buffer plus a status code (`ok` / `err`) flow back to JavaScript and render in the output pane.

Three error categories are caught and shown cleanly: `SyntaxError`, `TypeError_`, `RuntimeError`. Pyodide-level failures fall through to a final catch.

## Preset examples

The example dropdown loads eight Glass programs that exercise different language features:

| Example | What it shows |
|---------|---------------|
| Hello world | Basic string evaluation |
| Fibonacci | Recursion + refinement types (`n >= 0`) |
| ADTs & pattern matching | Tree ADT, insert, sum-tree |
| Refinement types | Static discharge, return refinements, implication |
| Effect system | `!{IO}` effect annotations |
| Generic functions | Polymorphism, type inference |
| Closures & higher-order | Currying via lambda return |
| Regex matcher (mini) | Recursive eval of an ADT-based language |

Each is loaded into the editor as a starting point. Modify freely.

## Keyboard shortcuts

- **Ctrl-Enter** (or **Cmd-Enter** on macOS) — Run the current source.
- **Tab** — Insert two spaces (doesn't shift focus).

## Aesthetic

Dark slate base (`#0a0d12`), refractive cyan accent (`#00bcd4`), monospace throughout. The octahedron in the header is the project mark, rotating gently while Pyodide loads. CSS is inline in the page — no external stylesheets, no font requests, no analytics, no tracking. The page is self-contained except for the Pyodide CDN reference.

## Limitations

- **No `read_file`.** The host's `read_file` builtin works against the local filesystem; in Pyodide's browser filesystem there are no `.glass` files to read. (Pyodide does have a virtual FS — a v2.2 idea is exposing example files into it so `read_file("examples/...")` works.)
- **No `print` interleaving.** Output is captured as a buffer and rendered when the run completes. Long-running computations don't stream their progress; they print everything at the end.
- **Pyodide warmup.** First load is the WASM bundle download. After that, page reloads are fast (cached). Code runs after Pyodide initialises take ~50–500ms, depending on program size.

## Why this matters

The playground turns "try Glass" from a three-step process — `git clone`, `pip install`, `glass file.glass` — into one click. That's the difference between a project that gets bookmarked and a project that gets tried. v2.0 was the maturity bump; v2.1 makes the maturity reachable.
