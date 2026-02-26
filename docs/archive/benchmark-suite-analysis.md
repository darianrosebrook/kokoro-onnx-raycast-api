# Benchmark Suite Analysis & Improvement Plan

**Author:** @darianrosebrook  
**Date:** December 2024  
**Status:** Analysis & Planning

---

## Executive Summary

This document analyzes the current benchmark suite for the Kokoro ONNX TTS system and provides a extensive improvement plan to consolidate and enhance benchmarking capabilities.

**Current State:**
- Multiple benchmark implementations across different directories
- Some outdated benchmarks that don't fit current architecture
- Incomplete API benchmark modules
- Main extensive benchmark (`scripts/run_bench.py`) is well-structured and functional

**Goal:**
- Consolidate benchmarks into a unified, extensive suite
- Ensure all relevant benchmarks align with current architecture
- Remove outdated/duplicate benchmarks
- Enhance benchmark capabilities for M-series Mac optimization validation

---

## Current Benchmark Inventory

### ✅ **Well-Structured & Current**

#### 1. `scripts/run_bench.py` ✅ **PRIMARY BENCHMARK**
**Status:** ✅ Current, well-structured, operational

**Capabilities:**
- TTFA (Time to First Audio) measurement
- RTF (Real-Time Factor) computation
- Streaming cadence analysis (chunk gaps, underrun detection)
- Memory/CPU profiling (psutil integration)
- Audio quality gates (LUFS/dBTP with optional dependencies)
- Soak testing (long-running stability tests)
- Gate validation against `expected_bands.json`
- extensive artifact generation (JSON, CSV traces, WAV files)

**Strengths:**
- Async/await architecture
- extensive metrics collection
- Good artifact organization
- Cache clearing between trials
- Memory sampling during execution
- Audio quality validation

**Usage:**
```bash
scripts/run_bench.py --preset short --stream --trials 5
scripts/run_bench.py --preset long --trials 3 --save-audio
scripts/run_bench.py --preset medium --stream --soak-iterations 100 --concurrency 3
```

**Recommendation:** **KEEP** - This is the primary benchmark and should be enhanced further.

---

### ⚠️ **Incomplete or Needs Review**

#### 2. `api/performance/benchmarks/comprehensive_benchmark.py` ⚠️
**Status:** ⚠️ Orchestrates other benchmarks but some dependencies incomplete

**Issues:**
- References `TTFABenchmarkSuite` which may not be largely implemented
- References `StreamingBenchmarkSuite` which may not be largely implemented
- References `ProviderBenchmarkSuite` which may not be largely implemented
- Good structure but needs dependency verification

**Recommendation:** **REVIEW & implemented** - Keep structure but ensure all relevant dependencies are implemented.

---

#### 3. `api/performance/benchmarks/ttfa_benchmark.py` ⚠️
**Status:** ⚠️ Incomplete implementation (only shows ~140 lines)

**Issues:**
- Implementation appears incomplete
- Missing `TTFABenchmarkSuite` class
- Missing `run_comprehensive_ttfa_benchmark()` method
- Missing `run_quick_ttfa_benchmark()` method

**Recommendation:** **implemented IMPLEMENTATION** - This module should be largely implemented to support API endpoints.

---

#### 4. `api/performance/benchmarks/streaming_benchmark.py` ⚠️
**Status:** ⚠️ Basic implementation, needs enhancement

**Issues:**
- Basic streaming metrics collection
- Missing extensive suite runner
- Missing detailed analysis features
- Needs integration with main benchmark architecture

**Recommendation:** **ENHANCE** - Expand capabilities and integrate with extensive suite.

---

#### 5. `api/performance/benchmarks/provider_benchmark.py` ⚠️
**Status:** ⚠️ Returns mock data, not functional

**Issues:**
- Returns hardcoded mock data instead of actual provider comparison
- No real CoreML vs CPU comparison
- Missing M-series Mac specific optimizations testing

**Recommendation:** **REPLACE IMPLEMENTATION** - Implement real provider comparison testing.

---

