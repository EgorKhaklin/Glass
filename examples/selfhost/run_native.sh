#!/usr/bin/env bash
# =============================================================================
# run_native.sh <file.glass> — run a Glass program at NATIVE speed.
#
# Glass has two execution paths: the reference interpreter (`glass.py`, the
# readable spec) and the self-hosted compiler (`native_glassc`, Glass → C → a
# native binary). For heavy work — the from-scratch zk-STARK, big circuits, the
# crypto frontier — the interpreter is the bottleneck; the native binary is
# ~50–100× faster and bit-for-bit identical (that's the dogfood guarantee).
#
#   bash examples/selfhost/run_native.sh examples/prove/prove_query_zk.glass
#   bash examples/selfhost/run_native.sh <file>  --time   # also print timing
#
# Workflow: prototype + verify on the interpreter (small inputs, `dogfood.sh`
# for the reference⟷compiler check), then RUN at scale here. native_glassc is
# built once via the quartz bootstrap (cached), then compiles any file in ~1s.
# =============================================================================
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: run_native.sh <file.glass> [--time]"; exit 2; }
FILE="$1"; TIMEIT="${2:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-$(command -v python3.12 || echo python3)}"   # quartz.py needs Python 3.10+
PRISM="$ROOT/examples/selfhost/prism.glass"
T=/tmp/glass-native; mkdir -p "$T"

# 1. the self-hosted native compiler (cached; built once via the quartz bootstrap)
GLASSC="${GLASSC:-$T/native_glassc}"
if [ ! -x "$GLASSC" ] || [ "$ROOT/examples/selfhost/glassc.glass" -nt "$GLASSC" ]; then
  echo "[build] compiling native_glassc via quartz (glassc.glass changed or first run)…" >&2
  printf '0\n' > /tmp/in.glass   # glassc.glass evals /tmp/in.glass at compile time; keep it trivial
  "$PY" "$ROOT/quartz.py" "$ROOT/examples/selfhost/glassc.glass" -o "$GLASSC" >/dev/null
fi

# 2. assemble the program (inline prism if the file imports it — the native
#    compiler reads /tmp/in.glass with no runtime import expansion)
if grep -q '^import ' "$FILE"; then
  firstlet=$(grep -n '^let ' "$PRISM" | head -1 | cut -d: -f1)
  head -n $((firstlet - 1)) "$PRISM" > /tmp/in.glass
  grep -v '^import ' "$FILE" >> /tmp/in.glass
else
  cp "$FILE" /tmp/in.glass
fi

# 3. compile to a native binary
rm -f /tmp/glassc_bin
if [ "$TIMEIT" = "--time" ]; then echo "[compile]" >&2; time "$GLASSC" >/dev/null 2>&1 || true
else "$GLASSC" >/dev/null 2>&1 || true; fi
[ -x /tmp/glassc_bin ] || { echo "run_native: native compile error (run $GLASSC on /tmp/in.glass to see cc errors)" >&2; exit 1; }

# 4. run it (drop the binary's auto-printed final return value, like dogfood)
if [ "$TIMEIT" = "--time" ]; then echo "[run]" >&2; time /tmp/glassc_bin | sed '$d'
else /tmp/glassc_bin | sed '$d'; fi
