"""Plonky3-exact Poseidon2 over Goldilocks (t=12, R_F=8, R_P=22, x^7), from scratch.
Independent re-implementation of the prove bridge's `perm`/`hashg` — plain Python int mod p,
NO Glass code. (v5.70.0: migrated Plonky2 v1 -> Poseidon2 in lock-step with the bridge.)

Poseidon2 (Plonky3 instance A): an external linear layer M_E = (4x4 MDS M4 on each 4-lane
chunk) + cross-chunk column sums, and an internal layer M_I = diag*x + sum; round schedule is
one bare M_E pre-multiply, 4 external rounds, 22 internal rounds (const+S-box on lane 0 only),
4 external rounds. S-box x^7. Matches Plonky3 goldilocks/src/poseidon2.rs (test_poseidon.py)."""
from ._gold_constants import RC_EI, RC_EF, RC_IN, DIAG

P = 2**64 - 2**32 + 1
M4 = [[2, 3, 1, 1], [1, 2, 3, 1], [1, 1, 2, 3], [3, 1, 1, 2]]   # Poseidon2 4x4 MDS

def _sbox(x): x2 = x*x % P; x4 = x2*x2 % P; x3 = x*x2 % P; return x3*x4 % P

def _mat4(c):
    # general 4x4 matrix-multiply (independent of the bridge's add-chain form)
    return [sum(M4[r][k] * c[k] for k in range(4)) % P for r in range(4)]

def _mext(st):
    # M4 on each of the 3 chunks, THEN add per-position column sums across chunks
    ch = [_mat4(st[4*c:4*c + 4]) for c in range(3)]
    flat = [ch[c][j] for c in range(3) for j in range(4)]
    colsum = [sum(ch[c][m] for c in range(3)) % P for m in range(4)]
    return [(flat[i] + colsum[i % 4]) % P for i in range(12)]

def _mint(st):
    s = sum(st) % P
    return [(DIAG[i] * st[i] + s) % P for i in range(12)]

def perm(st):
    st = _mext(list(st))                                   # bare external pre-multiply
    for r in range(4):                                     # 4 external rounds
        st = [(st[i] + RC_EI[r][i]) % P for i in range(12)]
        st = [_sbox(x) for x in st]; st = _mext(st)
    for r in range(22):                                    # 22 internal rounds (lane 0 only)
        st = list(st); st[0] = _sbox((st[0] + RC_IN[r]) % P); st = _mint(st)
    for r in range(4):                                     # 4 external rounds
        st = [(st[i] + RC_EF[r][i]) % P for i in range(12)]
        st = [_sbox(x) for x in st]; st = _mext(st)
    return st

def hashg(a_elems, b_elems):
    """2-to-1 sponge (rate 8 / capacity 4, permutation-agnostic): fill the t=12 state with
    (a ++ b) zero-padded, permute, squeeze the first 4 lanes (the digest)."""
    state = (list(a_elems) + list(b_elems) + [0] * 12)[:12]
    return perm(state)[:4]
