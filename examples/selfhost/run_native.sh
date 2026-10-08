#!/usr/bin/env bash
# =============================================================================
# run_native.sh <file.glass>: run a Glass program at NATIVE speed.
#
# Glass has two execution paths: the reference interpreter (`glass.py`, the
# readable spec) and the self-hosted compiler (`native_glassc`, Glass → C → a
# native binary). For heavy work: the from-scratch zk-STARK, big circuits, the
# crypto frontier: the interpreter is the bottleneck; the native binary is
# ~50–100× faster and bit-for-bit identical (that's the dogfood guarantee).
#
#   bash examples/selfhost/run_native.sh examples/prove/prove_query_zk.glass
#   bash examples/selfhost/run_native.sh <file>  --time   # also print timing
#   bash examples/selfhost/run_native.sh <file>  --build OUT   # compile only, install at OUT
#
# Workflow: prototype + verify on the interpreter (small inputs, `dogfood.sh`
# for the reference⟷compiler check), then RUN at scale here. native_glassc is
# built once (cached; see native_build.sh), then compiles any file in ~1s.
# =============================================================================
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: run_native.sh <file.glass> [--time | --build OUT]"; exit 2; }
FILE="$1"; TIMEIT="${2:-}"; BUILD_OUT=""
if [ "$TIMEIT" = "--build" ]; then
  BUILD_OUT="${3:-}"; TIMEIT=""
  [ -n "$BUILD_OUT" ] || { echo "usage: run_native.sh <file.glass> --build OUT"; exit 2; }
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-$(command -v python3.12 || echo python3)}"   # quartz.py needs Python 3.10+
PRISM="$ROOT/examples/selfhost/prism.glass"
T=/tmp/glass-native; mkdir -p "$T"

# The native compiler reads and writes fixed /tmp paths; hold the shared lock so a
# concurrent build (another prove, a gate, the fixpoint) cannot overwrite them.
. "$HERE/native_lock.sh"
native_lock
# --build: another process may have installed the binary while this one waited.
if [ -n "$BUILD_OUT" ] && [ -x "$BUILD_OUT" ]; then exit 0; fi

# 1. the self-hosted native compiler (cached; rebuilt when its sources change)
GLASSC="${GLASSC:-$T/native_glassc}"
. "$HERE/native_build.sh"
if [ ! -x "$GLASSC" ] || [ "$ROOT/examples/selfhost/glassc.glass" -nt "$GLASSC" ] \
   || [ "$ROOT/examples/selfhost/prism.glass" -nt "$GLASSC" ]; then
  echo "[build] building the self-hosted compiler (sources changed or first run)" >&2
  build_native_glassc "$GLASSC" "$ROOT" "$PY" || { echo "run_native: could not build native_glassc" >&2; exit 1; }
fi

# 2. assemble the program (inline prism if the file imports it: the native
#    compiler reads /tmp/in.glass with no runtime import expansion)
if grep -q '^import ' "$FILE"; then
  # `grep -m1` (stop after the first match) instead of `grep | head -1`: under `set -o pipefail`,
  # `head -1` closing the pipe early makes grep fail with EPIPE on hosts where SIGPIPE is ignored
  # (GitHub-Actions runners) ("grep: write error: Broken pipe", exit 2) which aborted run_native
  # (rc=2, no binary built) ONLY on CI, so heavy native proves skipped there. grep -m1 exits cleanly.
  firstlet=$(grep -m1 -n '^let ' "$PRISM" | cut -d: -f1)
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

# --build: install the binary at OUT (atomically, so a concurrent reader never sees
# half a file) and stop. glass prove caches the prover this way and runs it per proof.
if [ -n "$BUILD_OUT" ]; then
  mkdir -p "$(dirname "$BUILD_OUT")"
  cp /tmp/glassc_bin "$BUILD_OUT.partial.$$" && mv -f "$BUILD_OUT.partial.$$" "$BUILD_OUT"
  exit 0
fi

# 4. run it (drop the binary's auto-printed final return value, like dogfood).
#    512MB stack for the prover's deep m=32768 codeword recursion. macOS links it
#    (-Wl,-stack_size,0x20000000), a flag GNU ld IGNORES, so on Linux the prover
#    overflows the 8MB default stack and SIGSEGVs. Set it explicitly here (524288 KB =
#    512MB, matching the macOS link). NB: an explicit value, not `unlimited`, which is
#    unreliable for deep recursion on Linux. `|| true` so macOS (hard ulimit < 512MB,
#    but the link already provides the stack) is unaffected.
ulimit -s 524288 2>/dev/null || true
#    Run to a temp file and capture the binary's TRUE exit code FIRST, then strip the last line:
#    piping straight into `sed '$d'` lets `sed` exit before a slow/crashing binary finishes, which
#    raises SIGPIPE on the binary and (under `set -o pipefail`) reports the pipeline as rc=141,
#    masking the real exit. Decoupling makes the status honest on every platform (Linux included).
RUNOUT=/tmp/glassc_run.out
if [ "$TIMEIT" = "--time" ]; then echo "[run]" >&2; time "/tmp/glassc_bin" > "$RUNOUT"; rc=$?
else "/tmp/glassc_bin" > "$RUNOUT"; rc=$?; fi
sed '$d' "$RUNOUT"
exit $rc
