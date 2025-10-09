# CAWS Compliance Roadmap

**Author:** @darianrosebrook  
**Project:** Kokoro ONNX TTS  
**Working Spec:** KOKORO-001  
**Risk Tier:** 2  
**Date:** 2025-10-09  
**Status:** In Progress

## Executive Summary

This document outlines the roadmap to achieve full CAWS v1.0 compliance for the Kokoro ONNX TTS project. The project is currently at **~35% compliance** based on initial assessment. Full compliance requires meeting all Tier 2 quality gates for backend-api profile.

## Current State Assessment

### ✅ Completed (Foundation)

- [x] CAWS infrastructure initialized
- [x] Working specification defined (KOKORO-001)
- [x] Project configuration created (`.caws.yml`)
- [x] Git hooks active (pre-commit, commit-msg)
- [x] Provenance tracking initialized
- [x] Documentation and quick start guides created
- [x] Tools scaffolded (validation, gates)

### ⬜ In Progress / Pending

#### Test Coverage (Current: ~40% estimated)

**Existing Tests:**
- Unit tests: 2 files (`test_config.py`, `test_security.py`)
- Contract tests: 2 files (`test_api_contracts.py`, `test_openapi_contracts.py`)
- Integration tests: 1 file (`test_tts_integration.py`)
- Performance tests: 1 file (`test_tts_performance.py`)

**Required for Tier 2:**
- Branch coverage ≥ 80%
- Mutation score ≥ 50%
- Contract tests fully implemented
- Integration tests with real services
- Performance tests meeting all acceptance criteria

#### Quality Gates Status

| Gate | Status | Current | Target | Priority |
|------|--------|---------|--------|----------|
| Static Analysis | ⚠️ Partial | Manual | Automated | P0 |
| Unit Tests | ⬜ Pending | ~40% | 80% branch | P0 |
| Mutation Testing | ⬜ Not Run | 0% | 50% | P0 |
| Contract Tests | ⚠️ Partial | Basic | Complete | P1 |
| Integration Tests | ⚠️ Partial | Basic | Full | P1 |
| Performance Tests | ⚠️ Partial | Basic | A1-A4 verified | P0 |
| Security Scanning | ⬜ Pending | Manual | Automated | P1 |
| Dependency Audit | ⬜ Pending | Manual | Automated | P2 |

## Compliance Roadmap

### Milestone 1: Core Testing Infrastructure (Week 1) - P0

**Goal:** Establish comprehensive unit testing and achieve 80% branch coverage

#### Tasks

1. **Unit Test Expansion**
   - [ ] Audit all modules in `api/` for test coverage
   - [ ] Write unit tests for `api/model/` (loader, providers, sessions)
   - [ ] Write unit tests for `api/tts/` (core, streaming, text processing)
   - [ ] Write unit tests for `api/performance/` (monitoring, benchmarks)
   - [ ] Write unit tests for `api/routes/` (endpoints)
   - [ ] Add property-based tests using Hypothesis
   - [ ] Target: 80%+ branch coverage

   **Files to Cover:**
   ```
   api/model/loader.py
   api/model/providers.py
   api/model/sessions/session_manager.py
   api/tts/core.py
   api/tts/streaming_optimizer.py
   api/tts/text_processing.py
   api/performance/ttfa_monitor.py
   api/performance/request_tracker.py
   api/routes/performance.py
   api/routes/benchmarks.py
   ```

2. **Set Up Coverage Reporting**
   - [ ] Configure pytest-cov for detailed coverage reports
   - [ ] Set up coverage thresholds in pytest.ini
   - [ ] Create coverage report artifacts
   - [ ] Add coverage badge/reporting

   **Command:**
   ```bash
   pytest tests/unit/ \
     --cov=api \
     --cov-report=term-missing \
     --cov-report=html \
     --cov-report=json \
     --cov-branch \
     --cov-fail-under=80
   ```

