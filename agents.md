# CAWS v1.0 — Engineering-Grade Operating System for Coding Agents

## Purpose

Our "engineering-grade" operating system for coding agents that (1) forces planning before code, (2) bakes in tests as first-class artifacts, (3) creates explainable provenance, and (4) enforces quality via automated CI gates. It's expressed as a Working Spec + Ruleset the agent MUST follow, with schemas, templates, scripts, and verification hooks that enable better collaboration between agent and our human in the loop.

## Normative Language

This document uses RFC-2119/BCP-14 keywords:

- **MUST/SHALL**: Absolute requirement, enforced by automation
- **SHOULD**: Strong recommendation, may be waived with explicit rationale
- **MAY**: Optional, profile or context-dependent

## Profiles

CAWS supports different project profiles with tailored gate requirements:

- **web-ui**: Frontend applications with user interfaces
- **backend-api**: Server applications exposing APIs
- **library**: Reusable code packages
- **cli**: Command-line tools

## 1) Core Framework

### Risk Tiering → Drives Rigor

#### Risk Tier Examples

• **Tier 1**: Authentication flows, payment processing, data migrations, public APIs
• **Tier 2**: User-facing features, internal APIs, database writes, third-party integrations  
• **Tier 3**: Static content, read-only displays, internal tooling, documentation

Agent MUST infer and declare tier in the plan; human reviewer MAY bump it up, never down.

### Gate Matrix by Profile

| Gate / Profile                     | web-ui            | backend-api | library | cli     |
| ---------------------------------- | ----------------- | ----------- | ------- | ------- |
| Static (type/lint/sast/secret/dep) | ✅ MUST           | ✅ MUST     | ✅ MUST | ✅ MUST |
| Unit + mutation                    | ✅ MUST           | ✅ MUST     | ✅ MUST | ✅ MUST |
| Contract tests                     | ⚠️ IF API calls   | ✅ MUST     | 🔵 MAY  | 🔵 MAY  |
| Integration (Testcontainers)       | ⚠️ IF DB/external | ✅ MUST     | 🔵 MAY  | 🔵 MAY  |
| E2E smoke (Playwright/Cypress)     | ✅ MUST           | ❌ N/A      | ❌ N/A  | ❌ N/A  |
| A11y (axe)                         | ✅ MUST           | ❌ N/A      | ❌ N/A  | ❌ N/A  |
| Perf budgets (LHCI)                | ✅ MUST           | ❌ N/A      | ❌ N/A  | ❌ N/A  |
| Perf budgets (k6/API)              | ❌ N/A            | ✅ MUST     | ❌ N/A  | ❌ N/A  |

**Legend**: ✅ MUST, ⚠️ CONDITIONAL (profile + tier + declared contracts), 🔵 MAY, ❌ N/A

### Required Inputs (No Code Until Present)

• **Working Spec YAML** (see schema below) with user story, scope, invariants, acceptance tests, non-functional budgets, risk tier.
• **Interface Contracts**: OpenAPI/GraphQL SDL/proto/Pact provider/consumer stubs.
• **Test Plan**: unit cases, properties, fixtures, integration flows, e2e smokes; data setup/teardown; flake controls.
• **Change Impact Map**: touched modules, migrations, roll-forward/rollback.
• **A11y/Perf/Sec budgets**: keyboard path(s), axe rules to enforce; perf budget (TTI/LCP/API latency); SAST/secret scanning & deps policy.

If any are missing, agent must generate a draft and request confirmation inside the PR description before implementing.

### The Loop: Plan → Implement → Verify → Document

#### 2.1 Plan (agent output, committed as feature.plan.md)

• **Design sketch**: sequence diagram or pseudo-API table.
• **Test matrix**: aligned to user intent (unit/contract/integration/e2e) with edge cases and property predicates.
• **Data plan**: factories/fixtures, seed strategy, anonymized sample payloads.
• **Observability plan**: logs/metrics/traces; which spans and attributes will verify correctness in prod.

#### 2.2 Implement (rules)

