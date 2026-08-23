# CLAUDE.md — Tsumugi (紡ぎ)

## What this project is

An **offline visual-novel translation toolchain**. Point it at an installed Japanese VN;
it produces a fully translated, playable English **patch**. Deterministic work (archive
unpacking, script parsing, text reinsertion, font metrics, patch building) is C#. The
language work (story bible, translation, QA judging) runs on **local LLMs**.

It is a **generic tool** — there is no single target game — so the engine abstraction is
load-bearing rather than aspirational. See hard rule 8 and `docs/10-corpus.md`.

This is a **personal-use tool** for fan translation. It processes copyrighted game text on
the user's own machine. See "Hard rule 4" — the tool never redistributes game assets.

## Core thesis: translate the whole game once, offline (load-bearing)

**Real-time / hook-based translation is an explicit non-goal.** Textractor, LunaTranslator,
XUnity.AutoTranslator's live mode — all rejected as the *reading* experience. Reasons, in
order of how much they matter:

1. **No context.** A hooked line arrives alone. The model can't see who's speaking, what
   was just said, or what the term meant 4 hours ago. This is the same failure Yohaku and
   Fukidashi were built to fix; do not reintroduce it here.
2. **No consistency.** Names, terms, and character voice drift within a single session.
3. **No length fitting.** English runs 1.5–2.5× longer than Japanese. Live TL overflows
   the textbox and gets clipped. There is no second chance to fix it.
4. **Latency in the read loop.** Even 2s/line destroys pacing across a 40-hour game.
5. **It can't reach most of the text.** Menus, save/load screens, choice buttons, and
   text baked into CG images are invisible to a text hook.

Tsumugi does the model work **ahead of time, with the full script available**, gates it
behind QA, and ships a patch. At play time there is no model in the loop at all — the game
is just in English. Design every decision against that.

## Hard rules

These are gates, not preferences. Violating one is a bug even if the output looks fine.

1. **LLMs never parse game formats.** Archives, script bytecode, and control codes are
   parsed by deterministic C#. An LLM guessing at binary offsets produces silent
   corruption. The only sanctioned LLM use near formats is *dev-time assistance* while
   reverse-engineering a new one (reading hexdumps with a human), never in the pipeline.
2. **Two round-trip gates, both required.** For every engine adapter:
   - **Gate A — identity.** Extract → reinject *unchanged* → **byte-identical** file.
   - **Gate B — expansion.** Extract → reinject text ~2× longer → the file still parses,
     the archive still loads, the game still boots.

   Gate A alone is not enough and is easy to be fooled by: nothing moves, so every offset
   in the file is still correct by accident. Gate B is what proves offset fixup and
   string-table rebuilding — the class of bug that silently corrupts bytecode engines. No
   translated build may be produced for an engine failing either gate. Build both in
   Phase 1, before any LLM code exists. See `docs/10-corpus.md`.
3. **Placeholder contract.** Engine control codes are masked to sentinels before the model
   sees them and validated on the way back. A response that violates the contract is
   rejected and retried — never patched up by hand-waving. See `docs/05-qa.md`.
4. **Ship a patch, never assets.** Output is a diff/overlay plus an installer that applies
   it to the user's own legally-obtained install. Never build a "repack the whole game"
   distribution path. No feature that uploads, shares, or hosts game files.
5. **The bible is human-gated.** The auto-generated bible is a *draft*. A full translation
   run cannot start until the user has reviewed and marked it approved. Names and
   honorific policy are effectively irreversible once 30k lines are translated against
   them.
6. **Locked lines are immutable.** Any line the user has edited or approved is never
   silently re-translated by a later run. Re-runs touch only `machine` status lines.
7. **Nothing is destructive.** The game directory is read-only to Tsumugi. All output goes
   to the project folder. The installer backs up before it writes.