3. **Test Fixtures and Factories**
   - [ ] Create test fixtures for ONNX sessions (mocked)
   - [ ] Create test fixtures for audio generation
   - [ ] Create test fixtures for configuration
   - [ ] Create factory functions for test data generation
   - [ ] Document fixture usage patterns

   **Location:** `tests/fixtures/`

#### Success Criteria

- ✅ Branch coverage ≥ 80%
- ✅ All core modules have unit tests
- ✅ Coverage report generates successfully
- ✅ Test execution time < 30 seconds

#### Evidence Required

```bash
pytest tests/unit/ --cov=api --cov-report=term-missing --cov-branch
# Output showing ≥80% branch coverage
```

---

### Milestone 2: Mutation Testing (Week 1-2) - P0

**Goal:** Establish mutation testing and achieve 50% mutation score

#### Tasks

1. **Set Up Mutation Testing**
   - [ ] Configure mutmut for Python codebase
   - [ ] Define mutation targets (api/ excluding tests)
   - [ ] Create mutation testing workflow
   - [ ] Document mutation testing process

   **Configuration:**
   ```python
   # mutmut_config.py
   def pre_mutation(context):
       context.config.test_command = 'pytest tests/unit/ -x'
       
   paths_to_mutate = [
       'api/model/',
       'api/tts/',
       'api/performance/',
       'api/routes/',
   ]
   ```

2. **Run Initial Mutation Analysis**
   - [ ] Run mutmut on core modules
   - [ ] Analyze survived mutants
   - [ ] Identify weak test coverage areas
   - [ ] Create action items for test improvements

   **Command:**
   ```bash
   mutmut run --paths-to-mutate=api/ --tests-dir=tests/unit/
   mutmut results
   mutmut html
   ```

3. **Improve Test Quality**
   - [ ] Add assertions for survived mutants
   - [ ] Add edge case tests
   - [ ] Add boundary condition tests
   - [ ] Target: 50%+ mutation score

#### Success Criteria

- ✅ Mutation score ≥ 50%
- ✅ No critical paths have 0% mutation score
- ✅ Mutation report generated
- ✅ Weak areas documented and addressed

#### Evidence Required

```bash
mutmut run --paths-to-mutate=api/
mutmut results
# Output showing mutation score ≥50%
```

---

### Milestone 3: Contract Testing (Week 2) - P1

**Goal:** Complete OpenAPI contract testing for provider and consumer roles

#### Tasks

1. **Provider Contract Tests**
   - [ ] Validate all OpenAPI endpoints against schema
   - [ ] Test request/response shapes for `/v1/audio/speech`
   - [ ] Test request/response shapes for `/health`, `/status`, `/voices`
   - [ ] Validate error responses match schema
   - [ ] Test content-type headers
   - [ ] Test streaming responses

   **Tool:** Schemathesis or OpenAPI validators

   ```python
   import schemathesis
   
   schema = schemathesis.from_uri("contracts/kokoro-tts-api.yaml")
   
   @schema.parametrize()
   def test_api_contract(case):
       case.call_and_validate()
   ```

2. **Consumer Contract Tests** (for Raycast integration)
   - [ ] Mock API responses based on OpenAPI schema
   - [ ] Test Raycast client against mocked API
   - [ ] Verify Raycast handles all response types
   - [ ] Test error handling in Raycast client
   - [ ] Validate request construction

   **Tool:** MSW (Mock Service Worker) for TypeScript/Raycast

3. **Contract Versioning**
   - [ ] Set up contract version tracking
   - [ ] Document breaking vs non-breaking changes
   - [ ] Create contract changelog
   - [ ] Establish contract evolution policy

#### Success Criteria

- ✅ All OpenAPI endpoints have contract tests
- ✅ Provider contract tests pass 100%
- ✅ Consumer contract tests cover Raycast client
- ✅ Contract artifacts stored in `contracts/`

#### Evidence Required

```bash
pytest tests/contract/ -v
# All contract tests passing
```

---

### Milestone 4: Integration Testing (Week 2-3) - P1

**Goal:** Comprehensive integration tests with real or containerized services

#### Tasks

