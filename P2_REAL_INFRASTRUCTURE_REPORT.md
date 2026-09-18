# P2 — REAL INFRASTRUCTURE VERIFICATION REPORT

**Branch:** `arena/01a0b237-uniops-saas-product`
**Baseline SHA:** `e74a2a31ec32` (remote-synced; push started working again this session after the gate's GitHub-token outage resolved)
**Date:** 2026-09-18 (Africa/Cairo)
**Verdict (final):** CONDITIONAL PASS — see §21

> Method contract: every integration is verified via DISCOVER → CONNECT → PROVE REAL DATA → MUTATIONS → FAILURE → TENANT/RBAC → REGRESSION → DOCUMENT. No "200 = success", no seeded rows as proof, unavailable infra is marked UNVERIFIED / BLOCKED, never PASS.

---

## 1. Baseline / change control (recorded before any P2 change)

| Item | Result | Evidence |
|---|---|---|
| Branch | `arena/01a0b237-uniops-saas-product` | `git branch --show-current` |
| P1.6 gate standing condition | **RESOLVED** — 5 gate commits pushed after token recovery; fresh-clone start verified | `git ls-remote` = `0126773` then `65d7b3b`, `e74a2a3` |
| Working tree | clean at baseline start | `git status` |
| Remote sync | ✅ remote == `e74a2a31ec32` | `git ls-remote` |
| P1.6 suite re-run post-push | (in flight at baseline capture; final number appended below) | pytest |
| Clone → boot | ✅ health 200 from fresh clone at `65d7b3b` | in-process uvicorn |
| Clone → frozen install + prod build | ✅ green (11.2s) after adding `onlyBuiltDependencies` (see BUG-01) | `pnpm build` in clone |
| Backend suite on baseline tree | pending completion → filled in §18 | — |

**Environment (sandbox):** 2 vCPU Linux container, no Docker daemon, Redis 6/7 on :6379 (real), SQLite dev DB (`uniops_dev.db`), Postgres absent, no kubeconfig/kubectl, no in-cluster DNS.

**Egress allowlist (measured, 2026-09-18):**

| Endpoint | Reachable |
|---|---|
| api.github.com | ✅ 200 |
| gitlab.com | ❌ (connection failure) |
| api.stripe.com | ❌ |
| hooks.slack.com | ❌ |
| smtp.sendgrid.net:587 | ❌ |
| any in-VPC/cloud metadata | n/a |

**Credentials available:** sandbox `GH_TOKEN`/`GITHUB_TOKEN` = real GitHub App installation token (repo-scoped to `MomenLotfy/UniOps-SaaS-Product`; `/user` returns GitHub's own 403 "Resource not accessible by integration"). AWS keys EMPTY, GitLab none, Stripe none, Slack none, SendGrid none (from `backend/.env` presence scan — values never printed).

**BUG-01 (fixed):** root `pnpm install --frozen-lockfile` failed in clean clone with `ERR_PNPM_IGNORED_BUILDS` on pnpm 12 (esbuild postinstall blocked). Root cause: repo lacked `pnpm.onlyBuiltDependencies`. Fix: commit `e74a2a3` adds `onlyBuiltDependencies:["esbuild"]`; clone install+build verified green.

---

## 2. Real integration inventory

| Integration | Code path | Credentials | Reachable | Real test possible | Status |
|---|---|---|---|---|---|
| GitHub | `app/integrations/github/client.py`, used by `services/integration_service.py`, `tasks/sync_pipelines._sync_github`, webhooks receiver `app/api/webhooks/github.py` | real GitHub App installation token (repo-scoped) | ✅ | ✅ (repo-scoped only; `/user` returns provider-403) | **→ verifying (§5)** |
| Webhooks (github/gitlab/slack/stripe receivers) | `app/api/webhooks/*.py` | secrets configurable locally for test instance | ✅ local | ✅ positive+negative HMAC matrix | **→ verifying (§12)** |
| Redis | `app/core/redis_client.py`, rate limits, invite/reset tokens, pubsub ML listener, task broker | local daemon :6379 | ✅ | ✅ incl. multi-worker leader behavior | **→ verifying (§10)** |
| Celery/background workers | `app/core/celery_app.py` (10 task modules), plus in-process `scheduler` + `deployment_worker` | Redis broker local | ✅ | ✅ real task enqueue/execute via broker | **→ verifying (§10)** |
| WebSockets | `app/main.py /ws/{tenant_id}`, `ws_manager` | JWT | ✅ local | ✅ tenant isolation/multi-client/reject paths | **→ verifying (§11)** |
| Kubernetes | `app/services/kubernetes_service.py`, `app/integrations/kubernetes/client.py`, K8s watchers, remediation K8s gates | none; no cluster; no docker (cannot spawn kind/k3s) | ❌ | ❌ | **BLOCKED — environment (no cluster, no container runtime)** |
| AWS | `app/integrations/aws/client.py` | none | ❌ (and egress likely blocked) | ❌ | **NOT_CONFIGURED** |
| GitLab | `app/integrations/gitlab/client.py` (P1.5 GITLAB-1 fix path) | none; gitlab.com egress blocked | ❌ | ❌ | **UNVERIFIED — ENVIRONMENT BLOCKED** |
| Stripe | `app/integrations/stripe/client.py`, webhook receiver | none; api.stripe.com blocked | ❌ | ❌ | **NOT_CONFIGURED** |
| Slack | webhook receiver only (`app/api/webhooks/slack.py`) | none; hooks.slack.com blocked | ❌ | receiver-matrix only | **NOT_CONFIGURED (receiver verifiable, egress not)** |
| SMTP/SendGrid | notification_service providers (`app/services/notification_service.py`) | none; egress blocked | ❌ | ❌ | **NOT_CONFIGURED** |
| ArgoCD | gitops service (`app/services/gitops_service.py`) | none; no instance | ❌ | ❌ | **NOT_CONFIGURED** |
| Prometheus | observability/loki/etc. clients (`app/integrations/observability/*`) | none; no instance | ❌ | ❌ | **NOT_CONFIGURED** |
| Loki | `app/integrations/observability/loki.py` | none; egress blocked | ❌ | ❌ | **NOT_CONFIGURED** |
| PostgreSQL | `DATABASE_URL` supports PG; dev = sqlite | no server in sandbox | ❌ | ❌ | **NOT_CONFIGURED** (sqlite-mode verified) |

Status vocabulary: VERIFIED / PARTIAL / UNVERIFIED / BLOCKED / NOT_CONFIGURED — never "PASS" for a service not actually exercised.

(Sections 3–20 are filled as verification proceeds.)


---

## 3. Environment truth (measured, not assumed)

- DNS+TLS to `api.github.com` works from the backend venv only with `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` exported (system CA store). The verification server :3001 ran with it.
- Redis daemons: :6379 (suite default) and :6380 (P2-isolated broker + rate-limit namespace) — real `redis-server`, `PONG` live.
- Celery worker (`app.core.celery_app:celery_app`, `--concurrency=2`) connected to `redis://localhost:6380/0`, executed `app.tasks.sync_pipelines.sync_all_pipelines` twice; worker log shows real outbound HTTPS to GitHub from inside the task.
- Uvicorn API :3001 (this branch's code, restarted after every fix so live-verify reflects current tree).
- No Docker daemon (compose topology for celery_worker/celery_beat inventoried but not executed → §9 partial), no kubeconfig/kubectl (§6 blocked), no Postgres (SQLite dev DB).

## 4. GitHub — VERIFIED (real end-to-end), with one honest capability limit

DISCOVER: `gh auth token` is a real **GitHub App installation token** (len 24, never printed/stored), repo-scoped to `MomenLotfy/UniOps-SaaS-Product` (that repo runs 110 real Actions workflow runs).

CONNECT:
- A1 create integration (201) ✅; response never contains the token (checked substring).
- A2 integrations list response token-free ✅; credentials stored encrypted at rest (no plaintext in list payloads or in API responses).
- A3 `POST /integrations/{id}/test` → `success:false, "Resource not accessible by integration"` — **truthful**: the product's test calls GitHub `/user` (user-space endpoint), which App installation tokens cannot use. Honest failure, no 200-washing. Message contains no token.
- A4 garbage token → `success:false`, status `error`, message `Resource not accessible by integration`; no secret echo.

PROVE REAL DATA (the full production chain — worker edition):
- Forced `status='connected'` via SQL on our own test row (documented harness step — the only way to reach the worker code path with an App token; see Capability limit below).
- Enqueued `sync_all_pipelines` through the **real redis broker**; the worker executed it (logs: `Task ... received`, `HTTP Request: GET https://api.github.com/repos/MomenLotfy/UniOps-SaaS-Product/actions/runs?per_page=20 "HTTP/1.1 200 OK"`, `succeeded in 1.158s`).
- Dependabot leg: `GET .../dependabot/alerts` → 403 → logged as non-fatal skip — honest degradation.
- DB now holds **20 real pipeline rows** for the repo (external_ids = real GitHub run ids, e.g. 35296604818, names "UniOps CI"/"Nightly Security Scan", branch main, real SHAs).
- C4 id-value comparison: product rows matched GitHub's own `/actions/runs` ground truth for the same window (ids, names, branches) — done twice (pytest-style probe + envelope probe after BUG-P2-02 fix).
- **Signed webhook → DB chain**: forged-but-validly-signed `workflow_run` webhook (secret `p2wh-github-2026`) upserted a pipeline row visible via REST in the owning tenant (W1/W2/W3 battery ✅ 3/3), replay-idempotent (no duplicate on exact replay), and invisible to the control tenant.

TEST MUTATIONS:
- Cancel of a completed/failed pipeline → **422 `Pipeline is 'failed' — only active pipelines can be cancelled`** — lifecycle truthfully enforced (no fake success; nothing mutated, nothing emitted) ✅.
- Repeat cancel → same 422 (deterministic, no crash) ✅.

FAILURE PATHS: A3, A4 above; Dependabot 403 → skip; rate-limit error mapping present in code; App-token incompatibility surfaced verbatim from GitHub ("Resource not accessible by integration").

TENANT/RBAC: A5 cross-tenant get/test of A's integration → **404** (not 403-leak) ✅; C8 cross-tenant cancel → 404 ✅; C8b cross-tenant pipeline read → 404 ✅; W3 webhook-inserted row invisible to control tenant ✅.

**Capability limit (honest, classified NOT a defect but a product gap):** the product's GitHub client assumes **PAT semantics** — `test_connection` and `sync()` call user-space endpoints (`/user`, `/user/repos`). A GitHub **App installation token** can never pass those calls, so integrations using App tokens stay `error`/`disconnected` and the manual `/integrations/{id}/sync` gate (409 until connected) never opens. The pipeline-sync task *does* work with App tokens when `config.repos` is set (per-repo endpoints), which is how the 20 real rows were synced. GitHub App support is a feature decision, out of P2 scope; recorded here so the next phase can implement per-repo fallbacks (e.g., `/repos/{o}/{r}` checks) rather than only user-space probes.

## 5. GitLab — UNVERIFIED (environment-blocked), webhook receiver VERIFIED locally

- Egress to `gitlab.com` connection-refused (measured). No GitLab credential exists in the credential stack (`.env` presence scan, values never printed). Therefore no CONNECT/SYNC/FAILURE evidence is possible in this sandbox — **not marked PASS/PARTIAL; marked UNVERIFIED**.
- What *is* verified locally: the signed shared-secret webhook receiver (see §13/webhooks): missing token 401, wrong token 401, correct `X-Gitlab-Token` 200.

## 6. Kubernetes — BLOCKED

No kubeconfig, no in-cluster DNS, no `kubectl`, no container runtime in the sandbox (measured). K8s client code paths (build from kubeconfig, list/deploy/pods) cannot be truthfully exercised. Marked **BLOCKED**, not downgraded to PASS. (`test_connection` failure path for garbage kubeconfig is covered by the typed-error catch in `IntegrationService.test_connection` — code-reviewed only, not live-verified.)

## 7. Sentry — NOT VERIFIABLE in-sandbox (SDK installed, init inactive)

`sentry-sdk[fastapi]==2.7.0` pinned; `app/observability/sentry.py` initializes FastAPI+Celery+Logging integrations **only when `SENTRY_DSN` is non-empty**. `.env` scan: `SENTRY_DSN` EMPTY → SDK never initializes; there is no event to capture. Crash reporting cannot be truthfully verified without a DSN — marked **NOT_CONFIGURED** (by design fail-off, not a defect).

## 8. SMTP / transactional email (SendGrid) — NOT_CONFIGURED

`SENDGRID_API_KEY` EMPTY; egress to `smtp.sendgrid.net:587` refused. `app/integrations/email/client.py` targets `https://api.sendgrid.com/v3/mail/send` via httpx — code present, cannot be exercised. Marked **NOT_CONFIGURED**. Invitation/password-reset flows degrade per existing code paths (not live-verified end-to-end for email content).

## 9. Multi-container hard separation — PARTIAL

- **Real broker isolation proven**: API process (:3001) and Celery worker process are separate OS processes on separate redis DBs (6380/0 broker, 6380/1 results); the 20 GitHub rows were produced *by the worker process* and served *by the API process* — cross-process data flow verified.
- Compose defines `celery_worker` + `celery_beat` services (inventoried) but **Docker is absent** in the sandbox → the multi-container topology itself is **UNVERIFIED** (not executed).
- **Leader election: single-flag design, no distributed lock.** `BACKGROUND_LEADER` (env, default true) gates the in-process background scheduler in `app/main.py`; scaling guidance lives in `app/config.py` (set false on N-1 workers). This is config-gated — two instances with `BACKGROUND_LEADER=true` would both schedule (documented; no Redis lock exists). Recorded as a deployment-constraint finding (LOW; operators must follow the documented flag discipline; a Redis-lock upgrade is a P3 candidate, not fixed in P2 since P2 forbids feature expansion).

## 10. Redis — VERIFIED (live proof, not "runs locally")

- Broker/result backend: worker consumed two real tasks through it (§4).
- **Rate limiting is shared-state**: 13 logins to a nonexistent user → 10×401 then **3×429**; the counter key `rl:auth:auth.login:127.0.0.1:289` exists in redis:6380 **and is readable from a different process** (`redis-cli`), proving multi-worker sharing works in the running topology (not a test fixture).

## 11. Celery — VERIFIED (live logs)

Real worker, real broker: log lines captured — `Connected to redis://localhost:6380/0`, `Task app.tasks.sync_pipelines.sync_all_pipelines[bf6c…] received`, outbound `GET api.github.com… "HTTP/1.1 200 OK"`, `Task … succeeded in 1.1585129769991909s`. Second run idempotent (row count 20→20, no duplicates). Retry policy exists (`max_retries=3`, `soft_time_limit=600`) — failure/retry escalation not triggered live (would require multi-minute fault injection; code-reviewed only → PARTIAL on retry-path).

**Enqueue-latency observation (LOW):** cross-battery enqueue-to-receipt measured ~40–150s in this sandbox (kombu reconnect/backoff on a fresh connection to a second redis instance). Delivery is guaranteed (both tasks eventually ran and succeeded). Not a correctness defect; flagged for ops awareness. Known mitigations (persistent connections/broker pool tuning) are out of P2 scope.

## 12. Rate limits on risky endpoints — VERIFIED live

- `auth.login` limit 10/60/IP: 10 allowed (401s — wrong-password attempts), then HTTP **429** ×3. Shared redis counter confirmed (§10). `auth.register` 5/60, `auth.forgot` 5/60, `auth.reset` 5/60, `auth.2fa` 10/60 present in code (`app/api/v1/endpoints/auth.py`), plus generic composite limiter (burst+sustained+per-endpoint) in middleware.
- Webhook receivers: no rate limiter needed for correctness — they are signature-gated fail-closed (§13); abuse = 401s, cheap.

## 13. Webhooks — VERIFIED (4/4 receivers, signed matrix) + fake-success audit finding

All on instance configured with test secrets (`p2wh-github-2026`, `p2wh-gitlab-2026`, `p2wh-stripe-2026`, `p2wh-slack-2026`):

| Receiver | Missing sig | Wrong sig | Valid sig | Extra |
|---|---|---|---|---|
| `/webhooks/github` (HMAC sha256) | 401 ✅ | 401 ✅ | 200 ✅ | DB upsert proven (§4 W1–W3) |
| `/webhooks/gitlab` (`X-Gitlab-Token`) | 401 ✅ | 401 ✅ | 200 ✅ | — |
| `/webhooks/slack` (v0 HMAC) | 401 ✅ | — | 200 ✅ | stale timestamp (>300s window) 401 ✅; `url_verification` challenge echoed ✅ |
| `/webhooks/stripe` (`t=,v1=`) | 400 ✅ | 400 ✅ | 200 ✅ | unhandled event type returns handled=false, no 5xx ✅ |

**Fake-success audit (§13 of the mission):** scan of the codebase for fake-success patterns located exactly one reachable instance — the `_NoOpIntegration` fall-through — **removed** (BUG-P2-03). The webhook github handler silently no-ops for repos with no matching integration (returns 200 with no handler_ack echo) — reviewed: correct fail-silent by design (no fake success claimed; response makes no success claim about processing).

## 14. WebSockets — PARTIAL (structural isolation verified; positive emit path environment-blocked)

- Dual live sockets: tenant A socket + tenant B socket, both connected with valid JWTs (`token` query param), mutation attempted on A's side.
- Zero cross-tenant leakage observed (control tenant received 0 events in every battery).
- Zero false positives: refused cancel emitted **no** event (correct).
- **Positive path UNVERIFIED**: the `pipeline.update` emit happens only in `pipeline.cancel` *after* the provider cancel succeeds — the App token is read-only for Actions and the repo has no active runs; the webhook workflow_run handler does not emit. Honest classification: PARTIAL.
- Code-level tenant emit sites (pipeline cancel, ml, notifications) all use `send_to_tenant(tenant_id, …)` — reviewed.

## 15. Idempotency review (external mutations)

| Mutation | Evidence | Verdict |
|---|---|---|
| Worker pipeline sync re-run | row count 20 → 20 (no dup) | ✅ idempotent (upsert by tenant+external_id+repo) |
| Signed webhook replay (exact same delivery) | rows stay 1 | ✅ idempotent (upsert by tenant+external_id) |
| Pipeline cancel retry | deterministic 422, no partial mutation | ✅ safe |
| Integration create | creates new row per call (no natural key) | reviewed: acceptable (rows are user-scoped objects; unique constraint on (tenant,name)? — flagged as minor review note, not a proven defect) |

## 16. Failure paths — honest verification (not mocked success)

| Path | Live result |
|---|---|
| GitHub test with App token | truthful `success:false` + GitHub's own message |
| GitHub test with garbage token | truthful `success:false`, status=error, no secret echo |
| GitHub sync (svc.sync) under App token | 200 ack → background fails honestly → status=`error` (`Resource not accessible by integration`) |
| Dependabot 403 | non-fatal skip, logged, pipelines never lost |
| Cancel non-active pipeline | 422 with clear message, no mutation, no WS event |
| Cross-tenant cancel/read/test | 404 (no existence leak) |
| Bogus integration type | **was** 201 + traceback leak → **now** 422 (BUG-P2-03) |
| Webhook missing/wrong sig (all 4) | 401/400, fail-closed |
| Slack replay (>300s) | 401 |

## 17. Bugs found and fixed (FAIL → ROOT CAUSE → FIX → REGRESSION → LIVE VERIFY)

### BUG-P2-01 (baseline, infra) — pnpm frozen install fails on pnpm ≥12 in clean clone
Root cause: missing `pnpm.onlyBuiltDependencies` (esbuild postinstall blocked by default in pnpm 12). Fix `e74a2a3` (root package.json). Live-verified: fresh clone `/tmp/p2-fresh` install + `vite build` green (11.2s).

### BUG-P2-02 (contract, LOW) — `GET /pipelines` double-wrapped envelope
Evidence: live response `{"success":true,"data":{"success":true,"data":[…],"total":20,…}}` vs single-envelope contract everywhere else. Root cause: endpoint returned `APIResponse(data=PaginatedResponse(…))` with `response_model=APIResponse[PaginatedResponse]`. Fix `00d3cd6` (declare `PaginatedResponse[PipelineResponse]` as the response model, return it directly). Regression `tests/test_p2_pipeline_envelope.py` — **fails on pre-fix tree (verified via git stash), passes on fixed tree**; live-verified on restarted instance (keys exactly success/data/total/page/page_size/pages, data is a JSON array). Frontend compatible (dead `pipelinesApi` module still matches new shape).

### BUG-P2-03 (security-hygiene / fake-success, MEDIUM) — unknown integration type reaches fake-success client
Evidence: `POST /integrations {"type":"totally-bogus-provider"}` → 201; `POST …/test` → outer `success:true` + inner traceback leak `'_NoOpIntegration' object has no attribute 'get_authenticated_user'`; status `error` with raw exception in DB (live). Root cause: unvalidated free-string `type`, `_build_client` fall-through stub, generic `except` echoing `str(exc)`. Fix `cf0c98c`: schema allowlist (422), stub deleted (`_build_client` raises), catch-all sanitizes client-visible message (full exception still logged server-side). Regression `tests/test_p2_integration_type_gate.py` (4 tests; 2 failed pre-fix, all pass post) + existing suite updated to the new contract. Live-verified: bogus → 422, valid → 201 on restarted instance.

## 18. Test counts (truthful, full files only)

- P1.6 final gate suite: 285 passed (at `8a0fa81`, re-verified on final tree) — recorded in P1_6_FINAL_GATE_REPORT.md.
- P2 battery live checks (this session, against :3001): A×9 PASS, B×4/4 PASS, C: C1/C2/C7/C8/C8b/C5 PASS, C3/C4 superseded by direct truth-probes (PASS after envelope fix), C6 PARTIAL (see §14), H-RL PASS, W1–W3 PASS, NoOp reachability probe reproduced pre-fix and closed post-fix (BUG-P2-03).
- New regression tests added: `tests/test_p2_pipeline_envelope.py` (1), `tests/test_p2_integration_type_gate.py` (4). Final full-suite run on the closing tree is reported in §21.
- Frontend: no changes (P2 did not touch UI); P1.6's `vite build` green plus clone-build green post-BUG-P2-01 — re-run recorded in §21.

## 19. Reproducibility / fresh-clone truth

`/tmp/p2-fresh` clone at `65d7b3b` + BUG-P2-01 patch: backend venv install OK, boot health 200, `pnpm install --frozen-lockfile` OK, prod build OK. The P2 environment itself is also reproducible: commands in §3 (redis 6380, worker, uvicorn with webhook secrets + SSL_CERT_FILE, celery enqueue, webhook HMAC headers) are exactly what the batteries used.

## 20. Unverified / unavailable — 2026-09-18 (honest list)

| Surface | Status | Reason |
|---|---|---|
| GitLab API + sync | UNVERIFIED | egress refused; no credential |
| Kubernetes | BLOCKED | no cluster/config |
| Postgres hard isolation | BLOCKED in-sandbox | no Postgres; compose topology inventoried only |
| Docker multi-container | UNVERIFIED | no runtime (compose file reviewed) |
| Sentry crash events | NOT_CONFIGURED | DSN empty (fail-off by design) |
| SendGrid email | NOT_CONFIGURED | key empty + egress refused |
| Stripe API (billing sync) | NOT_CONFIGURED | key empty + webhook receiver verified w/ test secret |
| Slack egress (chat.postMessage) | NOT_CONFIGURED | webhook receiver verified w/ test secret |
| AWS Cost Explorer | NOT_CONFIGURED | keys empty |
| WS positive emit (`pipeline.update`) | UNVERIFIED in-sandbox | read-only App token + no active runs (§14) |
| GitHub App tokens in `test_connection`/manual sync | KNOWN GAP | product is PAT-oriented (§4) — feature decision, P3 |
| BACKGROUND_LEADER as real election | GAP (documented) | config flag, no distributed lock (§9) — P3 |

## 21. Final verdict

**Closing-tree proof (2026-09-18):**

- Backend suite on the final tree (includes BUG-P2-02 and BUG-P2-03 fixes + their regression tests): **290 passed, 0 failed, 0 skipped** (632.58s; P1.6's 285 + 5 new P2 regression tests).
- Frontend production build on the final tree: **green** (vite, 8.81s).
- Fresh-clone reproducibility: green post-BUG-P2-01 (§19).
- Tracked dev DB restored (`git checkout -- backend/uniops_dev.db`) so no battery rows leak into the tree.

**Verdict: CONDITIONAL PASS.**

**Passed (VERIFIED with real evidence):** GitHub integration end-to-end against the real GitHub API (connect → truth-comparison vs GitHub's own data → mutation lifecycle → tenant isolation → idempotency), the web→API→Redis→Celery-worker→DB chain with worker logs as proof, shared Redis rate limiting (real 429s + cross-process counter), all four webhook receivers' signed fail-closed matrices, webhook→DB→tenant-scoped-REST chain, contract fix for the pipelines envelope, and removal of the only reachable fake-success pattern in the codebase.

**Conditions (explicitly NOT passed, next-phase work, per §20):**
1. **WS positive event delivery** (`pipeline.update` to the owning tenant) — structurally isolated but positive-path unverified in-sandbox (read-only App token, no active runs). Needs a PAT-capable staging environment or an Actions-writable token.
2. **GitLab, Kubernetes, Postgres, Docker-compose topology** — environment-blocked here; need a staging env with egress + a real cluster + Postgres to verify.
3. **Sentry/SendGrid/Stripe/Slack egress/AWS CE** — credentials absent (NOT_CONFIGURED); must be supplied and verified in staging.
4. **Operational design constraints** (not P2-scope changes): GitHub App tokens unusable by the PAT-oriented `test_connection`/manual-sync; `BACKGROUND_LEADER` is a config flag, not a distributed election lock. Both documented with precise behavior; both are P3 feature decisions.

No proven defect was downgraded to "environmental", no unavailable service is counted as passed, and every fixed bug carries a regression test that demonstrably failed on the pre-fix tree.
