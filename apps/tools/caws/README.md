## CAWS (Code Assessment Workflow System) Tools

A comprehensive suite of tools for code quality assessment, compliance checking, and trust scoring integrated into your development workflow.

## 🎯 Overview

CAWS provides automated quality gates, performance monitoring, test variance detection, and spec-to-test traceability to ensure high-quality code delivery.

---

## 📦 Architecture

### Shared Components (`shared/`)

All CAWS tools are built on a unified architecture with shared utilities:

- **`base-tool.ts`** - Base class providing common functionality
- **`types.ts`** - Centralized type definitions
- **`validator.ts`** - Validation utilities
- **`config-manager.ts`** - Configuration management
- **`gate-checker.ts`** - Gate checking logic
- **`waivers-manager.ts`** - Waivers management

---

## 🔧 Core Tools

### Quality Gates

#### `gates.js`

Basic gate enforcement for coverage, mutation, trust score, and budget.

```bash
node gates.js tier 2
node gates.js coverage 0.85
node gates.js mutation 0.60
node gates.js trust 85
node gates.js budget 20 800
```

#### `validate.js`

Validates working specifications and project structure.

```bash
node validate.js .caws/working-spec.yaml
```

### Provenance & Attestations

#### `provenance.js`

Generates provenance information for CAWS projects.

```bash
node provenance.js
```

#### `attest.js`

Generates SBOM and SLSA-style attestations.

```bash
node attest.js /path/to/project .agent
```

---

## 🚀 Advanced Tools

### Flake Detection

#### `flake-detector.ts`

Monitors test variance and quarantines flaky tests automatically.

```bash
npx tsx flake-detector.ts detect
npx tsx flake-detector.ts quarantine "test name"
npx tsx flake-detector.ts release "test name"
npx tsx flake-detector.ts status
```

**Features:**

- Analyzes test run variance
- Identifies intermittently failing tests
- Automatic quarantine based on flake rate threshold (15%)
- Tracks historical test data
- Variance score calculation

---

### Spec-to-Test Mapping

#### `spec-test-mapper.ts`

Links acceptance criteria to actual test cases for full traceability.

```bash
npx tsx spec-test-mapper.ts report
npx tsx spec-test-mapper.ts save docs/spec-coverage.md
```

**Features:**

- Maps acceptance criteria to test files
- Generates coverage reports
- Identifies uncovered criteria
- Supports multiple test types (unit, integration, e2e, property-based)
- Keyword-based test discovery

---

### Performance Budget Validation

#### `perf-budgets.ts`

Validates API performance against working spec budgets.

```bash
npx tsx perf-budgets.ts
npx tsx perf-budgets.ts --real-data
```

**Features:**

- Validates p95 latency against budgets
- Supports mock and real performance data
- Per-endpoint tracking
- Deviation percentage reporting
- CI/CD integration

---

### Configuration Management

#### `config.ts`

Comprehensive configuration management with YAML import/export.

```bash
npx tsx config.ts get
npx tsx config.ts get gates
npx tsx config.ts set gates.coverage.enabled false
npx tsx config.ts export > config.yaml
npx tsx config.ts import config.yaml
npx tsx config.ts features
npx tsx config.ts paths
npx tsx config.ts gates
npx tsx config.ts tools
```

**Features:**

- Get/set configuration values
- Import/export YAML
- Section-specific views
- Feature flag management
- Path configuration

---

### Waivers Management

#### `waivers.js`

Manages time-boxed waivers for quality gates.

```bash
node waivers.js create HOTFIX-001 "Urgent fix" "mutation,coverage" urgent_fix "senior-dev" 3
node waivers.js list
node waivers.js check PROJECT-123 mutation
node waivers.js cleanup
```

**Features:**

- Time-boxed exemptions
- Multiple gate support
- Approval tracking
- Automatic expiry
- Project-specific waivers

---

## 📊 Test Quality Tools

### `test-quality.js`

Analyzes test meaningfulness beyond coverage.

```bash
node test-quality.js analyze tests .caws/working-spec.yaml
```

**Checks:**

- Meaningful assertions
- Spec coverage
- Property-based tests
- Edge case coverage
- Weak test detection

---

### `property-testing.js`

Property-based testing utilities.

---

### `mutant-analyzer.js`

Analyzes mutation testing results.

---

## 🌍 Multi-Language Support

### `language-adapters.ts`

Adapts CAWS to different programming languages with language-specific tools and thresholds.

```bash
npx tsx language-adapters.ts detect
npx tsx language-adapters.ts list
npx tsx language-adapters.ts config python
npx tsx language-adapters.ts tier rust 2
```

**Supported Languages:**

- **TypeScript/JavaScript** - vitest, stryker, pact, eslint
- **Python** - pytest, mutmut, schemathesis, ruff
- **Rust** - cargo test/tarpaulin/mutants/clippy
- **Go** - go test, golangci-lint
- **Java** - maven (jacoco, pitest, pact, checkstyle)

