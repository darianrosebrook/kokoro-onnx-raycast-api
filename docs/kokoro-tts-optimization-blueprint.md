# Kokoro TTS Optimization Blueprint for Apple Silicon (M1 Max)

**Author:** @darianrosebrook
**Status:** Working draft
**Scope:** Backend only (Kokoro ONNX → FastAPI). Raycast covered only as interface contract.
**Hardware target:** 64 GB M1 Max MacBook Pro
**Primary KPI:** Time‑to‑first‑audio (TTFA) and sustained real‑time factor (RTF)

---

## Executive Summary

This blueprint consolidates several review passes into one engineering plan to push Kokoro ONNX TTS toward **near‑instant** perceived response on Apple Silicon. The strategy layers optimizations across:

* **Model precision & graph engineering** (per‑channel INT8, selective FP16, QAT, ORT format, static shapes)
* **Apple Silicon execution** (Core ML EP, ANE vs CPU+GPU heuristics, MPS A/B, memory arena sizing)
* **Streaming pipeline design** (primer strategy, pre‑buffering, chunk cadence, sequence‑tagging, ring buffers, persistent playback daemon)
* **Text/G2P performance & robustness** (Misaki G2P, sanitation, fallback, ahead‑of‑time phonemization)
* **Scheduling & concurrency** (3‑stage lock‑free pipeline, dual sessions, QoS & thread affinity)
* **Continuous measurement & auto‑tuning** (bench harness, provider cache, Bayesian/heuristic tuning)

**Targets (M1 Max, single‑user, local):**

* **TTFA:** ≤ 300–500 ms for typical sentences; ≤ 150 ms for cache hits (primer micro‑cache).
* **RTF:** ≤ 0.5× (generate ≥ 2× faster than playback) sustained for article‑length inputs.
* **Stability:** No underruns; ≤ 5% degradation over 10+ minutes of continuous synthesis.

**Current Implementation Status (Dec 2024):**

* ✅ **Core streaming pipeline:** Fully implemented with 3.8x TTFA improvement (8371ms → 2188ms)
* ✅ **Dual session management:** DualSessionManager for ANE+GPU concurrent processing
* ✅ **Performance monitoring:** Comprehensive benchmark suite with HTTP endpoints
* ✅ **Production reliability:** Session leak fixes, error handling, fallback systems
* ⚠️ **Quantization ready:** Scripts implemented but models not quantized yet
* ❌ **Auto-tuning:** ML-based parameter optimization not implemented
* 📊 **Current TTFA:** 2188ms (target: 800ms) - 2.7x improvement still needed

---

# Table of Contents

