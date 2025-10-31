# CAWS Quality Gates Run MCP Tool - implemented Documentation

**Date:** October 30, 2025  
**Tool:** `caws_quality_gates_run` (MCP)  
**CLI Command:** `caws quality-gates`  
**Module Location:** `~/.cursor/extensions/paths-design.caws-vscode-extension-5.1.0/bundled/quality-gates/run-quality-gates.mjs`

---

## Overview

The `caws_quality_gates_run` MCP tool runs operational quality gates to enforce code quality standards. It checks for naming conventions, code freeze compliance, duplication, god objects, and documentation quality.

---

## Parameters

### Required Parameters
- **`workingDirectory`** (string) - Working directory to run gates in (defaults to current directory)

### Optional Parameters

#### Gate Selection
- **`gates`** (string) - Comma-separated list of gates to run
  - Valid gates: `naming`, `code_freeze`, `duplication`, `god_objects`, `documentation`
  - Default: all relevant gates
  - Example: `"naming,duplication"`

#### Output Format
- **`json`** (boolean) - Output machine-readable JSON instead of human-readable text
  - Default: `false`
  - Example: `true`

#### Execution Mode
- **`ci`** (boolean) - Run in CI mode (strict enforcement, exit on violations)
  - Default: `false`
  - When `true`: Exits with error code if violations found
  - Example: `true`

#### Auto-Fix
- **`fix`** (boolean) - Attempt automatic fixes for safe violations (experimental)
  - Default: `false`
  - Example: `true`

---

## Available Gates

### 1. **Naming** (`naming`)
Checks naming conventions and banned modifiers:

- **File naming standards**
  - Detects banned modifiers: `enhanced`, `unified`, `better`, `new`, `next`, `final`, `copy`, `revamp`, `improved`
  - Validates canonical naming patterns
  
- **Variable/function naming**
  - Checks for consistency
  - Validates naming patterns

- **Class naming patterns**
  - Ensures proper class naming conventions

**Example violations:**
- Files named `enhanced_loader.py`, `new_utils.py`
- Symbols with banned modifiers

### 2. **Code Freeze** (`code_freeze`)
Enforces code freeze compliance:

- Checks if code freeze is in effect
- Validates changes against freeze rules
- Blocks commits during freeze periods

**Configuration:**
- Typically configured in `.caws/policy/` or project settings

### 3. **Duplication** (`duplication`)
Detects functional duplication:

- Identifies duplicate code patterns
- Suggests refactoring opportunities
- Prevents code duplication accumulation

**Metrics:**
- Code similarity thresholds
- Duplication percentage

### 4. **God Objects** (`god_objects`)
Prevents oversized files:

- Identifies overly complex classes/modules
- Flags files with too many responsibilities
- Enforces single responsibility principle

**Thresholds:**
- Max lines per file: 1000 (preferred: 200-500)
- Max methods per class: 10
- Max complexity per function: 10

### 5. **Documentation** (`documentation`)
Checks documentation quality:

- Missing docstrings detection
- Documentation quality validation
- Required documentation checks
- Prohibited content patterns (marketing language, etc.)

**Checks:**
- Function/method docstrings
- Class docstrings
- Module-level documentation
- API documentation completeness

---

## Usage Examples

### Via MCP Tool (Cursor)

```typescript
// Run all relevant gates
caws_quality_gates_run({
  workingDirectory: "/path/to/project"
})

// Run specific gates
caws_quality_gates_run({
  workingDirectory: "/path/to/project",
  gates: "naming,duplication"
})

// CI mode with JSON output
caws_quality_gates_run({
  workingDirectory: "/path/to/project",
  ci: true,
  json: true
})

// Attempt auto-fixes
caws_quality_gates_run({
  workingDirectory: "/path/to/project",
  fix: true
})
```

### Via CLI Command

```bash
# Run all relevant gates
caws quality-gates

# Run specific gates
caws quality-gates --gates=naming,duplication

# CI mode with JSON output
caws quality-gates --ci --json

# Attempt auto-fixes
caws quality-gates --fix

# Show help
caws quality-gates --help
```

---

## Output Format

### Human-Readable (Default)

```
CAWS Quality Gates - Enterprise Code Quality Enforcement


 Checking naming gate...
✅ Naming gate passed

 Checking duplication gate...
⚠️  Found 3 instances of code duplication
   - api/utils/helper1.py:45-60 (similar to api/utils/helper2.py:30-45)
   - api/model/loader.py:120-135 (similar to api/model/loader_old.py:100-115)

 Checking god_objects gate...
 God objects gate failed
   - api/main.py: 1250 lines (exceeds 1000 line limit)

 Summary:
   ✅ Naming: PASSED
   ⚠️  Duplication: WARNINGS (3 instances)
    God Objects: FAILED (1 file)
   ✅ Documentation: PASSED
```