8. **No engine branching outside `Tsumugi.Formats/`.** No `if (engine == …)` anywhere else,
   ever. Anything a later stage needs to know about an engine is exposed through
   `EngineTextCaps`. This is the rule that keeps a *generic* tool generic: the moment
   Stage 5 or Stage 7 knows what KiriKiri is, the abstraction is dead and every new engine
   becomes a cross-cutting change.

## Stack

- **C# / .NET, current LTS.** Everything except the models.
  - ⚠️ **Prerequisite: there is no .NET SDK on this machine** (`dotnet --list-sdks` is
    empty; only runtimes 3.1/6.0/8.0 are present). Install the SDK before Phase 1.
  - `dotnet` and `gh` exist only as **Windows** binaries under WSL —
    `/mnt/c/Program Files/dotnet/dotnet.exe`, `/mnt/c/Program Files/GitHub CLI/gh.exe`.
    Prefer working from Windows-side paths for build/run; WSL paths are fine for docs/git.
- **Local LLMs via an OpenAI-compatible HTTP endpoint.** Ollama or llama.cpp's server.
  Never bind a stage to one runtime — see "LLM routing" below.
- **SQLite** as the project store (`Microsoft.Data.Sqlite`). One `.tsumugi` project file
  per game. Source of truth for every text unit and its translation state.
- **SkiaSharp / HarfBuzzSharp** for real glyph-advance measurement (line fitting).
- **NMeCab** for Japanese morphology (term mining, proper-noun candidates). Verify the
  package and dictionary licensing before depending on it.
- **UI: ASP.NET Core minimal API + a local browser workbench.** Decided (revisit only with
  cause): the workbench is a dense bilingual table with filtering, inline editing, diffing,
  and a font-accurate textbox preview. That is a web strength and a XAML weakness, it
  matches the muscle memory from WhatNotNow/Fukidashi/Yohaku, and the game's own font can
  be loaded as a webfont so `canvas.measureText` previews overflow exactly. The CLI is the
  real engine; the web UI drives it.

## LLM routing: per-task bindings (load-bearing)

Same rule as Yohaku, same reason. **Every model-using task is independently bound to a
`{provider, model, params}`, swappable by config and in the UI.** No global provider
switch, no stage hardcoding a model. Tasks:

- `bible.map` — per-scene observation extraction
- `bible.reduce` — merge observations into the canonical bible
- `translate` — the bulk line/chunk translation (this is 95%+ of the compute)
- `judge` — QA second-opinion on flagged lines only
- `retry` — the escalation model for lines that failed validation twice

**Model tiering is the point.** `translate` runs tens of thousands of times and should be
the *smallest model that passes QA*; `bible.*` and `retry` run rarely and should be the
biggest model that fits VRAM. Do not run a 31B on every line by default because it's what
happens to be loaded.

Local runtime notes that have already cost time on this machine:
- **Always pass an explicit large `num_ctx`.** Ollama silently truncates past its small
  default and the context-window design dies without an error.
- `num_ctx` is a **ceiling, not an allocation** — size it to measured free VRAM (the
  ladder from Fukidashi: 16384 / 12288 / 8192). Reuse that logic, don't reinvent it.
- q8_0 KV cache + flash attention are on by default on this box.
- This PC has a **history of GPU hangs/TDRs/BSODs** and the GPU is clock-capped to
  1800 MHz. A 20-hour unattended run *will* be interrupted. Checkpointing is not optional.

## Pipeline (nine stages)

Full detail in `docs/01-pipeline.md`. Summary:

```
0  Detect     engine fingerprint from the game dir       C#
1  Unpack     archives → loose files (read-only source)  C#
2  Extract    scripts → TextUnits + placeholders         C#   ← round-trip gate here
3  Analyze    order graph, speakers, voice map, terms    C#   (no LLM)
4  Bible      map/reduce over scenes → draft bible       LLM  → human gate
5  Translate  chunked, context-windowed, validated       LLM  ← the 95%
6  QA         validators + judge on flagged lines        C#+LLM
7  Fit        measure, reflow, insert break codes        C#
8  Build      reinject, repack, emit patch + installer   C#
```

