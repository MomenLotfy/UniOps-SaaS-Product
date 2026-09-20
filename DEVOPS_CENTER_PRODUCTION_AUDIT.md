# DevOps Center — Production Audit

**Repository:** `MomenLotfy/UniOps-SaaS-Product`
**Branch:** `arena/01a0bbd6-uniops-saas-product`
**Base commit:** `29b139a96ccf8c44f186ef927a73f99ae1ea8573` (2026-09-18 20:57:25 +0300)
**Audit date:** 2026-09-19
**Scope:** Every option visible in the DevOps Center (`/devops`) — where its data comes from, what integration powers it, what happens on interaction, and whether the complete flow actually works.

**Question this report answers:**
> For every option visible in DevOps Center, where does its data come from, what integration powers it, what happens when the user interacts with it, and does the complete flow actually work?

---

## 1. Executive Summary

The DevOps Center is a **genuinely wired** product surface, not a mock. Its 38 distinct API
calls all resolve to real backend routes, every read path hits a real database or a real
provider client, and when a provider is absent the system almost always degrades *honestly*
(`source: "unavailable"`, `ArgoCD not connected`, HTTP 502/503 with the real provider error).
Tenant isolation is strong and was proven against real cross-tenant rows. RBAC is enforced
server-side, not just in the UI. Audit logging captures every mutation with a user id.

However, **four defects mean that several visible buttons cannot succeed even with perfect
credentials and a healthy cluster**, and three more report success when nothing happened.
These are code-level faults, not environment gaps — a fully provisioned production
environment would still fail on them.

### Verdict: **NOT READY**

### Headline findings

| # | Severity | Finding | Evidence |
|---|----------|---------|----------|
| BUG-001 | **P0** | Every GitHub CI/CD mutation is dead code. `GitHubClient` reads `self._headers`, which is never assigned; the class only defines `_build_headers()`. `rerun`, `rerun_failed_jobs`, `cancel` all fail **before any HTTP request is made**. | `hasattr(client,'_headers') → False`; all three return `{'success': False, 'error': "'GitHubClient' object has no attribute '_headers'"}` |
| BUG-002 | **P0** | Pod **force-delete** and pod **restart** call `k8s.V1DeleteOptions(...)` on the `_K8sApis` shim, which exposes only API classes and has no such attribute. Latent: masked when the cluster is unreachable (an earlier check returns first), fires on a **working** cluster. | `hasattr(_K8sApis(None),'V1DeleteOptions') → False`; live `DELETE /kubernetes/pods/{id}` → 502 `'_K8sApis' object has no attribute 'V1DeleteOptions'` |
| BUG-003 | **P1** | The pod-sync background job **deletes every pod row** when the Kubernetes API is unreachable. `list_all_pods()` returns `[]` on exception, and the reconciliation loop then treats all rows as gone. | `_sync_pods() → {'integrations': 2, 'pods_synced': 0, 'pods_deleted': 4}`; API `total` 4 → 0 |
| BUG-004 | **P1** | `POST /kubernetes/pods/{id}/exec` returns **HTTP 200 `success: true`** with the provider failure text stuffed into `output`. The terminal panel renders a connection error as command output. | `{"success":true,"data":{"output":"exec failed: (0)\nReason: [Errno 111] Connection refused\n"}}` |
| BUG-005 | **P1** | Observability → Pod Metrics rendered **every** pod as `unknown / default / Unknown / null`, and the Namespace panel collapsed everything into one `default` row. Root cause: `PodResponse` is a pydantic model with no `to_dict()`, so the fallback produced `{}` per pod — at **two** call sites. **Both fixed and proven during this audit** (see §15.1). | Before: 4 × `{"name":"unknown",...}`; after: `worker-5b7c6-j8k9l / jobs / CrashLoopBackOff / cpu 45.0 / mem 97.7`. Namespaces before: `[{"default",4,null,null}]`; after: `[{"jobs",1,45.0,97.7},{"prod",3,33.0,48.3}]` |
| BUG-006 | **P1** | Deployment **scale** returns HTTP 200 / `code: "SUCCESS"` with `data.success: false`. The UI toasts the raw provider exception as if the scale succeeded. | `{"success":true,...,"data":{"success":false,"error":"HTTPSConnectionPool(...)"},"code":"SUCCESS"}` |
| BUG-007 | **P2** | Cluster **Test Connection** on an unreachable cluster returns HTTP 200 with `status: "disconnected"` **and `message: "Connection successful"`**. The UI shows a success-labelled red toast. | `{"status":"disconnected","node_count":0,"message":"Connection successful"}` |
| BUG-008 | **P2** | `DELETE /gitops/{id}` returns **204 unconditionally** — for another tenant's app, and for a random non-existent UUID. Tenant filtering *is* present (no data leak), but the caller is told "deleted" when nothing was deleted. | `A DELETEs B's app → 204, row still in DB: True`; `random UUID → 204` |
| BUG-009 | **P2** | The nine Control-Plane resource tabs (Deployments, StatefulSets, DaemonSets, Services, Ingresses, Jobs, ConfigMaps, Secrets, HPA) return **HTTP 200, `message: "OK"`, empty data** while the cluster is down. The server log shows all nine real API calls failing. | All nine → `http=200 empty=True error_signal='OK'` |
| BUG-010 | **P2** | The DevOps Center **cluster selector does nothing**. `selectedClusterId` is read only for the dropdown's own label and highlight; it is never passed to any child tab or sent to the API. | `index.tsx:88,214,215,235` — no other reference |

**Fixed during the audit:** BUG-005 (one-line root-cause fix in `observability.py`, proven
before/after, full backend suite green).
**Not fixed (documented only):** BUG-001, 002, 003, 004, 006–010.

---

## 2. Baseline

### 2.1 Code state

| Item | Value |
|------|-------|
| Commit | `29b139a96ccf8c44f186ef927a73f99ae1ea8573` |
| Branch | `arena/01a0bbd6-uniops-saas-product` |
| Remote | `https://github.com/MomenLotfy/UniOps-SaaS-Product.git` |
| Backend routes exposed | **354** paths (`/openapi.json`) + 1 WebSocket (`/ws/{tenant_id}`) |
| DevOps Center source | `artifacts/uniops/src/pages/DevOpsCenter/` — 12 files, ~5 480 LOC |

### 2.2 Backend test result

```
cd backend && .venv/bin/python -m pytest -q -p no:cacheprovider
```

Run twice — once at `HEAD` with the fix stashed, once with the fix applied:

| Run | Result | Duration |
|-----|--------|----------|
| **Before** the BUG-005 fix (`git stash`) | **290 passed**, 21 warnings | 511.04 s |
| **After** the BUG-005 fix | **290 passed**, 21 warnings | 493.91 s |

Identical outcome, so the fix introduces no regression.

Caveat recorded honestly: an earlier exploratory run reported `1 failed / 228 passed`, the
single failure being a missing `fakeredis` dev dependency. With it installed the suite
collects 290 tests and is fully green. `backend/Makefile` hardcodes `VENV ?= ./venv`, but that
interpreter is a dangling nix symlink, so `make test` cannot be used; `.venv` was used instead.

### 2.3 Frontend build result

```
pnpm build   →  PASS (13.03 s)
```
Only warning: one chunk exceeds 500 kB. No type errors, no unresolved imports.

### 2.4 Environment

| Component | Available | Notes |
|-----------|-----------|-------|
| Python | 3.11.2 | `pyproject.toml` targets 3.12 → `mypy`/`ruff` targets not reproducible here |
| Node / pnpm | v22.22.3 / 9.15.9 | `pnpm install --frozen-lockfile` fails with `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`; `--no-frozen-lockfile` used |
| Database | SQLite (aiosqlite) | `DATABASE_URL=sqlite+aiosqlite:///./audit.db` for the harness |
| Redis | **absent** | `apt-get install redis-server` → *Unable to locate package*. Rate limiting exercised via the in-process sliding-window fallback |
| PostgreSQL | **absent** | |
| Kubernetes | **absent** | Fixture integration points at unreachable `https://127.0.0.1:6443` |
| ArgoCD | **absent** | Deliberately not registered — used to prove the NOT_CONFIGURED path |
| Docker | **absent** | |

Backend run under test:

```
DATABASE_URL=sqlite+aiosqlite:///./audit.db  RATE_LIMIT_ENABLED=false
OTEL_SDK_DISABLED=true  LOG_LEVEL=WARNING  BACKGROUND_LEADER=false
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`BACKGROUND_LEADER=false` disables the in-process scheduler, so fixture pod rows survive long
enough to probe. This is a **harness accommodation for BUG-003**, not a production setting.

### 2.5 Configured integrations

| Integration | Registered | Credential | Effective state |
|-------------|-----------|-----------|-----------------|
| Kubernetes (tenant A) | yes, `connected` | kubeconfig → `https://127.0.0.1:6443` | unreachable — real calls attempted, real errors surfaced |
| Kubernetes (tenant B) | yes, `connected` | no kubeconfig | `K8s client init failed: Service host/port is not set.` |
| GitHub (tenant A) | yes, `connected` | syntactically-valid but invalid PAT | blocked earlier by BUG-001 |
| GitLab | no | — | NOT_CONFIGURED |
| ArgoCD | no | — | NOT_CONFIGURED (deliberate) |
| Prometheus | no | — | NOT_CONFIGURED |
| AWS / Slack / Stripe / SendGrid / Sentry | no | empty in `.env` | NOT_CONFIGURED |

### 2.6 Credentials available

`backend/.env` has `GITHUB_TOKEN`, `STRIPE_SECRET_KEY`, `SENDGRID_API_KEY`, `SLACK_BOT_TOKEN`,
`SENTRY_DSN` and all `AWS_*` values **empty**. No usable external credential exists in this
environment, so no test could confirm a successful round-trip against a real third party.

### 2.7 Audit harness (created for this audit, untracked)

| File | Purpose |
|------|---------|
| `backend/scripts/audit_fixture.py` | Seeds two tenants, five users, integrations, clusters, pods, pipelines, gitops apps, alerts, catalog services into `backend/audit.db` |
| `backend/scripts/audit_probe.py` | 8-section live probe (~140 HTTP calls): auth, reads, filters, IDOR, RBAC grid, mutations, rate limits, dead endpoints |
| `backend/scripts/audit_isolation.py` | Seeds **real** tenant-B rows, then attacks them as tenant A and re-reads the DB to confirm survival |
| `backend/scripts/audit_flows.py` | Six end-to-end CRUD lifecycles with read-back after every mutation |
| `backend/scripts/audit_ws_probe.py` | WebSocket handshake auth, tenant binding, protocol abuse, cross-tenant event isolation |
| `backend/.audit_ids.json` | Fixture identifiers |

All results quoted in this report were produced by these scripts against the running server.
Raw logs: `/tmp/probe2.log` (629 lines), `/tmp/flows.log`, `/tmp/pytest2.log`.

---

## 3. DevOps Center Feature Inventory