**Features:**

- Auto-detect project language
- Language-specific tool configurations
- Adjusted tier policies per language
- Fallback strategies for unavailable tools
- Tool availability checking

---

## 🔒 Security & Compliance

### `security-provenance.ts`

Cryptographic signing, SLSA attestations, and security scanning.

```bash
npx tsx security-provenance.ts sign .agent/provenance.json
npx tsx security-provenance.ts verify .agent/provenance.json <signature>
npx tsx security-provenance.ts scan .
npx tsx security-provenance.ts slsa <commit-hash>
```

**Features:**

- Cryptographic artifact signing
- Signature verification
- Model provenance tracking
- Prompt hashing for audit trails
- Secret scanning
- SAST integration placeholder
- Dependency scanning
- SLSA attestation generation

---

### `prompt-lint.js`

Validates prompts for secrets and tool allowlisting.

**Features:**

- Secret pattern detection
- Tool allowlist validation
- Provenance hashing

---

## 📊 Legacy Code Migration

### `legacy-assessment.ts`

Assess legacy code for CAWS migration and generate phased migration plans.

```bash
npx tsx legacy-assessment.ts assess src/auth
npx tsx legacy-assessment.ts plan .
```

**Features:**

- Complexity analysis (cyclomatic complexity)
- Current coverage assessment
- Change frequency analysis
- Dependency analysis
- Recommended tier inference
- Migration priority calculation
- Quick wins identification
- Effort estimation
- Phased migration plan generation
- Critical path identification

**Assessment Metrics:**

- **Complexity** - Average cyclomatic complexity per file
- **Coverage** - Current test coverage percentage
- **Change Frequency** - How often the module changes
- **Dependencies** - Average imports per file
- **Recommended Tier** - Suggested CAWS tier based on risk
- **Migration Priority** - High/Medium/Low priority
- **Estimated Effort** - Small (2 days), Medium (5 days), Large (10 days)

---

## 📋 Configuration

### Default Configuration Structure

```json
{
  "version": "1.0.0",
  "environment": "development",
  "gates": {
    "coverage": {
      "enabled": true,
      "thresholds": {
        "statements": 80,
        "branches": 75,
        "functions": 80,
        "lines": 80
      }
    },
    "mutation": {
      "enabled": true,
      "thresholds": {
        "killed": 70,
        "survived": 30
      }
    },
    "contracts": {
      "enabled": true,
      "required": true
    }
  },
  "tiers": {
    "1": {
      "min_branch": 0.9,
      "min_coverage": 0.9,
      "min_mutation": 0.8,
      "requires_contracts": true
    },
    "2": {
      "min_branch": 0.8,
      "min_coverage": 0.8,
      "min_mutation": 0.7,
      "requires_contracts": true
    },
    "3": {
      "min_branch": 0.7,
      "min_coverage": 0.7,
      "min_mutation": 0.6,
      "requires_contracts": false
    }
  }
}
```

---

## 🎯 Tier Policies

| Tier | Branch Coverage | Mutation Score | Contracts | Manual Review |
| ---- | --------------- | -------------- | --------- | ------------- |
| 1    | ≥90%            | ≥80%           | Required  | Required      |
| 2    | ≥80%            | ≥70%           | Required  | Optional      |
| 3    | ≥70%            | ≥60%           | Optional  | Optional      |

---

## 🔄 Workflow Integration

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Run CAWS quality gates
npx tsx apps/tools/caws/flake-detector.ts detect
npx tsx apps/tools/caws/spec-test-mapper.ts report
node apps/tools/caws/gates.js coverage 2
node apps/tools/caws/gates.js mutation 2
```

### CI/CD Pipeline

```yaml
# .github/workflows/caws.yml
name: CAWS Quality Gates

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run CAWS Gates
        run: |
          npm test -- --coverage
          npx tsx apps/tools/caws/flake-detector.ts detect
          npx tsx apps/tools/caws/perf-budgets.ts
          node apps/tools/caws/gates.js tier 2
```

---

## 📚 Documentation

- [Hooks & Agent Workflows Guide](../../docs/guides/hooks-and-agent-workflows.md)
- [Hook Strategy](../../docs/HOOK_STRATEGY.md)
- [Developer Guide](../../docs/caws-developer-guide.md)
- [API Documentation](../../docs/api/)

---

## 🤝 Contributing

When adding new CAWS tools:

1. **Extend CawsBaseTool** - Use the shared base class
2. **Use shared types** - Import from `shared/types.ts`
3. **Leverage validators** - Use `CawsValidator`
4. **Utilize config manager** - Use `CawsConfigManager`
5. **Follow gate checker** - Use `CawsGateChecker`

---

## 📝 License

Part of the CAWS project - see main project LICENSE

---

## 🙏 Credits

**Author:** @darianrosebrook

Built with insights from production CAWS implementations in:

- obsidian-rag project
- Animator project
- Portfolio project
