# 03 — The story bible

The bible is what turns "a machine translated each line" into "someone translated this game."
It is also the only artifact the user is *required* to look at.

## What actually goes wrong without one

Concrete failure modes, all of which a bible prevents:

- **Pronoun roulette.** Japanese drops subjects constantly. English can't. A model guessing
  per line will call the same character "he" and "she" ten lines apart. This is the single
  loudest tell of machine translation.
- **Name drift.** 神楽坂 renders as Kagurazaka, Kagurasaka, and Kagura-zaka across one route.
- **Register collapse.** A character whose whole characterisation is 俺様 arrogance and
  another who speaks in stiff keigo both come out as flat neutral English.
- **Term drift.** An invented term is "grimoire," then "magic book," then "spellbook."
- **Address relationships lost.** In Japanese, *what A calls B* encodes the entire
  relationship, and it changes when the relationship changes. Untracked, it randomises.
- **Late-reveal spoilers.** A nametag that reads `???` for six hours gets translated with the
  character's real name because the model saw the whole script.

## Structure

Human-editable YAML, version-controlled, living beside the project DB. Split into files so a
50-character cast doesn't become one unreadable blob.

```
bible/
  style.yaml        one policy set for the whole project
  cast/*.yaml       one file per character
  glossary.yaml     terms, places, organisations, invented words
  relations.yaml    the address matrix
  scenes.yaml       scene → route, cast present, summary
  golden.yaml       hand-approved example translations (few-shot anchors)
```

See `schemas/` for annotated examples.

### style.yaml — decided once, applies everywhere

The decisions that are painful to change later:

- `honorifics`: keep / drop / selective — and if selective, the rule
- `name_order`: japanese (Family Given) / western
- `terms_of_address`: how 先輩 / お兄ちゃん / 先生 are handled when honorifics are dropped
- `quotes`, `ellipsis`, `dash` style
- `sfx_policy`: translate / romanise / leave
- `ruby_policy`: drop, or preserve as parenthetical when the reading is a *gimmick*
- `profanity_register`, `narration_tense`, `oxford_comma` — small, but consistency shows

### cast/*.yaml — the pronoun and voice card

```yaml
id: kagurazaka_himeko
name_ja: 神楽坂 姫子
reading: かぐらざか ひめこ
name_en: Himeko Kagurazaka
aliases_ja: [姫子, 姫, 神楽坂さん, "???"]     # "???" = pre-reveal nametag
pronouns: she/her
first_person: わたし                          # drives English register
register: polite, warm, deflects with humour
verbal_tics: ["trails off when embarrassed"]
speech_notes: >
  Never swears. Uses ~ですね softeners constantly — render as hedges
  ("I think", "maybe"), not as dropped politeness.
spoiler_gate: scene_id_where_name_is_revealed
voice_prefix: [HMK]                            # from Stage 3 voice-file clustering
```

`first_person` and `register` are doing the real work: they're what the translate prompt
uses to keep a character sounding like themselves.

### relations.yaml — the address matrix

```yaml
kagurazaka_himeko:
  protagonist:   { ja: "先輩", en: "senpai",  after: confession -> { ja: "名前呼び", en: "first name" } }
  akiyama_rei:   { ja: "レイちゃん", en: "Rei-chan" }
```

Directional and stateful. This is the highest-value/lowest-cost thing in the bible and
almost no tool tracks it.

### glossary.yaml — enforced, not suggested

```yaml
- ja: 魔導書
  en: grimoire
  kind: item
  enforce: true         # QA fails the line if the term is missing
  notes: never "magic book"
- ja: 白鷺学園
  en: Shirasagi Academy
  kind: place
  enforce: true
- ja: ルミナ
  en: Lumina
  kind: name
  do_not_translate: true
```

`enforce: true` means Stage 6 mechanically verifies it. A glossary that only exists in the
prompt is a suggestion; this one is a gate.

## How it's built (Stage 4)

Three passes, because a 3 MB script does not fit in any local context window.

**Pass A — deterministic (Stage 3, already done, free).** Speaker frequencies, voice-prefix
clusters, proper-noun candidates by morphology + frequency, scene segmentation, the choice
graph. This gives the LLM a *scaffold* instead of a blank page, and it's exact where the LLM
would be approximate.

**Pass B — map (LLM, per scene).** For each scene: who spoke, how they spoke, what they
called each other, which new terms appeared, what the tone was. Schema-constrained JSON.
Cheap per call, many calls, parallel-safe, fully resumable.

**Pass C — reduce (LLM, few calls, big model).** Merge observations per character and per
term. Where scenes disagree — a character's register changes, a name is rendered two ways —
**do not silently pick.** Emit a conflict for the human.

## The approval gate (hard rule 5)

Stage 5 will not start against an unapproved bible. The workbench presents:

1. **Conflicts first** — the reduce pass's disagreements, each with the evidence lines.
2. **Names** — every proposed English rendering, with frequency and first-appearance
   context. This is where 10 minutes of attention saves a re-run of the entire game.
3. **Pronouns** — flagged loudly for any character the model was unsure about.
4. **Style policy** — the honorific decision, stated plainly, with a rendered before/after
   sample so it's a real choice and not a form field.
5. **Golden lines** — pick ~10 lines, see three candidate translations each, approve one.
   Those become the few-shot anchors in every subsequent prompt. This is the highest-leverage
   ten minutes in the tool: it's how the user's taste gets into 30,000 lines.

The bible stays editable afterward. Editing it re-queues only the affected non-locked lines.

## Spoiler scoping

Every bible entry carries an optional `spoiler_gate` (a scene id). When assembling a
translate prompt, entries gated after the current scene are **withheld** — the model
translating hour 2 does not know the hour-30 reveal, which is both safer and closer to how a
human translator working in order would handle it. The user-facing bible view has the same
toggle, so reviewing it doesn't spoil the game they haven't played.