Built from routing and navigation code, not documentation.

### 3.1 Entry points

| Element | Location | Value |
|---------|----------|-------|
| Route | `src/App.tsx:124` (lazy import `:15`) | `/devops` |
| Sidebar entry | `src/components/Layout/Sidebar.tsx:34` | `ROUTES.DEVOPS`, shortcut `⌘2` |
| Allowed roles (sidebar) | same | `super_admin`, `admin`, `devops_engineer` |
| Page root | `src/pages/DevOpsCenter/index.tsx` (369 L) | |

### 3.2 The four sections

| Section id | Component | File | LOC |
|-----------|-----------|------|-----|
| `control-plane` | `ClusterControlPlane` | `ClusterControlPlane.tsx` | 509 |
| `observability` | `PlatformObservability` | `PlatformObservability.tsx` | 73 |
| `delivery` | `DeliveryGitOps` | `DeliveryGitOps.tsx` | 238 |
| `catalog` | `CatalogTab` | `CatalogTab.tsx` | 1022 |

`PlatformObservability` is a thin wrapper that composes `ObservabilityTab` (598 L) and
`AlertsTab` (460 L) and passes `pods` down.
`ClusterControlPlane` embeds `ClusterTab` (684 L).
`DeliveryGitOps` hosts the sub-tab bar with `gitops` → `GitOpsTab` (629 L) and `pipelines`.

### 3.3 Header controls (`index.tsx`)

| Control | Line | Behaviour |
|---------|------|-----------|
| Role badge | — | Cosmetic, from `usePermissions()` |
| Cluster selector dropdown | 88, 214-215, 235 | Sets `selectedClusterId`; **read only for its own label/highlight — see BUG-010** |
| WebSocket status dot | — | Live, from `useWebSocket()` |
| Refresh button | — | `refetchPods()` + `refetchPipes()` + an 800 ms cosmetic `sleep` |
| Four stat cards | — | `/kubernetes/pods/stats` and `/pipelines/stats` |

### 3.4 Client-side action gate

`canAct = isAdmin() || hasRole('devops_engineer')` (`hooks.ts:224`, duplicated inline in
`index.tsx`). It gates the `DeliveryGitOps` section only. Server-side RBAC is enforced
independently (see §14).

### 3.5 Complete API surface used by DevOps Center

Extracted from the source and resolved against the live `/openapi.json`. **38 of 38 real API
paths resolve.** (`/settings/integrations` is a client-side route link, not an API call.)

| Frontend path | Backend | Consumed by |
|---------------|---------|-------------|
| `/clusters` | GET, POST | index, ClusterTab, CatalogTab |
| `/clusters/{id}` | GET, PATCH, DELETE | ClusterTab |
| `/clusters/{id}/test` | POST | ClusterTab |
| `/kubernetes/pods?page_size=100` | GET | hooks `usePods` |
| `/kubernetes/pods/stats` | GET | hooks `usePods` |
| `/kubernetes/pods/{id}` | GET, DELETE | ClusterControlPlane |
| `/kubernetes/pods/{id}/logs?tail=200` | GET | components `LogViewerDialog` |
| `/kubernetes/pods/{id}/restart` | POST | hooks `usePodActions` |
| `/kubernetes/pods/{id}/events` | GET | components |
| `/kubernetes/pods/deployments/{name}/scale` | POST | components `ScaleDialog` |
| `/kubernetes/pods/workloads/{deployments,statefulsets,daemonsets}` | GET | ClusterControlPlane |
| `/kubernetes/pods/network/{services,ingresses}` | GET | ClusterControlPlane |
| `/kubernetes/pods/batch/jobs` | GET | ClusterControlPlane |
| `/kubernetes/pods/config/{configmaps,secrets}` | GET | ClusterControlPlane |
| `/kubernetes/pods/autoscaling/hpa` | GET | ClusterControlPlane |
| `/observability/metrics/cluster?range=` | GET | ObservabilityTab |
| `/observability/metrics/pods?range=&top=10` | GET | ObservabilityTab |
| `/observability/metrics/namespaces` | GET | ObservabilityTab |
| `/observability/logs?pod=` | GET | ObservabilityTab |
| `/devops-alerts?status=&severity=` | GET, POST | AlertsTab |
| `/devops-alerts/stats` | GET | AlertsTab |
| `/devops-alerts/{id}` | DELETE | AlertsTab |
| `/devops-alerts/{id}/{acknowledge,mute,resolve,escalate}` | POST | AlertsTab |
| `/gitops?health_status=&sync_status=` | GET, POST | GitOpsTab |
| `/gitops/stats/summary` | GET | GitOpsTab |
| `/gitops/{id}` | GET, PATCH, DELETE | GitOpsTab |
| `/gitops/{id}/sync` | POST | GitOpsTab |
| `/gitops/{id}/rollback` | POST | GitOpsTab |
| `/gitops/{id}/history?limit=20` | GET | GitOpsTab |
| `/pipelines?page_size=30` | GET | hooks `usePipelines` |
| `/pipelines/stats` | GET | hooks `usePipelines` |
| `/pipelines/{id}/rerun?failed_only=` | POST | hooks `usePipelineActions` |
| `/pipelines/{id}/cancel` | POST | hooks `usePipelineActions` |
| `/pipelines/{id}/jobs` | GET | components |
| `/catalog/services?status=&type=&search=` | GET, POST | CatalogTab, hooks |
| `/catalog/stats` | GET | hooks `useCatalogServices` (**zero importers — dead**) |
| `/ws/{tenant_id}` | WebSocket | `WebSocketContext` |

**No orphaned frontend calls, no missing backend routes.** The contract is clean.

---

## 4. Integration Matrix

| Integration | Client | Powers which UI | Configured | Live-proven reachable | Verdict |
|-------------|--------|-----------------|-----------|----------------------|---------|
| Kubernetes API | `app/integrations/kubernetes/client.py` | Control Plane (all tabs), pod list/stats/logs/events/restart/delete/exec/scale, cluster test | yes | **no** (`127.0.0.1:6443` refused) | NOT_CONFIGURED — but real calls are made and real errors surface |
| GitHub Actions | `app/integrations/github/client.py` | Pipelines list, rerun, rerun-failed, cancel, jobs drawer, catalog repo creation | yes (invalid PAT) | **no** | **BROKEN** — BUG-001 kills mutations at the code level |
| GitLab CI | `app/integrations/gitlab/client.py` | Same, for GitLab tenants | no | n/a | NOT_CONFIGURED (client is correctly written — sets `self._headers` at `:17`) |
| ArgoCD | `app/integrations/gitops/argocd_client.py` | GitOps sync, rollback, live status | no | n/a | NOT_CONFIGURED — returns honest 503 |
| Prometheus | `app/integrations/observability/prometheus.py` | Observability time-series | no | n/a | NOT_CONFIGURED — honest `source: "unavailable"` |
| metrics-server | via K8s client | Pod CPU/memory snapshot | no | n/a | NOT_CONFIGURED |
| Redis | `app/core/rate_limit.py` | Rate limiting, cache | no | n/a | In-process fallback active and **proven working** (§9.4) |
| WebSocket (in-process) | `app/api/v1/websocket/manager.py` | Live pod/pipeline refresh | yes | **yes** | VERIFIED for one instance; **not** multi-instance (no pub/sub) |
| Slack / Stripe / SendGrid / Sentry / AWS | respective dirs | none in DevOps Center | no | n/a | Out of scope for this page |

**Key point:** the Kubernetes integration was exercised against a real (unreachable) endpoint,
so the audit distinguishes *code defects* from *environment gaps*. BUG-001, 002 and 004 are
code defects — they fail identically with a healthy cluster.

---

## 5. Kubernetes Audit

### 5.1 What was actually called

The server log during a single Control-Plane page load shows nine distinct real API calls,
each retried three times by `urllib3`, each failing:

```
/apis/apps/v1/deployments                       → Connection refused
/apis/apps/v1/statefulsets                      → Connection refused
/apis/apps/v1/daemonsets                        → Connection refused
/api/v1/services                                → Connection refused
/apis/networking.k8s.io/v1/ingresses            → Connection refused
/apis/batch/v1/jobs                             → Connection refused
/api/v1/configmaps                              → Connection refused
/api/v1/secrets                                 → Connection refused
/apis/autoscaling/v2/horizontalpodautoscalers   → Connection refused
```

So the resource tabs are **not** stubbed. They make real calls. The defect is what they return
afterwards (BUG-009).

### 5.2 Pod operations, live results

| Operation | HTTP | Response | Verdict |
|-----------|------|----------|---------|
| `GET /kubernetes/pods` | 200 | 4 real rows from DB | VERIFIED |
| `GET /kubernetes/pods/stats` | 200 | `total 4, running 2, pending 1, failed 1, cpu 37.0, mem 64.8, high_restart 1` | VERIFIED |
| `GET /kubernetes/pods/{id}` | 200 | Full pod detail, 19 fields | VERIFIED |
| `GET /kubernetes/pods/{id}/logs` | 502 | `"could not fetch pod logs: HTTPSConnectionPool(...)"` | Honest failure |
| `GET /kubernetes/pods/{id}/events` | 200 | real call path | VERIFIED path |
| `POST /kubernetes/pods/{id}/restart` | 502 | `"Pod api-gateway-7d9f8-x2k4p not found in namespace prod"` | Honest failure — **but see BUG-002** |
| `POST /kubernetes/pods/{id}/exec` | **200** | `{"success":true,"data":{"output":"exec failed: (0)\nReason: [Errno 111] Connection refused\n"}}` | **BUG-004** |
| `DELETE /kubernetes/pods/{id}` | 502 | `"'_K8sApis' object has no attribute 'V1DeleteOptions'"` | **BUG-002** |
| `POST .../deployments/{name}/scale` | **200** | `code:"SUCCESS"`, `data.success:false`, raw exception in `message` | **BUG-006** |

### 5.3 BUG-002 in detail (latent, cluster-dependent)

`client.py:36-66` defines `_K8sApis`, a shim that deliberately exposes only API *classes*
(`CoreV1Api`, `AppsV1Api`, `BatchV1Api`, `AutoscalingV2Api`, `CustomObjectsApi`) so that each
integration gets a private `ApiClient` and tenants cannot cross-wire. `V1DeleteOptions` is a
*model*, not an API class, so the shim does not expose it.

Two call sites assume it does:

```python
# client.py:334-335  (delete_pod)
# V1DeleteOptions — import from kubernetes.client directly (v29 compatible)
delete_opts = k8s.V1DeleteOptions(grace_period_seconds=0)

# client.py:383      (restart_pod)
delete_opts = k8s.V1DeleteOptions(grace_period_seconds=30)
```

The comment on line 334 states the correct approach; the code does not implement it.

Unit-level proof:

```
shim exposes V1DeleteOptions?  False
PROVEN AttributeError: '_K8sApis' object has no attribute 'V1DeleteOptions'
kubernetes.client.V1DeleteOptions -> <class '...v1_delete_options.V1DeleteOptions'>
```

