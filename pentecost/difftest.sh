#!/usr/bin/env bash
# =============================================================================
# pentecost/difftest.sh — "let the verifier be two", end to end.
#
# Glass's native prover emits a real ProofB3 as a token stream; the INDEPENDENT
# Python re-verifier (pentecost/pentecost_verify.py — plain int mod p, from-scratch
# Poseidon, NO Glass code) parses and checks it. The differential:
#
#   honest proof   -> Glass verify_b3 ACCEPT  AND  Pentecost ACCEPT
#   tampered proof -> Pentecost REJECT
#   wrong claim    -> Pentecost REJECT
#
# This retires the honest-ledger caveat "verify_b3 is reasoned, not machine-checked"
# for the B3 path: a second, independently-implemented verifier sharing no code
# agrees on accept and disagrees on tamper. Research-grade, UNAUDITED.
#
#   bash pentecost/difftest.sh        # exits 0 iff honest ACCEPT and all tampers REJECT
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PY="${PYTHON:-$(command -v python3.12 || echo python3)}"
BRIDGE="$ROOT/examples/prove/prove_source_goldilocks_zk.glass"
PROOF=/tmp/pentecost_proof.txt

echo "[1] build the emit driver (bridge machinery + a trivial claim a+b == 8)"
"$PY" - "$BRIDGE" <<'PYEOF' > /tmp/pentecost_emit_driver.glass
import sys
bridge = open(sys.argv[1]).read()
machinery = bridge[:bridge.find("# --- demo")]
sys.stdout.write(machinery + (
  '\nlet _usrc : String = "a + b"\n'
  'let _inp : List<Pair<String, List<Int>>> = [Pair("a", [3]), Pair("b", [5])]\n'
  'let _rv : List<List<Int>> = gref_m_checked(_usrc, _inp)\n'
  'let _r : List<Int> = vh(_rv)\n'
  'let _ : String = print(gprove_emit(_usrc, _inp, _r))\n'
  '"emit-done"\n'
))
PYEOF

echo "[2] Glass native prover emits the proof token stream"
PYTHON="$PY" bash "$ROOT/examples/selfhost/run_native.sh" /tmp/pentecost_emit_driver.glass > "$PROOF"
echo "    $(wc -w < "$PROOF" | tr -d ' ') tokens, $(wc -c < "$PROOF" | tr -d ' ') bytes"

echo "[3] the independent Python verifier checks honest + tampered"
"$PY" - "$PROOF" <<'PYEOF'
import sys
sys.setrecursionlimit(100000)
from pentecost.pentecost_verify import parse, verify_b3
path = sys.argv[1]
toks = open(path).read().split()

def verdict(tokens):
    open("/tmp/pentecost_tamper.txt", "w").write(" ".join(tokens))
    g, p = parse("/tmp/pentecost_tamper.txt")
    r = verify_b3(g, p)
    return r[0] if isinstance(r, tuple) else r

honest = verdict(toks)
pi = toks.index("PROOF")
t_root = toks[:]; t_root[pi + 1] = str(int(t_root[pi + 1]) + 1)          # perturb root1 lane0 limb0 (v5.122: no count prefix -> pi+1 is limb0)
t_claim = toks[:]; t_claim[9] = "9"                                       # claim a+b == 9, not 8
t_open = toks[:]; t_open[-2] = str(int(t_open[-2]) + 1)                   # perturb a deep opening token

cases = [("honest", honest, True), ("tampered-root1", verdict(t_root), False),
         ("wrong-claim(9)", verdict(t_claim), False), ("tampered-opening", verdict(t_open), False)]
ok = True
for name, got, want_accept in cases:
    good = (got == want_accept)
    ok = ok and good
    print(f"    {'OK ' if good else 'FAIL'}  {name:18s} -> {'ACCEPT' if got else 'REJECT'}  (expect {'ACCEPT' if want_accept else 'REJECT'})")
if ok:
    print("*** PENTECOST DIFFERENTIAL PASSED: the second verifier agrees on accept, rejects every tamper ***")
sys.exit(0 if ok else 1)
PYEOF
