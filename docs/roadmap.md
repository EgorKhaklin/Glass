# Glass Roadmap — toward the verifiable frontier language

*(written thinking as Glass — current as of v5.110.0)*

## What Glass is

- A pure functional language: ADTs, records, tuples, HM inference, refinement
  types, effect rows, linear types, pattern matching.
- **Self-hosting**: `native_glassc` compiles itself and `prism` byte-identically,
  with no Python in the loop (the bootstrap fixpoint, closed at v4.76 and still green).
- **ZK-native**: write a real Glass function — arithmetic, comparison, division,
  signed integers, **strings**, **records** — and get a zero-knowledge proof of its
  result. The structured-data shapes lower through the prove bridge today, not as a
  library you assemble by hand.
- **Proven in anger**: Pane (a query algebra) and Frost (a from-scratch zk-STARK
  — field, hashes, Merkle trees, arithmetization, FRI, AIR) — all written in Glass,
  all self-hosted.
- **A discipline, not just a language**: every layer is a *reference semantics* plus
  a *compiler* that must agree bit-for-bit, kept honest by differential testing.
  glass.py ⟷ quartz/glassc. eval ⟷ circuit. run_query ⟷ Frost.

## The frontier bet

Most languages optimize for one of: expressiveness, performance, or proof. Glass's
distinctive position is the *seam* it already lives on — reference ⟷ compiler
agreement — generalized to: **spec, implementation, and proof in one self-hosting
language.**

The unique edge: **ZK-native computation** — write a Glass function, get a
zero-knowledge proof of its execution. No mainstream functional language does this.
Glass already built the whole STARK toolkit; the bet is to make it a language
feature, not a library you assemble by hand.

> **Thesis — Glass, the verifiable functional language.** You write what a program
> *means*, what it *does*, and you get a machine-checkable proof it did.

## Honest scope (the standing boundary)

Everything below is **research / educational-grade and UNAUDITED**. The verifier is
sound by a pen-and-paper reduction and re-checked by a second independent
implementation and the reference interpreter — but **both verifiers descend from the
same public specs**, so a shared spec misread would fool both. Production-readiness
requires an **external professional audit + Poseidon cryptanalysis** — a hard
boundary that can never be produced inside this repo. Until it is crossed externally,
the **do-not-protect-real-value** banner stays. This is not a disclaimer bolted on;
it is part of the design, repeated at every layer.

---

## Where Glass is now (v5.110)

Four things are real and self-hosted. The detail for any line lives in
[`CHANGELOG.md`](../CHANGELOG.md); this is the map.

### 1 · The prove bridge — real Glass source → a sound zk-STARK

`glass prove <file.glass> a=… b=…` parses real prism source, lowers it to a Goldilocks
(`p = 2⁶⁴ − 2³² + 1`) gate circuit, proves it, and **independently verifies it** —
keeping the inputs private and revealing only the result. The recurring **cut** behind
almost every capability: *express the new operation in terms of already-lowered
primitives* (a multiply/add, the range gadget, the multi-wire value model) so it needs
**no new gate type and no change to the verifier**. What lowers today:

- **Arithmetic** `+ − *` (over the canonical field; negatives bind canonically as `p−|v|`).
- **Unsigned comparison** `< > <= >=` over `[0, 2³²)` — a bit-decomposition range gadget
  (range-prove both operands, read the sign bit of `d = a−b+2³²`). *v5.62.*
- **Integer division & modulo** `/ %` over `[0, 2³²)` — not a primitive: the identity
  `a = b·q + r, 0 ≤ r < b` with `q,r` advice pinned by the range gadget (and `r < b`
  forcing `b ≠ 0` as a circuit fact). Dead-branch divide-by-zero predicated to ACCEPT
  the live result. *v5.84, v5.88.*
- **Signed integers** over `[−2³¹, 2³¹)` — `slt/sle/sgt/sge` (desugar to the unsigned
  gadget with a monotonic `+2³¹` offset), `sdiv/smod` (C99 truncated; sign-magnitude
  composed from `slt` + `if` + unsigned divmod — the naive sign-bit design was
  adversarially proven unsound), and `sabs/smin/smax`. *v5.94–v5.100.*
- **Bitwise logic** `bit_and/bit_or/bit_xor` over `[0, 2³²)` — decompose both operands into
  boolean-pinned bits (reusing the range gadget), combine per position (AND `a·b`, OR `a+b−ab`,
  XOR `(a−b)²`), recompose; out-of-range ABSTAINs. *v5.116.*
- **Strings** — a string is a multi-wire value (one field wire per codepoint), so
  `++` is structural concat (no gate), `==`/`!=` the AND-folded per-codepoint is-zero
  gadget, `string_length`/`substring` static wire counts/slices, and `match` on string
  literals an allowlist dispatch — all over a **private** string. *v5.101–v5.102.*