Why it is *latent* for restart but *immediate* for delete: `restart_pod` calls
`read_namespaced_pod` first and returns early on failure, so with an unreachable cluster the
bug is masked. Against a **healthy** cluster both paths would raise. This is precisely the
class of defect that passes every test and dies in production.

### 5.4 Resource tabs

All nine return `HTTP 200`, `data: []`, `message: "OK"` while the cluster is down. The UI
renders "No deployments", "No services", "No secrets" — indistinguishable from an empty
cluster. **BUG-009.**

### 5.5 Cluster client resolution

`KubernetesService.get_k8s_client_for_tenant` falls back to `integrations[0]` when the
`cluster_id` filter matches nothing. Probed with a bogus `cluster_id`:

```
GET /kubernetes/pods/namespaces?cluster_id=99999999-...  → 200 ["jobs","prod"]
```

No error is raised; the request silently runs against a different cluster's credentials. In a
multi-cluster tenant this reads (and could mutate) the wrong cluster.

---

## 6. CI/CD Audit

### 6.1 Read path — works

| Endpoint | Result |
|----------|--------|
| `GET /pipelines?page_size=30` | 200, real rows from DB |
| `GET /pipelines/stats` | 200, real aggregates |
| `GET /pipelines/repositories` | 200, `["audit-org/api"]` (unused by UI) |
| Filters (`status`) | Reach the backend and work |

### 6.2 Mutation path — completely dead (BUG-001)

`GitHubClient.__init__` stores only `self.token`; the class defines `_build_headers()` (line 21)
but never assigns `self._headers`. Three methods reference the non-existent attribute:

| Line | Method |
|------|--------|
| 260 | `rerun_workflow_run` |
| 291 | `rerun_failed_jobs` |
| 316 | `cancel_workflow_run` |

Unit-level proof, with a syntactically valid token:

```
has attr _headers: False
rerun_workflow_run     -> {'success': False, 'run_id': 12345, 'error': "'GitHubClient' object has no attribute '_headers'"}
rerun_failed_jobs      -> {'success': False, 'run_id': 12345, 'error': "'GitHubClient' object has no attribute '_headers'"}
cancel_workflow_run    -> {'success': False, 'run_id': 12345, 'error': "'GitHubClient' object has no attribute '_headers'"}
```

No HTTP request is issued. Over HTTP:

```
POST /pipelines/{id}/rerun?failed_only=true → 502  github integration error: 'GitHubClient' object has no attribute '_headers'
POST /pipelines/{id}/cancel                 → 502  github integration error: 'GitHubClient' object has no attribute '_headers'
```

**Consequence for the user:** the Re-run, Re-run Failed Jobs and Cancel buttons in
Delivery → Pipelines can never succeed, for any tenant, with any token, regardless of GitHub
availability. `POST /catalog/services` also dies at its `create_repo` step for the same reason
(`deployment_logs`: `failed: GitHub authentication failed (invalid token?)`).

By contrast `get_run_jobs` uses the correct `_get()` helper and reached a real HTTPS request —
confirming the bug is isolated to the three mutation methods. The GitLab client sets
`self._headers` correctly at line 17, so this is a GitHub-only regression.

### 6.3 State-machine guards — work correctly

| Case | HTTP | Message |
|------|------|---------|
| Re-run a pipeline that is already running | 422 | `"Pipeline is already running — cannot re-run"` |
| Cancel a pipeline that already succeeded | 422 | `"Pipeline is 'success' — only active pipelines can be cancelled"` |

### 6.4 `GET /pipelines/{id}/jobs`

Returns **HTTP 500** rather than a mapped 502 when the provider raises `GitHubAPIError`. In
this sandbox the trigger was TLS interception; the *defect* is that provider errors are not
translated into the `INTEGRATION_ERROR` envelope, so the client receives an opaque 500.

### 6.5 Contract note

`pipelines.py GET ""` deliberately returns a **bare** `PaginatedResponse` (source comment
`BUG-P2-02`) while `pods.py GET ""` returns the **double** envelope `APIResponse[PaginatedResponse]`.
The frontend's `unwrap()` handles both, and `usePipelines` normalises with
`Array.isArray(data) ? data : data?.data ?? data ?? []`, so the list renders correctly either
way. Verified: pipelines are not silently empty.

---

## 7. GitHub Audit

| Surface | Status | Evidence |
|---------|--------|---------|
| Client construction | OK | `GitHubClient(config)` stores token |
| Read methods (`_get`) | Correct implementation | `get_run_jobs` reached a real HTTPS request |
| `rerun_workflow_run` | **BROKEN** | BUG-001 |
| `rerun_failed_jobs` | **BROKEN** | BUG-001 |
| `cancel_workflow_run` | **BROKEN** | BUG-001 |
| Catalog repo creation | **BROKEN** | `deployment_logs.create_repo → failed` |
| Webhook receiver | Present, not exercised | `app/api/webhooks/github.py` |
| Secret exposure in responses | Clean | Regex sweep of `/clusters`, `/integrations`, `/integrations/{id}` found no credential material |

**No `GITHUB_TOKEN` was available**, so even after fixing BUG-001 a successful round-trip could
not be demonstrated here. The claim is therefore: *the mutations are broken in code*, which is
proven; *they would work once fixed* is **not** claimed.

---

## 8. GitLab Audit

**NOT_CONFIGURED.** No GitLab integration is registered for either tenant, and no GitLab
credential exists.

Code inspection only (explicitly *not* live verification): `app/integrations/gitlab/client.py`
assigns `self._headers` in `__init__` at line 17 and uses it consistently at lines 27, 47, 62,
76, 90, 107, 137, 158, 187 — i.e. it does **not** carry the GitHub defect.

The UI handles this correctly: Delivery → Pipelines shows the `GitHub / GitLab not connected`
empty state with a link to `/settings/integrations` when `gitConnected` is false.

---

## 9. WebSocket Audit

Endpoint: `/ws/{tenant_id}` (`app/main.py`), token passed as a query parameter.

### 9.1 Handshake authentication and tenant binding — VERIFIED

```
no token                                 -> REJECTED  InvalidStatusCode
garbage token                            -> REJECTED  InvalidStatusCode
tenant A path + tenant B JWT             -> REJECTED  InvalidStatusCode
tenant B path + tenant A JWT             -> REJECTED  InvalidStatusCode
tenant A path + tenant A JWT             -> ACCEPTED  (connection open)
tenant B path + tenant B JWT             -> ACCEPTED  (connection open)
```

The path tenant must match the token tenant. Cross-tenant attachment is refused.

### 9.2 Protocol robustness — VERIFIED

```
ping             -> {"event":"pong","data":{"time":"2026-09-19T23:02:37.768391+00:00"}}
malformed JSON   -> {"event":"error","data":{"message":"Invalid JSON"}}
unknown event    -> {"event":"error","data":{"message":"Unknown event type: totally.bogus.event"}}
subscribe        -> {"event":"subscribed","data":{"channels":["pod.update","pipeline.update"],"status":"ok"}}
ping AFTER abuse -> {"event":"pong",...}   <- connection survived
```

Malformed input produces a clean error frame and does **not** drop the connection.

### 9.3 Cross-tenant event isolation — VERIFIED

The server was asked to publish a system event into tenant A only:

```
tenant A received: {"event":"system.message","data":{"system":true,"marker":"FROM_TENANT_A"}}
tenant B received: NOTHING  -> tenant isolation HOLDS
```

### 9.4 Architectural limit — single instance only

`app/api/v1/websocket/manager.py` keeps connections in an in-process
`dict[tenant_id, list[WebSocket]]`. There is **no Redis pub/sub**. Consequences:

* With more than one backend replica, an event raised on replica A never reaches a client
  attached to replica B. The frontend's 60 s fallback poll (`hooks.ts:14`) masks this, so it
  would present as "updates are slow" rather than an obvious break.
* `ws_manager.broadcast()` — used by `scheduler._sync_pods` — iterates every tenant key in the
  process. It is a deliberate fan-out, but it means a pod-sync event is emitted to all tenants
  at once; per-tenant payloads are not filtered at that layer.

`handlers.py` `subscribe`/`unsubscribe` only log and echo the channel list; they do not
actually filter which events a socket receives. Client-side filtering in
`WebSocketContext` is what makes this appear to work.

---

## 10. Logs Audit

### 10.1 Two separate log paths

| Path | Endpoint | Live result |
|------|----------|-------------|
| Pod log viewer (`LogViewerDialog`) | `GET /kubernetes/pods/{id}/logs?tail=200` | **502** with the real provider error — surfaces as an error in the dialog |
| Observability log search | `GET /observability/logs?pod=<name>` | **200** `{"pod":"worker-5b7c6-j8k9l","namespace":null,"lines":[],"total":0,"filtered":0,"message":"Pod ..."}` — honest empty |

Both are honest. Neither fabricates log lines.

### 10.2 Audit logging — VERIFIED

The `AuditMiddleware` (outermost, order RateLimit → CORS → Logging → JWTAuth → **Audit**)
records every DevOps mutation, including failures:

```
170 audit rows, 0 with a NULL user_id
distinct actions: POST:restart 82, POST:sync 14, POST:cancel 14, POST:services 10,
                  POST:exec 10, POST:devops-alerts 10, POST:clusters 10, POST:rerun 4,
                  DELETE:pods 4, deployment.scale 2, POST:test 2, POST:scale 2,
                  POST:rollback 2, POST:gitops 2, DELETE:gitops 2
```

Domain-level audit rows carry full context:

```
action=deployment.scale  resource=deployment  resource_id=prod/api-gateway
status=failed  user_id=651260b8-cbfd-4836-9d33-58cd234fa8a7
details={"replicas": 3, "namespace": "prod", "success": false}
```

A sweep for credential leakage in audit payloads (`token`, `password`, `kubeconfig`) returned
**nothing** — no secrets are written to the audit trail.

Gap worth noting: service-level `_write_audit` rows are written only after a successful
provider call, so failed pod/pipeline mutations produce only the generic middleware row. A
trail still exists (with `resource_id` and `status: failure`), but it lacks the domain
`action` label.

### 10.3 Application log quality

Provider failures are logged with full context and are not swallowed silently — e.g.
`K8s list_deployments failed: HTTPSConnectionPool(...)`. The problem is that this information
does not reach the HTTP response (BUG-009).

---

## 11. API Contract Audit

### 11.1 Resolution

**38 / 38** distinct frontend API paths resolve to a real backend route (§3.5). No orphans.

### 11.2 Envelope inconsistency (tolerated by the client)

| Endpoint | Shape |
|----------|-------|
| `pods.py GET ""` | `APIResponse[PaginatedResponse]` — double-wrapped |
| `pipelines.py GET ""` | bare `PaginatedResponse` (source comment `BUG-P2-02`) |
| `catalog.py GET /services` | raw `{success, data, total, page, page_size}` |
| `devops_alerts.py GET ""` | no `total` field |

