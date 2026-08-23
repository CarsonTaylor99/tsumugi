# 06 — Fitting, fonts, and shipping the patch

The stage everyone underestimates. A perfect translation that clips at the textbox edge, or
renders in full-width monospace Latin, is not playable.

---

## The encoding problem

Most Japanese VN engines predate Unicode adoption and read **Shift-JIS**. Three consequences:

1. **Typographic characters may be unavailable.** Em dash, curly quotes, ellipsis variants —
   either absent or mapped to something else.
2. **Latin text may render full-width.** `Ｈｅｌｌｏ` instead of `Hello`. Technically legible,
   visually terrible, and it wrecks the character budget.
3. **Layout may be a fixed character grid.** Every glyph gets an identical cell because
   Japanese is uniform-width. English in a monospace grid is the single loudest visual tell
   of an amateur patch.

Options, best first:

| Approach | Quality | Cost |
|---|---|---|
| **Engine hook** — a proxy DLL that forces UTF-8 input and proportional font rendering (the VNTextProxy approach) | Best — real proportional English | Per-engine work, needs the game to load a DLL |
| **Font substitution** — replace the game's font with one whose Latin glyphs are properly proportioned, if the engine honours advances | Good | Depends entirely on the engine |
| **Glyph-table hack** — map English glyphs into unused SJIS codepoints | Workable, old-school | Fiddly, per-game, brittle |
| **Full-width Latin** | Playable, ugly | Nearly free |

`EngineTextCaps` records which applies. Decide it once per engine, at adapter time — Stage 7
must know the answer before it measures anything.

---

## Textbox geometry and calibration

You cannot fit text without knowing the box. Sources, in order of preference:
engine config files → known per-title values → **user calibration**.

**Calibration UX** (worth building properly — it's a two-minute step that makes everything
downstream exact): the user drops in a screenshot of the game's dialogue box, drags a
rectangle over the text area, and picks the font and size. The workbench renders live sample
English into that rectangle. What's stored is `{x, y, w, h, font, size, line_height,
max_lines}` — and now every length warning in the pipeline is a real pixel measurement rather
than a character-count guess.

---

## Measuring and reflowing

- Measure with **real glyph advances** (`fonttools` + `uharfbuzz`) using **the game's own
  font at the game's own size**. Character counts are a lie: `Wimbledon` and `illicit` are
  the same length and nowhere near the same width.
- Break greedily to the measured width, insert the **engine's** break code, respect
  `max_lines`. Never break inside a placeholder, a ruby span, or a style pair.
- Ruby raises effective line height — account for it or ruby lines clip vertically.

**Overflow escalation:**

1. Reflow within the box → done.
2. Exceeds `max_lines` → return to Stage 5 with `"tighten to ≤ N characters"` and the
   original source. A shorter rendering is nearly always available.
3. Still too long after two attempts → if the engine supports per-line font scaling, shrink
   one step.
4. Otherwise → flag for the human queue. **Never clip silently.**

Route long UI strings (buttons, menu items) through the same path with far tighter budgets —
a button that reads "Configuration" where the art fits "Config" is a visible defect.

---

## Injection

Per adapter, in descending order of preference:

1. **Engine-native translation support** (Ren'Py `tl/` trees). Nothing is modified; the
   engine loads the translation. Always use this when it exists.
2. **Loose-file override** (KiriKiri reads `data/` beside the `.xp3`). Clean, reversible,
   trivially uninstallable.
3. **Repacked archive.** Rebuild the container with modified scripts.
4. **Bytecode string-table rewrite.** Rebuild the string table and fix every offset that
   moved — and English strings are longer, so most of them move. This is where the
   round-trip identity test (hard rule 2) stops being a nicety and becomes the only thing
   between you and silent corruption.

---

## Shipping (hard rule 4)

**The artifact is a patch. It never contains game assets.**

- **Version pinning.** Hash the target files before applying. A different game build has
  different offsets; patching it produces corruption that will be blamed on the translation.
  Refuse, with a clear message naming the expected and found versions.
- **Binary diff** (HDiffPatch / xdelta3) for anything derived from an original file, so the
  distributed patch carries only the delta.
- **Loose files** for anything newly authored (translated scripts, fonts, the proxy DLL).
- **Installer** must: verify version → back up every file it will touch → apply → verify →
  offer uninstall that restores the backup exactly.
- **No feature** that uploads, hosts, mirrors, or shares game files. Not as a convenience,
  not behind a flag.

---

## Text baked into images

CG inserts, UI button art, title logos, chapter cards. Invisible to the script pipeline and
usually the last 5% that makes a patch feel finished.

This is not a new problem — **Fukidashi already solves it** (OCR → mask → inpaint →
retypeset). Phase 7 bridges to it: enumerate image assets, detect Japanese text regions, hand
them to Fukidashi's pipeline with the bible's glossary as context, receive translated images
back, and patch them like any other asset.

Until that bridge exists, image text stays Japanese and the build **reports** it — a count
and a contact sheet of affected assets — so it's a known gap rather than a surprise.
