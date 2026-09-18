# UniOps — P0 Production Hardening

**Scope:** Canonical RBAC everywhere · tenant isolation · mock/demo removal · real integration verification · privileged-ops audit · tests · production verification.
**Branch:** `arena/01a0b237-uniops-saas-product`
**Date:** 2026-09-18

---

## 1. P0 Issues Fixed

### RBAC-1 — Fragmented role contract across frontend + backend (root fix)
- **Root cause:** Role names (`devops` / `security` / `finops`) appeared in Sidebar gates, route guards, permission-matrix columns, invite dropdowns, onboarding selects, pipeline/GitOps `hasRole` checks, and the backend `DEVOPS_MUTATION_ROLES` set — while the canonical contract (`devops_engineer` / `security_engineer` / `cost_analyst`) lived only in `ROLE_PERMISSIONS`/`UserRole`. The same user had different access depending on which string a component compared.
- **Fix — single normalization layer, legacy aliases ONLY at the boundary:**
  - Backend: `backend/app/constants/roles.py` — `LEGACY_ROLE_ALIASES`, `normalize_role(s)`, `is_valid_role`, `CORE_ROLES`. Applied in `deps.get_current_user` (JWT parse — the choke point for every `require_*`), `UserInvite` Pydantic validator (new data always canonical, unknown role → 422), `user_service.update` (write-time migration), `auth_service.register` (legacy invite-payload consumption-safe fallback). `DEVOPS_MUTATION_ROLES` alias removed — only canonical names remain.
  - Frontend: `artifacts/uniops/src/lib/permissions.ts` — `LEGACY_ROLE_ALIASES`, `normalizeRole(s)`; applied in `usePermissions` hook and `AuthContext` session boundary. Sidebar, `App.tsx` RoleBasedRoute, `PermissionMatrix`, DevOpsCenter `canAct`/`hasRole` (4 files), `TeamSettings`, `onboarding`, `PendingInvitations` all canonical-only.
- **Verification:** runtime probes — legacy `devops` JWT → cluster-create **201** (normalized); same request as `viewer` → **403**; unknown role invite → **422**; `admin` allowed. Automated: 24 new tests (`tests/test_rbac_tenancy.py`).

### TENANT-1 — CRITICAL IDOR class: id-addressed accessors without tenant ownership
- **Root cause:** BaseService `_get_by_id` lookups returned any row by id; several services never compared `tenant_id`. Cross-tenant impact proven live:
  - `WebhookService.get_by_id/update/delete` → **any tenant could read/update/delete another tenant's webhooks** (and `BaseModel.to_dict` serialized the HMAC **`secret`** in every response).
  - `IntegrationService.get_by_id/update/delete/sync` → cross-tenant **decrypted-credential sync** + destructive delete.
  - `AlertService.get_by_id/update`, `SecurityService.get_threat/update_threat/get_vulnerability/update_vulnerability`, `ReportsService.get_report/delete_report` (+ `/download`), `SecurityReportService`, `SecurityPolicyService.get/delete/update_policy`, `SecurityExceptionService.get_exception`, `UserService.get_by_id/deactivate` — all same class.
- **Fix:** every id-addressed accessor takes an optional `tenant_id` and 404s on mismatch (`_assert_tenant`); all calling endpoints pass the JWT-derived tenant (`current_user["tenant_id"]` / `TenantID` dependency) — never body/query. `Webhook.to_dict` redacts `secret` (exposes `has_secret` boolean). Design keeps 404-not-403 on cross-tenant (no existence leak), matching `cluster_service`.
- **Verification:** runtime probes — Tenant B reads Tenant A's webhook → **404**; A's create response contains **no `secret`**, `has_secret: true`; B lists clusters → **0**; B reads A cluster → **404**, A → **200**. Automated: 6 new isolation tests (webhooks, clusters, users, integrations, invitations, body-smuggling).

### MOCK-1 — Fabricated data passed off as real (4 pages + 2 widgets)
- **`company/PendingInvitations.tsx`** — 4 hardcoded fake people ("Alice Johnson" etc.), local-state revoke/resend no-ops. **Fix:** real `GET /users/invitations` + `DELETE /users/invitations/{id}` backend endpoints added (Redis-backed, tenant-scoped, hash-id never raw token) + full rewrite of the page (load/error/empty states, real invite POST with canonical role dropdown).
- **`admin/Roles.tsx`** — 6 fake roles with fake member counts (1,3,8,4,2,15), fake permission toggles, fake Create/Save buttons. **Fix:** read-only truth — permissions derived from the actual `ROLE_PERMISSIONS` map; member counts from real `GET /users`; fake affordances removed.
- **`admin/Teams.tsx`** — 4 fake teams with 9 fake members. **Fix:** rebuilt as role-grouped org view over real users (no teams entity exists in the backend; page now says so).
- **`DevOpsCenter/CatalogTab.tsx` Create-Service wizard** — fake target clusters (`prod-eks`, `staging-eks`, …) and fake namespace list in the deployment step. **Fix:** clusters fetched from real `GET /clusters` (tenant-scoped) with a truthful "No clusters connected" blocking state; namespace is user-provided free text (never invented).
- **`MLInsights`** — hardcoded fallback fillers (`?? 7`, `?? 5`, `?? 92% accuracy · Confidence: High`) inventing prediction numbers. **Fix:** removed; `is_fallback` DEMO badge (backend-driven, explicitly labeled) kept, missing values show `—` / "not trained".