`unwrap()` in `src/hooks/use-api.ts` strips the outer envelope when `success`/`data`/`message`
are all present, then returns the paginated object when `data` is an array and `total` is a
number. `usePods`/`usePipelines` additionally normalise with
`Array.isArray(data) ? data : data?.data ?? data ?? []`. **Verified: no list silently renders
empty because of the inconsistency.** It is still a latent hazard for any new caller that
does not use these helpers.

### 11.3 PATCH semantics

`AppUpdate` (gitops.py:203-207) accepts only `health_status`, `sync_status`,
`current_revision`, `sync_message`. Sending `path` or `repo_url` is silently ignored (200, no
change). Probed:

```
PATCH /gitops/{id} {"path":"apps/flow-v2"}  → 200, path unchanged
PATCH /gitops/{id} {"sync_status":"OutOfSync"} → 200, sync_status=OutOfSync  ✓
```

The frontend only PATCHes allowed fields, so this is not currently user-visible.

### 11.4 Duplicate route families

Two parallel GitOps APIs exist:

* `/gitops/{id}/sync`, `/gitops/{id}/rollback` — used by the UI
* `/gitops/applications/{id}/sync`, `/gitops/applications/{id}/rollback`, `/gitops/applications/{id}/status` — unused by the UI

No shadowing (distinct prefixes). The unused `status` endpoint is honest about its source:

```
{"app_name":"audit-app-a","sync_status":"Unknown","health_status":"Unknown",
 "message":"ArgoCD not connected — showing cached state","source":"db"}
```

### 11.5 Other endpoints verified live but unused by the UI

`GET /pipelines/repositories` → `["audit-org/api"]`;
`GET /kubernetes/pods/clusters` → `["audit-cluster-a"]`;
`GET /kubernetes/pods/namespaces` → `["jobs","prod"]`.

### 11.6 `deps.py`

`DEVOPS_MUTATION_ROLES = {admin, super_admin, devops_engineer}`; `CATALOG_CREATE_ROLES`
additionally includes `developer`. `DevOpsUser` is declared twice in the module — harmless
duplication, but a maintenance trap.

---

## 12. Database / Redis Audit

### 12.1 Database

SQLite via `aiosqlite` for this audit; the app is written against SQLAlchemy async and targets
PostgreSQL in production.

Tables exercised with real rows: `users`, `tenants`, `integrations`, `clusters`, `pods`,
`pipelines`, `gitops_apps`, `devops_alerts`, `catalog_services`, `deployment_logs`,
`audit_logs`.

Every read and write path in the DevOps Center is tenant-scoped. Confirmed by direct query and
by the isolation tests in §14.

Schema notes discovered while seeding:

* `pods` uses a plain `cluster` string column, not a `cluster_id` foreign key — so pods cannot
  be joined reliably to `clusters`.
* `pods.containers` and `pods.labels` are `NOT NULL` with no server default.
* `gitops_apps` has several `NOT NULL` columns (`source_type`, `target_revision`) that
  `AppCreate` supplies via defaults rather than validation.

### 12.2 Redis

**Absent from the environment.** `apt-get install redis-server` → *Unable to locate package*;
no Docker available either. The startup log confirms the app degrades:

```
[MLListener] Connection lost: Error 111 connecting to localhost:6379
```

Two subsystems depend on Redis:

1. **Rate limiting** — falls back to an in-process sliding window. **Proven working** (§14.5).
2. **WebSocket fan-out** — no fallback exists (§9.4). Multi-instance deployments silently lose
   live updates.

### 12.3 Stray artifacts in the repository

`test.db`, `uniops_dev.db`, `dump.rdb`, `trace.log`, `backend/uniops_dev.db`,
`backend/celerybeat-schedule`, `logs/{app,backend,frontend}.log` are committed or present at
repo root. `backend/uniops_dev.db` shows as modified after any local run. These should be
gitignored.

---

## 13. Background Jobs Audit

### 13.1 Scheduler

`app/core/scheduler.py` runs an in-process scheduler. `app/main.py` lifespan honours
`BACKGROUND_LEADER` — verified: with `BACKGROUND_LEADER=false`,
`getattr(settings, "BACKGROUND_LEADER", True)` → `False` and no jobs start.

| Job | Interval | Status |
|-----|----------|--------|
| `_sync_pods` | 120 s (first run +30 s) | **DESTRUCTIVE — BUG-003** |
| pod watcher (`k8s.events`) | streaming | Logs `K8s watch stream ended (audit-k8s-a)` on failure — honest |
| pipeline sync | on demand via `POST /pipelines/sync` | 200 `{"status":"syncing"}` — background task queued |
| deployment engine | async after `POST /catalog/services` | Runs, fails honestly at `create_repo` |

### 13.2 BUG-003 — the pod wipe

`app/tasks/sync_pods.py` upserts everything returned by `list_all_pods()`, then deletes every
pod row not seen. `KubernetesClient.list_all_pods()`
(`app/integrations/kubernetes/client.py:214-222`) returns `[]` **on exception**, so an
unreachable API server is indistinguishable from an empty cluster.

Direct proof against the audit database:

```
before: GET /kubernetes/pods/stats → total 4
_sync_pods() → {'integrations': 2, 'pods_synced': 0, 'pods_deleted': 4}
after:  GET /kubernetes/pods/stats → total 0
```

The UI then renders an honest-looking but false **"No pods running"**. Two minutes later the
same thing happens in production during any API-server blip, and the pod inventory is gone
until a successful sync repopulates it.

### 13.3 Deployment engine

`POST /catalog/services` returns **202 Accepted** and runs asynchronously. Observed end state:

```
service status = 'Failed'      repo_url = None
deployment_logs[create_repo] = failed: GitHub authentication failed (invalid token?)
```

The status vocabulary (`Pending`, `Running`, `Deploying`, `Failed`, `Stopped`) matches exactly
what `CatalogTab.tsx:791-793, 906` filters on — no casing mismatch. The failure is surfaced,
not hidden. Root cause is BUG-001 upstream.

---

## 14. Security Audit

### 14.1 Authentication — VERIFIED

| Case | HTTP |
|------|------|
| No `Authorization` header | 401 |
| Garbage token | 401 |
| Tampered token | 401 |
| Valid `admin_a` token | 200 |

Harness note recorded for transparency: the probe initially set `JWT_SECRET_KEY` via
`os.environ.setdefault`, which overrode `backend/.env` because environment variables outrank
`env_file` in pydantic-settings — producing a 401 storm. The probe now imports
`app.config.settings` so both sides derive the same key. Not a product defect.

### 14.2 Tenant isolation — VERIFIED against real rows

`scripts/audit_isolation.py` inserts a pod and a GitOps app that genuinely belong to tenant B
(`namespace=confidential`), then attacks them as tenant A's admin and re-reads the database:

```
seeded tenant-B pod f66f0a02-11f7-4ad0-815a-3385b4014015 (namespace=confidential)

  [✓] GET    /kubernetes/pods/{id}          -> HTTP 404 | row still in DB: True
  [✓] GET    /kubernetes/pods/{id}/logs     -> HTTP 404 | row still in DB: True
  [✓] GET    /kubernetes/pods/{id}/events   -> HTTP 404 | row still in DB: True
  [✓] POST   /kubernetes/pods/{id}/restart  -> HTTP 404 | row still in DB: True
  [✓] POST   /kubernetes/pods/{id}/exec     -> HTTP 404 | row still in DB: True
  [✓] DELETE /kubernetes/pods/{id}          -> HTTP 404 | row still in DB: True
  [✓] A's pod list does NOT contain B's pod  (names=[])

  [✓] GET as owner (tenant B) -> HTTP 200        <- control: the row is real and readable

  [✓] GET    /pipelines/{B id}          -> 404
  [✓] POST   /pipelines/{B id}/cancel   -> 404
  [✓] POST   /pipelines/{B id}/rerun    -> 404
  [✓] GET    /clusters/{B id}           -> 404 | row alive: True
  [✓] POST   /clusters/{B id}/test      -> 404 | row alive: True
  [✓] PATCH  /clusters/{B id}           -> 404 | row alive: True
  [✓] DELETE /clusters/{B id}           -> 404 | row alive: True
```

An earlier probe round reused a pod UUID that no longer existed, so its 404s proved nothing.
Those results were discarded and re-run as above. **No IDOR found** across pods, pipelines,
clusters, gitops reads, or the WebSocket handshake.

### 14.3 RBAC grid — VERIFIED server-side

| Actor | Pod restart | Pod exec | Pipeline cancel | Create cluster | Create alert | GitOps sync | Catalog create |
|-------|-------------|----------|-----------------|----------------|--------------|-------------|----------------|
| `viewer_a` | 403 | 403 | 403 | 403 | 403 | 403 | — |
| `dev_a` (developer) | 403 | 403 | 403 | 403 | 403 | 403 | **409 name collision** (passed RBAC, as designed) |
| `devops_a` | allowed | allowed | allowed | **201** | **201** | 503 (ArgoCD) | allowed |
| `admin_a` | allowed | allowed | allowed | **201** | **201** | 503 (ArgoCD) | allowed |

Enforcement is in `deps.py` via `DevOpsUser`, not in the client. `canAct` in the UI is
cosmetic.

### 14.4 Rate limiting — VERIFIED (in-process fallback)

`pod.restart` is declared at 30 requests / 60 s. 35 rapid calls produced:

```
[502 ×28, 429 ×7]   -> 429 fires exactly at the declared limit (2 earlier calls in the window)
```

Declared limits confirmed in source: pod.restart 30, pod.delete 20, pod.exec 10,
deployment.scale 20, pipeline.rerun/cancel 15, pipeline.sync 20, gitops.create 10,
gitops.sync 20, gitops.rollback 10, clusters.* 10, catalog.create 10, catalog.delete 20.

Caveat: the in-process fallback is per-worker, so with multiple replicas the effective limit is
`N × limit`. Redis is required for correctness.

### 14.5 Secret handling — clean

A regex sweep for `token` / `secret` / `password` / `kubeconfig` followed by a value across
`/clusters`, `/clusters/{id}`, `/integrations`, `/integrations/{k8s_id}`,
`/integrations/{github_id}` found **no credential material**. The secrets tab exposes key
names only, never values. Audit payloads contain no secrets (§10.2).

### 14.6 Concerns

| Item | Detail |
|------|--------|
| `verify=False` | All `_argocd_*` calls in `gitops.py` use `httpx.AsyncClient(verify=False)` — TLS verification disabled. Would allow MITM against an ArgoCD server. |
| Pod `exec` | Real shell-less arg vector, rate-limited to 10/60 s, audited. Gated to admin/devops. **But BUG-004 makes failures look like successes**, which is a security-relevant mis-signal. |
| Cluster client fallback | `integrations[0]` when `cluster_id` does not match (§5.5) — wrong-cluster access within a tenant. |
| `DevOpsUser` declared twice | `app/api/deps.py` — maintenance trap. |
| Middleware order | RateLimit → CORS → Logging → JWTAuth → Audit. Rate limiting runs **before** authentication, so limits are keyed on unauthenticated requests where no user id exists. |