• **Contract-first**: generate/validate types from OpenAPI/SDL; add contract tests (Pact/WireMock/MSW) before impl.
• **Unit focus**: pure logic isolated; mocks only at boundaries you own (clock, fs, network).
• **State seams**: inject time/uuid/random; ensure determinism; guard for idempotency where relevant.
• **Migration discipline**: forwards-compatible; provide up/down, dry-run, and backfill strategy.

#### 2.3 Verify (must pass locally and in CI)

• **Static checks**: typecheck, lint (code + tests), import hygiene, dead-code scan, secret scan.
• **Tests**:
• **Unit**: fast, deterministic; cover branches and edge conditions; property-based where feasible.
• **Contract**: consumer/provider; versioned and stored under contracts/.
• **Integration**: real DB or Testcontainers; seed data via factories; verify persistence, transactions, retries/timeouts.
• **E2E smoke**: Playwright/Cypress; critical user paths only; semantic selectors; screenshot+trace on failure.
• **Mutation testing**: minimum scores per tier; non-conformant builds fail.
• **Non-functional checks**: axe rules; Lighthouse CI budgets or API latency budgets; SAST/dep scan clean.
• **Flake policy**: tests that intermittently fail are quarantined within 24h with an open ticket; no retries as policy, only as temporary band-aid with expiry.

#### 2.4 Document & Deliver

• **PR bundle** (template below) with:
• Working Spec YAML
• Test Plan & Coverage/Mutation summary, Contract artifacts
• Risk assessment, Rollback plan, Observability notes (dashboards/queries)
• Changelog (semver impact), Migration notes
• Traceability: PR title references ticket; commits follow conventional commits; each test cites the requirement ID in test name or annotation.
• Explainability: agent includes a 10-line "rationale" and "known-limits" section.

## 2) Machine-Enforceable Implementation

### A) Executable Schemas & Validation