1. **Model Integration Tests**
   - [ ] Test ONNX model loading with real model files
   - [ ] Test Core ML EP initialization on macOS
   - [ ] Test provider fallback (Core ML → CPU)
   - [ ] Test quantization fallback (INT8 → FP16)
   - [ ] Test session lifecycle management
   - [ ] Test concurrent session handling

2. **TTS Pipeline Integration Tests**
   - [ ] Test end-to-end TTS generation (text → audio)
   - [ ] Test Misaki G2P integration
   - [ ] Test eSpeak fallback
   - [ ] Test audio format conversions
   - [ ] Test streaming pipeline
   - [ ] Test chunk sequencing and buffering

3. **API Integration Tests**
   - [ ] Test full request/response cycle
   - [ ] Test concurrent request handling
   - [ ] Test rate limiting (if implemented)
   - [ ] Test error propagation
   - [ ] Test middleware chain
   - [ ] Test performance monitoring integration

4. **Test Data Management**
   - [ ] Create deterministic test fixtures
   - [ ] Use fixtures for ONNX models (small test models)
   - [ ] Create seed data for consistent testing
   - [ ] Document test data setup/teardown

#### Success Criteria

- ✅ All integration test scenarios pass
- ✅ Real ONNX models used in tests (or test-size models)
- ✅ No mocking of owned boundaries
- ✅ Tests are deterministic and repeatable

#### Evidence Required

```bash
pytest tests/integration/ -v
# All integration tests passing with real components
```

---

### Milestone 5: Performance & Acceptance Testing (Week 3) - P0

**Goal:** Verify all acceptance criteria (A1-A4) and performance invariants

#### Tasks

1. **Acceptance Criterion A1: Short Text TTFA**
   ```
   Given: valid text input (~140 chars)
   When: /v1/tts request received
   Then: TTFA ≤ 0.50s p95, audio stream begins
   ```

   - [ ] Create test with 140-char text input
   - [ ] Measure TTFA over 100 trials
   - [ ] Verify p95 ≤ 0.50s
   - [ ] Document measurement methodology
   - [ ] Store benchmark results

   **Command:**
   ```bash
   python scripts/run_bench.py \
     --preset=short \
     --stream \
     --trials=100 \
     --output=artifacts/bench/$(date +%Y-%m-%d)/A1-short-ttfa.json
   ```

2. **Acceptance Criterion A2: Long Text RTF**
   ```
   Given: long paragraph input
   When: /v1/tts with streaming enabled
   Then: RTF ≤ 0.60 p95, no underruns, monotonic playback
   ```

   - [ ] Create test with long paragraph (~500 chars)
   - [ ] Measure RTF over 100 trials
   - [ ] Verify p95 ≤ 0.60
   - [ ] Verify no underruns
   - [ ] Verify monotonic playback (chunk sequencing)
   - [ ] Store benchmark results

3. **Acceptance Criterion A3: Error Handling**
   ```
   Given: malformed or unsupported text
   When: /v1/tts request received
   Then: explainable error, no state change, no PII in logs
   ```

   - [ ] Test with malformed UTF-8
   - [ ] Test with unsupported characters
   - [ ] Test with empty text
   - [ ] Test with text > max_length
   - [ ] Verify error messages are clear
   - [ ] Verify no PII leakage in logs
   - [ ] Verify no state corruption

4. **Acceptance Criterion A4: Concurrent Load**
   ```
   Given: concurrent requests
   When: multiple /v1/tts calls
   Then: memory envelope maintained, no drift in TTFA/RTF
   ```

   - [ ] Run load test with 10 concurrent requests
   - [ ] Monitor RSS memory during test
   - [ ] Verify memory envelope ±300 MB
   - [ ] Measure TTFA/RTF stability across requests
   - [ ] Verify no performance degradation
   - [ ] Store load test results

5. **Audio Quality Verification**
   - [ ] Test loudness: -16 LUFS ±1 LU
   - [ ] Test dBTP ≤ -1.0 dB
   - [ ] Create automated audio analysis tests
   - [ ] Use pyloudnorm or ffmpeg for measurement

