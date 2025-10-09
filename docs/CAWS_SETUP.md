# CAWS Setup Summary - Kokoro ONNX TTS

**Author:** @darianrosebrook  
**Date:** 2025-10-09  
**Status:** Initialized and Validated

## Overview

CAWS (engineering-grade operating system for coding agents) has been successfully initialized in the Kokoro ONNX TTS project. This document summarizes the setup and provides guidance for development workflows.

## What Was Installed

### Core Structure

```
.caws/
├── policy/
│   └── tier-policy.json           # Risk tier thresholds and requirements
├── schemas/
│   ├── provenance.schema.json     # Provenance tracking schema
│   └── working-spec.schema.json   # Working spec validation schema
├── templates/
│   ├── feature.plan.md            # Feature planning template
│   └── pr.md                      # Pull request template
├── provenance/
│   ├── chain.json                 # Provenance tracking chain
│   └── config.json                # Provenance configuration
└── working-spec.yaml              # Project working specification
```

### Tools & Scripts

```
tools/caws/
├── gates.py                       # Quality gate validation
└── validate.py                    # Spec validation utilities
```

### Configuration Files

- `.caws.yml` - Project-specific CAWS configuration
- `.agent/provenance.json` - Initial provenance manifest
- `.agent/scaffold-provenance.json` - Scaffold provenance record

### Git Hooks (2 active)

- **pre-commit**: Validation and quality checks
- **commit-msg**: Message validation

## Project Configuration

### Profile: backend-api

The project is configured as a **backend-api** profile with the following characteristics:

- **Risk Tier**: 2
- **Language**: Python
- **Framework**: FastAPI
- **Primary Concerns**: Performance, Real-time audio streaming, ONNX model optimization

### Performance Invariants

Per `docs/perf/baselines.json` and the optimization blueprint:

| Metric | Target | Unit |
|--------|--------|------|
| TTFA (short, ~140 chars) | ≤ 0.50 | seconds (p95) |
| RTF (long paragraph) | ≤ 0.60 | p95 |
| Underruns | ≤ 1 | per 10 minutes |
| Loudness | -16 ±1 | LUFS |
| dBTP | ≤ -1.0 | dB |
| Memory envelope | ±300 | MB (RSS) |

### Scope

**In Scope:**
- `api/` - Core API implementation
- `api/model/` - ONNX model loading and session management
- `api/tts/` - TTS core functionality and streaming
- `api/performance/` - Performance monitoring and optimization
- `raycast/src/` - Raycast integration
- `tests/` - All test suites
- `scripts/` - Utility scripts
- `docs/` - Documentation

**Out of Scope:**
- `node_modules/`
- `__pycache__/`
- `.venv/`
- `optimized_models/`
- `artifacts/`
- `logs/`
- `temp/`

## Acceptance Criteria

### A1: Short Text TTFA
**Given:** valid text input (~140 chars)  
**When:** `/v1/tts` request received  
**Then:** TTFA ≤ 0.50s p95, audio stream begins

### A2: Long Text Streaming
**Given:** long paragraph input  
**When:** `/v1/tts` with streaming enabled  
**Then:** RTF ≤ 0.60 p95, no underruns, monotonic playback

### A3: Error Handling
**Given:** malformed or unsupported text  
**When:** `/v1/tts` request received  
**Then:** explainable error, no state change, no PII in logs

### A4: Concurrent Load
**Given:** concurrent requests  
**When:** multiple `/v1/tts` calls  
**Then:** memory envelope maintained, no drift in TTFA/RTF

## Quality Gates

### Static Analysis
```bash
ruff check api/ && mypy api/ && bandit -r api/ -ll
```

### Unit Tests
```bash
pytest tests/unit/ --cov=api --cov-report=term-missing
```
**Target:** 80% branch coverage

### Mutation Testing
```bash
mutmut run --paths-to-mutate=api/
```
**Target:** 50% mutation score (Tier 2)

### Contract Tests
```bash
pytest tests/contract/ -v
```
Validates against `contracts/kokoro-tts-api.yaml`

### Integration Tests
```bash
pytest tests/integration/ -v
```

### Performance Tests
```bash
python scripts/run_bench.py --preset=short --stream --trials=3
```

