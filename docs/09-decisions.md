# 09 — Decisions and open questions

## Decisions made (Phase 0)

| # | Decision | Rationale | Reversible? |
|---|---|---|---|
| D1 | **Offline whole-game translation, not live hooking** | Context, consistency, line fitting, coverage of menus/UI, no latency in the read loop | No — it's the thesis |
| D2 | **LLMs never parse game formats** | Silent corruption; formats are deterministic and belong in C# | No |
| D3 | **Byte-identical round-trip gate per adapter** | The only cheap defence against a broken writer | No |
| D4 | **ASP.NET Core + browser workbench**, CLI is the engine | Dense bilingual tables, inline editing, and font-accurate `canvas.measureText` preview are web strengths; matches existing muscle memory from WhatNotNow/Fukidashi/Yohaku | Yes, with cost |
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
| D15 | **C# confirmed — but for ecosystem, not speed** (2026-08-23) | The pipeline is ~95% GPU-bound, so "fast and efficient" was never the real argument. GARbro + VNTranslationTools being .NET is; `Span<T>` and single-file publish are the rest. Rust and Python considered and rejected | No |
| D16 | **Pass-based execution; never escalate models inline** | Two large models can't be co-resident in ~20.4 GB. Inline escalation means ~120 model loads *and* evicts the KV prefix cache each time | No |
| D17 | **Prefer MoE for `translate`** | Full weights in VRAM, fraction active per token → large-model quality at small-model speed. Exactly the right trade for 3,000 sequential generation calls | Yes |

---

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

### Q2 — .NET SDK version
No SDK is installed on this machine at all (runtimes 3.1/6.0/8.0 only). Install the current
LTS. Confirm the actual version with `dotnet --list-sdks` after install and pin it in
`global.json` — don't take a version number in a doc on faith.

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
