# CAWS Tools & Commands Reference

**Project:** Kokoro TTS API  
**CAWS Version:** 3.4.0  
**Last Updated:** 2025-10-30

---

##  Quick Reference

### Status & Validation
```bash
# Check CAWS status
caws status

# Validate working spec
caws validate

# Run diagnostics
caws diagnose

# Run diagnostics with auto-fix
caws diagnose --fix
```

### Quality Gates
```bash
# Run all relevant quality gates
make caws-gates

# Individual gates
make caws-static      # Linting, type checking, security
make caws-unit        # Unit tests with coverage
make caws-mutation    # Mutation testing
make caws-contracts   # Contract tests + OpenAPI validation
make caws-integration # Integration tests
make caws-perf        # Performance budget validation
```

### Development Workflow
```bash
# Update progress on acceptance criteria
caws progress-update --criterion-id=A3 --status=completed

# Get iterative guidance
caws iterate --current-state="Implementing startup optimization"

# Monitor code quality
caws quality-monitor --action=code_edited --files="api/main.py"
```

---

##  Available Tools

### 1. CAWS MCP Tools (Available in Cursor)

These tools are available directly in Cursor through the CAWS MCP server:

####  Project Setup
- **`caws_init`** - Initialize a new project with CAWS setup
- **`caws_scaffold`** - Add CAWS components to an existing project

####  Validation & Status
- **`caws_validate`** - Validate working specification
- **`caws_evaluate`** - Evaluate work against CAWS quality standards
- **`caws_iterate`** - Get iterative development guidance
- **`caws_status`** - Get project health overview

#### 🩺 Health & Diagnostics
- **`caws_diagnose`** - Run health checks (with `--fix` for auto-fix)
- **`caws_hooks`** - Manage git hooks (install, remove, status)
- **`caws_provenance`** - Manage provenance tracking

####  Development Workflow
- **`caws_workflow_guidance`** - Get workflow-specific guidance (TDD, refactor, feature)
- **`caws_quality_monitor`** - Monitor code quality impact in real-time
- **`caws_progress_update`** - Update acceptance criteria progress

#### 🧪 Testing & Analysis
- **`caws_test_analysis`** - Statistical analysis for budget prediction
  - `assess-budget` - Test budget assessment
  - `analyze-patterns` - Pattern analysis
  - `find-similar` - Find similar tests

####  Compliance & Waivers
- **`caws_waiver_create`** - Create quality gate waivers
- **`caws_waivers_list`** - List active/expired waivers

####  Quality Gates
- **`caws_quality_gates`** - Run extensive quality gates
- **`caws_quality_gates_run`** - Run quality gates with options
- **`caws_quality_gates_status`** - Check quality gate status

---

### 2. Makefile Commands

Available via `make` in the project root:

#### Setup
```bash
make caws-bootstrap    # Install dependencies
make caws-validate     # Validate working spec
```

#### Quality Gates
```bash
make caws-static       # Static analysis (flake8, mypy, black, isort, security)
make caws-unit         # Unit tests with coverage (pytest)
make caws-mutation     # Mutation testing (mutmut or fallback)
make caws-contracts    # Contract tests + OpenAPI validation
make caws-integration  # Integration tests (including Testcontainers)
make caws-e2e          # End-to-end tests
make caws-a11y         # Accessibility tests (skipped for backend-api)
make caws-perf         # Performance tests + budget validation
make caws-gates        # Run all relevant quality gates
```

#### Monitoring
```bash
make monitor           # Start performance monitoring
make dashboard         # Start monitoring dashboard
```

---

### 3. Python Scripts

Available in the `scripts/` directory:

#### Quality Gates
```bash
# Simple quality gate checker
python3 scripts/simple_gates.py coverage --tier 2 --profile backend-api
python3 scripts/simple_gates.py mutation --tier 2 --profile backend-api
python3 scripts/simple_gates.py contracts --tier 2 --profile backend-api
python3 scripts/simple_gates.py trust --tier 2 --profile backend-api
python3 scripts/simple_gates.py all relevant --tier 2 --profile backend-api
```

#### Provenance Tracking
```bash
# Generate provenance manifest
python3 scripts/provenance_tracker.py

# Validate manifest
python3 scripts/provenance_tracker.py --validate

# Verbose output
python3 scripts/provenance_tracker.py --verbose
```

#### Security Scanning
```bash
# Run security scan
python3 scripts/security_scan.py

# Verbose output
python3 scripts/security_scan.py --verbose
```

#### Mutation Testing
```bash
# Run mutation tests (fallback if mutmut not available)
python3 scripts/run_mutation_tests.py
```

#### Performance Validation
```bash
# Validate performance budgets
python3 scripts/performance_budget_validator.py

# With custom URL
python3 scripts/performance_budget_validator.py --url http://localhost:8000

# Debug mode
python3 scripts/performance_budget_validator.py --debug
```