---

## 15. Fake / Mock Data Audit

The full DevOps Center code path was searched for `mock`, `demo`, `sample`, `fake`,
`placeholder`, `fallback`, `hardcoded`, `seed`, `Math.random`, `static arrays`, `fake success`,
`NoOp`, `TODO`.

**Finding: there is essentially no fabricated data in this codebase.** That is a genuine
strength. Specifics:

| Mechanism | Present? | Evidence |
|-----------|----------|----------|
| `Math.random` / randomised demo values | **No** | No hits in `pages/DevOpsCenter/` |
| Hardcoded static arrays posing as API data | **No** | Every list is fetched; `STATUS_COLOR`/`STATUS_DOT`/`SUB_TABS` are presentation constants only |
| Mock API client / MSW / fixtures | **No** | `useApi` calls the real `apiClient` |
| `NoOp` provider stubs | **No** | |
| Simulated latency to fake work | **One** | Refresh button `await sleep(800)` in `index.tsx` — purely cosmetic spinner, does not fabricate data |
| Fallback that hides a provider failure | **Yes ×3** | BUG-005, BUG-006, BUG-009 |

### 15.1 BUG-005 — the one fabricated dataset, and its fix

`app/api/v1/endpoints/observability.py` did this in **two** places (lines 134 and 209 at
`HEAD`):

```python
pod_dict = p if isinstance(p, dict) else (p.to_dict() if hasattr(p, "to_dict") else {})
```

`svc.list_pods()` returns `PodResponse` pydantic models. Proof:

```
PodResponse bases: ['PodResponse', 'BaseModel', 'object']
has to_dict: False
has model_dump: True
fields: ['cluster','containers','cpu_limit','cpu_request','cpu_usage','created_at','id',
         'integration_id','labels','memory_limit','memory_request','memory_usage','name',
         'namespace','node','phase','restart_count','status','tenant_id','updated_at']
```

So `pod_dict` was `{}` for **every** pod, and every field fell through to its default.
This was the only place in the DevOps Center that rendered invented values as if they were
measurements, and it poisoned two panels.

The fix is the root cause, one expression, applied at both sites, no behaviour change beyond
using the correct serialiser:

```python
if isinstance(p, dict):
    pod_dict = p
elif hasattr(p, "model_dump"):
    pod_dict = p.model_dump()
elif hasattr(p, "to_dict"):
    pod_dict = p.to_dict()
else:
    pod_dict = {}
```

#### `GET /observability/metrics/pods` — proven before / after on the same four rows

| Field | BEFORE | AFTER |
|-------|--------|-------|
| `source` | `"unavailable"` | `"k8s_metrics"` |
| names | `unknown` × 4 | `worker-5b7c6-j8k9l`, `api-gateway-7d9f8-x2k4p`, `payments-6c8d9-m1n2q`, `frontend-4a6b5-p3q4r` |
| namespaces | `default` × 4 | `jobs`, `prod`, `prod`, `prod` |
| statuses | `Unknown` × 4 | `CrashLoopBackOff`, `Running`, `Running`, `Pending` |
| `cpu_pct` | `null` × 4 | `45.0`, `24.0`, `42.0`, `null` |
| `memory_pct` | `null` × 4 | `97.7`, `37.1`, `59.6`, `null` |

The `Pending` pod correctly still reports `null` — the fix reads real values rather than
inventing them.

#### `GET /observability/metrics/namespaces` — proven before / after

The identical expression in `get_namespace_metrics` collapsed every pod into one namespace:

```json
BEFORE  (original expression executed against the 4 real PodResponse rows)
[
  { "namespace": "default", "pod_count": 4,
    "cpu_pct": null, "memory_pct": null, "has_metrics": false }
]

AFTER   (live endpoint response)
[
  { "namespace": "jobs", "pod_count": 1, "cpu_pct": 45.0, "memory_pct": 97.7, "has_metrics": true },
  { "namespace": "prod", "pod_count": 3, "cpu_pct": 33.0, "memory_pct": 48.3, "has_metrics": true }
]
```

Checked against the database:

```
SELECT namespace, count(*), avg(cpu_usage*100/cpu_limit), avg(memory_usage*100/memory_limit)
  FROM pods WHERE cpu_limit>0 AND memory_limit>0 GROUP BY namespace;
  ('jobs', 1, 45.0, 97.7)
  ('prod', 2, 33.0, 48.3)
```

The `prod` pod count differs (3 vs 2) only because that SQL excludes the `Pending` pod, which
has no resource limits; the endpoint correctly counts all three and still averages only the
two that have metrics.

Regression check: full backend suite **290 passed, 0 failed** both before and after.

### 15.2 Honest degradation confirmed (these are *not* fakes)

| Endpoint | Response when provider absent |
|----------|-------------------------------|
| `/observability/metrics/cluster` | `source: "unavailable"`, `"No metrics backend connected (prometheus or metrics-server)"` |
| `/observability/logs` | `source: "unavailable"`, `lines: []` |
| `/gitops/stats/summary` | `argocd_connected: false` |
| `/gitops` list | `message: "argocd=disconnected"` |
| `/gitops/{id}/sync` | **503** `"ArgoCD not connected — sync requires an ArgoCD integration"` |
| `/gitops/{id}/rollback` | **503** `"ArgoCD not connected — rollback requires an ArgoCD integration"` |
| `/gitops/applications/{id}/status` | `source: "db"`, `"ArgoCD not connected — showing cached state"` |
| `/clusters` rows | `status: "disconnected"`, `error_message: "No kubeconfig provided and no in-cluster config available"` |
| Catalog service after failed repo creation | `status: 'Failed'`, `repo_url: null`, `deployment_logs` records the reason |

This is the correct pattern, and it is applied consistently — with the three exceptions above.

---

## 16. Bugs Found

### BUG-001 — All GitHub CI/CD mutations are dead code

| Field | Value |
|-------|-------|
| **ID** | BUG-001 |
| **Severity** | **P0** — core advertised functionality is unreachable |
| **Feature** | Delivery → Pipelines: Re-run, Re-run Failed Jobs, Cancel. Catalog → Create Service (repo step) |
| **Location** | `backend/app/integrations/github/client.py:260, 291, 316` (uses `self._headers`) vs `:21` (defines `_build_headers()`) |
| **Expected** | Re-run/cancel issue a real GitHub API call with `Authorization: Bearer <token>` |
| **Actual** | `AttributeError` before any request. HTTP 502 `INTEGRATION_ERROR` |
| **Root Cause** | `GitHubClient.__init__` never assigns `self._headers`. Three mutation methods reference it; read methods correctly call `self._build_headers()` |
| **Evidence** | `hasattr(client,'_headers') → False`; all three return `{'success': False, 'error': "'GitHubClient' object has no attribute '_headers'"}`; live `POST /pipelines/{id}/rerun` and `/cancel` → 502 with that message |
| **External Dependency** | None — fails with or without a valid token or network |
| **Recommended Fix** | Replace `headers=self._headers` with `headers=self._build_headers()` at all three sites (or assign `self._headers = self._build_headers()` lazily, since `_build_headers` raises on an empty token). Add a unit test that constructs the client and calls each method with a stubbed transport |

### BUG-002 — Pod delete and restart reference a model class the client shim does not expose

| Field | Value |
|-------|-------|
| **ID** | BUG-002 |
| **Severity** | **P0** — destructive operations broken; latent until a real cluster is attached |
| **Feature** | Control Plane → pod force-delete; pod restart |
| **Location** | `backend/app/integrations/kubernetes/client.py:335` and `:383`; shim defined at `:36-66` |
| **Expected** | `V1DeleteOptions(grace_period_seconds=…)` is constructed and passed to `delete_namespaced_pod` |
| **Actual** | `AttributeError: '_K8sApis' object has no attribute 'V1DeleteOptions'` → HTTP 502 |
| **Root Cause** | `_K8sApis` intentionally exposes only API classes (`CoreV1Api`, `AppsV1Api`, `BatchV1Api`, `AutoscalingV2Api`, `CustomObjectsApi`). `V1DeleteOptions` is a model. The comment at line 334 describes the correct fix but the code does not implement it |
| **Evidence** | `hasattr(_K8sApis(None),'V1DeleteOptions') → False`; `PROVEN AttributeError: '_K8sApis' object has no attribute 'V1DeleteOptions'`; live `DELETE /kubernetes/pods/{id}` → 502 with that message. In `restart_pod` the bug is masked by an earlier `read_namespaced_pod` failure, so it would only surface against a **healthy** cluster |
| **External Dependency** | None for the defect; a healthy cluster is needed to observe the restart variant |
| **Recommended Fix** | `from kubernetes.client import V1DeleteOptions` and use it directly at both sites. Add a unit test that calls `delete_pod`/`restart_pod` with a mocked `CoreV1Api` so the AttributeError is caught without a cluster |

### BUG-003 — Pod sync deletes the entire pod inventory when the API server is unreachable

| Field | Value |
|-------|-------|
| **ID** | BUG-003 |
| **Severity** | **P1** — data loss |
| **Feature** | Background pod sync feeding Control Plane and the header stat cards |
| **Location** | `backend/app/tasks/sync_pods.py` (reconciliation loop); `backend/app/integrations/kubernetes/client.py:214-222` (`list_all_pods` returns `[]` on exception); scheduled at `backend/app/core/scheduler.py:35` every 120 s |
| **Expected** | An unreachable API server is an error; existing rows are preserved |
| **Actual** | All pod rows deleted |
| **Root Cause** | `list_all_pods()` swallows the exception and returns `[]`. The sync then treats "not returned" as "no longer exists" and deletes every row |
| **Evidence** | `_sync_pods() → {'integrations': 2, 'pods_synced': 0, 'pods_deleted': 4}`; `GET /kubernetes/pods/stats` total went **4 → 0**. Fixture pods vanished within ~2 minutes of seeding on the first run of this audit |
| **External Dependency** | Triggered by any API-server outage or network blip |
| **Recommended Fix** | Distinguish "empty result" from "call failed": have `list_all_pods` raise or return `(pods, ok)`. Skip the delete phase unless the list call succeeded for that integration. Add a test with a raising client asserting zero deletions |

### BUG-004 — Pod exec reports success when the command failed

