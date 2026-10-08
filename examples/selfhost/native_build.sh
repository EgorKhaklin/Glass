# native_build.sh: sourced by run_native.sh and dogfood.sh.
#
# build_native_glassc OUT ROOT PYTHON builds the self-hosted compiler in two steps:
#   1. quartz.py (Python) compiles glassc.glass        -> gen1
#   2. gen1 compiles glassc itself (prism + glassc)    -> gen2, installed at OUT
# gen1, the Quartz-built compiler, has a known garbage-collection liveness bug:
# on large inputs a collection can free an object that is still in use, and the
# compile fails (or, in principle, goes wrong) at random. It therefore runs once,
# with collection disabled; gen2, Glass compiled by Glass, is the compiler every
# later build uses, with the collector on. See docs/roadmap.md, Stage II.
build_native_glassc() {
  local out="$1" root="$2" py="$3" tmp firstlet
  tmp=$(mktemp -d /tmp/glass-build.XXXXXX)
  printf '0\n' > /tmp/in.glass   # glassc.glass evals /tmp/in.glass at compile time; keep it trivial
  if ! "$py" "$root/quartz.py" "$root/examples/selfhost/glassc.glass" -o "$tmp/gen1" >/dev/null; then
    rm -rf "$tmp"; return 1
  fi
  firstlet=$(grep -m1 -n '^let ' "$root/examples/selfhost/prism.glass" | cut -d: -f1)
  head -n $((firstlet - 1)) "$root/examples/selfhost/prism.glass" > /tmp/in.glass
  grep -v '^import "prism.glass"' "$root/examples/selfhost/glassc.glass" >> /tmp/in.glass
  rm -f /tmp/glassc_bin
  GC_DONT_GC=1 "$tmp/gen1" > "$tmp/gen1.log" 2>&1 || true
  if ! grep -q '^glassc: compiled' "$tmp/gen1.log" || [ ! -x /tmp/glassc_bin ]; then
    echo "native_build: gen1 could not build the self-hosted compiler:" >&2
    tail -5 "$tmp/gen1.log" >&2
    rm -rf "$tmp"; return 1
  fi
  mv /tmp/glassc_bin "$out"
  rm -rf "$tmp"
}