Stage 3 is deliberately LLM-free. The reading order of a VN is a *graph* (labels, jumps,
choices), not file order — reconstructing it is graph work, and feeding scenes to the model
out of order is exactly the scrambled-order failure Fukidashi hit on chapter 1.

## Repo layout (planned — no code yet)

```
src/Tsumugi.Core/        domain types: TextUnit, Scene, Bible, Glossary, Project
src/Tsumugi.Formats/     IEngineAdapter implementations, one folder per engine
src/Tsumugi.Archives/    container read/write (xp3, rpa, arc, pfs, …)
src/Tsumugi.Analysis/    morphology, term mining, choice graph, voice→speaker map
src/Tsumugi.Llm/         ILlmClient, batching, schema-constrained decode, prompt assembly
src/Tsumugi.Pipeline/    stage runner, job queue, checkpoint/resume
src/Tsumugi.Qa/          validators and linters
src/Tsumugi.Patch/       reinjection, repack, diff, installer
src/Tsumugi.Cli/         headless driver — the real interface
src/Tsumugi.Studio/      ASP.NET Core host + browser workbench
tests/                   round-trip corpus, validator unit tests
```

## Conventions

- **Every LLM call is cached to disk**, keyed by `(unit_id, stage, provider, model, params_hash,
  prompt_hash)`. Iterating on a prompt must not re-bill 20 hours of GPU.
- **Every text unit records provenance**: source hash, model, prompt hash, timestamp,
  status (`machine` / `edited` / `approved` / `locked` / `failed`). Re-runs are cheap and
  auditable.
- **Structured output is enforced by the decoder**, not by asking nicely. Use JSON-schema /
  GBNF grammar constraints so the model *cannot* emit malformed batches. Still parse
  defensively.
- **Prompts are built as `[stable prefix][volatile suffix]`** so the server's KV cache
  reuses the prefix across calls. Never interleave volatile content into the system block.
- Source addressability everywhere: any English line must be able to point back to its
  exact source unit, file, and offset. This is the trust mechanism.

## Build order (do not skip ahead)

- **Phase 1 — Walking skeleton.** One engine, extract + reinject, **byte-identical
  round-trip proven**, game still boots. Zero LLM code. Do not start Phase 4 before this
  passes.
- **Phase 2 — Project store + workbench (read-only).** SQLite, bilingual table, TM/dedupe.
- **Phase 3 — Analysis + bible.** Deterministic pass, then map/reduce, then the editor and
  the approval gate.
- **Phase 4 — Translation.** Chunked context windows, placeholder validation, resume.
- **Phase 5 — Fit + preview.** Font metrics, reflow, encoding/font hacks, in-situ preview.
- **Phase 6 — Patch build + installer.**
- **Phase 7 — One adapter per engine family** (text-script → archive+script → bytecode →
  managed runtime). Family coverage, not engine count, is what proves the abstraction.
  Then the **Fukidashi bridge** for text baked into CG/UI images.

See `docs/08-roadmap.md` for acceptance criteria per phase.

## Explicit non-goals

- **Real-time / hooked translation as the reading experience.** See the thesis.
- **Voice synthesis or dubbing.** The Japanese audio stays.
- **Redistributing game assets.** Patches only.
- **A universal 300-format extractor.** GARbro already exists; interoperate rather than
  re-implement (`docs/02-engines.md`).
- **Cloud-first translation.** Cloud providers may exist behind `ILlmClient` for
  comparison, but the pipeline must be fully functional offline on local models.

## Notes

- Sibling projects to reuse rather than reinvent: **Fukidashi** (`/home/claude/fukidashi`)
  for OCR + mask + retypeset of image-baked text, and its VRAM ladder / preflight crash
  guards. **Yohaku** (`/home/claude/yohaku`) for the per-task binding pattern and
  context-carry design.
