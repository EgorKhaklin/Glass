"""Plonky2-exact Poseidon over Goldilocks (t=12, R_F=8, R_P=22, x^7), from scratch.
Independent re-implementation of the prove bridge's `perm`/`hashg` (no Glass code).
Field = plain Python int mod p — genuinely independent of Glass's base-2^16 limbs."""
from ._gold_constants import ARC, CIRC

P = 2**64 - 2**32 + 1

def _sbox(x): x2 = x*x % P; x4 = x2*x2 % P; x3 = x*x2 % P; return x3*x4 % P

def _mds(st):
    out = []
    for r in range(12):
        acc = 0
        for i in range(12):
            acc = (acc + st[(i+r) % 12] * CIRC[i]) % P
        if r == 0:
            acc = (acc + st[0]*8) % P
        out.append(acc)
    return out

def _clayer(st, rc):
    return [(st[i] + ARC[12*rc + i]) % P for i in range(12)]

def _full_round(st, rc):
    st = _clayer(st, rc)
    st = [_sbox(x) for x in st]
    return _mds(st)

def _partial_round(st, rc):
    st = _clayer(st, rc)
    st = [_sbox(st[0])] + st[1:]          # S-box on lane 0 only
    return _mds(st)

def perm(st):
    st = list(st)
    for rc in range(0, 4):   st = _full_round(st, rc)       # 4 full
    for rc in range(4, 26):  st = _partial_round(st, rc)    # 22 partial
    for rc in range(26, 30): st = _full_round(st, rc)       # 4 full
    return st

def hashg(a_elems, b_elems):
    """2-to-1 sponge: fill the t=12 state with (a ++ b) elements, zero-padded; permute;
    return the first 4 elements (the 4-lane digest)."""
    state = (list(a_elems) + list(b_elems) + [0]*12)[:12]
    return perm(state)[:4]
