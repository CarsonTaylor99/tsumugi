# 00 — What Tsumugi is and why it's shaped this way

## The problem

A Japanese VN is 20,000–60,000 lines of text spread across a branching script graph, wrapped
in a proprietary archive, written in a proprietary scripting language, rendered into a fixed
pixel textbox by an engine that probably only speaks Shift-JIS. Existing options:

| Approach | What you get | Why it isn't enough |
|---|---|---|
| Official localization | Excellent | Doesn't exist for most titles |
| Fan TL patch | Excellent | Takes a team 1–3 years; most games never get one |
| Hooked live MTL (Textractor, LunaTranslator) | Instant, any game | Context-free, inconsistent, overflows the box, can't see menus or image text, adds latency to every line |
| Live LLM overlay (XUnity + local model) | Better prose | Same structural problems, plus seconds of wait per line |

Tsumugi targets the gap: **the quality shape of a patch, at the effort of running a tool.**

## The bet

Three things changed that make this viable now:

1. **Local models got good enough at JA→EN** that a 12–31B running on one consumer GPU
   produces prose a reader will accept, *if* it's given context and constrained properly.
2. **Time is free when it's offline.** A live translator has a 2-second budget per line. An
   offline one has 20 hours for the whole game. That is roughly a 10,000× compute budget
   per line, and it buys context windows, retries, validation, and a QA judge pass.
3. **The deterministic half is a solved problem in C#.** GARbro and VNTextPatch already
   encode years of format reverse-engineering, both in .NET.

## The shape that falls out

Everything hard splits cleanly into two buckets:

**Deterministic (C#) — must be exactly right, cheap to run.**
Archives, script parsing, control codes, reading-order graph, font metrics, line breaking,
reinjection, patching. These are correctness problems. A model here is a liability.

**Linguistic (LLM) — must be *good*, expensive to run.**
Who is this character and how do they speak, what does this invented term mean, what is this
line actually saying, does this English read like a person wrote it.

The pipeline is just that split, staged, with a validation gate between every model output
and the game files.

## What "best possible UX" means concretely

The stated priority. Decoded into requirements:

- **One flow, not a toolchain.** Point at a game folder. Engine is detected. Everything from
  unpack to installed patch is one progress view you can walk away from.
- **It survives the walk-away.** Resumable, checkpointed, pausable. A TDR at hour 14 costs
  minutes, not the run. (Non-negotiable on this machine specifically.)
- **Honest ETA.** Not a spinner. Lines done / total, current stage, measured throughput,
  time remaining — the same thing that made Fukidashi usable.
- **One decision point that actually matters.** The bible review. Everything else has a
  sane default; this one is worth the user's attention because it's irreversible in
  practice. Make that screen good and make it the *only* mandatory stop.
- **You can see it before you patch.** A font-accurate preview of the real textbox with the
  real English in it, so overflow is caught in the workbench, not on turn 9,000.
- **You can fix anything without re-running everything.** Edit a line, it locks, it never
  gets clobbered. Change a glossary term, only affected lines re-run.
- **It fails loudly and locally.** A line that can't be validated is flagged and left in
  Japanese with a marker — never silently mangled, never silently dropped.

## Scope boundary

Tsumugi translates **text the engine renders from a script**. Text baked into images (CG
inserts, UI button art, title logos) is a different problem — OCR, masking, inpainting,
retypesetting. That problem is already solved in **Fukidashi**. Phase 7 bridges to it rather
than rebuilding it. Until then, image text stays Japanese and is *reported*, not ignored.
