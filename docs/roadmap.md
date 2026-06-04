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
- **Strings** — a string is a multi-wire value (one field wire per codepoint), so
  `++` is structural concat (no gate), `==`/`!=` the AND-folded per-codepoint is-zero
  gadget, `string_length`/`substring` static wire counts/slices, and `match` on string
  literals an allowlist dispatch — all over a **private** string. *v5.101–v5.102.*
- **Records** — construct (`Account { … }`), destructure (`match a { Account { … } }`),
  and field access (`a.balance`), lowering like a tagless tuple. *v5.103–v5.104.*
- **String-VALUED results** — a proof can *return* a string, bound by pinning every
  output wire as the public claim and decoded back to text (selective disclosure of a
  private key's prefix; a verdict word chosen by a private comparison). *v5.110.*

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

2. **Wider provable range** *(small–medium if it rides LogUp; soundness-critical).* `[0, 2³²)`
   is chosen so `q·b < p`. The lookup argument (#1) lifts the ceiling almost for free; a
   standalone tighter `q·b < p` re-derivation is possible but lower-value. **Must** be the
   lookup or a rigorous re-derivation — *never* a soft range bit: the v5.89 audit REJECTED
   soft range-predication (the `v` vs `v+p` canonical-form attack reproduces the
   crown-jewel silent-wrong-ACCEPT class). Keep the hard `range_k` + ABSTAIN guard.

3. **String-result follow-ups** *(small–medium; low-risk, bridge-only).* A **string `--claim`**
   landed *v5.111* (a false string result REJECTs, a wrong-length claim ABSTAINs), and a
   **portable string-proof `--emit`** landed *v5.112* (`gprove_emit_mw` — the second verifier
   Pentecost now checks the string-*valued* proof shape, with a tamper-checked corpus fixture).
   **Remaining:** **unequal-width `if`-branches via length-tagged padding** (today they ABSTAIN).
   Additive, gateable (`cgen == heval == seval` + a corpus fixture), no `verify_b3` soundness change.

4. **Computed higher-order callees. ✅ LANDED v5.113.0 (+ let-alias v5.114.0).** A function value
   chosen *at runtime* (`(if c then g else h)(x)`) — the last refused bridge construct — lowers by
   pushing the application inside the selector (`if c then g(x) else h(x)`), reducing it to the
   named-fn calls already supported (*v5.87*); a shared `push_app` keeps `seval` and `unroll` in
   lockstep. A *let-aliased* fn name (`let f = g in f(x)`) resolves via the `fenv` slot (*v5.114*),
   and a *let-bound runtime selector* (`let f = (if c then g else h) in f(x)`) lowers by distributing
   the `let` over the selector — the dual of `push_app` (*v5.115*). The bridge now has **zero refused
   call forms**: named, runtime-chosen, let-aliased, and let-selector callees all lower soundly.

5. **H3 — full recursive STARK verifier** *(large; performance-gated; native-primary).*
   The two building blocks have landed: the FRI **fold-check as a circuit**
   (`prove_recursion*.glass`) and in-circuit **Merkle membership**
   ([`merkle_member.glass`](../examples/prove/merkle_member.glass), *v5.72*). Remaining:
   full Poseidon2 per node, composing membership with the fold-check, and
   **`verify_b3`-as-a-circuit** — all gated on a faster prover or LogUp (#1) relieving the
   per-node hash cost. High value, but correctly *downstream* of #1.

6. **Substrate performance (P)** *(large; multi-pass; not soundness-critical).* `glass.py`
   is a tree-walker (multi-hour for heavy STARKs), so `native_glassc` (~10–40×) is the
   workhorse and the pain is the *dogfood gate*, not production proving. No bytecode/closure
   compiler exists; the proposed lever is to promote `native_glassc` to a **co-equal
   differential oracle**. A force-multiplier (unblocks #5 and heavy demos), but a structural
   rewrite — the "do it when the dogfood pain bites" background project.

7. **R2 formal follow-ons** *(medium; not gateable).* A formal MDS/round-count cryptanalysis
   and a formal Fiat-Shamir separation argument — reviewed prose, no differential-testable
   artifact, partly subsumed by the external-audit boundary.

8. **External audit + Poseidon cryptanalysis** *(the hard boundary — not in-repo work).*
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
- **Soundness hardening (v5.52–v5.57).** Faithful boolean lowering with loud refusal (fixing a
  silent proven-0 regression); reference-interpreter fixes (effect rows, lexer, exhaustiveness,
  int64/C agreement).
- **The prover speed cuts (v5.59–v5.62).** Poseidon intrinsic, O(n log n) LDE, O(1) wire indexing,
  a deep-recursion stack flag — making the range gadget (and the whole two-verifier path) affordable.
- **The verification stack (v5.63–v5.79).** The Measuring Reed, Pentecost (verifier-be-two), the
  Name, the Preserved Tablet, ABSTAIN, Opening-the-Seals, the Poseidon2 migration, the Third
  Witness, the fuzzing campaigns, `Concealed<T>`, the plain-name surface.
- **The bridge gadget frontier (v5.62–v5.115).** Comparison, division/modulo, signed integers,
  strings, records, string-valued results (`--claim` / portable `--emit`), and computed callees
  (runtime-chosen, let-aliased, and let-selector) — each a faithful field lowering that narrowed the
  refusal without ever replacing it with a silent wrong proof, until **zero** refused call forms remained.
- **The standalone LogUp arc (v5.105–v5.107).** The de-risking of the cheap-range frontier: the
  rational-sum identity, the running-sum/AIR form, and the committed + Fiat-Shamir form.
