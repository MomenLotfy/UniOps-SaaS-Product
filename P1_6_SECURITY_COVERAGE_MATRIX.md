# P1.6 — Security Coverage Matrix

Generated from the **live FastAPI route table** (394 HTTP routes) cross-checked
against the test corpus (`tests/**/*.py`, normalized for `{param}` f-string
paths). A route counts as *test-touched* when at least one test asserts against
its path; classification is **structural coverage only** — "test-touched" does
not itself guarantee a deep security assertion, and "MISSING" is a gap
classification, not automatically a vulnerability. Security-critical gaps were
audited manually (see §2) and either fixed (P1.6 findings) or statically
verified guarded.

## 1. Module × test coverage

| Module prefix | Routes | Test-touched | Status |
|---|---|---|---|
| alerts | 6 | 3 | PARTIAL |
| api-keys | 3 | 3 | COVERED |
| assets | 9 | 0 | MISSING |
| audit-logs | 2 | 1 | PARTIAL |
| auth | 8 | 4 | PARTIAL |
| billing | 7 | 0 | MISSING |
| catalog | 7 | 4 | PARTIAL |
| clusters | 11 | 5 | PARTIAL |
| companies | 5 | 0 | MISSING |
| compliance | 13 | 0 | MISSING |
| copilot | 5 | 0 | MISSING |
| costs | 9 | 0 | MISSING |
| devops-alerts | 8 | 0 | MISSING |
| gitops | 12 | 5 | PARTIAL |
| governance | 13 | 0 | MISSING |
| graph | 4 | 0 | MISSING |
| health | 5 | 1 | PARTIAL |
| impact | 4 | 0 | MISSING |
| integrations | 10 | 9 | PARTIAL |
| intelligence | 17 | 1 | PARTIAL |
| investigation | 7 | 0 | MISSING |
| k8s | 7 | 0 | MISSING |
| kubernetes | 21 | 0 | MISSING |
| logs | 1 | 0 | MISSING |
| metrics | 2 | 0 | MISSING |
| ml | 19 | 0 | MISSING |
| observability | 4 | 0 | MISSING |
| ops-health | 6 | 2 | PARTIAL |
| ownership | 15 | 0 | MISSING |
| pipelines | 8 | 2 | PARTIAL |
| remediation | 18 | 2 | PARTIAL |
| reports | 9 | 5 | PARTIAL |
| repos | 3 | 0 | MISSING |
| savings | 4 | 0 | MISSING |
| sbom | 9 | 0 | MISSING |
| security | 37 | 2 | PARTIAL |
| security-exceptions | 7 | 5 | PARTIAL |
| security-policies | 10 | 6 | PARTIAL |
| security-posture | 4 | 0 | MISSING |
| security-reports | 4 | 4 | COVERED |
| sla | 4 | 0 | MISSING |
| threats | 6 | 5 | PARTIAL |
| tickets | 5 | 0 | MISSING |
| users | 12 | 9 | PARTIAL |
| vulnerabilities | 4 | 3 | PARTIAL |
| webhooks | 6 | 6 | COVERED |
| webhooks-inbound | 4 | 4 | COVERED |
## 2. Security-relevant gaps triage (manual audit, this round)

| Route(s) | Prior coverage | Audit result |
|---|---|---|
| `POST /api/v1/remediation/*` (propose/execute/start/cancel/rollback) | none | **P1 fixed** — REM-1/REM-2/REM-3/REM-4 (role gate + truthful lifecycle + propose persistence); 9 new tests |
| `PATCH /api/v1/k8s/findings/{id}/suppress|resolve` | none | **P1 fixed** — K8S-1 viewer→403 via `SecurityWriteUser`; 2 new tests |
| `POST /api/v1/integrations/kubernetes` | none | statically verified guarded (`AdminUser`+`TenantID`) → NOT A GAP |
| `POST /api/v1/intelligence/feeds/{id}/sync` | none | **P2 fixed** — INTEL-1 fake success → honest 503; 2 new tests |
| `POST /api/v1/users/me/change-password`, `GET|DELETE /users/me/sessions` | none | self-service routes on own session material (actor-bound) — audited in auth battery, no finding |
| `POST /api/v1/reports/schedule`, `POST …/{id}/regenerate` | none | covered by report service RBAC convention; report download cross-tenant pinned by P0 matrix line 139 |
| 46 intelligence read routes | 1 | shared/global TIP corpus (not tenant-owned) — tenant-scope N/A; mutation route fixed (above); enriched-finding synthetic stub documented as P2 |

## 3. Inbound webhooks (/webhooks/*)

all 4 providers: **COVERED** (fail-closed suite `tests/test_p15_webhook_failclosed.py` — unset secret → 503, missing → 401, forged → 401, non-int slack ts → 401, signed → accepted; GitHub secret cannot open GitLab hook).

## 4. Verdict categories used

COVERED — every route of the module matched in tests · PARTIAL — some matched ·
MISSING — none matched (manually triaged above when security-relevant) ·
NOT APPLICABLE — shared/global or ops surface with no tenant state.
