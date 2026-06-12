<div align="center">

<img src="assets/glass-logo.jpg" alt="Glass" width="460"/>


### You can see straight through it.

[![Tests](https://github.com/EgorKhaklin/Glass/actions/workflows/tests.yml/badge.svg)](https://github.com/EgorKhaklin/Glass/actions/workflows/tests.yml)
[![Tests passing](https://img.shields.io/badge/tests-487%2F487-00bcd4?style=flat-square)](tests/test_glass.py)
[![Latest](https://img.shields.io/badge/release-v5.134.0-00bcd4?style=flat-square)](CHANGELOG.md)
[![Self-hosting](https://img.shields.io/badge/self--hosting-✓_bootstrap_fixpoint-00bcd4?style=flat-square)](docs/self-hosting.md)
[![Verified twice](https://img.shields.io/badge/proofs-checked_by_three_lineages-00bcd4?style=flat-square)](pentecost/)
[![License](https://img.shields.io/badge/license-MIT_OR_Apache--2.0-00bcd4?style=flat-square)](LICENSE)

</div>

<br/>

Now a machine writes the code.

You describe what you want; it generates the structure. It runs, it reads
cleanly, it passes the demo and you are asked to trust it. The hard part was
never the typing. It was the trust. Underneath the plausible surface: a side
effect nobody declared, a branch never handled, a function that does more than
its name admits. And the plausible now ships faster than anyone can read it.

Glass refuses the asking.

Let the structure be generated — by you, by a model, by anyone. Glass does not
ask where it came from. It asks only that the truth about it stay visible, and
visible means machine-checkable, not merely plausible.

> Looks right is not the same as is right. One can be generated. The other has
> to be reconstructed.

So nothing is left implicit. Every signature states what a function takes,
returns, touches, and how it fails — declared, not discovered at runtime. A
function can't touch, return, or fail in any way its signature doesn't admit.
Effects are declared or they don't compile. Matches are exhaustive. Failure is a
value the caller must face, never a silent surprise. None of this is taken on
faith; it's checked, by the compiler, on every program, today.

You don't audit the intention. You audit what's *there* — and what's there has
nowhere left to hide.

Generated or written, one rule does not bend: **you should never have to take
the code's word for it.**

It tells the truth. It reconstructs itself. It proves what happened — and the
proof is judged by three separate lineages, none of which trusts the others.
The first you have just read; the rest it shows you below.

<br/>

> ### It reconstructs itself.
> Glass's compiler is **written in Glass**, and rebuilds itself byte-for-byte —
> two independently-produced native compilers emit **identical C** (1,167 lines,
> to the last byte), with no other language left in the loop. The discipline
> runs deeper: every layer is computed *two independent ways* — a reference
> meaning and a compiled one — and forced to agree to the last bit. The instant
> the two reconstructions diverge, the build stops. And the whole core has a
> single content-addressed fingerprint — [the Name](name/) — one Merkle root
> over compiler, prover, verifiers, tests, and spec. Recompute it, match it,
> and you have attested byte-for-byte that this is the same Glass.
>
> ### It proves what happened.
> Built from scratch, in Glass: a **zero-knowledge prover**. Write a Glass
> function — arithmetic, comparisons, division, signed integers, strings,
> records, recursion, higher-order calls — and get a cryptographic proof of its
> result that reveals the inputs you choose and **nothing else**. Prove that a
> private key starts with `"sk-live-"`. Prove a private number sits in
> `[-40, 125]`. Prove `gcd(48, 18) = 6` through four levels of recursion. The
> prover is a from-scratch zk-STARK over the production **Goldilocks** field
> with the **Poseidon2** hash real provers use — field, Merkle trees, FRI,
> grinding, all of it readable in this repository.
>
> ### The proof is judged three ways.
> A proof you can't independently check is just a promise. So the verdict
> comes from **three separate lineages**. First, a witness-free verifier
> (`verify_b3`) re-derives every Fiat–Shamir challenge and checks the proof
> with no access to the witness. Second, [**Pentecost**](pentecost/) — a
> from-scratch re-implementation in a different language, sharing **no code**
> with the prover — checks the same portable proof and must agree
> (`glass prove --emit` → `glass verify`). Third, the **Third Witness**
> (`--cross-check`) re-executes your *source* under the reference interpreter
> — a lineage independent of the prover's compiler *and* its circuit lowering —
> and confirms the proven result means what the program means. That third eye
> is not decoration: it has caught real wrong-lowerings the other two
> *structurally cannot see*, most recently a capture bug that made the circuit
> attest `gcd(48,18) = 18` while the source computes 6. Caught, fixed,
> regression-gated — that is the system working.
>
> ### And it says no out loud.
> When Glass cannot faithfully turn a program into a circuit, it **ABSTAINs**
> — loudly, with a reason — rather than bluff an answer. The verdict is
> machine-readable: `glass prove` exits **0 ACCEPT · 1 ABSTAIN · 2 REJECT ·
> 3 DIVERGENCE**, so a script can never mistake a disproof for success. Over
> 1,600 tampered and forged proofs have been thrown at the second verifier —
> every one rejected. The test suite even ships a **malicious prover**: a
> forged bridge that plants a dishonest witness hint, whose proof must be
> REJECTED for the suite to pass. We attack our own prover so you don't have
> to take its word for it either.
>
> It is a from-scratch demonstration, not audited cryptography — what a proof
> here does and does not guarantee is written down in full in
> [the soundness ledger](docs/soundness.md) and [SECURITY.md](SECURITY.md).

<br/>

```glass
# The signature is the entire contract: this returns EITHER an answer OR an
# error, and the type system makes the caller handle both. No silent failure,
# no exception, no surprise — the function can't do anything the type doesn't say.

fn safe_divide(a: Int, b: Int) : Result<Int, String> =
  if b == 0 then Err("cannot divide by zero")
  else Ok(a / b)

match safe_divide(42, 6) {
  Ok(n)  => print("result: " ++ int_to_string(n));
  Err(e) => print("error: " ++ e)
}
```

<br/>

## Try it

```bash
git clone https://github.com/EgorKhaklin/Glass.git
cd Glass
pip install -e .            # Python 3.10+ — no deps for the interpreter
                            # (the native compiler also needs cc + libgc; see docs/getting-started.md)

glass examples/basic/hello.glass
glass                       # or start the REPL
```

Then make it prove something. Each line is a real claim about a **private**
input, and a real cryptographic proof of the answer:

```bash
# Prove a recursive algorithm ran exactly as written — and have the reference
# interpreter (a third, independent lineage) confirm the meaning:
glass prove --cross-check examples/prove/gcd_prove.glass x=48 y=18
#   result: 6   proof: ACCEPT   witness3: THIRD LINEAGE AGREES

# Prove a private string starts with "sk-live-" — without revealing the key:
glass prove examples/prove/private_prefix.glass key=sk-live-9f3a2c7e1b

# Prove a private value lies in a signed range [-40, 125] — reveal only the verdict:
glass prove examples/prove/signed_band.glass t=20

# Prove a private command is on an allowlist — match over a hidden string:
glass prove examples/prove/private_allowlist.glass cmd=deploy

# Prove a division and its remainder at once — a tuple result, both components bound:
glass prove examples/prove/private_divmod.glass a=17 b=5      # -> (3, 2)

# Emit a portable proof, then check it with the INDEPENDENT second verifier:
glass prove --emit /tmp/p.txt examples/prove/hello_prove.glass inp=9
glass verify /tmp/p.txt      # -> PENTECOST: ACCEPT  (a separate program, no shared code)

# And a false claim must die: claim 17/5 = 4 (the truth is 3) and watch it REJECT.
echo 'a / b' > /tmp/div.glass
glass prove --claim 4 /tmp/div.glass a=17 b=5 ; echo "exit $?"    # -> REJECT, exit 2
```

The verdict is always in the exit code — `0` ACCEPT, `1` ABSTAIN, `2` REJECT,
`3` cross-check DIVERGENCE — so CI pipelines and scripts can branch on the
truth without parsing anything.

Prefer the browser? `python -m http.server` and open
[`playground.html`](playground.html) — Glass runs fully client-side, no install.

<br/>

## The questions you should be asking

**Why a language, and not a library?**
Because the guarantee has to start at the *meaning*. A proving library bolts
onto a host language that hides effects, panics, and partial functions; the
proof then certifies a circuit someone hand-built and *hopes* matches the
code. In Glass the same definition is the program, the thing the type system
constrains, the thing the prover lowers, and the thing the reference
interpreter re-executes to check the lowering. One artifact, several
independent reconstructions of it — disagreement anywhere stops the world.

**What can I prove, today?**
The result of a Glass function over private inputs: arithmetic, equality and
ordering, integer and signed division/modulo, bitwise ops, strings (prefix,
equality, allowlist `match`), records and tuples, `if`/`match` control flow,
recursion and higher-order calls. Results can be scalars, strings, tuples, or
records. The catalog grows behind one rule: a shape lowers *faithfully* or it
ABSTAINs — there is no third option where it quietly proves the wrong thing.

**How big? How fast?**
On a laptop: `a + b` proves in seconds and the portable proof is ~13k tokens
(~68 KB). A comparison (`a < b`) carries a 32-bit range gadget — about a
minute and ~154k tokens, after a 3.6× proof-size reduction from batched
Merkle openings. Deep recursion with division (the `gcd` showcase) is the
heaviest thing in the repo — tens of minutes, and honest about it. Substrate
performance is an open, profiled frontier; the numbers in
[the roadmap](docs/roadmap.md) are measured, not promised.

**How secure is it, really?**
The honest headline: **~80-bit provable** soundness (82 FRI queries, blowup
32, 12-bit grind), ~135-bit under a standard conjecture — both labeled inline
on every proof. Zero-knowledge is opt-in (`--zk`). And the banner that
matters: **Glass is research-grade and UNAUDITED — do not protect real value
with it.** What separates it from hopeful crypto is that this boundary is
maintained as scrupulously as the code: [SECURITY.md](SECURITY.md) states
exactly what is machine-checked in-repo and what only an external audit can
establish, and [the audit-readiness package](docs/audit-readiness.md) is
already written for whoever takes that job.

**Why should I believe the prover isn't lying?**
You shouldn't — that's the design. Believe the *checks*: a witness-free
verifier; a second verifier with no shared code that must independently
agree; a third lineage that re-executes the source and flags any divergence
between what you wrote and what was proven (exit 3, hard failure); a fuzzer
that generates seven families of adversarial programs; a committed proof
corpus where every fixture is tamper-checked; and a suite that runs a
*deliberately malicious* prover whose forged proof must REJECT. Every
soundness fix in the changelog ships with the attack that motivated it.

**Who is this for?**
People who want to *see* how a zk-STARK actually works — every line from
field arithmetic to FRI folding is here, readable, in one self-consistent
language. People studying verifiable computation, teaching it, or building
intuition before reaching for production stacks. And anyone interested in
what programming looks like when "trust me" is removed from the vocabulary —
including trusting code that machines wrote.

**How is this different from Noir, Circom, Cairo, RISC Zero?**
Those are production systems, audited and optimized, and if you are shipping
value you should use them. Glass is the opposite end of a real trade: nothing
is a black box. No trusted setup, no external circuit library, no opaque
runtime — the compiler that compiles the prover is itself written in Glass
and reproduces itself byte-for-byte. It is a working, end-to-end,
fully-legible laboratory of the whole idea, small enough to actually read.

**What just shipped?**
`v5.131–v5.134`: a forgery-resistance audit of the prover came back clean and
its one hardening item (a free advice value in the divide-by-zero sub-circuit)
was closed *with a forged-prover regression gate*; the Third Witness caught
and v5.132 fixed a real inlining-capture wrong-lowering (`gcd` now proves
true through three agreeing lineages); the verdict became machine-readable
(exit codes); and the Goldilocks modular reduction was replaced with the
branch-light fast reduction, unit-tested against the generic one on 20M
inputs, with every proof byte-identical. The full ledger is in
[CHANGELOG.md](CHANGELOG.md).

<br/>

## Where to go

| If you want to… | Go here |
|---|---|
| **Learn the language** | [A tour](docs/language-tour.md) · [Getting started](docs/getting-started.md) · [the spec](LANG.md) |
| **See what it can express** | [`examples/showcase/`](examples/showcase/) |
| **Watch Glass reconstruct itself** | [Self-hosting](docs/self-hosting.md) · [`examples/selfhost/`](examples/selfhost/) |
| **See the zero-knowledge prover** | **[Frost — a zk-STARK in Glass](examples/frost/)** · [write Glass, get a proof](examples/prove/) |
| **Prove a query over private data** | **[Pane ⊕ Frost — the founding payoff](examples/prove/prove_pane.glass)** · [in zero-knowledge](examples/prove/prove_query_zk.glass) |
| **See a proof checked independently** | **[Pentecost — let the verifier be two](pentecost/)** · [`glass prove --emit` → `glass verify`](pentecost/README.md) |
| **Read the whole story** | [Glass, end to end](docs/the-story.md) |
| **Know what a proof here really guarantees** | [Soundness — the honest ledger](docs/soundness.md) · [SECURITY.md](SECURITY.md) |
| **Audit it (please)** | [The audit-readiness package](docs/audit-readiness.md) |
| **Know where it's headed** | [Roadmap](docs/roadmap.md) |

<br/>

## What's in here

```
glass/
├── glass.py          # the language — parser, type checker, interpreter (one file)
├── quartz.py         # the native back end — Glass → C
├── examples/         # everything below runs with `glass <file>`
│   ├── basic/  features/  showcase/  lib/   ·  learn the language
│   ├── selfhost/  quartz/  stage3/          ·  Glass compiling Glass
│   └── pane/  frost/  prove/                ·  built in Glass: a query language, a
│                                                zk-STARK, and a bridge from source to proof
├── pentecost/        # a second, independent verifier — every proof checked twice
├── name/ ledger/ seal/   # content-addressed identity · append-only verdict ledger · selective disclosure
├── fuzz/             # soundness fuzzers — 7 adversarial program families + tamper/claim campaigns
├── docs/             # tour, spec, self-hosting, soundness, audit-readiness, roadmap
├── tests/            # the regression suite (487/487)
└── playground.html   # browser playground (Pyodide)
```

<br/>

## Status

Glass is a research language and a labor of love. It self-hosts byte-for-byte,
passes 487/487 tests, runs in the browser, proves the result of a function and
has that proof judged by three independent lineages — and when it can't do
something faithfully, it refuses out loud instead of pretending. It is not
production-hardened, and it doesn't pretend to be: every claim above is a
command you can run, and every limit is written down plainly — start with the
[soundness ledger](docs/soundness.md). Nothing taken on faith, including the
faith you'd place in it.

## License

Dual-licensed under [MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE), your choice.
