# Dual Session Timeout Tuning

> Author: @darianrosebrook  
> Status: Completed

## Goal
Reduce end-to-end request timeouts by preventing long waits on hardware session locks (ANE/GPU) and ensuring rapid fallback to CPU when concurrency is saturated.

## Summary of Changes
- Lowered `max_concurrent_segments` from 4 to 2 to reduce queue thrashing and long waits.
- Reworked `DualSessionManager.get_optimal_session()` to:
  - Attempt immediate, non-blocking lock acquisition in priority order.
  - Use short per-session wait budgets (ANE=2.0s, GPU=2.0s, CPU=0.75s) instead of a single 30s wait.
  - Include CPU as an explicit final fallback in the try order.
  - Fail-fast with a concise error after budgets are exhausted so upstream can fall back to single-model processing.

## Files Updated
- `api/model/loader.py`
  - `DualSessionManager.max_concurrent_segments` → 2
  - `DualSessionManager.get_optimal_session()` → immediate attempts + short budgets + CPU fallback

## Rationale
- Previous behavior could wait up to 30s for a preferred session, causing request timeouts and poor streaming efficiency.
- Short budgets plus CPU fallback ensure forward progress under load and quicker recovery if ANE/GPU are briefly saturated.

## How to Verify
1. Start the server: `./start_development.sh`
2. Confirm status shows reduced concurrency:
   - `GET /status` → `max_concurrent_segments: 2`
3. Exercise streaming:
   - `POST /v1/audio/speech` with body `{ "text": "Hello world", "voice": "bm_fable", "speed": 1.2, "stream": true, "format": "pcm" }`
   - Expect 200 with chunked audio; no long waits.

## Notes
- If sustained load requires more throughput, revisit `max_concurrent_segments` and budgets after observing real metrics.
- Upstream `_generate_audio_segment()` already falls back to single-model processing when dual-session selection fails; the fail-fast strategy leverages that path.


