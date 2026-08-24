# 11 — Phase 1/2 implementation notes

Written alongside the first code drop (`phase1-walking-skeleton` branch). Records the
design calls that the Phase 0 docs left open, so they can be reviewed rather than
rediscovered. Numbers 1–4 below were raised as review findings against the Phase 0 docs;
each has either a resolution in code or a note for later phases.

## 1. Gate A for Ren'Py — the resolution

The Phase 1 criterion says "Gate A produces byte-identical files," but docs/02 says Ren'Py
injection should use the engine's `tl/` framework — under which originals are never
modified, so there is nothing to byte-compare. And `.rpyc` decompile→recompile is not
byte-stable, so identity over compiled scripts is unachievable.

**Resolution implemented:** the Ren'Py adapter extracts from `.rpy` source and injects by
**exact span rewrite** of the string literals. To keep Gate A honest (not "passes because
nothing moved"):

- extraction asserts, per literal, that `canonical_escape(unescape(raw)) == raw` — a
  literal that fails is **skipped loudly**, never guessed at;
- masking asserts losslessness (balanced markup, no sentinel glyphs in source) with the
  same skip-loudly rule;
- inject therefore re-encodes every literal through the full unmask→escape path, and Gate A
  genuinely exercises the writer.

The `tl/` framework remains the intended **production** injection path (docs/06 preference
order is unchanged); span rewrite is what proves the generic round-trip machinery that
every later text-script adapter reuses, and is itself a legitimate patch path for games
shipping `.rpy` source. Both gates run over Tier 0 in CI. "The game still boots" remains a
manual, dated result per docs/10 — it needs a Ren'Py runtime, which CI doesn't have.

## 2. Rolling context vs. parallel slots (Stage 5, noted for Phase 4)

Stage 5's rolling context makes chunk N+1 depend on chunk N's output, which conflicts with
the parallel-slots throughput multiplier in docs/04 if applied naively. Note for Phase 4:
**parallelism is across scenes/routes; translation is sequential within a scene.** The
scene segmentation from Stage 3 is what makes this well-defined.

## 3. Dedupe threshold (Stage 3, noted for Phase 2/4)

"Duplicates translate once" is unsafe for short context-dependent lines (「うん」 →
"Yeah." / "Mm-hm." / "…Okay."). Note for Stage 3: share translations only above a length
threshold (suggest ≥ 10 characters, configurable), or dedupe keyed on
`(source_hash, speaker)`. Validator 11 only warns on divergence; nothing catches forced
*convergence*, so the threshold is the defence.

## 4. Semantic linebreaks (Stage 2/7)

docs/05 strips `linebreak` codes unconditionally. Some scripts use manual breaks
semantically (poems, letters, formatted text). `TextUnit.preserve_breaks` exists as of this
drop; Stage 7 must respect it. Ren'Py needs no stripping (proportional UTF-8, engine
reflows), so the field is dormant until the KiriKiri adapter.

## Phase 1 scope: what the Ren'Py adapter does NOT yet do

Recorded so nobody mistakes the skeleton for coverage:

- **Double-quoted, single-line strings only.** No `'…'`, no `"""…"""`, no monologue mode.
- **No `.rpa` unpacking and no `.rpyc`** — loose `.rpy` source only (the SDK demo and Tier 0
  fixtures satisfy this). `.rpa` is Stage 1 work; `.rpyc` extraction may never be needed if
  `unrpyc` output is treated as source.
- **No `voice`-statement pairing** (Stage 3 concern), no `label`/scene segmentation.
- `tl/` directories are skipped on extract, so an already-translated game isn't re-extracted.

## Phase 2: project store + read-only workbench

- `tsumugi/core/store.py` — one SQLite file per game. The units-table DDL is
  **generated from the TextUnit pydantic model** (the schema-first lever); only
  store-side columns (`status`) are declared by hand. Duplicate counts come from a
  `source_hash` group join, so the workbench shows ×N badges with no extra pass.
- `tsumugi/studio/` — FastAPI host + a single-file, dependency-free workbench page
  (offline tool: no webfonts, no CDN). Bilingual table, filters (file / speaker /
  kind / free-text / duplicates-only), stats header, pagination.
- Phase 2 is read-only, so `replace_units` is a full swap; hard rule 6 (locked
  lines survive re-runs) becomes binding when writes land in Phase 4 — the
  `status` column is already there for it.
- The roadmap's Phase 2 criterion says "reading order"; true reading order is the
  Stage 3 graph (Phase 3). Until then the table is file/ordinal order.

## KiriKiri adapter (family 2: archive + text script)

Second adapter, driven by a real Tier 3 target (encrypted KiriKiriZ title, XP3 v2).

- **`tsumugi/archives/xp3.py`** — clean-room XP3 reader: index parse for any
  archive, extraction for unencrypted ones. Commercial titles set the protect
  flag (per-title cxdec cipher); those are *reported with a workflow*, never
  guessed at. Writing (patch2.xp3) is Phase 6; revisit `construct` then.
- **Encrypted-title workflow** (hard rule 7 keeps Tsumugi from writing into the
  game dir, so the one-time dump is a user step): KirikiriTools' version.dll
  (arcusmaximus — already our docs/02 vendor) dumps decrypted files as the
  engine loads them; for `.scn`-based (KAGEnvPlayer) titles,
  `tsumugi krkr-dump-script` prints the appconfig.tjs that force-loads every
  scene so one run dumps everything. `tsumugi unpack` prints all of this when
  it meets a protected archive.
- **`.ks` (KAG) parsing** — line-start grammar (`;` comment, `*` label, `@`
  command, else text), 【名前】/【名前/表示名】 speaker prefixes,
  `[iscript]…[endscript]` skipped, quoted attribute values honored in tag
  scanning, `[[` literal brackets. Per-file encoding (cp932 / UTF-16LE / UTF-8)
  is detected and verified to re-encode byte-identically before extraction;
  Tier 0 commits one cp932 and one UTF-16LE fixture so both stay proven in CI.
- **Linebreak reconciliation (docs/05 vs Gate A):** `[r]` is masked with kind
  `linebreak` and *kept* in the unit — if Stage 2 stripped it, identity could
  never round-trip. The docs/05 "model never sees linebreaks" rule moves to
  Stage 5 prompt assembly, which drops linebreak-kind sentinels on the way to
  the model and Stage 7 re-derives them. Extraction stays lossless.
- **`.scn` caveat:** KAGEnvPlayer-era titles compile scenarios to PSB `.scn`
  binaries instead of (or alongside) `.ks`. The adapter currently handles `.ks`
  only; if a dump yields `.scn`, that is a separate parser (FreeMote/PSB prior
  art) — scoped when a real dump shows it's needed.

## Running it

```
uv sync --group dev
uv run pytest                             # gates + parser + store + API tests
uv run pyright                            # strict, hard rule 9
uv run tsumugi probe   tests/fixtures/renpy_tier0
uv run tsumugi gates   tests/fixtures/renpy_tier0
uv run tsumugi extract <renpy-game-dir> --project game.tsumugi
uv run tsumugi serve   game.tsumugi       # workbench on http://127.0.0.1:8788
```
