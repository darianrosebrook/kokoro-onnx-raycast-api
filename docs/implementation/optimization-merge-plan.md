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
1. **Test MPS Integration**: Verify MPS provider works correctly on Apple Silicon systems
2. **Performance Validation**: Run benchmarks to ensure MPS provider performance improvements
3. **Documentation**: Update API documentation to reflect new MPS provider options
4. **Integration Testing**: Test full pipeline with MPS provider enabled

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


