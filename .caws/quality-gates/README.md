# Quality Gates - Enterprise Code Quality Enforcement

**Enterprise-grade quality gates for preventing functional duplication, architectural drift, and code quality regression.** These gates work cohesively to maintain code quality across development, CI/CD, and production environments.

## Priority Focus

Quality gates **block commits** that degrade code quality while enabling controlled development workflows through **waiver integration** and **intelligent cache management**.

## What Quality Gates Check

### 1. Functional Duplication Prevention (`check-functional-duplication.mjs`)

**Blocks:** Increases in functional duplication beyond thresholds

- More than 692 duplicate struct names (CRITICAL - compilation conflicts)
- More than 200 duplicate function names (NEW - business logic duplication)
- More than 100 duplicate trait names (NEW - interface duplication)
- More than 20 problematic duplicate filenames (excluding Rust conventions)
- Rust convention files (lib.rs, mod.rs) are expected and allowed

### 2. Naming Conventions (`check-naming.js`)

**Blocks:** Files/structs with banned modifiers indicating functional duplication

- `enhanced-*`, `unified-*`, `new-*`, `final-*`, `copy-*`, `revamp-*`, `improved-*`
- Purpose-first canonical names
- Rust convention files (lib.rs, mod.rs) are ignored

### 3. God Object Prevention (`check-god-objects.js`)

**Blocks:** Files exceeding size thresholds

- **3,000+ LOC**: Severe god objects (immediate intervention required)
- **2,000+ LOC**: Critical god objects (CI/CD block)
- ⚠️ **1,500+ LOC**: Warning (allows but flags for decomposition)
- **<1,500 LOC**: Target for long-term maintainability

## Key Features

### Waiver System Integration

Quality gates integrate with CAWS CLI waivers for controlled exceptions:

```bash
# Create waiver for architectural work
caws waivers create \
  --title="Emergency hotfix waiver" \
  --reason=emergency_hotfix \
  --gates=hidden-todo \
  --expires-at=2025-12-31T23:59:59Z

# Quality gates automatically apply waivers
node run-quality-gates.mjs  # Waived violations won't block commits
```

**Waiver Display:**

```
🔖 ACTIVE WAIVERS (1):
   WV-0001: Extended CAWS feature implementation scope (63 days left)
      Gates: budget_limit
      Reason: experimental_feature

✅ WAIVED VIOLATIONS (2) - ALLOWED:
   hidden-todo: PLACEHOLDER - Real implementation needed
   Waived by: WV-0001 (Emergency hotfix waiver)
```

### Intelligent Cache Management

Quality gates automatically manage caches for performance and reliability:

- **File Change Detection**: Clears caches when files change
- **Successful Exit Cleanup**: Clears temporary caches on completion
- **Crash Recovery**: Automatic cleanup on unexpected termination
- **Stale Lock Prevention**: Removes locks older than 5 minutes

## How It Works

### Pre-commit Hook (Local Development)

```bash
# Automatic - runs before every commit
Quality gates passed - proceeding with commit
# OR
Quality gates failed - commit blocked
Fix the violations above before committing
```

### CI/CD Pipeline

- **Job**: `Quality Gates (Crisis Response)`
- **Runs**: Before tests, after linting
- **Blocks**: PR merges if quality violations detected
- **Reports**: Detailed violation breakdown in CI logs

## Current Functional Duplication Baselines

| Metric                                      | Current  | Threshold | Status      | Priority |
| ------------------------------------------- | -------- | --------- | ----------- | -------- |
| Duplicate struct names                      | 692+     | ≤692      | CRITICAL    | HIGH     |
| Duplicate function names                    | ~200     | ≤200      | CRITICAL    | HIGH     |
| Duplicate trait names                       | ~100     | ≤100      | CRITICAL    | HIGH     |
| Problematic filename duplicates             | ~20      | ≤20       | ⚠️ MODERATE | MEDIUM   |
| Rust convention duplicates (lib.rs, mod.rs) | ~128     | N/A       | EXPECTED    | NONE     |
| God objects >3K LOC                         | 11       | 0         | CRITICAL    | HIGH     |
| God objects >2K LOC                         | Multiple | 0         | CRITICAL    | HIGH     |