#### Working Spec JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CAWS Working Spec",
  "$id": "https://your-org.com/caws/working-spec.schema.json",
  "caws_version": "1.0",
  "type": "object",
  "required": [
    "id",
    "title",
    "risk_tier",
    "profile",
    "rationale",
    "scope",
    "invariants",
    "acceptance",
    "non_functional",
    "contracts"
  ],
  "properties": {
    "profile": {
      "type": "string",
      "enum": ["web-ui", "backend-api", "library", "cli"]
    },
    "id": { "type": "string", "pattern": "^[A-Z]+-\\d+$" },
    "title": { "type": "string", "minLength": 8 },
    "risk_tier": { "type": "integer", "enum": [1, 2, 3] },
    "rationale": { "type": "string", "minLength": 20 },
    "dependencies": { "type": "array", "items": { "type": "string" } },
    "feature_flags": { "type": "array", "items": { "type": "string" } },
    "scope": {
      "type": "object",
      "required": ["in", "out"],
      "properties": {
        "in": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
        "out": { "type": "array", "items": { "type": "string" } }
      }
    },
    "invariants": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "acceptance": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "given", "when", "then"],
        "properties": {
          "id": { "type": "string", "pattern": "^A\\d+$" },
          "given": { "type": "string" },
          "when": { "type": "string" },
          "then": { "type": "string" }
        }
      }
    },
    "non_functional": {
      "type": "object",
      "properties": {
        "a11y": {
          "type": "object",
          "properties": {
            "axe_rules": { "type": "array", "items": { "type": "string" } },
            "keyboard_paths": {
              "type": "array",
              "items": { "type": "string" }
            },
            "contrast_min": { "type": "number", "minimum": 3.0 }
          },
          "additionalProperties": false
        },
        "i18n": {
          "type": "object",
          "properties": {
            "locales": { "type": "array", "items": { "type": "string" } },
            "rtl_supported": { "type": "boolean" }
          }
        },
        "perf": {
          "type": "object",
          "properties": {
            "api_p95_ms": { "type": "integer", "minimum": 1 },
            "lcp_ms": { "type": "integer", "minimum": 1 }
          },
          "additionalProperties": false
        },
        "security": { "type": "array", "items": { "type": "string" } },
        "security_policy": {
          "type": "object",
          "properties": {
            "sast_max_severity": {
              "type": "string",
              "enum": ["none", "low", "medium", "high"]
            },
            "secret_scan_block": { "type": "boolean" },
            "dep_policy": { "type": "string", "enum": ["strict", "lenient"] }
          }
        }
      },
      "additionalProperties": false
    },
    "contracts": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["type", "path", "role"],
        "properties": {
          "type": {
            "type": "string",
            "enum": [
              "openapi",
              "graphql",
              "proto",
              "pact",
              "asyncapi",
              "jsonschema"
            ]
          },
          "path": { "type": "string" },
          "role": { "type": "string", "enum": ["consumer", "provider", "both"] }
        }
      }
    },
    "observability": {
      "type": "object",
      "properties": {
        "logs": { "type": "array", "items": { "type": "string" } },
        "metrics": { "type": "array", "items": { "type": "string" } },
        "traces": { "type": "array", "items": { "type": "string" } }
      }
    },
    "migrations": { "type": "array", "items": { "type": "string" } },
    "rollback": { "type": "array", "items": { "type": "string" } }
  },
  "additionalProperties": false
}
```

#### Provenance Manifest Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["agent", "model", "commit", "artifacts", "results", "approvals"],
  "properties": {
    "agent": { "type": "string" },
    "model": { "type": "string" },
    "prompts": { "type": "array", "items": { "type": "string" } },
    "commit": { "type": "string" },
    "artifacts": { "type": "array", "items": { "type": "string" } },
    "results": {
      "type": "object",
      "properties": {
        "coverage": {
          "type": "object",
          "properties": {
            "metric": {
              "type": "string",
              "enum": ["branch", "line", "condition"]
            },
            "value": { "type": "number" }
          },
          "required": ["metric", "value"]
        },
        "mutation_score": { "type": "number" },
        "tests_passed": { "type": "integer" },
        "spec_changed": { "type": "boolean" },
        "contracts": {
          "type": "object",
          "properties": {
            "consumer": { "type": "boolean" },
            "provider": { "type": "boolean" }
          }
        },
        "a11y": { "type": "string" },
        "perf": { "type": "object" },
        "flake_rate": { "type": "number" }
      },
      "additionalProperties": true
    },
    "redactions": { "type": "array", "items": { "type": "string" } },
    "attestations": {
      "type": "object",
      "properties": {
        "inputs_sha256": { "type": "string" },
        "artifacts_sha256": { "type": "string" }
      }
    },
    "approvals": { "type": "array", "items": { "type": "string" } }
  }
}
```

#### Tier Policy Configuration

```json
{
  "1": {
    "coverage_metric": "branch",
    "min_coverage": 0.9,
    "min_mutation": 0.7,
    "requires_contracts": true,
    "requires_manual_review": true,
    "profiles": {
      "library": { "requires_contracts": false },
      "web-ui": { "perf_budgets": "lhci" },
      "backend-api": { "perf_budgets": "k6" }
    }
  },
  "2": {
    "coverage_metric": "branch",
    "min_coverage": 0.8,
    "min_mutation": 0.5,
    "requires_contracts": true,
    "profiles": {
      "library": { "requires_contracts": false },
      "web-ui": { "perf_budgets": "lhci" },
      "backend-api": { "perf_budgets": "k6" }
    }
  },
  "3": {
    "coverage_metric": "line",
    "min_coverage": 0.7,
    "min_mutation": 0.3,
    "requires_contracts": false
  }
}
```

### B) CI/CD Quality Gates (Automated)

#### Complete GitHub Actions Pipeline

