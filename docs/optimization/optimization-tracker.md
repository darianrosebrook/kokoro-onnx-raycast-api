# Feature Verification Checklist — Kokoro TTS / Raycast Integration (One-Pager)

**Feature:** <!-- e.g., “Adaptive pre-buffer & sequence-tagged streaming” -->  
**Owner:** <!-- Name -->  
**Date:** <!-- YYYY-MM-DD -->  
**Branch/Tag:** <!-- repo ref -->  
**Environment:** macOS <!-- e.g., 14.6 --> · ORT <!-- e.g., 1.18.1 --> · Core ML Tools <!-- e.g., 7.x --> · HW: 64 GB M1 Max

---

## 1) Acceptance Criteria (Functional)
- [ ] Clear user story/intent documented. **Evidence:** <!-- link/note -->
- [ ] API behavior specified (inputs/outputs, error codes). **Evidence:**
- [ ] Backward compatibility preserved (no breaking changes under `/v1`). **Evidence:**
- [ ] UX behavior under Raycast (start/stop/interrupt) matches spec. **Evidence:**

## 2) Performance Gates (SLOs) — measure on device
> Record *p50/p95*; run 3 trials; list command(s) used.

- [ ] **TTFA (Time-to-First-Audio)** ≤ **0.50 s p95** (short text, ~140 chars).  
      Measured: p50 ____ s · p95 ____ s. **Evidence:**  
      Cmds: `scripts/run_bench.py --preset=short --stream`

- [ ] **RTF (Real-Time Factor)** ≤ **0.60 p95** (paragraph, ~5–8 sentences).  
      Measured: p50 ____ · p95 ____. **Evidence:**  
      Cmds: `scripts/run_bench.py --preset=long --stream`

- [ ] **Underruns** ≤ **1 per 10 min** playback (soak, 20 min).  
      Measured: ____ / 20 min. **Evidence:** logs `/status`

- [ ] **Stability drift** ≤ **5%** over 20-min soak (TTFA/RTF).  
      Drift: TTFA ____%; RTF ____%. **Evidence:**

- [ ] **Memory envelope (RSS)** within **±300 MB** steady-state (no leak).  
      Start ____ MB · End ____ MB. **Evidence:** Instruments/ps

## 3) Audio Quality Gates
- [ ] **Loudness & Peaks:** −16 LUFS target ±1 LU; dBTP ≤ −1.0 dB. **Evidence:** `tools/lufs_check.py`
- [ ] **Artifacts/Clicks:** 0 new glitches across 20 randomized clips. **Evidence:** listening notes
- [ ] **Objective score (if applicable):** PESQ/STOI not worse than baseline by >3%. **Evidence:**

## 4) Streaming Robustness
- [ ] **Sequencing:** monotonic chunk IDs; no out-of-order playback. **Evidence:** logs/trace
- [ ] **Pre-buffer policy:** 100–150 ms at start; adaptive thereafter. Verified. **Evidence:**
- [ ] **Reconnect/Resume:** WS/HTTP drop and resume within 1 s without replay. **Evidence:**
- [ ] **Chunk cadence:** 30–100 ms frames; jitter < 20 ms p95. **Evidence:**

## 5) Text Processing & Lexicon
- [ ] **G2P path:** Misaki warmed; fallback eSpeak works; cache hits logged. **Evidence:**
- [ ] **Sanitization:** control chars/newlines normalized. **Evidence:**
- [ ] **Lexicon overrides:** heteronyms/brands covered; regression tests updated. **Evidence:**

## 6) Security & Privacy (local API)
- [ ] Binds to `127.0.0.1` by default; CORS disabled unless allowlisted. **Evidence:**
- [ ] Limits: max chars/request, timeout, max concurrency. **Evidence:**
- [ ] Logs redact PII; debug gated behind env flag. **Evidence:**

## 7) API Contract & Compatibility
- [ ] `/v1/audio/speech` request/response documented; streaming format described. **Evidence:**
- [ ] Error schema versioned; clients unaffected (Raycast/OpenWebUI). **Evidence:**
- [ ] Semver bump + CHANGELOG entry. **Evidence:**

## 8) Observability & SLO Wiring
- [ ] `/status` exposes: TTFA, RTF, underruns, provider, cache stats. **Evidence:**
- [ ] Alert thresholds (local): warn if TTFA p95 > 0.5 s, RTF p95 > 0.6. **Evidence:**
- [ ] Perf CI job compares to golden bands; gate on >10% regress. **Evidence:**

## 9) Release Hygiene & Rollback
- [ ] Toolchain manifest updated (ORT/CoreML versions). **Evidence:**
- [ ] Repro seed/mode documented (fast/accurate math, denormals). **Evidence:**
- [ ] Rollback plan: env flag or version pin; tested. **Evidence:**

## 10) Docs & Ops
- [ ] README/Docs updated; flags and defaults documented. **Evidence:**
- [ ] Bench guide updated (commands, fixtures, expected bands). **Evidence:**
- [ ] Owner listed; next review date set. **Evidence:**

---

## 11) Next Priority Actions (P1)
Based on current implementation status analysis:

- [ ] **Deploy INT8 quantization:** Use ready scripts to quantize production model
  **Evidence:** `python scripts/quantize_model.py --input kokoro-v1.0.onnx --output kokoro-v1.0.int8.onnx --benchmark`
  
- [ ] **Apply ONNX graph optimizations:** Use optimization pipeline for model
  **Evidence:** `python scripts/optimization_pipeline.py --input models/ --stages graph_optimization,quantization`
  
- [ ] **Investigate provider selection:** Check why CPU provider selected over CoreML
  **Evidence:** Review `/status` endpoint CoreML availability and benchmark results
  
- [ ] **Session warming:** Implement pre-warmed inference sessions to reduce cold start
  **Evidence:** Measure TTFA improvement with warmed vs cold sessions
  
- [ ] **Audio pipeline optimization:** Reduce 700ms audio processing overhead
  **Evidence:** Profile audio conversion and streaming pipeline bottlenecks

## 12) Implementation Status
- **Current TTFA:** 2188ms (vs 800ms target)
- **Improvement needed:** 2.7x to reach target
- **Core systems:** ✅ Streaming, monitoring, session management working
- **Ready to deploy:** ⚠️ Quantization and graph optimization scripts
- **Next milestone:** Deploy P1 optimizations to achieve <1200ms TTFA

---

**Sign-off:**  
- [ ] Engineering  
- [ ] QA/Audio Review  
- [ ] Owner/Approver