**Focus: Functional duplication must decrease, Rust conventions are expected.**

## 🛠️ Usage

### Quick Start

```bash
# Run all quality gates (development mode)
node packages/quality-gates/run-quality-gates.mjs

# Run all gates in CI mode (strict enforcement)
node packages/quality-gates/run-quality-gates.mjs --ci

# Get machine-readable JSON output
node packages/quality-gates/run-quality-gates.mjs --json

# Run only specific gates
node packages/quality-gates/run-quality-gates.mjs --gates=naming,duplication
```

### Usage Scenarios

#### 1. Local Development (Interactive)

```bash
# Standard development check
node packages/quality-gates/run-quality-gates.mjs

# Focus on specific areas during development
node packages/quality-gates/run-quality-gates.mjs --gates=naming
node packages/quality-gates/run-quality-gates.mjs --gates=god_objects
node packages/quality-gates/run-quality-gates.mjs --gates=duplication
```

#### 2. CI/CD Integration

```bash
# GitHub Actions / CI pipeline
node packages/quality-gates/run-quality-gates.mjs --ci

# With step summary (GitHub Actions)
GITHUB_STEP_SUMMARY=/tmp/summary.md node packages/quality-gates/run-quality-gates.mjs --ci

# Matrix builds (test specific gates)
node packages/quality-gates/run-quality-gates.mjs --ci --gates=naming
node packages/quality-gates/run-quality-gates.mjs --ci --gates=duplication
```

#### 3. CAWS Integration

```bash
# As part of CAWS workflow
caws quality-gates --run-all

# CAWS with specific gates
caws quality-gates --gates=naming,god_objects

# CAWS in CI mode
caws quality-gates --ci --json
```

#### 4. Pre-commit Hook

```bash
# Setup pre-commit hook
echo '#!/bin/bash
node packages/quality-gates/run-quality-gates.mjs --ci' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Command Line Options

| Option           | Description                            | Example                      |
| ---------------- | -------------------------------------- | ---------------------------- |
| `--ci`           | Strict CI mode (blocks on warnings)    | `--ci`                       |
| `--json`         | Machine-readable JSON output           | `--json`                     |
| `--gates=<list>` | Run only specific gates                | `--gates=naming,duplication` |
| `--fix`          | Attempt automatic fixes (experimental) | `--fix`                      |

### Valid Gate Names

- `naming` - Naming conventions and banned modifiers
- `code_freeze` - Code freeze compliance (blocks new features)
- `duplication` - Functional duplication detection
- `god_objects` - God object size limits
- `documentation` - Documentation quality checks

### Output Formats

#### Standard Output (Development)

```
Running Quality Gates - Crisis Response Mode
==================================================
Context: COMMIT (staged files only)
Files to check: 13
==================================================

Checking naming conventions...
   No problematic naming patterns found

Checking duplication...
   Checking functional duplication...
   0 functional duplication findings (warn mode)
```

#### JSON Output (Automation)

```json
{
  "timestamp": "2025-10-28T22:01:19.090Z",
  "context": "commit",
  "files_scoped": 13,
  "warnings": [],
  "violations": []
}
```

#### GitHub Actions Summary

```markdown
# Quality Gates

- Context: commit
- Files scoped: 13
- Violations: 0
- Warnings: 1

## Violations

- **duplication/violation_type**: Description of issue
```

## When Gates Block Commits

### Naming Violations

```
FILENAME_BANNED_MODIFIER: iterations/v3/src/enhanced_parser.rs
   Filename contains banned modifier: enhanced
   Rule: No duplicate "enhanced/unified/new/final" modules
```

**Fix:** Rename to purpose-first canonical name (e.g., `parser.rs`)

### Functional Duplication Regression

```
STRUCT_DUPLICATION_REGRESSION
   Duplicate struct names increased from 692 to 700
   Issue: Functional duplication must not increase

FUNCTION_DUPLICATION_REGRESSION
   Duplicate function names increased from 200 to 210
   Issue: Business logic duplication detected