```yaml
name: CAWS Quality Gates
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]

jobs:
  setup:
    runs-on: ubuntu-latest
    outputs:
      risk: ${{ steps.risk.outputs.tier }}
      profile: ${{ steps.risk.outputs.profile }}
    steps:
      - uses: actions/checkout@v4
      - name: Parse Working Spec
        id: risk
        run: |
          pipx install yq
          yq -o=json '.caws/working-spec.yaml' > .caws/working-spec.json
          echo "tier=$(jq -r .risk_tier .caws/working-spec.json)" >> $GITHUB_OUTPUT
          echo "profile=$(jq -r .profile .caws/working-spec.json)" >> $GITHUB_OUTPUT
      - name: Bootstrap Environment
        run: make caws:bootstrap
      - name: Validate Spec
        run: tools/caws/validate .caws/working-spec.json

  static:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make caws:bootstrap
      - run: make caws:static

  unit:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make caws:bootstrap
      - run: make caws:unit
      - run: tools/caws/gates coverage --tier ${{ needs.setup.outputs.risk }}

  mutation:
    needs: unit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make caws:bootstrap
      - run: make caws:mutation
      - run: tools/caws/gates mutation --tier ${{ needs.setup.outputs.risk }}

  contracts:
    needs: setup
    runs-on: ubuntu-latest
    if: needs.setup.outputs.profile == 'backend-api' || (needs.setup.outputs.profile == 'web-ui' && contains(github.event.pull_request.changed_files, 'contracts/'))
    steps:
      - uses: actions/checkout@v4
      - run: make caws:bootstrap
      - run: make caws:contracts
      - run: tools/caws/gates contracts --tier ${{ needs.setup.outputs.risk }}

  integration:
    needs: [setup]
    runs-on: ubuntu-latest
    if: needs.setup.outputs.profile == 'backend-api' || needs.setup.outputs.profile == 'web-ui'
    steps:
      - uses: actions/checkout@v4
      - run: make caws:bootstrap
      - run: make caws:integration

  e2e_a11y:
    needs: [integration]
    runs-on: ubuntu-latest
    if: needs.setup.outputs.profile == 'web-ui'
    steps:
      - uses: actions/checkout@v4
      - run: make caws:bootstrap
      - run: make caws:e2e
      - run: make caws:a11y

  perf:
    if: needs.setup.outputs.risk != '3' && (needs.setup.outputs.profile == 'web-ui' || needs.setup.outputs.profile == 'backend-api')
    needs: [integration]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make caws:bootstrap
      - run: make caws:perf

  provenance_trust:
    needs: [static, unit, mutation, contracts, integration, e2e_a11y, perf]
    runs-on: ubuntu-latest
    if: always()
    steps:
      - uses: actions/checkout@v4
      - run: make caws:bootstrap
      - name: Generate Provenance
        run: tools/caws/provenance > .agent/provenance.json
      - name: Validate Provenance
        run: tools/caws/validate-prov .agent/provenance.json
      - name: Compute Trust Score
        run: tools/caws/gates trust --tier ${{ needs.setup.outputs.risk }} --profile ${{ needs.setup.outputs.profile }}
      - name: Check Spec Delta
        run: tools/caws/gates spec-delta --require-if '.agent/provenance.json.results.spec_changed==true'
```

### C) Repository Scaffold

```
.caws/
  policy/tier-policy.json
  schemas/{working-spec.schema.json, provenance.schema.json}
  templates/{pr.md, feature.plan.md, test-plan.md}
.caws.yml            # repo-level configuration
contracts/           # OpenAPI/GraphQL/Pact
docs/                # human docs; ADRs
  ci-profiles.md     # CI adapter examples
src/
tests/
  unit/
  contract/
  integration/
  e2e/
  axe/
  mutation/
tools/caws/
  validate.ts
  gates.ts          # thresholds, trust score
  provenance.ts
Makefile             # caws:* target definitions
.github/
  workflows/caws.yml
CODEOWNERS
```

### D) Repository Configuration (.caws.yml)

```yaml
caws_version: '1.0'
default_profile: backend-api
coverage_metric: branch

services:
  postgres: true
  redis: false

tools:
  unit: 'npm run test:unit -- --coverage'
  mutation: 'npm run test:mutation'
  contracts: 'npm run test:contract'
  integration: 'npm run test:integration'
  e2e: 'npm run test:e2e:smoke'
  a11y: 'npm run test:axe'
  static: 'npm run typecheck && npm run lint && npm run sast'
  perf: 'npm run perf:budgets'

overrides:
  paths:
    tier1: ['src/auth/**', 'src/billing/**']
    ignore_contracts: ['src/internal/telemetry/**']

waivers:
  max_concurrent: 2
  approvers: ['@security-team', '@platform-team']
```