1. [Goals & Constraints](#goals--constraints)
2. [Architecture Overview](#architecture-overview)
3. [Optimization Layers](#optimization-layers)

   1. [Quantization & Mixed Precision](#quantization--mixed-precision)
   2. [ONNX Graph & ORT Runtime](#onnx-graph--ort-runtime)
   3. [Apple Silicon Execution Strategy](#apple-silicon-execution-strategy)
   4. [Streaming & Playback Pipeline](#streaming--playback-pipeline)
   5. [Audio Quality & DSP Policy](#audio-quality--dsp-policy)
   6. [Text/G2P Path](#textg2p-path)

      1. [Prosody Control & SSML Subset](#prosody-control--ssml-subset)
      2. [Language, Code-Switching, and Lexicon Management](#language-code-switching-and-lexicon-management)
   7. [Scheduling, Concurrency & QoS](#scheduling-concurrency--qos)
   8. [Caching & Auto‑Tuning](#caching--auto-tuning)
4. [Observability & SLOs](#observability--slos)
5. [Benchmark Plan & Success Criteria](#benchmark-plan--success-criteria)
6. [Reliability & Fault Injection](#reliability--fault-injection)
7. [critical functiond Implementation Plan](#critical functiond-implementation-plan)
8. [Release & Reproducibility](#release--reproducibility)
9. [Interface Contract (Raycast/Clients)](#interface-contract-raycastclients)
10. [Appendix](#appendix)

    1. [Streaming Container & Format Policy](#streaming-container--format-policy)
    2. [Test Fixtures & Golden Samples](#test-fixtures--golden-samples)
    3. [Reference Config & Snippets](#reference-config--snippets)

---

## Goals & Constraints

* **Primary goal:** minimize *perceived* latency (TTFA) while preserving naturalness.
* **Quality bar:** avoid audible artifacts from over‑quantization; maintain prosody continuity across chunks.
* **Platform:** local, single‑user on a 64 GB M1 Max; design assumes **one active stream** (no need to mix multiple voices concurrently).
* **Compatibility:** OpenAI‑style `/v1/audio/speech` API; support both streaming and non‑streaming modes.
* **Reliability:** graceful fallbacks (provider, phonemizer, playback), robust to long texts.

---

## Architecture Overview

**Pipeline stages (single request):**

1. **Ingress & validation** → normalize language (`en → en‑us`), validate payload.
2. **Primer** (optional) → emit tiny header + \~50 ms silence; warm hot path.
3. **Text processing** → sanitation → segmentation → G2P (Misaki) → token seq.
4. **Inference** → Kokoro ONNX via ORT (Core ML EP preferred).
5. **Post‑processing** → splice segments, optional boundary cross‑fade.
6. **Egress** → chunked PCM/WAV streaming with sequence tags into a persistent audio daemon.

**Three queues (lock‑free):**

* **Q1:** text jobs (segmentation/G2P)
* **Q2:** inference jobs (provider‑bound)
* **Q3:** PCM frames to playback daemon

**Dual‑session option:** Session A (ANE/Core ML) for current chunk; Session B (CPU or GPU) precomputes next chunk.

---

## Optimization Layers

### Quantization & Mixed Precision

**Why:** reduce compute & bandwidth without audible degradation.

**Plan:**

* **Per‑channel INT8 (weights)** via ORT’s `quantize_static --per_channel` with calibration data covering typical English prose.
* **Hybrid precision:** keep vocoder/final post‑net layers at **FP16**, quantize encoders/intermediates to **INT8**.
* **QAT (optional):** brief fine‑tune pass simulating INT8 on sensitive blocks to recover fidelity lost to PTQ.
* **Layer exclusion list:** opt‑out layers empirically correlated with artifacts (maintain manifest).
* **Guardrails:** retain an **FP16 build** for A/B and as a quality fallback.

**Outputs:** `kokoro-v1.int8.onnx`, `kokoro-v1.int8fp16mix.onnx`, optional `.ort` variants.

---

### ONNX Graph & ORT Runtime

**Why:** fewer ops, static shapes, and precompiled ORT cut scheduling/launch overhead.

**Graph passes:** fold constants; fuse matmul+add; eliminate nop/transpose chains; remove dead branches; canonicalize shapes.
**Static binding:** prefer fixed max lengths for mel/frames; export `.ort` artifacts per common shape set.
**Runtime:**

* Convert **ONNX → ORT** offline; cache on disk; record metadata (ops count, input shapes).
* Tune **session options**: large memory arena (GB‑scale is fine on 64 GB), inter/intra‑op threads for CPU fallback.
* Maintain **A/B harness** to compare Core ML EP vs **MPS EP** for specific graphs; select per‑workload.

---

### Apple Silicon Execution Strategy

**Goal:** exploit ANE when it helps TTFA; prefer CPU+GPU when it sustains throughput on long streams.

**Core ML EP knobs (env or config):**

```bash
export KOKORO_COREML_MODEL_FORMAT=MLProgram
export KOKORO_COREML_COMPUTE_UNITS=ALL    # try: ALL vs CPUAndGPU
export KOKORO_COREML_SPECIALIZATION=FastPrediction
export KOKORO_MEMORY_ARENA_SIZE_MB=3072   # tune 2048–4096 on 64 GB
```

**Provider heuristic (rule‑of‑thumb):**

* **Short inputs (≤ 1–2 sentences):** `ALL` (engage ANE) → lower TTFA.
* **Long inputs (multi‑paragraph):** `CPUAndGPU` → fewer ANE context switches, steadier cadence.
* **Second session:** bind to CPU or GPU to precompute *next* chunk.

**Low‑level hints (optional):** use shared/unified buffers where possible; profile with Instruments; watch for hidden CPU fallbacks (unsupported ops) and refactor nodes to Core ML‑friendly forms.

---

### Streaming & Playback Pipeline

**Objectives:** near‑instant start, uninterrupted flow, deterministic ordering.

**Tactics:**

* **Immediate header & 50 ms silence** → flush client decoder.
* **Early primer strategy** → first 10–15% of text (≤ 700 chars) forced down fastest path; micro‑cache primer bytes by `(primer_text, voice, speed, lang)` for repeated phrases.
* **Chunk sizing** → 50–120 ms PCM per packet (tune by jitter profile).
* **Sequence‑tagging** → embed `chunk_id` & `segment_id`; playback reorders/holds until monotonic.
* **Pre‑buffer** → accumulate 2–3 chunks before play; shrink buffer adaptively once pipeline proves stable.
* **Boundary smoothing** → small overlap/cross‑fade at segment seams.
* **Persistent audio daemon** → long‑lived process with ring buffer; accepts PCM via WS/pipe; isolates playback timing from fetch jitter.
* **HTTP keep‑alive** → chunked transfer; periodic tiny‑silence if compute stalls; appropriate timeouts.

**Fallbacks:** if stream threatens underrun or IPC dies → swap to temp‑file + `afplay` for remainder; preserve UX continuity.

### Audio Quality & DSP Policy

**Purpose:** Maintain a consistent quality floor while optimizing for latency.

**Standards & processing**

* **Loudness target:** -16 LUFS integrated (speech) with -1 dBTP ceiling.
* **Sample format:** 24 kHz, mono, PCM 16‑bit for transport; synth in float32 then dither when down‑biting.
* **Dithering:** TPDF dither + optional noise shaping when converting float→int16.
* **Silence policy:** trim leading/trailing silence >100 ms; insert 80–120 ms inter‑segment pause for period/colon; shorter for comma.
* **Seam smoothing:** 5–20 ms cross‑fade at chunk boundaries.

**Quality validation**

* **Objective:** PESQ/STOI on a small fixture set; LUFS/dBTP compliance check per clip.
* **Subjective:** MOS ABX for FP16 vs INT8 vs mixed (10–20 listeners or your own panel).
* **Golden WAVs:** keep canonical outputs for regression diffs (perceptual hash + LUFS deltas).

---

### Text/G2P Path

**Objectives:** correctness without stalls; resilience to odd input.

**Steps:**

* **Sanitation** → normalize line breaks; collapse runs of newlines; strip control chars.
* **G2P** → Misaki primary; eSpeak/phonemizer fallback.
* **Ahead‑of‑time** for next segment while current audio renders.
* **Cache** phoneme results for repeated substrings; shard by language/voice.
* **Defensive wrapper** around phonemizer: exceptions → character‑level fallback; log offending spans.

#### Prosody Control & SSML Subset

* **Supported tags (subset):** `<break time="{ms}ms">`, `<say-as interpret-as="cardinal|ordinal|date|time">…</say-as>`, `<emphasis level="reduced|moderate|strong">…</emphasis>`, `<prosody rate="x%" pitch="+/-x%">…</prosody>`.
* **Boundary mapping:** punctuation → phrase breaks (period/colon = 120–180 ms; comma/semicolon = 60–100 ms); apply prosody continuity across segments.
* **Lexicon hooks:** per‑project and per‑user dictionaries for heteronyms and brand names; precedence: user > project > default.
* **Input negotiation:** `input_format: "text"|"ssml"`; reject unsupported SSML with actionable errors.

#### Language, Code-Switching, and Lexicon Management

* **Segment‑level LID:** detect language per segment; split on code‑switch boundaries.
* **Backend selection:** route to language‑appropriate G2P with warmup.
* **Lexicon schema:** TSV/CSV or JSON: `{lang, grapheme, phoneme, flags}`; reload on change with cache busting.
* **Pronunciation overrides:** client can pass a transient lexicon blob per request (bounded size) for rare names.

---

### Scheduling, Concurrency & QoS

**Three‑stage pipeline:**

1. **Text** (CPU threads) → 2) **Model** (ANE/GPU; backpressure aware) → 3) **Audio** (high‑priority playback thread).

**QoS/affinity:** mark playback with `QOS_CLASS_USER_INTERACTIVE`; bind to performance cores; keep GC off the hot path.
**Dual sessions:** ANE for “now”; CPU/GPU for “next”; throttle to avoid ANE oversubscription.
**Backpressure:** ring buffers expose fill‑levels; gating prevents starvation/overrun.

---

### Caching & Auto‑Tuning

* **Provider selection cache** (daily/weekly TTL); cold‑start benchmarks persisted.
* **ORT model/kernel cache** (first‑run compile only).
* **Primer micro‑cache** (immediate TTFA wins).
* **Memory watchdog** (periodic cleanup; fragmentation guard).
* **Auto‑tuning (optional)**: Bayesian search over chunk size, provider, thread counts; store (config → metrics) tuples and prefer Pareto‑optimal configs.

---

## Observability & SLOs

**SLOs (M1 Max, single user):** TTFA p95 ≤ 500 ms; RTF p95 ≤ 0.5×; underruns ≤ 0.5/hour; stream terminations = 0.
**Metrics emitted per request:** TTFA, RTF, provider path, chunk size, pre‑buffer depth, underruns, phonemizer time, GC time, CPU/GPU/ANE utilization snapshot.
**Endpoints & logs:** `/status` includes rolling p50/p95; structured logs (JSON) with correlation IDs.
**Alerts (local dev):** log warnings when SLO breached with suggested remediation (e.g., widen chunk size, switch provider).
**Perf CI:** nightly run on fixtures; fail if TTFA/RTF drift > +20% from baseline.

---

## Benchmark Plan & Success Criteria

> Measure *user‑visible* latency end‑to‑end, not just kernel timings.

**Core metrics**

* **TTFA:** request accepted → first audible sample delivered.
* **RTF:** synth time / audio duration.
* **Stability:** underruns/hour; stream terminations; variance of inter‑chunk arrival.
* **Quality:** ABX on quantized vs FP builds; artifact incidence at seams.

**Per‑optimization checks**

1. **INT8 (+mixed FP16)**

   * *Test:* fixed 5 s text; FP16 vs INT8 vs INT8+FP16.
   * *Expect:* 2–4× faster than FP16; no audible artifacts in blind ABX; identical prosody within tolerance.
2. **Graph/ORT format & static shapes**

   * *Test:* op count, scheduler time, cold vs warm start.
   * *Expect:* fewer ops; ≤ 50% cold‑start overhead after first run; stable warm starts.
3. **Provider heuristic (ALL vs CPUAndGPU)**

   * *Test:* 1‑sentence vs paragraph; measure TTFA & RTF.
   * *Expect:* `ALL` wins TTFA on short; `CPUAndGPU` steadier on long; dual session reduces seam gaps.
4. **Streaming pipeline**

   * *Test:* chunk sizes 30/50/80/120 ms; pre‑buffer 1–3 chunks.
   * *Expect:* no underruns; TTFA ≤ 300–500 ms; inter‑chunk jitter < 10 ms p95.
5. **G2P/Misaki**

   * *Test:* 1k‑char mixed punctuation; timing vs fallback; correctness regression set.
   * *Expect:* speedup over eSpeak path; zero crashes after sanitation; stable word/phoneme counts.
6. **Memory/stability**

   * *Test:* 15‑minute continuous read; report drift in RTF/TTFA; RSS envelope.
   * *Expect:* ≤ 5% drift; no growth beyond watchdog thresholds; 0 unexpected terminations.

**Acceptance (M1 Max):** TTFA ≤ 500 ms (typical); RTF ≤ 0.5×; no underruns under nominal load.

## Reliability & Fault Injection

**Faults to inject:**

* **Provider loss:** deny ANE; force CPU fallback.
* **Network/IPC:** drop 1 in 100 chunks; WS disconnect mid‑paragraph; delay bursts (200–400 ms).
* **G2P stalls:** simulate slow Misaki; trigger fallback; verify TTFA stays < 700 ms.
* **Memory pressure:** shrink arena; force cleanup; ensure continuity.

**Degrade modes matrix (goal → action):**

* **Avoid underrun:** increase pre‑buffer; enlarge chunk to 100–120 ms; lower sample rate (optional).
* **Reduce TTFA:** switch provider to `ALL` for primers; enable primer micro‑cache.
* **Stability first:** serialize segments; disable dual session; widen timeouts.

**Resume rules:** on reconnect, continue from next `chunk_id`; do not replay already‑played audio.

---

## critical functiond Implementation Plan

**Implementation Priority Matrix:**

| Priority | Category | Impact | Effort | Status |
|----------|----------|---------|--------|--------|
| P0 | Provider optimization | High | Low | ✅ Done |
| P0 | Session leak fixes | Critical | Low | ✅ Done |
| P1 | INT8 quantization | High | Medium | ⚠️ Ready |
| P1 | ONNX graph optimization | Medium | Low | ⚠️ Ready |
| P2 | Advanced caching | Medium | Medium | ❌ TODO |
| P2 | Auto-tuning | Medium | High | ❌ TODO |
| P3 | Custom Metal kernels | Low | High | ❌ R&D |

**Baseline & Instrumentation** ✅ **COMPLETED**

* ✅ Wire precise TTFA/RTF timers; log provider, chunk size, queue depths, underruns.
* ✅ Establish FP16 CPU/MPS baseline; save fixture texts & golden WAVs.

**Quick Wins** ✅ **MOSTLY COMPLETED**

* ⚠️ Enable **per‑channel INT8**; export `.ort`; set memory arena 2–4 GB. (Scripts ready)
* ✅ Primer header+silence; pre‑buffer 2 chunks; sequence‑tagged chunks.
* ✅ Sanitation + defensive G2P wrapper.

**Heuristics & Concurrency** ✅ **COMPLETED**

* ✅ Provider heuristic (ALL vs CPUAndGPU by input length).
* ✅ Dual session (ANE + CPU/GPU) with backpressure.
* ✅ Cross‑fade splice at seams; primer micro‑cache.

**Advanced** ⚠️ **PARTIALLY READY**

* ⚠️ Mixed‑precision layer allowlist; optional QAT on sensitive blocks. (Scripts ready)
* ❌ Auto‑tuner (Bayesian) for chunk size, provider, threads; Pareto store.
* ❌ MPS EP A/B; pick graph‑dependent winner.

**Experimental R\&D** ❌ **NOT STARTED**

* ❌ Structured pruning; student distillation; batched multi‑segment forward.
* ❌ MPSGraph custom kernels for hot ops; MLProgram JIT exploration.

Each critical function gates on the **Benchmark Plan** criteria before advancing.

## Release & Reproducibility

* **Pin toolchain:** ORT, Core ML converter, Python, OS build; capture in a **conversion manifest** alongside `.ort`.
* **Determinism:** control seeds where applicable; document math modes (fast vs accurate) per EP.
* **Upgrade playbook:** after macOS/Xcode updates, run smoke + rebenchmark; if drift > 10%, capture traces and freeze to previous EP/graph variant until remediated.

---

## Interface Contract (Raycast/Clients)

**Request (OpenAI‑style)**

```http
POST /v1/audio/speech
Content-Type: application/json
{
  "model": "kokoro-onnx-int8",
  "input": "Text to speak…",
  "voice": "<id>",
  "format": "wav",
  "language": "en-us",
  "speed": 1.0,
  "stream": true
}
```

**Streaming response**

* **Transport:** HTTP chunked (or WS).
* **Prelude:** WAV header + \~50 ms silence.
* **Payload:** sequence‑tagged PCM frames `{segment_id, chunk_id, bytes}`.
* **Keep‑alive:** continuous cadence; tiny‑silence if compute stalls.
* **Fallback:** if stream destabilizes, server switches to temp‑file + `afplay` and returns completion notice.

**Errors**

* 422 invalid payload; 429 (optional) if busy; 5xx with provider/phonemizer diagnostics.

---

## Security/Privacy & API Hardening

* **Bind** to `127.0.0.1` by default; optional allowlist; CORS disabled unless explicitly set.
* **Limits:** max chars/request, max concurrent jobs, request timeout; graceful 429.
* **Privacy:** redact PII from logs; optional ephemeral mode (no persistence).
* **API versioning:** `/v1` namespace; backward‑compatible error schema.

---

## Appendix

### Streaming Container & Format Policy

* **Transport default:** `audio/wav` with chunked transfer. Use RIFF header with placeholder sizes; many players accept unknown length during live streams. Finalize sizes on close when feasible.
* **Alternative:** raw PCM frames with out‑of‑band format metadata to the playback daemon.
* **Optional codecs:** Opus (48 kHz) for remote/low‑bandwidth clients; keep PCM for local low‑latency path.
* **Sample‑rate matrix:** default 24 kHz mono PCM16; allow 22.05/44.1/48 kHz on request with high‑quality resampling.

### Test Fixtures & Golden Samples

* **Edge corpus:** emoji, code/URLs, numbers (ordinals/cardinals), dates/times, mixed punctuation, long paragraphs, brand names/heteronyms.
* **Golden outputs:** FP16 and INT8 reference WAVs; perceptual hashes + LUFS per clip.
* **Code‑switch set:** en↔es, en↔ja with lexicon overrides.
* **Streaming chaos:** artificial chunk loss/reorder and reconnect scenarios.

### Reference Config & Snippets

```bash
# Core ML / ORT behavior
export KOKORO_COREML_MODEL_FORMAT=MLProgram
export KOKORO_COREML_COMPUTE_UNITS=ALL          # try CPUAndGPU for long text
export KOKORO_COREML_SPECIALIZATION=FastPrediction
export KOKORO_MEMORY_ARENA_SIZE_MB=3072
export KOKORO_VERBOSE_LOGS=0
```

```python
# Provider heuristic (pseudocode)
def choose_provider(text_len_chars: int) -> dict:
    if text_len_chars <= 280:       # ~1–2 sentences
        return {"ep": "coreml", "compute_units": "ALL"}
    else:
        return {"ep": "coreml", "compute_units": "CPUAndGPU"}
```

```python
# Text sanitation for G2P
import re

def sanitize_for_g2p(text: str) -> str:
    t = text.replace("
", "
").replace("
", "
")
    t = re.sub(r"
{2,}", "
", t)
    t = re.sub(r"[^ -~
]", "", t)
    return t.strip()
```

```python
# Streaming generator sketch (FastAPI)
from fastapi import Response
from typing import AsyncIterator

async def stream_wav(chunks: AsyncIterator[bytes]) -> Response:
    async def gen():
        yield wav_header()
        yield silence_50ms()
        async for frame in chunks:
            yield frame
    return StreamingResponse(gen(), media_type="audio/wav")
```

```python
# Dual session skeleton (concept)
class DualSession:
    def __init__(self, primary_coreml, secondary_cpu_or_gpu):
        self.primary = primary_coreml
        self.secondary = secondary_cpu_or_gpu

    def schedule(self, segments):
        pass
```

```python
# Cross-fade at segment seams (concept)
import numpy as np

def crossfade(a: np.ndarray, b: np.ndarray, ms: int, sr: int = 24000):
    n = int(sr * ms / 1000)
    fade = np.linspace(0, 1, n)
    a[-n:] = a[-n:] * (1 - fade)
    b[:n]  = b[:n] * fade
    return np.concatenate([a[:-n], a[-n:]+b[:n], b[n:]])
```

---

## Notes & Open Questions

* Track ops that silently fall back to CPU under Core ML EP; refactor if they impact hot path.
* Evaluate Misaki word/phoneme count alignment vs original tokenizer (correct earlier mismatch issue).
* Confirm Raycast sandbox timeouts for long streams; if any, segment requests transparently.

---

**End of Blueprint**
