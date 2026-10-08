# native_lock.sh: sourced by every script that drives the native compiler.
#
# The native compiler reads /tmp/in.glass and writes /tmp/glassc_out.c and
# /tmp/glassc_bin: fixed paths, shared by every caller on the machine. Two runs
# at once overwrite each other's input and output, and the loser reads a
# half-written file. native_lock serializes them; a lock whose holder has
# exited is treated as stale and taken over.
NATIVE_LOCK=/tmp/glass-native.lock

native_lock() {
  local said=0
  until mkdir "$NATIVE_LOCK" 2>/dev/null; do
    local holder
    holder=$(cat "$NATIVE_LOCK/pid" 2>/dev/null || true)
    if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
      rm -rf "$NATIVE_LOCK"
      continue
    fi
    if [ "$said" -eq 0 ]; then echo "waiting for another native build (pid ${holder:-?}) to finish" >&2; said=1; fi
    sleep 1
  done
  echo "${BASHPID:-$$}" > "$NATIVE_LOCK/pid"
  trap 'rm -rf "$NATIVE_LOCK"' EXIT
}
