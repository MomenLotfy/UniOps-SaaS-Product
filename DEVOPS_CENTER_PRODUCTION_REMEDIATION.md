# DevOps Center — Production Remediation Report

**Repository:** `MomenLotfy/UniOps-SaaS-Product`
**Branch:** `arena/01a0bbd6-uniops-saas-product`
**Baseline commit:** `29b139a96ccf8c44f186ef927a73f99ae1ea8573`
**Authority:** `DEVOPS_CENTER_PRODUCTION_AUDIT.md` (19 findings, BUG-001 … BUG-019)
**Phases completed:** P0 (baseline), P1 (critical correctness), P2 (provider
honesty), P4 (frontend correctness)
**Phase not started:** P3 — excluded by standing instruction

**Overall status: CODE-VERIFIED — not PRODUCTION VERIFIED.**
See [§9 Verification status](#9-verification-status) for exactly what was and was not proven.

---

## 1. Summary

**Eighteen of the nineteen audit findings are fixed** — all six P0/P1
critical-correctness bugs, all seven P2 provider-honesty bugs, and all five P4
frontend-correctness bugs. Only **BUG-010** remains, which sits in P3 (excluded
by standing instruction). A shared provider-failure contract was introduced so
the fix is one convention rather than thirteen one-off patches. A dedicated
DevOps Center regression suite of **396 tests** was added, including the two
mandatory classes the audit required (reconciliation safety and cluster
routing).

The single organising principle behind every change:

> **"The provider returned no data" and "the provider could not be reached" are
> different facts, and an operator is entitled to be told which one happened.**

Before this work the DevOps Center conflated them everywhere. A dead cluster
rendered as a healthy cluster with zero resources; a failed `kubectl scale`
returned HTTP 200 `SUCCESS`; an unreachable Kubernetes API caused the pod-sync
job to delete every pod row in the database.

| | Before | After |
|---|---|---|
| Backend test suite | 290 passed | **686 passed, 0 failed** |
| DevOps regression suite | none | **396 tests** in `backend/tests/devops/` |
| Provider failure → HTTP | 200 + `success: true` | 502/503 + `INTEGRATION_ERROR` |
| Dead cluster in UI | empty lists, "connected" | explicit "Cluster unavailable" |
| Sync on provider failure | deleted all pod rows | deletes nothing |
| Metric area fills | invalid `#blue` → rendered black | real `#60a5fa` gradient |
| Destructive confirms | blocking `window.confirm` ×3 | in-app `ConfirmDialog` ×3 |
| Pod fetches per view | 2 requests, half discarded | only what each view renders |
| Audit findings resolved | 0 / 19 | **18 / 19** |

---

## 2. Baseline (P0)

Captured before any application code was modified.

| Check | Command | Result |
|---|---|---|
| Backend suite | `.venv/bin/python -m pytest -q -p no:cacheprovider` | **290 passed, 0 failed** in 507.54 s |
| Frontend build | `pnpm build` | **PASS** in 12.75 s |

**Environment constraints (all confirmed, none assumed):**

- Python 3.11.2 via `backend/.venv` (system Python — `backend/venv` is a dangling
  nix symlink and unusable; `pyproject.toml` targets 3.12, so static analysis
  runs on a 3.11 interpreter — see §8 for what that does and does not prove).
- Node v22.22.3, pnpm 9.15.9.
- **No Docker, no Redis, no PostgreSQL, no Kubernetes cluster, no live GitHub /
  GitLab / ArgoCD / Prometheus credentials.** `sudo apt-get install redis-server`
  fails with `Unable to locate package`. `fakeredis` is importable and used only
  in tests.

**Caveat on the baseline number.** The baseline run's collection window opened
before the first Phase 1 edit landed, so 290 is "290 at HEAD at collection time"
rather than a pristine pre-remediation figure. Historical runs at this commit
also returned 290/0, so 290 is the correct expected clean count. This is
recorded rather than smoothed over.

---

## 3. Shared provider-failure contract (new)

**File:** `backend/app/integrations/base.py`

Rather than inventing a second error envelope, the existing exception hierarchy
was reused and one mapper was added on top of it:

```python
raise_for_provider_failure(result: dict, integration: str) -> dict
```

It returns the result dict when the provider call succeeded, otherwise raises
the exception that already maps to the correct HTTP status:

| Provider condition | Exception raised | HTTP | Code |
|---|---|---|---|
| transport/auth failure | `IntegrationError` | 502 | `INTEGRATION_ERROR` |
| provider unreachable / not connected | `IntegrationUnavailableError` | 503 | `INTEGRATION_UNAVAILABLE` |
| resource does not exist | `NotFoundError` | 404 | `NOT_FOUND` |
| invalid state for the operation | `ConflictError` | 409 | `CONFLICT` |

Classification is driven by lowercase marker tuples (`_UNAVAILABLE_MARKERS`,
`_NOT_FOUND_MARKERS`, `_CONFLICT_MARKERS`) applied to the provider's error text,
so an integration that follows the project's existing `{"success": False,
"error": "..."}` convention is handled without modification.

This is the contract every subsequent fix routes through.

---

## 4. Bugs fixed — root cause and resolution

### BUG-001 — GitHub mutations were dead (P0)

**Root cause.** `GitHubClient` referenced `self._headers`, but nothing ever
assigned it. Every mutating call (`rerun`, `rerun-failed-jobs`, `cancel`,
repository creation) raised on first use. Reads happened to work because they
were built elsewhere, which is why the defect survived: the UI could list
pipelines but never act on them.

**Fix.** Centralised into `_request` / `_post` / `_build_headers()`. Header
construction now exists in exactly one place, so the four mutations cannot
drift apart again.

**Before → after.** All four mutations raised before sending a request → all
four now issue real HTTP calls with correct auth headers, verified against
per-verb status codes (`rerun`/`rerun-failed-jobs` → 201, `cancel` → **202**;
these differ and must not be parametrised as one).

---

### BUG-002 — `V1DeleteOptions` missing at both sites (P0)

**Root cause.** The `_K8sApis` shim exposes typed API objects bound to a single
`ApiClient` (deliberately, to avoid the kubernetes client's global
`Configuration` mutation cross-wiring concurrent tenants). The shim did not
re-export `V1DeleteOptions`, so both delete paths failed.

**Fix.** `V1DeleteOptions` imported from `kubernetes.client` in
`app/integrations/kubernetes/client.py`, covering **both** call sites —
force-delete (grace period 0) and restart (grace period 30).

---

### Wrong-cluster fallback — silent cross-cluster routing (P1)

**Root cause.** `get_k8s_client_for_tenant(tenant_id, cluster)` searched the
tenant's integrations for the requested cluster and, when no match was found,
fell back to `integrations[0]`. A request naming `cluster-b` was silently
executed against `cluster-a`. For read endpoints this is a wrong answer; for
`delete`/`scale`/`restart` it is a destructive action against the wrong cluster.

**Fix.** `backend/app/services/kubernetes_service.py`:

- `get_k8s_client_for_tenant` no longer falls back. `integrations[0]` is used
  **only** in the `else` branch of `if cluster:` — the documented "no cluster
  requested" default. When a cluster *was* requested and does not match, the
  method logs a warning and returns `None`.
- Added `resolve_cluster(tenant_id, cluster_id)` → raises `NotFoundError`.
  Unknown and other-tenant cluster ids are deliberately indistinguishable so
  cluster existence is not leaked across tenants.
- Added `get_client_for_cluster(tenant_id, cluster_id)` — checks the `Cluster`
  row first, then name-matched integrations.

**Architecture note that shaped this.** Kubernetes credentials live in *two*
parallel stores: `Integration(type="kubernetes")` and
`Cluster.kubeconfig_encrypted`. `Pod.cluster` is a plain **string name**, not a
foreign key. `get_client_for_cluster` therefore has to consult both.

**Verified:** `cluster-a` → `https://a.example:6443`, `cluster-b` →
`https://b.example:6443`, unknown/UUID/other-tenant → `None` (no fallback),
`resolve_cluster` on another tenant's id → `NotFoundError`.

