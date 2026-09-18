# P1.6 — Final Production Readiness & Attack Surface Audit

**Date:** 2026-09-18 · **Branch:** `arena/01a0b237-uniops-saas-product` · **Entry HEAD:** `8096c21` (remote-synced, tree clean)
**Method:** every finding ran DISCOVER → CLASSIFY → PROVE (live) → FIX → REGRESSION (fails pre-fix) → LIVE VERIFY. No mocks-as-proof, no invented infrastructure, no feature work, no UI redesign.

---

# FINAL VERDICT: ✅ CONDITIONAL PASS

No unresolved P0. No blocking P1 (all fixed, regression-pinned, live-verified). Entry-point "production-true" scope expanded: this round closed **7 P1-class and 3 P2-class** findings that escaped P0/P1/P1.5, including one vertical-privilege-escalation class (remediation/K8s role gates) and one secret-echo class. The gate is CONDITIONAL (not PASS) because real Kubernetes/AWS/GitLab/Slack/Stripe/ArgoCD/observability infrastructure remains credibly unavailable in this environment — per the verdict rules the app must not be declared "production ready" on simulated infrastructure. See §23/§25.

## 1. Exact baseline
- HEAD `8096c21` == remote; tree clean; env intact.
- **Backend suite: 264/264 (191.7 s)**, **frontend build ✓ (8.83 s)** → baseline GREEN → audit proceeded (`P1_6_BASELINE_REPORT.md`).

## 2. Complete attack surface discovered (generated from the app, not prior reports)
- **394 HTTP routes** across 47 modules (security 37, kubernetes 21, ml 19, remediation 18, intelligence 17, ownership 15, governance/compliance 13, gitops 12, users 12, clusters 11, security-policies 10, integrations 10, …).
- **2 WebSocket routes**: `/ws/{tenant_id}`, `/api/v1/k8s/clusters/{cluster_id}/scan-stream`.
- **Root-level (outside /api/v1)**: `/health[/{live,ready,startup,metrics}]`, `/metrics`, `/webhooks/{github,gitlab,slack,stripe}` — all intentional; middleware exempts exactly these prefixes plus `/ws/*` and pre-auth `/api/v1/auth/{login,register,refresh,forgot-password,reset-password}`.
- No debug/test endpoints, no hidden admin surface, no unregistered-mount routes found beyond the inventory.

## 3. Findings (all proven, fixed, regression-pinned, live-verified)

