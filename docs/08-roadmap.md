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
One engine (**Ren'Py** — text scripts, engine-native translation support, a day's work).
Unpack → extract → reinject. **No LLM code at all.**

- Python 3.12+ and `uv` environment; `pyright --strict` wired into CI (hard rule 9)
- Package skeleton per the planned layout
- `EngineAdapter` protocol + one implementation
- **Both round-trip gates** + CI: Gate A (identity) and Gate B (expansion)
- **Tier 0 synthetic fixtures** — hand-authored minimal scripts covering every control code
  the adapter claims to support. These are committable and unblock adapter work without any
  real game present (`docs/10-corpus.md`)
- Corpus manifest + harness (the manifest is committed; game files never are)

**Done when:** Gate A produces byte-identical files for every script, Gate B survives ~2×
expansion with the game still booting, and both run in CI against Tier 0. Hard rule 2.
Everything downstream is built on this being true; nothing else may start until it is.

---

### Phase 2 — Project store and read-only workbench
SQLite project file, `TextUnit` pydantic model, FastAPI host, bilingual table, filters, dedupe.

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

### Phase 7 — Engine families, then the Fukidashi bridge
Because there is no single target game, this phase *is* the product. Supporting fifteen
engines from one family proves less than one from each of four. Ladder, in this order —
each rung is chosen for what it teaches, not for coverage:

| # | Family | Representative | What it proves |
|---|---|---|---|
| 1 | Text script, loose files | Ren'Py *(Phase 1)* | The pipeline end to end |
| 2 | Archive + text script | KiriKiri | Container repack, SJIS/font handling, loose-file patching |
| 3 | **Compiled bytecode** | Majiro or BGI/Ethornell | **String-table rebuild and offset fixup — the real test** |
| 4 | Managed runtime | Unity | Injection via resource redirection |

Rung 3 is the one that matters. It's where a text-script-shaped abstraction breaks, and
where Gate B stops being theoretical. Get there sooner rather than later — discovering the
seam is wrong after four text-script engines is the expensive version.

Then image-baked text via the Fukidashi bridge.

**Done when:** each new family reaches Phase 6 quality **without changes outside its own
adapter folder** (hard rule 8). If that's not true, the abstraction was wrong and this is
where you find out cheaply.

---

## Sequencing notes

- **Phase 1 before everything.** The temptation is to start with the fun part (the model).
  Resist it. An LLM pipeline sitting on an unverified writer produces beautiful English that
  silently corrupts save files, and you will not find out for weeks.
- **Phases 2 and 3 are where the UX is won.** They're also the least glamorous.
- **The gold bench set (Phase 4) is worth a full day** and pays for itself the first time it
  saves a 20-hour run on the wrong model.
- **Phase 7 is a design test, not a feature.** Its real output is the answer to "is
  `EngineAdapter` the right seam?"
- **With no target game, breadth is the deliverable** — but breadth *within* a family is
  cheap incremental work, and breadth *across* families is where the risk lives. Order the
  ladder by risk, not by how many games each engine unlocks.
- **Tier 0 synthetic fixtures mean adapter development is never blocked** on finding a free
  game in that engine. Build the fixtures first for each new adapter; a real title is only
  needed for the integration test.