### OPS-1 — `POST /pipelines/sync` missing rate limit
- Spawns external GitHub/GitLab API work per call, unbounded. **Fix:** `rate_limit("pipeline.sync", 20, 60)` — consistent with `gitops.sync`; existing rerun/cancel/sync/rollback limits verified present (`pipeline.rerun` 15/60, `pipeline.cancel` 15/60, `gitops.sync` 20/60, `gitops.rollback` 10/60).

### RT-1 — Frontend DevOpsCenter accepted both legacy + canonical in comparison lists
- Convenience `.get('/users/invitations')` route was shadowed by `/{user_id}` (fastapi declaration order) — reordered (static before dynamic).

---

## 2. Test Results

| Suite | Result |
|---|---|
| Backend full suite (`pytest tests -q`) | **195 passed, 0 failed** (baseline was 171 at start of P0) |
| New in P0: `tests/test_rbac_tenancy.py` | **24 tests, all passing** |
| Frontend production build (`pnpm build`) | **✓ built** |

New tests by mandate section:
- RBAC canonical + normalization (unit): alias map, pass-through, dedup/merge, `is_valid_role` — 7 tests.
- RBAC e2e through JWT parse: legacy-alias-allowed, canonical-allowed, viewer-403, unknown-role-403, admin-allowed — 5 tests.
- Invite schema: legacy→canonical, unknown rejected (422), default viewer — 4 tests.
- Invitations tenancy: list/revoke own, B-cannot-see/revoke (404), non-admin 403, unknown role 422 — 4 tests.
- Cluster isolation: read/update/delete cross-tenant → 404; body `tenant_id` smuggling ignored — 2 tests.
- Webhooks: secret redaction (create + list), CRUD cross-tenant → 404 — 1 test.
- Users + integrations isolation: PII read/deactivate → 404; integration read/delete/sync → 404 — 2 tests _(+1 sync-false-success guard)_.

## 3. Production Verification (live, sandbox runtime)

Backend `:3001` + frontend `:5173` (vite proxy → backend).

| Check | Status |
|---|---|
| App lifespan startup (DB init, scheduler, event bus, deployment worker, WS bridge) | **VERIFIED** (live logs; K8s watchers disabled w/o cluster — honest state; ML listener runs on memory fallback without Redis) |
| `GET /health` 200, frontend 200, proxied `/api/v1/health` 200 | **VERIFIED** |
| Register → login → authed requests | **VERIFIED** |
| Authorized-can / unauthorized-403 (cluster create × devops/devops_engineer/viewer-admin invites) | **VERIFIED** |
| Legacy alias normalization at runtime (`devops` JWT → 201) | **VERIFIED** |
| Invitations happy path + tenant isolation + revoke | **VERIFIED** |
| Webhook secret redaction + cross-tenant 404 | **VERIFIED** |
| Cluster cross-tenant read/list | **VERIFIED** |
| Empty/not-connected states (invitations, teams, catalog wizard) | **VERIFIED** (frontend renders real empty/error states) |
| K8s exec/restart/scale against a live cluster | **NOT AVAILABLE — credentials required** (UNVERIFIED, capability gated as designed: returns clear not-connected/404 states) |
| GitHub/GitLab/AWS real sync with creds | **NOT AVAILABLE — credentials required** (IDOR/rate-limit paths verified; external data path needs creds) |
| WebSocket live events | **PARTIALLY VERIFIED** (event-bus bridge starts, WS endpoint up; no live cluster events emitted w/o integrations) |

## 4. Remaining Risks (honest)

1. **Invitations listing is Redis/memory-fallback based** — with no Redis in this environment it uses the in-process fallback (single pod OK; multi-pod would need Redis — which production mandates anyway). Expiry is by Redis TTL (48h); the API returns pending records only.
2. **`admin/Roles` permission display tolerates the wildcard rows** correctly, but creating *custom* roles is intentionally NOT offered — the system role set is code-defined; this is truthful but a future product gap.
3. K8s/GitOps/cloud features are **integration-gated**; without credentials they now report truthful not-connected states rather than fabricated data, but end-to-end flows are UNVERIFIED against real infra in this sandbox.
4. The MLInsights DEMO badge relies on the backend `is_fallback` flag; when real models aren't trained, cards are explicitly marked DEMO and never passed off as predictions.
5. Older tenants with legacy role names in DB rows: normalization handles them at JWT parse + write time; a one-shot data migration to canonical names is recommended but was deliberately **not** run (no destructive migrations without operator consent).

## 5. Production Readiness Counts

- **P0 BLOCKERS (unfixed): 0 open** · (1 found during this round — the IDOR class — fixed + regression-tested)
- **VERIFIED: 11 checks** (RBAC normalization e2e, auth, invitations flow + isolation, webhook redaction + isolation, cluster isolation, 403 semantics, health/readiness, lifespan startup, build, full test suite, frontend proxy)
- **PARTIALLY VERIFIED: 1** (WebSocket/event flow)
- **NOT AVAILABLE (credentials required / UNVERIFIED): 2 capability groups** (K8s live control-plane ops, external cloud/git sync with creds)

---
*Fixes follow the mandate: no new features, no UI redesign, root-cause fixes, no fake data, RBAC as final backend authority, tenant isolation proven by tests and live probes, failed/cross-tenant privileged ops never report success.*