---

##  Common Workflows

### Daily Development

1. **Check Status:**
   ```bash
   caws status
   ```

2. **Update Progress:**
   ```bash
   caws progress-update --criterion-id=A1 --status=in_progress --tests-passing=5
   ```

3. **Monitor Quality:**
   ```bash
   caws quality-monitor --action=code_edited --files="$(git diff --name-only)"
   ```

### Before Committing

1. **Run Quality Gates:**
   ```bash
   make caws-gates
   ```

2. **Check Specific Gate:**
   ```bash
   make caws-static
   make caws-unit
   ```

3. **Generate Provenance:**
   ```bash
   python3 scripts/provenance_tracker.py
   ```

### Feature Completion

1. **Update Acceptance Criteria:**
   ```bash
   caws progress-update --criterion-id=A1 --status=completed --tests-passing=10 --coverage=85
   ```

2. **Evaluate Work:**
   ```bash
   caws evaluate
   ```

3. **Get Guidance:**
   ```bash
   caws iterate --current-state="Feature implemented, ready for review"
   ```

---

##  Acceptance Criteria Tracking

Your project has 6 acceptance criteria (A1-A6):

- **A1:** Streaming TTFA ≤500ms, RTF ≤1.0
- **A2:** Non-streaming API P95 ≤1000ms
- **A3:** Service ready time <10 seconds ✅
- **A4:** Memory usage ≤500MB, no leaks
- **A5:** Audio quality: LUFS -16±1, dBTP ≤-1.0
- **A6:** Trust score ≥80/100, all relevant tests pass

### Update Progress:
```bash
caws progress-update \
  --criterion-id=A3 \
  --status=completed \
  --tests-passing=25 \
  --coverage=85
```

---

##  Quality Gate Details

### Static Analysis (`make caws-static`)
- **Linting:** flake8 (max-line-length=100)
- **Type Checking:** mypy (ignore-missing-imports)
- **Formatting:** black, isort
- **Security:** Secret detection, SAST analysis

### Unit Tests (`make caws-unit`)
- **Framework:** pytest
- **Coverage:** XML, terminal, HTML reports
- **Target:** ≥80% branch coverage

### Mutation Testing (`make caws-mutation`)
- **Framework:** mutmut (with fallback)
- **Target:** ≥50% mutation score
- **Results:** `mutmut-results.json`

### Contract Tests (`make caws-contracts`)
- **OpenAPI:** Schema validation
- **Provider Tests:** API contract compliance
- **Location:** `tests/contract/`

### Integration Tests (`make caws-integration`)
- **Framework:** pytest
- **Testcontainers:** Realistic testing scenarios
- **Location:** `tests/integration/`

### Performance Tests (`make caws-perf`)
- **Benchmarks:** Automated performance testing
- **Budget Validation:** TTFA, API latency, memory
- **Location:** `tests/performance/`

---

##  Monitoring & Metrics

### Trust Score Calculation
```
Trust Score = (Coverage × 0.25) + 
              (Mutation × 0.25) + 
              (Contracts × 0.2) + 
              (A11y × 0.1) + 
              (Performance × 0.1) + 
              (Flake Rate × 0.1)
```

**Target:** ≥80/100  
**Current:** Track via `caws status`

### Performance Budgets
- **TTFA:** ≤500ms (streaming)
- **API P95:** ≤1000ms (non-streaming)
- **Memory:** ≤500MB (steady-state)
- **Startup:** <10 seconds ✅
- **RTF:** ≤1.0

---

##  Integration Points

### CI/CD
The project has GitHub Actions workflows that automatically run CAWS gates:
- `.github/workflows/caws.yml`

### Git Hooks
CAWS hooks can be installed for automatic quality gate checks:
```bash
caws hooks install
```

### IDE Integration
CAWS provides IDE integrations for:
- VS Code (workspace settings, debug configs)
- IntelliJ (run configurations)
- Windsurf (workflow files)
- GitHub Copilot (integration instructions)

---

##  Tips

1. **Start with Status:** Always check `caws status` first
2. **Run Gates Incrementally:** Test individual gates before running all relevant
3. **Update Progress Regularly:** Keep acceptance criteria up to date
4. **Use Auto-Fix:** `caws diagnose --fix` can fix common issues
5. **Monitor Quality:** Use `caws quality-monitor` during development

---

##  Troubleshooting

### Quality Gates Failing?
```bash
# Diagnose issues
caws diagnose

# Auto-fix what can be fixed
caws diagnose --fix

# Check specific gate
make caws-static
```

### Validation Warnings?
```bash
# Validate working spec
caws validate

# Check status
caws status
```

### Provenance Issues?
```bash
# Regenerate provenance
python3 scripts/provenance_tracker.py --verbose
```

---

**For detailed help on any tool:**
```bash
caws help --tool <tool-name>
caws help --category <category>
```