#### Success Criteria

- ✅ All acceptance criteria (A1-A4) verified with evidence
- ✅ Performance benchmarks stored in `artifacts/bench/`
- ✅ Audio quality metrics meet specifications
- ✅ Tests run in CI/CD pipeline

#### Evidence Required

For each acceptance criterion:
```bash
# A1
python scripts/run_bench.py --preset=short --trials=100
cat artifacts/bench/$(date +%Y-%m-%d)/short.json | jq '.ttfa_p95'
# Output: ≤ 0.50

# A2
python scripts/run_bench.py --preset=long --trials=100
cat artifacts/bench/$(date +%Y-%m-%d)/long.json | jq '.rtf_p95'
# Output: ≤ 0.60

# A3
pytest tests/integration/test_error_handling.py -v
# All error handling tests pass

# A4
python scripts/run_bench.py --preset=load --concurrent=10
cat artifacts/bench/$(date +%Y-%m-%d)/load.json | jq '.memory_envelope'
# Output: within ±300 MB
```

---

### Milestone 6: Static Analysis & Security (Week 3-4) - P1

**Goal:** Automate static analysis, security scanning, and dependency audits

#### Tasks

1. **Static Type Checking**
   - [ ] Set up mypy for strict type checking
   - [ ] Add type hints to all public APIs
   - [ ] Fix all mypy errors
   - [ ] Configure mypy in CI

   **Command:**
   ```bash
   mypy api/ --strict --no-incremental
   ```

2. **Linting**
   - [ ] Configure ruff for Python linting
   - [ ] Fix all linting errors
   - [ ] Set up pre-commit hook for linting
   - [ ] Document linting rules

   **Command:**
   ```bash
   ruff check api/ --fix
   ```

3. **Security Scanning (SAST)**
   - [ ] Set up Bandit for security issues
   - [ ] Fix all high/medium severity issues
   - [ ] Document any accepted low-severity issues
   - [ ] Configure Bandit in CI

   **Command:**
   ```bash
   bandit -r api/ -ll -f json -o security-scan-results.json
   ```

4. **Secret Scanning**
   - [ ] Set up gitleaks or trufflehog
   - [ ] Scan repository history
   - [ ] Set up pre-commit hook for secrets
   - [ ] Document secret management policy

   **Command:**
   ```bash
   gitleaks detect --source . --report-path gitleaks-report.json
   ```

5. **Dependency Audit**
   - [ ] Run pip-audit on requirements.txt
   - [ ] Update vulnerable dependencies
   - [ ] Document dependency policy (strict)
   - [ ] Set up automated dependency scanning

   **Command:**
   ```bash
   pip-audit -r requirements.txt
   ```

#### Success Criteria

- ✅ Zero SAST critical/high severity issues
- ✅ No secrets in repository
- ✅ All dependencies up to date and secure
- ✅ Type checking passes with strict mode
- ✅ Linting passes with zero errors

#### Evidence Required

```bash
# Type checking
mypy api/ --strict
# Output: Success: no issues found

# Linting
ruff check api/
# Output: All checks passed!

# Security
bandit -r api/ -ll
# Output: No issues identified

# Secrets
gitleaks detect --source .
# Output: No leaks detected

# Dependencies
pip-audit -r requirements.txt
# Output: No known vulnerabilities found
```

---

### Milestone 7: CI/CD Pipeline (Week 4) - P1

**Goal:** Automate all quality gates in CI/CD pipeline

#### Tasks

1. **GitHub Actions Workflow**
   - [ ] Create `.github/workflows/caws.yml`
   - [ ] Set up job matrix for Python versions
   - [ ] Configure caching for dependencies
   - [ ] Set up artifact storage for reports

2. **Quality Gate Jobs**
   - [ ] Static analysis job (mypy, ruff, bandit)
   - [ ] Unit test job with coverage
   - [ ] Mutation test job
   - [ ] Contract test job
   - [ ] Integration test job
   - [ ] Performance test job
   - [ ] Security scan job
   - [ ] Dependency audit job

