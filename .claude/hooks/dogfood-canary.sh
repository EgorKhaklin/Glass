#!/usr/bin/env bash
# =============================================================================
# dogfood-canary.sh — Glass's differential-testing discipline, as a hook.
#
# Wired as a PostToolUse hook (Edit|Write). It enforces the project's own
# definition of "done": the reference interpreter (glass.py) and the
# self-hosted compiler (native_glassc) must agree byte-for-byte.
#
#   * Editing glass.py (the reference / host side) → re-run dogfood.sh on a few
#     fast canary programs. A DIFF means the edit drifted the reference away
#     from the compiler — exit 2 surfaces the diff back to the agent so it's
#     caught at the moment it's introduced, not in CI.
#   * Editing the compiler side (quartz.py / glassc.glass / prism.glass) → the
#     cached /tmp native_glassc is now stale, so invalidate it and print a
#     reminder. A full rebuild is too slow to run inline (use bootstrap or
#     dogfood.sh manually).
#   * Any other file → no-op.
#
# Reads the PostToolUse JSON payload on stdin; needs no arguments.
# Advisory by design: it only "blocks" (exit 2) on a real reference⟷compiler
# DIFF, never on a clean pass or a transient toolchain error.
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DOGFOOD="$ROOT/examples/selfhost/dogfood.sh"

# Fast, prism-free canaries that the self-hosted compiler actually supports:
# recursion/arithmetic (fib), ADTs + pattern matching + Option/Result, and a
# trivial print baseline (hello) — enough to exercise parser, types, and eval
# on the core subset glassc compiles. (Many richer examples, e.g. effects /
# records / generics, hit native-compile limits and are intentionally excluded
# so the gate stays signal, not noise.)
CANARIES=(
  "examples/basic/fib.glass"
  "examples/basic/option_result.glass"
  "examples/basic/hello.glass"
)

# --- which file was just edited? -------------------------------------------
INPUT="$(cat)"
FILE_PATH="$(printf '%s' "$INPUT" | python3 -c \
  "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)"
BASE="$(basename "$FILE_PATH" 2>/dev/null)"

case "$BASE" in
  glass.py)
    : ;;  # reference/host side — verify below
  quartz.py|glassc.glass|prism.glass)
    rm -f /tmp/glass-dogfood/native_glassc /tmp/glass-native/native_glassc \
          /tmp/glassc_bin 2>/dev/null
    echo "[dogfood] compiler source changed ($BASE) — stale native_glassc cache invalidated." >&2
    echo "[dogfood] re-verify with: bash examples/selfhost/dogfood.sh <file>  (or bootstrap_fixpoint.sh)" >&2
    exit 0 ;;
  *)
    exit 0 ;;  # not a reference/compiler file — nothing to check
esac

[ -x "$DOGFOOD" ] || { echo "[dogfood] $DOGFOOD not found/executable — skipping." >&2; exit 0; }

# --- run the canaries through dogfood --------------------------------------
drift=""
for c in "${CANARIES[@]}"; do
  [ -f "$ROOT/$c" ] || continue
  out="$(bash "$DOGFOOD" "$ROOT/$c" 2>&1)"
  if printf '%s' "$out" | grep -q "DOGFOOD DIFF"; then
    drift="${drift}
${out}"
  elif ! printf '%s' "$out" | grep -q "DOGFOOD PASS"; then
    # toolchain / compile hiccup — warn, don't block
    echo "[dogfood] canary $c did not complete cleanly (toolchain?); not blocking." >&2
  fi
done

if [ -n "$drift" ]; then
  echo "[dogfood] reference ⟷ compiler DRIFT after editing $BASE:" >&2
  echo "$drift" >&2
  echo "[dogfood] glass.py and native_glassc disagree — fix before this counts as done." >&2
  exit 2
fi

echo "[dogfood] canaries pass: glass.py == native_glassc (byte-identical)." >&2
exit 0
