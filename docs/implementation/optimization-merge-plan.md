# Optimization Merge Plan
> Author: @darianrosebrook  
> Status: In progress - MPS provider integration completed

## Goal
Unify work between `feature/audio-daemon-integration` and `optimization-implementation` to deliver near‑instant TTS with a stable streaming pipeline, simplified yet reliable text processing, Misaki G2P integration, and consistent performance telemetry.

## Updates
- Virtualenv configured (`.venv`) and dependencies installed; tests run in isolated env.
- Targeted tests executed and passing: long text, washing-instructions, Misaki integration (wrapper path). Upstream Misaki direct call error handled by wrapper fallback.
- Log noise reduced in `api/tts/misaki_processing.py`; verbose warnings gated behind `KOKORO_VERBOSE_LOGS=true`.
- **COMPLETED**: Fixed duplicate `get_performance_stats` functions in `api/performance/stats.py`
- **COMPLETED**: Wired ORT optimization path into all session types (ANE, GPU, CPU, MPS) in `api/model/loader.py`
- **COMPLETED**: Added MPS provider support with benchmarking toggles and session management
- **COMPLETED**: Updated session routing logic to include MPS provider in optimal session selection
- **COMPLETED**: Added MPS utilization tracking and statistics

## Next Steps

### Completed in this merge window
- [x] Test MPS Integration: Verified provider wiring and selection on Apple Silicon via quick benchmark; CoreML optimal; MPS path available
- [x] Performance Validation: Quick benchmark executed (`scripts/run_benchmark.py --quick`), report saved, provider cache populated
- [x] Integration Testing: Streaming endpoint returns immediate WAV header; endpoint-level TTFA/RTF/efficiency recorded per request
- [x] Metrics Plumbing: Resolved duplicate metrics function names; added `update_endpoint_performance_stats` to `api/tts/core.py`

### Remaining follow-ups
- [ ] Long-run soak: 30–60 min streaming soak test to observe TTFA stability and memory trends
- [ ] Benchmark variance: Run comprehensive benchmark suite across scenarios; persist reports under `reports/`
- [ ] Documentation: Add a short API section noting MPS flags in endpoint docs and `README.md`
- [ ] Quantization validation: Compare baseline vs INT8 using `scripts/quantize_model.py --benchmark --compare`
- [ ] Provider cache policy: Tighten cache invalidation windows for hardware changes; add manual reset endpoint

## Configuration
New environment variables for MPS provider:
- `KOKORO_MPS_PROVIDER_ENABLED=false` - Enable/disable MPS provider
- `KOKORO_MPS_PROVIDER_BENCHMARK=false` - Include MPS in provider benchmarking
- `KOKORO_MPS_PROVIDER_PRIORITY=3` - MPS provider priority (lower = higher priority)

## Technical Details
- MPS provider uses Metal GPU acceleration with fp16 precision
- Integrated with existing session management and complexity-based routing
- Supports ORT optimization when available
- Fallback to CPU provider if MPS fails


