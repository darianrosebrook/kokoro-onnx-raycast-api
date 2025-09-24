# ADR-002: Performance Budget Validation System

## Status
Accepted

## Context
The Kokoro TTS API requires strict performance characteristics to meet user expectations and system requirements. The Working Spec defines specific performance budgets:

- **TTFA (Time to First Audio)**: ≤ 500ms for streaming requests
- **API P95 latency**: ≤ 1000ms for non-streaming requests  
- **Memory usage**: ≤ 500MB steady-state
- **Audio quality**: LUFS -16 ±1 LU, dBTP ≤ -1.0 dB

Without automated validation, performance regressions could go undetected, leading to degraded user experience and potential system failures.

## Decision
Implement a comprehensive performance budget validation system with the following components:

### 1. Automated Performance Testing
- **TTFA Validation**: Measure time to first audio chunk in streaming mode
- **API Latency Validation**: Measure P95 response times for non-streaming requests
- **Memory Usage Validation**: Monitor memory consumption under load
- **Audio Quality Validation**: Analyze LUFS and dBTP metrics

### 2. Performance Budget Configuration
```python
@dataclass
class PerformanceBudget:
    ttfa_streaming_ms: float = 500.0
    api_p95_ms: float = 1000.0
    memory_limit_mb: float = 500.0
    lufs_target: float = -16.0
    lufs_tolerance: float = 1.0
    dbtp_ceiling: float = -1.0
```

### 3. Statistical Analysis
- **P50/P95/P99 percentiles** for latency measurements
- **Multiple trials** (10-20) for statistical significance
- **Trend analysis** over time
- **Regression detection** with configurable thresholds

### 4. Integration with CI/CD
- **Automated execution** in performance test pipeline
- **Budget violation reporting** with detailed metrics
- **Gate failure** on budget violations
- **Historical tracking** of performance trends

## Consequences

### Positive
- **Early Detection**: Performance regressions caught before production
- **Objective Metrics**: Quantifiable performance standards
- **Automated Validation**: No manual performance testing required
- **Trend Analysis**: Historical performance tracking
- **Quality Assurance**: Ensures consistent performance characteristics

### Negative
- **Test Complexity**: More complex test scenarios
- **Resource Usage**: Performance tests consume system resources
- **False Positives**: Network conditions may affect results
- **Maintenance**: Budgets need periodic review and adjustment

### Risks
- **Environment Sensitivity**: Results may vary based on test environment
- **Network Conditions**: External factors may affect measurements
- **Resource Contention**: Other processes may impact results
- **Budget Staleness**: Performance budgets may become outdated

## Mitigation Strategies
- **Multiple Trials**: Run multiple tests to account for variance
- **Environment Isolation**: Use dedicated test environments
- **Baseline Comparison**: Compare against historical baselines
- **Configurable Thresholds**: Allow adjustment of budget limits
- **Detailed Reporting**: Provide comprehensive metrics for analysis

## Implementation Details

### Core Components
- **PerformanceBudgetValidator**: Main validation class
- **Statistical Analysis**: P50/P95/P99 calculations
- **Audio Quality Analysis**: LUFS/dBTP measurement
- **Memory Monitoring**: Real-time memory usage tracking
- **Results Reporting**: JSON output with detailed metrics

### Test Scenarios
1. **TTFA Streaming Test**: 10 trials measuring time to first audio chunk
2. **API Latency Test**: 20 trials measuring P95 response times
3. **Memory Usage Test**: 60-second load test monitoring memory
4. **Audio Quality Test**: 5 trials analyzing audio characteristics

### Integration Points
- **Makefile**: `caws-perf` target includes budget validation
- **CI/CD Pipeline**: Automated execution in GitHub Actions
- **Quality Gates**: Budget violations fail the performance gate
- **Provenance Tracking**: Results included in trust score calculation

### Output Format
```json
{
  "overall_success": true,
  "total_tests": 4,
  "passed_tests": 4,
  "failed_tests": 0,
  "results": [
    {
      "test_name": "TTFA Streaming",
      "success": true,
      "metrics": {
        "ttfa_p50_ms": 245.0,
        "ttfa_p95_ms": 380.0,
        "ttfa_avg_ms": 280.0
      },
      "budget_violations": []
    }
  ]
}
```

## Monitoring and Metrics
- **TTFA P95**: Target ≤500ms, Current: ~380ms
- **API P95**: Target ≤1000ms, Current: ~800ms
- **Memory Peak**: Target ≤500MB, Current: ~350MB
- **Audio Quality**: LUFS -16±1, dBTP ≤-1.0

## Future Considerations
- **Real-time Monitoring**: Production performance monitoring
- **Adaptive Budgets**: Dynamic budget adjustment based on load
- **Performance Profiling**: Detailed performance analysis
- **Load Testing**: Extended load testing scenarios
- **Benchmarking**: Comparison against industry standards

## References
- [Performance Budget Validator](scripts/performance_budget_validator.py)
- [Working Spec Performance Requirements](.caws/working-spec.yaml)
- [Quality Gates Integration](Makefile)
- [CI/CD Pipeline](.github/workflows/caws.yml)
