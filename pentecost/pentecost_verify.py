#!/usr/bin/env python3
"""Pentecost — a SECOND, independent verifier of Glass's zk-STARK.

Glass's compiler has two witnesses (glass.py <-> native_glassc); its cryptographic
verifier `verify_b3` (in examples/prove/prove_source_goldilocks_zk.glass) stood
ALONE. This is the second tongue: a from-scratch re-implementation of the SAME
verification algorithm in Python, sharing NO code with the Glass prover. It reads a
serialized proof + public gate list and re-derives every Fiat-Shamir challenge,
re-checks every gate identity, the PLONK grand product, the FRI low-degree test, and
the Merkle openings — returning ACCEPT / REJECT. Differential agreement with the
in-Glass verifier on the proof corpus is what "let the verifier be two" means.

Field = plain Python int mod p (Goldilocks). This is genuine independence: the Glass
side uses base-2^16 limb lists; nothing here touches that representation.

The Poseidon permutation (the only shared *spec*, not code) is validated byte-exact
against Plonky2's published vectors in poseidon.py — see test_poseidon.py.
"""
import sys
from .poseidon import P, perm, hashg   # hashg(a_elems, b_elems) -> 4-lane digest (list of 4 ints)

# ---------------------------------------------------------------- field (int mod p)
def fadd(a, b): return (a + b) % P
def fsub(a, b): return (a - b) % P
def fmul(a, b): return (a * b) % P
def finv(a):    return pow(a % P, P - 2, P)   # a^(p-2); 0 -> 0

# --------------------------------------------------------- F_{p^2} extension, u^2=7
NR = 7
def g2(a0, a1): return (a0 % P, a1 % P)
def gadd2(a, b): return ((a[0]+b[0]) % P, (a[1]+b[1]) % P)
def gsub2(a, b): return ((a[0]-b[0]) % P, (a[1]-b[1]) % P)
def gmul2(a, b): return ((a[0]*b[0] + NR*a[1]*b[1]) % P, (a[0]*b[1] + a[1]*b[0]) % P)
def gscale2(a, s): return ((a[0]*s) % P, (a[1]*s) % P)
def gconj(a): return (a[0], (-a[1]) % P)
def gnorm(a): return (a[0]*a[0] - NR*a[1]*a[1]) % P
def ginv2(a): return gscale2(gconj(a), finv(gnorm(a)))
def geq2(a, b): return a[0] % P == b[0] % P and a[1] % P == b[1] % P
def gpow2(a, e):
    r = (1, 0)
    while e > 0:
        if e & 1: r = gmul2(r, a)
        a = gmul2(a, a); e >>= 1
    return r
ONE2 = (1, 0)
def emb(x): return (x % P, 0)