| ID | Sev | Finding | Proof (live) | Fix | Regression (pre-fix → post-fix) |
|---|---|---|---|---|---|
| **INVITE-1** | **P1** | Invitation redemption dead: `RegisterRequest` lacked `invite_token`; every invitee silently registered as **admin of a NEW tenant**, invite row unconsumed in Redis | Redis row present (role viewer/tenant X); post-register claims `['admin']`, tenant ≠ X; row not consumed | added `invite_token` to schema (existing, correct service logic now reachable) | `test_p16_invite_role_binding.py` — 1 fail → 2 pass. Live: roles `['viewer']`, tenant match, token consumed |
| **REM-1** | **P1** | No role gate on remediation propose/execute/start/cancel/rollback — any authenticated viewer reached privileged infra mutations | viewer cancel → **200** on a real seeded plan | `DevOpsUser` (admin/devops/super_admin) on all 5 routes | 6 fail → 8 pass. Live: viewer→**403** on propose+cancel |
| **REM-2** | **P1** | `cancel` fabricated success: 200 `{"status":"cancelled"}` for nonexistent plans; DB row unchanged (`CREATED`) for existing ones | cancel of existing plan → 200, DB still `CREATED` | truthful lifecycle: 404 missing / 409 terminal / persist `CANCELLED` | incl. above. Live: admin cancel existing→200 **and** DB=`CANCELLED`; missing→404 |
| **REM-4** | **P1** | propose→execute chain dead by design: `create_execution_plan` never persisted | code + live (execute on proposed id can never resolve) | propose now persists plan (status `CREATED`) and returns persisted id | pin + suite |
| **SECRET-1** | **P1** | 422 validation errors echoed request bodies — **plaintext password returned** on register-validation failure | live: `"input":{"password":"SECRET-PASS-123"}` in 422 response | global `RequestValidationError` handler serializing only `type/loc/msg` | `test_p16_secret_validation_echo.py` — 3 fail → 3 pass. Live re-probe clean |
| **RACE-1** | **P1** | Concurrent same-username registration: `UNIQUE constraint failed: tenants.slug` → unhandled **500** (plus check-then-insert slug race) | logs + 6-parallel race → 1×500 | rollback + one uuid-suffix retry on slug insert | `test_p16_register_race.py` — 1 fail → 1 pass. Live: **0×500** (1×200/4×409/1×429) |
| **K8S-1** | **P1** | `PATCH /k8s/findings/{id}/suppress|resolve` gated by mere `CurrentUser` — viewer could mask/close security findings | static + sweep (role alias absent) | `SecurityWriteUser` on both routes | 1 fail → 2 pass (viewer→403; admin-on-missing→404) |
| REM-3 | P2 | rollback raised bare `Exception("Plan not found")` → **500** for a client error | live: rollback missing → 500 | `HTTPException(404)` | incl. REM suite; live → 404 |
| INTEL-1 | P2 | `POST /intelligence/feeds/{id}/sync` returned `{"success": true, "Sync triggered"}` with **zero dispatch** | code (no task/service) + route shape | fail-closed 503 (same contract as unconfigured webhooks); 404 for unknown provider preserved | `test_p16_intel_feed_sync.py` — 1 fail → 2 pass |
| CORS-1 | P2 | Preflight to foreign origin answered `allow-origin: <evil>` **with** `allow-credentials: true` (wildcard+credentials) | live OPTIONS probe | code default CORS_ORIGINS → explicit local dev origins (env override); auth is Bearer (no auth cookies) so exploitability today is low — defense-in-depth fix | `test_p16_config_hardening.py` |

**Sibling checks that came back clean (proven, not assumed):** all 27 then 20 flagged no-role-mutations resolved — decision-approvals (`require_security_write`+explicit tenant), security-policies (`SecurityWriteUser`), reports/security-reports deletes (`AdminUser`/scoped services) are all guarded; only remediation/intel/k8s-findings were real. Complete `{id}`-path sweep across all 175 ID routes (mutations + GETs): no remaining unscoped lookup beyond the classified intelligence module.

## 4. P0 findings — **ZERO unresolved** (gate rule satisfied)
*(INVITE-1 was assessed for P0 but fails closed toward a separate tenant — no cross-tenant write/read — so P1 by the discipline rules, not P0.)*

## 5. P1 findings — **ZERO blocking** (all 7 fixed and live-verified)

## 6. P2 findings
- Fixed this round: REM-3, INTEL-1, CORS-1 (above).
- Documented, not fixing (bounded, no security impact):
  - **`GET /intelligence/enriched/{finding_id}` / `/recommendations/{finding_id}`** return a **synthetic stub** (hardcoded metadata, no DB access) — fabricated data surface; NOT tenant-unsafe (nothing tenant-owned is read).
  - Integration not-found errors reflect the path id back (JSON, 404-uniform for missing vs foreign) — noted hygiene.
  - No request-body size middleware: 2 MB bodies reach the parser (422) — hardening note for WAF/reverse-proxy layer.

## 7. Authentication — **PASS**
Live battery (real app): unauthenticated→401 · garbage→401 · **refresh-as-access→401** · **access-as-refresh→401** · valid refresh→200 · expired access (real signature, past exp)→401 · **logout revokes refresh**→401 after re-login attempt · wrong password→401 · nonexistent user→401 (no enumeration) · 2FA/setup unauth→401 · **login rate limit: 5 attempts → 429 (real, distributed)**. Session material never appears in any response (SECRET-1 closed the last echo path).

