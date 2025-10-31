# Quality Gates Templates

This directory contains template files for CAWS quality gates configuration and build artifacts.

## Files

### Policy/Config Files (Editable by Humans)

- **`.caws/code-freeze.yaml`** - Policy for the code-freeze gate (types, keywords, budgets, allowlists)
- **`.caws/refactor-targets.yaml`** - Week/phase targets used by the refactor progress monitor
- **`.caws/refactor-baselines.yaml`** - Initial/baseline comparison anchors
- **`.caws/quality-exceptions.json`** - Shared exception framework store (all gates)
- **`.caws/naming-exceptions.json`** - Narrow, time-boxed exceptions specific to the naming gate
- **`.caws/file-scope.yaml`** - File-scope policy (tune traversal without editing scope manager)
- **`duplication.qualitygatesrc.yaml`** - Configuration for the duplication gate (thresholds, patterns, languages)
- **`godObject.qualitygatesrc.yaml`** - Configuration for the god objects gate (thresholds, budgets, exclusions)

### Build Artifacts (Written by Scripts; Machine-Readable)

- **`docs-status/refactoring-progress-report.json`** - Current snapshot from the refactor progress monitor
- **`docs-status/refactoring-progress-history.jsonl`** - Time-series append-only log (one JSON object per line)
- **`docs-status/quality-gates-report.json`** - Aggregate output from the quality-gates runner

## Usage

These templates are used when initializing a new CAWS project or when setting up quality gates in an existing project. The policy files can be customized by project maintainers, while the build artifacts are generated automatically by the quality gates system.

## Gate-Specific Configuration

The `duplication.qualitygatesrc.yaml` and `godObject.qualitygatesrc.yaml` files provide comprehensive configuration for their respective quality gates:

- **Duplication Gate**: Controls similarity thresholds, language-specific patterns, and test file handling
- **God Objects Gate**: Manages file size limits, known large files, remediation budgets, and exclusion patterns

These files should be customized based on your project's specific needs and coding standards.