---

### BUG-003 — Pod sync deleted every pod row when the cluster was down (P1)

**Root cause.** `_sync_pods` treated "listing returned nothing" as "the cluster
has no pods" and reconciled the database to match — deleting every row. With
the cluster unreachable, a 120-second scheduler tick wiped the entire pod table.
This was observed live during the audit: `pods_deleted: 4`.

**Fix.** Introduced an explicit success/failure result type rather than an
ambiguous empty list:

- `PodListResult` (`ok: bool`, `pods: list`, `error: str | None`)
- `KubernetesClient.list_all_pods_checked()` — backed by a **raising**
  `_list_all_pods_raw()` core
- `app/tasks/sync_pods.py` skips deletion entirely when `ok is False`, and
  `continue`s rather than deleting on unknown state

**A defect introduced and fixed during this work.** `list_all_pods_checked()`
was first implemented as a wrapper over the exception-swallowing
`list_all_pods()`, so a provider failure still reported `ok=True` — the fix did
not fix anything. The core had to be extracted so it raises. Lesson recorded:
*when adding a "checked" variant of a swallowing helper, the core must raise.*

**A second defect introduced and fixed.** The `except` handler read
`integration.id` / `integration.name` *after* `await db.rollback()`. Rollback
expires the ORM instance, so attribute access fired a lazy reload on a session
with no live connection → `MissingGreenlet`. The identifiers are now captured
before the `try`.

**Verified (class D, mandatory):** provider failure / timeout / malformed
response / raw raise → `pods_deleted == 0` and `integrations_failed == 1`;
confirmed-empty (`ok=True, pods=[]`) → `pods_deleted == 4`; partial listing →
only the 2 absent rows deleted; one tenant's failure leaves another tenant's
rows untouched.

---

### BUG-004 — Pod exec returned 200 `success: true` on failure (P1)

**Root cause.** `exec_pod` swallowed provider exceptions and returned a dict
that the endpoint rendered as a successful execution. An operator was shown a
terminal that had never connected.

**Fix.** Two layers:

- `KubernetesClient.exec_pod` raises `KubernetesProviderError` /
  `KubernetesClientUnavailable` instead of returning a failure dict.
- `KubernetesService.exec_pod` maps them: `KubernetesClientUnavailable` →
  `IntegrationUnavailableError` (503), `KubernetesProviderError` →
  `IntegrationError` (502), `ValueError` → `IntegrationError`.

`kubernetes.stream.stream` was hoisted to module scope as `k8s_stream` — it was
imported inside the function, making it unpatchable in tests.

---

### BUG-005 — Pod/namespace metrics collapsed to empty (P1)

**Root cause.** `PodResponse` is a Pydantic `BaseModel`, which has no
`to_dict()`. The endpoint called `p.to_dict()` inside a fallback chain, so every
pod serialised to `{}`.

**Fix.** `model_dump()` at **both** sites. An earlier "fix" patched only the
first occurrence (`observability.py:134`); the same expression appeared again at
L209. Lesson recorded: *grep for every occurrence of a root cause, not the first
hit.*

**Verified after:** `source: "k8s_metrics"` with real pod/namespace names, CPU
and memory; namespace aggregation matches SQL ground truth.

**Do not regress.** Both `get_pod_metrics` and `get_namespace_metrics` must keep
emitting real names, CPU and memory.

---

### BUG-006 — Deployment scale returned 200 SUCCESS on failure (P1)

**Root cause.** `scale_deployment` returned the client's
`{"success": False, "error": ...}` dict straight through. The endpoint wrapped it
in a 200 `APIResponse` with `code: "SUCCESS"` and `data.success: false` — a
contradiction the UI rendered as success.

**Fix.** No-client branch now raises `IntegrationUnavailableError`; the success
path ends with `return raise_for_provider_failure(result, "Kubernetes")`.

---

### BUG-007 — Cluster "test connection" always reported success (P2)

**Root cause.** `test_connection` returned `message: "Connection successful"`
whenever `_run_health_check` did not raise. But `_run_health_check` does **not**
raise when it cannot build a client — it records `status = "disconnected"` and
returns normally. A cluster that was never reached was reported as connected.

**Fix.** `app/services/cluster_service.py::test_connection` now raises
`IntegrationUnavailableError` when the health check raises, **and** when the
resolved `cluster.status != "connected"`. `"Connection successful"` is returned
only after a check that actually connected. The import line was widened to
`(IntegrationUnavailableError, NotFoundError, ValidationError)`.

**Verified:** disconnected → raises; exception → raises and records
`status="error"`; `status="error"` → raises carrying the provider's message;
genuinely connected → still returns success (guarding against over-correction).

---

### BUG-008 — GitOps delete returned 204 for a row that was never deleted (P2)

**Root cause.** `delete_app` deleted unconditionally and returned 204 whether or
not a row matched.

**Important correction to the audit.** This is **not** an IDOR. `gitops.py:492`
filters by `tenant_id`; tenant B's row survives an attack from tenant A. The
defect was purely the false 204.

**Fix.** `raise HTTPException(404, "App not found")` when the tenant-filtered row
is absent. **The tenant filter was preserved.**

**Verified:** absent row → 404, `db.deleted == 0`, `db.committed == 0`; the
tenant filter is asserted still present so it cannot be "fixed" away.

---

### BUG-009 — Kubernetes outage rendered as an empty cluster (P2)

**Root cause.** All nine Cluster Control Plane endpoints shared one shape:

```python
client = await svc.get_k8s_client_for_tenant(tenant_id)
if not client:
    return APIResponse(data=[])
data = await client.list_deployments(namespace)
return APIResponse(data=data)
```

And every `client.list_*` helper swallows exceptions into `[]`. Twenty-nine
`return []` sites made an unreachable cluster byte-identical to a healthy one
with no resources. `/cluster/summary` was worse: it asserted
`"connected": True` merely because a client object could be built, then reported
all-zero counts.

**Fix.** Rather than touch 29 error-swallowing call sites, one reachability seam
was added:

- `KubernetesClient.check_reachable() -> tuple[bool, str | None]` — a single
  cheap `get_api_versions` probe
- `KubernetesService.list_cluster_resource(...)` returns the degraded envelope:

```python
{"items": [...], "source": "kubernetes",  "degraded": False}
{"items": [],    "source": "unavailable", "degraded": True,
 "error_code": "KUBERNETES_UNAVAILABLE", "message": "Kubernetes unavailable: ..."}
```

`source: "unavailable"` deliberately mirrors the convention the observability
endpoints already used — this is not a second envelope.

All nine endpoints were rewritten to use it, and each gained a `cluster_id`
query parameter. `/cluster/summary` now probes reachability before trusting any
count, and returns `connected: False, degraded: True, counts: {}` when the API
server is down.

**Frontend (required by the audit).** `ClusterSection` in `components.tsx`
rendered `"No resources found"` whenever `count === 0` — the exact visual
symptom. It gained an `unavailable?: string | null` prop rendering an explicit
amber "Cluster unavailable — these resources could not be read; the cluster is
unreachable, not empty." `ClusterControlPlane.tsx` gained a `resourceRows()`
helper that accepts **both** the old bare-array shape and the new envelope, and
all 18 consumption sites (9 counts + 9 row maps) were rewired.

