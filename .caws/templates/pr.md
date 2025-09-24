## Summary

What changed and why (business value), link to ticket.

## Working Spec

- Risk Tier: 2
- Invariants: Audio quality, TTFA ≤ 500ms, API P95 ≤ 1000ms, Memory ≤ 500MB
- Acceptance IDs covered: A1, A2, A3, A4, A5, A6

## Contracts

- OpenAPI diff: contracts/kokoro-tts-api.yaml (v1.0 → v1.1)
- Consumer tests: ✅ TBD
- Provider verification: ✅ TBD

## Tests

- Unit: TBD tests, branch cov TBD% (target 80%)
- Mutation: TBD% (target 50%) – survived mutants listed below (rationale)
- Integration: TBD flows (Testcontainers TBD)
- E2E smoke: TBD (Playwright) – recordings & traces attached
- A11y: N/A for backend-api

## Non-functional

- API p95 TBDms (budget 1000ms)
- Streaming TTFA TBDms (budget 500ms)
- Zero SAST criticals; deps policy compliant

## Observability

- New metrics: TBD
- OTel spans: TBD with attributes

## Migration & Rollback

- DDL: TBD (idempotent)
- Kill switch env: KOKORO_DISABLE_COREML=true

## Known Limits / Follow-ups

- TBD

## Spec Delta (REQUIRED if scope changed during implementation)

<!-- Describe any changes made to scope.in/out, invariants, acceptance. Link to commit updating .caws/working-spec.yaml. -->

- none
