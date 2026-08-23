# Tsumugi (紡ぎ)

Offline visual-novel translation toolchain. Point it at an installed Japanese VN; get a
playable English patch.

**Status: Phase 0 — design only. No code yet.**

Deterministic work (archive unpacking, script parsing, text reinsertion, font metrics, patch
building) is **Python**. The language work (story bible, translation, QA) runs on **local LLMs**.

It's a **generic** tool — engine support is a plug-in surface, not a hardcoded target.

## Why not a real-time translator

Hooked live MTL has no context, no consistency, no line fitting, adds latency to every line,
and can't see menus, choice buttons, or text baked into images. Tsumugi does the model work
**once, offline, with the whole script available**, gates it behind QA, and ships a patch. At
play time there is no model in the loop — the game is just in English.

## Pipeline

```
detect → unpack → extract → analyse → bible → [YOU REVIEW] → translate → QA → fit → patch
  py       py        py        py       LLM                      LLM      py+LLM  py    py
```

## Docs

| | |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Operating rules, stack, hard gates |
| [`docs/00-overview.md`](docs/00-overview.md) | What this is and why it's shaped this way |
| [`docs/01-pipeline.md`](docs/01-pipeline.md) | The nine stages in detail |
| [`docs/02-engines.md`](docs/02-engines.md) | Engine landscape, adapter contract, prior art |
| [`docs/03-bible.md`](docs/03-bible.md) | Story bible schema and how it's built |
| [`docs/04-llm.md`](docs/04-llm.md) | Local model strategy, tiering, throughput math |
| [`docs/05-qa.md`](docs/05-qa.md) | Placeholder contract and validators |
| [`docs/06-patching.md`](docs/06-patching.md) | Fonts, encoding, line fitting, shipping |
| [`docs/07-ux.md`](docs/07-ux.md) | The workbench and the run experience |
| [`docs/08-roadmap.md`](docs/08-roadmap.md) | Phases and acceptance criteria |
| [`docs/09-decisions.md`](docs/09-decisions.md) | Decisions made, questions open |
| [`docs/10-corpus.md`](docs/10-corpus.md) | Test corpus tiers and the two round-trip gates |

## Scope

Personal-use fan-translation tooling. It produces **patches**, never redistributable game
assets, and has no upload, hosting, or sharing features by design.