## 3) Templates & Examples

### Working Spec YAML Template

```yaml
id: FEAT-1234
title: 'Apply coupon at checkout'
risk_tier: 2
profile: backend-api
rationale: >
  Applies coupons server-side to prevent client-side tampering; requires contract-first to coordinate with web-ui client.
dependencies: ['FEAT-1200']
feature_flags: ['ENABLE_COUPON_STACKING']
scope:
  in: ['apply percentage/fixed coupons', 'stacking rules per business policy']
  out: ['gift cards', 'multi-currency proration']
invariants:
  - 'Total ≥ 0'
  - 'Coupon validity window respected (server time)'
  - 'Max one store-wide coupon; stacking only with product-specific coupons'
acceptance:
  - id: A1
    given: 'valid percentage coupon and eligible cart'
    when: 'user applies coupon'
    then: 'subtotal reduces by rate; taxes recomputed; UI reflects discount'
  - id: A2
    given: 'expired coupon'
    when: 'apply'
    then: 'explainable error; no state change'
non_functional:
  a11y:
    axe_rules: []
    keyboard_paths: []
  perf: { api_p95_ms: 250 }
  security: ['server-side validation; no client trust']
  security_policy:
    sast_max_severity: 'none'
    secret_scan_block: true
    dep_policy: 'strict'
  i18n:
    locales: ['en-US']
    rtl_supported: false
contracts:
  - type: openapi
    role: provider
    path: 'contracts/checkout.yaml#/applyCoupon'
observability:
  logs: ['coupon.apply result, reason']
  metrics: ['coupon_apply_success_count', 'failure_reason']
  traces: ['applyCoupon span with coupon_id, cart_id']
migrations:
  - 'add coupon_usages table with FK and unique constraints'
rollback: ['feature flag kill-switch; revert migration step DDL']
```

### PR Description Template

```markdown
## Summary

What changed and why (business value), link to ticket.

## Working Spec

- Risk Tier: 2
- Invariants: ...
- Acceptance IDs covered: A1, A2, ...

## Contracts

- OpenAPI diff: contracts/checkout.yaml (v1.3 → v1.4)
- Consumer tests: ✅ 12
- Provider verification: ✅

## Tests

- Unit: 74 tests, branch cov 86% (target 80%)
- Mutation: 56% (target 50%) – survived mutants listed below (rationale)
- Integration: 8 flows (Testcontainers Postgres)
- E2E smoke: 3 (Playwright) – recordings & traces attached
- A11y: axe 0 critical; keyboard path video attached

## Non-functional

- API p95 212ms (budget 250ms)
- Zero SAST criticals; deps policy compliant

## Observability

- New metrics: coupon_apply_success_count
- OTel spans: applyCoupon with attributes

## Migration & Rollback

- DDL: coupons_usages (idempotent)
- Kill switch env: FEATURE_COUPONS_APPLY=false

## Known Limits / Follow-ups

- Stacking with gift cards is out of scope (FEAT-1290)

## Spec Delta (REQUIRED if scope changed during implementation)

<!-- Describe any changes made to scope.in/out, invariants, acceptance. Link to commit updating .caws/working-spec.yaml. -->

- none
```

### Testing Patterns

#### Property-Based Unit Test

```typescript
import fc from 'fast-check';
import { applyCoupon } from '../../src/discount';
import { fixedClock } from '../helpers/clock';

it('total never < 0 [INV: Total ≥ 0]', () => {
  const cart = cartArb();
  const coupon = couponArb();
  fc.assert(
    fc.property(cart, coupon, (c, k) => {
      const r = applyCoupon(c, k, fixedClock('2025-09-17T00:00:00Z'));
      return r.total >= 0;
    })
  );
});
```

