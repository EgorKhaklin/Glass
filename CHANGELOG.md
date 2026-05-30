# Changelog

All notable changes to Glass.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/).
This project follows [Semantic Versioning](https://semver.org/).

---

## [5.48.0] — 2026-05-30 — TIER-1: a from-scratch sound + zero-knowledge zk-STARK (research-grade, unaudited)
- **An independent, witness-free verifier with per-row gate soundness *and* inter-row wire consistency — the structural gap v5.47.0 scoped as "the next frontier" is now built.** v5.46.1/5.47 named the honest ceiling: the prover *self-checked* over its own witness (no malicious-prover bound) and statement-binding was prover-side only. [`prove_source_goldilocks_zk.glass`](examples/prove/prove_source_goldilocks_zk.glass) now carries **`verify_b3`** — a verifier that takes only the proof + public statement and re-derives every Fiat-Shamir challenge itself, built in four composable layers (the four-piece build-out v5.47 scoped): **(A)** witness-free verifier scaffolding; **(B1+B2)** per-row gate-binding via an out-of-domain quotient identity at a Fiat-Shamir point z + DEEP-batched FRI (the `P=0` evil proof that the scaffolding accepted is now **REJECTed** — gates must actually hold at z); **(B3)** a from-scratch **PLONK grand-product copy/permutation argument** (staged 3-tree commit T1{l,r,o}→β,γ→T2{Z}→α→T3{Q}→z) that catches a prover threading *inconsistent values down the same wire* — a per-row-only verifier accepts the wiring attack, the grand product **REJECTs** it. Soundness budget: **32N coset, ρ=1/8, fold-to-8, 82 queries sampled without replacement + a real 12-bit grind ⇒ ~80-bit provable** (FRI-query-limited; ~2⁻¹³⁵ list-decoding is conjectural). Two audit-readiness findings were caught *and fixed* in the same cycle: the commitment hash `hashg` returned **one ~64-bit lane** (a silent ~2⁻³² binding cap that gated the whole proof at ~32-bit, not ~80) — widened to **4 Poseidon lanes (~128-bit binding)**; and queries were sampled **with** replacement — now **distinct** (`sample_distinct`), so the full 82-query margin holds. Public statements are pinned: **`build_claim_pub`** binds an input wire to a public value (a wrong public input REJECTs — the proof is now `R = f(THESE inputs)`, not "some valid output"). **Zero-knowledge** is implemented via a **randomized trace** (`build_claim_zk`: ~240 dummy `GAdd` rows with fresh wires that are σ-fixed-points cancelling in the grand product, padding to n=256 so the ~240 random rows ≫ the ~170 query openings) — HVZK / NIZK-in-ROM, verifier unchanged; validated native **ACCEPT at n=256, sound *and* hiding**. Native gates all hold: honest **ACCEPT**; `P=0` / cross-statement / tampered-opening / wiring / wrong-public-input all **REJECT**; ZK blinding hides; ZK full integration (n=256) **ACCEPT**.
- **A pen-and-paper soundness reduction + an audit-readiness package — and the hard boundary, restated.** [`docs/tier1-soundness-proof.md`](docs/tier1-soundness-proof.md) reduces the construction in four links (FRI proximity → DEEP-ALI → identity-at-z + the PLONK permutation lemma → Fiat-Shamir-in-ROM) with an explicit proven/conjectural/idealized/gap ledger; [`docs/tier1-wip-soundness.md`](docs/tier1-wip-soundness.md) re-derives the concrete ~80-bit budget (razor-thin 68+12, zero slack); [`docs/tier1-zk-design.md`](docs/tier1-zk-design.md) documents the HVZK design (and the silent-rate-erosion trap the randomized-trace route avoids); [`docs/audit-readiness.md`](docs/audit-readiness.md) is the threat model + assumptions ledger + audit scope + auditor-start-here. **This is the integrity discipline working end to end: an adversarial completeness pass written to stress the claims for an auditor caught *five* overclaims this cycle (the ~32-bit hash cap being the integrity-critical one) — each corrected and re-validated in-session.** **Honest scope — the boundary is hard and stays:** every Merkle node and FS challenge is a Poseidon output **modeled as a random oracle** — the in-repo Poseidon is **unaudited / un-cryptanalyzed**, and *if it has exploitable structure the entire bound is vacuous* (soundness and the designed ZK collapse together). All reductions are **reasoned, not machine-checked**; the ZK simulator is reasoned, masks are Poseidon-seeded (ideal-RNG). So this is **research/educational-grade, UNAUDITED — production-readiness requires an external professional audit + community cryptanalysis, which is never producible in-repo**. The *do-not-protect-real-value* banner stands. The construction lives in `verify_b3` + the prover demo; the CLI `glass prove` default is still the older per-row path (noted in `audit-readiness.md`). Suite **382/382**; bootstrap fixpoint byte-identical (this cycle touched only the prover source + docs, not `glassc`/`prism`).

## [5.47.0] — 2026-05-29 — Fiat-Shamir transcript now binds the statement (prover-side)
- **The prover's Fiat-Shamir transcript is now seeded with a digest of the statement.** Until now the transcript was seeded only by the prover's own FRI Merkle roots — the challenges did not depend on *what* was being proven. [`prove_source_goldilocks_zk.glass`](examples/prove/prove_source_goldilocks_zk.glass) now computes **`stmt_seed_of(gates) = circuit_digest(gates, glit(2718281))`** — a Poseidon digest over the full gate list (each gate's variant tag + wire indices + the `GConst` holding the claimed result R; **witness-independent** — only public opcodes/indices/constants are absorbed, the private witness is never passed in, and R is captured at full 2⁶⁴ width) — and threads it through `commit_g` (new transcript-seed parameter; `beta_of_root_g` → `beta_of_seed_g`). So **every** Fiat-Shamir challenge — the per-layer FRI fold β's *and* the query positions — is now a deterministic function of the statement (this also fixes a prior gap: each β now chains through `stmt_seed` + **all** preceding layer roots, where the old code used only the single current root). Verified: `transcript_seed_g(layers, stmt_seed)` equals the threaded seed by identical hashg-chaining (a load-bearing invariant, pinned in a comment). **Honest scope — NARROWED, not closed:** this is **prover-side seeding only**. `verify` still reads each layer's *stored* β rather than re-deriving it, so statement-seeding buys **zero soundness against a malicious prover** on its own — a false statement is *not* rejected by this change. Enforcing it requires the independent verifier, which an adversarial design review scoped as a **four-piece soundness build-out** (verify scaffolding + trace commitment + OOD/DEEP quotient identity + a from-scratch copy/permutation argument) — TIER-1, the next frontier. ACCEPT/REJECT behavior is unchanged (native: honest **ACCEPT**, wrong claim **REJECT**, full-strength, ~2m13s); only proof internals (β's, query positions, roots from layer 1 on) change — the intended effect of binding. No soundness-bits number is attached to this change; the unaudited / *do-not-protect-real-value* banner stands.
- **Two follow-on honesty fixes + a regression guard.** (1) The prover's demo footer **and** `soundness.md` still described the demo as *"runs reduced (64-pt coset, grind off)"* — which directly contradicted v5.46.1's grind fix and the committed code: the demo runs **full-strength natively** (ρ=1/8, coset 16N, 64 queries, real 12-bit grind, ~2–3 min), the reference interpreter being multi-hour for a Poseidon STARK. v5.46.1 reconciled the soundness ledger but missed these; both are now corrected. (2) A new **`BIND-GUARD` regression test** ([`prove_source_goldilocks_bind_test.glass`](examples/prove/prove_source_goldilocks_bind_test.glass), wired into the suite) proves the statement digest actually distinguishes statements — same circuit → same seed, different claimed R → different seed, reordered operands → different seed — so the binding can never silently regress to a no-op (institutionalizing the v5.46.1 grinding lesson: pin behavior the code claims, in CI). Suite **382/382** (+1: the guard); bootstrap fixpoint byte-identical; `soundness.md` §3/§4 updated (statement-binding marked PARTIAL — prover-side done, verifier-side enforcement is TIER-1).

## [5.46.1] — 2026-05-29 — Honesty patch: the grinding proof-of-work is now real (it was a no-op)
- **The 12-bit grinding that v5.40–v5.46 credited (+12 bits, the ~65-bit provable figure) was a no-op — now fixed.** `pow_ok` in [`prove_source_goldilocks_zk.glass`](examples/prove/prove_source_goldilocks_zk.glass) was `x % 1 == 0` — a tautology (always true), so the proof-of-work search returned on the first nonce and added **0 bits**, while the code comment, the prover banner, `parameters.md`, and `soundness.md` all credited 12 (and ~65-bit *provable* depended on them). It was a reduced-demo "grind off" toggle that leaked into the committed prover; an adversarial roadmap review caught it. Fixed to a **real 12-bit PoW** (`x % 4096 == 0` — the Fiat-Shamir query seed's low 12 bits must be 0): the existing two-level grind search now does ~2¹² Poseidon hashes to find a valid nonce and the verifier checks it (the ADT proof goes 2m13s → 3m16s native). **~65-bit provable is now real, not claimed.**
- **`soundness.md` reconciled to the shipped reality** — it still described "default = Baby Bear / hash = MiMC" (false since v5.45/v5.46). Corrected to: default = Goldilocks-ADT + Poseidon. And two genuine **research-grade gaps** are now stated honestly rather than glossed: the prover's inline Fiat-Shamir transcript binds the FRI roots **but not yet the statement** (circuit digest + claimed result + public inputs), and there is **no separate `verify(proof, public)`** (the prover self-checks over the witness — not yet a malicious-prover bound; the biggest structural gap to a real proof system). Both are now on the production roadmap. Suite **381/381**; bootstrap fixpoint intact; the *do-not-protect-real-value* banner stands. *(The integrity discipline working: claim only what the code delivers — caught and corrected within the hour.)*

## [5.46.0] — 2026-05-29 — The default `glass prove` moves off the toy field: ADTs over Goldilocks
- **The default `glass prove` no longer proves over the educational 2³¹ field — it proves over Goldilocks (2⁶⁴).** The default path was Baby Bear (`prove_source_adt_zk.glass`), whose ~2³¹ value space made any private input brute-forceable in ~2³¹ work *regardless of the FRI* — the last structural educational-grade gap in the prove bridge. `glass prove <file> a=..` (no flag) now compiles the program's `match`/ADT circuit and emits a zero-knowledge STARK over the production field **p = 2⁶⁴−2³²+1** (`glass prove --baby-bear` opts back into the old small-field prover). Three pieces made it real: (1) **variable trace domain** — the Goldilocks prover's FRI was hardcoded N=16 (scalar demos only); it now sizes **N = next_pow2(#gates)** (the validated Baby Bear ρ=1/8 relation: coset 16N, tested degree 2N = 3(N−1)−N, fold-to-8), so ADT circuits of hundreds of gates prove; (2) the **ADT multi-wire `cgen`** (`[tag, …fields]` wire-lists, is-zero match dispatch, type-directed widths) ported to the Goldilocks bignum, validated `cgen == heval` (circuit ≡ reference evaluator); (3) **fast field arithmetic** — `gold_mul`/`gold_add`/`gold_sub` (combine the base-2¹⁶ limbs → one op mod p with a 128-bit intermediate → split back) in **both** `glass.py` (Python bignum) and `glassc.glass` (C `unsigned __int128`), **interp == native byte-identical** (incl. `finv·a = 1`), and the **bootstrap fixpoint holds** (1003 lines of C, exact self-reproduction). Net: an ADT proof that was ~30 min+ (limb schoolbook, killed unfinished) now runs in **~24 s (ρ=1/2) / ~160 s (ρ=1/8, ~65-bit)** native. End-to-end: `glass prove` of a `match`-over-ADT program → `result` over Goldilocks + `proof: ACCEPT` (a wrong claim REJECTs), in ~2m13s incl. the one-time native_glassc build. Because Goldilocks is bignum-heavy, the default CLI runs **natively** via `run_native.sh` (the interpreter is ~hours) — so the default now needs a C compiler + libgc (documented in getting-started; `--baby-bear` stays interpreter-only / Python-only). Suite **381/381**; bootstrap fixpoint intact. **Honest scope:** this closes the *structural* educational-grade gap — the toy value space — for the default; it does **not** make the crypto production-ready. Matching no reference is an audit, there is no external audit, and the *do-not-protect-real-value* banner in [`docs/soundness.md`](docs/soundness.md) stands. `soundness.md` + `roadmap.md` updated.

## [5.45.0] — 2026-05-29 — Poseidon is the in-STARK hash: MiMC retired from the prover
- **The last educational-grade primitive in the Goldilocks prover, replaced.** The hardening track's most-cited gap was the in-STARK hash (MiMC). With the v5.44 GC runtime removing the OOM wall, this wires the **vetted Poseidon** (Plonky2-exact, vector-verified — [`frost_goldilocks_poseidon.glass`](examples/frost/frost_goldilocks_poseidon.glass)) into [`prove_source_goldilocks_zk.glass`](examples/prove/prove_source_goldilocks_zk.glass) as the prover's hash. MiMC's `hashg` is replaced by a 2-to-1 Poseidon sponge — `hashg(a,b) = perm([a, b, 0…])[0]` — so the Merkle commitment, the Fiat-Shamir challenges, and query sampling all run on the standard hash; the 14 Poseidon functions + 360 round constants are spliced in verbatim from the verified file (no transcription risk), reusing the prover's existing Goldilocks field. Honest ACCEPT / wrong-claim REJECT verified **native** (the reduced-param demo); the Poseidon machinery is spliced **verbatim** from the separately vector-verified + byte-identical-dogfooded `frost_goldilocks_poseidon.glass`, and the **bootstrap fixpoint + suite (381/381) are untouched** (v5.45 changes only the prover source, not `glassc`/`prism`). The full interpreter↔native byte-identical dogfood of the *Poseidon proof* is native-territory — multi-hour even at reduced params — so it is not the routine gate here. The interpreter's type-checker even caught a real issue the type-erased native missed (an `[[]]` whose element type wouldn't unify — fixed with `[glit(0)]`), the differential-testing discipline working exactly as intended. **Honest scope:** Poseidon is ~300× heavier than MiMC, so the *shipped demo* runs **reduced params** (64-pt coset, grind off, ACCEPT+REJECT) for a tolerable interpreter dogfood; **full-strength** (ρ=1/8, 64 queries, 12-bit grind, ~65-bit provable) + ZK run **native** under the v5.44 GC (the prover that OOM'd at 16 GB now runs at ~10 MB). The **default Baby Bear prover's hash is separate and still educational**; matching a reference is **not an audit**; no external audit — the "do not protect real value" banner stands. With this, the Goldilocks prover's structural primitives — field (Goldilocks 2⁶⁴), challenge space (F_{p²} ≈ 2¹²⁸), and now the **hash (Poseidon)** — are all standard/vetted. `soundness.md` + `roadmap.md` updated.

## [5.44.0] — 2026-05-29 — A freeing native runtime (Boehm GC): the no-free OOM wall, removed
- **The native backend now frees memory — unblocking the heavy crypto the whole hardening track was gated on.** The v5.43 cycle hit a precise wall: wiring the vetted Poseidon into the prover OOM'd the native binary (>16 GB on even *one* proof), because the emitted C was **no-free** — it `malloc`'d but never `free()`'d/GC'd — and a Poseidon permutation allocates ~300× a MiMC round, so the allocations accumulated past memory. This gives the native backend a **conservative garbage collector** (Boehm bdw-gc): [`glassc.glass`](examples/selfhost/glassc.glass)'s codegen now emits `GC_malloc` for every runtime allocation, `#include <gc.h>` + `GC_INIT()`, and links `-lgc`. **The bootstrap fixpoint still holds byte-identical** — `native_glassc` and `native_glassc_2` emit the same 974-line C and compiled `prism` matches the interpreter (the self-reproduction is unchanged; only the allocator differs) — and the suite is **381/381**. The payoff is immediate and measured: the Poseidon prover that OOM'd at **16 GB now runs at ~10 MB** (bounded — GC collects the per-permutation allocations). This removes the OOM ceiling that blocked Poseidon-in-the-prover and bigger FRI blowups toward real 80-bit. Honest scope: it adds a **`libgc` build dependency** (the cc invocation passes `-lgc` + homebrew include/lib paths — a portability cost; the *bootstrap* compiler `quartz.py` is left no-GC since compiling is light, and the fixpoint only needs `glassc.glass`'s codegen consistent); GC adds runtime overhead; and this is a *runtime* enabler, not new cryptography. **Next (v5.45): wire Poseidon in as the in-STARK hash**, retiring MiMC — the last educational-grade primitive in the prover. `soundness.md` + `roadmap.md` updated.

## [5.43.0] — 2026-05-28 — The rate fix, generalized: the default Baby Bear path → ρ=1/8
- **v5.42 lowered the Goldilocks rate and *found* the default path was secretly ρ=1/2; v5.43 fixes it.** While analyzing v5.42, the default Baby Bear path ([`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass)) turned out to fold its FRI all the way to length 2 over a 4n coset with a degree-~2n quotient (the `qm·l·r` gate ÷ Z_H) — so it tested degree < 2n at rate **1/2 (~10–12 bits)**, not the ρ=1/4 the docs had claimed. v5.43 applies the same fold-count technique as the Goldilocks path: the coset grows **4n → 16n** and the fold **stops at length 8** (= coset/(2n)) instead of 2, so the *tested degree stays 2n* while the rate drops to **ρ = 1/8**; queries go **24 → 64**, made cheap by **memoizing the FRI layer trees** (ported from the Goldilocks path's v5.41 — each layer's tree is built once in `commit` and query paths read from the stored levels, so a query no longer rebuilds a tree). Net query-phase soundness: **~53-bit provable / ~96-bit list-decoding**, up from ~10–12. **Both `glass prove` paths now run at ρ=1/8.** Honest scope: the default path's *binding* weakness is no longer the FRI but its **2³¹ value space** — a private input is brute-forceable in ~2³¹ work regardless of the proof — so the real next step for this path is the Goldilocks-ADT migration (R1b); and the in-STARK hash is still MiMC on both paths. Dogfoods byte-identical (`glass.py == native_glassc`); honest ACCEPT, lying-about-its-type REJECT, two seeds → different openings (ZK). `parameters.md` + `soundness.md` updated. (native ~0.08s; interpreter dogfood ~2.5 min — the memoization cut it from ~32 min, a 13× speedup, since the 64 queries no longer rebuild a Merkle tree each.)

## [5.42.0] — 2026-05-28 — Lowering the rate: ρ=1/8 + 64 queries → ~65-bit provable query soundness
- **Spending v5.41's cheap queries on a real run at 80-bit — and lowering the rate to get there.** v5.41 made FRI queries cheap (memoized layer trees) and named the next lever: a bigger blowup (lower rate). This applies *both* at once on the Goldilocks STARK ([`prove_source_goldilocks_zk.glass`](examples/prove/prove_source_goldilocks_zk.glass)). The FRI evaluation coset grows **64 → 256** (blowup 8), and — the part that actually matters — the fold is now **fixed at 5 rounds, stopping at domain/32**, so the *tested degree stays 32* while the rate drops to **ρ = 1/8**. (The subtle trap, avoided: folding all the way to length 2 as before would instead test the useless bound domain/2 and leave ρ pinned at 1/2 — *no soundness gain*. Stopping at domain/32 is the whole point.) On top of the lower rate, queries go **32 → 64** (nearly free post-v5.41). Net query-phase soundness: **~65-bit provable (unique-decoding) / ~108-bit list-decoding** — *past 80 bits by the list-decoding standard modern STARKs use*, ~65 by the conservative provable one, up from ~25–28 (ρ=1/2, 32 q). The rate lever costs ~4× the quotient/commit work (the interpreter-dogfood gate); the query lever is the cheap one — which is why the *provable* bound climbs fastest by spending queries. The proof is refactored to a single source of truth (`fri_log`/`fri_dsize`/`fri_final`/`fri_queries`), and the demo banner prints the live config so it can't drift. **Honest scope, unchanged:** the in-STARK hash is still educational **MiMC** (the vector-verified Poseidon is built but not yet wired in), the **default `glass prove` is still toy Baby Bear**, and 80-bit *across the board* + an external audit remain — the "do not protect real value / unaudited" banner in [`docs/soundness.md`](docs/soundness.md) stands. Dogfoods byte-identical (`glass.py == native_glassc`); honest ACCEPT, wrong claim REJECT, two seeds → different commitments (ZK) — the 256-coset bignum dogfood is **~2h07m on the interpreter vs ~90s native**, the rate lever's cost made concrete (and exactly why the native path is the workhorse). **Also corrected an honest overclaim** surfaced while analyzing the rate: the *default* Baby Bear path (`prove_source_adt_zk`) folds to length 2 over a 4n coset with a degree-~2n quotient (the `qm·l·r` gate ÷ Z_H), so its rate is **1/2 → ~10–12 bits**, not the ρ=1/4 / ~16–24 bits `parameters.md` had stated — the path is correctly *built* (the rate matches the quotient degree), only the stated *number* was wrong. `parameters.md` + `soundness.md` updated.

## [5.41.0] — 2026-05-28 — Memoized Merkle trees → 32 queries cheap → ~25–28 bit soundness
- **The perf unlock that v5.40 pointed to, plus the soundness it enables.** v5.40 found that raising the FRI query count was too slow because `merkle_path_g` rebuilt each layer's Merkle tree on *every* query (8→32 queries pushed the dogfood past 4 hours). This memoizes it: each FRI layer's full tree (its levels) is built **once** in `commit_g` and stored in the `Layer`; query verification reads sibling paths straight from the stored levels (`merkle_path_levels`) instead of rebuilding. Byte-identical (same hashes, just not recomputed). With query verification now cheap, the Goldilocks STARK goes to **32 FRI queries** — bringing query-phase soundness to **~25–28 bits** (≈ (3/4)³²·2⁻¹² unique-decoding to ≈ 0.707³²·2⁻¹² list-decoding, with the v5.40 12-bit grinding), up from ~4 bits at 8 queries / no grind. Dogfoods byte-identical; a wrong claim is still rejected. Honest scope: still short of an 80-bit cryptographic target — that needs a **bigger blowup** (lower rate), whose cost is the quotient evaluation, not the queries (see [`docs/parameters.md`](docs/parameters.md) §4). `parameters.md` + `soundness.md` updated.

## [5.40.0] — 2026-05-28 — Applying the analysis: grinding on the Goldilocks STARK
- **Acting on v5.39's analysis — the Goldilocks query soundness goes from ~4 bits to ~15–16 via grinding.** The parameter analysis named the FRI query phase as the weak link and grinding as the *cheap* lever; this applies it. `prove_source_goldilocks_zk.glass` adds **grinding** — a 12-bit proof-of-work on the Fiat-Shamir query seed: the prover must find a nonce whose hash clears the low 12 bits, so an adversary must redo 2¹² hashing per attempt to grind favorable query positions (the standard STARK trick, here a demo factor; production uses 20–30). A two-level search keeps recursion depth bounded (~chunk + #chunks), so neither the interpreter limit nor the native C stack is at risk, and the grind is **deterministic** so both engines find the same nonce (byte-identical dogfood). Net query-phase soundness ≈ (3/4)⁸·2⁻¹² ≈ 2⁻¹⁵ to ≈ 2⁻¹⁶, **up from ~2⁻⁴**. The verifier checks the PoW (`pow_ok`); a wrong claim is still rejected. **Honest lesson (now in [`docs/parameters.md`](docs/parameters.md)):** the *other* lever — more queries — turned out to be expensive on the interpreter because query verification re-derives each Merkle path from scratch (`merkle_path_g` rebuilds the layer tree per call); memoizing the committed trees is a noted perf item that would unlock raising ℓ cheaply. So grinding carries this step; reaching an 80-bit cryptographic target still needs a bigger blowup (perf-gated). `parameters.md` + `soundness.md` updated.

## [5.39.0] — 2026-05-28 — Concrete soundness: the parameters, analyzed
- **The "no parameter analysis" caveat, closed with rigor instead of a hand-wave.** New [`docs/parameters.md`](docs/parameters.md) writes down every parameter of both proving paths (field, value space, trace/FRI domain, rate, query count, challenge extension, hash, blinding) and computes the **actual bit-security**. The honest finding: the *challenge space* is already cryptographic-width (F_{p⁴} ≈ 2¹²⁴ / F_{p²} ≈ 2¹²⁸), but the **FRI query phase** is demonstration-grade — **~16 bits** for Baby Bear (ρ ≈ 1/4, 24 queries) and **~3–4 bits** for Goldilocks (ρ = 1/2, 8 queries). It states the standard FRI bound (commit + query phases, both the provable unique-decoding δ=(1−ρ)/2 and the list-decoding/proximity-gap δ=1−√ρ regimes) and gives a concrete **recipe to 80/128-bit** — lower the rate (bigger blowup) + more queries + grinding — with a cost table (e.g. 80-bit ≈ blowup-8, ~54 queries, or ~40 queries + 20-bit grind). [`docs/soundness.md`](docs/soundness.md) updated: the "no parameter analysis" line now points to the analysis, and item #4 of "what it would take" is marked done (the numbers exist; *applying* cryptographic-strength parameters costs prover time). No code change — this is the rigor that tells the heavier work exactly what to aim for.

## [5.38.0] — 2026-05-28 — `glass prove --goldilocks`: proving over the production field
- **`glass prove` can now prove over Goldilocks (2⁶⁴), not just toy Baby Bear (2³¹) — the start of the field migration.** Baby Bear's ~2³¹ value range means a private input is brute-forceable and any result above ~2.1·10⁹ wraps; the new `--goldilocks` flag routes the proof through the production field (p = 2⁶⁴−2³²+1) instead. [`prove_source_goldilocks_zk.glass`](examples/prove/prove_source_goldilocks_zk.glass) gains **multiple named private inputs** (each lowers to its own low wire) and **claim-binding** (the proof asserts `output == result` via the v5.34 is-zero/`GEqZero` gadget, so a wrong claimed result is rejected), plus a bignum→decimal display. Demo: `fn f(a,b,c) = a*b + c` with `a=b=100000, c=99` → **result 10000000099** (= 10¹⁰+99 — *Baby Bear cannot hold this*), honest claim **ACCEPT**, wrong claim **REJECT**, two seeds → different commitments (ZK). End-to-end: `glass prove --goldilocks <file> a=… b=…` → result + **ACCEPT** over a blinded F_{p²} FRI STARK. Dogfoods byte-identical. Scope, honestly: the Goldilocks path covers the **arithmetic/comparison subset** (`+ - * let calls == if`, multi-input) and is **heavier on the interpreter** (bignum); the **default stays Baby Bear** for the full ADT/refinement feature set, and `match`/ADTs over bignum remain the next step. The "do not protect real value / unaudited" banner in [`docs/soundness.md`](docs/soundness.md) stands.

## [5.37.0] — 2026-05-28 — Fiat-Shamir over the verified hash — the foundation is complete
- **The proof's challenges now come from a vector-verified standard hash.** [`frost_goldilocks_fiat.glass`](examples/frost/frost_goldilocks_fiat.glass) ports the domain-separated Fiat-Shamir transcript (`tr_init` / `tr_absorb` / `tr_challenge`) onto the **Plonky2-exact Goldilocks Poseidon** of v5.35 — replacing the toy MiMC `frost_grain.glass` used. Every absorb and squeeze is tagged by an integer **role**, folded in before the value, so a fold challenge can't collide with a query index at the same state, and every challenge **binds all prior commitments** (the prover commits first, then the challenge falls out). The demo runs a scripted FRI-like protocol and shows determinism, domain separation, no `(tag,v)` collision, and history-binding (tamper the first commitment → the fold challenge moves). Dogfoods byte-identical (`glass.py == native_glassc`). **With this, all four structural pieces are real/standard over Goldilocks: the field, the hash (Plonky2-exact), the Merkle commitment (v5.36), and the transcript.** Still pending (and still in `docs/soundness.md`): wiring these into the *actual proving STARK* (it still uses MiMC), the `glass prove` field migration off Baby Bear, a formal FS-separation argument, and an external audit.

## [5.36.0] — 2026-05-28 — The standard hash, made load-bearing: a Poseidon Merkle commitment
- **The verified Poseidon now drives a real commitment.** v5.35 established the *primitive* (Poseidon over Goldilocks, byte-identical to Plonky2, vector-verified). [`frost_goldilocks_merkle.glass`](examples/frost/frost_goldilocks_merkle.glass) makes it **load-bearing**: a Merkle tree built with **Plonky2's exact `two_to_one` compression** (`permute([x₀..x₃, y₀..y₃, 0,0,0,0])`, take the first 4 of 12) and `hash_no_pad` leaves — both faithful to Plonky2 and both built on the same vector-verified permutation. Commit four leaves → root, open leaf 2 with its inclusion path, **verify**; a leaf not in the tree or a tampered root is **rejected**. Dogfoods byte-identical (`glass.py == native_glassc`). This is the first step of **wiring the standard hash into the proof system's commitments**. Honest scope: the STARKs themselves still hash with the educational MiMC for Merkle + Fiat-Shamir — the Plonky2 Poseidon is ~300× heavier per call than the 4-round MiMC, so the full FRI integration is the heavier follow-on (and the `glass prove` field migration off Baby Bear remains the bigger headline item). The "do not protect real value / unaudited" banner in [`docs/soundness.md`](docs/soundness.md) stands.

## [5.35.0] — 2026-05-28 — A standard hash: Poseidon over Goldilocks, byte-identical to Plonky2
- **The toy MiMC is replaced by the real thing — and proven to be the real thing.** MiMC with ad-hoc magic-number round constants was the least defensible piece of the crypto (docs/soundness.md). [`frost_goldilocks_poseidon.glass`](examples/frost/frost_goldilocks_poseidon.glass) is **Poseidon over the production Goldilocks field, in the exact instance Plonky2 ships** (the de-facto standard Goldilocks ZK hash): t=12 state (rate 8 / capacity 4), 8 full + 22 partial rounds, S-box x⁷, Plonky2's exact MDS (circ `[17,15,41,16,2,28,13,13,39,18,34,20]` + diag `[8,0…]`) and all **360 round constants** (the Poseidon reference's "hadeshash" Grain-LFSR constants), reproduced verbatim. It's checked the only way that settles *"is this really the standard hash"*: **against Plonky2's own published test vectors — all four pass** (inputs all-zeros / 0..11 / all−1 / random GoldilocksField elements; e.g. `perm(0..11)` lane 0 = `0xd64e1e3efc5b8e9e`). The forward permutation needs no inversion, so it reuses the int64-safe Goldilocks bignum field unchanged and **dogfoods byte-identical** (`glass.py == native_glassc`). This is the first step of moving the crypto off educational-grade. Scope, honestly: this establishes the standard hash **primitive** with verified provenance; the frost/prove STARKs still hash with MiMC for Merkle + Fiat-Shamir, so **wiring this Poseidon in is the next step**, and matching a reference vector is **not** a security audit. (soundness.md updated.)

## [5.34.0] — 2026-05-28 — Comparisons and branches over the production field
- **`==` and `if`, lowered to real circuit gadgets over Goldilocks.** [`prove_source_goldilocks_zk.glass`](examples/prove/prove_source_goldilocks_zk.glass) — the bridge that takes *real prism-parsed Glass source* to a cryptographic STARK over the production field (p = 2⁶⁴−2³²+1) — now compiles `==` and `if`, not just arithmetic. Equality is a genuine field gadget, not a host shortcut: a **free inverse-hint wire** (`GHint`) plus an **assert** (`GEqZero`, the new `qe·l` constraint term) realise is-zero — `d = a−b`, `inv = d⁻¹` (or 0 when `d=0`), `di = d·inv`, `z = 1−di`, and asserting `z·d == 0` forces `z = (a==b)`, a 0/1 wire; `if c then t else f` is the mux `f + c·(t−f)`. The gadget pushes the gate count past 8, so the trace domain grows to **N=16** (interpolation, `Z_H = x¹⁶−1`, a 4× coset of 64). Demo: `fn f(x) = if x == 7 then 100 else 200; f(inp)` over a **private** `inp` → `f(7)=100`, `f(305419896)=200`, honest **ACCEPT**, a tampered output wire **REJECT**, and two blinding seeds give different commitments (zero-knowledge). Dogfood **byte-identical** (`glass.py == native_glassc`). Scope, honestly: this widens *what proves on the production field* — it does **not** change the crypto's grade (the main `glass prove` bridge is still toy Baby Bear, the hash is unaudited); moving the crypto off educational-grade is the next focus.

## [5.33.0] — 2026-05-28 — Full memory consistency in one ZK proof — the `State` capstone
- **Permutation ⊕ read-after-write, composed in a single zero-knowledge proof.** [`general_state_prove.glass`](examples/prove/general_state_prove.glass) is the capstone of the `State` story: a memory trace (`write m0=v0; write m1=v1; read m0→r2; read m1→r3`) proven consistent by *composing* the permutation argument (v5.32) with read-after-write consistency (v5.30) in one proof, all values **private**. The prover supplies the address-sorted values `s0..s3`; the proof attests (a) the sorted `(addr,val)` pairs are a multiset-**permutation** of the original (grand product `∏(γ−enc)`, `enc(addr,val)=addr+δ·val`, with `γ,δ` Fiat-Shamir'd from a hash of all values — so no value can be swapped between positions) and (b) each sorted read equals the preceding write (`s1==s0`, `s3==s2`). A tampered read is caught *either way*: faithful sorting fails consistency, faked sorting fails the permutation. `glass prove general_state_prove.glass v0=42 v1=7 r2=42 r3=7 s0=42 s1=42 s2=7 s3=7` → **result 1, ACCEPT (succinct, zero-knowledge)**; a tampered read (`r2=50`) → **R=0**. Reuses the dogfooded bridge — no new STARK code. This closes the `State` arc end to end: its three components (permutation, range/sortedness, consistency) shipped individually (v5.30–5.32) and now composed. (Sortedness is public for this fixed structure; the prover-chosen-order case adds `age_prove`'s range/bit-decomposition check — the same three pieces.)

## [5.32.0] — 2026-05-28 — A permutation argument in zero-knowledge (general-`State`'s last component)
- **The grand-product permutation argument, proven in ZK — the anti-fabrication core of every memory-consistency proof.** [`permutation_prove.glass`](examples/prove/permutation_prove.glass) proves a *private* sequence `B` is a permutation of a public set `A = [10,20,30,40]`, without revealing the ordering: two sequences are the same multiset iff `∏(γ − aᵢ) == ∏(γ − bᵢ)`, with the challenge **`γ` derived by Fiat-Shamir from a hash of the witness `B`** so a non-permutation can't be chosen after seeing it (Schwartz–Zippel: a mismatch fails except with prob ~len/p). All `*`/`-`/`==`/hash — bridge arithmetic, proven by the blinded F_{p⁴} FRI STARK; `B` is private. `glass prove permutation_prove.glass b0=30 b1=10 b2=40 b3=20` → **result 1, ACCEPT**; a `B` with a `99` not in `A` → **R=0**. This is the **third and last component** of a full general-`State` memory-consistency proof: with **permutation** (this), **range/sortedness** (`age_prove`, v5.31), and **read-after-write consistency** (`state_prove`, v5.30) all individually ZK-provable through the bridge, the general case (a prover-chosen order) is now reachable by composing them — no custom STARK. (Educational-grade `γ`: small base field, same construction as `prove_state_zk`.)

## [5.31.0] — 2026-05-28 — Range / comparison proofs in zero-knowledge (the zkVM workhorse)
- **A new ZK primitive: comparisons, via bit-decomposition range proofs.** A field has no native `<`, so `a >= k` becomes a *range* statement — `a − k` decomposes into `n` booleans — exactly the range check every zkVM is built on. [`age_prove.glass`](examples/prove/age_prove.glass) proves the canonical case: *prove you are at least 21 without revealing your age.* The proof attests `a - 21 = Σ dᵢ·2ⁱ` with each `dᵢ ∈ {0,1}` (`dᵢ·(dᵢ-1) == 0`) — all expressible in the bridge's arithmetic (`*`, `+`, `==`, `&&`) and proven by the blinded F_{p⁴} FRI STARK; `a` and the bit-witness are private. `glass prove age_prove.glass a=25 d0=0 d1=0 d2=1 …` → **result 1, ACCEPT (succinct, zero-knowledge)**; an underage `a=18` makes `a-21` negative with no 8-bit decomposition → **R=0**. This is the range/comparison building block the general `State` sortedness check (a prover-chosen order) is built on — comparisons are now reachable through the existing bridge, no new STARK code.

## [5.30.0] — 2026-05-27 — `State` consistency in *full* zero-knowledge (Phase 3 — the effect trilogy lowered)
- **Memory read-after-write consistency lowered to the real succinct + ZK prover — completing the `Inference`/`Random`/`State` lowering trilogy.** [`state_prove.glass`](examples/prove/state_prove.glass) takes the C2 `State` gadget from standalone sound-RLC to the **blinded F_{p⁴} FRI STARK** via the bridge, for a fixed memory trace (`write m[0]=v0; read m[0]→r1; write m[0]=v2; read m[0]→r3`): the values are a *private* witness pinned by a public commitment `C`, and the proof attests in zero-knowledge that the trace is **read-after-write consistent** (`r1==v0`, `r3==v2` — each read equals the last write) and opens to `C` — revealing the trace's shape and "consistent," never the values. `glass prove state_prove.glass v0=42 r1=42 v2=99 r3=99` → **result 1, ACCEPT (succinct, zero-knowledge)**; an inconsistent read (`r1=50`) → `R=0`. Because the trace *order* is fixed and public, consistency is direct equality (no sorting needed); the general case — a prover-chosen order guarded by a **permutation argument** against fabrication — stays the standalone `prove_state_zk` (sound) and the heavier in-circuit follow-on. All three effect gadgets now have a full-ZK realization through the dogfooded bridge — no new STARK code.

## [5.29.0] — 2026-05-27 — `Random` in *full* zero-knowledge (Phase 3, cont.)
- **Provably-fair randomness lowered to the real succinct + ZK prover.** Following the `Inference` lowering (v5.28), [`random_prove.glass`](examples/prove/random_prove.glass) takes the C2 `Random` gadget (a draw bound so it can't be ground) from standalone sound-RLC to the **blinded F_{p⁴} FRI STARK** via the bridge: the committer holds a private `seed`, publishes only a commitment `C`, a public beacon (fixed *after* C) determines the fair draw `D = derive(seed, beacon)`, and the proof attests in zero-knowledge that the *same committed seed* produced the public `D` — revealing `C`, the beacon, and `D`, never the seed. `glass prove random_prove.glass seed=7777` → **result 1, proof ACCEPT (succinct, zero-knowledge)**; a wrong seed yields `R=0` and can't be forged (a different seed gives a different `C` *and* `D` — binding). Un-grindable (C fixed before the beacon), reuses the dogfooded bridge — no new STARK code. Two of the three effect gadgets (`Inference`, `Random`) are now lowered to full ZK; **`State` remains** standalone sound-RLC (its in-circuit memory-permutation + range arguments aren't reachable from the source bridge — the genuinely heavy follow-on).

## [5.28.0] — 2026-05-27 — The trust boundary, in *full* zero-knowledge (Phase 3: sound → succinct ZK)
- **The C3 trust-boundary check, lowered from a standalone sound-RLC demo to the real succinct + zero-knowledge prover.** Every C2/C3 effect demo carried the caveat "sound here; the FRI STARK adds succinct + ZK." This closes it for the marquee one: [`trust_prove.glass`](examples/prove/trust_prove.glass) expresses the trust-boundary check — a binding commitment to the model's answer + the refinement (`answer` must be a bit) — as real Glass source, and proves it through the **existing, verified blinded F_{p⁴} FRI STARK** (`glass prove`), not a hand-rolled RLC. `glass prove trust_prove.glass answer=1 nonce=42` → **result 1, proof ACCEPT (succinct, zero-knowledge)**; a non-conforming answer yields `R=0` and cannot be forged to 1 (5 fails the bit check; even 0 fails — the commitment binds the *specific* answer). The model output stays a private witness throughout; `R=1` is a zero-knowledge certificate that the committed answer met the type-level contract. Reuses the dogfooded bridge — no new STARK code, no new unverified crypto. This is a **Phase 3** item from the recommended path (lower the sound gadgets to the FRI STARK), done for the Inference/trust-boundary gadget; `Random`/`State` remain standalone sound-RLC (their in-circuit transcript / memory-permutation lowering is the heavier follow-on).

## [5.27.0] — 2026-05-27 — The trust boundary, proven (C1 ⊕ C2 — LANG.md's AI-era centerpiece)
- **A model's output, contained by its refinement, proven in zero-knowledge — the convergence of refinement types (C1) and the Inference effect (C2).** LANG.md's §"Refinement types as trust boundary" describes the AI-era contract: `fn classify(prompt) : Int where (result == 0 || result == 1) !{Inference}` — *this calls a model, and whatever it returns must be a bit.* [`prove_trust_boundary_zk.glass`](examples/prove/prove_trust_boundary_zk.glass) realizes it as a proof: prism parses the signature, and **both halves are read straight off the type** — the effect row (`!{Inference}`) says the output is an untrusted model oracle, so it's a private witness pinned by a hiding commitment `C = hash(prompt, answer, nonce)`; the return refinement (`where (P)`) is the trust contract, its predicate *parsed from the type and evaluated* on the committed answer. The proof attests (sound RLC, γ from `C`): the answer opens to the commitment **and** satisfies the refinement — revealing `C` and "the contract held," never the answer. A valid bit ACCEPTs; an answer of 5 (violating `result == 0 || result == 1`) is **unprovable**; a fresh nonce hides the answer. *You don't prove the model is correct — you prove your program only accepted output that met the type-level contract.* Self-hosted byte-identical. (Caught a prism `eval_pred` name-clash via the reference typechecker — renamed; native is type-erased and had silently used the right one.)

## [5.26.0] — 2026-05-27 — The end-to-end story, refreshed (U2)
- **[`docs/the-story.md`](docs/the-story.md) now tells the *whole* arc.** It had stopped at "queries over private data" (section 4) — predating the frontier built since. Two sections added, in the same voice, every shown command verified to run: **§5 "It proves what you wrote — and what you promised"** (real Glass source — recursion, linked lists, higher-order functions — lowered to a proof; and a function's refinement `where`-clause asserted *in-circuit*, so the type becomes a cryptographic guarantee and a function that lies about its type is unprovable; now also over the production Goldilocks field), and **§6 "It proves what your code touches"** (the effect row *generates the proof* — `Inference`/`Random`/`State` each a committed trace entry; the LLM-in-the-loop case: prove a computation used a committed model answer faithfully, revealing nothing about it). The intro now spans the fuller arc ("of what a program computed, the types it promised, and the effects it touched"), and the close points to the [soundness ledger](docs/soundness.md) — the cryptography is honestly educational-grade. This is the roadmap's **U2**.

## [5.25.1] — 2026-05-27 — Portability fix: GCC support (don't hard-require `-fbracket-depth`)
- **Fixed a real portability bug: the native compile now works on GCC, not just Clang.** Quartz (`quartz.py`) and the self-hosted compiler (`glassc.glass`) invoked `cc` with `-fbracket-depth=100000` — a **Clang-only** flag (it raises the expression-nesting limit for the deeply-nested C they emit). GCC *rejects* the flag outright, so on a GCC box every test that shells out to `cc` failed (the cause behind reports of ~213/381 in GCC sandboxes — an environment/portability issue, not a code defect). Both sites now **try `cc` with the flag and fall back without it** when `cc` rejects it; GCC's default nesting limit is higher, so the fallback compiles. Verified: 381/381 on Clang (unchanged), and a GCC-simulating `cc` (one that rejects the flag) now compiles and runs via the fallback — through both `quartz.py` and `glassc.glass`. The bootstrap fixpoint still holds (self-compilation byte-identical). Clang is no longer required; GCC is supported.

## [5.25.0] — 2026-05-27 — The effect row generates the proof (C2, step 4 — the unifying step)
- **The proof's obligations are now *derived from a function's effect row*.** Steps 1–3 proved one effect each; [`prove_effects_zk.glass`](examples/prove/prove_effects_zk.glass) unifies them: prism parses a signature, the bridge reads the `!{…}` row off the function type (`TyFn(_, _, EffRow(labels, _))`), and each label becomes a **proof obligation** — `Inference → committed-oracle check`, `Random → transcript-bound draw`, `State → memory-consistency`, `IO → committed read`. A single driver then discharges every obligation with the matching gadget from steps 1–3. Demo: `fn analyze(x) : Int !{Inference, Random, State}` → its row parses to 3 obligations → all discharged → ACCEPT; a *pure* `fn plain(x) : Int` yields an empty schema (just prove the result); `fn coin(x) : Int !{Random}` yields one. **Change the row, the schema changes — the effect row *is* the proof's statement.** Because Glass's type checker refuses to let a function perform an undeclared effect, the row is complete, so the derived schema covers every effect the function can have. Self-hosted byte-identical. This completes the **C2** arc (the four steps: `Inference`, `Random`, `State`, and now the type-derived schema) — *read the signature, know what the proof proves.* ([design](docs/effects-in-proofs.md)). Sound prover-side gadgets; the FRI STARK adds succinct + ZK.

## [5.24.0] — 2026-05-27 — Proving a `State`-effectful computation: memory consistency (C2, step 3)
- **The deep effect lands: mutable `State`, proven via a memory-consistency argument — every read pinned to the last write, and the log un-fakeable.** [`prove_state_zk.glass`](examples/prove/prove_state_zk.glass) is the construction at the heart of every zkVM, written from scratch: the `State` effect emits an access trace `Acc(addr, time, val, op)` in program order; the prover also supplies it re-sorted by `(addr, time)`; three checks make the log undeniable — **(1) permutation** (the sorted trace is a multiset-permutation of the original, via a grand product `∏ (γ − encode(accessᵢ))` with `γ`/`δ` drawn by Fiat-Shamir from a commitment to the trace — Schwartz–Zippel, so no entry can be fabricated/dropped/altered), **(2) sortedness** (ordered by `addr` then `time`, so "the previous entry at this address" is well defined), and **(3) read-after-write consistency** (a same-address read returns the previous entry's value — the last write; a first/new-address read sees 0). Demo: a 6-access program (`write m[0]=42; write m[1]=7; read m[0]; write m[0]=99; read m[0]; read m[1]`) ACCEPTs; a read that lies about its value (50, when the last write was 99) is caught by **consistency** *even though the permutation still holds* (changed in both orderings); a fabricated sorted trace is caught by the **permutation** fingerprint. Self-hosted byte-identical. This completes the **C2** triad (`Inference`, `Random`, `State`); sound prover-side here, lowering the permutation to a FRI'd z-accumulator (`prove_zperm`) + the order checks to range gadgets adds succinct + ZK. ([design](docs/effects-in-proofs.md).)

## [5.23.0] — 2026-05-27 — Proving a `Random`-effectful computation (C2, step 2)
- **The second effect gets its proof: `Random`, bound so it can't be ground.** [`prove_random_zk.glass`](examples/prove/prove_random_zk.glass) models `random_int` as a draw **pinned to the Fiat-Shamir transcript** — the prover commits its inputs first, then the randomness falls out of a hash of the transcript, so it's determined, unpredictable, and un-grindable (the same way the STARK draws its own FRI challenges, lifted to a language effect; the transcript is domain-separated, every absorb/squeeze tagged by role). Demo — a **provably-fair dice roll / randomness beacon**: a committer publishes only `C = hash(seed)` (seed private), a *public beacon* is fixed afterward, and `roll = (draw over transcript[C, beacon]) mod 6 + 1`. Because `C` is fixed before the beacon, the committer can't grind the roll; because the derivation is a deterministic function of the *public* `(C, beacon)`, anyone verifies it was honest — while the seed stays private. Shown: verifiable from public data alone, deterministic, un-grindable (the draw avalanches with the beacon), and bound to the seed. Self-hosted byte-identical. This is **C2 step 2** ([design](docs/effects-in-proofs.md)); sound here, the FRI STARK adds full ZK.

## [5.22.0] — 2026-05-27 — Proving an `Inference`-effectful computation (C2 seed)
- **The first piece of effects-in-the-proof-story: an `Inference` (LLM) call, proven in zero-knowledge.** Glass tracks side-effects in the type (`model_call(prompt) : String !{Inference}` reaches outside the program to a model). [`prove_inference_zk.glass`](examples/prove/prove_inference_zk.glass) shows how to prove such a computation: the model's answer becomes a **committed oracle** — a *private* witness pinned by `C = hash(prompt, ans, nonce)` (binding + hiding) — and the proof attests a downstream pure validator over it, revealing `C` and that it passed, **not the answer**. You don't prove the model is *correct*; you prove the computation used a committed model response *faithfully*. Demo: the model returns an answer in an allowed set `{17, 42, 99}`; the proof attests *"the answer is an allowed option, committed in C"* without revealing which — honest ACCEPT, a disallowed answer (50) REJECTs, and even swapping in a *different allowed* answer (17) REJECTs because `C` binds the specific output; a fresh nonce gives a different `C` for the same answer (hiding). A sound random-linear-combination ties commitment-opening and validation with a Fiat-Shamir challenge from `C`. Self-hosted byte-identical. This is the **C2** seed (effect = committed trace entry; the effect row is the proof's schema). Sound here; lowering it to the blinded FRI STARK adds succinct + zero-knowledge, as `prove.glass` → `prove_zk` did. (Design: [`docs/effects-in-proofs.md`](docs/effects-in-proofs.md).)

## [5.21.0] — 2026-05-27 — Lambda literals as higher-order arguments (E2-next)
- **Lambda literals can now be passed as function arguments and proven in ZK.** v5.14's higher-order support took only top-level function *names* (`twice(inc, x)`); the unroll's `fenv` now maps a function-valued parameter to a function *value* — a top-level fn **or** an `ELam` — so a lambda literal argument (and a directly-applied lambda) is inlined too. [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass): `fn twice(f: (Int) -> Int, x) : Int where (result != 0) = f(f(x)); twice(fn(n) -> n + 1, inp)` proves `(inp+1)+1 = 7` over a private input **and** its refinement in-circuit (ACCEPT); lying `ident` REJECTs; two seeds verify with a differing opening (ZK). The whole higher-order program is still beta-reduced to a first-order, call-free circuit (no closures in the proof); a lambda's captured variables resolve via the enclosing `let`s in the unrolled term. Self-hosted byte-identical (ng=32). Regression-checked: top-level-fn HOF, recursion, and recursive-list folds all still pass with the generalized `fenv`. This is **E2-next**.

## [5.20.0] — 2026-05-27 — Real Glass source → a ZK proof over Goldilocks (the source front-end, wired in)
- **Real prism-parsed Glass source now proves over the production field.** [`prove_source_goldilocks_zk.glass`](examples/prove/prove_source_goldilocks_zk.glass) wires the source front-end into the Goldilocks backend: source text → **prism parse** → **unroll** (calls and higher-order arguments inlined to a call-free term) → a **Goldilocks `cgen`** (lowers `+`/`-`/`*`/`let` to gates + a bignum witness) → the **R1b cryptographic STARK** (committed, F_{p²}-challenged via Fiat-Shamir, query-verified, blinded). The output wire *is* the function's result, so claiming a wrong value breaks the gate that produced it. Demo: `fn sq(n) = n * n; fn f(x) = sq(x) + 5; f(inp)` proves `f(inp) = inp²+5` over Goldilocks (2⁶⁴, no 2³¹ wrap) — honest ACCEPT, tampered REJECT, two blinding seeds → different commitments (ZK). Self-hosted byte-identical. This advances **R1** (wire Goldilocks through the bridge): *write Glass source, get a succinct zero-knowledge proof on the field real provers use.* **Scope:** the hint-free arithmetic subset (`+`, `-`, `*`, `let`, calls inlined) — exactly the subset `prove_source_zk` began with, now on the real field; comparisons / `match` / ADTs (which need is-zero inverse-hint wires in the bignum witness) and the heavier circuits are the remaining step.

## [5.19.0] — 2026-05-27 — The Goldilocks circuit proof, now a full cryptographic STARK (R1b complete)
- **R1b's Goldilocks gate quotient is upgraded from a fixed base-field fold to the full cryptographic STARK.** [`prove_circuit_goldilocks_zk.glass`](examples/prove/prove_circuit_goldilocks_zk.glass) now embeds the quotient codeword into **F_{p²}**, blinds it, and **Merkle-commits each FRI layer**; the fold challenge **β ∈ F_{p²} ≈ 2¹²⁸** is derived from each layer's root (**Fiat-Shamir**, so unpredictable), and sampled query positions are **opened against the commitment** — a prover whose Q isn't low-degree is caught at (almost) every query. Honest → 8 Fiat-Shamir queries all verify (ACCEPT); tampered → the queries catch the inconsistency (REJECT); two blinding seeds → different layer-0 commitments (ZK). So the proof is now **committed, F_{p²}-challenged, query-verified, and blinded** — the production STARK shape, on the production field. (FRI-over-F_{p²} + Merkle from `frost_goldilocks_zk`, applied to the gate quotient.) Self-hosted byte-identical; closes the honest-scope gap noted in v5.17. **Remaining:** wire it into the full source bridge (`prove_source_*` still computes over Baby Bear).

## [5.18.0] — 2026-05-27 — README, re-voiced
- Rewrote the [README](README.md) to carry the project's deeper current — faithful re-execution, two independent reconstructions forced to meet at every bit, and a proof of what a computation did — around the same factual claims and commands. "It compiles itself" → "It reconstructs itself" (the differential-testing discipline framed as replay-and-check: diverge and it's a desync, the build stops); "It proves itself" → "It proves what happened."
- Surfaced the [soundness ledger](docs/soundness.md) on the front page (the "Where to go" table and Status): *nothing taken on faith, including the faith you'd place in it.*

## [5.17.0] — 2026-05-27 — A Glass circuit proven succinctly + ZK over Goldilocks (R1b)
- **A Glass arithmetic circuit, proven SUCCINCTLY and in zero-knowledge over the production field.** R1 (`prove_circuit_goldilocks.glass`) proved a circuit over Goldilocks (p = 2⁶⁴−2³²+1) with a sound but *linear-verifier* RLC. R1b ([`prove_circuit_goldilocks_zk.glass`](examples/prove/prove_circuit_goldilocks_zk.glass)) makes it **succinct**: the gate constraints become a single low-degree polynomial, FRI-tested. The construction is `prove_quotient`'s (Baby Bear), **ported to Goldilocks in base-2¹⁶ bignum limbs** — lay the gates in rows with selector columns `qa/qm/qs/qc` + value columns `l/r/o/c`; interpolate each over the trace domain H (N=8) by an **inverse NTT**; the gate identity lifts to `G(x) = qa·(o−(l+r)) + qm·(o−l·r) + qs·(o−(l−r)) + qc·(o−c)`, which vanishes on H ⟺ every gate holds; so `Q = G/Z_H` (Z_H = xᴺ−1) is genuinely **low-degree iff the constraints hold**. Evaluate Q on a 32-coset and FRI-fold: honest → folds to a constant (**ACCEPT**); tamper any wire → G stops vanishing, Q isn't a polynomial, the fold doesn't reach a constant (**REJECT**). The output binds the claim automatically (claiming a wrong `f(x)` breaks the gate that produced it). **Zero-knowledge:** Q is blinded with a random low-degree mask — FRI is linear, so Q+R still folds to a constant and ACCEPTs, but every opened value is randomized (two seeds → two different valid proofs of the same statement). Demo: `f(x) = x*x + 5` over a private 2⁶⁴-range input (no 2³¹ wrap), honest ACCEPT / tampered REJECT / two seeds verify with a differing opening. Self-hosted byte-identical (heavy bignum — run via `run_native.sh`). This is the roadmap's **R1b**: succinct + ZK over the real field, retiring the Baby Bear value-range cap for the proven circuit. **Honest scope:** the fold uses a fixed base-field challenge here; the cryptographic F_{p²} fold challenge + Merkle query-verification (built for codewords in `frost_goldilocks_zk`) are the next wiring step — the same Stage-3 → Stage-4 split the Baby Bear bridge used.

## [5.16.0] — 2026-05-27 — A domain-separated Fiat-Shamir transcript (R2, step 2)
- **A Fiat-Shamir transcript with domain separation, built on the Grain Poseidon.** [`frost_grain.glass`](examples/frost/frost_grain.glass) gains `tr_init`/`tr_absorb`/`tr_challenge`: a non-interactive proof derives its challenges by hashing the transcript of prover messages, and soundness needs **domain separation** — a challenge meant for "fold round 2" must never coincide with one meant for "query index", even at the same transcript state. Every absorb and squeeze is **tagged by an integer role**, folded in *before* the value (`state' = H(H(s, tag), v)`), so `(tag, v)` for different roles can't collide. A scripted FRI-like protocol (commit → fold challenge → bind back → commit → query index) demonstrates: **determinism** (same script → same challenges), **domain separation** (tag 20 ≠ tag 30 at the same state), **no (tag,value) collision**, and **binding to history** (tampering the first commitment changes every later challenge). Self-hosted byte-identical. This is roadmap **R2 step 2** (the soundness ledger's Fiat-Shamir row is updated). **Honest scope:** domain separation is implemented and demonstrated, but there's no formal transcript-separation *proof*, and it isn't yet wired into the prove bridge's challenges.

## [5.15.0] — 2026-05-27 — Poseidon round constants from the Grain LFSR (R2, first step)
- **Poseidon's round constants now come from the spec's Grain LFSR, not a hand-picked schedule.** [`frost_grain.glass`](examples/frost/frost_grain.glass) implements the Poseidon Grain LFSR from scratch: an 80-bit state initialized from the concrete parameters (field flag, S-box type, field size, `t`, `R_F`, `R_P`, then thirty 1s), feedback taps `b₀⊕b₁₃⊕b₂₃⊕b₃₈⊕b₅₁⊕b₆₂`, a 160-round warm-up, and **rejection sampling** (draw `n` bits MSB-first, redraw if ≥ p) so every constant is a uniform residue. Glass has no bitwise ops, so a bit is an `Int ∈ {0,1}`, XOR is `(a+b)%2`, and the state is a `List<Int>`. It generates the 90 constants (30 rounds × 3 lanes) and feeds the same `x⁷` Poseidon permutation — which stays deterministic, order-sensitive, collision-free on samples, and avalanching. Self-hosted byte-identical. This is the first step of roadmap **R2** and directly addresses the hash caveat in [`docs/soundness.md`](docs/soundness.md) (the ledger is updated). **Honest scope:** the construction follows the spec's *structure* but is **not yet cross-checked against Poseidon's official reference test vectors**, the MDS/round-counts aren't analyzed, and the hash is unaudited — a real upgrade over hand-picked constants, not a final word.

## [5.14.0] — 2026-05-27 — Higher-order functions in zero-knowledge (E2)
- **A higher-order function — one that takes another function as an argument — proven in zero-knowledge.** The `unroll` pre-pass now carries an `fenv` mapping a function-valued *parameter* to the top-level function it was passed (`fn twice(f, x) = f(f(x)); twice(inc, …)` binds `f → inc`). When a call's head resolves through `fenv` to a top-level fn, it inlines that fn — so the higher-order program is **beta-reduced to a first-order, call-free term**, and `heval`/`cgen` need *zero* changes (higher-order source, first-order proof; no closures in the circuit). The `fenv` threads through the recursion, so a **recursive** higher-order function works too: `suml(map(inc, Cons(5, Cons(2, Cons(3, Nil))))) = 13` proves correctly (verified). [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass)'s demo proves `twice(inc, inp) = 7` over a *private* input **and** its refinement `where (result != 0)` in-circuit (ACCEPT, ng=32); the lying `ident` REJECTs; two seeds verify with different openings (ZK). Self-hosted byte-identical. Reachable via `glass prove` — [`map_prove.glass`](examples/prove/map_prove.glass) composes HOF + recursion + lists. This is the roadmap's **E2**. (Scope: top-level function names as arguments — the canonical HOF case; capturing lambda literals are future work.)

## [5.13.0] — 2026-05-27 — Recursive datatypes (linked lists) in zero-knowledge (E1-next)
- **A fold over a recursive linked list, proven in zero-knowledge — with no new machinery.** A recursive datatype `type IntList = Nil | Cons(Int, IntList)` lays out as a **fixed-width buffer** (the type-directed `twidth` already bounds a recursive type's wire-width by a depth fuel), and a recursive fold `fn suml(l) = match l { Nil => 0; Cons(h, t) => h + suml(t) }` is **bounded-unrolled** by the v5.12 pass — so an entire linked list *and* the fold over it compile to one arithmetic circuit. The two bounds compose: the multi-wire ADT layout (since the ADT bridge) supplies the recursive *data*, and the unroll pre-pass supplies the recursive *function*. [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass)'s demo proves `suml(Cons(inp, Cons(2, Cons(3, Nil)))) = 10` over a *private* head **and** its refinement `where (result != 99)` in-circuit (ACCEPT); a wrong claim or the lying `ident` REJECTs; two seeds verify with different openings (ZK). Self-hosted byte-identical (ng=256). Reachable via `glass prove` — [`list_sum_prove.glass`](examples/prove/list_sum_prove.glass). This is the roadmap's **E1-next**: the recursive-datatype frontier, reached by *composition* — the cleanest kind of progress. (Scope: lists bounded by the layout/unroll fuel — exact for depth ≤ 5.)

## [5.12.0] — 2026-05-27 — Bounded recursion in the prove bridge (E1)
- **A recursive function can now be proven in zero-knowledge.** [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass) gains a source-level **unroll pre-pass** (`unroll`/`inline_fn`): a self-recursive call is inlined to a fixed depth, with each call rewritten as `let p = arg in body` — so an argument used many times is still evaluated once (no duplicate gates), and the unrolled term is **call-free**, so the circuit generator never recurses on `EApp`. Past the bound a call lowers to `0`; for inputs within the bound the base case fires first, so the cutoff sits in a branch the `if`/`match` discards and the result is exact. The same transform runs on `glass.py` and on native (and `ref_result` unrolls too), so the claimed result and the circuit agree on the same bounded semantics — and it stays byte-identical.
- **Demo — recursion ⊕ refinement, fused:** `fn fact(n) : Int where (result != 0) = if n == 0 then 1 else n * fact(n - 1)` proves `fact(5) = 120` over a *private* input **and** proves its own `where` clause in-circuit (ACCEPT); the lying `ident` still REJECTs; two seeds verify with different openings (ZK). Recursive functions are also reachable through `glass prove` — see [`fact_prove.glass`](examples/prove/fact_prove.glass). This is the roadmap's **E1**. (Scope: recursion bounded by a fixed unroll depth — the honest limit of a circuit model, which has no unbounded loops.)

## [5.11.0] — 2026-05-26 — An honest soundness ledger (R3)
- **[`docs/soundness.md`](docs/soundness.md) — what Glass's proofs actually guarantee.** With "zero-knowledge proof" claimed across 30+ files and the repo public, this is the integrity ledger: it separates the **strong, real differential-testing guarantee** (glass.py ⟷ native_glassc byte-identical, the bootstrap fixpoint — a correctness/consistency guarantee) from the **educational-grade cryptography** (Baby Bear's ~2³¹ value range, the F_{p⁴} ≈ 2¹²⁴ *challenge* space which *is* cryptographic-width, the unaudited MiMC/Poseidon hash with non-standard round constants, no parameter analysis or audit). Per-component table, what `glass prove` specifically does/doesn't guarantee, the ordered path to production-soundness, and a blunt bottom line: *Glass is a complete, self-hosted **demonstration** of a zk-STARK and a ZK-native language — not production cryptography; do not use it to protect real value.* Linked from the docs index. This is the roadmap's **R3**, and it's the responsible counterweight to the capability claims.

## [5.10.0] — 2026-05-26 — Proving a function's refinement type in zero-knowledge (C1)
- **Glass proves its own refinement types in zero-knowledge.** [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass) extracts a function's return refinement — `fn f(..) : Int where (P) = ..` parses to a return type `TyRefine(Int, "result", P)` — binds `result` to the circuit's output, lowers the predicate `P` to gates, and asserts it. The `where` clause becomes a **cryptographic guarantee about the result**, not just a runtime check, and a function that *violates* its declared refinement is **unprovable** (the in-circuit assertion fails). Demo: `fn classify(x) : Int where (result == 0 || result == 1) = if x == 0 then 0 else 1` proves ACCEPT (the result is a bit), while `fn ident(x) : Int where (result == 0 || result == 1) = x` REJECTs (5 ∉ {0,1}). Two seeds verify with different openings (ZK). This is the roadmap's **C1** — the convergence of types and zero-knowledge, which no other language can do because none has the type system and the prover in one self-hosting language.
- **Fixed a latent gap:** the ADT source-bridge's `cgen`/`heval` were missing `||`, `&&`, `!=`, and `!` (its demos only exercised `match`/ADTs); they now lower correctly (`&&`→`a·b`, `||`→`a+b−ab`, `!`→`1−a`, `!=`→`1−(a==b)`). Self-hosted byte-identical.

## [5.9.0] — 2026-05-26 — Tuples in the prove bridge
- **The source→ZK bridge now handles tuples.** [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass) supports `ETuple`/`PTuple`/`TyTuple`: a tuple `(a, b)` is a **tagless** multi-wire value (just the concatenation of its elements — no constructor tag), `(x, y)` patterns always match and bind positionally, and a function may **return** a tuple (the result mux is element-wise over its wires). Demo: `fn swap(p: (Int, Int)) : (Int, Int) = match p { (x, y) => (y, x) }; fn first(p) = match p { (a, b) => a }; first(swap((inp, 7)))` over a *private* `inp` proves the result = 7 — honest ACCEPT, lying REJECT, ZK. Self-hosted byte-identical. (Scope: tuples of scalar elements — the common case; reuses the type-directed layout via a synthetic width-1-per-element type list. Also reachable through `glass prove`.)

## [5.8.0] — 2026-05-26 — `glass prove` — the zero-knowledge prover as a command (U1)
- **The prove bridge is now a tool, not a pile of demo files.** `glass prove <file.glass> [name=value …]` compiles the file's `main` expression into an arithmetic circuit and emits a succinct, zero-knowledge proof of its result. Names passed on the command line are **private inputs** — they stay in the witness; the proof reveals only the result. The prove logic stays in Glass (the command assembles a driver over `prove_source_adt_zk.glass`, the most complete bridge — arithmetic, `let`, calls, `==`/`if`, and `match` over nested ADTs), so there's no second implementation to keep honest. Example: `glass prove examples/prove/hello_prove.glass inp=9` → `result: 86`, `proof: ACCEPT (succinct, zero-knowledge)`. This is the roadmap's **U1** — "a feature, not a library you assemble by hand." (`glass prove` both proves and verifies; the heavy STARK runs interpreted, so keep inputs small or use the native path for scale.)

## [5.7.0] — 2026-05-26 — A Glass circuit proven over the real field (Goldilocks) — R1
- **The prove bridge reaches the production field.** Every bridge proof so far computed over toy Baby Bear (values mod 2³¹, which wrap). [`prove_circuit_goldilocks.glass`](examples/prove/prove_circuit_goldilocks.glass) compiles a Glass arithmetic circuit (`f(x) = x*x + 5`, plus a `GEq` binding the output to a public claim `R`) and proves it over **Goldilocks** (p = 2⁶⁴ − 2³² + 1, the field Plonky2/RISC Zero use): real 64-bit-range values, no wraparound. The argument is the sound RLC — commit the witness (a Goldilocks MiMC hash), derive a challenge γ ∈ **F_{p²} ≈ 2¹²⁸** from the commitment (Fiat-Shamir), and check `Σ residualᵢ·γⁱ == 0`; by Schwartz–Zippel a violated gate makes the RLC nonzero except with probability ~(#gates)/2¹²⁸. Honest ACCEPT, lying about `R` REJECT. Int64-safe (base-2¹⁶ limbs), dogfoods byte-identical. This is **R1**'s dogfoodable first step (sound + real-field); succinct + zero-knowledge over Goldilocks — the FRI quotient over bignum — is the heavier native-primary follow-on, mirroring the Baby Bear RLC→FRI progression.

## [5.6.0] — 2026-05-26 — Nested patterns (destructure a nested ADT in one match)
- **Structured pattern matching is now complete to arbitrary depth.** [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass) handles nested constructor patterns: `match l { L(P(x, y), b) => x + y }` destructures the inner `Point` directly. The arm selector becomes the **product of is-zeros down the pattern tree** (tag = L *and* field 0's tag = P), `psel`/`pmatch`/`psel_hint` recurse into field patterns (slicing each sub-value by type width), and binders recurse too (a `PVar` at any depth binds its slice). Demo: `type Point = P(Int,Int); type Line = L(Point, Point); fn endx(l) = match l { L(P(x, y), b) => x + y }; endx(L(P(inp, 7), P(2, 3)))` over a *private* `inp` proves the result = 12 — honest ACCEPT, lying REJECT, ZK. Self-hosted byte-identical. The source→ZK bridge now covers the full first-order pure-functional core over real prism Glass: arithmetic, let, calls, comparisons/booleans, if, and `match` over (nested) ADTs with (nested) patterns.

## [5.5.0] — 2026-05-26 — Nested ADTs (a field can be an ADT), via type-directed layout
- **The source→ZK bridge handles ADTs whose fields are themselves ADTs.** [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass) gains a **type-directed layout**: a value's wire-width is computed from the type declarations (`twidth` — a sum type padded to its widest constructor), so `ECtor` pads each field to its declared width and a `match`/`PCtor` slices fields out of the flat wire list by those widths (`slicew`). A `Line` holding two `Point`s lays out as one list `[tagL, tagP,x,y, tagP,x,y]`; `fst(l) = match l { L(a, b) => a }` slices the first `Point` sub-value (itself an ADT) and returns it. Demo: `type Point = P(Int,Int); type Line = L(Point, Point); fn fst(l) = match l { L(a,b) => a }; fn sm(p) = match p { P(x,y) => x+y }; sm(fst(L(P(inp,1), P(2,3))))` over a *private* `inp` proves the result = 6 — honest ACCEPT, lying REJECT, ZK. Self-hosted byte-identical. (Bounded to non-recursive types via a depth fuel; field patterns are `PVar`/`PWild` — nested `PCtor` *inside* a field pattern is the next layer.)

## [5.4.0] — 2026-05-26 — ADT-returning matches (a match can build an ADT)
- **The source→ZK bridge now handles matches that *return* an ADT.** [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass) generalizes the match-result multiplexer from a single wire to **element-wise over the body's wires** (`accw`): the result accumulator starts empty and the first arm establishes the body's width, so a function like `fn mv(p) = match p { P(x, y) => P(x + 1, y + 2) }` — whose match body builds a `Point` — compiles, with each output wire `result_i += eff·body_i`. Demo: `type Point = P(Int, Int); fn mv(p) = match p { P(x,y) => P(x+1, y+2) }; fn sm(p) = match p { P(x,y) => x+y }; sm(mv(P(inp, inp)))` over a *private* `inp` proves the result = 13 — honest ACCEPT, lying REJECT, ZK. Self-hosted byte-identical. (`heval`'s first-match selection already returned multi-wire values, so only the circuit side changed. Nested-ADT fields — a field that is itself an ADT — remain the next layer.)

## [5.3.0] — 2026-05-26 — Real Glass source with ADTs → a zero-knowledge proof (multi-wire values)
- **The source→ZK bridge handles algebraic data types over real prism source.** [`prove_source_adt_zk.glass`](examples/prove/prove_source_adt_zk.glass) generalizes the bridge's circuit value from a single wire to a **multi-wire list** `[tag, f0, f1, …]` (a scalar is `[w]`; an ADT `Ctor(a, b)` is `[tag, wa, wb]`, where `tag` is the constructor's index in its type declaration). Real prism `ECtor` builds such a value; a `match` with `PCtor(C, vars)` dispatches on wire 0 (is-zero(tag − ctor_tag), inverse hint on an input wire) and binds the pattern variables to the field wires. `cgen`/`heval` thread multi-wire values through every form. Demo: `type Shape = Circle(Int) | Rect(Int, Int); fn area(s) = match s { Circle(r) => 3·r·r; Rect(w, h) => w·h }; area(Circle(inp))` over a *private* `inp` proves `area = 27`: honest ACCEPT, lying REJECT, two blinding seeds give different openings (zero-knowledge). Self-hosted byte-identical. (Scope: flat ADTs with scalar fields; nested-ADT fields and ADT-returning matches are the next layer.)

## [5.2.0] — 2026-05-26 — Structured ADT match, in zero-knowledge
- **`prove_adt_zk.glass` proves a structured ADT match succinct + zero-knowledge.** Upgrades `prove_adt`'s sound-RLC structured match to the blinded F_{p⁴} FRI STARK. An ADT value is a tagged tuple `(tag, f0, f1)`; `match s { Circle(r) => 3·r·r; Rect(w, h) => w·h }` dispatches on the tag (is-zero gadget, inverse hint on an input wire), binds the field wires, and multiplexes the bodies (first-match). The ADT value is *private*; a `qassert` binds the match output to a public claim `R`. Proves "I know an `s` with `area(s) = R`" (R = 27): honest ACCEPT, lying REJECT, two blinding seeds give different openings (zero-knowledge). Self-hosted byte-identical. (Hand-shaped `(tag, f0, f1)` representation — wiring prism's real `ECtor`/`PCtor` through the general source bridge, where every value becomes multi-wire, is the larger follow-on.)

## [5.1.0] — 2026-05-26 — The source→ZK bridge gains scalar `match`
- **`prove_source_zk` now proves real `match` expressions.** [`prove_source_zk.glass`](examples/prove/prove_source_zk.glass) extends the bridge with scalar pattern dispatch: `match x { 7 => 100; k => k * k }`. Each arm becomes a selector (`PInt`/`PBool` via the is-zero gadget — consuming an inverse hint; `PVar`/`PWild` always match), combined first-match style (`eff = sel·(1−matched)`, `result += eff·body`, `matched += eff`) so the circuit is branchless. The hint pre-pass (`heval`) was extended to collect each arm's selector hint and all bodies' hints in the exact order `cgen_match` consumes them. Demo: `fn grade(x) = match x { 7 => 100; k => k * k }` over a private input proves `grade(inp) = 100` (honest ACCEPT). Self-hosted byte-identical. (`PCtor`/`PTuple`/`PRecord`/`PStr` patterns are treated as non-matching — structured-pattern circuits are the next step.)

## [5.0.0] — 2026-05-26 — The thesis, realized: real branching Glass source → a zero-knowledge proof
*A milestone release (not a breaking change). The founding bet — write a Glass function, get a zero-knowledge proof of its result — is now real end to end: real multi-function Glass source with control flow, parsed by Glass's own front end, lowered to a circuit, and proven succinct + zero-knowledge. Alongside, this session built a complete from-scratch zk-STARK on the production Goldilocks field (v4.95–v4.98). Glass remains a research language (see LANG.md), not production-hardened.*

- **`prove_source_zk` now proves real branching Glass source.** [`prove_source_zk.glass`](examples/prove/prove_source_zk.glass) extends the unified source→ZK bridge from arithmetic to a real control-flow subset: `==`/`!=`, `&&`/`||`/`not`, and `if`. The `==` is an is-zero gadget (`out = 1 − d·inv`, with `d·out == 0` forcing `out = [d==0]`); `if` is a multiplexer (`out = f + c·(t−f)`, condition constrained boolean). Both need an inverse *hint* that can't be a gate output — so a pre-pass (`heval`) evaluates the program to compute the hints and lays them on input wires in the exact order `cgen` consumes them. Demo: `fn classify(x) = if x == 7 then 100 else x * x` over a *private* input proves "I know an input with `classify(input) = 100`" — honest ACCEPT, lying REJECT, two blinding seeds give different openings (ZK). Self-hosted byte-identical. (Order comparisons `<`/`>` would add a heavy range gadget and stay in the RLC bridge for now.)

## [4.99.0] — 2026-05-26 — Real Glass source → a succinct, zero-knowledge proof (unified)
- **The thesis, end to end in one file.** [`prove_source_zk.glass`](examples/prove/prove_source_zk.glass) joins the two halves that lived apart: the real-source front end (prism parses an actual multi-function Glass program) and the succinct, zero-knowledge backend (the blinded F_{p⁴} FRI STARK). A program `fn sq … fn cube … fn f … f(inp)` is parsed by Glass's own front end, lowered to a circuit (function calls inlined, arithmetic → add/mul/sub gates) with a `qassert` gate binding the output wire to a public claim `R`, then proven with the blinded FRI STARK. With a *private* input, it proves "I know an input with `f(input) = R`" (R = 25): honest ACCEPT, lying about R REJECTs, two blinding seeds verify with different openings (zero-knowledge). Self-hosted byte-identical. Scope: arithmetic + `let` + calls — the hint-free subset that lowers directly to trace rows (`==`/`if` need an inverse-hint input wire, the RLC bridge's domain).

## [4.98.0] — 2026-05-26 — Zero-knowledge over Goldilocks (the arc complete)
- **The full zk-STARK shape, now on the production field.** [`frost_goldilocks_zk.glass`](examples/frost/frost_goldilocks_zk.glass) adds the last property — zero-knowledge — to the Goldilocks FRI via blinding: the codeword is masked with a random low-degree polynomial R (degree below the fold-to-constant bound), so f + R still folds to a constant and the proof ACCEPTs, while the committed Merkle root and every opened value are randomized. Two independent blinding seeds produce two different valid proofs of the same statement (both ACCEPT; layer-0 commitment differs; opened value #5 differs) — the verifier learns only "low-degree", nothing about the codeword. **Sound + committed + zero-knowledge, over Goldilocks**, int64-safe and dogfooded. This completes the Goldilocks arc: field → FRI fold → F_{p²} challenge → committed/query-verified → zero-knowledge.

## [4.97.0] — 2026-05-25 — A committed, query-verified FRI over Goldilocks
- **The cryptographic STARK core, complete on the production field.** [`frost_goldilocks_stark.glass`](examples/frost/frost_goldilocks_stark.glass) brings all three FRI soundness mechanisms together over Goldilocks: each layer's codeword is **Merkle-committed** (a Goldilocks MiMC hash with the x⁷ S-box), the fold **challenge β ∈ F_{p²}** is derived from the root (Fiat-Shamir), and the verifier **samples query positions** from the transcript, opens each `(f(x), f(−x))` pair with a Merkle path, recomputes the fold, and checks it equals the next layer. An honest low-degree codeword ACCEPTs (0/12 faults); a faked final layer REJECTs (12/12 — caught at every query). All int64-safe, dogfooded byte-identical — the Baby Bear `frost_crypto` capstone, now on the field real provers use. (Next: blinding → a full zero-knowledge STARK over Goldilocks.)

## [4.96.0] — 2026-05-25 — F_{p²} over Goldilocks: a cryptographic challenge space
- **FRI over Goldilocks gains cryptographic soundness.** [`frost_goldilocks_ext.glass`](examples/frost/frost_goldilocks_ext.glass) builds the degree-2 extension F_{p²} = F_p[X]/(X² − 7) over Goldilocks (W = 7 is a non-residue, 7^((p−1)/2) = −1). Since p ≈ 2⁶⁴, F_{p²} ≈ 2¹²⁸ — a challenge space too large to guess. Inversion stays int64-safe via the norm (a⁻¹ = conj(a)·N(a)⁻¹, N(a) ∈ F_p inverted by the base Fermat inverse). FRI now folds with β ∈ F_{p²} (≈2¹²⁸ per-round soundness instead of a guessable 2⁶⁴): a low-degree codeword folds to a constant, a tampered one doesn't. All int64-safe, dogfooded byte-identical. (Mirrors the Baby Bear arc frost_fri → frost_fri_ext; next is Merkle + Fiat-Shamir over Goldilocks.)

## [4.95.0] — 2026-05-25 — FRI over Goldilocks
- **The STARK's core engine now runs over the real field.** [`frost_goldilocks_fri.glass`](examples/frost/frost_goldilocks_fri.glass) runs the FRI low-degree test over Goldilocks (p = 2⁶⁴ − 2³² + 1): the evaluation domain is a genuine 2ᵏ-th-root-of-unity subgroup (built from the field's 2-adicity), the fold `(f(x)+f(−x))/2 + β·(f(x)−f(−x))/(2x)` uses the limb-walked inverse, and a low-degree codeword folds to a constant while a tampered one does not. Every step is int64-safe, so it dogfoods byte-identical — FRI over a production-grade field, not toy Baby Bear. (Base-field β for now; the degree-2 extension challenge space and Merkle/Fiat-Shamir are the next layers, mirroring how the Baby Bear path grew.)

## [4.94.0] — 2026-05-25 — A hash preimage in zero-knowledge, and the Goldilocks field
- **The canonical ZK statement — knowledge of a hash preimage.** [`prove_preimage_zk.glass`](examples/prove/prove_preimage_zk.glass) proves *"I know a secret x such that Hash(x) = H"* in zero-knowledge. `Hash` is a 2-to-1 compression built from Poseidon's own heart — the x⁷ S-box, round constants, and the MDS mix `[[2,3,1],[1,2,3],[3,1,2]]` — lowered gate-for-gate into a Frost circuit, with the secret preimage on private input wires and a `qassert` forcing the truncated permutation output to the public digest. Proven by the blinded F_{p⁴} FRI STARK: honest ACCEPT, wrong preimage REJECT, two blinding seeds give different openings. Rounds are reduced so the trace dogfoods on the interpreter; the full 30-round Poseidon runs the same way (~1.2s native).
- **The Goldilocks field, from scratch, int64-safe.** [`frost_goldilocks.glass`](examples/frost/frost_goldilocks.glass) builds p = 2⁶⁴ − 2³² + 1 — the field Plonky2/RISC Zero run on — with its signature division-free reduction (2⁶⁴ ≡ 2³² − 1), a real Fermat inverse (p − 2 overflows int64, so the exponent is walked in base-2¹⁶ limbs too), and the 2³²-th root of unity (32 NTT layers). Every step stays inside int64, so it dogfoods byte-identical — the int64 wall is genuinely lifted, not hidden by Python's big ints.

## [4.93.0] — 2026-05-25 — A FRI fold step, verified in zero-knowledge
- **H3 advances: the recursion step is now succinct and blind.** [`prove_recursion_zk.glass`](examples/prove/prove_recursion_zk.glass) takes the FRI fold check — `fold(f(x), f(-x)) = (f(x)+f(-x))/2 + β·(f(x)−f(-x))/(2x)` — and lowers it through the blinded F_{p⁴} FRI STARK (the `prove_zk` backend), so the verifier's own fold step is proven in zero-knowledge: the opened values stay private. Division rides as input-wire inverse hints with `(2x)·inv == 1` `qassert` gates. Honest fold step ACCEPTs, a tampered fold REJECTs, and two blinding seeds verify with different quotient openings. Self-hosted byte-identical; ~1.1s native vs ~46s interpreted (~42×) — the native-substrate payoff on a genuinely heavy circuit.

## [4.92.0] — 2026-05-25 — Top-level functions self-host as values
- A bare top-level function used as a first-class value (`map(xs, inc)`) now self-hosts: `glassc` gains an eta-expansion pre-pass that rewrites it to an arity-saturated lambda (`fn(a) -> inc(a)`) before codegen, which compiles to a proper closure. Call heads and shadowing locals are untouched, so the pass is a no-op on code that doesn't use a bare fn as a value — the bootstrap fixpoint still closes byte-identically (972 lines of C, gen1 == gen2); suite 381/381.
- **This closes the last self-hosting divergence.** The reference interpreter and the self-hosted compiler now agree on the entire practical language — the culmination of the parser-parity audit (v4.89–v4.92).

## [4.91.0] — 2026-05-25 — Record patterns self-host
- Record patterns in `match` (`Point { x, y } => …`) now parse in `prism` and compile through `glassc` — they previously ran on the reference interpreter and Quartz but not the self-hosted native compiler. With this, the parser-parity audit has closed **every practical divergence**: the reference, Quartz, and the self-hosted compiler now agree on the whole language. Bootstrap fixpoint byte-identical (972 lines of C, gen1 == gen2); suite 381/381.

## [4.90.0] — 2026-05-25 — The prelude self-hosts
- The entire standard prelude now compiles through the **self-hosted** compiler, not just the reference: `fst`, `snd`, `reverse`, `map_option`, `bind_option`, and `map_result` join `bind_result`/`string_contains` — all emitted by `glassc` (Pair field access, a `q_reverse` list walker, and closure-applying Option/Result mappers built on `q_apply1`). Every prelude function now runs identically on the interpreter, Quartz, and the self-hosted compiler. Bootstrap fixpoint byte-identical (963 lines of C, gen1 == gen2); suite 381/381.

## [4.89.0] — 2026-05-25 — Parser parity: reference ⟷ self-hosted front end
- A parser-parity audit aligned the reference interpreter (`glass.py`) with the self-hosted front end (`prism`), so a program that runs on `glass` is one that self-hosts:
  - **chained comparison** (`a == b == c`) is now a parse error in the reference too — comparison operators don't associate; write `(a == b) == c`.
  - **negative integer literals** (`-5`) now lex in prism, matching the reference's `-?\d+` — examples that used them (`quartz/lookup`, `basic/option_result`) now self-host.
  - **fixed-length list patterns** (`[a, b]`) now parse in the reference, matching prism, alongside the `[x, ...rest]` cons form.
- Documented the two remaining self-hosting gaps honestly in [`docs/self-hosting.md`](docs/self-hosting.md): record patterns in `match` (interpreter + Quartz, not prism) and a bare top-level function used as a value (interpreter only — wrap it in a lambda). Bootstrap fixpoint re-verified byte-identical; suite 381/381.

## [4.88.0] — 2026-05-25 — Poseidon: a permutation-based hash
- Frost gains **Poseidon**, the hash production STARKs actually use, built from scratch: an `x⁷` S-box (a real *permutation* on Baby Bear — MiMC's `x⁵` is not, since 5 ∣ p−1), full + partial rounds, and an MDS mixing layer. It even proves the S-box is a bijection — `(x⁷)^d == x` for `d = 7⁻¹ mod (p−1)` — and powers a Poseidon Merkle root. A genuine upgrade over the toy MiMC. (`examples/frost/frost_poseidon.glass`)
- Frost's README gains a **"Sharper primitives"** section gathering the drop-in upgrades: Poseidon, the recursive O(n log n) NTT, and the 128-bit bignum field.

## [4.87.0] — 2026-05-25 — A faster reference interpreter
- The reference interpreter (`glass.py`) runs the heavy STARK demos **~24% faster** — `dataclass(slots=True)` on the runtime value classes (Python 3.10+, graceful on 3.9), plus inlining the leaf-operand cases (`Ident` / `IntLit` / `BinOp`) in the binop, function-call, and tail-call paths to skip millions of `eval_expr` dispatch calls. Output is byte-identical: suite 381/381, dogfoods unchanged, Python 3.9 ≡ 3.12.
- **MIN/MAX now support `WHERE`**, so every aggregate (SUM, COUNT, AVG, MIN, MAX, GROUP BY) filters uniformly — each proven over the same committed table. (`examples/prove/prove_pane.glass`)

## [4.86.0] — 2026-05-25 — The complete aggregate set
- Pane's query algebra (and its Frost proof backend) now covers the full analytics surface over a committed private table: **SUM, COUNT, AVG, MIN, MAX, and GROUP BY**, on top of equality / boolean / arithmetic / `<`–`>` range filters. (`examples/pane/pane.glass`, `examples/prove/prove_pane.glass`)
- **AVG** is revealed as a proven `sum` + `count` (a finite field has no exact division, so the verifier forms the average); **MIN/MAX** claim a value and prove it is both a *bound* (via the range gadget) and *present* (via an inverse hint); **GROUP BY** decomposes into per-group filtered sums — each proven over the *same* committed table.
- `run_query` and the prover stay in lockstep: the circuit ACCEPTs exactly when its answer equals the reference interpreter's.

## [4.85.0] — 2026-05-25 — Pane ⊕ Frost: zero-knowledge queries
- The founding vision, realized: commit a **private table**, then prove the result of a query — revealing only the commitment, the query, and the answer, never a row. (`examples/prove/prove_query`)
- **Frost as a second backend over the real Pane query algebra**: a genuine Pane `Query` value (`SumQ`/`CountQ`/`Where`) is *lowered* into a Frost circuit — equality, booleans, arithmetic, and `<`/`>` range comparisons — with one AST and two evaluators (`run_query` interprets, `prove_pane` proves) kept honest by their agreement. (`examples/prove/prove_pane`)
- **A committed-table query in zero-knowledge**: a SUM, and a `WHERE`-filtered SUM, over a committed private column — lowered to the blinded F_{p⁴} FRI STARK, succinct and leaking nothing. The PLONK gate identity gains a `qassert` selector so the binding/result assertions and the filter's is-zero gadget ride inside the low-degree quotient. (`examples/prove/prove_query_zk`)
- The reference interpreter now **rejects uppercase value bindings** — an uppercase name is a constructor, and binding one as a value silently miscompiled — closing a glass.py ⟷ compiler divergence.

## [4.84.0] — 2026-05-25 — A 128-bit bignum field, a hardened runtime, and a written semantics
- A **production-width field**: a 128-bit prime (2¹²⁸ − 159) built from base-2¹⁶ bignum limbs — arithmetic that overflows a single int64 now works limb-by-limb, and self-hosts byte-for-byte. (`examples/frost/frost_field`)
- **Hardened the native runtime**: the emitted `run_command` uses process-unique temp files with cleanup (no more fixed-`/tmp` clobber); the bootstrap fixpoint still closes byte-identically.
- **Tooling**: `dogfood.sh` runs the self-host differential check in one command, and `docs/semantics.md` writes down Glass's big-step operational semantics.

## [4.83.0] — 2026-05-25 — Structured match, a unified bridge, and self-host tooling
- The prove bridge compiles structured **`match` on ADTs** — a value becomes a `(tag, fields…)` wire-tuple, dispatched by tag and bound by field. (`examples/prove/prove_adt`)
- A **unified front end** proves real multi-function Glass programs — function calls, `match`, `if`, `==`, and arithmetic all interacting. (`examples/prove/prove_full`)
- **`dogfood.sh`** runs any file on both `glass.py` and the self-hosted compiler and checks byte-identical output — the differential-testing discipline as one command; plus a `glass --quiet` flag that suppresses declaration echoes. (`examples/selfhost/dogfood.sh`)

## [4.82.0] — 2026-05-25 — The prove bridge closes the loop: Glass source → a succinct, zero-knowledge proof
- Write a Glass function, get a STARK proof of its execution that is sound, succinct, *and* zero-knowledge — the circuit is lowered through a PLONK arithmetization, copy constraints (a z-accumulator permutation), a gate-constraint quotient, and a blinded FRI over F_{p⁴}. (`examples/prove/prove_stark`, `prove_copy`, `prove_quotient`, `prove_zk`, `prove_zperm`)
- The bridge now also handles **function calls** (by inlining) and **`match`** (scalar dispatch), over real prism-parsed Glass. (`prove_calls`, `prove_match`)
- Developer experience: a standard **prelude** (`examples/lib/prelude.glass` — `nth`, `take`/`drop`, `zip`, Option/Result helpers), a `glass --version` flag, and parser/type diagnostics that *explain* the common gotchas (uppercase = constructor, tuple-vs-`Pair`).
- Performance: a recursive **O(n log n) NTT** replaces the O(n²) transform under evaluate/interpolate/FRI. (`frost_ntt`)

## [4.81.0] — 2026-05-24 — Docs & repo: a cinematic pass
- README rewritten around the macro idea — transparency, carried from a type signature to a zero-knowledge proof.
- Examples reorganized so the repo reads itself: Frost split into its own folder, per-folder guides, a navigation index.
- Changelog condensed from ~11k lines to a couple of bullets per version.

## [4.80.0] — 2026-05-24 — The prove bridge: write Glass, get a proof
- A Glass expression compiles to a Frost circuit + witness and is proved correct for a secret input.
- `prove_glass` parses REAL Glass source with Glass's own front end (prism) and proves it — arithmetic, comparisons, booleans, `if`/`let`.

## [4.79.0] — 2026-05-24 — Frost goes cryptographic, and zero-knowledge
- An extension field F_{p⁴} (~2¹²⁴) built in int64; FRI fold challenges and a permutation argument drawn from it.
- Amplified Fiat-Shamir query sampling and trace blinding — cryptographic soundness and the actual zero-knowledge property.
- The capstone: one end-to-end zk-STARK proving a computation that is sound, succinct, *and* zero-knowledge.

## [4.78.0] — 2026-05-24 — Frost: a zk-STARK from scratch
- Own finite field, MiMC hash, Merkle trees, and arithmetic-circuit arithmetization.
- Polynomial interpolation, the FRI low-degree test, and an AIR that proves a computation via a low-degree quotient.

## [4.77.0] — 2026-05-24 — Pane: a query language in Glass
- A small, total, deterministic query algebra + reference interpreter, shaped so the same AST can be lowered into a zero-knowledge circuit (Frost).

## [4.76.0] — 2026-05-24 — Self-hosting: the bootstrap fixpoint closes
- Glass self-hosts.

## [4.75.0] — 2026-05-24 — Glass compiles Glass: native_glassc compiles prism.glass identically
- The self-hosting payoff.

## [4.74.0] — 2026-05-24 — A native Glass compiler (Phase B/C: glassc.glass)
- Glass now compiles Glass, natively.

## [4.73.0] — 2026-05-24 — Quartz Phase A4: prism.glass RUNS identically (keystone milestone)
- The asterisk is gone.

## [4.72.0] — 2026-05-24 — Quartz Phase A4: prism.glass compiles and links
- The keystone compile milestone — with an honest asterisk.

## [4.71.0] — 2026-05-24 — Quartz Phase A1/A2: effects compile, prism is now the target
- First release of the off-Python migration

## [4.70.0] — 2026-05-24 — A module system: `import`, and the end of copy-pasted cores
- The most practical feature on the table, and one I kept hitting.

## [4.69.0] — 2026-05-24 — Field-level refinements: data that carries its own invariant
- The gap units.glass hit, closed.

## [4.68.0] — 2026-05-24 — Linear types in prism: Glass self-hosts its own substructural check
- Parity, and a self-hosting milestone.

## [4.67.0] — 2026-05-24 — Linear / resource types: the first feature the type checker had to grow for
- The phase change.

## [4.66.0] — 2026-05-24 — Physical types: dimensional analysis and conservation laws
- My additions to the backlog, and the last showcase-style bundle.

## [4.65.0] — 2026-05-24 — Information & Observation: who's looking, how deep, and what leaks
- Second Tier-2 bundle.

## [4.64.0] — 2026-05-24 — Time & Causality: partial-order time, intervention, identity-over-time
- First Tier-2 bundle (now unblocked).

## [4.63.0] — 2026-05-24 — Rationals & Probability: the no-floats decision, made well
- The architectural fork I'd been flagging, resolved.

## [4.62.0] — 2026-05-24 — Strategy & Worlds: the Dilemma's tragedy and many-worlds nondeterminism
- Last unblocked Tier-1 bundle.

## [4.61.0] — 2026-05-24 — Quantum II: entanglement and the interference that isn't classical
- Fourth bundle, and the deepest physics so far.

## [4.60.0] — 2026-05-24 — Epistemic-games & Symmetry: groups as data, knowledge as worlds
- Third bundle from the buildable cluster.

## [4.59.0] — 2026-05-24 — Self-Similarity & Spirals: the same shape, all the way down
- Second bundle from the buildable cluster.

## [4.58.0] — 2026-05-24 — Proportion & Form: refinements that encode mathematical truths
- First bundle from the "exotic types" backlog.

## [4.57.0] — 2026-05-24 — Quantum-inspired measurement: the first of the "exotic types" backlog
- A new direction begins.

## [4.56.0] — 2026-05-24 — Cross-parameter refinements: a later param's predicate can reference an earlier one
- Closing the v4.55 carve-out.

## [4.55.0] — 2026-05-24 — Quartz refinement predicates: recursive compiler replaces the shape-matcher
- Retiring the growing match cascade.

## [4.54.0] — 2026-05-24 — Logical NOT `!` — the boolean operator trio is complete
- Closing the boolean operator set.

## [4.53.0] — 2026-05-24 — Modulo `%` lands — parity / divisibility refinements compile
- Glass couldn't lex %.

## [4.52.0] — 2026-05-23 — `&&` and `||` in prism — host/prism parity restored
- Closing v4.51's deferred work.

## [4.51.0] — 2026-05-23 — `&&` and `||` land — range refinements compile through Quartz
- A long-standing language gap closes.

## [4.50.0] — 2026-05-23 — Quartz refinement coverage: let-bindings + lambda params
- v4.49 follow-on, scoped exactly to the two carve-outs that release named.

## [4.49.0] — 2026-05-23 — Refinements reach Quartz: param + return runtime checks in compiled C
- Refinement-type story finally crosses the native boundary.

## [4.48.0] — 2026-05-23 — Multi-param lambdas in prism close the host parity gap
- Follow-on to v4.47.

## [4.47.0] — 2026-05-23 — Refined-param lambdas: predicates fire on every apply
- Fourth and final step of the staged lambdas plan.

## [4.46.0] — 2026-05-23 — Quartz multi-arg lambdas + map / filter / fold
- Third step of the lambdas arc. Map/filter/fold compile end-to-end.

## [4.45.0] — 2026-05-23 — Quartz capturing closures: free-variable analysis + capture marshalling
- Second step of the lambdas arc.

## [4.44.0] — 2026-05-23 — Quartz lambdas (first cut): non-capturing closures compile to native
- The biggest open Quartz item starts landing.

## [4.43.0] — 2026-05-23 — Carry-forward bundle: range builtin, wrap_int64, cast-bridge factored
- Three small open carry-forward items, closed together.

## [4.42.0] — 2026-05-23 — Bitwise ops batch lands in host + Quartz
- Six builtins, identical semantics through host and Quartz.

## [4.41.0] — 2026-05-23 — char_at resolves: codepoint semantics in host + Quartz, prism's String version preserved as internal
- The longest-standing item from the carry-forward list closes.

## [4.40.0] — 2026-05-23 — string_to_upper / string_to_lower land in BOTH host and Quartz
- The first v4.x release that adds to the host's builtin surface.

## [4.39.0] — 2026-05-23 — Quartz builtins batch 2: len, head, tail, reverse, string_index_of
- Five more host-prelude builtins land.

## [4.38.0] — 2026-05-23 — Quartz gains three string builtins: string_length, substring, int_to_string
- New arc begins.

## [4.37.0] — 2026-05-23 — Quartz structural `==` complete: generic sum types (Option, Result, user-declared)
- The structural-eq arc closes.

## [4.36.0] — 2026-05-23 — Quartz structural `==` capstone: records and concrete sum types
- The structural-eq arc closes for every type Quartz can construct except generic sum types.

## [4.35.0] — 2026-05-23 — Quartz structural `==` recurses through nested List and Tuple
- The smallest release in the structural-eq arc.

## [4.34.0] — 2026-05-23 — Quartz structural `==` extends to primitive-element List and Tuple
- Building on v4.33's loud-error scaffolding.

## [4.33.0] — 2026-05-23 — Quartz `==` sweep: Strings get content-eq, boxed types fail loudly
- The silent-miscompilation sweep flagged in v4.32 — closed for ==.

## [4.32.0] — 2026-05-23 — Quartz `++` becomes type-polymorphic — list-concat lands
- A silent-miscompilation bug closed.

## [4.31.0] — 2026-05-23 — Quartz lists: cons-chain in q_value_t
- Second step in the resumed Quartz arc.

## [4.30.0] — 2026-05-23 — Quartz arc resumed: tuples compile to native
- The Quartz arc was last touched at v4.20.

## [4.29.0] — 2026-05-23 — Honest perf release: ChainMap experiment failed, findings recorded
- A release whose headline deliverable is a calibrated finding, not a feature.

## [4.28.0] — 2026-05-23 — Tail-call elimination in the host — unbounded tail recursion
- Switched arcs from prism-parity to host performance.

## [4.27.0] — 2026-05-23 — Parens-after-let parser fix ports to prism
- v4.21's host fix, finally mirrored in prism.

## [4.26.0] — 2026-05-23 — Division `/` lands in prism — textbook safe_div finally runs
- The canonical refinement-types demo, end-to-end in prism.

## [4.25.0] — 2026-05-23 — Return-type refinement runtime checks land in prism
- v4.24's queued item, closed.

## [4.24.0] — 2026-05-23 — Refinement runtime checks reach all curried params via VRefinedClos
- v4.23's deferred item, closed.

## [4.23.0] — 2026-05-23 — Refinement runtime checks land in prism (first-param top-level fns)
- The refinement story in prism gets its missing chunk.

## [4.22.0] — 2026-05-23 — Quartz monomorphization fix — generic fns over ADTs round-trip cleanly
- The 2 baseline-failing Quartz tests, flagged honestly in v4.21, now pass.

## [4.21.0] — 2026-05-23 — Parens-after-let parser fix + drift catch on misdiagnosed AGENT.md §5
- One real parser bug closed. One mis-documented language gotcha retired.

## [3.17.0] — 2026-05-22 — Parser extends: ADTs + match
- Glass-side parser handles algebraic data types and pattern matching.

## [4.20.0] — 2026-05-22 — calc with parens + djb2 hash (zero compiler changes, pure proof points)
- Two real algorithms in compiled Glass, no compiler changes.

## [4.19.0] — 2026-05-22 — typed parameters + parameter-type-aware return inference (chronic foot-gun gone)
- The recurring foot-gun across v4.12, v4.13 is fixed.

## [4.18.0] — 2026-05-22 — division `/` + calculator demo (a real interpreter in compiled Glass)
- The strongest end-to-end proof point yet.

## [4.17.0] — 2026-05-22 — hex literals (`0xFF`, `0xcafe`)
- Hex literals close the readability gap from v4.16.

## [4.16.0] — 2026-05-22 — bitwise builtins (direction #2 advances)
- Direction #1 was symbolic strings. Direction #2 is numeric — v4.16 lands its first installment.

## [4.15.0] — 2026-05-22 — `string_index_of` (symbolic-string vocabulary complete)
- Search closes the symbolic-string toolkit.

## [4.14.0] — 2026-05-22 — `substring` + `string_at` (palindrome checker compiles)
- The slicing toolkit completes the symbolic-string vocabulary.

## [4.13.0] — 2026-05-22 — `string_length`, `string_to_upper`, `string_to_lower` (focused stdlib for symbolic strings)
- Three idiomatic string builtins.

## [4.12.0] — 2026-05-22 — `>=`, `<=` + `int_to_char` (Caesar cipher compiles)
- Caesar cipher in pure Glass, compiled to native.

## [4.11.0] — 2026-05-22 — `char_at` builtin (symbolic string processing foundation)
- Compiled Glass programs can now inspect strings character-by-character.

## [4.9.0] — 2026-05-22 — Two foot-guns closed: string semantic equality + identifier mangling
- Both lurking quirks fixed in one release.

## [4.8.0] — 2026-05-22 — Inequality (`!=`) + block comments (`/* ... */`)
- Two surgical small wins.

## [4.7.0] — 2026-05-22 — Equality + logical operators (primality test compiles)
- ==, &&, || work end-to-end.

## [4.6.0] — 2026-05-22 — Unary minus + modulo (Euclidean GCD compiles)
- Two small operator additions unlock real number-theory programs.

## [4.5.0] — 2026-05-22 — Line comments + honest performance roadmap
- Source files can now have # comments.

## [4.4.0] — 2026-05-22 — Direct file read in selfcompile + newlines as whitespace
- Real .glass files on disk now self-compile.

## [4.3.0] — 2026-05-22 — Nested PCtor sub-patterns + nullary ctor fix
- Patterns can now descend into nested ADT structure.

## [4.2.0] — 2026-05-22 — Fn-chain return-type inference via fixed-point
- Chains of string-returning fns now propagate correctly.

## [4.1.0] — 2026-05-22 — String escape sequences in parser
- Parser handles \n, \", \\ escapes.

## [4.0.0] — 2026-05-22 — Stage 5 endpoint — `selfcompile.glass` drives full self-compile pipeline
- Glass compiles Glass via Glass-side scripts, end to end.

## [3.20.0] — 2026-05-22 — Parser reaches feature parity — generics + multi-type fields + fn return-type tracking
- The Glass-side parser now handles every AST shape quartz_min handles.

## [3.19.0] — 2026-05-22 — Parser extends: string literals + concatenation
- Glass-side parser handles strings.

## [3.18.0] — 2026-05-22 — Parser extends: records + field access
- Glass-side parser handles records.

## [3.17.0] — 2026-05-21 — Parser extends: ADTs + match
- Glass-side parser handles algebraic data types and pattern matching.

## [3.16.0] — 2026-05-21 — Parser extends: fn decls, ECall, if/else, comparison
- Recursive factorial parses end-to-end through Glass.

## [3.15.0] — 2026-05-21 — Parser extends: identifiers + let bindings
- Glass-side parser handles let.

## [3.14.0] — 2026-05-21 — Source to native, all in Glass — `quartz_parser.glass`
- Glass parses Glass source.

## [3.13.0] — 2026-05-21 — Glass drives cc — `write_file`, `run_command`, end-to-end build pipeline
- Glass can now compile and run native binaries from inside Glass.

## [3.12.0] — 2026-05-21 — Quartz-in-Glass: multi-type fields + generics (via boundary discipline)
- Two big roadmap items close with one small codegen fix.

## [3.11.0] — 2026-05-21 — Quartz-in-Glass: strings (EStr, EConcat, String results)
- Quartz-in-Glass handles strings.

## [3.9.0] — 2026-05-21 — Quartz-in-Glass: records + field access
- Quartz-in-Glass handles records.

## [3.8.0] — 2026-05-21 — Quartz-in-Glass: ADTs + pattern matching
- Quartz-in-Glass handles algebraic data types.

## [3.7.0] — 2026-05-21 — Quartz-in-Glass: identifiers, let, fn calls
- Quartz-in-Glass grows.

## [3.6.0] — 2026-05-21 — Quartz, written in Glass (first piece)
- The Stage 5 piece arrives.

## [3.5.0] — 2026-05-21 — Quartz: generic functions
- Generic functions compile to native C.

## [3.4.0] — 2026-05-21 — Quartz: generic ADTs and generic records
- Generic types compile to native C.

## [3.3.0] — 2026-05-21 — Quartz: records
- Records compile to native C.

## [3.2.0] — 2026-05-21 — Quartz: ADTs + pattern matching
- Sum types compile to native C.

## [3.1.0] — 2026-05-21 — Quartz: functions
- Top-level functions compile to native C.

## [3.0.0] — 2026-05-21 — Quartz (first prototype)
- Quartz arrives.

## [2.16.0] — 2026-05-21
- Quartz design document.

## [2.15.0] — 2026-05-21
- Stage 4.5 — the self-host milestone.

## [2.14.0] — 2026-05-21
- Refinements port chunk 3: implication discharge in prism.

## [2.13.0] — 2026-05-21
- Refinements port chunk 2a: alpha-equivalence discharge in prism.

## [2.12.0] — 2026-05-21
- Refinement types port to prism — chunk 1: parsing + constant-fold discharge.

## [2.11.0] — 2026-05-21 — *v2.10 skipped per version contract*
- Parameterized record literal type inference in prism — the second gap from v2.9's Stage 4.5 attempt closed.

## [2.9.0] — 2026-05-21
- Generic fn declarations in prism, surfaced by a Stage 4.5 attempt.

## [2.8.0] — 2026-05-21
- Markdown-to-HTML converter library in Glass.

## [2.7.0] — 2026-05-21
- Plain let with patterns.

## [2.6.0] — 2026-05-21
- Config-file parser library in Glass — let* and let? paying off in real code.

## [2.5.0] — 2026-05-21
- let? syntactic sugar for Option threading.

## [2.4.0] — 2026-05-21
- let* syntactic sugar for Result threading.

## [2.3.1] — 2026-05-21
- Patch release.

## [2.3.0] — 2026-05-21
- AGENT.md.

## [2.2.0] — 2026-05-21
- A real Glass library: JSON parser.

## [2.1.0] — 2026-05-21
- Browser playground.

## [2.0.0] — 2026-05-21
- Maturity release.

## [1.9.0] — 2026-05-21
- Real interactive REPL.

## [1.8.0] — 2026-05-21
- Pair and Result pre-declared in prism.glass.

## [1.8.0] — 2026-05-21
- Scaling up Stage 4: midlang.glass — a Glass-in-Glass interpreter with closures, lambdas, let-bindings, and recursion.

## [1.7.0] — 2026-05-21
- Interpreter performance pass.

## [1.6.0] — 2026-05-21
- Reflexive feature coverage expansion.

## [1.5.0] — 2026-05-21
- Meta-circular evaluation.

## [1.4.0] — 2026-05-21
- Implication-based subsumption and dual licensing.

## [1.3.0] — 2026-05-21
- Refinement composition.

## [1.2.0] — 2026-05-21
- Static refinement discharge.

## [1.1.0] — 2026-05-21
- Showcase release.

## [1.0.0] — 2026-05-21
- Stage 3 self-host achieved.

## [0.9.7] — internal release
- - Function types (A) -> B in parse_type (split into parse_type and parse_type_atom, with optional effect on the arrow).

## [0.9.6] — internal release
- - print builtin with !{IO} effect.

## [0.9.5]
- - Top-level fn declarations with mutual recursion via VMutRecClos(name, body_expr, all_decls, outer_env).

## [0.9.4]
- - First-class String type (TyStr, VStr, EStr).

## [0.9.0 – 0.9.3] — internal releases
- Records with named fields, generic ADTs (TyAdt with type params), pattern matching with exhaustiveness checking, recursion via let rec, subtraction/multiplication/comparisons, tuples, list literals [...] with spread [h, ...t].

## [0.0 – 0.8] — early development
- Initial language design: pure functional core, Hindley-Milner type inference, ADTs, pattern matching, immutability, effect rows.