3. **Gate Enforcement**
   - [ ] Configure required status checks
   - [ ] Set up branch protection rules
   - [ ] Configure gate thresholds
   - [ ] Set up failure notifications

4. **Provenance Integration**
   - [ ] Generate provenance on each PR
   - [ ] Compute trust score
   - [ ] Post trust score to PR
   - [ ] Store provenance artifacts

#### Success Criteria

- ✅ All quality gates run automatically on PR
- ✅ PRs blocked if gates fail
- ✅ Provenance generated and stored
- ✅ Trust score displayed on PR

#### Evidence Required

- GitHub Actions workflow file
- Successful PR run with all gates passing
- Trust score ≥ 80/100

---

### Milestone 8: Documentation & Observability (Week 4-5) - P2

**Goal:** Complete documentation and observability implementation

#### Tasks

1. **API Documentation**
   - [ ] Complete OpenAPI specification
   - [ ] Add request/response examples
   - [ ] Document error codes and messages
   - [ ] Set up interactive API docs (Swagger UI)

2. **Code Documentation**
   - [ ] Add docstrings to all public functions
   - [ ] Add module-level documentation
   - [ ] Document complex algorithms
   - [ ] Generate API reference docs

3. **Observability Implementation**
   - [ ] Implement structured logging
   - [ ] Add metrics collection (Prometheus-compatible)
   - [ ] Add distributed tracing (OpenTelemetry)
   - [ ] Create observability dashboard

4. **Runbooks**
   - [ ] Document deployment process
   - [ ] Document rollback procedures
   - [ ] Document incident response
   - [ ] Document troubleshooting guides

#### Success Criteria

- ✅ All acceptance criteria have observability
- ✅ Logs, metrics, and traces implemented
- ✅ Documentation complete and up to date
- ✅ Runbooks available for operations

---

## Prioritized Action Plan

### This Week (P0 - Critical Path)

1. **Unit Test Expansion** (3-4 days)
   - Focus on core modules: `api/model/`, `api/tts/`, `api/performance/`
   - Target: 80% branch coverage
   - Daily coverage reports

2. **Performance Testing** (2-3 days)
   - Verify A1-A4 acceptance criteria
   - Run benchmarks and store results
   - Document performance baselines

3. **Mutation Testing Setup** (1-2 days)
   - Configure mutmut
   - Run initial mutation analysis
   - Target: 50% mutation score

### Next Week (P1 - High Priority)

1. **Contract Testing** (2 days)
   - Complete provider contract tests
   - Add consumer tests for Raycast
   - Store contract artifacts

2. **Integration Testing** (3 days)
   - Test full TTS pipeline
   - Test model loading and providers
   - Test concurrent handling

3. **Static Analysis** (1 day)
   - Set up mypy, ruff, bandit
   - Fix all issues
   - Configure in CI

### Following Weeks (P2 - Standard Priority)

1. **CI/CD Pipeline** (2-3 days)
   - Create GitHub Actions workflow
   - Configure all quality gates
   - Set up provenance generation

2. **Documentation** (2-3 days)
   - Complete API docs
   - Add code documentation
   - Create runbooks

3. **Observability** (2-3 days)
   - Implement logging/metrics/traces
   - Create dashboard
   - Verify observability for A1-A4

---

## Quality Gate Matrix (Tier 2 Requirements)