| Field | Value |
|-------|-------|
| **ID** | BUG-004 |
| **Severity** | **P1** — false success on a security-sensitive operation |
| **Feature** | Control Plane → pod exec terminal |
| **Location** | `backend/app/integrations/kubernetes/client.py:492-494` |
| **Expected** | A failed exec surfaces as an error (HTTP 502 / `success: false`) |
| **Actual** | HTTP 200, `success: true`, failure text inside `data.output` |
| **Root Cause** | `except Exception as e: return f"exec failed: {e}"` returns a **string**, which the endpoint wraps as `APIResponse(data={"output": output})` — indistinguishable from real command output |
| **Evidence** | `{"success":true,"data":{"output":"exec failed: (0)\nReason: [Errno 111] Connection refused\n"},"message":"OK","code":"SUCCESS"}` |
| **External Dependency** | Any exec failure (unreachable API server, missing container, RBAC denial) |
| **Recommended Fix** | Raise `KubernetesIntegrationError` from the `except` block so the endpoint returns 502 `INTEGRATION_ERROR`. Never encode an error as return data |

### BUG-005 — Observability pod and namespace metrics fabricated  *(FIXED, both sites)*

| Field | Value |
|-------|-------|
| **ID** | BUG-005 |
| **Severity** | **P1** — invented data presented as measurement |
| **Feature** | Observability → Pod Metrics panel **and** Namespace breakdown panel; also starves Restart Spikes and Error Rate |
| **Location** | `backend/app/api/v1/endpoints/observability.py` — `get_pod_metrics` (line 134 at `HEAD`) and `get_namespace_metrics` (line 209 at `HEAD`) |
| **Expected** | Real pod name, namespace, status, CPU%, memory% from the synced pod rows |
| **Actual** | Every pod row `{"name":"unknown","namespace":"default","status":"Unknown","cpu_pct":null,"memory_pct":null}` while `pods/stats` reported 4 real pods with CPU 37.0% / memory 64.8%; the namespace panel showed a single `default` row with 4 pods and null metrics |
| **Root Cause** | `PodResponse` is a pydantic `BaseModel` with no `to_dict()`; the fallback produced `{}` for every pod at both call sites |
| **Evidence** | Before/after tables in §15.1. `has to_dict: False`, `has model_dump: True` |
| **External Dependency** | None |
| **Recommended Fix** | **Applied at both sites**: prefer `model_dump()`. Proven before/after on real rows; suite green at 290 passed both before and after. Note the pod response still omits `restart_count`, so Restart Spikes stays empty — see BUG-011 |

### BUG-006 — Deployment scale returns HTTP 200 SUCCESS on failure

| Field | Value |
|-------|-------|
| **ID** | BUG-006 |
| **Severity** | **P1** — false success on a mutation |
| **Feature** | Control Plane → Scale dialog |
| **Location** | `pods.py` scale endpoint returning `APIResponse(data=result, message=result.message)` where `result.success` is `False` |
| **Expected** | HTTP 502 / `success: false` at the envelope level |
| **Actual** | HTTP 200, `code: "SUCCESS"`, `data.success: false`, raw `HTTPSConnectionPool(...)` in `message`. The UI's `ScaleDialog` toasts `json.message` as a success message |
| **Root Cause** | The service returns a result object instead of raising, and the endpoint forwards it without inspecting `result.success` |
| **Evidence** | `{"success":true,"data":{"success":false,"error":"HTTPSConnectionPool(host='127.0.0.1', port=6443)..."},"message":"HTTPSConnectionPool(...)","code":"SUCCESS"}` |
| **External Dependency** | Any scale failure |
| **Recommended Fix** | Raise `KubernetesIntegrationError` when `result.success` is false, or set the envelope `success` flag from `result.success` and map the status code accordingly |

### BUG-007 — Cluster "Test Connection" says "Connection successful" for a disconnected cluster

| Field | Value |
|-------|-------|
| **ID** | BUG-007 |
| **Severity** | **P2** — false success, misleading operator signal |
| **Feature** | Clusters → Test Connection |
| **Location** | `backend/app/services/cluster_service.py:156-164` |
| **Expected** | Message reflects the health-check outcome |
| **Actual** | HTTP 200 with `status: "disconnected"`, `node_count: 0`, `message: "Connection successful"`. The UI renders a red toast labelled "Connection successful" |
| **Root Cause** | `_run_health_check` silently sets `status = "disconnected"` when `_build_client` returns `None` and does not raise; `test_connection` then returns the success message unconditionally |
| **Evidence** | `{"status":"disconnected","k8s_version":null,"node_count":0,"message":"Connection successful"}` |
| **External Dependency** | None |
| **Recommended Fix** | Derive the message from the resolved status; return `success: false` / 502 when disconnected |

### BUG-008 — GitOps delete always reports success

| Field | Value |
|-------|-------|
| **ID** | BUG-008 |
| **Severity** | **P2** — false success; **not** a data leak |
| **Feature** | Delivery → GitOps → Remove app |
| **Location** | `backend/app/api/v1/endpoints/gitops.py:483-497` |
| **Expected** | 404 when the app does not exist or belongs to another tenant |
| **Actual** | 204 in every case |
| **Root Cause** | The query **is** tenant-filtered (`GitOpsApp.tenant_id == tenant_id`), so nothing is deleted — but the handler returns 204 unconditionally with no rowcount check |
| **Evidence** | `A DELETEs B's app → HTTP 204 | row still in DB: True`; `A DELETEs a random UUID → HTTP 204`; control `B DELETEs its own app → HTTP 204 | row still in DB: False` |
| **External Dependency** | None |
| **Recommended Fix** | `if not app: raise HTTPException(404, "App not found")` before deleting |

### BUG-009 — Control-Plane resource tabs report success with empty data when the cluster is down

| Field | Value |
|-------|-------|
| **ID** | BUG-009 |
| **Severity** | **P2** — hides a provider failure behind an empty state |
| **Feature** | Control Plane → Workloads, Network, Jobs, Config, Autoscaling tabs (9 endpoints) |
| **Location** | `backend/app/integrations/kubernetes/client.py` list methods (each catches and logs, returning `[]`), surfaced through the resource endpoints |
| **Expected** | An unreachable cluster produces an error the UI can show |
| **Actual** | HTTP 200, `message: "OK"`, `data: []` for all nine. The UI shows "No deployments / No services / No secrets", indistinguishable from an empty cluster |
| **Root Cause** | Provider exceptions are logged and converted to empty lists, with no error signal propagated to the response envelope |
| **Evidence** | All nine → `http=200 empty=True error_signal='OK'`, while the server log records nine distinct failing calls (`/apis/apps/v1/deployments`, `/api/v1/services`, `/api/v1/secrets`, `/apis/autoscaling/v2/horizontalpodautoscalers`, …), each retried three times |
| **External Dependency** | Triggered by any API-server outage |
| **Recommended Fix** | Return an explicit degraded envelope (e.g. `source: "unavailable"` as the observability endpoints already do) so the UI can render "cluster unreachable" instead of "nothing here" |

### BUG-010 — The DevOps Center cluster selector has no effect

| Field | Value |
|-------|-------|
| **ID** | BUG-010 |
| **Severity** | **P2** — a visible control that does nothing |
| **Feature** | DevOps Center header cluster dropdown |
| **Location** | `artifacts/uniops/src/pages/DevOpsCenter/index.tsx:88, 214-215, 235` |
| **Expected** | Selecting a cluster scopes pods, workloads and metrics to it |
| **Actual** | `selectedClusterId` is read only to render the dropdown's own label and highlight. It is never passed to `ClusterControlPlane`, `PlatformObservability`, `DeliveryGitOps` or `CatalogTab`, and never sent as a query parameter |
| **Root Cause** | State is created and consumed inside the header component only |
| **Evidence** | `grep -rn "selectedClusterId" *.tsx` → 4 hits, all inside the header block |
| **External Dependency** | None |
| **Recommended Fix** | Thread the value into the tabs and into `usePods`/the resource queries as a `cluster_id` parameter — or remove the control until it can be honoured. Compounds the wrong-cluster fallback in §5.5 |

### BUG-011 — Restart Spikes can never show data

| Field | Value |
|-------|-------|
| **ID** | BUG-011 |
| **Severity** | **P2** — permanently empty panel |
| **Feature** | Observability → Restart Spikes |
| **Location** | `ObservabilityTab.tsx:286-300` filtering `p.restart_count > 0` over `/observability/metrics/pods` |
| **Expected** | Top 5 pods by restart count |
| **Actual** | Always "No restart events detected" |
| **Root Cause** | The `metrics/pods` response schema never includes `restart_count`, even though `PodResponse.restart_count` exists and is populated (`pods/stats` reports `high_restart_count: 1`) |
| **Evidence** | Response fields are `name, namespace, status, cpu_pct, memory_pct, cpu_timeseries, memory_timeseries` — no `restart_count`. `pods/stats` for the same data returns `high_restart_count: 1` |
| **External Dependency** | None |
| **Recommended Fix** | Add `"restart_count": pod_dict.get("restart_count")` to the emitted pod object |

### BUG-012 — Pod detail CPU/memory bars read fields that do not exist

| Field | Value |
|-------|-------|
| **ID** | BUG-012 |
| **Severity** | **P2** — always-zero gauges |
| **Feature** | Pod detail drawer CPU / Memory usage bars |
| **Location** | `components.tsx` `PodDetail` reading `p['cpu_usage_pct']` / `p['memory_usage_pct']` |
| **Expected** | Percentage bars driven by real usage |
| **Actual** | Both keys absent from the API response → `undefined` → bars render 0% |
| **Root Cause** | Frontend expects derived percentage fields the backend never emits; the backend provides raw `cpu_usage`/`cpu_limit`/`memory_usage`/`memory_limit` |
| **Evidence** | `GET /kubernetes/pods/{id}` keys: `cluster, containers, cpu_limit, cpu_request, cpu_usage, created_at, id, integration_id, labels, memory_limit, memory_request, memory_usage, name, namespace, node, phase, restart_count, status, tenant_id, updated_at`. `cpu_usage_pct present? False`, `memory_usage_pct present? False` |
| **External Dependency** | None |
| **Recommended Fix** | Compute the percentage in the component from `cpu_usage`/`cpu_limit`, or add the derived fields to `PodResponse` |

### BUG-013 — Catalog `total` ignores filters

| Field | Value |
|-------|-------|
| **ID** | BUG-013 |
| **Severity** | **P2** — wrong pagination metadata |
| **Feature** | Catalog service list pagination |
| **Location** | `backend/app/api/v1/endpoints/catalog.py` `GET /services` |
| **Expected** | `total` reflects the filtered result set |
| **Actual** | `GET /catalog/services?search=zzz` → `data: []` but `total: 5` |
| **Root Cause** | `total` is computed from the unfiltered count |
| **Evidence** | Live probe, §Section 3 of `/tmp/probe2.log` |
| **External Dependency** | None |
| **Recommended Fix** | Apply the filter before counting |

### BUG-014 — Chart gradient colour is an invalid CSS colour