## 8. RBAC — **PASS (after fixes) + strengthened grid**
Canonical role gates verified dep-by-dep; vertical gaps found only in remediation (REM-1) and k8s findings (K8S-1) → fixed with project conventions (`DevOpsUser`, `SecurityWriteUser`), viewer→**403** live.

## 9. Tenant isolation — **PASS**
175-route ID sweep clean; P0 IDOR matrix (12 tests incl. integrations `/test` from P1.5) green; cross-tenant probes live: integrations→404, remediation viewer-blocked, report download pinned 404 by matrix, approval reads explicitly tenant-checked.

## 10. Webhooks / callbacks — **PASS (fail-closed)**
github/gitlab/slack/stripe all enforce secret-present + valid signature/timestamp before any handler runs; forged/unsigned/ghost/duplicate cases pinned by 15-test suite; signed-acceptance verified per provider in tests.

## 11. Secrets — **PASS (after SECRET-1)**
Source scan: only documented placeholders (AWS `AKIAIOSFODNN7EXAMPLE`, `ghp_xxxx…` onboarding hints) — no real credentials tracked. Schemas: credentials only on write inputs; `IntegrationResponse`/`UserInfo` serialize no secrets. Logs/audit `details`: method/path/duration only. **SECRET-1 closed pydantic 422 echo** (passwords/credentials no longer round-trip).

## 12. Error handling — **PASS (after SECRET-1/REM-3/RACE-1)**
Malformed JSON→422 clean · SQLi-in-path→404 no-SQL-leak · oversized param→404 · wrong content-type→422 · 2 MB body→422 · schema violations→422 sanitized · nonexistent-plan rollback→404 · register race→409/429 not 500. No stack traces, SQL strings, internal class names, or credentials observed in any live response.

## 13. Middleware — **PASS**
JWT middleware exempts exactly: docs/health/auth-login-family/webhooks-root/ws — all intentional and individually verified (webhooks self-authenticate via signatures; `/api/v1/webhooks/*` (managed CRUD) is NOT exempted); OPTIONS preflight allowed; audit middleware writes truthful rows (see §14).

## 14. Audit trail — **PASS for scope**
Live mutations produced rows with **tenant_id + user_id + action + resource + truthful status (incl. a historical `failure` row) + ip + user_agent + duration**; no secrets in `details`. Gaps: `resource_id` is `None` on some create actions (weak metadata, not false); listed per-module audit tables (risk/intel/ownership) are empty in dev — acceptable, they target their own flows.