TRAIT_DUPLICATION_REGRESSION
   Duplicate trait names increased from 100 to 105
   Issue: Interface duplication detected
```

**Fix:** Extract common traits, consolidate duplicate business logic, unify interfaces

### God Object Violations

```
SEVERE_GOD_OBJECT
   File: council/src/intelligent_edge_case_testing.rs
   Size: 6348 LOC
   Limit: 3000 LOC
   Issue: SEVERE god object: 6348 LOC exceeds 3000 LOC limit
```

**Fix:** Decompose into smaller, focused modules

## Functional Duplication Response Integration

Quality gates integrate with the **Functional Duplication Prevention** plan:

1. **Automated Enforcement**: Gates prevent new functional duplication
2. **Business Logic Consolidation**: Gates detect duplicate functions and traits
3. **Interface Unification**: Gates prevent duplicate trait definitions
4. **Structural Cleanup**: Gates allow Rust conventions while blocking problematic patterns

## 📊 Monitoring & Artifacts

### Generated Artifacts

Quality gates automatically create artifacts for monitoring and automation:

```
docs-status/
├── quality-gates-report.json    # Complete results (machine-readable)
└── refactoring-progress-report.json  # Refactoring metrics
```

### JSON Report Structure

```json
{
  "timestamp": "2025-10-28T22:01:19.090Z",
  "context": "commit|push|ci",
  "files_scoped": 13,
  "warnings": [
    {
      "gate": "naming|duplication|god_objects|documentation|code_freeze",
      "type": "violation_type",
      "message": "Human-readable description",
      "file": "relative/path/to/file",
      "severity": "warn"
    }
  ],
  "violations": [
    {
      "gate": "naming|duplication|god_objects|documentation|code_freeze",
      "type": "violation_type",
      "message": "Human-readable description",
      "file": "relative/path/to/file",
      "severity": "block|fail"
    }
  ]
}
```

### Dashboard Integration

```bash
# Generate quality metrics for dashboards
node packages/quality-gates/run-quality-gates.mjs --json > quality-report.json

# Extract metrics for monitoring
jq '.violations | length' quality-report.json  # Total violations
jq '.warnings | length' quality-report.json    # Total warnings
jq '.files_scoped' quality-report.json         # Files analyzed
```

### CI/CD Integration Examples

#### GitHub Actions

```yaml
- name: Quality Gates
  run: node packages/quality-gates/run-quality-gates.mjs --ci --json > quality-report.json

- name: Upload Report
  uses: actions/upload-artifact@v3
  with:
    name: quality-gates-report
    path: quality-report.json

- name: Generate Summary
  run: GITHUB_STEP_SUMMARY=/tmp/summary.md node packages/quality-gates/run-quality-gates.mjs --ci
```

#### Jenkins Pipeline

```groovy
stage('Quality Gates') {
    steps {
        sh 'node packages/quality-gates/run-quality-gates.mjs --ci --json > quality-report.json'
        archiveArtifacts artifacts: 'quality-report.json', fingerprint: true
    }
    post {
        always {
            sh 'cat quality-report.json | jq .violations'
        }
    }
}
```

#### Local Development Dashboard

```bash
# Run gates and generate local report
node packages/quality-gates/run-quality-gates.mjs --json > docs-status/quality-gates-report.json

# View violations by gate
jq '.violations | group_by(.gate) | map({gate: .[0].gate, count: length})' docs-status/quality-gates-report.json
```

## 🔧 Troubleshooting

### Common Issues

#### Invalid Gate Names

```bash
# Error: Invalid gate names: invalid_gate
# Valid gates: naming, code_freeze, duplication, god_objects, documentation

# Fix: Use valid gate names
node packages/quality-gates/run-quality-gates.mjs --gates=naming,duplication
```

#### Documentation Linter Missing

```bash
# Error: Command failed: python3 "/Users/darianrosebrook/Desktop/Projects/caws/scripts/doc-quality-linter.py"

