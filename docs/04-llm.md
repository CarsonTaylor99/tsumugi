# 04 — Local LLM strategy

Target hardware: **RTX 3090, nominally 24 GB, clock-capped to 1800 MHz**, on a machine with
a documented history of GPU hangs and TDRs.

> ⚠️ **The real budget is ~20.4 GB, not 24 GB.** Measured 2026-08-23: 3.9 GB is held at idle
> by Windows desktop compositing and GPU-accelerated Brave, invisible to `nvidia-smi` under
> WSL, and it moves with what's open. **Any guide that says "fits in 24 GB" probably does not
> fit here.** Freeing that 3.9 GB — disabling Brave's hardware acceleration, or closing it —
> is a real lever, not housekeeping: it decides whether the best available model fits.

Model landscape surveyed **2026-08-23**. Models move fast; re-survey before a big run and
treat the specific names below as a dated snapshot, not a standing truth. The *method* —
tiering, MoE preference, benching before committing — is the durable part.

## Prefer MoE for `translate`

The single most useful architectural fact for this workload: a **Mixture-of-Experts** model
holds all its weights in VRAM but only activates a fraction per token. You pay a large
model's *memory* cost and a small model's *speed* cost. For a job that is 3,000 sequential
generation calls, that trade is exactly the right way round.

Qwen's `A3B` line (≈3B active parameters) is the concrete example: **~50–65 tok/s on a 3090
at Q4_K_M**, versus ~18 tok/s for a dense 31B. Roughly 3× the throughput at comparable or
better quality.

This matters because it collapses the usual tiering dilemma. You do not have to choose
between "good" and "finishes overnight."

## What fits in ~20.4 GB

Weights at Q4_K_M plus KV cache at the ~12k context this pipeline actually needs (**not** the
32k figure most guides quote — our prompts land at 4–5k):

| Model | Type | Weights | + KV | Total | Fits? | ~tok/s |
|---|---|---|---|---|---|---|
| Qwen 3.6-35B-A3B | **MoE, 3B active** | ~20 GB | ~1.2 | **~21.2** | ⚠️ **needs ~1 GB freed** | **50–65** |
| Gemma 4 31B Heretic | dense | 18.7 | ~1.0 | ~19.7 | ✅ barely | ~18 |
| Qwen 3.8-27B | dense | ~17 | ~1.2 | ~18.2 | ✅ | ~22 |
| Qwen 3.6-27B | dense | ~16.5 | ~1.2 | ~17.7 | ✅ | ~22 |
| Qwen 3.6-14B | dense | ~9 | ~1.0 | ~10 | ✅ room for 4 slots | ~38–45 |
| Shisa V2.1 14B | dense, **JA/EN specialist** | ~9 | ~1.0 | ~10 | ✅ room for 4 slots | ~38–45 |
| Qwen 3.5-9B | dense | ~5.5 | ~0.8 | ~6.3 | ✅ co-resident | ~55–65 |

**The 35B-A3B is the prize and it misses by about a gigabyte.** That gigabyte is sitting in
Brave. Free it before concluding the model doesn't fit.

Quantization floor: **Q4_K_M is the minimum for Japanese** — quantization damages CJK more
than English. Do not drop to IQ3 to make something fit; drop a size class instead. Keep the
KV cache at q8_0; q4 KV shows up as drift over long contexts, which is precisely our failure
mode.

## The lineup

| Task | Calls | Pick | Why |
|---|---|---|---|
| `translate` | ~3,000 | **Qwen 3.6-35B-A3B abliterated** if VRAM is freed; else **Qwen 3.6-27B abliterated**, or **14B + 4 parallel slots** | 95% of GPU time. MoE gives ~35B quality at ~14B wall clock |
| `bible.map` | ~600 | **same model as `translate`** | Structured extraction. A different model here forces a swap for no gain |
| `bible.reduce` | ~50 | largest that fits alone | Judgement-heavy, runs once, quality compounds over the whole game |
| `judge` | ~5–10% | **9B abliterated**, co-resident if `translate` leaves room | Scoring, not generating. Co-residency buys live telemetry from hour 1 |
| `retry` | ~1–3% | largest that fits alone, **Pass 3 only** | Never inline — see below |

### Never escalate inline

Two large models cannot be resident at once in 20.4 GB, so inline escalation means an
unload/reload — ~120 model loads per run, and **each swap evicts the KV prefix cache**, which
destroys the prompt-caching win the throughput table below depends on. Run passes instead:

```
Pass 1   translate model resident   →  translate everything, QUEUE failures
Pass 2   same model, no swap        →  retry the queue with validator feedback
Pass 3   swap once to the big model →  drain remaining failures + judge
```

Two model loads instead of a hundred and twenty.

### Wall clock, 30k units