### JSON Format (`--json`)

```json
{
  "status": "failed",
  "gates": {
    "naming": {
      "status": "passed",
      "violations": []
    },
    "duplication": {
      "status": "warnings",
      "violations": [
        {
          "file": "api/utils/helper1.py",
          "lines": [45, 60],
          "similar_to": "api/utils/helper2.py:30-45",
          "severity": "medium"
        }
      ]
    },
    "god_objects": {
      "status": "failed",
      "violations": [
        {
          "file": "api/main.py",
          "lines": 1250,
          "threshold": 1000,
          "severity": "high"
        }
      ]
    },
    "documentation": {
      "status": "passed",
      "violations": []
    }
  },
  "summary": {
    "total_gates": 5,
    "passed": 2,
    "warnings": 1,
    "failed": 1,
    "skipped": 0
  }
}
```

---

## Output Locations

### Console Output
- Human-readable results printed to stdout
- Error messages and warnings to stderr

### Artifacts Generated
- **`docs-status/quality-gates-report.json`** - Full JSON report (always generated)
- **GitHub Actions Summary** - Automatic step summary when `GITHUB_STEP_SUMMARY` is set

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | all relevant gates passed (or warnings only in non-CI mode) |
| `1` | One or more gates failed (or any violations in CI mode) |
| `2` | Execution error (tool failure, not gate failure) |

---

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run CAWS Quality Gates
  run: |
    caws quality-gates --ci --json
  continue-on-error: false
```

### Pre-Commit Hook

```bash
#!/bin/bash
# Run quality gates before commit
caws quality-gates --ci || exit 1
```

---

## Configuration

### Gate Thresholds

Gate thresholds are typically configured in:
- `.caws/policy/policy.yaml` - Policy configuration
- `.caws/working-spec.yaml` - Working specification
- Project-specific configuration files

### Enforcement Levels

- **Development Mode** (default): Warnings shown, but doesn't block
- **CI Mode** (`--ci`): Strict enforcement, exits on violations

---

## Common Workflows

### Daily Development

```bash
# Quick check before committing
caws quality-gates --gates=naming,duplication
```

### Pre-Commit

```bash
# Full check with auto-fix
caws quality-gates --fix
```

### CI Pipeline

```bash
# Strict enforcement
caws quality-gates --ci --json > quality-gates-report.json
```

### Feature Completion

```bash
# Full quality check
caws quality-gates
```

---

## Troubleshooting

### Module Not Found Error

**Error:**
```
Error: Cannot find module '/Users/.../.cursor/extensions/packages/quality-gates/run-quality-gates.mjs'
```

**Solution:**
The module exists at:
```
~/.cursor/extensions/paths-design.caws-vscode-extension-5.1.0/bundled/quality-gates/run-quality-gates.mjs
```

This is a path resolution issue in the MCP server. Use the CLI command directly:
```bash
caws quality-gates
```

### Gates Not Running

**Check:**
1. Working directory is correct
2. CAWS is initialized (`caws status`)
3. Policy file exists (`.caws/policy.yaml`)

**Fix:**
```bash
caws diagnose
caws validate
```

### False Positives

**Documentation gate too strict:**
- Review documentation requirements in policy
- Use waivers for acceptable exceptions:
  ```bash
  caws waivers create --gate=documentation --reason="..."
  ```

**Duplication false positives:**
- Review similarity thresholds
- Adjust in policy configuration

---

## Related Tools

- **`caws_quality_gates`** - Run extensive quality gates (same as `caws_quality_gates_run` with default parameters)
- **`caws_quality_gates_status`** - Check quality gate status
- **`caws_validate`** - Validate working specification
- **`caws_diagnose`** - Run health checks

---

## See Also

- `docs/CAWS_TOOLS_REFERENCE.md` - implemented CAWS tools reference
- `docs/optimization/CAWS_QUALITY_GATES_RESULTS.md` - Recent execution results
- `docs/optimization/CAWS_MCP_QUALITY_GATES_EXPLANATION.md` - MCP tool explanation

---

**Last Updated:** October 30, 2025  
**CAWS Version:** 3.4.0  
**MCP Server:** paths-design.caws-vscode-extension-5.1.0