## Observability

### Logs
- Request start/end with duration
- TTFA per request
- RTF per request
- Errors with sanitized input context

### Metrics
- `tts_requests_total`
- `tts_ttfa_seconds`
- `tts_rtf_ratio`
- `tts_errors_total`
- `tts_underruns_total`

### Traces
- `/v1/tts` span with attributes:
  - `text_length`
  - `voice`
  - `streaming`

## Rollback Strategy

1. **Feature flag kill-switch** via environment variables
2. **Provider fallback**: Core ML → ORT
3. **Quantization fallback**: INT8 → FP16

## Development Workflow

### 1. Planning Phase

Before implementing a feature:

```bash
# Check current status
caws status

# Validate working spec
caws validate

# Create feature plan from template
cp .caws/templates/feature.plan.md docs/features/<feature-slug>.md
```

### 2. Implementation Phase

During development:

```bash
# Update progress on acceptance criteria
caws progress update --criterionId A1 --status in_progress

# Run quality checks locally
make caws:static
make caws:unit
make caws:perf
```

### 3. Verification Phase

Before committing:

```bash
# Run all gates
make caws:verify

# Generate provenance
caws provenance update --commit $(git rev-parse HEAD)
```

### 4. Delivery Phase

When opening a PR:

1. Use template from `.caws/templates/pr.md`
2. Include evidence for each acceptance criterion
3. Link to benchmark results in `artifacts/bench/`
4. Document any spec changes

## CAWS Commands Reference

### Status & Health
```bash
caws status                          # Project health overview
caws diagnose                        # Run health checks
caws diagnose --fix                  # Auto-fix detected issues
```

### Validation
```bash
caws validate                        # Validate working spec
caws validate --suggestions          # Get improvement suggestions
```

### Quality Gates
```bash
python tools/caws/gates.py           # Check quality gates
```

### Provenance
```bash
caws provenance show                 # View provenance history
caws provenance update --commit <hash>  # Update provenance
caws provenance verify               # Verify provenance chain
```

### Progress Tracking
```bash
caws progress update --criterionId A1 --status in_progress
caws progress update --criterionId A1 --status completed --coverage 85 --testsWritten 10 --testsPassing 10
```

### Help
```bash
caws help                            # General help
caws help --tool provenance          # Tool-specific help
```

## AI Assessment

**Confidence Level:** 0.9

**Uncertainty Areas:**
- Core ML EP selection logic (ALL vs CPUAndGPU)
- Memory profiling under sustained load

**Complexity Factors:**
- Real-time audio streaming with buffering
- Multi-provider ONNX session management
- Performance monitoring and adaptive optimization

**Risk Factors:**
- Audio quality regression from quantization
- Memory leaks in long-running sessions
- Platform-specific Core ML behavior

## Next Steps

1. ✅ CAWS initialized and validated
2. ✅ Working spec customized for Kokoro TTS
3. ✅ Project configuration created (`.caws.yml`)
4. ✅ Tools scaffolded and verified
5. ⬜ Review and customize acceptance criteria
6. ⬜ Set up CI/CD pipeline (`.github/workflows/caws.yml`)
7. ⬜ Run initial quality gate assessment
8. ⬜ Create feature plans for upcoming work

## References

- Working Spec: `.caws/working-spec.yaml`
- Project Config: `.caws.yml`
- Tier Policy: `.caws/policy/tier-policy.json`
- Optimization Blueprint: `docs/kokoro-tts-optimization-blueprint.md`
- Performance Baselines: `docs/perf/baselines.json`
- API Contract: `contracts/kokoro-tts-api.yaml`

## Troubleshooting

### Issue: Git hooks conflict with existing hooks
**Solution:** Use `caws hooks install --backup` to preserve originals

### Issue: Validation fails
**Solution:** Run `caws validate` to see specific errors, then fix in `.caws/working-spec.yaml`

### Issue: Quality gates not found
**Solution:** Ensure Python environment is activated and dependencies installed

### Issue: Performance tests fail
**Solution:** Check that ONNX models are present in expected locations

---

For detailed CAWS documentation, see the [CAWS v1.0 specification](./agents.md) and [implementation guide](./CAWS_IMPLEMENTATION.md).

