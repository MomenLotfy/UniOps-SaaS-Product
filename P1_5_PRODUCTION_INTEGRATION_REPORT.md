# P1.5 — Production Integration Verification Report

**Date:** 2026-09-18 · **Branch:** `arena/01a0b237-uniops-saas-product` · **Baseline HEAD:** `f2503d5`
**Standard:** no mocks/fixtures/static-inspection alone may count as integration success; UNVERIFIED is used wherever infrastructure or credentials are unavailable; no "production ready" claims over unverified critical integrations.

---

## 1. Verdict

# ✅ PASS WITH UNVERIFIED SCOPE

Four defects were discovered, proven live, classified, fixed at root cause, regression-tested (each fails on pre-fix code, passes after), live-verified against a running app, and covered by a full-suite re-run (**264/264 backend tests, 176 s**; baseline was 243/243 — 21 net-new tests, one legacy test tightened).

**What this verdict means:** every integration surface that *could* be proven true against real infrastructure in this environment *was* — and is now honest, tenant-scoped, and fail-closed. **Two P0 security defects (unscoped integration test route; fail-open webhook verification) were found and eliminated this round; the pre-P1.5 codebase was not production-true.** No "production ready" claim is made for the UNVERIFIED integrations below; they must be verified in an environment with the corresponding infrastructure before any such claim.

---

## 2. Environment & evidence policy (what "proof" meant)

- Real HTTP against a running app (uvicorn, dev DB restored after probes) for every API-level claim.
- Real egress probes: `api.github.com` reachable (200, TLS valid); `gitlab.com` **unreachable** from the sandbox (curl exit 35, TLS EOF — infra-blocked, classified UNVERIFIED-infra, never worked around with simulation).
- Python TLS initially failed (sandbox egress CA is in the system store, not certifi) — resolved at **environment level** via `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`; TLS verification stayed ON (no code change, no `verify=False`).
- `GITHUB_TOKEN` (session env) is a **GitHub App installation token**: repo-scoped endpoints work; user-scoped endpoints (`/user`, `/user/repos`) are brokered to 403 for *any* token. Used in-memory only; **never written to the git-tracked `uniops_dev.db`** (GitHub DB flows ran on a throwaway `/tmp/p15_gh.db`).
- No kubeconfig/kubectl/cluster, no AWS credentials, no Slack/Stripe live keys, no observability/ArgoCD infrastructure in the sandbox — those surfaces are UNVERIFIED per policy (below), with their *failure contracts* verified honest wherever reachable.

---

## 3. Findings (DISCOVER → CLASSIFY → PROVE → FIX → REGRESSION → LIVE VERIFY)

### P0 — IDOR-1: `POST /api/v1/integrations/{id}/test` ignored tenancy
- **Discover/Root cause:** `endpoints/integrations.py` called `svc.test_connection(integration_id)` unscoped; the service fetches by id alone and *mutates* the row (status/error_message). Every sibling route already scopes by `current_user["tenant_id"]`.
- **Prove (live):** tenant-T2 `POST …/{t1-integration}/test` → **HTTP 200** with T1's result body and state committed onto T1's row.
- **Fix:** scoped guard `svc.get_by_id(integration_id, current_user["tenant_id"])` first (404 — existence never leaked). One route; internal background callers unchanged (they operate on already-validated rows).
- **Regression:** P0 IDOR matrix extended (`test_integrations` asserts cross-tenant `/test` → 404) — **fails pre-fix, passes post-fix**.
- **Live verify:** own-tenant 200 / cross-tenant **404** on restarted app.