| Field | Value |
|-------|-------|
| **ID** | BUG-014 |
| **Severity** | **P3** — cosmetic |
| **Feature** | Observability metric area charts |
| **Location** | `ObservabilityTab.tsx:86-87` |
| **Expected** | A valid hex colour for `stopColor` |
| **Actual** | `'text-blue-400'.replace('text-','#').replace('-400','')` → `"#blue"`, which is not a valid colour, so the gradient silently does not render |
| **Root Cause** | Tailwind class names string-munged into CSS colours |
| **Evidence** | Source line read directly |
| **External Dependency** | None |
| **Recommended Fix** | Keep an explicit colour map alongside the class names |

### BUG-015 — Dead code in the DevOps Center hook layer

| Field | Value |
|-------|-------|
| **ID** | BUG-015 |
| **Severity** | **P3** — cleanup |
| **Feature** | `hooks.ts` |
| **Location** | `useCatalogServices` and `useDevOpsRBAC` |
| **Expected** | Used, or removed |
| **Actual** | **Zero** references anywhere in `src/` outside their own definitions. `CatalogTab` implements its own fetch and its own RBAC checks instead |
| **Root Cause** | Superseded implementations left behind |
| **Evidence** | `grep -rn` across `src/` → `refs=0` for both |
| **External Dependency** | None |
| **Recommended Fix** | Delete, or migrate `CatalogTab` onto them. Note `/catalog/stats` is fetched only by the dead hook, so that endpoint currently has no live consumer |

### BUG-016 — Duplicate pod fetches across sibling tabs

| Field | Value |
|-------|-------|
| **ID** | BUG-016 |
| **Severity** | **P3** — redundant load |
| **Feature** | `usePods()` |
| **Location** | `index.tsx:105`, `ClusterControlPlane.tsx:53`, `PlatformObservability.tsx:29` |
| **Expected** | One fetch shared via a query cache |
| **Actual** | Three independent hook instances, each with its own `useApi` state and its own HTTP request. `useApi` is hand-rolled (`src/hooks/use-api.ts`), not TanStack Query, so there is no deduplication |
| **Root Cause** | Per-component fetching without a cache layer |
| **Evidence** | Three distinct `usePods()` call sites; `useApi` implements its own `useState`/`useEffect` fetch |
| **External Dependency** | None |
| **Recommended Fix** | Lift pod state to a context or adopt the query cache used elsewhere in the app |

### BUG-017 — Stale comment misdescribes the pod action contract

| Field | Value |
|-------|-------|
| **ID** | BUG-017 |
| **Severity** | **P3** — maintenance trap |
| **Feature** | `usePodActions` / `usePodLogs` |
| **Location** | `hooks.ts` — `// podId = "namespace/name"` and `// podId is "namespace/name" — maps to /:namespace/:name/logs` |
| **Expected** | Comments match the code |
| **Actual** | Call sites pass the DB UUID (`podActions.restart(pod.id)` at `ClusterControlPlane.tsx:86-87`), and the backend routes are `/{pod_id}/...` with a single path segment. If anyone follows the comment and passes `"namespace/name"`, the URL gains a segment and 404s |
| **Root Cause** | Left over from an earlier route shape |
| **Evidence** | Route table shows `/kubernetes/pods/{pod_id}/logs`; call site passes `pod.id` |
| **External Dependency** | None |
| **Recommended Fix** | Correct the comments to say "pod database UUID" |

### BUG-018 — Native `window.confirm` for destructive actions

| Field | Value |
|-------|-------|
| **ID** | BUG-018 |
| **Severity** | **P3** — UX inconsistency |
| **Feature** | Alert delete, cluster delete, GitOps app delete |
| **Location** | `AlertsTab.tsx:352`, `ClusterTab.tsx:592`, `GitOpsTab.tsx:445` |
| **Expected** | The app's own confirmation dialog, consistent with pod delete |
| **Actual** | Browser `window.confirm`, unstyled and unthemed |
| **Root Cause** | Ad-hoc implementation |
| **Evidence** | Three `window.confirm` call sites |
| **External Dependency** | None |
| **Recommended Fix** | Use the existing confirmation dialog component |

### BUG-019 — Unhandled provider error becomes an opaque HTTP 500

| Field | Value |
|-------|-------|
| **ID** | BUG-019 |
| **Severity** | **P2** — error contract |
| **Feature** | Pipelines → Jobs drawer |
| **Location** | `GET /pipelines/{id}/jobs` |
| **Expected** | `GitHubAPIError` mapped to 502 `INTEGRATION_ERROR` |
| **Actual** | HTTP 500 "Internal server error" |
| **Root Cause** | `get_run_jobs` propagates `GitHubAPIError` out of the endpoint without a handler |
| **Evidence** | Unit call raised `GitHubAPIError`; endpoint returned 500. In this sandbox the trigger was TLS interception, so the *trigger* was environmental — the *missing error mapping* is not |
| **External Dependency** | Any GitHub API failure |
| **Recommended Fix** | Catch `GitHubAPIError`/`GitLabAPIError` and return the standard 502 envelope |

---

## 17. Environment-Blocked Features

These could **not** be verified here because the dependency is absent. They are **not** claimed
broken, and they are **not** claimed working.

| Feature | Blocker | What was verified instead |
|---------|---------|---------------------------|
| Real pod logs | No cluster | Endpoint issues a real call and returns 502 with the genuine provider error |
| Pod restart / delete success path | No cluster | Blocked earlier by BUG-002 (delete) and by the `read_namespaced_pod` pre-check (restart) |
| Deployment scale success path | No cluster | Blocked; failure path mis-reported (BUG-006) |
| Workload / network / batch / config / autoscaling listings | No cluster | All nine issue real calls; all return honest-shaped but unlabelled empties (BUG-009) |
| GitOps sync / rollback | No ArgoCD | 503 with an explicit, correct message |
| GitOps live status & diff | No ArgoCD | `source: "db"` with `"showing cached state"` |
| Metrics time-series | No Prometheus | `source: "unavailable"` with an explanatory message |
| GitHub pipeline mutations success path | No valid token **and** BUG-001 | Proven broken in code before any network call |
| Catalog repo creation | No valid GitHub token **and** BUG-001 | Fails at `create_repo`, records the reason in `deployment_logs` |
| Distributed rate limiting | No Redis | In-process fallback proven correct at the declared limit |
| Multi-instance WebSocket fan-out | No Redis / single process | Single-instance isolation proven; multi-instance is an architectural gap |
| GitLab pipelines | No integration | Client code inspected only — explicitly not live-verified |
| `mypy` / `ruff` at project settings | Python 3.11 vs target 3.12 | Not run |

---

## 18. Verified Features

Each row below is backed by a live HTTP response or a direct database read captured during
this audit — not by source inspection.

| Feature | Evidence |
|---------|----------|
| Authentication rejects missing / garbage / tampered tokens, accepts valid | 401 / 401 / 401 / 200 |
| Tenant isolation on pods (read, logs, events, restart, exec, delete) | 6/6 → 404, rows survived, owner could read (control 200) |
| Tenant isolation on pipelines (read, cancel, rerun) | 3/3 → 404 |
| Tenant isolation on clusters (read, test, patch, delete) | 4/4 → 404, rows alive |
| Tenant isolation on GitOps read / sync | → 404 |
| Tenant isolation on the WebSocket handshake | Cross-tenant JWT rejected |
| Cross-tenant event isolation | Tenant B received nothing from a tenant-A publish |
| RBAC — `viewer_a` blocked on 6 mutation classes | all 403 |
| RBAC — `dev_a` blocked on mutations but allowed catalog create | 403s, then 409 name collision |
| RBAC — `devops_a` / `admin_a` may create clusters and alerts | 201 / 201 |
| Rate limiting fires at the declared limit | `pod.restart` 30/60 s → `[502 ×28, 429 ×7]` |
| Pipeline list + stats | 200, real rows |
| Pipeline filters reach the backend | `status` filter works |
| Pipeline state-machine guards | 422 "already running"; 422 "only active pipelines can be cancelled" |
| `POST /pipelines/sync` | 200 `{"status":"syncing"}` |
| Pod list, stats, detail | 200, 4 real rows, `total 4 / running 2 / pending 1 / failed 1 / cpu 37.0 / mem 64.8` |
| Pod namespace / status / search filters | all reach the backend and filter correctly |
| Cluster CRUD lifecycle | 201 → read-back → PATCH persisted → DELETE → subsequent GET 404 |
| **Alert full lifecycle** | 201 → acknowledge → `acknowledged` → mute → `muted` → resolve → `resolved` → DELETE 204. `stats` reflected the change (`resolved: 1`) |
| GitOps CRUD lifecycle | 201 → PATCH `sync_status=OutOfSync` persisted → history 200 → DELETE → subsequent GET 404 |
| GitOps sync / rollback honest refusal | 503 with explicit ArgoCD message |
| Catalog create → async pipeline → honest failure | 202 → `status='Failed'`, `repo_url=None`, `deployment_logs[create_repo]=failed` with reason |
| Catalog status / search filters | reach the backend and filter |
| Observability pod metrics (after BUG-005 fix) | Real names, namespaces, statuses, `cpu_pct` 45.0 / 24.0 / 42.0, `memory_pct` 97.7 / 37.1 / 59.6; `source: "k8s_metrics"` |
| WebSocket ping / malformed / unknown-event / subscribe | clean frames, connection survives abuse |
| Audit trail for every mutation | 170 rows, 0 null `user_id`, no secrets leaked |
| Domain audit detail on scale | `action=deployment.scale, resource_id=prod/api-gateway, status=failed, user_id=…, details={"replicas":3,"namespace":"prod","success":false}` |
| No secrets in any integration or cluster payload | regex sweep clean |
| Backend test suite | **290 passed, 0 failed** |
| Frontend build | PASS, 13.03 s |
| API contract completeness | 38 / 38 frontend paths resolve |

---

## 19. Broken Features

| Feature | Status | Blocking bug |
|---------|--------|--------------|
| Delivery → Pipelines → **Re-run** | **BROKEN** | BUG-001 |
| Delivery → Pipelines → **Re-run failed jobs** | **BROKEN** | BUG-001 |
| Delivery → Pipelines → **Cancel** | **BROKEN** | BUG-001 |
| Delivery → Pipelines → **Jobs drawer** | **BROKEN** (opaque 500) | BUG-019 |
| Catalog → **Create Service** (repo creation step) | **BROKEN** | BUG-001 |
| Control Plane → **Force-delete pod** | **BROKEN** | BUG-002 |
| Control Plane → **Restart pod** | **BROKEN against a healthy cluster** | BUG-002 (latent) |
| Control Plane → **Scale deployment** | **BROKEN** (reports success on failure) | BUG-006 |
| Control Plane → **Exec into pod** | **BROKEN** (reports success on failure) | BUG-004 |
| Observability → **Pod Metrics** | **FIXED during audit** | BUG-005 |
| Observability → **Namespace breakdown** | **FIXED during audit** | BUG-005 |
| Observability → **Restart Spikes** | **BROKEN** (always empty) | BUG-011 |
| Observability → **Error Rate** | **DEGRADED** — derives from the same endpoint | BUG-005 (fixed), BUG-011 |
| Pod detail → **CPU / Memory bars** | **BROKEN** (always 0%) | BUG-012 |
| Clusters → **Test Connection** | **BROKEN** (false success message) | BUG-007 |
| Control Plane → **9 resource tabs** | **BROKEN when cluster is down** (silent empties) | BUG-009 |
| Header → **Cluster selector** | **BROKEN** (no effect) | BUG-010 |
| Delivery → GitOps → **Remove app** | **PARTIAL** (deletes own app, lies about the rest) | BUG-008 |
| Catalog → **pagination total** | **BROKEN** | BUG-013 |
| Background pod sync | **DESTRUCTIVE** | BUG-003 |
| Multi-instance live updates | **BROKEN by design** | no Redis pub/sub |