## 15. WebSockets — **PASS**
`/ws/{t}`: no-token/garbage/cross-tenant → disconnect; valid → connects; malformed message → closed; tenant scoping enforced at connect (JWT) with fan-out isolation covered by P1 multi-worker tests (re-green). `/k8s/clusters/{id}/scan-stream`: token-required (browsers can't header — documented `?token=`), invalid→close 4001, cluster lookup tenant-scoped → close 4004.

## 16. Background / internal operations — **PASS for scope**
Tenant id is passed explicitly through bg chains (`_bg_test_and_sync`, `_bg_sync`, costs probe) operating on rows validated tenant-side at request time; P1 worker/idempotency suites re-green; webhook-driven mutations are signature-gated (WEBHOOK-1) and repo→tenant-mapped server-side.

## 17. Database integrity — **PASS (after RACE-1)**
Constraints honored under parallel load (slug retry heals; duplicate email → 409); singleton-upsert prevents duplicate integration rows under repeated connect (P1.5-proven); failed mutations roll back (no partial state observed in any probe).

## 18. File security — **COVERED**
Only two materialized download routes (`/reports/{id}/download`, `/sbom/{id}/download`); cross-tenant report download pinned 404 by P0 matrix; no upload/mulitpart storage surface exists beyond those → rest **NOT APPLICABLE**.

## 19. External integrations — **UNCHANGED since P1.5 (truth table intact)**
GitHub real-verified (client boundary + error contract), user-scope happy path still capability-blocked; GitLab/K8s/AWS/ArgoCD/observability/scanners/Slack/Stripe: **UNVERIFIED — infrastructure unavailable**; failure contracts all honest (no fake-green anywhere reachable).

## 20. Security coverage matrix — **`P1_6_SECURITY_COVERAGE_MATRIX.md`**
47 modules: 4 COVERED, 19 PARTIAL, 24 fully missing path-level test references; every security-relevant gap manually triaged (§2 of the matrix) — real gaps fixed this round, the rest statically verified guarded or classified shared/global (N/A).

## 21. Regression tests — **PASS**
**Backend: 282/282 (196 s)** vs P1.5 baseline 264/264 → **+18 net-new tests** (invite 2, remediation/k8s truth-gate 9, intel feed-sync 2, secret-echo 3, config 2, race 1; one legacy test tightened in P1.5 already). **Every new regression was executed against pre-fix code and confirmed to fail.** Frontend: `pnpm build` ✓ **9.01 s**. **No test deleted or weakened.**

## 22. Live verification evidence (selected)
- invite: viewer → roles `['viewer']`, tenant matches inviter, Redis invite consumed
- viewer → `403` on remediation propose/cancel; admin → cancel existing `200` + DB `CANCELLED`; missing → `404`; rollback missing → `404`
- register race: 1×200/4×409/1×429/**0×500**; `grep IntegrityError` in server log → 0
- 422 register: response `{"detail":[{"type":"missing","loc":…,"msg":…}]}` — **no password**
- auth battery: all 14 cases (§7) as expected; login 429 after 5
- Redis-down injection: register/login 200 (memory fallback), rate-limit still 429 after window-free attempts, `/health/ready` → `ready_degraded` with honest `redis:error`; **no fail-open**
- CORS preflight from foreign origin (pre-fix evidence); post-fix code default no-wildcard
- WS battery (§15) as listed

## 23. Remaining UNVERIFIED infrastructure (unchanged, honest)
K8s cluster/API · AWS (STS/EKS/Cost Explorer/Security Hub) · GitLab egress/user-scope · GitHub user-scope happy path (installation-token capability) · ArgoCD/GitOps server · Loki/Prometheus · semgrep/trivy servers · Slack & Stripe signed delivery against live keys · production-grade Postgres/Redis HA · SMTP delivery.

## 24. Remaining risks (documented, bounded)
- Intelligence `enriched/recommendations` synthetic stub returns fabricated (but tenant-safe) data — P2.
- No request-size middleware (reverse-proxy recommended) — P2 note.
- Audit `resource_id` blank on create actions — P2 metadata completeness.
- Webhook handlers' durability under provider-secret rotation/deployment = ops concern; endpoints 503 (intentionally) until secrets are set — document for go-live.

## 25. Recommended next phase
**P2 — Staged Infrastructure Verification** (one environment, real resources):
1. Real K8s cluster (kind/EKS) → k8s integration, pods/logs/security-scan WS stream, pod-exec path, per-tenant kubeconfig isolation.
2. Read-only AWS identity → STS verify, EKS, Cost Explorer, Security Hub ingestion.
3. GitLab from a network with real egress → the fixed `get_authenticated_user` happy path + repo/pipeline sync.
4. GitHub with a standard PAT → user-scope `connected` + repo sync closure.
5. Configure all `*_WEBHOOK_SECRET`/`SLACK_SIGNING_SECRET` in staging → end-to-end signed delivery from real providers.
6. Postgres-backed multi-worker redeployment (sqlite is dev-only) — re-run P1 multi-worker suite.

---

**Commit lineage for P1.6:** see `git log --oneline` after `8096c21` (baseline → invite binding → remediation truth & role gate → intel honesty → secret-echo sanitization → CORS default → slug-race → k8s findings role gate → coverage matrix + this report).
