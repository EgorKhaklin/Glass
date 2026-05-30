# Audit-readiness package — Glass Goldilocks zk-STARK

> **This package makes the construction AUDITABLE. It does NOT claim
> production-readiness.** The construction is **research/educational-grade**, merged
> to `main` in **v5.48.0**; the default `glass prove` (Goldilocks, no flags) **now runs
> `verify_b3`** — the sound path is the one users invoke (`--fast` opts into the old
> witness self-check, `--zk` adds hiding). Wiring the default to `verify_b3` does **not**
> change the audit boundary. **Do not protect real value.** Produced + adversarially
> completeness-checked this session (workflow `wa4qip7ht`), every load-bearing claim
> verified against `examples/prove/prove_source_goldilocks_zk.glass`.

## The hard boundary (production requires this; in-repo cannot provide it)

**Production grade requires an external professional audit + community cryptanalysis.**
Three facts gate any production claim and are never crossable in-repo:

1. **Poseidon-as-random-oracle is an unproven idealization.** Every Merkle node and
   every Fiat-Shamir challenge is a Poseidon output modeled as an RO. The in-repo
   Poseidon is unaudited/un-cryptanalyzed (matching Plonky2's 4 test vectors is a
   consistency check, **not** an audit). **If Poseidon has exploitable structure the
   entire bound is *vacuous*** — soundness *and* the designed ZK collapse together.
2. **The ~2⁻¹³⁵ list-decoding figure is conjectural** (FRI proximity-gap to capacity).
   Only the unique-decoding figure is conjecture-free.
3. **All reductions are pen-and-paper, not machine-checked.**

## The #1 finding (a live overclaim) — caught, then FIXED

The adversarial completeness pass caught a **live overclaim**: the FRI-query soundness
is ~80-bit provable, but `hashg` originally returned **one ~64-bit Goldilocks lane**, so
each Merkle node and transcript seed had only **~2⁻³² birthday collision-resistance** —
the commitment binding *capped the whole proof at ~32-bit*, not ~80.

- **FIXED:** `hashg` now outputs **4 Poseidon lanes** (~256-bit ⇒ ~2⁻¹²⁸ binding;
  `to_lanes`/`from4`/`lane0`), so the commitment binding (~128-bit) no longer gates the
  ~80-bit FRI term. Validated native (all ACCEPT/REJECT gates hold with the wide hash).
- **Honest headline now: ~80-bit provable** (FRI-query-limited), no longer hash-capped.
- **#2 also FIXED:** queries are now sampled **without replacement** (`sample_distinct`
  re-draws on a collision → 82 *distinct* positions), so the full 82-query FRI bound holds
  with no duplicate erosion. Validated native. (The razor-thin 68+12=80 margin still has
  zero slack — an auditor must re-derive it independently.)
- **Audit must still** independently verify the 4-lane sponge/compression actually gives
  ~128-bit collision-resistance, and that the ~32-bit fix is complete across every
  Merkle + FS path.

*(This is the no-overclaim discipline working end to end: an adversarial pass written
specifically to stress the claims for an auditor found the gap; it was corrected, the
hash widened, and re-validated — all in-session.)*

## Which artifact is under audit (pin this first)

Audit **`verify_b3`** (82 queries / 32N coset / ρ=1/8 / 12-bit grind / independent
witness-free verifier / B3 wire-consistency). As of the post-v5.48.0 production-hardening
work this **is** the default `glass prove` path (Goldilocks, no flags): `gprove_sound`
builds the claim circuit and runs `verify_b3(gs, prove_b3(gs, w))`. The other two CLI modes
are **out of the audited scope**: `--fast` is the old witness self-check (`gprove_m` /
`prove_stark` — NOT a soundness proof), and `--baby-bear` is the educational 2³¹ path.
`--zk` is `verify_b3` over a randomized trace (sound + hiding). Confirm end-to-end that the
no-flag default invokes `verify_b3` (it does) — and note its cost scales with circuit size.

## Threat model (security goals + attack surfaces)

**Goals:** soundness vs a malicious prover (an accepting proof ⇒ the committed trace is
a consistent satisfying assignment, R is genuine); HVZK / NIZK-in-ROM hiding vs an
honest/RO verifier — **implemented via randomized trace** (`build_claim_zk`: ~240 random
dummy rows ≫ the ~170 openings; validated ACCEPT at n=256). *Computational*; masks are
Poseidon-seeded (an ideal-RNG idealization), hiding is by-construction + reasoned
simulator, not machine-checked.

**Attacker models:** malicious prover; honest-but-curious verifier; the FS/ROM adversary
with a bounded RO-query budget.

**Attack surfaces (each defended + residual risk):** FRI low-degree forgery (defended by
82 queries + grind — *capped by the hash binding*); DEEP/OOD evaluation forgery (SZ over
γ in F_{p²}); the grand-product permutation (PLONK lemma over β,γ_p); FS grinding /
re-grinding (verifier-rechecked 12-bit PoW; *transcript seed only 64-bit*); **Merkle /
commitment binding (now a 4-lane ~256-bit node hash → ~128-bit; was the ~32-bit cap, FIXED)**; staged-transcript ordering
(prefix-monotone, re-derived — but the `transcript_seed_g ≡ seed_from_roots` invariant is
hand-maintained, not asserted); parameter substitution (now bound into `stmt_seed`); the
extension field (`x²−7` assumed irreducible); **the compiler/arithmetization bridge** —
`unroll`/`resolve_fn` silently lower unresolved or fuel-exhausted calls to `EInt(0)`, so a
mis-parsed/unresolved call becomes a *proven 0* with no error; side channels (limb field
not constant-time); the ZK mask RNG (Poseidon-seeded PRG, an ideal-RNG idealization).

