# CAWS Compliance Checklist

**Author:** @darianrosebrook  
**Project:** Kokoro ONNX TTS  
**Working Spec:** KOKORO-001  
**Last Updated:** 2025-10-09

---

## Week 1: Foundation & Core Testing (P0)

### Day 1-2: Unit Test Expansion

**api/model/** - Model Loading & Providers
- [ ] `api/model/loader.py` - ONNX model loading
- [ ] `api/model/providers.py` - Provider selection logic
- [ ] `api/model/sessions/session_manager.py` - Session lifecycle
- [ ] `api/model/initialization/initializer.py` - Model initialization
- [ ] `api/model/memory/monitor.py` - Memory monitoring

**api/tts/** - TTS Core Functionality
- [ ] `api/tts/core.py` - Core TTS generation
- [ ] `api/tts/streaming_optimizer.py` - Streaming optimization
- [ ] `api/tts/text_processing.py` - Text preprocessing
- [ ] `api/tts/misaki_processing.py` - Misaki G2P integration
- [ ] `api/tts/audio_variation_handler.py` - Audio variation

**api/performance/** - Performance Monitoring
- [ ] `api/performance/ttfa_monitor.py` - TTFA tracking
- [ ] `api/performance/request_tracker.py` - Request tracking
- [ ] `api/performance/stats.py` - Statistics collection
- [ ] `api/performance/optimization.py` - Performance optimization

**api/routes/** - API Endpoints
- [ ] `api/routes/performance.py` - Performance endpoints
- [ ] `api/routes/benchmarks.py` - Benchmark endpoints

**Coverage Target**
- [ ] Run coverage report: `pytest tests/unit/ --cov=api --cov-report=html`
- [ ] Verify branch coverage ≥ 80%
- [ ] Generate coverage badge
- [ ] Store coverage report in artifacts

### Day 2-3: Performance Testing (A1-A4)

**A1: Short Text TTFA**
- [ ] Create test with 140-char input
- [ ] Run 100 trials
- [ ] Measure TTFA p95
- [ ] Verify ≤ 0.50s
- [ ] Store results: `artifacts/bench/$(date +%Y-%m-%d)/A1-short-ttfa.json`
- [ ] Evidence: `python scripts/run_bench.py --preset=short --trials=100`

**A2: Long Text RTF**
- [ ] Create test with long paragraph (~500 chars)
- [ ] Run 100 trials with streaming
- [ ] Measure RTF p95
- [ ] Verify ≤ 0.60
- [ ] Check for underruns (≤1 per 10 min)
- [ ] Verify monotonic playback
- [ ] Store results: `artifacts/bench/$(date +%Y-%m-%d)/A2-long-rtf.json`
- [ ] Evidence: `python scripts/run_bench.py --preset=long --stream --trials=100`

**A3: Error Handling**
- [ ] Test malformed UTF-8 input
- [ ] Test unsupported characters
- [ ] Test empty text
- [ ] Test text exceeding max_length
- [ ] Verify clear error messages
- [ ] Verify no PII in logs
- [ ] Verify no state corruption
- [ ] Evidence: `pytest tests/integration/test_error_handling.py -v`

**A4: Concurrent Load**
- [ ] Run 10 concurrent requests
- [ ] Monitor RSS memory during test
- [ ] Verify memory envelope ±300 MB
- [ ] Measure TTFA/RTF stability
- [ ] Verify no performance degradation
- [ ] Store results: `artifacts/bench/$(date +%Y-%m-%d)/A4-load.json`
- [ ] Evidence: `python scripts/run_bench.py --preset=load --concurrent=10`

**Audio Quality**
- [ ] Test loudness: -16 LUFS ±1 LU
- [ ] Test dBTP ≤ -1.0 dB
- [ ] Set up pyloudnorm or ffmpeg analysis
- [ ] Create automated audio quality tests

### Day 3-4: Mutation Testing Setup

**Configuration**
- [ ] Update `mutmut_config.py` with test command
- [ ] Define paths to mutate (api/ excluding tests)
- [ ] Configure mutation testing workflow
- [ ] Document mutation testing process

**Execution**
- [ ] Run: `mutmut run --paths-to-mutate=api/model/`
- [ ] Run: `mutmut run --paths-to-mutate=api/tts/`
- [ ] Run: `mutmut run --paths-to-mutate=api/performance/`
- [ ] Run: `mutmut run --paths-to-mutate=api/routes/`
- [ ] Generate report: `mutmut results`
- [ ] Generate HTML: `mutmut html`

**Analysis**
- [ ] Analyze survived mutants
- [ ] Identify weak test coverage areas
- [ ] Add tests for survived mutants
- [ ] Re-run mutation tests
- [ ] Verify mutation score ≥ 50%

---

## Week 2: Contract & Integration Testing (P1)

### Day 5-6: Contract Testing

**Provider Contract Tests (OpenAPI)**
- [ ] Validate `/v1/audio/speech` endpoint schema
- [ ] Validate `/health` endpoint schema
- [ ] Validate `/status` endpoint schema
- [ ] Validate `/voices` endpoint schema
- [ ] Test request/response shapes
- [ ] Test error responses match schema
- [ ] Test content-type headers
- [ ] Test streaming responses
- [ ] Evidence: `pytest tests/contract/ -v`

**Consumer Contract Tests (Raycast)**
- [ ] Set up MSW for API mocking
- [ ] Mock all API endpoints
- [ ] Test Raycast client against mocks
- [ ] Verify error handling
- [ ] Validate request construction
- [ ] Store contract artifacts in `contracts/`

**Contract Versioning**
- [ ] Set up version tracking
- [ ] Document breaking vs non-breaking changes
- [ ] Create contract changelog
- [ ] Establish evolution policy

### Day 7-9: Integration Testing

**Model Integration**
- [ ] Test ONNX model loading (real models)
- [ ] Test Core ML EP initialization
- [ ] Test provider fallback (Core ML → CPU)
- [ ] Test quantization fallback (INT8 → FP16)
- [ ] Test session lifecycle management
- [ ] Test concurrent session handling

**TTS Pipeline Integration**
- [ ] Test end-to-end TTS (text → audio)
- [ ] Test Misaki G2P integration
- [ ] Test eSpeak fallback
- [ ] Test audio format conversions
- [ ] Test streaming pipeline
- [ ] Test chunk sequencing and buffering

**API Integration**
- [ ] Test full request/response cycle
- [ ] Test concurrent request handling
- [ ] Test rate limiting (if implemented)
- [ ] Test error propagation
- [ ] Test middleware chain
- [ ] Test performance monitoring integration

**Test Data**
- [ ] Create deterministic fixtures
- [ ] Use test-size ONNX models
- [ ] Create seed data
- [ ] Document setup/teardown
- [ ] Evidence: `pytest tests/integration/ -v`

### Day 9-10: Static Analysis

**Type Checking**
- [ ] Install and configure mypy
- [ ] Add type hints to public APIs
- [ ] Fix all mypy errors
- [ ] Run: `mypy api/ --strict`
- [ ] Configure mypy in CI

**Linting**
- [ ] Install and configure ruff
- [ ] Fix all linting errors
- [ ] Run: `ruff check api/ --fix`
- [ ] Document linting rules
- [ ] Configure pre-commit hook

**Security (SAST)**
- [ ] Install and configure Bandit
- [ ] Fix high/medium severity issues
- [ ] Document accepted low-severity issues
- [ ] Run: `bandit -r api/ -ll -f json -o security-scan-results.json`
- [ ] Configure Bandit in CI

**Secret Scanning**
- [ ] Install gitleaks or trufflehog
- [ ] Scan repository history
- [ ] Run: `gitleaks detect --source . --report-path gitleaks-report.json`
- [ ] Set up pre-commit hook
- [ ] Document secret management policy

**Dependency Audit**
- [ ] Install pip-audit
- [ ] Run: `pip-audit -r requirements.txt`
- [ ] Update vulnerable dependencies
- [ ] Document dependency policy (strict)
- [ ] Configure automated scanning

---

## Week 3-4: CI/CD & Automation (P1-P2)

### Day 11-13: CI/CD Pipeline

**GitHub Actions Workflow**
- [ ] Create `.github/workflows/caws.yml`
- [ ] Set up job matrix for Python versions
- [ ] Configure dependency caching
- [ ] Set up artifact storage

**Quality Gate Jobs**
- [ ] Job: Static analysis (mypy, ruff, bandit)
- [ ] Job: Unit tests with coverage
- [ ] Job: Mutation tests
- [ ] Job: Contract tests
- [ ] Job: Integration tests
- [ ] Job: Performance tests
- [ ] Job: Security scan
- [ ] Job: Dependency audit

**Gate Enforcement**
- [ ] Configure required status checks
- [ ] Set up branch protection rules
- [ ] Configure gate thresholds
- [ ] Set up failure notifications

**Provenance**
- [ ] Generate provenance on each PR
- [ ] Compute trust score
- [ ] Post trust score to PR
- [ ] Store provenance artifacts

### Day 14-16: Documentation

**API Documentation**
- [ ] Complete OpenAPI specification
- [ ] Add request/response examples
- [ ] Document error codes and messages
- [ ] Set up Swagger UI
- [ ] Generate API reference docs

**Code Documentation**
- [ ] Add docstrings to all public functions
- [ ] Add module-level documentation
- [ ] Document complex algorithms
- [ ] Follow Python docstring conventions

**Runbooks**
- [ ] Document deployment process
- [ ] Document rollback procedures
- [ ] Document incident response
- [ ] Document troubleshooting guides

### Day 17-19: Observability

**Logging**
- [ ] Implement structured logging
- [ ] Add request start/end logs
- [ ] Add TTFA per request
- [ ] Add RTF per request
- [ ] Add error logs with context
- [ ] Verify no PII in logs

**Metrics**
- [ ] Set up Prometheus-compatible metrics
- [ ] Add `tts_requests_total`
- [ ] Add `tts_ttfa_seconds`
- [ ] Add `tts_rtf_ratio`
- [ ] Add `tts_errors_total`
- [ ] Add `tts_underruns_total`

**Tracing**
- [ ] Set up OpenTelemetry
- [ ] Add `/v1/tts` span
- [ ] Add `text_length` attribute
- [ ] Add `voice` attribute
- [ ] Add `streaming` attribute

**Dashboard**
- [ ] Create observability dashboard
- [ ] Add TTFA monitoring
- [ ] Add RTF monitoring
- [ ] Add error rate monitoring
- [ ] Add memory monitoring

---

## Week 5: Final Validation & Compliance

### Day 20-21: Final Review

**Quality Gate Validation**
- [ ] Run all static analysis gates
- [ ] Run all test suites
- [ ] Generate final coverage report
- [ ] Generate final mutation report
- [ ] Verify all acceptance criteria
- [ ] Generate final performance benchmarks

**Trust Score Calculation**
- [ ] Run: `python tools/caws/gates.py`
- [ ] Verify trust score ≥ 80/100
- [ ] Address any failing gates
- [ ] Generate final provenance manifest

**Documentation Review**
- [ ] Review all documentation for completeness
- [ ] Update CHANGELOG
- [ ] Update README
- [ ] Review API documentation
- [ ] Review runbooks

**Final Checklist**
- [ ] All unit tests passing
- [ ] Branch coverage ≥ 80%
- [ ] Mutation score ≥ 50%
- [ ] All contract tests passing
- [ ] All integration tests passing
- [ ] All performance tests passing (A1-A4)
- [ ] All static analysis clean
- [ ] No security issues
- [ ] No vulnerable dependencies
- [ ] CI/CD pipeline operational
- [ ] Provenance tracking active
- [ ] Trust score ≥ 80/100
- [ ] Documentation complete
- [ ] Observability implemented

---

## Daily Standup Template

**Date:** YYYY-MM-DD

**Yesterday:**
- [ ] What did we complete?
- [ ] Evidence collected?

**Today:**
- [ ] What are we working on?
- [ ] Expected completion?

**Blockers:**
- [ ] Any blockers or risks?

**Compliance %:** XX%

---

## Weekly Review Template

**Week of:** YYYY-MM-DD

**Completed:**
- [ ] List completed milestones
- [ ] Evidence artifacts generated

**In Progress:**
- [ ] Current work items

**Blocked:**
- [ ] Any blockers

**Next Week:**
- [ ] Planned work

**Metrics:**
- Current compliance: XX%
- Target compliance: XX%
- On track: Yes/No

---

## Evidence Tracking

### Unit Tests
- [ ] Coverage report stored: `artifacts/coverage/report.html`
- [ ] Coverage meets threshold: ≥80%
- [ ] Date verified: YYYY-MM-DD

### Mutation Tests
- [ ] Mutation report stored: `mutmut-results.html`
- [ ] Mutation score meets threshold: ≥50%
- [ ] Date verified: YYYY-MM-DD

### Performance Tests
- [ ] A1 results stored: `artifacts/bench/YYYY-MM-DD/A1-short-ttfa.json`
- [ ] A2 results stored: `artifacts/bench/YYYY-MM-DD/A2-long-rtf.json`
- [ ] A3 results stored: `artifacts/bench/YYYY-MM-DD/A3-errors.json`
- [ ] A4 results stored: `artifacts/bench/YYYY-MM-DD/A4-load.json`
- [ ] All criteria met: Yes/No
- [ ] Date verified: YYYY-MM-DD

### Static Analysis
- [ ] Type check clean: `mypy api/ --strict`
- [ ] Linting clean: `ruff check api/`
- [ ] SAST clean: `bandit -r api/ -ll`
- [ ] Secrets clean: `gitleaks detect`
- [ ] Dependencies clean: `pip-audit`
- [ ] Date verified: YYYY-MM-DD

### Contract Tests
- [ ] Provider tests passing: `pytest tests/contract/ -v`
- [ ] Consumer tests passing: (Raycast tests)
- [ ] Contract artifacts stored: `contracts/`
- [ ] Date verified: YYYY-MM-DD

### Integration Tests
- [ ] All integration tests passing: `pytest tests/integration/ -v`
- [ ] Using real components: Yes/No
- [ ] Date verified: YYYY-MM-DD

---

## Command Reference

```bash
# Coverage
pytest tests/unit/ --cov=api --cov-report=html --cov-branch --cov-fail-under=80

# Mutation Testing
mutmut run --paths-to-mutate=api/
mutmut results
mutmut html

# Static Analysis
mypy api/ --strict
ruff check api/ --fix
bandit -r api/ -ll -f json -o security-scan-results.json
gitleaks detect --source . --report-path gitleaks-report.json
pip-audit -r requirements.txt

# Contract Tests
pytest tests/contract/ -v

# Integration Tests
pytest tests/integration/ -v

# Performance Tests
python scripts/run_bench.py --preset=short --trials=100
python scripts/run_bench.py --preset=long --stream --trials=100
python scripts/run_bench.py --preset=load --concurrent=10

# CAWS Commands
caws status
caws validate
caws diagnose
python tools/caws/gates.py
```

---

**Progress Tracking:** Update this checklist daily  
**Review Frequency:** Daily standup + Weekly review  
**Target Completion:** 2025-11-06

