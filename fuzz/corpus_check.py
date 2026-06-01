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

corpus = sorted(glob.glob(os.path.join(_root, "pentecost", "corpus", "*.b3.txt*")))
assert corpus, "no corpus fixtures under pentecost/corpus/"
fails = []
for path in corpus:
    name = os.path.basename(path)
    toks = load_tokens(path)
    pi = toks.index("PROOF")
    if not accepts(toks):
        fails.append(f"{name}: honest proof REJECTED"); continue
    t = toks[:]; t[pi + 1] = str(int(t[pi + 1]) + 1)        # proof-region tamper (+1, never a no-op)
    if accepts(t):
        fails.append(f"{name}: PROOF tamper wrongly ACCEPTED")
    t = toks[:]; t[pi - 1] = str(int(t[pi - 1]) + 1)        # claim-region tamper (last gate token)
    if accepts(t):
        fails.append(f"{name}: CLAIM tamper wrongly ACCEPTED")
print(f"CORPUS: {len(corpus)} fixtures (honest ACCEPT + proof/claim tamper REJECT), {len(fails)} failures"
      + (f"  !! {fails}" if fails else ""))
sys.exit(0 if not fails else 1)
