#!/bin/bash
# bootstrap_fixpoint.sh — prove Glass self-hosts.
#
#   1. quartz.py (Python) compiles glassc.glass        -> native_glassc   (one-time)
#   2. native_glassc (no Python) compiles glassc itself -> native_glassc_2
#   3. native_glassc_2 compiles prism.glass; output must match `glass.py prism.glass`
#   4. triple-test: native_glassc and native_glassc_2 emit byte-identical C for prism
#
# glassc reads /tmp/in.glass and emits /tmp/glassc_bin (compile-and-stop).
set -e
cd "$(dirname "$0")/../.."
PY=python3.12
T=/tmp

echo "[1] quartz.py compiles glassc.glass -> native_glassc"
printf '0\n' > $T/in.glass            # tiny input so the install-time eval is cheap
$PY quartz.py examples/selfhost/glassc.glass -o $T/native_glassc >/dev/null

echo "[*] build self-contained glassc source (prism defs + glassc, no import)"
firstlet=$(grep -n '^let ' examples/selfhost/prism.glass | head -1 | cut -d: -f1)
head -n $((firstlet - 1)) examples/selfhost/prism.glass > $T/glassc_self.glass
grep -v '^import "prism.glass"' examples/selfhost/glassc.glass >> $T/glassc_self.glass

echo "[2] native_glassc compiles glassc itself -> native_glassc_2"
cp $T/glassc_self.glass $T/in.glass
$T/native_glassc >/dev/null
cp $T/glassc_bin $T/native_glassc_2

echo "[3] native_glassc_2 compiles prism.glass; diff vs host"
cp examples/selfhost/prism.glass $T/in.glass
$T/native_glassc_2 >/dev/null
$T/glassc_bin | grep '==>' > $T/prism_self.txt
$PY glass.py examples/selfhost/prism.glass 2>/dev/null | grep '==>' > $T/prism_host.txt
if diff -q $T/prism_self.txt $T/prism_host.txt >/dev/null; then
  echo "    OK: $(wc -l < $T/prism_self.txt) demo lines, byte-identical to host"
else
  echo "    FAIL: prism output differs from host"; diff $T/prism_self.txt $T/prism_host.txt | head; exit 1
fi

echo "[4] triple-test: gen1 vs gen2 emit identical C for prism"
cp examples/selfhost/prism.glass $T/in.glass
$T/native_glassc   >/dev/null; cp $T/glassc_out.c $T/prismC_gen1.c
$T/native_glassc_2 >/dev/null; cp $T/glassc_out.c $T/prismC_gen2.c
if diff -q $T/prismC_gen1.c $T/prismC_gen2.c >/dev/null; then
  echo "    OK: $(wc -l < $T/prismC_gen1.c) lines of C, byte-identical (exact self-reproduction)"
else
  echo "    FAIL: gen1 and gen2 emit different C"; exit 1
fi

echo "*** SELF-HOSTING BOOTSTRAP FIXPOINT VERIFIED ***"
