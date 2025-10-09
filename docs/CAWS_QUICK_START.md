# CAWS Quick Start Guide

**Author:** @darianrosebrook  
**Project:** Kokoro ONNX TTS  
**CAWS Version:** 1.0

## Daily Workflow

### Before Starting Work

```bash
# Check project health
caws status

# Review current working spec
cat .caws/working-spec.yaml
```

### During Development

```bash
# Mark acceptance criterion as in-progress
caws progress update --criterionId A1 --status in_progress

# Run tests locally
pytest tests/unit/ --cov=api
python scripts/run_bench.py --preset=short --stream --trials=3

# Check quality gates
python tools/caws/gates.py
```

### Before Committing

```bash
# Run static checks
ruff check api/ && mypy api/ && bandit -r api/ -ll

# Validate spec (if modified)
caws validate

# Git hooks will run automatically on commit
git add .
git commit -m "feat: your changes"
```

### Opening a PR

1. Copy PR template: `.caws/templates/pr.md`
2. Fill in acceptance criteria evidence
3. Include benchmark results from `artifacts/bench/`
4. Link to any spec changes

## Common Commands

| Command | Purpose |
|---------|---------|
| `caws status` | View project health |
| `caws validate` | Validate working spec |
| `caws diagnose` | Run health checks |
| `caws diagnose --fix` | Auto-fix issues |
| `caws provenance show` | View provenance history |
| `python tools/caws/gates.py` | Check quality gates |

## Quality Gates

### Tier 2 Requirements

- ✅ Branch coverage ≥ 80%
- ✅ Mutation score ≥ 50%
- ✅ Contract tests passing
- ✅ Integration tests passing
- ✅ Performance budgets met
- ✅ Zero SAST criticals
- ✅ Secret scan clean

## Performance Budgets

| Metric | Target |
|--------|--------|
| TTFA (short) | ≤ 0.50s p95 |
| RTF (long) | ≤ 0.60 p95 |
| Underruns | ≤ 1 per 10 min |
| Memory | ±300 MB RSS |

## Troubleshooting

**Validation fails:**
```bash
caws validate
# Fix errors in .caws/working-spec.yaml
```

**Git hooks fail:**
```bash
# Check what failed
cat .git/hooks/pre-commit
# Fix issues or use --no-verify (not recommended)
```

**Performance tests fail:**
```bash
# Check models are present
ls optimized_models/
# Review baselines
cat docs/perf/baselines.json
```

## Resources

- Full Setup Guide: `docs/CAWS_SETUP.md`
- Working Spec: `.caws/working-spec.yaml`
- Project Config: `.caws.yml`
- Optimization Blueprint: `docs/kokoro-tts-optimization-blueprint.md`
- API Contract: `contracts/kokoro-tts-api.yaml`

---

**Need help?** Run `caws help` or see `docs/CAWS_SETUP.md`