`/cluster/summary`'s two consumers (`KubernetesSecurity.tsx`,
`KubernetesIntegration.tsx`) were checked before the shape change: both use
optional chaining (`summary?.deployments?.length ?? '—'`), so the degraded path
renders `—` rather than crashing.

---

### BUG-011 — `restart_count` missing from pod metrics (P2)

**Root cause.** The Restart Spikes panel filters `podsData` by
`restart_count > 0`, but `/observability/metrics/pods` never included the field.
The panel always read "No restart events detected" — correct-looking, always
wrong.

**Fix.** `restart_count` added to the payload, sourced from
`pod_dict.get("restart_count", 0) or 0`. The schema default is `0`, so an
unknown count never invents restarts.

---

### BUG-012 — Usage "percentages" that were not percentages (P2)

**Root cause.** `_live_cluster_snapshot` computed:

```python
"cpu_pct":    sum(cores) / n * 100        # cores × 100
"memory_pct": sum(bytes) / n / 1024**2    # MiB
```

`get_node_metrics()` returns **cores** and **bytes**. Both values were absolute
quantities published under `*_pct` keys that the frontend renders as
percentages. With 1.0 core used of 4.0 allocatable the endpoint reported
`cpu_pct: 100.0` and `memory_pct: 4096.0`.

**Fix.** Added `KubernetesClient.get_node_capacity()` (per-node allocatable,
cores and bytes). Usage is now paired per-node with that node's own capacity,
and only when capacity is a real positive number:

```python
if cu is not None and cc and cc > 0:
    cpu_used += cu; cpu_cap += cc
```

When capacity is unknown the function returns `None` rather than guessing.

**Verified by direct execution:** 1.0 core of 4.0 allocatable → `25.0`; 4 GiB of
8 GiB → `50.0`; zero capacity → `None`; no capacity rows → `None`;
metrics-server absent → `None`.

The DB path (`KubernetesService.get_stats`) was **audited and found already
correct** — it guards `cpu_l > 0` / `mem_l > 0`, averages only over present
values, and leaves the default untouched. It was not changed; a test now pins
that behaviour.

---

### BUG-013 — Catalog `total` ignored the filters (P2)

**Root cause.** `list_services` built the page query with `status`/`type`/
`search` conditions but built the count query from `tenant_id` alone. `total`
described the unfiltered catalog while `data` described the filtered one, so
pagination reported pages that did not exist.

**Fix.** Conditions are built once into a list and applied to **both** queries
via `where(*conditions)`.

**Verified by real HTTP round-trips** against the ASGI app with a seeded tenant
(3 Running microservices, 1 Failed database, 1 Running gateway):
unfiltered → 5; `status=Running` → data 4 **and** total 4 (was 5);
`type=Database` → 1/1; `search=api-` → 3/3; combined → 3/3; `page=3&page_size=2`
→ empty, not phantom rows; no match → 0; another tenant → 0.

---

### BUG-019 — Pipeline jobs leaked an opaque 500 (P2)

**Root cause.** `GitHubAPIError` escaped `get_jobs` uncaught and surfaced as an
HTTP 500 with no integration context.

**Fix.** `PipelineService.get_jobs` now maps provider failures to the shared
contract. A 401/403 is attributed to credentials rather than reported as a
transport outage.

**Verified:** provider 500/502/503 → `IntegrationError` (502,
`INTEGRATION_ERROR`); 403 → message contains "credentials"; GitLab path → 502.

**A defect introduced and fixed during this work.** The first version imported
`GitLabAPIError` from the GitLab client. **That class does not exist** — the
GitLab client deliberately re-raises `GitHubAPIError` so the shared VCS branch
contracts stay on one exception type (documented at `gitlab/client.py:5`). The
import would have failed at call time, i.e. exactly when the error path was
taken. A test now pins the real import path.

---

## 4b. Phase 4 — frontend correctness

Frontend-only changes. The backend was not touched, so the backend suite result
stands unchanged. Verified by `vite build` (see the caveat in §8).

### BUG-014 — SVG gradients used invalid CSS colours

**Root cause.** `ObservabilityTab.tsx` derived an SVG `stop-color` from a
Tailwind class with:

```js
color.replace('text-', '#').replace('-400', '')
```

For the two actual call sites this produces `"text-blue-400"` → `"#blue"` and
`"text-purple-400"` → `"#purple"`. Neither is a valid CSS colour, so the browser
ignores the `stop-color` attribute and the gradient stop falls back to black —
the area fills rendered invisible rather than blue/purple.

The deeper issue is that Tailwind classes only resolve through *generated CSS*,
which never applies to SVG presentation attributes; they must be literal colours.

**Fix.** Reused the file's **existing** `resolveColor()` helper (already applied
to the matching `<Area stroke>` on the next line, and already carrying the
`#60a5fa` / `#c084fc` values used by the CPU/Memory bars). An initial version of
this fix added a second, parallel colour map; that duplicate was removed in
favour of the existing helper, so stroke and fill now resolve through one path
and cannot drift.

**Before → after.** `stopColor="#blue"` (invalid, rendered black) →
`stopColor="#60a5fa"`.

---

### BUG-015 — Dead hooks removed

**Root cause.** `useCatalogServices` and `useDevOpsRBAC` in `hooks.ts` had zero
importers.

**Verified before deleting,** not assumed:

- `grep` for each name across `src/` → 0 references outside the definition.
- No barrel re-export: the five importers of `./hooks` all use **named** imports
  of other hooks, so nothing re-exports this module's surface.
- `usePermissions` (line 9) was used *only* by the dead `useDevOpsRBAC`, so its
  import was removed too; leaving it would have created an unused import.
- `FALLBACK_INTERVAL_MS` is still used by two live hooks and was kept.

47 lines removed, boundaries asserted before deletion.

**Note on scope.** `useDevOpsRBAC` contained client-side RBAC gating logic.
Removing it does not affect authorization: RBAC is enforced server-side, and no
caller used this hook.

---

### BUG-016 — Wasted pod fetches

**Root cause.** `usePods()` fires two requests — `/kubernetes/pods?page_size=100`
and `/kubernetes/pods/stats` — plus a WebSocket subscription and a fallback
poller. `useApi` holds **per-component state with no shared cache**, so every
`usePods()` call site issues its own copy of both requests.

**Correction to the audit's framing.** The audit recorded "`usePods()` ×3", which
overstates the concurrency: the DevOps sections are **mutually exclusive**
(`{section === 'control-plane' && …}` / `{section === 'observability' && …}`), so
only **two** instances are mounted at once — the root plus whichever section is
active.

The concrete waste is sharper than "three fetches": **each of the three call
sites uses only one of the two responses.**

| Call site | Reads | Was also fetching, unused |
|---|---|---|
| `index.tsx` | `podStats` | the 100-pod list |
| `PlatformObservability.tsx` | `pods` | `/pods/stats` |
| `ClusterControlPlane.tsx` | `pods`, `loading`, `error`, `refetch` | `/pods/stats` |

**Fix.** Added opt-out flags to `usePods(namespace?, { includeList, includeStats })`,
both defaulting to `true` so no existing caller changes behaviour implicitly.
Each site now requests only what it renders. `useApi(null)` short-circuits
without issuing a request, so a disabled fetch is genuinely absent from the
network rather than merely ignored.

---

### BUG-017 — Stale comments (no behaviour change)

**Root cause.** Two comments in `hooks.ts` claimed `podId` is `"namespace/name"`
and that it maps to a `/:namespace/:name/logs` route.

**Verified against both ends before editing:**

