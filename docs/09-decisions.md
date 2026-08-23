# 09 — Decisions and open questions

## Decisions made (Phase 0)

| # | Decision | Rationale | Reversible? |
|---|---|---|---|
| D1 | **Offline whole-game translation, not live hooking** | Context, consistency, line fitting, coverage of menus/UI, no latency in the read loop | No — it's the thesis |
| D2 | **LLMs never parse game formats** | Silent corruption; formats are deterministic and belong in ordinary deterministic code | No |
| D3 | **Byte-identical round-trip gate per adapter** | The only cheap defence against a broken writer | No |
| D4 | **Local web workbench (FastAPI), CLI is the engine** | Dense bilingual tables, inline editing, and font-accurate `canvas.measureText` preview are web strengths; matches WhatNotNow/Fukidashi/Yohaku exactly | Yes, with cost |
| D5 | **SQLite project store; translations keyed by `SourceHash`** | Re-extracting after an adapter fix must not lose work | Yes |
| D6 | **Per-task LLM bindings**, no global provider switch | Same reason as Yohaku: rebind one task when a better model ships | Yes |
| D7 | **Chunked translation (5–15 units) with rolling context**, not per-line | ~3× throughput *and* better coherence — the rare case where both improve together | Yes (it's a config knob) |
| D8 | **Schema-constrained decoding** (GBNF / JSON schema) | Eliminates a whole class of retry | Yes |
| D9 | **`[stable prefix][volatile suffix]` prompt architecture** | KV cache reuse; cheap and load-bearing | Yes |
| D10 | **Patch-only distribution, never assets** | Hard rule 4 | No |
| D11 | **Bible requires human approval before translation** | Names and honorific policy are irreversible after 30k lines | No |
| D12 | Project name **Tsumugi (紡ぎ)** — "spinning thread / weaving" | Fits the Fukidashi / Yohaku naming; describes the pipeline | Trivially — `gh repo rename` |
| D13 | **Generic tool, no single target game** (2026-08-23) | User's call. Makes the engine abstraction the product rather than a convenience, and promotes hard rule 8 and the family ladder to load-bearing | No |
| D14 | **Two round-trip gates: identity *and* expansion** | Identity alone moves nothing, so every offset stays correct by accident. Expansion is what proves offset fixup — the bug class that matters most as engine coverage widens | No |
| ~~D15~~ | ~~C# confirmed for ecosystem, not speed~~ — **superseded by D19** | The ecosystem argument was overstated: `docs/02-engines.md` Q5 already chose to *shell out* to GARbro/VNTextPatch rather than vendor them, and shelling out works identically from Python | — |
| D16 | **Pass-based execution; never escalate models inline** | Two large models can't be co-resident in ~20.4 GB. Inline escalation means ~120 model loads *and* evicts the KV prefix cache each time | No |
| D17 | **Prefer MoE for `translate`** | Full weights in VRAM, fraction active per token → large-model quality at small-model speed. Exactly the right trade for 3,000 sequential generation calls | Yes |
| ~~D18~~ | ~~Modern C# idioms mandatory~~ — **superseded by D19** | Measurement retained below; the conclusion changed | — |
| D19 | **Python 3.12+, not C#** (2026-08-23) | User's call, on session token cost. Measured 1.46× fewer tokens than modern C#; direct reuse of Fukidashi/Yohaku; Ren'Py tooling is Python; the Fukidashi bridge becomes an import rather than IPC. Runtime speed is a non-issue at ~95% GPU-bound | Yes, with cost |
| D20 | **`pyright --strict` is a hard rule (9), not a style choice** | It is the only mechanical replacement for the compiler C# would have provided on offset arithmetic, where errors are silent rather than raising | No |

---

## Language token-density measurement (2026-08-23)

Same function (placeholder validator) implemented in six languages, so D15/D18 are not
re-litigated from intuition in a future session:

| Language | Lines | ~Tokens | vs Python |
|---|---|---|---|
| Python | 12 | 145 | 1.00× |
| TypeScript | 11 | 167 | 1.16× |
| **F#** | **11** | 181 | **1.25×** |
| C# (modern idioms) | 15 | 211 | 1.46× |
| Go | **46** | 247 | 1.71× |
| C# (conventional) | 25 | 282 | 1.95× |

Three findings worth keeping:
- **Python is near the floor but the margin is small.** TypeScript and F# are within 25%.
- **Go is a trap.** Minimal syntax reads as terse, but no collection operators and explicit
  everything gives 46 lines against Python's 12 — nearly 4× the line count, 1.71× the tokens.
  Do not reach for Go on a "it's simple so it must be compact" intuition.
- **F# is the genuinely interesting option**: near-Python density, *fewest lines of any
  language tested*, fully static typing, and it is **.NET** — so the D15 ecosystem argument
  (GARbro, VNTranslationTools, SkiaSharp, ASP.NET Core) survives completely intact. Its
  discriminated unions are close to ideal for the placeholder-kind and engine-variant models,
  with exhaustiveness checking that a C# enum cannot give.

**Outcome (D19): Python.** The measurement above was the deciding input, together with three
things that only became clear on re-examination:
- The **ecosystem argument was overstated.** Q5 had already chosen to shell out to
  GARbro/VNTextPatch rather than vendor them, and a subprocess call is language-agnostic.
- **Ren'Py's toolchain is Python** (`unrpa`, `unrpyc`, Ren'Py itself), so the Phase 1 walking
  skeleton gets *easier*, not harder.
- **The tool is never distributed** — only the patch is. Single-binary packaging, one of C#'s
  real advantages, turned out not to matter for a local single-user authoring tool.

**F# remains the road not taken.** It measured 1.25× with the fewest lines of anything
tested, is fully typed, and would have kept the .NET ecosystem. It lost on model fluency:
far less F# in training data, and extra iterations would swamp a density edge, since
iteration count dominates session cost. Recorded here so it isn't rediscovered from scratch.

**What Python gives up, and what replaces it** — the honest ledger:

| Lost with C# | Replacement |
|---|---|
| Compiler catching offset-math errors | `pyright --strict` in CI (hard rule 9) + both round-trip gates carrying more weight |
| `Span<T>` zero-copy binary parsing | `construct` (bidirectional, so one definition serves parse *and* build → Gate A), `memoryview`, `mmap` |
| Vendoring GARbro / VNTextPatch source | Shell out to their CLIs — already the plan (Q5); `pythonnet` as an unused fallback |
| Fast bulk byte work | `hashlib`, `mmap`, `numpy` on those paths only |
| Single-file `.exe` distribution | Irrelevant: the tool stays local, only the patch ships |

And what it gains: Fukidashi/Yohaku code reuse, `hypothesis` for the corpus mutation fuzzing,
`pydantic` as one definition serving type + JSON Schema + validation, and the Phase 7
Fukidashi bridge collapsing from an IPC boundary to an import.

## Open questions

### ~~Q1 — What is the first real target game and engine?~~ ✅ **Answered 2026-08-23**
**Generic tool, no specific game** → D13. Consequences, all now baked into the docs:
bytecode rewriting and font hacking are both on the critical path (nothing is ruled out by
picking an easy title); hard rule 8 forbids engine branching outside `Tsumugi.Formats/`; and
Phase 7 becomes a **family ladder** rather than "a second adapter."

### Q1b — Which titles seed the Tier 1 corpus? ⬅ **now the practical blocker**
Generic means CI needs real files, and game assets can't be committed (hard rule 4).
Tier 0 synthetic fixtures cover adapter development, but Gate B's "the game still boots"
needs actual games. Needs: a shortlist of freely-redistributable or freely-downloadable
titles per engine family, each with its license individually **verified, not assumed**.
Ren'Py is easy (open demo projects ship with the SDK); the bytecode engines are the hard
ones and may end up Tier 3 (user-owned, local-only, never in CI). See `docs/10-corpus.md`.

### Q2 — Python version and toolchain
Target 3.12+. Pin the exact version in `.python-version` and manage the environment with
`uv`. Confirm what's actually installed rather than trusting a doc — and note that the
Windows-side tooling matters here too, since the games and the proxy DLL are Windows.

### Q3 — llama.cpp server or Ollama as the primary runtime?
Ollama is what's already running on this box and what Fukidashi/Yohaku use. llama.cpp's
server offers finer control over GBNF grammars, parallel slots (`-np`), and cache-reuse
behaviour — all three of which are in the throughput table. Both sit behind `ILlmClient`, so
this is a default-choice question, not an architecture one. **Suggest: benchmark both during
Phase 4's bench-set work and let the measurement decide.**

### Q4 — Default honorific policy
Keep (`-san`, `-senpai`) or localise? Affects every line. Keeping is the fan-TL norm and
matches the Japanese audio the player is hearing, which is a real argument in a *voiced*
medium. Per-project setting either way, but the default matters because most projects won't
change it. **Suggest: keep, defaulted, prominently changeable at the bible gate.**

### Q5 — Vendor or shell out to GARbro / VNTextPatch?
Depends on their actual licenses, which must be **read and verified**, not assumed.
Shelling out is lower risk and lower coupling; vendoring is faster at runtime and removes a
dependency. **Suggest: shell out initially, revisit only if it becomes a bottleneck.**

### Q6 — Chunk size
5–15 units. Larger is faster and more coherent; larger also raises output-format fragility.
**Suggest: start at 10, then let the measured validator failure rate tune it — it's an
empirical question, not a design one.**

### ~~Q7 — Repo visibility~~ ✅ **Answered 2026-08-23 — public**
Consistent with `fukidashi` and `yohaku`. Two standing consequences:
- **The design docs are the public face of the project.** They describe patch-only tooling
  (hard rule 4) and contain no game assets. Keep it that way — the `.gitignore` blocks
  archive and media extensions deliberately, so don't relax it.
- **CLAUDE.md and `docs/04-llm.md` reference this specific machine** (WSL paths, GPU
  hang/TDR history, browser VRAM usage). Harmless, and load-bearing for the throughput
  numbers, but it's now public — genericise it if that ever stops being wanted.