#### Contract Consumer Test

```typescript
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { ApplyCouponResponse } from '../../contracts/checkout.types';

const server = setupServer(
  http.post('/applyCoupon', () =>
    HttpResponse.json({
      success: true,
      subtotal: 90,
    } satisfies ApplyCouponResponse)
  )
);
beforeAll(() => server.listen());
afterAll(() => server.close());

it('conforms to /applyCoupon schema [contract]', async () => {
  const res = await client.applyCoupon({ code: 'SAVE10' });
  expect(res.success).toBe(true);
});
```

#### Integration Test with Testcontainers

```typescript
import {
  StartedPostgreSqlContainer,
  PostgreSqlContainer,
} from '@testcontainers/postgresql';
let pg: StartedPostgreSqlContainer;

beforeAll(async () => {
  pg = await new PostgreSqlContainer().start();
  await migrate(pg);
});
afterAll(async () => await pg.stop());

it('persists coupon usage [flow A1]', async () => {
  await seed(pg).withCustomer().withEligibleItems();
  const res = await api(pg).applyCoupon('SAVE10');
  expect(res.status).toBe(200);
  const cnt = await countUsages(pg, 'SAVE10');
  expect(cnt).toBe(1);
});
```

#### E2E Smoke Test

```typescript
test('apply coupon updates subtotal [A1]', async ({ page }) => {
  await page.goto('/checkout');
  await page.getByRole('textbox', { name: /coupon/i }).fill('SAVE10');
  await page.getByRole('button', { name: /apply/i }).click();
  await expect(page.getByRole('status')).toHaveText(/discount applied/i);
  await expect(page.getByTestId('subtotal')).toContainText('$90.00');
});
```

## 4) Agent Conduct Rules (Hard Constraints)

1. **Spec adherence**: Do not implement beyond scope.in; if discovered dependency changes spec, open "Spec delta" in PR and update tests first.
2. **No hidden state/time/net**: All non-determinism injected and controlled in tests.
3. **Explainable mocks**: Only mock boundaries; never mock the function under test; document any mock behavior in comments.
4. **Idempotency & error paths**: Provide tests for retries/timeouts/cancel; assert invariants on error.
5. **Observability parity**: Every key acceptance path emits logs/metrics/traces; tests assert on them when feasible (e.g., fake exporter assertions).
6. **Data safety**: No real PII in fixtures; factories generate realistic but synthetic data.
7. **Accessibility required**: For UI changes: keyboard path test + axe scan; for API: error messages human-readable and localizable.
8. **Performance ownership**: Include micro-bench (where hot path) or budget check; document algorithmic complexity if changed.
9. **Docs as code**: Update README/usage snippets; add example code; regenerate typed clients from contracts.
10. **Rollback ready**: Feature-flag new behavior; write a reversible migration or provide kill-switch.

## 5) Trust & Telemetry

• **Provenance manifest** (.agent/provenance.json): agent name/version, prompts, model, commit SHAs, test results hashes, generated files list, and human approvals. Stored with the PR for auditability.
• **Trust score per PR**: composite of rubric + gates + historical flake rate; expose in a PR check and dashboard.
• **Drift watch**: monitor contract usage in prod; alert if undocumented fields appear.

## 6) Operational Excellence

### Flake Management

• **Detector**: compute pass rate variance per spec ID over rolling time windows.
• **Policy**: >0.5% variance → auto-label flake:quarantine, open ticket with owner + expiry (7 days).
• **Implementation**: Store test run hashes in .agent/provenance.json; periodic job aggregates and posts a table to dashboard.

### Waivers & Escalation

• **Temporary waiver requires**:
• waivers.yml with: gate, reason, owner, expiry ISO date (≤ 14 days), compensating control.
• PR must link to ticket; trust score maximum capped at 79 with active waivers.
• **Escalation**: unresolved flake/waiver past expiry auto-blocks merges across the repo until cleared.

### Security & Performance Checks

