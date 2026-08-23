# 08 — Roadmap

Phases are sequential. Each has an acceptance criterion that is a **demonstrable fact**, not
a feeling. Do not start a phase before the previous one's criterion is met.

---

### Phase 0 — Groundwork ✅
Repo, CLAUDE.md, design docs, decisions recorded.

**Done when:** this repo exists and the open questions in `docs/09-decisions.md` are either
answered or explicitly deferred.

---

### Phase 1 — Walking skeleton
One engine. Unpack → extract → reinject. **No LLM code at all.**

- .NET SDK installed (currently missing — see `CLAUDE.md`)
- Solution skeleton per the planned layout
- `IEngineAdapter` + one implementation
- Round-trip identity test harness + CI

**Done when:** for every script in a real game, extract→reinject-unchanged produces a
**byte-identical** file, and the rebuilt game **boots and plays**. Hard rule 2. Everything
downstream is built on this being true; nothing else may start until it is.

---

### Phase 2 — Project store and read-only workbench
SQLite project file, `TextUnit` model, ASP.NET host, bilingual table, filters, dedupe.

**Done when:** you can open a real game and browse all its text in reading order, with
speakers attributed and duplicate counts shown.

---

### Phase 3 — Analysis and bible
Control-flow graph, scene segmentation, voice→speaker clustering, morphology term mining,
then bible map/reduce, the bible editor, and the approval gate.

**Done when:** a real game yields a draft bible whose cast, pronouns, and top 50 glossary
terms are *mostly right*, and the user can review and approve it in under 30 minutes.

---

### Phase 4 — Translation
`ILlmClient`, per-task bindings, chunked context windows, schema-constrained decoding,
placeholder validation, escalation, caching, checkpoint/resume, the gold bench set.

**Done when:** a full game translates end to end unattended, survives at least one forced
interruption with a clean resume, and finishes with a validator failure rate under 2%.

---

### Phase 5 — Fit and preview
Font metrics, textbox calibration, reflow, encoding/font handling, in-situ preview, the
review queue.

**Done when:** zero silently-clipped lines in a full pass, and the workbench preview matches
what the game actually renders.

---

### Phase 6 — Patch build and installer
Reinjection at scale, repack, binary diff, version pinning, backup, install, uninstall.

**Done when:** a patch installs onto a clean install of the game, the game is playable in
English start to finish, and uninstall restores the original byte-for-byte.

---

### Phase 7 — Second adapter and the Fukidashi bridge
A second engine — ideally one from a different family (text-script vs bytecode) — to prove
the abstraction is real rather than one engine wearing an interface. Then image-baked text
via Fukidashi.

**Done when:** the second engine reaches Phase 6 quality **without changes outside its own
adapter folder**. If that's not true, the abstraction was wrong and this is when you find
out cheaply.

---

## Sequencing notes

- **Phase 1 before everything.** The temptation is to start with the fun part (the model).
  Resist it. An LLM pipeline sitting on an unverified writer produces beautiful English that
  silently corrupts save files, and you will not find out for weeks.
- **Phases 2 and 3 are where the UX is won.** They're also the least glamorous.
- **The gold bench set (Phase 4) is worth a full day** and pays for itself the first time it
  saves a 20-hour run on the wrong model.
- **Phase 7 is a design test, not a feature.** Its real output is the answer to "is
  `IEngineAdapter` the right seam?"
