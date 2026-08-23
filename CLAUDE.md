# CLAUDE.md — Tsumugi (紡ぎ)

## What this project is

An **offline visual-novel translation toolchain**. Point it at an installed Japanese VN;
it produces a fully translated, playable English **patch**. Deterministic work (archive
unpacking, script parsing, text reinsertion, font metrics, patch building) is Python. The
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
   parsed by deterministic Python. An LLM guessing at binary offsets produces silent
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
8. **No engine branching outside `tsumugi/formats/`.** No `if engine == …` anywhere else,
   ever. Anything a later stage needs to know about an engine is exposed through
   `EngineTextCaps`. This is the rule that keeps a *generic* tool generic: the moment
   Stage 5 or Stage 7 knows what KiriKiri is, the abstraction is dead and every new engine
   becomes a cross-cutting change.
9. **`pyright --strict` passes, with no `Any` in format or pipeline code.** Enforced in CI.
   Without a compiler this is the only mechanical defence against offset-math errors, and
   those errors are silent — they corrupt a save file rather than raising. A `# type: ignore`
   in `tsumugi/formats/` or `tsumugi/patch/` needs a comment justifying it.

## Stack

**Python 3.12+.** Everything except the models. Chosen 2026-08-23 over C# (D19) primarily for
**session token cost** — a representative function measures 1.46× the tokens in modern C# —
and for direct reuse of the Fukidashi/Yohaku codebases. Runtime speed is a non-issue here:
this pipeline is ~95% GPU-bound and parsing a 3 MB script takes milliseconds in any language.

- **`uv`** for environment and dependency management. Not pip, not poetry, not conda.
- **`pyright` in strict mode — mandatory, enforced in CI (hard rule 9).** This is not a style
  preference. Python's weakness for this project is offset arithmetic in binary parsers, where
  a type error becomes silent corruption discovered at hour 14 of a run instead of at compile
  time. Strict typing buys most of that back; skipping it forfeits the main thing C# offered.
- **`pydantic`** for every data model. One definition yields the Python type, the JSON Schema
  for constrained decoding, and validated parsing of model output — three uses, one edit.
  This is the schema-first lever; use it rather than hand-writing parallel definitions.
- **`construct`** for binary formats. It is **bidirectional by design** — one declarative
  definition gives you both parse and build — which maps directly onto Gate A (identity
  round-trip). Prefer it over hand-rolled `struct.unpack` wherever a format is regular enough.
  `memoryview` / `mmap` for the parts that aren't.
- **`sqlite3`** (stdlib) for the project store. One `.tsumugi` file per game.
- **`fonttools` + `uharfbuzz`** for real glyph advances and shaping (line fitting).
- **`fugashi`** or **`SudachiPy`** for Japanese morphology (term mining). Verify dictionary
  licensing before depending on either.
- **`httpx`** for the LLM client, **`typer`** for the CLI, **`rich`** for progress and ETA.
- **`pytest` + `hypothesis`.** Property-based testing is an unusually good fit here: the
  mutation fuzzing in `docs/10-corpus.md` is literally "generate valid length-changing
  mutations, assert the round-trip holds." Let Hypothesis generate them.
- **UI: FastAPI + a local browser workbench.** Same shape as WhatNotNow, Fukidashi, and
  Yohaku. The CLI is the real engine; the web UI drives it.

**What Python costs us, and the mitigation** — be honest about this rather than discovering
it in Phase 7:
- No compiler to catch offset-math errors → **strict pyright, plus both round-trip gates
  doing more work than they would in a typed language.** Gate B matters more here, not less.
- Cannot vendor GARbro / VNTranslationTools source → **shell out to their CLIs**, which was
  already the plan (Q5). `pythonnet` is a fallback if in-process access ever becomes
  necessary; it has not yet.
- Bulk byte work (hashing, diffing multi-GB archives) is slow in pure Python → `hashlib`,
  `mmap`, and `numpy` for those paths specifically. Nowhere else needs it.

**Two things are not Python and that's expected:** the font/encoding proxy DLL must be native
(C++) because it injects into the game process, and external format tools are invoked as
subprocesses. The **Fukidashi bridge (Phase 7) is now a plain import, not an IPC boundary** —
one of the concrete wins from this switch.

## Token-efficient Python (conventions)

Session token cost is a real budget and a stated reason for choosing Python (D19). Do not
give the advantage back:

- **Keep files under ~300 lines.** Re-reading a 2,000-line module to change one function is
  the actual token sink — far larger than any syntax difference. The package layout below
  exists partly for this.
- **Tests must fail with values, not verdicts.** `expected 0x40 at offset 12, got 0x44` costs
  one read; `assert failed` costs a debugging session. Use `pytest` assertion rewriting and
  explicit messages. A good failure message *is* a token optimisation — which is why the
  round-trip gates emit byte diffs (`docs/10-corpus.md`).