- Frontend call sites pass `pod.id` — `ClusterControlPlane.tsx:114-115`
  (`podActions.restart(pod.id)` / `forceDelete(pod.id)`) and
  `components.tsx:224` (`usePodLogs(podId, true)`).
- Backend routes are `/{pod_id}/logs`, `/{pod_id}/restart`, `/{pod_id}` and
  resolve through `_get_by_id_tenant(Pod, pod_id, tenant_id)` — a primary-key
  lookup within the tenant, not a name composite.

Comments corrected to state that `podId` is the DB id (UUID). **Code paths were
not modified**, so there is no behaviour change to regress.

---

### BUG-018 — `window.confirm` replaced with the existing dialog

**Root cause.** Three destructive actions used the native `window.confirm`, which
blocks the main thread, cannot be themed, and is not consistent with the rest of
the product. `ConfirmDialog` already existed in `components.tsx` and was already
in use elsewhere.

| File | Site | Action |
|---|---|---|
| `AlertsTab.tsx` | 352 | delete alert |
| `ClusterTab.tsx` | 592 | remove cluster |
| `GitOpsTab.tsx` | 445 | remove GitOps app |

**Fix.** Each tab gained a `pendingDelete: string | null` state. The trigger now
only *stages* the deletion; the dialog's `onConfirm` performs it via a
`confirmDelete` callback. In `GitOpsTab` the `window.confirm` lived inside the
child `AppCard`, so the state was hoisted to the parent that owns the delete
handler, and the child button was reduced to `onClick={() => onDelete(app.id)}`.

No new component was introduced and no UI was redesigned — the existing
`ConfirmDialog` is reused as-is.

---

## 4c. Defects found by verifying a requirement that was still unproven

The standing requirement "keep audit logging (actor, tenant, action, resource,
result, no tokens/secrets)" had **not** actually been verified after the
remediation. Converting provider failures from "return a dict" into "raise an
exception" creates a specific hazard: if the audit write sits *after* the raise,
every failed mutation silently stops being audited — losing precisely the record
that matters most. Checking it found two real problems.

### Failed mutations were not being audited

**Root cause.** In `KubernetesService`, the `_write_audit` call sat *after* the
provider call and *after* the `raise` on failure:

```python
result = await client.delete_pod(pod.name, pod.namespace)
if not result["success"]:
    raise IntegrationError(...)          # <-- audit never reached
...
await self._write_audit(...)             # success path only
```

So `pod.delete`, `pod.restart` and `pod.exec` produced an audit row **only on
success**. Every failure was absent from the trail.

This was pre-existing for delete/restart, and for `exec` it was made worse by
the BUG-004 fix, which moved the failure into a raised exception and therefore
*away* from the audit write.

**Fix.** Each of the three now writes an audit row with `status="failed"` and a
truncated `error` before re-raising. `exec_pod` was restructured around a local
`_audit(status, error)` helper so success and all four failure branches record
through one path.

**Verified:** failed scale → 1 row, `status="failed"`, `success: False`, correct
tenant/user/resource; failed exec → 1 row; failed delete → 1 row with
`error == "forbidden"`; failed restart → 1 row; successful scale/delete →
`status="success"` with no `error` key (guarding against over-correction).

### `NotFoundError` mangled provider messages

**Root cause — a defect I introduced in Phase 1.** `raise_for_provider_failure`
called `NotFoundError(message)`. But `NotFoundError.__init__(resource,
resource_id="")` is designed for a **resource name** and formats
`f"{resource} not found"`. Passing a provider message through it produced:

```
'deployment not found'  ->  'deployment not found not found'
```

**Fix.** Added `ProviderResourceNotFoundError(NotFoundError)` in
`app/core/exceptions.py`, which keeps the 404 status and the `NOT_FOUND` code
but carries the provider's message verbatim. It **subclasses** `NotFoundError`
deliberately, so existing `except NotFoundError` handlers keep working — notably
the re-raise in `pods.cluster_summary` and `list_cluster_resource`.

**Verified after:**

| Provider error | HTTP | Code | Message |
|---|---|---|---|
| `deployment not found` | 404 | `NOT_FOUND` | `deployment not found` (verbatim) |
| `connection refused` | 503 | `INTEGRATION_UNAVAILABLE` | `Kubernetes integration unavailable: connection refused` |
| `already exists` | 409 | `CONFLICT` | `already exists` |
| `boom` | 502 | `INTEGRATION_ERROR` | `Kubernetes integration error: boom` |

And `catchable_as_NotFoundError=True` for the 404 case.

### ArgoCD reported "Live" while unreachable (BUG-007 class, found by the sweep)

**Root cause.** `GET /gitops/stats/summary` returned
`"argocd_connected": bool(creds)` — true whenever ArgoCD **credentials existed**,
regardless of whether ArgoCD was answering. `GitOpsTab.tsx:546-551` renders that
flag as a pulsing green **"ArgoCD Live"** pill, so a dead ArgoCD displayed as
live. Configuration presence is not connectivity.

This is the same defect class as BUG-007 and BUG-009, which P1 explicitly
required hunting repo-wide — it was not one of the nineteen audit findings.

**Fix.**

- Backend: added `_argocd_reachable(creds)` — a real `GET /api/version` probe
  with a 5 s timeout, returning `False` on any transport error or 5xx. The stats
  endpoint now returns **both** `argocd_connected` (probed) and
  `argocd_configured` (credentials present).
- Frontend: the pill now has three honest states — **Live** (green, pulsing),
  **Unreachable** (amber), **Not configured** (grey). `argocd_configured` is
  optional in the TS interface and falls back to `argocd_connected`, so an older
  backend response still renders rather than going blank.

**Verified:** no credentials → `False`; empty server → `False`; connection error
→ `False`; 200 response → `True`; stats with credentials but a failing probe →
`configured: True, connected: False`; stats with no credentials → both `False`.

### Unexpected provider exceptions in `exec_pod`

While testing the above, a bare `RuntimeError` from the provider layer was found
to escape `exec_pod` unwrapped — an opaque HTTP 500, exactly the failure mode
BUG-004 set out to eliminate. A final `except Exception` branch now classifies it
as `IntegrationError` (502) and audits it first.

---

## 5. Repo-wide pattern sweeps

The audit required hunting each root cause across the codebase, not just at the
reported site.

### `.to_dict()`-on-Pydantic

Every `.to_dict()` call site in `app/` was enumerated (23 sites) and each
receiver's type determined.

| Receiver | Type | Verdict |
|---|---|---|
| `AuditLog`, `Webhook`, `Asset`, `AssetRelationship`, `Repository`, `K8sScan`, `K8sFinding`, `Compliance`, `Integration` | ORM | correct — `Base.to_dict()` at `app/models/base.py:23` |
| `observability.py:142,229` | Pydantic `PodResponse` | **BUG-005** — fixed, guarded |

Verified at runtime: 82 of 88 ORM model classes carry `to_dict` (inherited from
`Base`; 7 declare their own); `PodResponse.has to_dict`
is `False`; both observability sites test `model_dump` **before** `to_dict`
(confirmed by tokenising the source and stripping comments, since the
explanatory comment mentions `to_dict` first and produced a false positive on a
naive `str.find`). Six `investigation.*` models lack `to_dict` and are never
called with it — no defect.

### Fake-data keyword sweep

Required search terms across the whole DevOps Center path — frontend
(`src/pages/DevOpsCenter/`) and the backend endpoints/services/integrations it
calls:

| Term | Frontend | Backend | Verdict |
|---|---|---|---|
| `mock`, `demo`, `sample`, `fake`, `hardcoded`, `seed`, `Math.random`, `TODO`, `FIXME` | 0 | 0* | clean |
| `placeholder` | 31 | 0 | all Tailwind `placeholder-gray-600` CSS classes and HTML `placeholder=` attributes — verified by filtering those out, leaving **0** |
| `NoOp` | 3 | 0 | all three are `rel="noopener noreferrer"` on external links — a security attribute, not fake data |

\* The two backend `fake` hits are comments asserting the *opposite* —
`catalog.py:160` "never a fake success" and `kubernetes_service.py:133` "rather
than show fake content".

**No synthetic data, no static arrays standing in for provider responses, and no
mocked infrastructure exist in the production code paths.**

### `except Exception` → empty return

Enumerated across the DevOps endpoints and services. Each candidate was
classified rather than blanket-edited:

| Sites | Classification |
|---|---|
| `gitops.py` ×5 (`_argocd_*` helpers) | **Fixed** — the ArgoCD reachability defect above came from this pattern |
| `observability.py:376,423,449` | acceptable — `None` produces `source: "unavailable"`, not fake data |
| `cluster_service.py:55,82,412` | acceptable — client-build failure → caller treats as "no client" |
| `cluster_service.py:427,440,444` | out of scope — `_parse_cpu`/`_parse_memory` string parsers returning `0.0` |
| Kubernetes client ×29 | resolved for DevOps surfaces via the `check_reachable()` seam rather than editing all 29 (BUG-009) |

### Other patterns

- `integrations[0]` — exactly one occurrence in code, in the legitimate
  `else` default branch, guarded by
  `test_default_selection_only_happens_when_no_cluster_was_requested`.
- `success=True` on failure paths — remediated for exec, scale, cluster test,
  GitOps delete, catalog, pipeline jobs.
- `window.confirm` — all three call sites replaced (BUG-018); the only remaining
  textual matches are explanatory comments.
- `verify=False` — five sites in `gitops.py`, documented and left for P3 (see §10).

---

## 6. Files changed

| File | Change |
|---|---|
| `backend/app/core/exceptions.py` | `ProviderResourceNotFoundError` — 404 that carries a verbatim provider message |
| `backend/app/integrations/base.py` | `raise_for_provider_failure`, `_classify`, marker tuples |
| `backend/requirements.txt` | declare `fakeredis` (test-only dep that was missing — see §8) |
| `backend/app/integrations/github/client.py` | BUG-001 `_request`/`_post`/`_build_headers` |
| `backend/app/integrations/kubernetes/client.py` | BUG-002/003/004/009/012; `PodListResult`, `KubernetesProviderError`, `KubernetesClientUnavailable`, `check_reachable`, `get_node_capacity`, module-scope `k8s_stream` |
| `backend/app/services/kubernetes_service.py` | fallback removal, `resolve_cluster`, `get_client_for_cluster`, `list_cluster_resource`, exec/scale error mapping |
| `backend/app/services/cluster_service.py` | BUG-007 truthful `test_connection` |
| `backend/app/services/pipeline_service.py` | BUG-019 error mapping |
| `backend/app/tasks/sync_pods.py` | BUG-003 checked listing, no deletion on unknown state |
| `backend/app/api/v1/endpoints/pods.py` | BUG-009 — 9 endpoints + `/cluster/summary`, `cluster_id` params |
| `backend/app/api/v1/endpoints/observability.py` | BUG-005 (2 sites), BUG-011, BUG-012 |
| `backend/app/api/v1/endpoints/gitops.py` | BUG-008 delete→404; ArgoCD `_argocd_reachable()` probe + `argocd_configured` |
| `backend/app/api/v1/endpoints/catalog.py` | BUG-013 |
| `artifacts/uniops/.../components.tsx` | `ClusterSection` `unavailable` prop |
| `artifacts/uniops/.../ClusterControlPlane.tsx` | `resourceRows()` — 9 sections rewired through 27 call sites, BUG-016/018 |
| `artifacts/uniops/.../ObservabilityTab.tsx` | BUG-014 — reuse `resolveColor()` for SVG `stop-color` |
| `artifacts/uniops/.../hooks.ts` | BUG-015 (−47 lines, unused import), BUG-016 opt-outs, BUG-017 comments |
| `artifacts/uniops/.../index.tsx` | BUG-016 — `includeList: false` |
| `artifacts/uniops/.../PlatformObservability.tsx` | BUG-016 — `includeStats: false` |
| `artifacts/uniops/.../AlertsTab.tsx` | BUG-018 — `ConfirmDialog` |
| `artifacts/uniops/.../ClusterTab.tsx` | BUG-018 — `ConfirmDialog` |
| `artifacts/uniops/.../GitOpsTab.tsx` | BUG-018 — `ConfirmDialog`, state hoisted from `AppCard` |

No schema changes and no migrations were required, so the migration up/down/data
requirement is not engaged.

---

## 7. Tests added

`backend/tests/devops/` — **396 tests, all passing**.

Counts are pytest-collected tests (parametrisation expanded), summing to 396.

| File | Collected | Audit class |
|---|---|---|
| `test_github_client.py` | 20 | A — integration client |
| `test_kubernetes_client.py` | 14 | A — integration client |
| `test_reconciliation_safety.py` | 7 | **D — mandatory** |
| `test_cluster_routing.py` | 13 | **E — mandatory** |
| `test_provider_contract.py` | 31 | C — unreachable provider + ArgoCD reachability/TLS |
| `test_resource_endpoints.py` | 41 | B/C — API contract |
| `test_catalog_filters.py` | 8 | B — API contract |
| `test_audit_logging.py` | 7 | audit-trail integrity |
| `test_api_contract_matrix.py` | 226 | B — authn/isolation/404 across all 71 routes |
| `test_gitops_mutations.py` | 12 | A/C — ArgoCD sync + rollback |
| `test_tenant_isolation_mutations.py` | 17 | B — cross-tenant mutations + RBAC |
| **Total** | **396** | |

**Class B (mandatory) — API contract for every visible DevOps path.** The route
table is **derived from the live ASGI app**, not hardcoded, so the sweep cannot
silently drift when an endpoint is added: a new DevOps route is picked up
automatically and must satisfy the same contract. `test_route_table_is_discovered_not_hardcoded`
asserts at least 60 routes are actually seen, so the sweep cannot pass while
silently iterating an empty list.

All **71** DevOps routes (pods, gitops, clusters, pipelines, catalog,
devops-alerts, observability) are asserted against three credential states:

| State | Expected | Result |
|---|---|---|
| no `Authorization` header | 401/403 | 71/71 pass |
| JWT signed with the **wrong** secret | 401/403 | 71/71 pass |
| malformed `Bearer not.a.jwt` | 401/403 (never 500) | 71/71 pass |

That is 213 authn assertions. A forged token carrying `roles: ["admin"]` and a
fabricated `tenant_id` is rejected everywhere — no route trusts claims from a
token signed by anything other than this server.

Plus tenant isolation and not-found contracts: a GitOps app, cluster, catalog
service and pod owned by tenant B are invisible from tenant A (404, row
intact, still visible to B); unknown ids on 7 read paths and 4 mutation paths
return 404 and never `success: true`.

**Class A/C — ArgoCD sync and rollback** (`test_gitops_mutations.py`, 12 tests).
These were the only DevOps Center mutations with no provider-failure coverage.
Each test asserts the status code **and** the resulting database state, because
"returns 502" is a weaker guarantee than "did not record a success":