• **Secrets**: run gitleaks/trufflehog on changed files; CAWS gate blocks any hit above low severity.
• **SAST**: language-appropriate tools; gate requires zero criticals.
• **Performance**: k6 scripts for API budgets; LHCI for web budgets; regressions fail gate.
• **Migrations**: lint for reversibility; dry-run in CI; forward-compat contract tests.

## 7) Language & Tooling Ecosystem

### TypeScript Stack (Recommended)

• **Testing**: Jest/Vitest, fast-check, Playwright, Testcontainers, Stryker, MSW or Pact
• **Quality**: ESLint + types, LHCI, axe-core
• **CI**: GitHub Actions with Node 20

### Python Stack

• **Testing**: pytest, hypothesis, Playwright (Python), Testcontainers-py, mutmut, Schemathesis
• **Quality**: bandit/semgrep, Lighthouse CI, axe-core

### JVM Stack

• **Testing**: JUnit5, jqwik, Testcontainers, PIT (mutation), Pact-JVM
• **Quality**: OWASP dependency check, SonarQube, axe-core

**Note**: Mutation testing is non-negotiable for tiers ≥2; it's the only reliable guard against assertion theater.

## 8) Review Rubric (Scriptable Scoring)

| Category                          | Weight | Criteria                            | 0                 | 1                  | 2                           |
| --------------------------------- | ------ | ----------------------------------- | ----------------- | ------------------ | --------------------------- |
| Spec clarity & invariants         | ×5     | Clear, testable invariants          | Missing/unclear   | Basic coverage     | Comprehensive + edge cases  |
| Contract correctness & versioning | ×5     | Schema accuracy + versioning        | Errors present    | Minor issues       | Perfect + versioned         |
| Unit thoroughness & edge coverage | ×5     | Branch coverage + property tests    | <70% coverage     | Meets tier minimum | >90% + properties           |
| Integration realism               | ×4     | Real containers + seeds             | Mocked heavily    | Basic containers   | Full stack + realistic data |
| E2E relevance & stability         | ×3     | Critical paths + semantic selectors | Brittle selectors | Basic coverage     | Semantic + stable           |
| Mutation adequacy                 | ×4     | Score vs tier threshold             | <50%              | Meets minimum      | >80%                        |
| A11y pathways & results           | ×3     | Keyboard + axe clean                | Major issues      | Basic compliance   | Full WCAG + keyboard        |
| Perf/Resilience                   | ×3     | Budgets + timeouts/retries          | No checks         | Basic budgets      | Full resilience             |
| Observability                     | ×3     | Logs/metrics/traces asserted        | Missing           | Basic emission     | Asserted in tests           |
| Migration safety & rollback       | ×3     | Reversible + kill-switch            | No rollback       | Basic revert       | Full rollback + testing     |
| Docs & PR explainability          | ×3     | Clear rationale + limits            | Minimal           | Basic docs         | Comprehensive + ADR         |

**Target**: ≥ 80/100 (weighted sum). Calculator in `tools/caws/rubric.ts`.

## 9) Anti-patterns (Explicitly Rejected)

• **Over-mocked integration tests**: mocking ORM or HTTP client where containerized integration is feasible.
• **UI tests keyed on CSS classes**: brittle selectors instead of semantic roles/labels.
• **Coupling tests to implementation details**: private method calls, internal sequence assertions.
• **"Retry until green" CI culture**: quarantines without expiry or owner.
• **100% coverage mandates**: without mutation testing or risk awareness.

## 10) Cursor/Codex Agent Integration

### Agent Commands

• `agent plan` → emits plan + test matrix
• `agent verify` → runs local gates; generates provenance
• `agent prove` → creates provenance manifest
• `agent doc` → updates README/changelog from spec

### Guardrails

• **Templates**: Inject Working Spec YAML + PR template on "New Feature" command
• **Scaffold**: Pre-wire tests/\* skeletons with containers and contracts
• **Context discipline**: Restrict writes to spec-touched modules; deny outside scope unless spec updated
• **Feedback loop**: PR comments show coverage, mutation diff, contract verification summary

## 11) Implementation Roadmap

### Foundation Milestone

