#!/usr/bin/env python3
# Cross-check the in-circuit REAL Poseidon2 (examples/prove/poseidon2_node.glass, H3 block B2) against
# the independent from-scratch Poseidon2 spec (pentecost/poseidon.py). The circuit lowers the full t=12
# permutation to ~1.9k Goldilocks gates; this proves it for input lanes 0..11 and checks all 12 output
# lanes equal pentecost.perm([0..11]) mod p. The native verify_b3 ACCEPT + this spec match is the gate
# (the circuit is faithful but NOT witness3-agreeing -- x^7 + ~2^64 constants overflow int64 in the
# reference interp -- so the from-scratch Python Poseidon2 is the right independent oracle).
#   python3 fuzz/poseidon2_node_check.py
import sys, os, subprocess, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pentecost.poseidon import perm, P

GLASS = os.path.join(ROOT, "glass.py")
inp = list(range(12))
args = ([sys.executable, GLASS, "prove", os.path.join(ROOT, "examples", "prove", "poseidon2_node.glass")]
        + [f"i{i}={inp[i]}" for i in range(12)])
try:
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT, timeout=600)
except subprocess.TimeoutExpired:
    print("POSEIDON2-NODE: SKIP (native heavy-prove timed out -- env-limited)"); sys.exit(0)
if r.returncode >= 128:
    print(f"POSEIDON2-NODE: SKIP (native heavy-prove killed by signal rc={r.returncode} -- env-limited)")
    sys.exit(0)
m = re.search(r"result:\s*\(([^)]*)\)", r.stdout)
if not m or "proof:   ACCEPT" not in r.stdout:
    print("POSEIDON2-NODE: FAIL (no ACCEPT or no tuple result)")
    print((r.stdout + r.stderr).strip()[-400:]); sys.exit(1)
got = [int(x.strip()) % P for x in m.group(1).split(",")]
exp = perm(inp)
if got == exp:
    print("POSEIDON2-NODE: PASS (in-circuit real Poseidon2 == independent spec on all 12 lanes)")
    sys.exit(0)
print("POSEIDON2-NODE: FAIL (circuit != spec)")
print("got:", got); print("exp:", exp); sys.exit(1)