| Setup | Est. translate pass |
|---|---|
| Gemma 4 31B dense @ ~18 tok/s, 1 slot | **~17 h** |
| Qwen 3.6-27B dense @ ~22 tok/s, 2 slots | ~9 h |
| Qwen 3.6-14B @ ~40 tok/s, 4 slots | ~4.2 h |
| **Qwen 3.6-35B-A3B MoE @ ~57 tok/s, 1 slot** | **~5.3 h** |

Read the last two rows together: the MoE reaches roughly the same wall clock as a 14B running
four parallel slots, at a much higher quality ceiling. **That is quality for free**, and it is
the whole argument for spending an hour freeing VRAM.

## Abliteration

VN dialogue includes violence, sexual content, and adult themes. A model that refuses
mid-run does not error — it **silently bowdlerises**, inconsistently, and QA validator 7
(`docs/05-qa.md`) is the only thing that catches it. Treat an abliterated `translate` model
as a functional requirement, not a preference.

- Reported capability cost of abliteration is **~1–3%** versus a full finetune — small, but
  real, and worth measuring rather than assuming.
- Qwen 3.6 has abliterated and "heretic" builds for both the 27B dense and the 35B MoE.
- Qwen 3.8-27B (released 2026-08-14) is newer and scores substantially higher on general
  intelligence benchmarks, but community uncensored builds were still landing at the time of
  this survey. **Apply the same cooldown instinct as `npm min-release-age`**: a nine-day-old
  community abliteration is not battle-tested. Bench it, don't trust it.
- If the abliteration tax measures worse than expected, split it: run a **base** model for
  `translate` and route validator-7 refusals to an **abliterated** `retry` in Pass 3. You
  then pay the tax only on the lines that need it.

## Benching: use JP-TL-Bench, don't hand-roll

**JP-TL-Bench** (Shisa.AI, open source, with a paper) is purpose-built for exactly this
decision: reference-free **pairwise** JA↔EN comparison aggregated with a Bradley–Terry model,
covering dialogue with cultural references, literature, and long documents. It exists because
traditional metrics "bunch all the good models together" — which is the precise problem when
choosing between several models that are all *adequate*.

Use it as the primary screen, then add a **VN-specific supplement** it cannot cover:

- ~100 units from a real target script, weighted toward banter, keigo, dialect, and
  emotional beats
- lines carrying heavy control codes → measures **placeholder survival**, our hard gate
- lines with `enforce: true` glossary terms → measures glossary compliance
- deliberately spicy lines → measures refusal rate under abliteration
- length ratio distribution → feeds the Stage 7 fitting budget

One note from the JP-TL-Bench leaderboard worth carrying: **Qwen3-30B-A3B-Instruct scored the
top open-weight result (84.33% win rate), above a 405B JA-specialist finetune and above
GPT-4o.** That is a direct, task-relevant signal for the A3B MoE line on Japanese→English —
not a general-benchmark extrapolation.

Also worth benching, and easy to overlook: a **JA/EN specialist** like Shisa V2.1 14B. The
intuition that a Japanese-specialised model must be better is not safe — specialists are
often tuned for *producing* Japanese, while JA→EN needs Japanese comprehension **and**
natural English generation. Only the bench settles it.

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

---

## Sources for the 2026-08-23 model survey

Re-verify before acting on any specific model name — this is a dated snapshot.

- [JP-TL-Bench: Anchored Pairwise LLM Evaluation for Bidirectional Japanese–English Translation](https://blog.shisa.ai/posts/jp-tl-bench/) — the benchmark, leaderboard, and method ([paper](https://arxiv.org/abs/2601.00223), [code](https://github.com/shisa-ai/jp-tl-bench))
- [Shisa V2.1: Smaller, Smarter, More Accessible](https://blog.shisa.ai/posts/shisa-v2.1/) — JA/EN bilingual specialist lineup (1.2B / 3B / 8B / 14B / 70B)
- [Abliterated Models 2026: The Best Uncensored GGUFs by VRAM](https://locallyuncensored.com/blog/abliterated-models-guide.html) — abliteration capability cost (~1–3%), sizes by VRAM tier
- [Qwen 3.8 vs Qwen 3.6: What Actually Changed](https://locallyuncensored.com/blog/qwen-3-8-vs-qwen-3-6.html) — variant lineup, uncensored build availability
- [Qwen 3.6-35B-A3B Local Hardware Guide (2026)](https://www.compute-market.com/blog/qwen-3-6-local-hardware-guide-2026) — per-quant VRAM table and 3090 tok/s figures
- [Benchmarking Qwen 3.6 35B MoE (3B active) on an RTX 3090](https://www.gilesthomas.com/2026/07/benchmarking-qwen-3-6-35b-moe-rtx-3090) — independent 3090 throughput
- [Qwen3.8-27B: Specs, Benchmarks & Verdict](https://kingy.ai/blog/qwen3-8-27b-specs-benchmarks-local-hardware/) — 2026-08-14 release, Q4_K_M footprint
- [Best Open Source LLM for Japanese in 2026](https://www.siliconflow.com/articles/best-open-source-llm-for-japanese) — Q4_K_M as the quantization floor for Japanese