# Fix: Documentation quality gate requires Python script (currently missing)
# Skip documentation gate for now
node packages/quality-gates/run-quality-gates.mjs --gates=naming,code_freeze,duplication,god_objects
```

#### Context Determination Issues

```bash
# If context detection fails, gates fall back to 'commit' mode
# Override explicitly if needed
CAWS_ENFORCEMENT_CONTEXT=ci node packages/quality-gates/run-quality-gates.mjs
```

#### File Scoping Issues

```bash
# If files aren't being scoped correctly, check git status
git status --porcelain
# Ensure changes are staged for commit context
```

### Performance Optimization

```bash
# Run gates in parallel (not yet implemented)
# For now, use selective gates for faster feedback
node packages/quality-gates/run-quality-gates.mjs --gates=naming  # Fast feedback
node packages/quality-gates/run-quality-gates.mjs --gates=duplication  # Slower
```

### Debug Mode

```bash
# Enable verbose logging (if implemented)
DEBUG=quality-gates node packages/quality-gates/run-quality-gates.mjs

# Check individual gate outputs
node packages/quality-gates/check-naming.mjs
node packages/quality-gates/check-functional-duplication.mjs --context commit
```

## Emergency Overrides

### Exception-Based Overrides

Quality gates respect exceptions defined in `.caws/quality-exceptions.json`:

```bash
# View current exceptions
node packages/quality-gates/shared-exception-framework.mjs list

# Add temporary exception for specific file/pattern
node packages/quality-gates/shared-exception-framework.mjs add duplication \
  --pattern="src/temp-file.rs" \
  --reason="Temporary workaround for urgent fix" \
  --expires-days=7
```

### Temporary Bypass (Not Recommended)

```bash
# Skip pre-commit hook (only for emergencies)
git commit --no-verify

# Skip specific gates in CI
node packages/quality-gates/run-quality-gates.mjs --gates=naming,god_objects  # Skip duplication
```

**⚠️ Bypasses should only be used for critical hotfixes during crisis response.**

## 📚 Related Documentation

- **Crisis Response Plan**: `docs/refactoring.md`
- **CAWS Integration**: See CAWS documentation for workflow integration
- **Exception Framework**: `packages/quality-gates/shared-exception-framework.mjs --help`
- **Refactoring Progress**: `packages/quality-gates/monitor-refactoring-progress.mjs`

### Audit Reports

- **Naming Violations**: `docs/audits/v3-codebase-audit-2025-10/06-naming-violations.md`
- **Duplication Report**: `docs/audits/v3-codebase-audit-2025-10/02-duplication-report.md`
- **God Objects Analysis**: `docs/audits/v3-codebase-audit-2025-10/03-god-objects-analysis.md`

---

## ✅ Success Criteria

Quality gates are successful when they:

### Core Quality Enforcement

- ✅ **Block functional duplication increases** (692+ struct, 200+ function, 100+ trait names)
- ✅ **Prevent god object growth** (no files >3K LOC, strict 2K LOC limits)
- ✅ **Enforce code freeze compliance** (block new features during freezes)
- ✅ **Maintain architectural integrity** (no naming violations, proper scoping)

### Operational Excellence

- ✅ **CI/CD integration works** (JSON output, GitHub summaries, artifact generation)
- ✅ **Exception framework functions** (temporary waivers, audit trails, time-based expiry)
- ✅ **Selective gate execution** (targeted testing, faster feedback loops)
- ✅ **Machine-readable outputs** (JSON reports, dashboard integration)

### Developer Experience

- ✅ **Fast local feedback** (gate filtering, clear error messages)
- ✅ **Comprehensive monitoring** (artifacts, metrics, trend analysis)
- ✅ **Graceful error handling** (fail-open for development, fail-closed for CI)
- ✅ **Enterprise-grade reliability** (consistent contexts, no emoji output)

### Enterprise Integration

- ✅ **CAWS workflow compatible** (feature specs, progress tracking, provenance)
- ✅ **Multi-environment support** (commit/push/ci contexts, environment detection)
- ✅ **Audit compliance ready** (structured logs, violation tracking, exception management)
- ✅ **Scalable architecture** (concurrent processing ready, file scoping, performance monitoring)

**🎯 Mission Accomplished**: Enterprise-grade quality gates that prevent functional duplication while enabling controlled, monitored development workflows across all environments.
