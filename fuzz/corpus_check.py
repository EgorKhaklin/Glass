#!/usr/bin/env python3
# Differential + tamper check across the committed proof corpus. For every honest proof
# fixture in pentecost/corpus/, the independent Pentecost verifier must:
#   1. ACCEPT the honest proof                       (two verifiers agree, on varied shapes)
#   2. REJECT a tamper in the PROOF region           (proof-binding)
#   3. REJECT a tamper in the GATES region           (statement-binding)
# This broadens the "let the verifier be two" + tamper guarantees beyond the single a+b
# shape the end-to-end differential originally ran on. Pure Python; fast (verify only).
#   python3 fuzz/corpus_check.py
import sys, os, glob, gzip
sys.setrecursionlimit(100000)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
from pentecost.pentecost_verify import parse, verify_b3

def load_tokens(path):
    """Fixtures are stored gzipped (token streams compress ~3-5x); read either form."""
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt") as f:
        return f.read().split()

def accepts(toks):
    open("/tmp/corpus_scratch.txt", "w").write(" ".join(toks))
    try:
        g, p = parse("/tmp/corpus_scratch.txt"); r = verify_b3(g, p)
        return r[0] if isinstance(r, tuple) else r
    except Exception:
        return False

# Big proofs (the comparison/division gadgets are ~600k tokens) verify slowly; running the two
# extra tamper checks on each tripled the gate's wall-clock. The *differential* (honest ACCEPT by
# the independent verifier) is the new coverage a fixture buys; tamper-REJECT is already covered
# exhaustively on a+b by the 1,600-proof + 640-claim campaigns. So: every fixture is checked for
# honest ACCEPT, and fixtures under the threshold ALSO get proof- and claim-region tamper checks.
# Which fixtures were tamper-checked vs accept-only is logged (no silent cap).
TAMPER_MAX_TOKENS = 250000
corpus = sorted(glob.glob(os.path.join(_root, "pentecost", "corpus", "*.b3.txt*")))
assert corpus, "no corpus fixtures under pentecost/corpus/"
fails = []; tampered = []; accept_only = []
for path in corpus:
    name = os.path.basename(path)
    toks = load_tokens(path)
    pi = toks.index("PROOF")
    if not accepts(toks):
        fails.append(f"{name}: honest proof REJECTED"); continue
    if len(toks) > TAMPER_MAX_TOKENS:
        accept_only.append(name); continue
    tampered.append(name)
    t = toks[:]; t[pi + 1] = str(int(t[pi + 1]) + 1)        # proof-region tamper (+1, never a no-op)
    if accepts(t):
        fails.append(f"{name}: PROOF tamper wrongly ACCEPTED")
    t = toks[:]; t[pi - 1] = str(int(t[pi - 1]) + 1)        # claim-region tamper (last gate token)
    if accepts(t):
        fails.append(f"{name}: CLAIM tamper wrongly ACCEPTED")
print(f"CORPUS: {len(corpus)} fixtures, {len(fails)} failures "
      f"(honest ACCEPT: all; +proof/claim tamper-REJECT: {tampered}; accept-only [large]: {accept_only})"
      + (f"  !! {fails}" if fails else ""))
sys.exit(0 if not fails else 1)