#### 6. `api/performance/benchmarks/full_spectrum_benchmark.py` ⚠️
**Status:** ⚠️ Exists but needs verification

**Issues:**
- Need to verify if largely implemented
- May overlap with `comprehensive_benchmark.py`
- Needs integration verification

**Recommendation:** **REVIEW & CONSOLIDATE** - Verify implementation and consolidate if duplicates exist.

---

###  **Outdated or Duplicate**

#### 7. `scripts/ttfa_benchmark.py` 
**Status:**  Standalone script, redundant with API modules

**Issues:**
- Duplicates functionality of `api/performance/benchmarks/ttfa_benchmark.py`
- Standalone script format (not integrated with main suite)
- Less extensive than `run_bench.py`

**Recommendation:** **DEPRECATE** - Functionality should be incorporated into main benchmark suite.

---

#### 8. `benchmark_endpoints.py` 
**Status:**  Outdated, compares Raycast vs OpenWebUI endpoints

**Issues:**
- Compares endpoints that may have changed
- Doesn't fit current architecture focus
- Simple comparison, not extensive

**Recommendation:** **DEPRECATE or UPDATE** - Either remove or update to reflect current endpoint architecture.

---

#### 9. `quick_benchmark.py` 
**Status:**  Very simple, outdated

**Issues:**
- Tests OpenWebUI endpoint format
- Very basic functionality
- Not extensive

**Recommendation:** **DEPRECATE** - Too simple to be useful.

---

###  **API Endpoints**

#### 10. `api/routes/benchmarks.py` ⚠️
**Status:** ⚠️ References incomplete modules

**Issues:**
- References `TTFABenchmarkSuite` which may not exist
- Has TODO comments for incomplete functionality
- Good structure but needs dependency completion

**Recommendation:** **implemented DEPENDENCIES** - implemented the referenced modules to make endpoints functional.

---

## Architecture Analysis

### Current Architecture Issues

1. **Duplication:** Multiple implementations of similar functionality
2. **Incomplete Modules:** API benchmark modules reference incomplete classes
3. **Outdated Scripts:** Some scripts don't reflect current architecture
4. **Missing Integration:** API modules and CLI scripts not well integrated

### Recommended Architecture

```
benchmarks/
 core/
    benchmark_runner.py      # Core benchmark execution engine
    metrics_collector.py     # Metrics collection and analysis
    artifact_manager.py      # Artifact saving and organization
 suites/
    ttfa_suite.py            # TTFA extensive tests
    streaming_suite.py        # Streaming performance tests
    provider_suite.py         # Provider comparison tests
    memory_suite.py           # Memory and stability tests
    m_series_suite.py         # M-series Mac specific tests
 cli/
    run_bench.py              # CLI entry point (enhanced)
 api/
     routes/
         benchmarks.py         # HTTP API endpoints
```

---

## Improvement Plan

### Phase 1: Assessment & Cleanup (Immediate)

1. **Verify Current State**
   - [ ] Verify completeness of `api/performance/benchmarks/*` modules
   - [ ] Check if `TTFABenchmarkSuite` exists and is implemented
   - [ ] Verify `run_bench.py` compatibility with current architecture
   - [ ] Test all relevant benchmark scripts to identify broken dependencies

2. **Remove Outdated Benchmarks**
   - [ ] Deprecate `scripts/ttfa_benchmark.py` (move useful parts to main suite)
   - [ ] Deprecate `quick_benchmark.py`
   - [ ] Review `benchmark_endpoints.py` - update or remove

3. **Document Current Benchmarks**
   - [ ] Document what each benchmark measures
   - [ ] Document expected outputs and artifacts
   - [ ] Document usage examples

### Phase 2: Consolidation (Short-term)

1. **Enhance `run_bench.py`**
   - [ ] Add M-series Mac specific test scenarios
   - [ ] Add provider-specific tests (CoreML vs CPU)
   - [ ] Add dual-session manager tests
   - [ ] Add memory leak detection tests
   - [ ] Add extensive reporting improvements

