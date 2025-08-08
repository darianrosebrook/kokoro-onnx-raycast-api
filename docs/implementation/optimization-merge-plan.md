# Optimization Merge Plan
> Author: @darianrosebrook  
> Status: In progress

## Goal
Unify work between `feature/audio-daemon-integration` and `optimization-implementation` to deliver near‑instant TTS with a stable streaming pipeline, simplified yet reliable text processing, Misaki G2P integration, and consistent performance telemetry.

## Updates
- Virtualenv configured (`.venv`) and dependencies installed; tests run in isolated env.
- Targeted tests executed and passing: long text, washing-instructions, Misaki integration (wrapper path). Upstream Misaki direct call error handled by wrapper fallback.
- Log noise reduced in `api/tts/misaki_processing.py`; verbose warnings gated behind `KOKORO_VERBOSE_LOGS=true`.

## Branch Diff Summary
- **Shared modified files**: `.kokoro-root`, `api/config.py`, `api/performance/stats.py`, `api/tts/core.py`, `api/tts/misaki_processing.py`, `api/tts/text_processing.py`, `raycast/src/utils/tts/streaming/audio-playback-daemon.ts`, `start_development.sh`.
- **Optimization branch adds**: `docs/implementation/*` (phoneme truncation, line-break fix, Misaki fixes, TTFA results), multiple `scripts/*` for testing/validation.
- **Audio-daemon branch adds**: full modular package at `api/tts/text_processing/**` (normalization pipeline, types, base classes). The optimization branch removes this package in favor of a consolidated `api/tts/text_processing.py`.

### Key Conflicts/Overlaps
- **Text Processing**
  - Branch A (optimization): single-file `api/tts/text_processing.py` with focused fixes (line-break handling, phoneme truncation) and performance simplifications.
  - Branch B (audio-daemon): modular `api/tts/text_processing/**` normalization pipeline (abbreviation/number/text), types, and pipeline orchestration.
- **Misaki G2P**: both modify `api/tts/misaki_processing.py`; need a unified integration path and tests.
- **Core synthesis**: `api/tts/core.py` has divergent streaming and sequencing adjustments.
- **Telemetry**: `api/performance/stats.py` expanded vs trimmed metrics; align exported fields and `/status` expectations.
- **Raycast audio daemon**: both touch `raycast/src/utils/tts/streaming/audio-playback-daemon.ts`; ensure protocol and timing compatibility.

## Decisions (proposed)
1. Text Processing Architecture
   - Prefer the simpler, performant `api/tts/text_processing.py` as the execution path to minimize overhead.
   - Selectively port high‑value rules from the modular pipeline (number and abbreviation handling) into the simplified path behind fast regex/rule toggles.
   - Retain the modular package in a `legacy/` or `experimental/` folder only if specific locales require it; otherwise remove to reduce maintenance. (Removed)

2. Misaki Integration
   - Keep Misaki as primary G2P with robust fallbacks (text passthrough) and safe defaults.
   - Adopt the fixes from optimization branch (line breaks, truncation guards) and preserve any accuracy tweaks from audio‑daemon branch.

3. Streaming & Sequencing
   - Align server streaming behavior with Raycast audio daemon expectations (chunk size, headers, ordering).
   - Ensure first‑chunk latency targets (<500 ms) and stable sequential assembly across segments.

4. Telemetry & Status
   - Consolidate `api/performance/stats.py` to a single schema and update `/status` accordingly. Keep minimal, actionable metrics (provider, TTFA, RTF, memory cleanup counters, fallback counts).

5. Tooling & Docs
   - Keep the optimization scripts (`scripts/*`) and formalize them as validation gates in development docs.
   - Preserve the docs added in optimization branch and add a consolidated benchmark report after merge.

## Implementation Checklist
### Phase 0 — Prep
- [x] Create integration branch: `merge/optimization-audio-daemon`
- [x] Export diffs to `docs/implementation/branch-diff-optimization-vs-audio-daemon.md`
- [x] Setup venv and install deps

### Phase 1 — Text Processing
- [x] Remove modular `api/tts/text_processing/**` and keep simplified path
- [ ] Port essential normalization (numbers/abbrev) behind fast guards (if needed)
- [x] Add/Run tests: line breaks, long paragraphs, truncation edge cases

### Phase 2 — Misaki G2P
- [x] Reconcile changes in `api/tts/misaki_processing.py` (thread-safe init, robust None handling)
- [x] Implement safe defaults, fallbacks, and log demotion; `KOKORO_VERBOSE_LOGS` toggle
- [x] Validate with scripts: `test_misaki_*`, `verify_washing_fix.py`, long text tests

### Phase 3 — Core & Streaming
- [ ] Validate `/v1/audio/speech` streaming end-to-end (TTFA, chunking, ordering)
- [ ] Align with Raycast daemon (`raycast/src/utils/tts/streaming/audio-playback-daemon.ts` contract)

### Phase 4 — Telemetry
- [ ] Unify `api/performance/stats.py` schema and `/status` outputs
- [ ] Add counters for fallbacks, provider selection, cleanup cycles (verify)

### Phase 5 — Docs & Benchmarks
- [ ] Update `docs/comprehensive-optimization-plan-for-kokoro-backend.md` with final architecture choices
- [ ] Add new benchmark run (TTFA, RTF, provider comparison) and attach to `docs/implementation/ttfa-optimization-results.md`
- [ ] Summarize merge outcomes and deprecations in `docs/production-patches.md`

## References
- Branches: `origin/feature/audio-daemon-integration`, `optimization-implementation`
- Key files: `api/tts/core.py`, `api/tts/misaki_processing.py`, `api/tts/text_processing.py`, `api/performance/stats.py`, `raycast/src/utils/tts/streaming/audio-playback-daemon.ts`
- Context: `docs/full-chat-convo-on-optimization.md`, `docs/comprehensive-optimization-plan-for-kokoro-backend.md`