| Gate | Required | Current Status | Target Date | Owner |
|------|----------|----------------|-------------|-------|
| **Static Analysis** |
| Type Checking (mypy) | ✅ MUST | ⬜ Not configured | Week 2 | TBD |
| Linting (ruff) | ✅ MUST | ⬜ Not configured | Week 2 | TBD |
| SAST (bandit) | ✅ MUST | ⬜ Not configured | Week 2 | TBD |
| Secret Scan (gitleaks) | ✅ MUST | ⬜ Not configured | Week 2 | TBD |
| Dependency Audit | ✅ MUST | ⬜ Not configured | Week 2 | TBD |
| **Unit Testing** |
| Branch Coverage ≥ 80% | ✅ MUST | ⬜ ~40% | Week 1 | TBD |
| Mutation Score ≥ 50% | ✅ MUST | ⬜ 0% | Week 1-2 | TBD |
| Property Tests | ⬜ SHOULD | ⬜ Not added | Week 1 | TBD |
| **Contract Testing** |
| Provider Tests | ✅ MUST | ⚠️ Partial | Week 2 | TBD |
| Consumer Tests | ⬜ CONDITIONAL | ⬜ Not added | Week 2 | TBD |
| **Integration Testing** |
| Full Pipeline | ✅ MUST | ⚠️ Partial | Week 2-3 | TBD |
| Real Services | ✅ MUST | ⬜ Mocked | Week 2-3 | TBD |
| **Performance Testing** |
| A1: Short TTFA | ✅ MUST | ⬜ Not verified | Week 1 | TBD |
| A2: Long RTF | ✅ MUST | ⬜ Not verified | Week 1 | TBD |
| A3: Error Handling | ✅ MUST | ⬜ Not verified | Week 1 | TBD |
| A4: Concurrent Load | ✅ MUST | ⬜ Not verified | Week 1 | TBD |
| **CI/CD** |
| Automated Gates | ✅ MUST | ⬜ Not configured | Week 4 | TBD |
| Provenance | ✅ MUST | ⚠️ Initialized | Week 4 | TBD |
| Trust Score | ✅ MUST | ⬜ Not calculated | Week 4 | TBD |

---

## Risk Factors & Mitigations

### Risk 1: Test Coverage Takes Longer Than Expected
**Likelihood:** High  
**Impact:** Medium  
**Mitigation:**
- Start with critical paths first (api/tts/core.py, api/model/loader.py)
- Use parallel test writing efforts
- Accept temporary waivers for non-critical paths

### Risk 2: Mutation Score Hard to Achieve
**Likelihood:** Medium  
**Impact:** Medium  
**Mitigation:**
- Focus on quality over quantity of tests
- Use mutation testing to guide test improvements
- Document accepted low-value mutants

### Risk 3: Performance Tests Fail on Different Hardware
**Likelihood:** Medium  
**Impact:** High  
**Mitigation:**
- Use relative performance metrics
- Establish hardware-specific baselines
- Document test environment requirements

### Risk 4: CI/CD Pipeline Complexity
**Likelihood:** Low  
**Impact:** Medium  
**Mitigation:**
- Start with simple workflow
- Iterate and add complexity gradually
- Use existing templates from CAWS

---

## Success Metrics

### Phase 1 (Weeks 1-2)
- ✅ Unit test coverage ≥ 80%
- ✅ Mutation score ≥ 50%
- ✅ All acceptance criteria verified
- ✅ Performance baselines established

### Phase 2 (Weeks 3-4)
- ✅ All static analysis gates passing
- ✅ Contract tests complete
- ✅ Integration tests complete
- ✅ CI/CD pipeline operational

### Phase 3 (Week 5+)
- ✅ Full CAWS compliance
- ✅ Trust score ≥ 80/100
- ✅ Documentation complete
- ✅ Observability implemented

---

## Next Immediate Actions

1. **Create test tracking issue** for each module in `api/`
2. **Set up coverage reporting** with pytest-cov
3. **Run initial benchmark** for A1-A4
4. **Configure mutmut** for mutation testing
5. **Schedule daily standup** to review compliance progress

---

## Resources

- CAWS Specification: `agents.md`
- Working Spec: `.caws/working-spec.yaml`
- Quality Gates Tool: `python tools/caws/gates.py`
- Benchmark Scripts: `scripts/run_bench.py`
- OpenAPI Contract: `contracts/kokoro-tts-api.yaml`
- Performance Baselines: `docs/perf/baselines.json`

---

## Approvals & Sign-offs

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Security Team
- [ ] QA Lead

---

**Last Updated:** 2025-10-09  
**Review Frequency:** Weekly  
**Next Review:** 2025-10-16