- **Filter tool output at the source.** `pytest -q`, `pyright --outputjson | jq`, pipe builds
  and logs through `grep`/`head`. Raw output routinely dwarfs the source it describes.
- **Generate, don't hand-write.** One `pydantic` model → Python type + JSON Schema + SQLite
  DDL. Parallel hand-maintained definitions are both a token cost and a drift bug.
- **Never re-read a file to confirm an edit landed.** The tooling errors if it didn't.
- **Long pipeline runs must log terse failures.** A 5-hour run that dumps stack traces per
  failed line produces logs nobody can afford to read. One line, with values, per failure.


## LLM routing: per-task bindings (load-bearing)

Same rule as Yohaku, same reason. **Every model-using task is independently bound to a
`{provider, model, params}`, swappable by config and in the UI.** No global provider
switch, no stage hardcoding a model. Tasks:

- `bible.map` — per-scene observation extraction
- `bible.reduce` — merge observations into the canonical bible
- `translate` — the bulk line/chunk translation (this is 95%+ of the compute)
- `judge` — QA second-opinion on flagged lines only
- `retry` — the escalation model for lines that failed validation twice

**Model tiering is the point.** `translate` runs tens of thousands of times; `bible.reduce`
and `retry` run rarely. Do not run the biggest model on every line by default because it's
what happens to be loaded. Current model picks and the reasoning live in `docs/04-llm.md` —
**that document is the authority; do not choose a model from memory.**

### VRAM budget: the number that decides everything

**This box has ~20.4 GB usable, not 24 GB.** Measured 2026-08-23: 3.9 GB is held at idle by
Windows desktop compositing and GPU-accelerated Brave, and `nvidia-smi` under WSL cannot see
those processes. It also *fluctuates* with what's open. Every model-sizing decision must be
made against ~20.4 GB, and a guide that says "fits in 24 GB" probably does not fit here.

**Freeing that 3.9 GB is a real lever**, not housekeeping — it is the difference between the
best available model fitting and not fitting. Disable Brave's hardware acceleration (or
close it) before a long run; the preflight gate should measure free VRAM and refuse to start
against a model that won't fit.

### Never escalate inline (load-bearing)

You cannot hold two large models at once in 20.4 GB, so an inline escalation to a bigger
`retry` model is an unload/reload — ~120 model loads across a run, and, worse, **each swap
evicts the KV prefix cache**, destroying the prompt-caching win the throughput math depends
on. Run **passes by resident model** instead:

```
Pass 1   translate model resident   →  translate everything, QUEUE failures
Pass 2   same model, no swap        →  retry the queue with validator feedback
Pass 3   swap once to the big model →  drain remaining failures + judge
```

Two model loads for the whole run instead of a hundred and twenty. `judge` may run
interleaved **only** when it is small enough to be co-resident with `translate`
(`OLLAMA_MAX_LOADED_MODELS=2`) — that buys live quality telemetry from hour 1. If the
`translate` model is large enough to fill VRAM alone, `judge` becomes a Pass 3 job.

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
0  Detect     engine fingerprint from the game dir       py
1  Unpack     archives → loose files (read-only source)  py
2  Extract    scripts → TextUnits + placeholders         py   ← round-trip gate here
3  Analyze    order graph, speakers, voice map, terms    py   (no LLM)
4  Bible      map/reduce over scenes → draft bible       LLM  → human gate
5  Translate  chunked, context-windowed, validated       LLM  ← the 95%
6  QA         validators + judge on flagged lines        py+LLM
7  Fit        measure, reflow, insert break codes        py
8  Build      reinject, repack, emit patch + installer   py
```

Stage 3 is deliberately LLM-free. The reading order of a VN is a *graph* (labels, jumps,
choices), not file order — reconstructing it is graph work, and feeding scenes to the model
out of order is exactly the scrambled-order failure Fukidashi hit on chapter 1.

## Repo layout (planned — no code yet)

```
tsumugi/core/        domain models (pydantic): TextUnit, Scene, Bible, Glossary, Project
tsumugi/formats/     EngineAdapter implementations, one module per engine
tsumugi/archives/    container read/write (xp3, rpa, arc, pfs, …) — `construct` definitions
tsumugi/analysis/    morphology, term mining, choice graph, voice→speaker map
tsumugi/llm/         LlmClient protocol, batching, schema-constrained decode, prompt assembly
tsumugi/pipeline/    stage runner, job queue, checkpoint/resume
tsumugi/qa/          validators and linters
tsumugi/patch/       reinjection, repack, diff, installer
tsumugi/cli/         typer entrypoint — the real interface
tsumugi/studio/      FastAPI host + browser workbench
tests/               round-trip corpus, hypothesis fuzzing, validator unit tests
```

`EngineAdapter` is a `typing.Protocol`, not an ABC — structural typing keeps adapters
decoupled and `pyright --strict` still checks conformance.

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