**Explicitly out of the threat model:** compiler correctness (proves the *gate-circuit's*
out = R, not faithful lowering of the source) — including **bounded symbolic unrolling**: the
unroller inlines recursion to a fixed fuel (8) and caps deeper calls with 0, so a program
whose *runtime* recursion depth exceeds the fuel lowers to a depth-truncated circuit. On the
**honest CLI path this is now caught loudly** — `gref_m_checked` runs a short-circuiting,
fuel-locked guard (`seval`) that detects when the genuinely-taken recursion exceeds the
unroll bound and **aborts** (e.g. `glass prove fact_prove.glass inp=8` refuses instead of
proving the truncated `0`), so the honest user no longer gets a silent-wrong result + a valid
proof. **Still out of scope (faithful-lowering / malicious path):** a prover hand-building a
truncated circuit, or calling `gprove_sound`/`prove_b3` directly with a forged `R`, can still
produce a valid proof of the truncated value — the guard is a CLI check, not a circuit-level
constraint. *Unresolved / unparseable* programs also abort loudly. Also out: witness/input
semantics (private inputs = "knowledge of a witness yielding R"; *public* inputs are pinnable
via `build_claim_pub`, a wrong public value REJECTs); constant-time; the conjectures.

## Assumptions ledger

| Assumption | Tag | If it fails |
|---|---|---|
| Poseidon = random oracle (Merkle + all FS squeezes) | IDEALIZED / UNVALIDATED-IN-REPO | entire bound vacuous |
| Poseidon collision-resistance at the **256-bit (4-lane)** output (was 64-bit/~32-bit-capped, FIXED) | UNVALIDATED (≥128-bit by width) | binding broken if Poseidon CR fails |
| FS-in-ROM soundness + ZK for this 5-phase composition | IDEALIZED (framework only) | non-interactive security unproven |
| FRI unique-decoding proximity (δ<(1−ρ)/2) | PROVEN-REDUCTION | — |
| FRI decoding-to-capacity (δ<1−√ρ) | CONJECTURAL | the ~135 figure falls |
| Schwartz-Zippel over F_{p²}, \|F_{p²}\|≈2¹²⁸ | PROVEN-REDUCTION | — |
| `x²−7` irreducible / field arithmetic correct | UNVALIDATED-IN-REPO | challenge space / SZ wrong |
| OOD point z misses the coset (no explicit guard) | UNVALIDATED (leans on \|coset\|/2¹²⁸) | a pole could be hidden |
| ideal mask RNG (for the designed ZK) | IDEALIZED | ZK only computational/weaker |
| bounded RO-query budget ≪ 2¹⁰⁴ | STANDARD | RO-bookkeeping term grows |

## Audit scope (the checklist; discipline-tagged)

1. **[cryptanalysis]** Poseidon-over-Goldilocks at these exact parameters (x⁷, R_P=22, the
   MDS, the 360 round constants) — **and the single-lane 2-to-1 squeeze width.** *The
   irreducible, highest-leverage item.*
2. **[conjecture-validation]** the FRI proximity-gap / decoding-to-capacity assumption at δ<1−√ρ.
3. **[formal-methods]** a machine-checked or peer-reviewed FS-in-ROM round-by-round
   soundness **and** ZK proof for this exact 5-phase transcript.
4. **[code-review]** constant-time / side-channel review of the limb field.
5. **[code-review]** the arithmetization↔source bridge (cgen) for faithful lowering;
   the silent `EInt(0)` lowering of unresolved/fuel-exhausted calls.
6. **[code-review]** confirm the deployed verifier is the independent witness-free
   `verify_b3` path, not a self-check; and the native TCB (Boehm GC memory-safety).
7. **[design]** the public-input boundary / input-pinning semantics; the explicit
   knowledge extractor (if witness-extraction, not just existential soundness, is wanted).
8. **[re-derive]** the concrete bit budget independently — **including the hash-width
   cap (#1 finding) and the with-replacement query loss.**

## Security / responsible disclosure

**Status: educational / research-grade. Auditable, not audited. Not production-ready.
Must NOT protect anything of real value.** The do-not-protect-real-value banner is
permanent until an external audit + cryptanalysis completes and clears the scope above.
This package is the bridge *to* that audit; it is not a substitute for it.

**Auditor, start here:** (1) pin the target (`verify_b3` — now the default Goldilocks
`glass prove` path via `gprove_sound`; `--fast` self-check and `--baby-bear` are out of
scope). (2) Attack Poseidon — the single load-bearing primitive, including the 64-bit
squeeze width; if its RO model is false, nothing else matters. Everything else (the thin
68+12 margin, the hash-width cap, with-replacement sampling, the bridge's unresolved /
unsupported-call lowering — now a loud `error`, was a silent `EInt(0)` proven-0 (deep
recursion past the unroll fuel now also REFUSES loudly on the honest CLI path via the
`seval` guard, though the malicious/bypass path can still prove a truncated circuit) — and
the missing z-in-coset guard) is itemized above but secondary to those two.