- [ ] Add .caws/ directory with schemas and templates
- [ ] Create tools/caws/ validation scripts
- [ ] Wire basic GitHub Actions workflow
- [ ] Add CODEOWNERS for Tier-1 paths

### Quality Gates Milestone

- [ ] Enable Testcontainers for integration tests
- [ ] Add mutation testing with tier thresholds
- [ ] Implement trust score calculation
- [ ] Add axe + Playwright smoke for UI changes

### Operational Excellence Milestone

- [ ] Publish provenance manifest with PRs
- [ ] Implement flake detector and quarantine process
- [ ] Add waiver system with trust score caps
- [ ] Socialize review rubric and block merges <80

### Continuous Improvement

- [ ] Monitor drift in contract usage
- [ ] Refine tooling based on feedback
- [ ] Expand language support as needed
- [ ] Track trust score trends and flake rates

## 12) Trust Score Formula

```typescript
const weights = {
  coverage: 0.25,
  mutation: 0.25,
  contracts: 0.2,
  a11y: 0.1,
  perf: 0.1,
  flake: 0.1,
};

function trustScore(tier: string, profile: string, prov: Provenance) {
  const tierPolicy = tiers[tier];
  const profilePolicy = tierPolicy.profiles?.[profile] || {};
  const wsum = Object.values(weights).reduce((a, b) => a + b, 0);

  const score =
    weights.coverage *
      normalize(prov.results.coverage.value, tierPolicy.min_coverage, 0.95) +
    weights.mutation *
      normalize(prov.results.mutation_score, tierPolicy.min_mutation, 0.9) +
    weights.contracts *
      ((profilePolicy.requires_contracts ?? tierPolicy.requires_contracts)
        ? prov.results.contracts.consumer && prov.results.contracts.provider
          ? 1
          : 0
        : 1) +
    weights.a11y * (prov.results.a11y === 'pass' ? 1 : 0) +
    weights.perf * budgetOk(prov.results.perf) +
    weights.flake * (prov.results.flake_rate <= 0.005 ? 1 : 0.5);
  return Math.round((score / wsum) * 100);
}
```

## 13) Project-Specific Addenda

Each project MUST provide the following sections in their `AGENTS.project.md` file:

### Project Profiles

- **Primary Profile**: [web-ui|backend-api|library|cli]
- **Secondary Profiles**: (if applicable)
- **Justification**: Why this profile fits the project

### Service Matrix

- **Databases**: PostgreSQL, Redis, etc.
- **Message Queues**: RabbitMQ, Kafka, etc.
- **External APIs**: Third-party services used in integration tests
- **Test Data Strategy**: Fixtures, factories, anonymization approach

### Performance Budgets

- **Web UI**: LCP < 2.5s, FID < 100ms, CLS < 0.1
- **API**: P95 latency targets per endpoint
- **Measurement Harness**: Tools and CI integration

### A11y & i18n Targets

- **Supported Locales**: en-US, es-ES, etc.
- **RTL Support**: Yes/No
- **Assistive Technology**: Screen readers, keyboard navigation
- **Compliance Level**: WCAG 2.1 AA

### Security Policy Overrides

- **Temporary Leniency**: With expiration dates
- **Compensating Controls**: Alternative security measures
- **Risk Acceptance**: Documented and approved exceptions

### Tool Adapters

```makefile
# Example Makefile targets
caws:bootstrap:
	npm ci

caws:unit:
	npm run test:unit -- --coverage

caws:mutation:
	npm run test:mutation
```

### CI Provider Adapter

- **Primary**: GitHub Actions
- **Alternative**: GitLab CI, CircleCI mappings
- **Runner Requirements**: Docker, Node 20, specific services

### Data Classifications

- **Public**: Can be logged and stored
- **Internal**: Requires redaction in logs
- **Confidential**: Must be excluded from fixtures and traces

---

This v1.0 combines the philosophical foundation of our system with the practical, executable implementation details needed for immediate adoption. The framework provides both the "why" (quality principles) and the "how" (automated enforcement) needed for engineering-grade AI coding agents.