---

## 20. Recommended Fix Plan

### Phase 1 — Unblock the product (must ship before any production claim)

| Order | Bug | Change | Effort | Verification |
|-------|-----|--------|--------|--------------|
| 1 | BUG-001 | `headers=self._build_headers()` at `github/client.py:260, 291, 316` | XS | Unit test constructing the client and calling each method against a stubbed transport |
| 2 | BUG-002 | `from kubernetes.client import V1DeleteOptions`; use directly at `:335` and `:383` | XS | Unit test with a mocked `CoreV1Api`; no cluster needed |
| 3 | BUG-003 | Make `list_all_pods` distinguish failure from empty; skip the delete phase on failure | S | Test with a raising client asserting `pods_deleted == 0` |
| 4 | BUG-004 | Raise `KubernetesIntegrationError` instead of returning `f"exec failed: {e}"` | XS | Assert 502 rather than 200 |
| 5 | BUG-006 | Raise / map `result.success == False` to the error envelope | XS | Assert 502 and `success: false` |

**These five are all small and all provable without external infrastructure.** Together they
convert the Pipelines tab, pod delete, pod restart, pod exec, pod scale and catalog repo
creation from broken to functional.

### Phase 2 — Stop lying to the operator

| Order | Bug | Change | Effort |
|-------|-----|--------|--------|
| 6 | BUG-007 | Derive the test-connection message from the resolved status | XS |
| 7 | BUG-009 | Return `source: "unavailable"` (as observability already does) from the nine resource endpoints when the provider call failed | S |
| 8 | BUG-008 | `if not app: raise HTTPException(404)` in `delete_app` | XS |
| 9 | BUG-019 | Catch `GitHubAPIError` / `GitLabAPIError` → 502 `INTEGRATION_ERROR` | XS |
| 10 | BUG-011 | Add `restart_count` to the `metrics/pods` payload | XS |
| 11 | BUG-012 | Compute CPU/memory percentages in `PodDetail` from the raw fields already returned | S |
| 12 | BUG-013 | Count after filtering in `catalog.py` | XS |

### Phase 3 — Correctness and scale

| Order | Item | Change |
|-------|------|--------|
| 13 | BUG-010 | Thread `selectedClusterId` into the tabs and the API calls, or remove the control |
| 14 | §5.5 | Remove the `integrations[0]` fallback in `get_k8s_client_for_tenant`; 404 when the cluster is not found |
| 15 | §14.6 | Replace `verify=False` in the ArgoCD client with proper TLS verification |
| 16 | §9.4 | Add Redis pub/sub to `ws_manager`, or document single-instance as a hard deployment constraint |
| 17 | §14.6 | Move rate limiting after authentication so limits key on identity |
| 18 | BUG-014/015/016/017/018 | Frontend cleanup: valid gradient colours, delete dead hooks, deduplicate pod fetching, fix stale comments, replace `window.confirm` |

### Phase 4 — Prevent recurrence

* Add a **contract test** that walks every path the DevOps Center calls and asserts the
  envelope shape and required fields. BUG-005, BUG-011 and BUG-012 are all schema drift that a
  single contract test would have caught.
* Add an **"unreachable provider" test class**: point a fixture integration at a dead address
  and assert that *no* endpoint returns 200 with success semantics. That one test catches
  BUG-003, BUG-004, BUG-006, BUG-007 and BUG-009 simultaneously.
* Add a **smoke test per integration client** that instantiates the client and calls every
  public method against a stubbed transport. BUG-001 and BUG-002 are both
  "attribute does not exist" errors that any such test would surface in milliseconds, and both
  survived a 290-test suite.
* Raise coverage `fail_under` beyond the current 70 % on three modules, and include
  `integrations/` in the measured set.

---

## 21. Final Verdict

# NOT READY

### Why

The DevOps Center is real software with real integrations, honest degradation in most places,
strong tenant isolation, working server-side RBAC, working rate limiting and a complete audit
trail. **38 of 38** frontend API calls resolve, the backend suite is **290 passed / 0 failed**,
and the frontend builds clean. None of that is in dispute.

But the question asked was whether the **complete flow works** — and for a substantial set of
visible controls it does not, for reasons that have nothing to do with the missing
infrastructure in this sandbox:

1. **The entire CI/CD mutation surface is dead code.** Re-run, Re-run Failed Jobs and Cancel
   raise `AttributeError` before a single byte is sent to GitHub. No token, permission or
   network condition can make them succeed (BUG-001).
2. **Pod force-delete is dead code**, and pod restart carries the identical defect behind an
   earlier guard that a healthy cluster would remove (BUG-002).
3. **A background job deletes the whole pod inventory** on any API-server blip, and the UI then
   reports a confident, false "No pods running" (BUG-003).
4. **Three operations report success when they failed** — exec returns the provider's
   connection error as command output under `success: true` (BUG-004), scale returns
   `code: "SUCCESS"` with `data.success: false` (BUG-006), and Test Connection says
   "Connection successful" about a disconnected cluster (BUG-007).
5. **Nine resource tabs render "nothing here" when the cluster is unreachable**, with no error
   signal at all (BUG-009).
6. **Two panels and two gauges can never display data** — Restart Spikes, and the pod-detail
   CPU/memory bars — because the API omits fields the components read (BUG-011, BUG-012).
7. **The cluster selector in the header does nothing** (BUG-010).

A 200 status code was explicitly not treated as evidence, and that discipline is what
surfaced items 4, 5 and 7 — all of which return HTTP 200.

### What would change the verdict

* **CONDITIONAL** — Phase 1 complete (BUG-001, 002, 003, 004, 006) plus Phase 2 items 6-9, with
  the "unreachable provider" test class added and green. At that point the honest remaining
  gaps are configuration gaps (ArgoCD, Prometheus, GitLab, Redis) rather than code defects.
* **PRODUCTION VERIFIED** — the above, plus a live round-trip against a real cluster, a real
  GitHub token, a real ArgoCD server and Redis, demonstrating state change in each source
  system.

### Already banked from this audit

BUG-005 is **fixed and proven at both call sites** in
`backend/app/api/v1/endpoints/observability.py` — a 21-line, two-hunk change whose entire
substance is preferring `model_dump()` over the non-existent `to_dict()`.

* Pod Metrics went from four fabricated `unknown / Unknown / null` rows to real pods with real
  percentages (`worker-5b7c6-j8k9l / jobs / CrashLoopBackOff / cpu 45.0 / mem 97.7`); `source`
  moved from `"unavailable"` to `"k8s_metrics"`; the `Pending` pod correctly still reports
  `null`.
* The Namespace breakdown went from one invented `default` row with null metrics to
  `jobs (1 pod, 45.0 / 97.7)` and `prod (3 pods, 33.0 / 48.3)`, matching the database.
* The backend suite returns **290 passed, 0 failed** both with the fix stashed and with it
  applied.

Everything else in this report is documented, not patched.

---

## Appendix A — Evidence artifacts

| Artifact | Contents |
|----------|----------|
| `/tmp/probe2.log` (629 lines) | 8-section live probe: auth, reads, filters, IDOR, RBAC grid, mutations, rate limits, dead endpoints |
| `/tmp/flows.log` | Six end-to-end CRUD lifecycles with read-back after each mutation |
| `/tmp/pytest2.log` | `290 passed, 21 warnings in 493.91s` |
| `backend/scripts/audit_fixture.py` | Two-tenant fixture seeder |
| `backend/scripts/audit_probe.py` | Live HTTP probe |
| `backend/scripts/audit_isolation.py` | Cross-tenant attack with DB read-back |
| `backend/scripts/audit_flows.py` | CRUD lifecycle flows |
| `backend/scripts/audit_ws_probe.py` | WebSocket probe |
| `backend/.audit_ids.json` | Fixture identifiers |
| `backend/audit.db` | Audit database (untracked) |

## Appendix B — Reproducing

```bash
# backend
cd backend
.venv/bin/python scripts/audit_fixture.py                     # seed two tenants
DATABASE_URL="sqlite+aiosqlite:///./audit.db" \
RATE_LIMIT_ENABLED=false OTEL_SDK_DISABLED=true \
LOG_LEVEL=WARNING BACKGROUND_LEADER=false \
  .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

.venv/bin/python scripts/audit_probe.py       # 8-section probe
.venv/bin/python scripts/audit_isolation.py   # cross-tenant proof
.venv/bin/python scripts/audit_flows.py       # CRUD lifecycles
.venv/bin/python scripts/audit_ws_probe.py    # WebSocket
.venv/bin/python -m pytest -q -p no:cacheprovider

# frontend
cd artifacts/uniops && pnpm install --no-frozen-lockfile && pnpm build
```

`BACKGROUND_LEADER=false` is required only because BUG-003 otherwise wipes the fixture pods
within two minutes. Removing that flag reproduces BUG-003 directly.

## Appendix C — Method

**DISCOVER** — enumerated the DevOps Center from `App.tsx` routing, `Sidebar.tsx` navigation,
and the four section components; extracted all 38 API paths from source.

**MAP** — resolved each path against the live `/openapi.json`; traced UI → hook → endpoint →
service → integration → database for every feature; mapped RBAC and rate-limit declarations.

**TEST** — seeded a two-tenant fixture with real rows, started the backend, and ran ~140 live
HTTP calls plus WebSocket sessions. No mutation was accepted on a 200 alone; every one was
followed by a read-back of the API and/or a direct database query.

**PROVE** — for each suspected defect, reproduced it at the narrowest level that isolates the
cause (unit-level attribute checks for BUG-001 and BUG-002, a direct `_sync_pods()` invocation
for BUG-003, a before/after response capture for BUG-005), and re-ran the cross-tenant tests
against rows that were confirmed to exist.

**CLASSIFY** — VERIFIED only where a live response or database read demonstrates the behaviour;
NOT_CONFIGURED / BLOCKED where a dependency is absent; BROKEN / FAKE where a fallback hides a
real provider failure.

**REPORT** — this document.

An earlier probe round produced 404s for pod routes because the fixture had been re-seeded and
`.audit_ids.json` still held stale UUIDs. Those results were **discarded** and re-run; the
tenant-isolation claims in §14.2 rest on rows seeded and confirmed inside
`audit_isolation.py` itself.
