# 01 — The pipeline

Nine stages. Each has a defined input, output, and gate. Stages are individually
re-runnable; nothing recomputes what a later stage already locked.

---

## Stage 0 — Detect

**In:** a game install directory. **Out:** `{engine, confidence, evidence[]}`.

Fingerprint by file signatures, not guesswork: archive magic bytes (`XP3\r\n`, `RPA-3.0`,
`PFS`, `.int`), executable imports and version strings, telltale filenames
(`data.xp3`, `Scene.pck`, `nscript.dat`, `*.rpa`, `Assembly-CSharp.dll`).

Ship `signatures/engines.json` as data so a new engine is a data edit, not a rebuild. Report
confidence and evidence to the user; never silently pick.

> **Gate:** unknown engine → stop with a useful report (what was found, what it resembles),
> not a crash.

---

## Stage 1 — Unpack

**In:** archives. **Out:** loose files in the project workspace.

The game directory is **read-only**. Everything is copied out. Where an existing tool is
better than what we'd write (GARbro for exotic containers), shell out to it and treat it as
an external dependency — see `docs/02-engines.md`.

---

## Stage 2 — Extract

**In:** script files. **Out:** ordered `TextUnit` rows in the project DB.

```
TextUnit
  Id            stable, content+location derived
  SourceText    control codes replaced by sentinels ⟦0⟧ ⟦1⟧ …
  Placeholders  [{ index, raw, kind, rules }]
  Speaker       raw name field / bracket / null
  Kind          Dialogue | Narration | Choice | UI | System | Name | Debug
  File, Offset, Ordinal
  VoiceAsset    referenced voice file, if any
  SceneId, RouteHints
  SourceHash
```

Two things earn their own attention here:

**Classification.** Not every string in a script is player-facing. Asset paths, labels,
debug strings, and flag names must be excluded or they get translated and break the game.
Start with per-engine heuristics (is it in a `@say` opcode? does it contain kana?) and only
reach for a model if the heuristics genuinely can't separate them.

**Placeholders.** Control codes never reach the model. See `docs/05-qa.md` for the contract.

> **Gate — the round-trip identity test.** Extract, then reinject the *unmodified* text, and
> diff against the original file. Byte-identical or the adapter is broken. This runs over a
> corpus in CI. Hard rule 2.

---

## Stage 3 — Analyze (no LLM)

**In:** TextUnits + script control flow. **Out:** reading-order graph, speaker map, term
candidates, scene segmentation.

This stage exists because **file order is not reading order.** A VN script is a graph of
labels, jumps, conditionals, and choices. Translating in file order feeds the model scenes
out of sequence, which is exactly the failure mode that forced the chapter-1 redo in
Fukidashi.

1. **Control-flow graph** from the engine's jump/label/choice opcodes. Topologically order
   what can be ordered; segment into scenes at jump targets and scene-transition opcodes.
2. **Route detection.** Branch points → route labels. Common route vs. character routes.
   Used later for spoiler-scoped context and for prioritizing translation order.
3. **Speaker attribution.** Explicit name fields first. Where absent, the **voice filename is
   the best signal available** — `voice/ARI_0142.ogg` clusters by prefix into per-character
   voice sets, and mapping prefix→character is a one-time human confirmation of ~10 items.
   Track that a nametag may be a *variable* (`???` before a reveal) and never bake a name
   into a line where the engine expects the placeholder.
4. **Term mining.** Morphological analysis (NMeCab) → proper nouns, unknown-word candidates,
   high-frequency compounds. Rank by frequency × unknown-ness. This is the raw material for the
   glossary and it costs no GPU time.
5. **Duplicate detection.** Hash source text. VNs repeat lines heavily across routes;
   duplicates translate **once** and share the result. Typically 10–30% of units.

---

## Stage 4 — Bible (LLM, map/reduce) → human gate

The whole script does not fit in context, so this is map/reduce, not one big read.

- **Map:** per scene, extract structured observations — characters present, how each speaks,
  first-person pronoun, who they address and with what honorific, new terms, tone.
- **Reduce:** merge observations into one canonical bible; resolve contradictions; propose
  an English rendering for every name and term; flag conflicts for the human.

Schema and rationale: `docs/03-bible.md`.

> **Gate — bible approval.** Hard rule 5. Names, honorific policy, and register decisions
> are effectively irreversible after 30,000 lines. The user reviews and approves before
> Stage 5 can start. This is the one mandatory stop in the whole tool.

---

## Stage 5 — Translate (LLM) — the 95%

Unit of work is a **chunk** (~5–15 consecutive units in reading order), not a line.

Prompt assembly, in `[stable prefix][volatile suffix]` order so the server's KV cache reuses
the prefix (`docs/04-llm.md`):

```
STABLE    system role + style policy + honorific policy + golden few-shot examples
          + core cast card (the recurring principals)
VOLATILE  scene cast card (who is in *this* scene)
          + glossary entries matched to *this* chunk's source text
          + rolling context: previous N units, source + the APPROVED English
          + the chunk itself, numbered, with sentinels
```

Output is schema-constrained JSON: exactly one entry per input index, sentinels preserved.

**Rolling context carries the English forward**, not just the Japanese — that's what makes
character voice stay consistent across a scene instead of resetting every chunk.

Every response passes Stage 6 validation before it is written as `machine` status. Failures
retry **once on the resident model** with the validator's complaint, then **queue** — they
are drained by a batched Pass 3 on the larger `retry` model. Never swap models inline; see
"Never escalate inline" in `docs/04-llm.md`.

---

## Stage 6 — QA

Deterministic validators first (free), model judge only on what they flag (expensive).
Full rule list in `docs/05-qa.md`. Headline checks: placeholder integrity, residual
Japanese, glossary compliance, honorific consistency, speaker-voice drift, length budget,
duplicate-line divergence.

---

## Stage 7 — Fit

**In:** validated English. **Out:** English with engine line-break codes inserted, guaranteed
to fit the box.

Real glyph advances via SkiaSharp using **the game's own font at the game's own size**, and
the game's own textbox geometry. Break with the engine's break code, respecting no-break
rules. Lines that cannot fit even when broken go back to Stage 5 with a "tighten to N
characters" instruction rather than being clipped. Details: `docs/06-patching.md`.

---

## Stage 8 — Build

Reinject → repack → diff against pristine originals → emit a patch plus an installer that
backs up before writing. Hard rule 4: the artifact is a patch, never the game.

---

## Re-run semantics

| Changed | Recomputes |
|---|---|
| A glossary term | Only units whose source contains it, that aren't locked |
| A style policy | All non-locked units (prompt prefix changed) |
| One line, hand-edited | Nothing; the line locks |
| The bible cast | Units in scenes containing that character, non-locked |
| An adapter bug fix | Stage 2 re-extract; translations re-map by SourceHash |

Translations key off **SourceHash**, not file offset, so re-extracting after an adapter fix
does not lose work.
