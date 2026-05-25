#!/usr/bin/env bash
# =============================================================================
# dogfood.sh <file.glass> — the Glass differential-testing discipline, as one
# command. Runs <file> on BOTH the reference host (glass.py) and the
# self-hosted Glass-written compiler (native_glassc), and confirms they produce
# identical output. This is what "self-hosting" means in practice: the language
# describing itself, checked bit-for-bit.
#
#   bash examples/selfhost/dogfood.sh examples/prove/prove_adt.glass
#
# Handles two details automatically:
#   * files that `import "../selfhost/prism.glass"` are inlined (the native
#     compiler reads /tmp/in.glass without runtime import expansion);
#   * glass.py echoes inferred type signatures and the native binary auto-prints
#     the program's final return value — both are stripped before diffing, so
#     only the actual print() output is compared.
# =============================================================================
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: dogfood.sh <file.glass>"; exit 2; }
FILE="$1"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"
PRISM="$ROOT/examples/selfhost/prism.glass"
T=/tmp/glass-dogfood; mkdir -p "$T"

# 1. the self-hosted compiler (cached; build once via the one-time quartz bootstrap)
GLASSC="${GLASSC:-$T/native_glassc}"
if [ ! -x "$GLASSC" ]; then
  echo "[build] compiling native_glassc via quartz (one-time)…"
  printf '0\n' > "$T/seed.glass"
  "$PY" "$ROOT/quartz.py" "$ROOT/examples/selfhost/glassc.glass" -o "$GLASSC" >/dev/null
fi

# 2. assemble the program (inline prism if the file imports it)
SRC="$T/prog.glass"
if grep -q '^import ' "$FILE"; then
  firstlet=$(grep -n '^let ' "$PRISM" | head -1 | cut -d: -f1)
  head -n $((firstlet - 1)) "$PRISM" > "$SRC"
  grep -v '^import ' "$FILE" >> "$SRC"
else
  cp "$FILE" "$SRC"
fi

# 3. reference host (-q: only program output, no declaration echoes)
"$PY" "$ROOT/glass.py" -q "$SRC" 2>/dev/null > "$T/host.out" || true

# 4. self-hosted compiler: compile /tmp/in.glass -> /tmp/glassc_bin, run it
cp "$SRC" /tmp/in.glass
rm -f /tmp/glassc_bin
"$GLASSC" >/dev/null 2>&1 || true
# glassc exits 0 even when cc fails, so check the binary was actually produced
[ -x /tmp/glassc_bin ] || { echo "DOGFOOD FAIL ($FILE): native compile error (no binary; run native_glassc to see cc errors)"; exit 1; }
/tmp/glassc_bin 2>/dev/null | sed '$d' > "$T/native.out" || true   # drop the auto-printed final value

# 5. compare
if diff -q "$T/native.out" "$T/host.out" >/dev/null; then
  echo "DOGFOOD PASS: $FILE  —  native_glassc == glass.py (self-hosted, byte-identical)"
else
  echo "DOGFOOD DIFF: $FILE"
  diff "$T/native.out" "$T/host.out" | head -20
  exit 1
fi