| Scenario | Expected | State asserted |
|---|---|---|
| no ArgoCD integration | 503 | no history row, `last_synced_at` NULL |
| app not registered in ArgoCD | 409 | no history row |
| `_argocd_sync` returns False | 502 | no history row, `last_synced_at` NULL, no `sync_message` |
| httpx transport blow-up | 502 | no history row |
| sync succeeds | 200 | 1 history row, status `Running` (not `Succeeded`) |
| `dry_run: true` | 200 | `last_synced_at` still NULL, message tagged dry-run |
| rollback provider failure | 502 | `current_revision` unchanged, no history row |
| rollback confirmed live | 200 | `sync_status == "Synced"` |
| rollback accepted, revision unconfirmed | 200 | **not** `Synced` — `OutOfSync`/`Progressing` |
| viewer role | 403 | provider mock never awaited |
| other tenant's app | 404 | no history row |

Two of these are the important ones. A failed sync must not leave a history row
claiming the deployment happened, and a rollback whose live revision cannot be
read back must **not** report `Synced` — the endpoint marks it `Progressing`
instead, which is the same "never claim an unverified success" principle the rest
of this pass enforces.

**A false claim I made while writing these, corrected.** My first attempt patched
`_argocd_sync` itself with a raising stub, observed a raw **500**, and I recorded
it as a product defect violating the 502 contract. That was wrong. `_argocd_sync`
already wraps its call in `except Exception: return False`, so it *cannot* raise
in production — replacing the helper wholesale bypassed the very guard under test
and manufactured the 500. The endpoint was correct. The test now patches `httpx`
instead, exercising the real helper end to end, and asserts 502. **Lesson: patch
at the I/O boundary, never at the function whose error handling you are testing.**

**Class C (mandatory) — no endpoint reports a successful mutation when the
provider failed.** Covers all nine resource endpoints × {no integration,
unreachable cluster, reachable-but-empty}, plus `/cluster/summary`, exec, scale,
cluster test-connection, GitOps delete, pipeline jobs.

**Class D (mandatory) — reconciliation safety.** Failure/timeout/malformed/raw
raise → zero deletions; confirmed-empty → deletion allowed; partial listing →
only absent rows deleted; failure scoped to the failing integration.

**Class E (mandatory) — cluster routing.** A→A, B→B, invalid→`None`/404,
other-tenant→`None`/404, never a silent swap.

The API-level tests are real HTTP round-trips through the ASGI app with seeded
tenants — not re-implementations of the logic under test.

---

## 8. Test execution

| Run | Scope | Result |
|---|---|---|
| Baseline | full suite | 290 passed, 0 failed (507.54 s) |
| After P1 | full suite | **344 passed, 0 failed** (631.22 s) |
| After P2 | full suite | **377 passed, 0 failed** (729.81 s) |
| DevOps suite | `tests/devops` (396) | **396 passed, 0 failed** |
| Frontend | `vite build` | **PASS** (10.03 s, after Phase 4 + ArgoCD pill) |
| Frontend | `tsc -p tsconfig.json --noEmit` | **PASS** (exit 0, 1157 files, all 12 DevOpsCenter files) |
| After P2 | full suite incl. summary-endpoint changes | **418 passed, 0 failed** (739.70 s) |
| **After P4** | full suite, rebuilt environment | **418 passed, 0 failed** (832.86 s) |
| Final | full suite incl. audit-logging fixes | **425 passed, 0 failed** (818.66 s) |
| Final | full suite incl. ArgoCD reachability fix | **430 passed, 0 failed** (877.12 s) |
| Final | full suite incl. API contract matrix | **656 passed, 0 failed** (1195.96 s) |
| Static analysis | `mypy` 1.10.1 + `ruff` 0.5.7, project `pyproject.toml` | **0 findings on added lines** (baseline-triaged — see below) |
| Final | full suite after static-analysis fixes | **656 passed, 0 failed** (1079.47 s) |
| Final | full suite incl. ArgoCD sync/rollback tests | **668 passed, 0 failed** (1129.10 s) |
| Final | full suite incl. ArgoCD TLS guard | **669 passed, 0 failed** (1113.12 s) |
| **Final** | full suite incl. cross-tenant mutation tests | **686 passed, 0 failed** (1124.64 s) |

The progression 290 → 344 → 377 → 418 → 418 → 425 → 430 → 656 → 668 → 669 →
**686** tracks exactly +54, +33, +41, +7, +5, +226, +12, +1, +17 new tests, with
**zero failures at every stage**. 686 = 290 baseline + 396 DevOps regression
tests, confirming the new suite caused no regression anywhere in the existing
290. Phase 4 touched **frontend files only**, and the post-P4 backend re-run
reproduced 418 exactly.

### Environment rebuilt mid-verification — recorded, not hidden

After Phase 4 the sandbox environment was reset: `/tmp` was wiped, `pnpm`
disappeared from `PATH`, and `backend/.venv` was deleted (the pre-existing
`backend/venv` is a symlink into a wiped nix store and was already unusable).

Rather than fall back to asserting that the backend "cannot have changed", the
environment was rebuilt from `requirements.txt` and the suite re-run. The rebuilt
venv resolves to the **same pinned versions** as the original — fastapi 0.111.0,
sqlalchemy 2.0.30, pydantic 2.7.1, pytest 8.2.0, kubernetes 29.0.0 — so the
re-run is comparable. All **twelve** modified backend modules import cleanly on
it (verified individually: 12/12).

**Frontend build and typecheck.** With `pnpm` unavailable, the build was run as
`./node_modules/.bin/vite build --config vite.config.ts` — the same command the
`build` script invokes.

`tsc --noEmit` **is now passing**. `typescript` was absent from `node_modules`
and `npm install` fails outright in this workspace (`EUNSUPPORTEDPROTOCOL` —
`package.json` uses the pnpm `catalog:` protocol, which npm cannot parse), so
TypeScript 5.5.4 was installed into an isolated directory outside the repo and
pointed at the project's own `tsconfig.json`:

```
tsc -p tsconfig.json --noEmit   →  exit 0
```

Verified as a *real* check rather than a vacuous pass:

- `--listFiles` reports **1157 files** type-checked, including **all 12** files
  under `src/pages/DevOpsCenter/` (`GitOpsTab.tsx` included).
- A deliberate error injected into the field added this session
  (`argocd_configured: number`) was caught —
  `GitOpsTab.tsx(491,9): error TS2322: Type 'boolean' is not assignable to type
  'number'`, exit 2 — then reverted and re-verified clean at exit 0.

So the Phase 4 and ArgoCD frontend changes are confirmed to be **type-correct**,
not merely bundlable. Caveat: this used a standalone TypeScript install, not the
workspace's pinned version, and `vite build` was run directly rather than via
`pnpm`.

### A pre-existing dependency gap the rebuild exposed

The first post-P4 run returned **417 passed, 1 failed**. The failure was
`tests/test_p1_reliability.py::TestR2SharedRateLimitCounters::test_ip_rate_limit_uses_shared_redis_counter`
with `ModuleNotFoundError: No module named 'fakeredis'`.

This is **not** a regression from any change in this pass. `fakeredis` was
present in the original `.venv` but is **not declared in `requirements.txt`**, so
the rebuilt environment lacked it. Confirmed by installing `fakeredis` (2.38.0)
and re-running that single test: **1 passed in 3.34 s**. The subsequent full run
returned 418 passed, 0 failed.

**Fixed:** `fakeredis` is now declared in the Testing section of
`backend/requirements.txt`, with a comment explaining why. This is the only
non-remediation source change in this pass, and it exists so the suite is
reproducible from a clean checkout. Verified that every line in the modified
`requirements.txt` still parses.

Six failures were encountered during development, and every one was a defect in
my own new code or tests, not in the product:

1. `test_github_client` parametrised one status code across three verbs — GitHub
   answers `cancel` with 202, not 201.
2. `list_all_pods_checked` initially wrapped the swallowing helper (see BUG-003).
3. `sync_pods` read expired ORM attributes after rollback (see BUG-003).
4. A source-guard test failed because the fix's own explanatory comment contains
   the forbidden pattern — resolved by stripping `#` lines before matching.
5. A secrets test used `str(dict).replace('"keys": [...]', "")`, but Python
   renders dicts with single quotes, so nothing was stripped.
6. `GitLabAPIError` does not exist (see BUG-019).

### Static analysis (`mypy` + `ruff`) — triaged against a baseline, not blanket-fixed

`mypy` 1.10.1 and `ruff` 0.5.7 were installed into the gitignored venv and run
with the project's own `pyproject.toml`. Raw output is misleading here — mypy
follows imports and reported **279 errors across 37 files**, and ruff reported
**hundreds** across the 12 changed backend files — because the codebase does not
currently satisfy either gate. So each finding was intersected with the exact
lines this pass added (parsed from `git diff -U0 HEAD`), then compared against
the same rules run over `git show HEAD:<file>` copies.

**Two genuine defects were found and fixed:**

1. **`sync_pods.py` — my change silently broke pre-existing lines.** Adding
   `"errors": []` to the `summary` dict widened mypy's inferred value type from
   `int` to `object`, which invalidated `+=` and `.append` on *lines I never
   touched*. The file went from 4 mypy errors at HEAD to 11. Fixed by annotating
   `summary: dict[str, Any]` (and importing `Any`) — back to **4, matching
   baseline**.
2. **`sync_pods.py` — `Any` used without being imported.** The module imports
   fine only because `from __future__ import annotations` makes annotations lazy
   strings; any runtime introspection (`typing.get_type_hints`) would have raised
   `NameError`. Verified resolving now.

**Nine findings on added lines were resolved to zero.** `_argocd_reachable`
accepted `dict` but is called with `dict | None` — its own body already guards
`if not creds`, so the signature was widened to match actual behaviour rather
than papering over the call site. Four `no-untyped-def` findings on functions
this pass added (`_match_integration`, `_client_from_integration`,
`list_cluster_resource`, `get_client_for_cluster`) were annotated properly, using
a `TYPE_CHECKING` import for `KubernetesClient` so no runtime import changed.
`_list_tenant_k8s_integrations` was retyped `list` → `list[Integration]`, which
also removed a real narrowing gap where `_match_integration`'s
`Integration | None` leaked into `_client_from_integration`.

**Deliberately NOT fixed, with reasons:**

| Rule | Added-line count | Baseline (HEAD) | Why left |
|---|---|---|---|
| `E402` | 10 | 76 | Root cause is pre-existing: in several modules the docstring sits *after* `from __future__ import annotations`, so it is a no-op expression (`module.__doc__` is `None` — verified) and every later import reads as "not at top". Fixing means restructuring files, which is out of scope. |
| `UP007` | 10 | 51 | `Optional[X]` vs `X | None`. `pods.py` already had 13 `Optional[` at HEAD; my signatures match the file's existing convention. Converting only mine would make the file *less* consistent. |
| `I001` | 3 | 24 | ruff's fix rewrites pre-existing import lines (verified: it reorders `from typing import Optional, Any` at line 3, which I did not author). |
| `UP017` | 1 | 19 | `timezone.utc` vs `datetime.UTC`; matches the file's existing 19 occurrences. |
| `F401` | 1 | 12 | `ValidationError` in `cluster_service.py` — **proven pre-existing**: it is present at HEAD line 24, alongside unused `io` and `yaml`. Not introduced here, and removing it is unrelated cleanup. |

An earlier `ruff --fix` run was **reverted** after inspection: although invoked
with `--select I001,UP037,E702`, it reordered pre-existing module-level imports
in all four files (`import tempfile, os` → two lines, `sqlalchemy` groups
reshuffled). That is exactly the broad refactor this pass is not permitted to
make. The two findings that were genuinely mine (`E702` semicolons in the
BUG-012 block, `UP037` quoted annotation on `list_all_pods_checked`) were applied
by hand and diffed line-by-line.

**Net result: 0 mypy findings and 0 ruff findings on added lines that are not
either pre-existing in kind or consistent with the surrounding file's
established style.** Full suite re-run after all of it: **656 passed, 0 failed**
(1079.47 s).

---

## 9. Verification status

**Status: CODE-VERIFIED.** This is deliberately **not** PRODUCTION VERIFIED.

Source-code inspection is not live verification, and no claim below exceeds the
evidence actually gathered.

### Proven locally (real code executed)

- All 396 DevOps regression tests and the full backend suite (686 passed).
- BUG-012 arithmetic executed directly against the changed function: 25.0 / 50.0
  / `None` on zero capacity.
- BUG-013 via real HTTP round-trips through the ASGI app with seeded tenants.
- BUG-009 via real HTTP round-trips across all nine endpoints.
- BUG-019 via the real `PipelineService.get_jobs` code path.
- BUG-003/004/006 via the real client and service code paths with the provider
  layer mocked — mocks exist **only** in tests.
- **Tenant isolation and server-side RBAC, now in the committed suite.** This was
  originally proven by `scripts/audit_isolation.py`, but that script needs a live
  server plus untracked fixtures (`audit.db`, `.audit_ids.json`), so the evidence
  was unreproducible — the report could cite it and nobody could re-run it. The
  same guarantees are now pytest tests (`test_tenant_isolation_mutations.py`, 17
  tests) that run in CI without a server.

  Every destructive case re-reads the database afterwards, because "returns 404"
  is weaker than "did not destroy anything" — a 404 that quietly deleted the
  victim's row would pass the status assertion and fail the survival one:

  | Attacked as tenant A's admin, owned by tenant B | Result |
  |---|---|
  | pod `POST /restart`, `DELETE`, `POST /exec` | 404, row intact, `restart_count` unchanged |
  | cluster `GET`, `POST /test`, `PATCH`, `DELETE` | 404, row alive, `name` not mutated |
  | pipeline `GET`, `POST /cancel`, `POST /rerun` | 404, row intact, `status` unchanged |

  A control test proves the 404 comes from the *tenant filter* rather than the
  endpoint always 404ing. RBAC: `viewer` → 403 on cluster create, GitOps create,
  alert create, pod restart and pod delete (row intact); `devops_engineer` → not
  403, proving the denials are real rather than a blanket rejection.

### Requires live infrastructure — NOT verified here

| Capability | Blocker |
|---|---|
| Real `kubectl scale`/`delete`/`restart`/`exec` round-trips | no Kubernetes cluster |
| Real GitHub `rerun`/`cancel` state transitions | no GitHub credentials |
| Real ArgoCD sync/rollback | no ArgoCD, no TLS CA bundle |
| Real Prometheus time-series | no Prometheus |
| Redis-backed WebSocket fan-out and rate limiting | no Redis; `apt-get install redis-server` unavailable |
| PostgreSQL behaviour (JSONB, migrations) | tests run on SQLite |

**BUG-001 is the most important caveat.** The mutations were dead because no
headers were ever built; the fix makes them issue real HTTP calls, verified
against a mocked transport returning the correct per-verb status codes. That a
real GitHub account accepts these calls has **not** been demonstrated. Until a
live round-trip is performed, BUG-001 should be read as CODE-VERIFIED.

### Not fabricated

No external infrastructure was faked, in tests or otherwise. Where a provider is
unreachable the code degrades honestly and says so. Production paths contain no
mock data, no synthetic series, no `Math.random`, no static arrays standing in
for provider responses.

---

