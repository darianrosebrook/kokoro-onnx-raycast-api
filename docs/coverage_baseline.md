# Coverage Baseline Assessment

**Date:** 2025-10-09  
**Assessed by:** CAWS Compliance Process  
**Testing Tool:** pytest + pytest-cov

## Current Coverage Summary

### Overall Statistics
- **Total Statements:** ~8,000+
- **Branch Coverage Target:** 80%
- **Current Branch Coverage:** ~15-20% (estimated)
- **Tests Collected:** 80 tests
- **Tests Passing:** ~30/80 (many failures due to missing dependencies)

### Module-Level Coverage

#### High Coverage (>50%)
- `api/model/loader.py`: **80%** ✅ (Well-tested!)

#### Medium Coverage (30-50%)
- `api/config.py`: **38%**
- `api/model/patch.py`: **38%**
- `api/model/utils/temp_management.py`: **41%**

#### Low Coverage (<30%)
- `api/main.py`: **24%**
- `api/model/sessions/manager.py`: **31%**
- `api/model/hardware/capabilities.py`: **29%**
- `api/model/memory/coreml_leak_mitigation.py`: **26%**
- `api/model/pipeline/patterns.py`: **25%**
- `api/model/sessions/utilization.py`: **23%**
- `api/model/utils/cache_utils.py`: **19%**

#### No Coverage (0%)
- `api/core/dependencies.py`: **0%**
- `api/model/benchmarking/*`: **0%**
- `api/model/initialization/*`: **0%**
- `api/model/providers/*`: **0%**
- `api/performance/benchmarks/*`: **0%**
- `api/tts/*`: **0%**
- Most other modules: **0%**

## Key Findings

### Strengths
1. **Test infrastructure exists** - 80 tests already written
2. **Coverage reporting works** - pytest-cov configured correctly
3. **Some critical paths tested** - Model loader has good coverage
4. **Test organization** - Proper separation (unit/contract/integration/performance)

### Gaps
1. **TTS core modules untested** - 0% coverage on `api/tts/`
2. **Provider logic untested** - Core ML and ORT providers at 0%
3. **Performance monitoring untested** - All benchmark modules at 0%
4. **Initialization untested** - Fast init and lifecycle at 0%
5. **Many test failures** - Missing dependencies preventing test execution

## Priority Modules for Testing

### P0 - Critical Path (Must reach 80%)
1. **api/tts/core.py** - Core TTS generation logic
2. **api/tts/streaming_optimizer.py** - Streaming audio generation
3. **api/model/providers/coreml.py** - Core ML provider
4. **api/model/providers/ort.py** - ONNX Runtime provider
5. **api/model/sessions/manager.py** - Session management
6. **api/main.py** - Main API entry point

### P1 - High Value (Should reach 80%)
1. **api/tts/text_processing.py** - Text preprocessing
2. **api/model/initialization/fast_init.py** - Fast initialization
3. **api/performance/ttfa_monitor.py** - TTFA tracking
4. **api/performance/request_tracker.py** - Request tracking
5. **api/routes/performance.py** - Performance endpoints

### P2 - Supporting (Target 70%)
1. **api/model/memory/*** - Memory management
2. **api/model/pipeline/*** - Pipeline optimization
3. **api/performance/benchmarks/*** - Benchmark tooling
4. **api/utils/*** - Utility functions

## Test Execution Status

### Current Test Results
```
Total: 80 tests collected
Passing: ~30 tests
Failing: ~50 tests
Skipped: 1 test
```

### Common Failure Reasons
1. **Missing dependencies** - ONNX models not loaded
2. **Import errors** - Some modules not importable without full dependencies
3. **Configuration issues** - Test fixtures need proper config
4. **Logging errors** - File handle issues during cleanup

## Recommendations

### Immediate Actions (This Week)
1. **Install full dependencies** - Run `pip install -r requirements.txt`
2. **Fix test fixtures** - Mock ONNX models and heavy dependencies
3. **Add unit tests for TTS core** - Bring from 0% to 80%
4. **Add unit tests for providers** - Test Core ML and ORT logic
5. **Fix integration tests** - Resolve dependency issues

### Short-Term (Week 2)
1. **Expand existing tests** - Add edge cases and error handling
2. **Add property-based tests** - Use Hypothesis for robustness
3. **Mock external dependencies** - Test without real models
4. **Document test patterns** - Create test writing guide

### Medium-Term (Week 3-4)
1. **Add mutation testing** - Ensure test quality
2. **Integration with real models** - Test actual TTS generation
3. **Performance testing** - Verify A1-A4 acceptance criteria
4. **CI/CD integration** - Automate coverage reporting

## Gap Analysis

### To Reach 80% Branch Coverage

**Current estimate:** ~18% overall  
**Target:** 80%  
**Gap:** 62 percentage points

**Required additions:**
- ~300-400 new test cases
- ~2,000-3,000 lines of test code
- Focus on critical paths first

**Estimated effort:**
- Week 1: +30-40% coverage (to ~50%)
- Week 2: +20-25% coverage (to ~70%)
- Week 3: +10-15% coverage (to ~85%)

## Next Steps

1. ✅ Coverage baseline established
2. ⬜ Install full dependencies
3. ⬜ Fix existing test failures
4. ⬜ Write unit tests for `api/tts/core.py`
5. ⬜ Write unit tests for `api/model/providers/`
6. ⬜ Write unit tests for `api/tts/streaming_optimizer.py`
7. ⬜ Achieve 50% coverage milestone
8. ⬜ Run mutation testing on covered code
9. ⬜ Push to 80% coverage target
10. ⬜ Verify all acceptance criteria (A1-A4)

---

**Report generated by:** CAWS v1.0 Compliance Process  
**Coverage tool:** pytest-cov 7.0.0  
**Next assessment:** Weekly

