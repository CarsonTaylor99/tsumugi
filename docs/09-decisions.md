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

---

## Open questions

### Q1 — What is the first real target game and engine? ⬅ **blocking Phase 1's second half**
The walking skeleton should be Ren'Py regardless (it's a day's work and proves the pipeline).
But the *first real target* determines adapter difficulty, whether bytecode rewriting is on
the Phase 6 critical path, and whether font hacking is needed at all. A KiriKiri title and a
Siglus title are months apart in effort. **Needs an answer before Phase 3.**

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

### Q7 — Repo visibility
Created **private** by default. Fan-TL tooling with an unfinished design; nothing here needs
to be public yet. `gh repo edit --visibility public` when and if that changes.