### P0 — WEBHOOK-1: inbound webhook verification was fail-OPEN
- **Discover/Root cause:** github/gitlab/slack guards were `if secret and header(s)` — unset secret **or** omitted headers skipped verification, while handlers mutate tenant-owned DB rows (`_handle_workflow_run` upserts pipeline rows for the repo's owning tenant). `gitlab.py` additionally compared `X-Gitlab-Token` against **GITHUB**_WEBHOOK_SECRET (copy-paste; no GitLab setting existed). `slack.py` signed with the bot token and had `except Exception: pass` → **non-integer timestamp = total bypass**. Stripe was the correct fail-closed control.
- **Prove (live, root-mounted `/webhooks/*`):** forged github sig → **200 `{"handled":true}`**; unsigned github → 200; forged gitlab → 200; unsigned gitlab → 200; forged slack → 200 `{"ok":true}`; unsigned slack → 200; **stripe forged → 400 (control)**.
- **Fix:** uniform fail-closed, mirroring stripe: secret unset → **503** (never process); signed headers missing/mismatched → **401**; constant-time compares; slack replay window kept; new settings `GITLAB_WEBHOOK_SECRET`, `SLACK_SIGNING_SECRET`. No handler/business logic touched.
- **Regression:** `tests/test_p15_webhook_failclosed.py` (15 tests incl. signed-requests-still-accepted per provider, github-secret-cannot-open-gitlab, non-int timestamp) — **13/15 fail pre-fix, 15/15 pass post-fix**; legacy `test_github_webhook_without_secret` tightened (it tolerated the fail-open 200).
- **Live verify:** all forged/unsigned probes → 503/401 per contract; stripe unchanged.

### P1 — GITLAB-1: GitLab connection flow was deterministically dead
- **Discover/Root cause:** the shared GitHub/GitLab service branch calls `client.get_authenticated_user()` — implemented only by `GitHubClient`; `GitLabClient` never had it → `AttributeError` → status `error` with the internal attribute name leaked in the user-facing message. **Never reached the network.**
- **Prove (live):** any GitLab integration test → 100% `'error'` + `"'GitLabClient' object has no attribute 'get_authenticated_user'"`.
- **Fix (bounded):** implemented `GitLabClient.get_authenticated_user()` — real `GET {base}/api/v4/user`, `username` surfaced under the shared `login` key, non-200 raised with the real provider status/message via the transport-error type the branch already contracts on; provider-named messages made truthful (`Invalid GitLab token`, `GitLab API …` via a display-name helper; `.capitalize()` mangled "GitLab").
- **Regression:** `tests/services/test_p15_gitlab_connection_flow.py` (success→connected+username; 401→invalid_token provider-named; transport error→honest error, never AttributeError; **interface pin** on the real client fails pre-fix).
- **Live verify:** restarted app → flow now reaches the real network; honest `error` = the true blocked-egress TLS failure, no AttributeError.

### P2 — DEMO-1: fabricated "Demo integration — connected" success path
- **Discover/Root cause:** `IntegrationService.test_connection` returned `success=True` ("Demo integration — connected") for rows with no credentials ∧ `status=="connected"` — a fake-green surface contradicting the no-fake-success mandate.
- **Prove (live):** unreachable through current API flows — cred-less create stays `pending` and explicit test fails honestly (`credentials_invalid`); no seed path manufactures the state. Classified **dormant** P2, not P1 — but the fabricated-success branch had to die permanently.
- **Fix:** branch now returns `success=False` ("No credentials configured — connectivity cannot be verified") and logs an integrity warning.
- **Regression:** `tests/services/test_p15_demo_connected_honesty.py` (never fake-green; **no provider call made**) — fails pre-fix, passes post-fix.

---

## 4. Integration-by-integration truth table

| Integration | Wire/transport | Credentials available | Failure contract (verified live) | Happy path | Verdict |
|---|---|---|---|---|---|
| **GitHub** | ✅ REAL — production `GitHubClient` against `api.github.com`: real 200 (repo id 1248171842), real 404, real 403, 15 s timeout, no-verify hacks absent | ⚠️ App-installation token (user-scope broker-blocked) | ✅ REAL — provider 401/403/404 typed into `GitHubAPIError`; mapped to honest statuses with real provider text; 403 reaches row as `error`; TLS verified | ⚠️ `/user`-based `connected` blocked by token scope — env/capability limit, not-app | **PARTIAL REAL** — client boundary + error contract VERIFIED; user-scope happy path UNVERIFIED (credential capability) |
| **GitLab** | ⚠️ egress to gitlab.com blocked (curl exit 35) | none | ✅ — POST-fix flow reaches the real network; honest transport error, no exception-text leak (GITLAB-1 bug eliminated) | ⛔ unreachable infrastructure | **UNVERIFIED — infrastructure unavailable** (failure contract verified) |
| **Kubernetes** | no cluster/kubeconfig anywhere in sandbox | none | ✅ — pods API 404 with no fake data; garbage kubeconfig → honest "connection failed"; T2 cannot test T1's k8s integration (IDOR-1) | ⛔ no cluster | **UNVERIFIED — infrastructure unavailable** (failure contract verified) |
| **AWS** | no credentials/session in sandbox | none | ✅ — cred-less connect → honest `credentials_invalid` via real STS verify stage, never fake-green | ⛔ no credentials | **UNVERIFIED — credentials unavailable** (failure contract verified) |
| **ArgoCD / GitOps, Loki/Prometheus, semgrep/trivy, Slack, Stripe, Email** | no servers/keys in sandbox | none | ✅ webhook layers fail-closed (WEBHOOK-1); Stripe already fail-closed pre-existing | ⛔ no infrastructure/keys | **UNVERIFIED — infrastructure unavailable** |

---

## 5. Failure-contract & recovery audit highlights (Phase 7/8)

- Honest error propagation with **real provider messages** end-to-end (GitHub 403 text reached `error_message` verbatim; `invalid_token` on 401; truncation at 500 chars prevents unbounded payloads). `IntegrationResponse` never serializes credentials (schema-level); P0 secret-exposure suite green.
- Background create→test→sync flow is fire-and-report: failures mark rows honestly (`error`/`invalid_token`/`credentials_invalid`), never 200-with-fake-success; singleton-upsert means repeated connects merge credentials instead of duplicating rows (proven live).
- Webhook handlers mutate DB state **only after** signature verification (post-fix) — unauthenticated forged events rejected (503/401), signed events still processed (proven by tests since sandbox lacks provider secrets).

## 6. Suite & regression state

- **Backend:** 264/264 passed (176 s) — 243 baseline + IDOR-matrix assertion + 2 demo-honesty + 15 webhook fail-closed + 4/4 gitlab flow (incl. interface pin) + tightened legacy test_api.py. Every fix's regression test was executed against **pre-fix code to confirm it fails**, then restored.
- **Frontend:** untouched this phase (baseline build ✓ 9.35 s at Phase 0; `P1_5_BASELINE_REPORT.md`).
- Dev DB restored to committed state after all probes; throwaway GitHub DB in `/tmp` only.

## 7. Required before any "production ready" claim

1. **Kubernetes:** verify with a real cluster (tenant-scoped kubeconfigs, watcher lifecycle, pod exec audit path).
2. **AWS:** verify with real (read-only first) credentials — STS verify, EKS, Cost Explorer, Security Hub.
3. **GitLab:** verify from an environment where gitlab.com (or self-hosted base_url) is reachable — including the now-fixed `get_authenticated_user` happy path and repo sync.
4. **GitHub:** verify user-scoped happy path with a standard PAT/OAuth token (the sandbox token is installation-scoped).
5. **Webhooks in deployment:** set `GITHUB_WEBHOOK_SECRET`, `GITLAB_WEBHOOK_SECRET`, `SLACK_SIGNING_SECRET`, `STRIPE_WEBHOOK_SECRET` — endpoints now reject everything until configured (fail-closed, intentional).
6. **Slack/Stripe/Email/ArgoCD/observability/scanners:** verify against real services.

## 8. Commits

Chain on `arena/01a0b237-uniops-saas-product`: baseline report → DEMO-1 → IDOR-1 → WEBHOOK-1 → GITLAB-1 → this report (see `git log`).
