# Documentation Cleanup Plan
> Author: @darianrosebrook  
> Status: In Progress – consolidate, modernize, and de-duplicate docs

## Goal
Bring `docs/` in line with current implementation and repo rules by:
- Removing banned emoji and “phase/week” phrasing
- Replacing outdated commands/paths with working scripts
- Condensing redundant long-form narratives into focused guides
- Archiving chat transcripts and historical plans

## Scope Summary
- Total docs scanned: 28 files (11 top-level + 17 under `docs/implementation/`)
- Recommended actions: 26 need cleanup; 2 can be kept as-is

## Top-level Docs

- benchmarking.md — Update
  - Remove emoji; keep content. Validate commands reference existing scripts.

- comprehensive-optimization-plan-for-kokoro-backend.md — Condense
  - Long narrative; convert to high-signal summary and link to current guides. Remove “Phase”/emoji.

- development.md — Update (Outdated script references)
  - Replace references to non-existent scripts (e.g. `scripts/convert_to_ort.py`, `troubleshoot_coreml.py`, `quick_benchmark.py`) with existing ones: `scripts/optimize_onnx_graph.py`, `scripts/run_benchmark.py`, `scripts/validate_optimization_performance.py`, `scripts/check_environment.py`. Remove emoji and “phase/week”.

- environment-toggles.md — Update
  - Remove emoji in headings. Re-check variable names and defaults align with `api/config.py`. Keep content.

- full-chat-convo-on-optimization.md — Archive
  - Mark as archived transcript; link only from history. Remove from navigation references.

- logging-optimization.md — Update
  - Remove emoji and “Phase” from examples; keep guidance. Ensure examples match current logging in `api/main.py`, `api/model/loader.py`.

- MISAKI_INTEGRATION_GUIDE.md — Condense
  - Remove emoji/“Phase” wording; align with Python 3.13 notes and current fallback behavior. Keep actionable env examples.

- ORT-optimization-guide.md — Update
  - Remove emoji. Replace/manual steps that reference `scripts/convert_to_ort.py` with existing scripts or clearly mark as automatic ORT path. Keep benefits/logic sections.

- production-patches.md — Keep
  - Content current; no emoji. No action required.

- python-3.13-compatibility.md — Keep
  - Content current and actionable. No action required.

- security-implementation.md — Update
  - Remove emoji. Validate endpoints/flags with `api/security.py` and startup scripts.

## Implementation Docs (`docs/implementation/`)

- benchmark-results-summary.md — Update
  - Ensure latest numbers; remove emoji. Link to `reports/` artifacts.

- branch-diff-optimization-vs-audio-daemon.md — Condense/Archive
  - If superseded by merge plans, condense to a short note or archive.

- concurrent-processing-debugging.md — Update
  - Keep; scrub emoji/“phase”. Ensure code paths match `api/tts/core.py`, `api/model/loader.py`.

- dual-session-manager-fix.md — Update
  - Keep; scrub emoji/“phase”. Verify references to current `DualSessionManager`.

- dual-session-timeout-tuning.md — Update
  - Keep; scrub emoji/“phase”. Validate current defaults.

- line-break-phonemizer-fix.md — Update
  - Keep; scrub emoji/“phase”.

- logging-deduplication-plan.md — Merge/Remove
  - Likely superseded by `logging-optimization.md`. Merge salient points, then remove.

- misaki-future-enhancements.md — Update
  - Keep; scrub emoji/“phase”. Cross-link with `MISAKI_INTEGRATION_GUIDE.md`.

- misaki-integration-fixes.md — Update
  - Keep; scrub emoji/“phase”. Ensure fixes reflect current code.

- misaki-integration-merge-plan.md — Condense
  - Replace “Phase/Day” structure with clear steps. Ensure branch status is accurate or mark historical.

- optimization-gap-analysis.md — Update
  - Replace “Phase” language; keep results. Ensure claims match `api/` state.

- optimization-implementation-plan.md — Update
  - Replace “Phase” sections with feature areas; ensure checklists match current code.

- optimization-merge-plan.md — Update
  - Keep; scrub emoji/“phase”. Confirm MPS notes align with loader/provider logic.

- optimization-progress-tracker.md — Update
  - Replace “Phase” summary headings with feature-area summaries. Keep as living checklist.

- phoneme-truncation-fix.md — Update
  - Keep; scrub emoji/“phase”.

- ttfa-optimization-results.md — Update
  - Keep; scrub emoji/“phase”. Ensure targets/metrics reflect current benchmark outputs.

## Execution Checklist

- [ ] Remove emoji across all docs (per project rule)
- [ ] Replace “phase/week” wording with specific feature-area or target wording
- [ ] Fix outdated script references in: development.md, ORT-optimization-guide.md
- [ ] Condense: comprehensive-optimization-plan, MISAKI_INTEGRATION_GUIDE, branch-diff-optimization-vs-audio-daemon, misaki-integration-merge-plan
- [ ] Merge/remove: logging-deduplication-plan (redundant)
- [ ] Archive: full-chat-convo-on-optimization.md (label clearly as historical transcript)
- [ ] Verify all command examples exist in `scripts/` or update to equivalents
- [ ] Cross-link key docs to relevant files (`api/tts/core.py`, `api/model/loader.py`, `api/performance/*`)

## Acceptance Criteria

- No banned emoji remain in documentation
- No “phase”/“week” phrasing in docs; replaced by explicit goals or feature areas
- All command snippets and file paths exist and are correct
- Redundant docs merged or archived; navigation remains clear