## 10. Remaining findings

Only P3 remains. P4 is complete (see §4b).

| ID | Finding | Phase |
|---|---|---|
| BUG-010 | `selectedClusterId` (`index.tsx:88,214,215,235`) is never sent to the API, so the cluster selector does not route requests. The nine endpoints now *accept* `cluster_id`; the frontend does not yet send it. `KubernetesSecurity.tsx:886` also sends `?cluster=` where the endpoint expects `?cluster_id=`. | P3 |
| — | WebSocket fan-out is single-instance only; no Redis pub/sub, no tenant isolation across instances | P3 |
| — | Rate limiting runs **before** authentication, so identity is unauthenticated at throttle time; not Redis-backed when Redis is configured | P3 |
| — | ArgoCD TLS verification disabled — see note below | P3 |

Fixed in this pass (P4): BUG-014, BUG-015, BUG-016, BUG-017, BUG-018 — see §4b.

Also documented, unfixed: `DevOpsUser` is declared twice in `deps.py`.

### ArgoCD TLS — corrected finding

The audit described this as "ArgoCD client uses `verify=False` on all
`_argocd_*` calls". Verified against the source, that is **not accurate**, and
the real picture is narrower but sharper:

- `app/integrations/gitops/argocd_client.py` (L42, L60) and
  `app/core/deployment_engine/argocd.py` (L31, L40) both use
  `verify=not self.insecure`, with `insecure` defaulting to `False` and read
  from `cfg.get("insecure", False)`. **These are already correct and
  configurable — verification is ON by default.**
- The defect is confined to `app/api/v1/endpoints/gitops.py`, which hardcodes
  `httpx.AsyncClient(verify=False, ...)` at **five** sites, one per helper
  (line → function, both verified):

  | Line | Function |
  |---|---|
  | 133 | `_argocd_list_apps` |
  | 147 | `_argocd_sync` |
  | 174 | `_argocd_rollback` |
  | 189 | `_argocd_get_history` |
  | 205 | `_argocd_get_revision` |

- Sharper still: `_get_argocd_creds` in that same module already resolves an
  `insecure` flag — `creds.get("insecure") or cfg.get("insecure") or False` —
  and puts it in the dict it hands to those helpers. **The helpers ignore it and
  hardcode `verify=False` anyway.** So the configuration plumbing already
  exists; the fix is to honour it (`verify=not creds["insecure"]`) rather than
  to build anything new.

There is no `app/integrations/argocd/` directory; the audit's path reference was
wrong. This remains a P3 item and was not changed in this pass.

### A regression I introduced here, and caught

When `_argocd_reachable` was added for the connectivity-honesty fix, it was
written copying the surrounding style — `httpx.AsyncClient(verify=False, ...)`.
That would have taken the module from **five** hardcoded TLS bypasses to **six**:
a fix for a UI-honesty bug would have quietly made the security posture worse.

Caught by counting actual call sites before and after (tokenising the source to
strip comments, since the explanatory comment itself contains the string
`verify=False` and inflates a naive `grep`):

| | `verify=False` call sites |
|---|---|
| `git HEAD` baseline | 5 |
| after the naive version of this fix | 6 |
| after correction | **5** |

Corrected to `verify=not creds.get("insecure", False)`. `_get_argocd_creds`
already resolves an `insecure` flag from the integration's credentials or config,
so **the new probe verifies TLS by default** and only skips it on an explicit
tenant opt-out — strictly better than the five pre-existing helpers beside it.
Locked in by `test_reachability_probe_verifies_tls_by_default`, which asserts
`verify is True` with no flag and `verify is False` with `insecure: True`.

The five pre-existing bypasses are unchanged and remain the P3 item above.

---

## 11. Residual risks

1. **BUG-001 unproven against a real GitHub account.** Highest-risk residual. The
   code path is correct and tested against the documented status codes, but no
   live mutation has been observed.
2. **Two credential stores remain.** `Integration(type="kubernetes")` and
   `Cluster.kubeconfig_encrypted` are parallel sources of truth.
   `get_client_for_cluster` consults the cluster row first, then name-matched
   integrations. This is correct today but is a standing source of confusion.
3. **`check_reachable()` adds one API call per resource listing.** Acceptable for
   nine endpoints on a tab-scoped view; it is a real cost and would matter on a
   hot path.
4. **18 `except Exception` → empty-return sites remain in the Kubernetes client**
   (measured as an `except Exception` whose next three lines return `[]`/`{}`/`None`).
   The DevOps Center surfaces are covered by the reachability seam; other
   callers of those helpers are not.
5. **SQLite vs PostgreSQL.** Tests run on file-backed SQLite. JSONB semantics,
   transaction isolation and migration behaviour are untested here.
6. **Static analysis ran against 3.11, not the project's 3.12 target.**
   `mypy` 1.10.1 and `ruff` 0.5.7 were installed into the (gitignored) venv and
   run against the project's own `pyproject.toml`. Both produced findings, and
   every finding landing on a line I added was triaged against a `git HEAD`
   baseline rather than accepted or blanket-fixed — see §8. The residual caveat
   is the interpreter: `python_version = "3.12"` with a 3.11.2 runtime, so
   3.12-only diagnostics cannot surface here.
7. **Typecheck ran against a standalone TypeScript, not the workspace pin.**
   `tsc --noEmit` now passes (exit 0, 1157 files, all 12 DevOpsCenter files,
   proven non-vacuous by a deliberate-error check — see §8). But the workspace's
   own `pnpm typecheck` still cannot run here: `pnpm` is unavailable and `npm`
   cannot parse the `catalog:` protocol in `package.json`. The compiler version
   used (5.5.4) may differ from the pinned one, and it did not resolve through
   the workspace's dependency graph. Re-run `pnpm typecheck` in CI to confirm.
8. **Environment reproducibility.** The verification venv was rebuilt from
   `requirements.txt` after the sandbox reset. It reproduces the pinned versions,
   but it is not the original interpreter, and no lockfile hash was compared.

---

## 12. Readiness

**CONDITIONALLY READY.**

The DevOps Center no longer reports success when a provider failed, no longer
routes an operation to a cluster the caller did not name, and no longer deletes
data because a provider was unreachable. Those were the conditions under which
the system could actively mislead an operator or destroy data, and all three are
fixed with regression coverage that locks them in.

Conditions before this can be called production-ready:

1. Live round-trip of the GitHub mutations (BUG-001) against a real account.
2. Live Kubernetes round-trips for scale/delete/restart/exec against a real
   cluster, including a deliberate outage to confirm the degraded path renders.
3. ArgoCD TLS verification (`verify=False` → `verify=True` / configurable CA).
4. Redis-backed WebSocket fan-out and rate limiting for multi-instance
   deployment.
5. BUG-010 — wire `selectedClusterId` through to the API, or the cluster
   selector remains decorative.
6. `mypy`/`ruff` on a true 3.12 toolchain. Both were run here (3.11.2 runtime,
   project `pyproject.toml` config) and every finding on a line I added was
   triaged against a `git HEAD` baseline — **0 mypy findings remain on added
   lines** — but 3.12-only diagnostics cannot surface on this interpreter.
7. **`pnpm typecheck` on the frontend.** Now verified locally via a standalone
   TypeScript 5.5.4 against the project's `tsconfig.json` — exit 0 across 1157
   files including all 12 DevOpsCenter files (see §8). Re-run through the
   workspace's own pinned toolchain in CI.
8. Full-suite run on PostgreSQL rather than SQLite.
9. P3 completion: BUG-010 cluster routing, WebSocket Redis pub/sub, rate-limit
   placement/identity, and ArgoCD TLS.
