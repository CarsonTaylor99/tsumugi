# 04 — Local LLM strategy

Target hardware for planning: **RTX 3090, 24 GB, clock-capped to 1800 MHz**, on a machine
with a documented history of GPU hangs and TDRs. Every number below assumes that box.

## Model tiering

`translate` runs tens of thousands of times. `bible.reduce` runs fifty times. They should not
be the same model.

| Task | Calls per game | Size guidance | Why |
|---|---|---|---|
| `bible.map` | ~500–800 | mid (12–14B) | Structured extraction; cheap and parallel |
| `bible.reduce` | ~50 | **largest that fits** | Judgement-heavy, runs once, quality compounds |
| `translate` | ~3,000 batched | **smallest that passes the bench** | 95% of total GPU time |
| `judge` | ~5–10% of lines | mid | Short outputs, only on flagged lines |
| `retry` | ~1–3% of lines | largest | The hard lines deserve the big model |

**Do not default `translate` to the 31B just because it's the loaded model.** The whole
tiering argument is that a 14B that passes the bench finishes in a third of the time, and the
saved hours buy retries and a judge pass — which usually beat raw model size.

### Picking `translate`: build a bench, don't guess

Before committing 20 hours, assemble a **gold bench set**: ~200 source units sampled across
narration, banter, emotional beats, keigo, dialect, and lines with heavy control codes, each
with a hand-approved English rendering. Run every candidate model against it and score:
placeholder survival rate, glossary compliance, pronoun accuracy, length ratio, and a
blind human preference pass over ~40 lines.

This is the same open question left on Fukidashi ("real-volume A/B vs gemma3"). Do it once
here, properly, and it settles the model question for both projects.

## Throughput — the number that decides the design

Planning estimate, stated assumptions, **not a promise**:

> 30,000 text units · ~35 output tokens/unit · batch of 10 units/call → 3,000 calls ·
> ~450 output tokens/call · volatile prefill ~1,400 tokens · stable prefix ~3,000 tokens.

| Configuration | Est. wall clock |
|---|---|
| 31B, batch 1, no prefix reuse | ~50 h ❌ |
| 31B, batch 10, prefix reuse | ~24 h |
| 14B, batch 1, no prefix reuse | ~21 h |
| 14B, batch 10, prefix reuse | ~9 h |
| 14B, batch 10, prefix reuse, dedupe, 2 parallel slots | **~4–5 h** ✅ |

Four multipliers, all of them engineering rather than hardware:

1. **Batching (~3×).** Per-call overhead and prefill amortise across 10 units. It also
   *improves* quality — the model sees a coherent run of dialogue instead of an orphan line.
   Ceiling: output-format fragility grows with batch size. 5–15 is the sweet spot; make it
   configurable and let QA failure rate pick the number.
2. **KV prefix reuse (~1.2–1.7×).** Covered below. Nearly free.
3. **Deduplication (~1.2×).** Stage 3 hashes source text; VNs repeat heavily across routes.
4. **Continuous batching / parallel slots (~1.5–2×).** llama.cpp's server with `-np 2..4`
   keeps the GPU fed. Costs KV cache VRAM per slot — budget it against the ladder below.

## Prompt architecture: stable prefix, volatile suffix

**Load-bearing.** Both llama.cpp's server and Ollama reuse the KV cache for a *shared prefix*
across requests. That only works if the prefix is byte-identical every time.

```
┌─ STABLE ────────────────────── cached across every call in the run
│  system role · style policy · honorific policy
│  golden few-shot examples · core cast card
├─ VOLATILE ──────────────────── re-prefilled each call
│  scene cast card · glossary entries matching this chunk
│  rolling context (previous units, source + approved English)
│  the chunk itself
└─────────────────────────────────────────────────────────────────
```

Rules that follow:
- Never interleave volatile content into the system block. One timestamp, one line counter,
  one "chunk 41 of 3000" in the prefix and the cache misses on **every call**.
- Order glossary entries deterministically (sort by term) so identical chunks hit the cache.
- The prefix changes when the bible or style changes — which is correct, and is exactly why
  a style edit invalidates all non-locked lines.

Context budget lands around 4–5k tokens per call. Modest — so favour a **bigger model at
moderate `num_ctx`** over a small model at 32k. Nothing here needs a huge window.

## Structured output: constrain the decoder

Do not ask for JSON and hope. Use **schema-constrained decoding** — llama.cpp GBNF grammars
or Ollama's JSON-schema `format` — so the model *cannot* emit a malformed batch or the wrong
number of entries.

```json
{"lines":[{"i":0,"en":"…"},{"i":1,"en":"…"}]}
```

Constrain: exactly N entries, `i` strictly increasing from 0, `en` non-empty. This removes an
entire class of retry and is the difference between a 3% and a 15% failure rate.

Still parse defensively — strip fences, tolerate whitespace. Constraints reduce failures;
they don't eliminate them.

## Runtime abstraction

`ILlmClient` over an **OpenAI-compatible HTTP endpoint**, so llama.cpp-server, Ollama, LM
Studio, and cloud providers are all one code path. Per-task bindings resolve at call time
(`{provider, model, params}`); no stage names a model.

Runtime-specific notes that have already cost time on this machine:
- **Ollama silently truncates** past its default context. Always pass an explicit `num_ctx`.
- **`num_ctx` is a ceiling, not an allocation.** Size it to *measured free VRAM* using the
  Fukidashi ladder (16384 / 12288 / 8192). Reuse that code; don't rewrite it.
- q8_0 KV cache + flash attention are the standing defaults on this box.
- Confirm prefix caching is actually working before trusting the throughput table — log
  prompt-eval token counts per call and watch them collapse after call 1. If they don't,
  something in the prefix is varying.

## Crash resilience (not optional here)

A 5-hour unattended run on this PC will sometimes be interrupted. Assume it.

- **Checkpoint every completed chunk** to SQLite, not at the end of a stage.
- **Resume is the default**, not a flag. Re-running the command continues.
- **Preflight gate** before a long run: free VRAM measured, endpoint reachable, model
  loaded, disk space, bible approved. Fail before hour 1, not during hour 14.
- **Watchdog on the endpoint.** If a request exceeds a generous timeout or the server dies,
  back off, reload the model, resume from the last checkpoint. Do not let one hung request
  waste a night.
- **Cap unattended run length** by default with a `--max-hours`, so an overnight run parks
  cleanly instead of hanging into the morning.

## Caching

Every call cached to disk keyed by `(unit_id, stage, provider, model, params_hash,
prompt_hash)`. Prompt iteration must never re-bill a completed run. The cache is also the
audit trail: any English line can be traced to the exact prompt and model that produced it.
