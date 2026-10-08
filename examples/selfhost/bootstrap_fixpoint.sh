#!/bin/bash
# bootstrap_fixpoint.sh: prove Glass self-hosts.
#
#   1. quartz.py (Python) compiles glassc.glass        -> native_glassc   (one-time)
#   2. native_glassc (no Python) compiles glassc itself -> native_glassc_2
#   3. native_glassc_2 compiles prism.glass; output must match `glass.py prism.glass`
#   4. triple-test: native_glassc and native_glassc_2 emit byte-identical C for prism
#
# glassc reads /tmp/in.glass and emits /tmp/glassc_bin (compile-and-stop).
#
# native_glassc (gen1, built by Quartz) has a known garbage-collection liveness bug:
# on large inputs a collection can free a live object and the compile fails at
# random. gen1 therefore runs with collection disabled (GEN1 below); gen2, Glass
# compiled by Glass, runs with the collector on. See docs/roadmap.md, Stage II.
set -e
cd "$(dirname "$0")/../.."
PY=python3.12
T=/tmp
. examples/selfhost/native_lock.sh
native_lock

# compile_with STEP COMMAND...: run a native compiler on /tmp/in.glass from a clean
# slate, and fail loudly unless it reports success and leaves both outputs. A stale
# /tmp/glassc_bin or /tmp/glassc_out.c from an earlier step must never stand in for
# this one's result.
compile_with() {
  rm -f "$T/glassc_bin" "$T/glassc_out.c"
  local step="$1"; shift
  if ! "$@" > "$T/fixpoint_compile.log" 2>&1 \
     || ! grep -q '^glassc: compiled' "$T/fixpoint_compile.log" \
     || [ ! -x "$T/glassc_bin" ] || [ ! -s "$T/glassc_out.c" ]; then
    echo "    FAIL ($step): the native compiler did not produce a binary"
    sed 's/^/      /' "$T/fixpoint_compile.log" | tail -5
    exit 1
  fi
}

GEN1="env GC_DONT_GC=1 $T/native_glassc"

echo "[1] quartz.py compiles glassc.glass -> native_glassc"
printf '0\n' > $T/in.glass            # tiny input so the install-time eval is cheap
rm -f $T/native_glassc
$PY quartz.py examples/selfhost/glassc.glass -o $T/native_glassc >/dev/null
[ -x $T/native_glassc ] || { echo "    FAIL (1): quartz did not produce native_glassc"; exit 1; }

echo "[*] build self-contained glassc source (prism defs + glassc, no import)"
firstlet=$(grep -n '^let ' examples/selfhost/prism.glass | head -1 | cut -d: -f1)
head -n $((firstlet - 1)) examples/selfhost/prism.glass > $T/glassc_self.glass
grep -v '^import "prism.glass"' examples/selfhost/glassc.glass >> $T/glassc_self.glass

echo "[2] native_glassc compiles glassc itself -> native_glassc_2"
cp $T/glassc_self.glass $T/in.glass
compile_with 2 $GEN1
rm -f $T/native_glassc_2
cp $T/glassc_bin $T/native_glassc_2

echo "[3] native_glassc_2 compiles prism.glass; diff vs host"
cp examples/selfhost/prism.glass $T/in.glass
compile_with 3 $T/native_glassc_2
$T/glassc_bin | grep '==>' > $T/prism_self.txt || true
$PY glass.py examples/selfhost/prism.glass 2>/dev/null | grep '==>' > $T/prism_host.txt || true
if [ -s $T/prism_self.txt ] && diff -q $T/prism_self.txt $T/prism_host.txt >/dev/null; then
  echo "    OK: $(wc -l < $T/prism_self.txt) demo lines, byte-identical to host"
else
  echo "    FAIL: prism output differs from host (or is empty)"; diff $T/prism_self.txt $T/prism_host.txt | head; exit 1
fi

echo "[4] triple-test: gen1 vs gen2 emit identical C for prism"
cp examples/selfhost/prism.glass $T/in.glass
compile_with 4 $GEN1; cp $T/glassc_out.c $T/prismC_gen1.c
compile_with 4 $T/native_glassc_2; cp $T/glassc_out.c $T/prismC_gen2.c
if diff -q $T/prismC_gen1.c $T/prismC_gen2.c >/dev/null; then
  echo "    OK: $(wc -l < $T/prismC_gen1.c) lines of C, byte-identical (exact self-reproduction)"
else
  echo "    FAIL: gen1 and gen2 emit different C"; exit 1
fi

echo "*** SELF-HOSTING BOOTSTRAP FIXPOINT VERIFIED ***"