# --------------------------------------------------------------------- size params
def ilog2(n): return 0 if n <= 1 else 1 + ilog2(n // 2)
def next_pow2(n, p=1):
    while p < n: p *= 2
    return p
def ng(gates):        return next_pow2(len(gates), 1)
def fri_dsize(d):     return 32 * d
def fri_final():      return 8
def fri_queries():    return 82
def fri_log(d):       return ilog2(d) + 5
def fri_layers(d):    return ilog2(fri_dsize(d) // fri_final())   # ilog2(4*d)
def root_pow2(k):     return pow(7, (P - 1) >> k, P)              # 2^k-th root of unity
def dom_powers(cur, g, k):
    out = []
    for _ in range(k): out.append(cur); cur = cur * g % P
    return out
def fri_coset(d):     return dom_powers(7, root_pow2(fri_log(d)), fri_dsize(d))
def sqd(dom, half):   return [dom[k]*dom[k] % P for k in range(half)]
def build_doms(dom, count):
    out, d = [], dom
    for _ in range(count): out.append(d); d = sqd(d, len(d)//2)
    return out

# ------------------------------------------------------- hash helpers + challenges
def lane0(h): return h[0]                       # first lane of a 4-lane digest
def absorb_g2(acc, gg): return hashg(hashg(acc, [gg[0]]), [gg[1]])
def absorb6(ts, *gs):
    for gg in gs: ts = absorb_g2(ts, gg)
    return ts
def absorb_final(acc, fin):
    for gg in fin: acc = hashg(hashg(acc, [gg[0]]), [gg[1]])
    return acc
def _chal(ts, t0, t1): return (lane0(hashg(ts, [t0])), lane0(hashg(ts, [t1])))
def beta_p_of(ts):     return _chal(ts, 221, 222)
def gam_p_of(ts):      return _chal(ts, 223, 224)
def alpha_of(ts):      return _chal(ts, 231, 232)
def ood_of(ts):        return _chal(ts, 201, 202)
def gamma_of(ts):      return _chal(ts, 211, 212)
def beta_of_seed_g(ts):return _chal(ts, 101, 102)
def rederive_betas(roots, tseed):
    out, ts = [], tseed
    for r in roots: ts = hashg(ts, r); out.append(beta_of_seed_g(ts))
    return out
def seed_from_roots(roots, tseed):
    ts = tseed
    for r in roots: ts = hashg(ts, r)
    return ts

# ---------------------------------------------------------------- statement digest
# A gate is a tuple: ('const',o,c) / ('add'|'sub'|'mul',o,a,b) / ('hint',o) / ('eq',a)
def gate_dig(g, acc):
    k = g[0]
    if k == 'const': return hashg(hashg(hashg(acc, [1]), [g[1]]), [g[2]])
    if k == 'add':   return hashg(hashg(hashg(hashg(acc, [2]), [g[1]]), [g[2]]), [g[3]])
    if k == 'sub':   return hashg(hashg(hashg(hashg(acc, [3]), [g[1]]), [g[2]]), [g[3]])
    if k == 'mul':   return hashg(hashg(hashg(hashg(acc, [4]), [g[1]]), [g[2]]), [g[3]])
    if k == 'hint':  return hashg(hashg(acc, [5]), [g[1]])
    if k == 'eq':    return hashg(hashg(acc, [6]), [g[1]])
    raise ValueError(g)
def stmt_seed_of(gates):
    seed0 = hashg(hashg(hashg(hashg(hashg([2718281], [7]), [fri_dsize(1)]), [fri_final()]),
                        [fri_queries()]), [12])
    acc = seed0
    for g in gates: acc = gate_dig(g, acc)
    return acc

# ------------------------------------------------------------- INTT (interpolation)
def interp_n(ev, n):
    """Inverse NTT: coefficients of the degree-<n polynomial interpolating `ev` on
    the n-th roots of unity. coeff[k] = ni * sum_j ev[j] * wi^((j*k) mod n)."""
    omega = root_pow2(ilog2(n)); wi = finv(omega); ni = finv(n)
    # precompute wi powers
    wp = [1]*(n)
    for i in range(1, n): wp[i] = wp[i-1]*wi % P
    out = []
    for k in range(n):
        acc = 0
        for j in range(n):
            acc = (acc + ev[j] * wp[(j*k) % n]) % P
        out.append(acc * ni % P)
    return out
def lpad(xs, n): return list(xs) + [0]*(n - len(xs))
def icol(col, n): return interp_n(lpad(col, n), n)

# ------------------------------------------------------ public selector + perm cols
def public_cols(gates, n):
    qa = [1 if g[0]=='add'   else 0 for g in gates]
    qm = [1 if g[0]=='mul'   else 0 for g in gates]
    qs = [1 if g[0]=='sub'   else 0 for g in gates]
    qc = [1 if g[0]=='const' else 0 for g in gates]
    qe = [1 if g[0]=='eq'    else 0 for g in gates]
    c  = [g[2] if g[0]=='const' else 0 for g in gates]
    return [icol(qa,n), icol(qm,n), icol(qs,n), icol(qc,n), icol(qe,n), icol(c,n)]

def gate_cells(g, i, n):
    k = g[0]
    if k in ('add','sub','mul'): return [(i, g[2]), (n+i, g[3]), (2*n+i, g[1])]
    if k == 'const':            return [(2*n+i, g[1])]
    if k == 'hint':             return [(2*n+i, g[1])]
    if k == 'eq':               return [(i, g[1])]
    raise ValueError(g)
def all_cells(gates, n):
    cells = []
    for i, g in enumerate(gates): cells += gate_cells(g, i, n)
    return cells
def wire_of(cid, cells):
    for c, w in cells:
        if c == cid: return w
    return -1
def sigma(cid, cells):
    w = wire_of(cid, cells)
    if w < 0: return cid
    grp = [c for (c, ww) in cells if ww == w]
    idx = grp.index(cid)
    return grp[(idx + 1) % len(grp)]
def perm_cols(gates, n):
    cells = all_cells(gates, n)
    id1 = [i        for i in range(n)]
    id2 = [n+i      for i in range(n)]
    id3 = [2*n+i    for i in range(n)]
    s1  = [sigma(i,     cells) for i in range(n)]
    s2  = [sigma(n+i,   cells) for i in range(n)]
    s3  = [sigma(2*n+i, cells) for i in range(n)]
    return [icol(id1,n), icol(id2,n), icol(id3,n), icol(s1,n), icol(s2,n), icol(s3,n)]

# ------------------------------------------------------------ gate identity at z
def poly_eval_g(coeffs, z):
    acc = (0, 0)
    for c in reversed(coeffs): acc = gadd2(emb(c), gmul2(z, acc))
    return acc
def zh_g(z, n): return gsub2(gpow2(z, n), ONE2)
def g_at_z(pc, lz, rz, oz, z):
    va = poly_eval_g(pc[0], z); vm = poly_eval_g(pc[1], z); vs = poly_eval_g(pc[2], z)
    vc = poly_eval_g(pc[3], z); vqe = poly_eval_g(pc[4], z); vk = poly_eval_g(pc[5], z)
    t  = gmul2(va, gsub2(oz, gadd2(lz, rz)))
    t  = gadd2(t, gmul2(vm, gsub2(oz, gmul2(lz, rz))))
    t  = gadd2(t, gmul2(vs, gsub2(oz, gsub2(lz, rz))))
    t  = gadd2(t, gmul2(vc, gsub2(oz, vk)))
    t  = gadd2(t, gmul2(vqe, lz))
    return t
def pf(val, idv, beta, gam): return gadd2(val, gadd2(gmul2(beta, idv), gam))
def recur_at_z(pm, lz, rz, oz, zz, zwz, beta, gamp, z):
    id1=poly_eval_g(pm[0],z); id2=poly_eval_g(pm[1],z); id3=poly_eval_g(pm[2],z)
    s1=poly_eval_g(pm[3],z);  s2=poly_eval_g(pm[4],z);  s3=poly_eval_g(pm[5],z)
    numz = gmul2(gmul2(pf(lz,id1,beta,gamp), pf(rz,id2,beta,gamp)), pf(oz,id3,beta,gamp))
    denz = gmul2(gmul2(pf(lz,s1, beta,gamp), pf(rz,s2, beta,gamp)), pf(oz,s3, beta,gamp))
    return gsub2(gmul2(zwz, denz), gmul2(zz, numz))
def qcombined_z(pc, pm, lz, rz, oz, zz, zwz, beta, gamp, alpha, z, n):
    izh  = ginv2(zh_g(z, n))
    qg   = gmul2(g_at_z(pc, lz, rz, oz, z), izh)
    qr   = gmul2(recur_at_z(pm, lz, rz, oz, zz, zwz, beta, gamp, z), izh)
    qb   = gmul2(gsub2(zz, ONE2), ginv2(gsub2(z, ONE2)))
    return gadd2(qg, gadd2(gmul2(alpha, qr), gmul2(gmul2(alpha, alpha), qb)))

# ----------------------------------------------------------- Merkle + FRI queries
def lhash(gg): return hashg(hashg([7], [gg[0]]), [gg[1]])
def comb_lro(l, r, o): return hashg(hashg([l], [r]), [o])
def fold_path(h, index, path):
    for s in path:
        h = hashg(h, s) if index % 2 == 0 else hashg(s, h)
        index //= 2
    return h
def merkle_verify_h(leaf, index, path, root): return fold_path(leaf, index, path) == root
def merkle_verify_g(leaf, index, path, root): return fold_path(lhash(leaf), index, path) == root
def fold_pair2(fx, fmx, x, beta, finv2):
    even = gscale2(gadd2(fx, fmx), finv2)
    odd  = gscale2(gsub2(fx, fmx), finv(2*x % P))
    return gadd2(even, gmul2(beta, odd))
def deep_batch_b3(l, r, o, q, z_, xi, lz, rz, oz, qz, zz, zwz, z, wz, gamd):
    invz  = ginv2(gsub2(emb(xi), z))
    invwz = ginv2(gsub2(emb(xi), wz))
    dq  = gmul2(gsub2(q, qz), invz)
    dl  = gmul2(gsub2(emb(l), lz), invz)
    dr  = gmul2(gsub2(emb(r), rz), invz)
    dlo = gmul2(gsub2(emb(o), oz), invz)
    dz  = gmul2(gsub2(z_, zz), invz)
    dzw = gmul2(gsub2(z_, zwz), invwz)
    g = gamd; g2_=gmul2(g,g); g3=gmul2(g2_,g); g4=gmul2(g3,g); g5=gmul2(g4,g)
    t = dq
    t = gadd2(t, gmul2(g,  dl)); t = gadd2(t, gmul2(g2_, dr)); t = gadd2(t, gmul2(g3, dlo))
    t = gadd2(t, gmul2(g4, dz)); t = gadd2(t, gmul2(g5, dzw))
    return t
def vq(oq, roots, betas, doms, final, p, finv2):
    for layer in range(len(oq)):
        lx, lmx, plx, plmx = oq[layer]
        dom = doms[layer]; half = len(dom)//2; j = p % half
        if layer == len(oq)-1:
            nextv = final[j]
        else:
            next_half = len(doms[layer+1])//2
            nxt = oq[layer+1]
            nextv = nxt[0] if j < next_half else nxt[1]
        if not merkle_verify_g(lx,  j,        plx,  roots[layer]): return False
        if not merkle_verify_g(lmx, j+half,   plmx, roots[layer]): return False
        folded = fold_pair2(lx, lmx, dom[j], betas[layer], finv2)
        if not geq2(folded, nextv): return False
        p = j
    return True
def vb3_q1(boq, toq, root1, root2, root3, broots, betas, doms, bfinal, coset,
           lz, rz, oz, qz, zz, zwz, z, wz, gamd, m, p, lyrs, finv2):
    half = m // 2; j = p % half
    (lj,rj,oj,qj,zj, p1j,p3j,p2j, ljh,rjh,ojh,qjh,zjh, p1jh,p3jh,p2jh) = toq
    if not merkle_verify_h(comb_lro(lj,rj,oj),   j,      p1j,  root1): return False
    if not merkle_verify_h(comb_lro(ljh,rjh,ojh), j+half, p1jh, root1): return False
    if not merkle_verify_g(qj, j, p3j, root3) or not merkle_verify_g(qjh, j+half, p3jh, root3): return False
    if not merkle_verify_g(zj, j, p2j, root2) or not merkle_verify_g(zjh, j+half, p2jh, root2): return False
    bj  = deep_batch_b3(lj, rj, oj, qj, zj,    coset[j],      lz,rz,oz,qz,zz,zwz, z,wz,gamd)
    bjh = deep_batch_b3(ljh,rjh,ojh,qjh,zjh,   coset[j+half], lz,rz,oz,qz,zz,zwz, z,wz,gamd)
    blx, blmx = boq[0][0], boq[0][1]
    if not (geq2(bj, blx) and geq2(bjh, blmx)): return False
    if len(boq) != lyrs: return False
    return vq(boq, broots, betas, doms, bfinal, p, finv2)
def vb3_qs(bopen, topen, root1, root2, root3, broots, betas, doms, bfinal, coset,
           lz, rz, oz, qz, zz, zwz, z, wz, gamd, m, queries, lyrs, finv2):
    if not (len(bopen) == len(topen) == len(queries)): return False
    for boq, toq, p in zip(bopen, topen, queries):
        if not vb3_q1(boq, toq, root1, root2, root3, broots, betas, doms, bfinal, coset,
                      lz, rz, oz, qz, zz, zwz, z, wz, gamd, m, p, lyrs, finv2): return False
    return True

# --------------------------------------------------------- query sampling + grind
def q_low(h, dsize):  return (lane0(h) & 0xFFFF) % dsize
def sample_distinct(seed, need, ctr, acc, dsize):
    while need > 0 and len(acc) < dsize:
        q = q_low(hashg(seed, [ctr]), dsize)
        if q not in acc: acc.append(q); need -= 1
        ctr += 1
    return acc
def sample_queries_g(seed, count, dsize): return sample_distinct(seed, count, 1, [], dsize)
def pow_ok(ground): return (lane0(ground) & 0xFFFF) % 4096 == 0
def is_const2(cw):  return all(geq2(x, cw[0]) for x in cw) if cw else True

# --------------------------------------------------------------------- verify_b3
def verify_b3(gates, proof):
    (root1, root2, root3, lz, rz, oz, qz, zz, zwz, broots, bfinal, nonce, bopen, topen) = proof
    n = ng(gates); m = fri_dsize(n); coset = fri_coset(n); lyrs = fri_layers(n)
    omega = root_pow2(ilog2(n))
    stmt = stmt_seed_of(gates); pc = public_cols(gates, n); pm = perm_cols(gates, n)
    ts1 = hashg(stmt, root1); beta = beta_p_of(ts1); gamp = gam_p_of(ts1)
    ts2 = hashg(ts1, root2);  alpha = alpha_of(ts2)
    ts3 = hashg(ts2, root3);  z = ood_of(ts3); wz = gmul2(z, emb(omega))
    ts4 = absorb6(ts3, lz, rz, oz, qz, zz, zwz); gamd = gamma_of(ts4)
    betas = rederive_betas(broots, ts4)
    base_seed = absorb_final(seed_from_roots(broots, ts4), bfinal)
    ground = hashg(base_seed, [nonce])
    doms = build_doms(coset, lyrs)
    queries = sample_queries_g(ground, fri_queries(), fri_dsize(n))
    id_ok = geq2(qz, qcombined_z(pc, pm, lz, rz, oz, zz, zwz, beta, gamp, alpha, z, n))
    struct_ok = (len(broots) == lyrs and len(bfinal) == fri_final()
                 and len(bopen) == fri_queries() and len(topen) == fri_queries()
                 and pow_ok(ground) and is_const2(bfinal))
    if not (id_ok and struct_ok): return (False, id_ok, struct_ok)
    qok = vb3_qs(bopen, topen, root1, root2, root3, broots, betas, doms, bfinal, coset,
                 lz, rz, oz, qz, zz, zwz, z, wz, gamd, m, queries, lyrs, finv(2))
    return (id_ok and struct_ok and qok, id_ok, struct_ok and qok)

# ---------------------------------------------------------------- proof parser
def parse(path):
    toks = iter(open(path).read().split())
    rd = lambda: int(next(toks))
    def rd_fe():
        n = rd(); limbs = [rd() for _ in range(n)]
        return sum(l << (16*i) for i, l in enumerate(limbs)) % P
    def rd_g2(): return (rd_fe(), rd_fe())
    def rd_hash(): return [rd_fe() for _ in range(4)]    # a digest = 4 lanes
    def rd_path():
        n = rd(); return [rd_hash() for _ in range(n)]
    def rd_qopen(): return (rd_g2(), rd_g2(), rd_path(), rd_path())
    def rd_layerlist():
        n = rd(); return [rd_qopen() for _ in range(n)]
    def rd_bopen():
        n = rd(); return [rd_layerlist() for _ in range(n)]
    def rd_topenb():
        return (rd_fe(),rd_fe(),rd_fe(), rd_g2(), rd_g2(), rd_path(),rd_path(),rd_path(),
                rd_fe(),rd_fe(),rd_fe(), rd_g2(), rd_g2(), rd_path(),rd_path(),rd_path())
    def rd_topen():
        n = rd(); return [rd_topenb() for _ in range(n)]
    def rd_g2list():
        n = rd(); return [rd_g2() for _ in range(n)]
    def rd_roots():
        n = rd(); return [rd_hash() for _ in range(n)]
    assert next(toks) == 'GATES'
    ng_ = rd(); gates = []
    for _ in range(ng_):
        t = rd()
        if t == 1:   gates.append(('const', rd(), rd_fe()))
        elif t == 2: gates.append(('add', rd(), rd(), rd()))
        elif t == 3: gates.append(('sub', rd(), rd(), rd()))
        elif t == 4: gates.append(('mul', rd(), rd(), rd()))
        elif t == 5: gates.append(('hint', rd()))
        elif t == 6: gates.append(('eq', rd()))
        else: raise ValueError(t)
    assert next(toks) == 'PROOF'
    root1, root2, root3 = rd_hash(), rd_hash(), rd_hash()
    lz, rz, oz, qz, zz, zwz = rd_g2(), rd_g2(), rd_g2(), rd_g2(), rd_g2(), rd_g2()
    broots = rd_roots(); bfinal = rd_g2list(); nonce = rd()
    bopen = rd_bopen(); topen = rd_topen()
    proof = (root1, root2, root3, lz, rz, oz, qz, zz, zwz, broots, bfinal, nonce, bopen, topen)
    return gates, proof

if __name__ == '__main__':
    gates, proof = parse(sys.argv[1])
    ok, id_ok, q_ok = verify_b3(gates, proof)
    print("PENTECOST: " + ("ACCEPT" if ok else "REJECT") +
          f"   (gate-identity={'ok' if id_ok else 'FAIL'}, fri/struct={'ok' if q_ok else 'FAIL'})")
    sys.exit(0 if ok else 1)
