# CAWS Quality Gates MCP Tool - How It's Supposed to Work

**Date:** 2025-10-30  
**Issue:** MCP tool looking for missing Node.js module

---

## Expected Behavior

The `caws_quality_gates_run` MCP tool is supposed to:

1. **Call a Node.js Module:**

   - Expected path: `~/.cursor/extensions/packages/quality-gates/run-quality-gates.mjs`
   - This module should implement quality gate checks
   - Currently **missing** - causing the error

2. **Parameters Available:**

   - `gates` - Comma-separated list of gates (naming, code_freeze, duplication, god_objects, documentation)
   - `ci` - Run in CI mode (strict enforcement)
   - `json` - Output JSON format
   - `fix` - Attempt auto-fixes
   - `workingDirectory` - Working directory

3. **Should Execute:**
   - Quality gate checks (naming conventions, code freeze, duplication, god objects, documentation)
   - Return results in JSON or human-readable format
   - Optionally fix issues automatically

---

## Current Issue

### Error Encountered:

```
Error: Cannot find module '/Users/drosebrook/.cursor/extensions/packages/quality-gates/run-quality-gates.mjs'
```

### Root Cause:

- The CAWS MCP server expects a Node.js quality gates module
- This module is **not installed** in the expected location
- The module may need to be:
  1. Installed as part of CAWS setup
  2. Created manually
  3. Or the MCP tool needs to use Python scripts instead

---

## Alternative Implementation

Since the Node.js module is missing, we have **working alternatives**:

### 1. Use Makefile Commands (Current Working Solution)

```bash
make caws-gates        # Run all relevant gates
make caws-static       # Static analysis
make caws-unit         # Unit tests
make caws-mutation     # Mutation testing
# etc.
```

### 2. Use Python Scripts Directly

```bash
python3 scripts/simple_gates.py all relevant --tier 2 --profile backend-api
python3 scripts/provenance_tracker.py
python3 scripts/security_scan.py
```

### 3. Use CAWS CLI (if available)

```bash
caws validate
caws status
caws diagnose
```

---

## What the MCP Tool Should Do

Based on the parameter descriptions, `caws_quality_gates_run` should check:

1. **Naming Conventions:**

   - File naming standards
   - Variable/function naming
   - Class naming patterns

2. **Code Freeze:**

   - Check if code freeze is in effect
   - Validate changes against freeze rules

3. **Duplication:**

   - Detect code duplication
   - Suggest refactoring opportunities

4. **God Objects:**

   - Identify overly complex classes/modules
   - Flag files with too many responsibilities

5. **Documentation:**
   - Check for missing docstrings
   - Validate documentation quality
   - Check for required documentation

---

## Recommended Fix

### Option 1: Use Python Implementation (Current)

Since we have Python scripts that work, the MCP tool should:

- Delegate to `make caws-gates` or Python scripts
- Or integrate with existing Python quality gate scripts

### Option 2: Install Missing Node Module

- Check if CAWS provides a quality gates package
- Install it in the expected location
- Or update the MCP server to use a different path

### Option 3: Create Fallback Implementation

- Create a simple Node.js wrapper that calls Python scripts
- Or update MCP tool configuration to use Python directly

---

## Current Working Solution

For now, use:

```bash
# Direct Makefile commands
make caws-gates

# Or individual gates
make caws-static
make caws-unit
make caws-mutation
make caws-contracts
make caws-integration
make caws-perf

# Or Python scripts
python3 scripts/simple_gates.py all relevant --tier 2 --profile backend-api
```

These work and provide the same functionality.

---

## Next Steps

1. **Check CAWS Documentation:**

   - See if quality gates module needs separate installation
   - Check if there's a CAWS package to install

2. **Verify MCP Server Configuration:**

   - Check if paths are configurable
   - See if we can point to Python scripts instead

3. **Consider Using Python Wrapper:**

   - Create a Python script that implements the same interface
   - Use it as a bridge between MCP tool and actual gates

4. **File Issue/Request:**
   - Report missing module to CAWS maintainers
   - Or request Python-based implementation

---

**Summary:** The MCP tool expects a Node.js module that doesn't exist. Use `make caws-gates` or Python scripts instead, which provide equivalent functionality.