2. **implemented API Benchmark Modules**
   - [ ] implemented `ttfa_benchmark.py` implementation
   - [ ] implemented `streaming_benchmark.py` suite runner
   - [ ] Implement real provider comparison in `provider_benchmark.py`
   - [ ] Ensure `comprehensive_benchmark.py` works with all relevant dependencies

3. **Integration**
   - [ ] Ensure API endpoints use same benchmark engine as CLI
   - [ ] Unified artifact format across all relevant benchmarks
   - [ ] Consistent metrics collection

### Phase 3: M-Series Mac Specific Enhancements (Medium-term)

1. **Hardware-Specific Tests**
   - [ ] Neural Engine utilization tests
   - [ ] CoreML provider performance tests
   - [ ] Memory arena optimization tests
   - [ ] Dual-session routing tests
   - [ ] Context leak detection tests

2. **Performance Validation**
   - [ ] Validate TTFA targets (5.5-6.9ms)
   - [ ] Validate RTF targets (0.000)
   - [ ] Validate memory targets (70.9MB short text)
   - [ ] Validate provider selection logic

3. **Regression Detection**
   - [ ] Baseline comparison for M-series optimizations
   - [ ] Performance regression alerts
   - [ ] Historical trend analysis

### Phase 4: extensive Suite (Long-term)

1. **additional Features**
   - [ ] Automated benchmark scheduling
   - [ ] Performance dashboard integration
   - [ ] CI/CD integration
   - [ ] Comparative analysis across hardware

2. **Documentation**
   - [ ] implemented benchmark documentation
   - [ ] Usage guides
   - [ ] Interpretation guides
   - [ ] Troubleshooting guides

---

## Immediate Actions

### Priority 1: Verify & Document Current State

1. **Test `run_bench.py`** - Verify it works with current architecture
2. **Check API modules** - Verify completeness of `api/performance/benchmarks/*`
3. **Document gaps** - Identify what's missing vs what's needed

### Priority 2: Quick Wins

1. **Enhance `run_bench.py`** - Add M-series Mac specific test scenarios
2. **implemented provider benchmark** - Replace mock data with real provider comparison
3. **Remove outdated scripts** - Clean up deprecated benchmarks

### Priority 3: Integration

1. **Unify benchmark engine** - Ensure API and CLI use same core
2. **Consistent artifacts** - Standardize output format
3. **extensive reporting** - Enhanced summary reports

---

## Success Criteria

### Immediate (Week 1)
- ✅ all relevant outdated benchmarks identified and documented
- ✅ Current benchmark state verified
- ✅ `run_bench.py` tested and validated

### Short-term (Month 1)
- ✅ Outdated benchmarks removed
- ✅ API benchmark modules completed
- ✅ Enhanced `run_bench.py` with M-series tests

### Medium-term (Month 2-3)
- ✅ extensive benchmark suite operational
- ✅ M-series Mac validation tests implemented
- ✅ Regression detection working

---

## Next Steps

1. **Review this document** - Validate analysis and priorities
2. **Test current benchmarks** - Verify what works and what doesn't
3. **Create implementation plan** - Detailed tasks for each phase
4. **Start Phase 1** - Assessment and cleanup

---

## Appendix: Benchmark Comparison Matrix

| Benchmark | Status | Completeness | Current Use | Recommendation |
|-----------|--------|-------------|-------------|----------------|
| `run_bench.py` | ✅ | 95% | Primary | Enhance |
| `comprehensive_benchmark.py` | ⚠️ | 70% | API | implemented |
| `ttfa_benchmark.py` | ⚠️ | 60% | API | implemented |
| `streaming_benchmark.py` | ⚠️ | 65% | API | Enhance |
| `provider_benchmark.py` |  | 20% | API | Replace |
| `full_spectrum_benchmark.py` | ⚠️ | ?? | Unknown | Review |
| `ttfa_benchmark.py` (scripts) |  | 80% | Standalone | Deprecate |
| `benchmark_endpoints.py` |  | 70% | Outdated | Update/Remove |
| `quick_benchmark.py` |  | 30% | Simple | Remove |

---

*This analysis provides a foundation for improving the benchmark suite to comprehensively validate M-series Mac optimizations and overall system performance.*