- **Records** — construct (`Account { … }`), destructure (`match a { Account { … } }`),
  and field access (`a.balance`), lowering like a tagless tuple. *v5.103–v5.104.*
- **Structured results** — a proof can *return* a string (*v5.110*), or a **tuple/record**
  of scalar components (*v5.117*), bound by pinning every output wire as the public claim
  (`build_claim_mw`) and decoded/displayed (a key's revealed prefix; a verdict word; a
  `divmod` revealing `(q, r)`; a record `Bounds { lo, hi }`). Scalar/string/tuple/record —
  what a proof can return is complete; a non-scalar tuple component ABSTAINs.

- **Computed (runtime-chosen) callees** — `(if c then g else h)(x)`, the callee selected at
  runtime, lower by pushing the application inside the selector (`if c then g(x) else h(x)`).
  Named-fn callees already proved (*v5.87*); with this the bridge has **no refused call form**. *v5.113.*

Anything the bridge cannot lower **faithfully** *abstains* loudly — it is never silently proven.
(Still refused: unequal-width string `if`-branches, multi-wire non-string public claims, and a wider
comparison range — see *What's open*.)

### 2 · The verification stack — three independent lineages

The proof is checked by three lineages that fail in different ways, so a bug in one is
caught by the others (detailed in *The instruments*, below):

- **`verify_b3`** — an in-bridge, **witness-free** verifier (per-row gate soundness +
  PLONK grand-product wire consistency + public-input pinning), ~80-bit provable, the
  CLI default. *v5.48.*
- **Pentecost** — a *second*, non-Glass re-verifier (`pentecost/`, plain Python int-mod-p,
  sharing no Glass code). `glass prove --emit` writes a portable proof; `glass verify`
  checks it. *v5.64 / v5.74.*
- **The Third Witness** — `glass prove --witness3` re-executes the source under the
  reference interpreter (a lineage independent of *both* the bridge's evaluator and its
  circuit lowering) and binds the public result, catching a source↔circuit gap two STARK
  verifiers structurally cannot. *v5.71.*
- **Differential fuzzing** (`fuzz/`) exercises all of the above on random programs across
  five families (arithmetic, comparison, signed, string, record) and adversarial
  single-token tampers — thousands of forged proofs, zero wrong-ACCEPTs. *v5.75+.*

### 3 · The cryptographic core (Frost)

Built from scratch and self-hosted: **Goldilocks** with its division-free reduction and
2³²-th root of unity; the **F_{p²} ≈ 2¹²⁸** extension as the FRI challenge space;
**Poseidon2** (Plonky3-exact) as the in-STARK hash, migrated in lock-step across both
verifiers (*v5.70*); committed + query-verified **FRI**; a **PLONK grand-product**
permutation argument; and **zero-knowledge** via a randomized trace. Every layer is
int64-safe (base-2¹⁶ limbs) so Python bignum ≡ C int64 and it dogfoods. The **Measuring
Reed** (*v5.63*) prints the live bit-security on every ACCEPT, re-derived from the actual
circuit's params — not asserted in prose.

### 4 · Self-hosting

The bootstrap fixpoint (`examples/selfhost/bootstrap_fixpoint.sh`) proves source-level
self-reproduction: `native_glassc` compiles its own source (`glassc.glass`) and `prism`
to **byte-identical emitted C** (1151 lines) and byte-identical program output (192 demo
lines), with `gen1 == gen2`. `glass.py`/`quartz.py` are now only the reference interpreter
and the one-time bootstrap. The honest **dialect scope** (interpreter-only surface
features: `|>`, `import`, nullary `f()`, a few runtime builtins) produces *clean compile
errors*, never silent desyncs (see [`self-hosting.md`](self-hosting.md)).

*The test suite is `python tests/test_glass.py` (not pytest); the heavy fixpoint +
native-difftest byte-identity checks run separately. Suite **453/453**; Name `259e98cf…`.*

---

## What's open — ranked (as of v5.110)

Ranked by value × tractability for a builder choosing the next session. Items 1–4 are
buildable next-session work; 5–6 are large/gated; 7–8 are rigor and the hard boundary.

0. **Soundness hardening — audit holes A, B, C: ✅ ALL CLOSED (v5.129–v5.130).** A v5.128 read-only
   audit ([memory `project_bridge_soundness_audit`]) found three silent wrong-ACCEPTs caught only by
   `--witness3` (the `ctag` class). **A** (substring over-read) + **C** (vacuous scalar-claim bind):
   fixed v5.129. **B** (fixed-width layout overflow): fixed v5.130 — a recursive-ADT value can be *wider*
   than its `twidth` slot (`twidth` decrements fuel per level while construction pads flat), so a field
   *following* a recursive field was read at a shifted offset → silent `0` (`second(MkPair(Cons(7,Nil),
   inp))` proved `0`); now `cgen_fields`/`heval_fields`/`seval_fields` ABSTAIN on a **non-last** over-width
   field (benign-when-last, so the head-reading fold `map_prove` still ACCEPTs 13). Sibling: a `String`
   field in a record/ADT/tuple (no fixed wire width) now ABSTAINs in `twidth`. *Residual (deferred, not a
   wrong-ACCEPT — it ABSTAINs):* truly **supporting** these layouts (fuel-threaded layout so a recursive
   field can precede another, or an embedded String) is a larger feature; today they are safe-by-refusal.
   `scalar_types_e/_p` hardcode `TyInt` per tuple element — a tuple with a *non-last* variable-width
   element is caught by the over-width guard; a *last* one is the same deferred "support it" feature.
   **Forgery-resistance audit (2026-06-10): clean — 0 structural gaps.** A complementary read-only sweep
   (can a *cheating* prover get a false statement ACCEPTed?) over gate-constraint enforcement, range/divmod
   advice-pinning, public binding, Fiat-Shamir order, and two-verifier lockstep found **no** structural
   forgery path: the DEEP-ALI binding (`id_ok` + per-query deep-tie + FRI low-degree test), grand-product
   closure (transition on all rows incl. wrap), bit-decomposition pinning, and claim binding are all sound
   and lockstep-identical. Residual risk is **cryptanalytic** (FRI proximity-gap margin, Poseidon2
   collision-resistance) — the external audit (#10), not structural. **Its one defense-in-depth finding
   is ✅ CLOSED (v5.131):** `divmod_build`'s `b=0` dead-branch left the quotient advice `q` FREE in
   [0,2^32) (the `r<b` assert is predicated on the in-circuit `nz` bit and goes vacuous at `b=0`) —
   soundness leaned on the *external* `gref_m_checked` (seval+heval refuse a live `b=0`). The predicated
   pin `isz·q == 0` now makes the `b=0` witness UNIQUE in-circuit (`q=0, r=a`, matching heval's totalized
   `a/0=0, a%0=a`), so no future call path reaching `verify_b3` can ride the freedom. Gated by a real
   forged-prover suite gate: a malicious bridge copy hinting `q=7` (internally consistent everywhere
   else, via the new `GLASS_BRIDGE_DIR` harness hook) ACCEPTed pre-fix and REJECTs now.
   **Inlining capture: ✅ CLOSED (v5.132).** Gating v5.131 surfaced (via the Third Witness, exactly as
   designed) that `inline_fn`'s sequential ELet binding **captured**: in `gcd(b, a % b)` the `a` inside
   `a % b` bound to the just-inlined parameter, so the circuit attested `gcd(48,18) = 18` vs the source's
   6 — STARK-valid wrong lowering (heval+cgen shared the captured unroll; seval and the reference both
   computed 6). Fixed by two-phase capture-avoiding binding (caller-fenv arg resolution + `q9p_` temps,
   value AND fn namespaces); capture-free programs lower byte-identically (corpus differential). A
   `--cross-check` DIVERGENCE now **exits 3** (was: printed, exit 0). Gates: capture shape 307+AGREES,
   regressed-capture bridge → DIVERGENCE + rc 3, gcd headline 6+AGREES.

1. **LogUp in-circuit range integration — *the headline frontier*** *(large;
   soundness-critical; multi-session).* Replace the bridge's per-operand bit-decomposition
   range gadget (`range_k`/`lt_build`, ~600k-token comparison/division proofs) with a
   **LogUp (log-derivative) lookup** — shrinking every comparison/division proof toward
   the ~150k arithmetic class, widening the provable range (frontier #2), and unblocking
   H3's per-node hashing (#5). The **standalone arc is fully landed and de-risked**
   ([`frost_logup.glass`](../examples/frost/frost_logup.glass) identity over a *dense*
   literal table, [`…_air.glass`](../examples/frost/frost_logup_air.glass) the
   constrained running-sum/AIR form, [`…_committed.glass`](../examples/frost/frost_logup_committed.glass)
   commit-then-challenge Fiat-Shamir β; *v5.105–v5.107*). The remaining work is **careful
   execution, not exploration**: wire a *constrained* running-sum column + advice-pinned
   multiplicities into `range_k`/`lt_build`, with β re-derived **identically** in both
   `verify_b3` AND Pentecost (mirror the existing `z_build`/`build_q_b3` grand-product
   quotient). Two recorded hazards it MUST close: the **sparse-table self-cancellation**
   hole (closed by a dense literal table) and the **forged-`S≡0` fools a boundary-only
   check** hazard (closed by the cleared-denominator transition constraint). Explicitly
   *not* tail-of-context work — a dedicated focused session.
   - **✅ DESIGN PHASE DONE** ([`logup-integration-design.md`](logup-integration-design.md), grounded +
     adversarially red-teamed). It **reframed the goal**: a LogUp lookup is an **amortized** win (the
     dense table is one trace row per table entry, so it shrinks circuits with *many* range-checks —
     deep `divmod`/`gcd`, H3 hashing — but is a *regression* for a single comparison; `range_k` stays
     as the large-`k` fallback behind a `k`-sizing guard). The red-team killed three would-be forgeries
     on paper (an unconstrained comparison-result wire, a degree-broken `S_N=0` boundary, an out-of-range
     escape) and showed the change is **≈12 lockstep sites** that must land in **ordered stages** (S
     column → multiplicity + `GLookup` marker → wire the gadget), each its own verified changeset, with
     a **Stage 0 GO/NO-GO** on the table representation. The design doc is the executable plan.
   - **🟠 STAGE 0 DONE → DEFER (2026-06-04).** A *measured* cost analysis settled the GO/NO-GO: a
     baseline `a+b` proof is **154,842 tokens**, one comparison `a<b` is **552,366** (the ~693-gate range
     gadget, +397k). The dense table is `2^k` trace rows paid once, so LogUp's break-even is `≈ 2^k/693`
     range-checks (~6–20 at small `k`, ~95 at `k=16`). Two facts: **(a)** the single comparison (`N=1`,
     essentially every current proof) is *never* helped — it stays on `range_k`; **(b)** no current
     workload (max ~dozens, mostly the semantics-gated `gcd`) crosses break-even, so building it now
     **regresses every routine proof**. So: **keep `range_k`, defer Stages 1–3.** Trigger to execute:
     a workload emitting **&gt; ~20 range-checks in one proof** (batched multi-statement proofs, wide-range
     arithmetic at scale, or H3 accumulating many range-checked values). The design is ready to fire then.

2. **Wider provable range** *(small–medium if it rides LogUp; soundness-critical).* `[0, 2³²)`
   is chosen so `q·b < p`. The lookup argument (#1) lifts the ceiling almost for free; a
   standalone tighter `q·b < p` re-derivation is possible but lower-value. **Must** be the
   lookup or a rigorous re-derivation — *never* a soft range bit: the v5.89 audit REJECTED
   soft range-predication (the `v` vs `v+p` canonical-form attack reproduces the
   crown-jewel silent-wrong-ACCEPT class). Keep the hard `range_k` + ABSTAIN guard.

3. **String-result follow-ups — ✅ COMPLETE.** A **string `--claim`** landed *v5.111* (a false
   string result REJECTs, a wrong-length claim ABSTAINs); a **portable string-proof `--emit`**
   landed *v5.112* (`gprove_emit_mw` — the second verifier Pentecost checks the string-*valued*
   proof shape, with a tamper-checked corpus fixture); and **unequal-width `if`/`match` branches**
   landed *v5.121* via NUL-termination (the shorter branch is padded with codepoint-0, `decode_str`
   stops at the sentinel) — which also fixed a latent `accw` silent-truncation bug that attested a
   corrupted string. **Residual (deep corner, sound):** an `if`/`match` whose branches are a
   *structure carrying a variable-length string field* (e.g. `if c then ("ab", 1) else ("xyz", 2)`)
   is not a flat string, so it **ABSTAINs** rather than NUL-corrupt — a faithful refusal, not a gap
   to close unless a real workload needs structured-with-variable-string results (then: a
   length-tagged value model, a string-model change for a fresh session).

4. **Computed higher-order callees. ✅ LANDED v5.113.0 (+ let-alias v5.114.0).** A function value
   chosen *at runtime* (`(if c then g else h)(x)`) — the last refused bridge construct — lowers by
   pushing the application inside the selector (`if c then g(x) else h(x)`), reducing it to the
   named-fn calls already supported (*v5.87*); a shared `push_app` keeps `seval` and `unroll` in
   lockstep. A *let-aliased* fn name (`let f = g in f(x)`) resolves via the `fenv` slot (*v5.114*),
   and a *let-bound runtime selector* (`let f = (if c then g else h) in f(x)`) lowers by distributing
   the `let` over the selector — the dual of `push_app` (*v5.115*). The bridge now has **zero refused
   call forms**: named, runtime-chosen, let-aliased, and let-selector callees all lower soundly.

5. **H3 — full recursive STARK verifier** *(feasibility verdict: NO-GO today — a measured defer; see
   [`docs/h3-feasibility.md`](h3-feasibility.md)).* The two half-blocks have landed (FRI **fold-check as a
   circuit** `prove_recursion*.glass`; in-circuit **Merkle membership** `merkle_member.glass`, reduced hash).
   Re-assessed after the Merkle dedup (which shrank proofs ~2.9×): **expressibility is GREEN** (every op
   lowers; only modular-inverse needs the routine inverse-as-advice rewrite; NTT is prover-only; Poseidon2
   is pure `+`/`*`), but the **size is ~580× over the practical prover ceiling** (`verify_b3`-as-circuit ≈
   19M gates post-dedup, ~98% Poseidon2, vs ~32k rows; one permutation ≈ ~1,900 gates). Dedup moved the gate
   ~2.8× — groundwork, not the closer. **Gated on substrate perf (#6: a higher ceiling T1, or a chunking/
   accumulation substrate T2) — NOT on LogUp (#1), which is the wrong cost class for the hash core and stays
   independently deferred.** Next SHIPPABLE blocks: **B1 ✅ LANDED v5.126** —
   `merkle_fold_member.glass` composes in-circuit Merkle membership + the exact FRI fold in ONE circuit
   (two openings authenticated AND folded; `fx=10,fmx=20,β=7,x=1 → fold=−20`); **B2 ✅ LANDED v5.127** —
   `poseidon2_node.glass` is the REAL production Poseidon2 (t=12, 30 rounds, 130 constants, M_E/M_I) as a
   ~1.9k-gate provable circuit, cross-checked against `pentecost/poseidon.py` on all 12 lanes (the ~2^64
   constants lower as `hi·2³²+lo`); the honest per-node cost anchor (confirms the ~1.9k/perm estimate).
   **B3** the chunking/accumulation harness (= #6 in H3-shaped form, = T2) — the load-bearing lever that
   would erase the ~580× gap; the remaining piece.
   The recursive verifier's *arithmetic* is done; only the prover's *throughput* stands between Glass and a
   verifier that verifies itself.

6. **Substrate performance (P)** *(large; multi-pass; not soundness-critical).* `glass.py`
   is a tree-walker (multi-hour for heavy STARKs), so `native_glassc` (~10–40×) is the
   workhorse and the pain is the *dogfood gate*, not production proving. No bytecode/closure
   compiler exists; the proposed lever is to promote `native_glassc` to a **co-equal
   differential oracle**. A force-multiplier (unblocks #5 and heavy demos), but a structural
   rewrite — the "do it when the dogfood pain bites" background project.

7. **Proof-size reduction (serialization).** *(soundness-neutral; proof-format change.)* A comparison
   proof was ~552k tokens, ~94.5% of which is hash-digest data ([`docs/proof-size-frontier.md`](proof-size-frontier.md)).
   The grind/query *parameter* lever is NO-GO (~5%, brittle, v5.120). **First increment shipped v5.122:**
   a **denser hash encoding** (fixed 16 base-2^16 limbs per digest, dropping the always-`"4"` per-lane
   count) — `emit_hash` ⇄ `rd_hash` in lockstep, all 8 fixtures regenerated via the new
   [`fuzz/regen_corpus.py`](../fuzz/regen_corpus.py) (emit→Pentecost-verify→write), Name re-rooted, the
   native round-trip `difftest.sh` fixed (it had bit-rotted to a SIGSEGV on a stale input type) and
   green. Result: `a<b` 552k → **448k tokens (−18.9%)**. **Remaining (ranked):** (a) ✅ **wired `difftest.sh`
   into the suite** as a permanent native-round-trip gate *(v5.123)* — the green-but-broken hazard for
   *future* format changes is now caught automatically; (b) **Merkle-path deduplication** ([`docs/merkle-dedup-design.md`](merkle-dedup-design.md)): a per-tree
   sorted-index batch multiproof — *monotone* (never larger, no break-even, helps **every** proof, unlike
   LogUp), but a proof-*format* break (`verify_b3` IS in the lockstep). **✅ COMPLETE.** Stage 1 (batched
   TRACE trees) LANDED v5.124 and Stage 2 (batched FRI `bopen`) LANDED v5.125. **Measured end-to-end:
   `a<b` 448k → 154k tokens (−65.6%, a 2.91× smaller proof)**, matching the design's ~2.86×/65%; `a+b`
   −91%. O3 canonical reconstruction was validated in both languages before either stage; byte-identical
   Glass `verify_b3` ⇄ Pentecost; all soundness gates green (Stage-0 loud-break, difftest, corpus_check
   8/8 tamper-checked, fixpoint, suite 480/480). Isolated to `ProofB3` (the standalone `Proof`/`ProofS`
   demos keep `QOpen`). This *de-risks* H3 (a 2.9× smaller proof = ~⅓ the in-circuit Merkle hashing).
   (c) base-2^31 limbs — still deferred (a cross-lane combine overflows `int64`; the safe per-lane form
   yields a smaller win than the count-drop already shipped, and Merkle dedup was the dominant lever).

8. **Test-suite performance (test-infra).** *(medium; not soundness-critical.)* A full
   `tests/test_glass.py` run is **slow** (~tens of minutes): each of the ~50 heavy `glass prove` gates
   shells to `run_native.sh`, which native-**compiles** the ~2000-line bridge+driver (`native_glassc` →
   C → `cc`) and then runs a STARK — ~1 min/gate. (`native_glassc` *itself* is already cached across
   gates — `run_native.sh:27-33`; the per-gate cost is recompiling the *bridge*, since Glass has no
   separate compilation, plus the prove run.) It balloons to **hours** only when killed-suite `cc`/native
   processes accumulate and push load to 17+ — an *operational* issue (pkill the orphans + let load
   settle), not an inherent one. v5.123 made the suite *complete* under load (timeout-guard → a hung
   gate SKIPs rather than hangs forever). Real levers (none cheap): a suite-level warm binary that
   batches many claims into one compiled program (the bridge is identical across gates — only the driver
   tail differs); or emitting less/faster C. Lower-priority than the LogUp/Merkle frontiers; the
   pragmatic interim is shipping on standalone gates + partial-suite OK/0-FAIL when a full run is
   impractical.

9. **R2 formal follow-ons** *(medium; not gateable).* A formal MDS/round-count cryptanalysis
   and a formal Fiat-Shamir separation argument — reviewed prose, no differential-testable
   artifact, partly subsumed by the external-audit boundary.

10. **External audit + Poseidon cryptanalysis** *(the hard boundary — not in-repo work).*
   The only path from research-grade to production-soundness. Listed to keep the roadmap
   honest about what in-repo work can and cannot achieve; a builder cannot pick this.

**Deferred/known** (tracked in the audit-findings memory): **RC-D** string
codepoint-vs-byte divergence (host counts Unicode codepoints, emitted C counts UTF-8
bytes; codepoints are the intended semantics, so the C side is the deviation — non-ASCII
only, unreachable in the corpus, and the fix touches bootstrap `glassc.glass` for zero
current payoff, so it waits); plus the `--baby-bear` silent-truncation, the `glassc` TyInt
fallback, and the `run_command` argv divergence — none reach a well-typed Goldilocks
proof.

## Honestly de-prioritized (and why)

- **Dependent types / full theorem proving** — enormous; refinement types plus ZK proofs
  already give a real verification story.
- **A bytecode/closure backend for the reference interpreter** — real (it is *Substrate
  performance*, above), but the native path is already the fast workhorse; correctness and
  the ZK frontier come first.
- **Mainstream DX (package manager, IDE plugins)** — matters for adoption, not for the
  frontier edge. A partial DX pass (prelude, diagnostics, `glass help`, the plain-name
  surface) has shipped.
- **Faithfully lowering built-in `List<T>` in a proof** — the bridge proves *declared* recursive
  ADTs (`type IntList = | Nil | Cons(Int, IntList)`, as in `map_prove.glass`) but not the built-in
  `List<T>` literal/spread, because its `Cons`/`Nil` live in no source `TypeDecl`. As of *v5.128* an
  undeclared constructor **ABSTAINs loudly** (no silent proof-of-0), so this is *safe*, just not
  *supported*. Supporting it means monomorphizing `List<T>` onto that same ADT machinery (element
  type, recursion-depth `twidth` bound) — a real but bounded feature; the declared-ADT form is the
  workaround today, so it is low priority.

## Success criteria (the Glass discipline)

Every item ships a differential-tested, self-hosting artifact: the reference and the
compiled/proved result agree, and `native_glassc` reproduces it byte-for-byte. Nothing is
"done" until the interpreter and the self-hosted compiler give the same answer — and,
for a proof, until an independent verifier (Pentecost) and the reference interpreter (the
Third Witness) agree on it too.

---

## The instruments — verification & revelation

The guiding idea behind these is that *verification and revelation are the same problem*:
unveiling that something is true without exposing how. That framing surfaced a ranked set
of directions; the buildable, sound ones — all now landed:

- **Let the verifier be two. ✅ v5.64.0.** `verify_b3` no longer stands alone: an
  **independent, non-Glass re-verifier** (`pentecost/`, plain int mod p, from-scratch
  Poseidon, sharing no Glass code) parses and checks a real Glass-emitted `ProofB3`. End-to-end
  differential ([`pentecost/difftest.sh`](../pentecost/difftest.sh)): **honest → both ACCEPT;
  tampered root / wrong claim / tampered opening → Pentecost REJECT.** Retires the
  honest-ledger caveat "reasoned, not machine-checked" for the B3 path. (Still UNAUDITED; the
  second verifier is from public specs, not a trusted third-party oracle — that is the Third
  Witness bet below.) `pentecost/pentecost_verify.py` (~355 LOC) re-implements the full verifier
  — FS transcript, INTT, OOD gate-identity, PLONK grand-product, FRI+Merkle, grind — fed by a
  Glass serializer (`emit_proofb3`, byte-for-byte with `parse()`). **CLI-operationalized v5.74.0**
  (`glass prove --emit` / `glass verify` — prove-once-verify-anywhere).
- **The Name — content-addressed canonical identity. ✅ v5.65.0.** `glass name`
  ([`../name/`](../name/)) publishes one Poseidon-Merkle root over the self-hosting core +
  prover/`verify_b3` bridge + the second verifier + tests + `LANG.md`, recomputed by the suite
  (`--check` gates `name/NAME` lockfile-style) on the same Plonky2-exact Poseidon the prover
  uses. The fixpoint as a publicly attestable fingerprint. Path + content bound (currently
  `259e98cf…`).
- **The Preserved Tablet — committed, append-only proof ledger. ✅ v5.66.0.** `glass tablet`
  ([`../ledger/`](../ledger/)) appends each verdict and commits the history into a
  Poseidon-Merkle root with inclusion proofs (`prove`/`verify <i>`); tampering a past entry
  changes the root.
- **The Measuring Reed — bit-security on every ACCEPT. ✅ v5.63.0.** `glass prove` (Goldilocks)
  prints `security: 80 bits provable / 135 bits list-decoding (82 queries, blowup 32 ⇒ rate
  1/8, 12-bit grind, 4-lane hash)`, re-derived by the prover from the live params of the actual
  circuit (`fri_queries`/`fri_dsize`/`grind_modulus`), not asserted in prose.
- **The Urim's Silence — ABSTAIN as a third verdict. ✅ v5.67.0.** `glass prove` reports ABSTAIN
  (refused to lower) distinctly from REJECT (`verify_b3` ran and the proof failed). Sound by
  construction — the refusal aborts before `verify_b3`, so ABSTAIN cannot swallow a real REJECT.
- **Opening the Seals — selective disclosure. ✅ v5.68.0.** `glass seal` ([`../seal/`](../seal/))
  commits a record as blinded Poseidon leaves and reveals any subset with inclusion proofs —
  revealed fields bind to the root, the rest stay hidden (*prove you're over 21 without your
  birthdate*, generalized).
- **Tzimtzum-as-a-type — `Concealed<T>`. ✅ type-level v5.73.0.** A value provable-about
  (`concealed_in_range` → public Bool) and computable-within (`cmap`) but never observable: an
  opaque type with **no reveal eliminator and no constructor**, so every reveal (arithmetic,
  print, pattern-match) is a compile-time type error — privacy by construction. *Remaining:*
  wire concealed values to the prover's ZK witness (cryptographic, not only type-level hiding).
- **Migrate the bridge hash Plonky2 → Poseidon2 (Plonky3). ✅ v5.70.0.** The live bridge `hashg`
  is Poseidon2; the second verifier migrated in **lock-step**, re-implemented independently,
  matching only at Plonky3's vector. Full differential green; fixpoint holds; the Pentecost
  keystone is suite-gated; the Name re-rooted (one Poseidon everywhere).
- **Fuzzing the verifiers — random and adversarial. ✅ v5.75–v5.109.** [`../fuzz/`](../fuzz/)
  tests *random* proofs three ways: **witness3** (reconciled against the reference interpreter),
  **differential** (Glass `verify_b3` and Pentecost AGREE on honest proofs), and **adversarial
  tamper** (forged proofs — 1,600 across 16 seeds → 0 wrong-ACCEPTs; 640 public-statement
  tampers → 0). A multi-shape **corpus** (`fuzz/corpus_check.py`, suite-gated) runs the
  differential + tamper checks across committed fixtures of several circuit shapes (`a+b`,
  `a*b`, `a<b`, `a/b`, string-eq, **and a record destructure**) — catching a `verify_b3` bug
  that only manifests on certain gate kinds. (Every campaign so far has surfaced *fuzzer* bugs,
  never prover-soundness bugs.)
- **A plain-name surface — the thematic layer made optional. ✅ v5.79.0.** Every instrument has
  a neutral public name beside its thematic one: `glass fingerprint`/`ledger`/`disclose` +
  `--cross-check` alias `name`/`tablet`/`seal`/`--witness3`; [`naming.md`](naming.md) maps plain
  ⇆ thematic ⇆ what-it-is. Both names are suite-gated.

The research-scale bet, wearing its honest scope: **the Third Witness.** 🟡 **Semantic cut
LANDED v5.71.0:** `glass prove --witness3` binds the proof's public result to the reference
interpreter — a lineage independent of the bridge's evaluator AND its circuit lowering —
catching a source↔circuit gap (`heval`+`cgen` sharing a bug) that `gen1 == gen2` and
verifier-be-two (both verify the circuit) structurally cannot. The fuller bet — a third
*independent verifier of the STARK construction itself* (3-way consensus on the proof, not just
the semantics) — remains open.

## The convergence: self-improving, self-proving

Glass does two deep things that most languages do neither of, and they are starting to meet:
it **rebuilds itself** (the self-hosting bootstrap fixpoint — `native_glassc` compiles its own
source byte-for-byte, no other language in the loop) and it **proves its own computations** (the
zk-STARK prove bridge). The frontier is closing those into one loop: *a language that can
recursively improve itself and prove it at the same time.*

- **First step — Glass proves its own building blocks. ✅ v5.85.0.** `examples/prove/selfprove.glass`
  proves, in zero-knowledge, a polynomial-hash step `(h*31 + c) % m` — the exact arithmetic shape
  of Glass's own djb2/polynomial string hash — composing `*`, `+`, and the `%` gadget. The result
  is bound three independent ways (`verify_b3`, Pentecost, the reference interpreter). The kind of
  code Glass is made of, proven by Glass.
- **Open — the gaps between "proves a function" and "proves itself":**
  - **Deeper / unbounded recursion.** The bridge unrolls recursion to a fixed fuel (8); deeper
    programs ABSTAIN. Proving Glass's *own* larger functions needs a higher bound (cost) or a
    recursion/induction argument rather than unrolling. (`gcd`-class programs additionally hit an
    exponential unroll from compound recursive args — semantics-gated today.)
  - **Range-predication — REJECTED in this gate model (v5.89).** Out-of-*range* operands in dead
    `if`-arms still ABSTAIN. A soft `in_range_bit` *is* the range problem — any non-failing 0/1
    answer for an arbitrary field element must canonicalize against `p`, which is unsound via
    64-bit decomposition near the prime. Keep the hard `range_k` + ABSTAIN guard; the **LogUp
    range argument** (*What's open* #1) is the sound route to cheap+wide range. (Division
    *value*-predication, by contrast, IS sound and shipped — *v5.88*.)
  - **Proving a property of the compiler itself** (not just a helper's result) — the largest step:
    `verify_b3`-as-a-circuit (H3), or proving the fixpoint relation, is the eventual closing of the
    loop.

---

## Milestone ledger

The forward map is above; this is the rear-view, one line per era. Full detail per version is in
[`CHANGELOG.md`](../CHANGELOG.md).

- **Self-hosting (v4.71–v4.76).** The quartz→glassc migration; the bootstrap fixpoint closes —
  Glass compiles itself byte-identically.
- **Pane ⊕ Frost (through ~v5.3).** A query algebra (Pane) and a from-scratch zk-STARK toolkit
  (Frost: field, MiMC/Poseidon, Merkle, arithmetization, FRI, AIR, ZK blinding, permutation
  argument) — *Frost = the ZK extension of Pane*: commit a private table, prove a query's result.
- **The production field + a sound verifier (v5.34–v5.49).** `glass prove` moved off toy Baby Bear
  onto Goldilocks; F_{p²} challenge space; statement-binding Fiat-Shamir; the witness-free
  `verify_b3` became the CLI default. The founding thesis — *write Glass, get a zero-knowledge
  proof* — realized for first-order pure Glass.
- **Soundness hardening (v5.52–v5.57, v5.128).** Faithful boolean lowering with loud refusal (fixing a
  silent proven-0 regression); reference-interpreter fixes (effect rows, lexer, exhaustiveness,
  int64/C agreement). *v5.128:* the same class, found while building B2 — a **built-in `List<Int>`**
  threaded into a proof had its desugared `Cons`/`Nil` constructors (absent from any source `TypeDecl`)
  collapse to tag 0, silently proving `0`; `ctag`/`ctor_argtypes` now ABSTAIN on any undeclared
  constructor. (Faithfully *lowering* built-in lists — monomorphizing `List<T>` onto the ADT machinery
  that already proves declared ADTs like `map_prove.glass`'s `IntList` — is an open feature, distinct
  from this make-it-safe refusal.)
- **The prover speed cuts (v5.59–v5.62).** Poseidon intrinsic, O(n log n) LDE, O(1) wire indexing,
  a deep-recursion stack flag — making the range gadget (and the whole two-verifier path) affordable.
- **The verification stack (v5.63–v5.79).** The Measuring Reed, Pentecost (verifier-be-two), the
  Name, the Preserved Tablet, ABSTAIN, Opening-the-Seals, the Poseidon2 migration, the Third
  Witness, the fuzzing campaigns, `Concealed<T>`, the plain-name surface.
- **The bridge gadget frontier (v5.62–v5.117).** Comparison, division/modulo, signed integers,
  strings, records, structured results (string / tuple / record, `--claim` / portable `--emit`),
  computed callees (runtime-chosen, let-aliased, and let-selector), and bitwise logic
  (`bit_and/or/xor`) — each a faithful field lowering that narrowed the refusal without ever
  replacing it with a silent wrong proof, until zero refused call forms remained, the
  integer-operation families were complete, and a proof could return any scalar/string/tuple/record.
- **The standalone LogUp arc (v5.105–v5.107).** The de-risking of the cheap-range frontier: the
  rational-sum identity, the running-sum/AIR form, and the committed + Fiat-Shamir form.
