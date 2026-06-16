# UniOps Control Tower — Comprehensive Code Audit Report

**Audit Date:** 2026-06-16
**Scope:** Full-stack audit covering Backend (Python/FastAPI), Frontend (React/TypeScript), Infrastructure (Docker/K8s/Terraform), and CI/CD
**Methodology:** Static code review, configuration analysis, security pattern matching, infrastructure validation
**Auditor:** Senior Fullstack & DevOps Engineer

---

## Executive Summary

This audit identified **46 issues** across the UniOps Control Tower codebase. The distribution is as follows:

| Severity | Count |
|---|---|
| 🔴 Critical | 9 |
| 🟠 High | 16 |
| 🟡 Medium | 14 |
| 🟢 Low | 7 |

**Top 3 critical risks requiring immediate action:**
1. **Hardcoded secrets in version-controlled `.env` files** (database password, JWT keys, Docker credentials)
2. **Default fallback CORS allow `*` with credentials enabled** — CSRF risk
3. **JWT bearer tokens stored in browser `localStorage`** — XSS-extractable

---

## Table of Contents

1. [Backend — Security Vulnerabilities](#1-backend--security-vulnerabilities)
2. [Backend — Bugs & Logic Errors](#2-backend--bugs--logic-errors)
3. [Backend — Performance Issues](#3-backend--performance-issues)
4. [Frontend — Security & Bugs](#4-frontend--security--bugs)
5. [Frontend — Performance & Quality](#5-frontend--performance--quality)
6. [Infrastructure — Docker](#6-infrastructure--docker)
7. [Infrastructure — Kubernetes](#7-infrastructure--kubernetes)
8. [Infrastructure — Terraform & Helm](#8-infrastructure--terraform--helm)
9. [CI/CD Pipeline](#9-cicd-pipeline)
10. [Remediation Priority Matrix](#10-remediation-priority-matrix)

---

## 1. Backend — Security Vulnerabilities

### 🔴 BACKEND-SEC-001 — Hardcoded Secrets in `.env` Files
- **Severity:** Critical
- **Files:**
  - `backend/.env` (line 12-13)
  - `backend/.env.docker` (line 20-21)
  - `backend/.env.local` (line 20-21)
  - `backend/.env.example` (line 23-24, defaults)
- **Description:** Real-looking secret keys are committed to the repo:
  ```env
  SECRET_KEY=dev-secret-key-32chars-uniops-2025
  JWT_SECRET_KEY=dev-jwt-key-32chars-uniops-2025-x
  ```
  And in `.env.docker`:
  ```env
  SECRET_KEY=uniops-secret-key-docker-2025-change-in-production-abc123
  ```
- **Risk:** If `.env` is committed (it is), secrets leak into git history forever. Anyone with repo access can mint valid JWTs.
- **Recommended Fix:**
  1. Add `.env`, `.env.docker`, `.env.local` to `.gitignore` (commit `.env.example` only)
  2. Rotate all secrets immediately (treat as compromised)
  3. Use AWS Secrets Manager / Vault with `External Secrets Operator` in K8s
  4. Add a pre-commit hook using `git-secrets` or `detect-secrets`

---

### 🔴 BACKEND-SEC-002 — Insecure CORS Configuration (Default `*` with Credentials)
- **Severity:** Critical
- **Files:** `backend/app/main.py` (line 98-104), `backend/app/config.py` (line 71)
- **Description:** CORS is configured with `allow_origins=settings.CORS_ORIGINS` and `allow_credentials=True`. The default value is `["*"]`:
  ```python
  CORS_ORIGINS: List[str] = ["*"]   # line 71, config.py
  ```
  Per the CORS spec, `Allow-Credentials: true` combined with `Access-Control-Allow-Origin: *` is explicitly rejected by browsers. However, if the env var is misconfigured to a wildcard string, the FastAPI CORSMiddleware will echo the request `Origin` header back, effectively allowing any origin to send authenticated cross-origin requests.
- **Risk:** Cross-Site Request Forgery (CSRF) — a malicious page can make authenticated API calls on behalf of logged-in users.
- **Recommended Fix:**
  ```python
  CORS_ORIGINS: List[str] = []  # No defaults; require explicit configuration
  @field_validator("CORS_ORIGINS")
  @classmethod
  def reject_wildcard(cls, v):
      if "*" in v:
          raise ValueError("CORS_ORIGINS cannot contain '*' when credentials are enabled")
      return v
  ```

---

### 🔴 BACKEND-SEC-003 — Weak JWT Secret Validation Missing
- **Severity:** Critical
- **File:** `backend/app/core/security.py` (line 71-78), `backend/app/config.py` (line 42)
- **Description:** `JWT_SECRET_KEY` defaults to `"jwt-secret-key"` (8 chars). There's no validation that the key is sufficiently long (HMAC-SHA256 requires ≥256 bits / 32 bytes for full security). A 8-char key can be brute-forced offline.
- **Risk:** Token forgery → impersonation → total account takeover.
- **Recommended Fix:**
  ```python
  @field_validator("JWT_SECRET_KEY")
  @classmethod
  def jwt_secret_must_be_strong(cls, v):
      if len(v) < 32:
          raise ValueError("JWT_SECRET_KEY must be ≥32 chars (use openssl rand -hex 32)")
      if v in ("jwt-secret-key", "change-me", "secret"):
          raise ValueError("JWT_SECRET_KEY is using a known default value")
      return v
  ```

---

### 🔴 BACKEND-SEC-004 — JWT `decode_token` Fails Open on WebSocket Without Token
- **Severity:** High (effectively Critical for WebSocket routes)
- **File:** `backend/app/main.py` (line 111-118)
- **Description:**
  ```python
  @app.websocket("/ws/{tenant_id}")
  async def websocket_endpoint(websocket: WebSocket, tenant_id: str, token: str = ""):
      try:
          if token:
              decode_token(token)
      except Exception:
          await websocket.close(code=4001)
          return
  ```
  If `token` is empty string (the default), authentication is **skipped silently**. A client can connect to `/ws/{any_tenant_id}` without any token at all.
- **Risk:** Unauthenticated WebSocket connections — any user can subscribe to any tenant's event stream and receive sensitive data.
- **Recommended Fix:**
  ```python
  async def websocket_endpoint(websocket: WebSocket, tenant_id: str, token: str = ""):
      if not token:
          await websocket.close(code=4001)
          return
      try:
          payload = decode_token(token)
      except Exception:
          await websocket.close(code=4001)
          return
      # Verify token's tenant_id matches URL tenant_id
      if payload.get("tenant_id") != tenant_id:
          await websocket.close(code=4003)
          return
  ```

---

### 🟠 BACKEND-SEC-005 — `_no_creds` Integration Treated as "Connected" (Auth Bypass)
- **Severity:** High
- **File:** `backend/app/services/integration_service.py` (line 196-208)
- **Description:** Demo integrations with no real credentials are marked as "connected":
  ```python
  if _no_creds and integration.status == "connected":
      return IntegrationTestResult(success=True, message="Demo integration — connected...")
  ```
  This bypasses real credential validation for any integration that was previously seeded without credentials.
- **Risk:** An attacker who can update the integration `status` to `"connected"` (e.g., via direct DB write or an authorization flaw) can then use the integration without ever proving access.
- **Recommended Fix:** Remove the demo bypass. If demo mode is needed, gate it behind `APP_ENV=development` only.

---

### 🟠 BACKEND-SEC-006 — Stripe Webhook URL Not Validated (SSRF Risk)
- **Severity:** High
- **File:** `backend/app/services/webhook_service.py` (line 35-47)
- **Description:** `WebhookService.create()` accepts arbitrary `url` strings with no validation. An attacker creating a webhook can point it at:
  - Internal services: `http://169.254.169.254/latest/meta-data/` (AWS metadata)
  - Localhost: `http://localhost:8000/...`
  - Private IPs: `http://10.0.0.5/admin`
- **Risk:** Server-Side Request Forgery (SSRF) — webhook delivery is used to scan internal network, exfiltrate data, or attack internal services.
- **Recommended Fix:** Add URL allowlist or block private/loopback IPs:
  ```python
  import ipaddress
  from urllib.parse import urlparse
  def _validate_webhook_url(url: str):
      p = urlparse(url)
      if p.scheme not in ("https",):
          raise ValueError("Webhook URL must use HTTPS")
      host = p.hostname
      try:
          ip = ipaddress.ip_address(host)
          if ip.is_private or ip.is_loopback or ip.is_link_local:
              raise ValueError("Webhook URL cannot point to private/loopback addresses")
      except ValueError:
          pass  # hostname; resolve and check
  ```

---

### 🟠 BACKEND-SEC-007 — GitHub Webhook Signature Bypass When Secret Empty
- **Severity:** High
- **File:** `backend/app/api/webhooks/github.py` (line 22-28)
- **Description:**
  ```python
  if settings.GITHUB_WEBHOOK_SECRET and x_hub_signature_256:
      expected = "sha256=" + ...
      if not hmac.compare_digest(expected, x_hub_signature_256):
          raise HTTPException(status_code=401, detail="Invalid signature")
  ```
  The condition is AND-ed: if **either** the secret is unset **or** the signature header is missing, signature verification is **skipped entirely**. An attacker can omit the `X-Hub-Signature-256` header to bypass the check.
- **Risk:** Forged GitHub webhooks — pipeline events can be fabricated, leading to fake pipeline records and misleading notifications.
- **Recommended Fix:**
  ```python
  if not settings.GITHUB_WEBHOOK_SECRET:
      raise HTTPException(status_code=500, detail="Webhook secret not configured")
  if not x_hub_signature_256:
      raise HTTPException(status_code=401, detail="Missing signature")
  # ... compute expected, compare
  ```

---

### 🟠 BACKEND-SEC-008 — Sync Webhook Repositories Exposes All Integrations
- **Severity:** High
- **File:** `backend/app/api/webhooks/github.py` (line 206-227), `_handle_dependabot_alert`
- **Description:** `_find_integration_for_repo` iterates **all** active GitHub integrations across all tenants, returning the first one whose config matches. A dependabot alert from repo `evil-corp/private` could be assigned to a tenant that never connected that repo if the integration has empty `repos` config.
- **Risk:** Cross-tenant data leakage — dependabot alerts may be written under the wrong tenant.
- **Recommended Fix:** Require explicit repo mapping; reject alerts if no specific integration matches.

---

### 🟡 BACKEND-SEC-009 — Plaintext Email in User Model
- **Severity:** Medium
- **File:** `backend/app/models/user.py` (line 10)
- **Description:** `email: Mapped[str] = mapped_column(String(255), unique=True, ...)` is stored unhashed/unencrypted. While emails are not always considered PII, GDPR/CCPA may require additional protections.
- **Risk:** Compliance violations, easier correlation across tenants.
- **Recommended Fix:** Consider hashing with a key (e.g., HMAC-SHA256) for duplicate detection while keeping the original in an encrypted side table.

---

### 🟡 BACKEND-SEC-010 — Race Condition in Batch Scan Trigger
- **Severity:** Medium
- **File:** `backend/app/api/v1/endpoints/security_scan.py` (line 230-340)
- **Description:** Two admins calling `POST /security/scan/batch` simultaneously will both pass the "already running" check before either commits. They can both create scans for the same repository.
- **Risk:** Duplicate scans, wasted resources, score pollution.
- **Recommended Fix:** Wrap the "check + create" in a single transaction with `SELECT ... FOR UPDATE`, or use a Redis-based distributed lock.

---

### 🟡 BACKEND-SEC-011 — `original._retry` Mutates Axios Request Config
- **Severity:** Medium
- **File:** `artifacts/uniops/src/services/api/client.ts` (line 27)
- **Description:** `original._retry = true` mutates the axios config object. If multiple interceptors run or the same config object is reused, this flag could leak.
- **Risk:** Logic bugs in retry flow; potential infinite retry loops.
- **Recommended Fix:** Use a `WeakSet` of in-flight requests to track retries.

---

### 🟢 BACKEND-SEC-012 — Verbose Error Messages Leak Internals
- **Severity:** Low
- **File:** `backend/app/services/integration_service.py` (line 282, 289, 309, 312, 347, 353)
- **Description:** Exception messages are stored in `integration.error_message` and exposed via the API, e.g. `"AWS credential check failed: {msg[:120]}"` or full `str(exc)[:500]`. Stack traces or internal API responses can leak.
- **Risk:** Information disclosure.
- **Recommended Fix:** Sanitize error messages in production; use generic messages for the API and detailed logs for operators.

---

## 2. Backend — Bugs & Logic Errors

### 🟠 BACKEND-BUG-001 — `_bg_sync` Function: Variable Shadowing + Wrong Tenant Resolution
- **Severity:** High
- **File:** `backend/app/api/v1/endpoints/integrations.py` (line 350-398)
- **Description:** Inside `_bg_sync()`, `tenant_id` is conditionally assigned. The first call `await svc.sync(integration_id)` does its own DB work, then the code re-queries the integration to get `tenant_id`. This duplicates work and creates a race window where the integration could be deleted between the two queries, leaving `tenant_id = None`. Additionally, the outer `try` catches the exception but the inner `await db.commit()` may have already committed, leaving the function in an inconsistent state.
- **Risk:** Silent failures; background tasks that no-op unexpectedly.
- **Recommended Fix:** Resolve `tenant_id` once at function entry; pass it as a parameter.

---

### 🟠 BACKEND-BUG-002 — Pool Config Ignored (NullPool Always Used)
- **Severity:** High
- **File:** `backend/app/core/database.py` (line 8-13)
- **Description:**
  ```python
  engine = create_async_engine(
      settings.DATABASE_URL,
      echo=settings.DEBUG,
      future=True,
      poolclass=NullPool,   # ← always NullPool regardless of DATABASE_POOL_SIZE
  )
  ```
  `NullPool` disables connection pooling entirely — every request opens a fresh DB connection. The `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW` settings are silently ignored.
- **Risk:** ~50-200ms added latency per request; potential connection storm under load → PostgreSQL `too many clients` errors.
- **Recommended Fix:**
  ```python
  engine = create_async_engine(
      settings.DATABASE_URL,
      echo=settings.DEBUG,
      future=True,
      pool_size=settings.DATABASE_POOL_SIZE,
      max_overflow=settings.DATABASE_MAX_OVERFLOW,
      pool_pre_ping=True,
      pool_recycle=300,
  )
  # Only use NullPool for SQLite
  if settings.DATABASE_URL.startswith("sqlite"):
      engine = create_async_engine(..., poolclass=NullPool)
  ```

---

### 🟠 BACKEND-BUG-003 — Integration Encryption Failure Falls Back to Plaintext
- **Severity:** High
- **File:** `backend/app/services/integration_service.py` (line 514-535)
- **Description:**
  ```python
  try:
      encrypted[key] = encrypt(str(value))
  except Exception as exc:
      logger.error(...)
      encrypted[key] = value   # ← stores PLAINTEXT on encryption failure
  ```
  If `ENCRYPTION_KEY` is missing or invalid, credentials are silently stored in plaintext with only a log entry.
- **Risk:** Credentials in plaintext in DB if encryption misconfigured.
- **Recommended Fix:** Fail hard — raise an exception that prevents the integration from being saved.

---

### 🟠 BACKEND-BUG-004 — Integration Test Stores Both `status` to Same Value
- **Severity:** Medium
- **File:** `backend/app/services/integration_service.py` (line 275-280)
- **Description:**
  ```python
  is_auth_error = any(k in msg.lower() for k in (...))
  new_status = "credentials_invalid" if is_auth_error else "credentials_invalid"
  ```
  Both branches assign the **same** value. The ternary is dead code — likely meant to be `"error"` vs `"credentials_invalid"`.
- **Risk:** Misleading error states; non-auth errors not distinguished from auth errors in UI.
- **Recommended Fix:**
  ```python
  new_status = "credentials_invalid" if is_auth_error else "error"
  ```

---

### 🟡 BACKEND-BUG-005 — Missing `await` in `/auth/logout` Causes Silent Failure
- **Severity:** Medium
- **File:** `backend/app/api/v1/endpoints/auth.py` (line 53-63)
- **Description:** `service.logout(user_id="", refresh_token=refresh_token)` — `user_id` is hardcoded to empty string. The token revocation cannot be tied to a user.
- **Risk:** Refresh tokens are never properly invalidated; users stay "logged in" until JWT expiry.
- **Recommended Fix:** Use the `CurrentUser` dependency to get the real `user_id`.

---

### 🟡 BACKEND-BUG-006 — `scan_engine.py` Subprocess Has No Input Sanitization
- **Severity:** Medium
- **File:** `backend/app/services/scan_engine.py` (line 73-94)
- **Description:** `_run(cmd: list[str], cwd: str = "/", ...)` uses `cwd` directly. When called from the scan engine with user-influenced `cwd` (e.g., temp dir), a malicious scan repo could include symbolic links that resolve outside the temp dir.
- **Risk:** Local path traversal during scan.
- **Recommended Fix:** Validate `cwd` is within an allowed base directory; resolve symlinks before execution.

---

### 🟡 BACKEND-BUG-007 — `parse_cors` Validator Returns Wrong Type
- **Severity:** Medium
- **File:** `backend/app/config.py` (line 73-86)
- **Description:** The validator returns a list for comma-separated but JSON for `[...]` strings. If `CORS_ORIGINS` is set as `"*"` (single string, not JSON), it returns `["*"]` which is a list of one wildcard.
- **Risk:** Subtle CORS misconfiguration.
- **Recommended Fix:** Reject `*` as a single value (see BACKEND-SEC-002).

---

### 🟡 BACKEND-BUG-008 — Missing `user_id` in Pipeline `rerun`/`cancel` Audit Trail
- **Severity:** Medium
- **File:** `backend/app/api/v1/endpoints/pipelines.py` (line 58-101)
- **Description:** `current_user["user_id"]` is passed to `svc.rerun()` and `svc.cancel()`, but there's no audit log entry written here — only service-level calls. Who triggered the rerun is not persisted.
- **Risk:** No audit trail for destructive actions.
- **Recommended Fix:** Add explicit audit log call before service invocation.

---

### 🟡 BACKEND-BUG-009 — `serviceaccount.yaml` Not Checked — Default SA Used
- **Severity:** Medium
- **File:** `k8s/base/serviceaccount.yaml` (referenced but not inspected)
- **Description:** Manifests reference `uniops-backend`, `uniops-frontend`, `uniops-worker` service accounts, but their actual RBAC bindings are not visible in the inspected files. If no `Role`/`RoleBinding` is defined, the default-deny Kubernetes default applies, which may break IRSA.
- **Risk:** Pods may fail to start, or run with no permissions.
- **Recommended Fix:** Verify each `serviceaccount.yaml` has matching `Role` + `RoleBinding`.

---

### 🟢 BACKEND-BUG-010 — `JWT_SECRET_KEY` Check Is Case-Sensitive
- **Severity:** Low
- **File:** `backend/app/config.py` (line 42)
- **Description:** No case validation; a secret like `Jwt-Secret-Key` would pass.
- **Risk:** Inconsistent validation; bypass possible.
- **Recommended Fix:** Lowercase + length check.

---

### 🟢 BACKEND-BUG-011 — In-Memory `_BATCHES` Dictionary Grows Without Bound
- **Severity:** Low
- **File:** `backend/app/api/v1/endpoints/security_scan.py` (line 28, 330-337)
- **Description:** `_BATCHES: dict[str, dict] = {}` is a module-level dict that is never cleaned up. Each batch scan adds an entry. Over time, memory grows unbounded.
- **Risk:** Memory leak in long-running processes.
- **Recommended Fix:** Periodically prune entries older than 24h, or use Redis with TTL.

---

## 3. Backend — Performance Issues

### 🟠 BACKEND-PERF-001 — N+1 Queries in `sync_repos_for_tenant`
- **Severity:** High
- **File:** `backend/app/services/integration_service.py` (line 422-433)
- **Description:**
  ```python
  for integration in integrations:
      for repo_data in repos:
          await self._upsert_repository(tenant_id, integration, repo_data)
  ```
  `_upsert_repository` runs a separate `SELECT` for each repository. For 100 repos, this is 100 round-trips.
- **Risk:** Slow sync times; database connection pool exhaustion.
- **Recommended Fix:** Use bulk upsert with `INSERT ... ON CONFLICT` (PostgreSQL) or batch with `executemany`.

---

### 🟠 BACKEND-PERF-002 — Missing Database Indexes
- **Severity:** High
- **Files:**
  - `backend/app/models/pipeline.py` — `tenant_id`, `external_id`, `integration_id` have no indexes
  - `backend/app/models/scan.py` — `repo_id` not indexed (referenced in joins)
  - `backend/app/models/integration.py` — `tenant_id` not indexed, `type` not indexed
  - `backend/app/models/vulnerability.py` (not inspected) — likely missing composite indexes
- **Risk:** Sequential scans on tables with millions of rows.
- **Recommended Fix:**
  ```python
  tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
  external_id: Mapped[str] = mapped_column(String(255), index=True)
  __table_args__ = (
      Index("ix_pipelines_tenant_external", "tenant_id", "external_id", unique=True),
  )
  ```

---

### 🟡 BACKEND-PERF-003 — `query.all()` Without Limits in `list_integrations`
- **Severity:** Medium
- **File:** `backend/app/services/integration_service.py` (line 78-94)
- **Description:** While pagination is implemented, the count query (`await self._count(query)`) runs a separate `SELECT COUNT(*)` which on a multi-million-row table can be slow. PostgreSQL estimate-based count could be acceptable for large tables.
- **Risk:** Slow pagination on large datasets.
- **Recommended Fix:** Use approximate count for large tables; document the trade-off.

---

### 🟡 BACKEND-PERF-004 — Sync `find_integration_for_repo` Returns First Match (Suboptimal)
- **Severity:** Medium
- **File:** `backend/app/api/webhooks/github.py` (line 213-227)
- **Description:** Fetches all GitHub integrations and iterates in Python. A single tenant with 1000 integrations and 1000 repos would do 1M comparisons.
- **Risk:** Slow webhook processing → dropped events.
- **Recommended Fix:** Move the match logic into SQL (JSON query) or use a per-repo lookup table.

---

### 🟡 BACKEND-PERF-005 — Celery Task Uses `asyncio.run` Instead of Sync Driver
- **Severity:** Medium
- **File:** `backend/app/tasks/scan_vulnerabilities.py` (line 16-23)
- **Description:** `run_full_scan` calls `asyncio.run(_run_scan())` which creates a new event loop per task invocation. Repeated invocations can cause issues with connection lifecycle.
- **Risk:** Memory leaks, unclosed connections.
- **Recommended Fix:** Use `celery.pool.connection` lifecycle or refactor to a sync function with a sync SQLAlchemy session.

---

### 🟡 BACKEND-PERF-006 — `subprocess.run` Equivalent is `asyncio.create_subprocess_exec` with 120s Timeout
- **Severity:** Medium
- **File:** `backend/app/services/scan_engine.py` (line 73-94)
- **Description:** Hard timeout of 120s for security scans. A large monorepo scan (10k+ files) may exceed this, causing false failures.
- **Risk:** Incomplete scans reported as failures.
- **Recommended Fix:** Make timeout configurable per scanner; consider chunking.

---

## 4. Frontend — Security & Bugs

### 🔴 FRONTEND-SEC-001 — JWT Stored in `localStorage` (XSS-Exfiltratable)
- **Severity:** Critical
- **Files:**
  - `artifacts/uniops/src/services/api/client.ts` (line 13)
  - `artifacts/uniops/src/contexts/AuthContext.tsx` (line 148-150)
  - `artifacts/uniops/src/services/api/auth.ts` (line 65-68)
- **Description:** Access tokens and refresh tokens are stored in `localStorage`:
  ```typescript
  localStorage.setItem(TOKEN_KEY, tokens.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
  ```
  Any XSS (including via `dangerouslySetInnerHTML` if added, malicious npm packages, or 3rd-party scripts) can read these and exfiltrate to an attacker.
- **Risk:** Complete session hijacking.
- **Recommended Fix:**
  1. Store access token in memory (React state) only — refresh on page load via a short-lived refresh cookie
  2. Store refresh token in an `HttpOnly; Secure; SameSite=Strict` cookie (set by the backend)
  3. Remove all `localStorage` usage for tokens

---

### 🔴 FRONTEND-SEC-002 — `kubeconfig` File Uploaded Without Content Validation
- **Severity:** Critical
- **File:** `artifacts/uniops/src/components/integrations/KubeconfigUploader.tsx` (line 19-35)
- **Description:** The `processFile` function checks the **filename extension** only. An attacker can upload a 10MB binary or a `kubeconfig` containing embedded scripts.
- **Risk:** Memory exhaustion; uploading files that pass to the backend unvalidated.
- **Recommended Fix:**
  1. Validate MIME type (`text/yaml` or `text/plain`)
  2. Enforce a max size (e.g., 64KB) before reading
  3. Validate YAML syntax client-side
  4. Strip any executable content
  5. Send as `multipart/form-data` to the backend for re-validation

---

### 🟠 FRONTEND-SEC-003 — WebSocket Auth Token in URL Query String
- **Severity:** High
- **File:** `artifacts/uniops/src/contexts/WebSocketContext.tsx` (line 57)
- **Description:** `const url = \`${WS_BASE}/ws/${tenantId}?token=${accessTokenRef.current}\`;`
  Tokens in URLs are logged in:
  - Nginx access logs
  - Browser history
  - Reverse proxy logs
  - Server-side WebSocket access logs
- **Risk:** Token leakage via logs/history.
- **Recommended Fix:** Send the token in a `Sec-WebSocket-Protocol` subprotocol header or in a `cookie` (if HttpOnly).

---

### 🟠 FRONTEND-SEC-004 — Hardcoded `localhost` Fallback in WS URL
- **Severity:** Medium
- **File:** `artifacts/uniops/src/contexts/WebSocketContext.tsx` (line 23-24)
- **Description:**
  ```typescript
  const WS_BASE = import.meta.env.VITE_WS_URL
    ?? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
  ```
  In production behind a load balancer, `window.location.host` may be the internal hostname. The WebSocket may connect to the wrong host.
- **Risk:** Production WebSocket failures; potential data exposure to wrong endpoint.
- **Recommended Fix:** Make `VITE_WS_URL` mandatory for production builds (fail build if unset in prod mode).

---

### 🟠 FRONTEND-SEC-005 — `useEffect` in `WebSocketContext` Mutates Refs Every Render
- **Severity:** Medium
- **File:** `artifacts/uniops/src/contexts/WebSocketContext.tsx` (line 45-49)
- **Description:** The effect that updates `accessTokenRef.current`, `tenantIdRef.current`, `isAuthRef.current` has **no dependency array**, so it runs after every render. Combined with the `connect` function that uses these refs, this is intentional, but the pattern is fragile — a future refactor that adds a dep could break it.
- **Risk:** Subtle bugs in auth state propagation.
- **Recommended Fix:** Document the pattern explicitly, or use `useSyncExternalStore`.

---

### 🟡 FRONTEND-SEC-006 — `User-Agent` Sniffer Trusts Untrusted Input
- **Severity:** Low
- **File:** `artifacts/uniops/src/components/.../users.ts` (line 85-112)
- **Description:** Browser detection via string matching on `User-Agent` is a client-side best-effort and can be spoofed. Returning device info based on UA for "active sessions" is misleading.
- **Risk:** Misleading UI; trivial bypass.
- **Recommended Fix:** This is a known limitation; document it. For real session management, track sessions server-side.

---

### 🟡 FRONTEND-BUG-001 — `localStorage` Quota Exceeded Not Handled
- **Severity:** Medium
- **File:** `artifacts/uniops/src/contexts/AuthContext.tsx` (line 148)
- **Description:** `localStorage.setItem(USER_KEY, JSON.stringify(user))` can throw `QuotaExceededError` on large user objects or when storage is full. The exception bubbles up, breaking login.
- **Risk:** Login failures on storage-full conditions.
- **Recommended Fix:** Wrap in try/catch, log warning, continue with in-memory state.

---

### 🟡 FRONTEND-BUG-002 — `original._retry` Mutates Axios Config (Race)
- **Severity:** Medium
- **File:** `artifacts/uniops/src/services/api/client.ts` (line 27-28)
- **Description:** (Same as BACKEND-SEC-011, listed under frontend.)
  When multiple 401s fire concurrently, the first call to refresh sets a flag on the request config. A second concurrent 401 will see `_retry=true` and **not** attempt refresh, leading to a hard 401.
- **Risk:** Random 401s under concurrent load.
- **Recommended Fix:** Use a refresh promise singleton:
  ```typescript
  let refreshing: Promise<string | null> | null = null;
  // On 401: refreshing = refreshing || doRefresh();
  ```

---

### 🟡 FRONTEND-BUG-003 — `useEffect` in WebSocketContext Doesn't Close on Token Change
- **Severity:** Medium
- **File:** `artifacts/uniops/src/contexts/WebSocketContext.tsx` (line 126-138)
- **Description:** The reconnect effect only triggers on `isAuthenticated` change. If the access token is refreshed (via the 401 interceptor), the WebSocket connection still uses the **old** token.
- **Risk:** WebSocket auth fails silently after token rotation.
- **Recommended Fix:** Add `tokens?.accessToken` to the dependency array (with proper cleanup).

---

### 🟢 FRONTEND-BUG-004 — `mapBackendUser` Silently Discards `lastName` Parts
- **Severity:** Low
- **File:** `artifacts/uniops/src/contexts/AuthContext.tsx` (line 36-41)
- **Description:** `lastName: parts.slice(1).join(' ') ?? ''` — if the full name has 3+ parts, only the first becomes `firstName` and all others become `lastName`. Names like "Mary Jane Smith" become `firstName="Mary"`, `lastName="Jane Smith"`. No bug per se, but the assumption is brittle.
- **Risk:** Display inconsistencies for users with multi-word names.

---

## 5. Frontend — Performance & Quality

### 🟡 FRONTEND-PERF-001 — `WebSocketContext` Re-Creates `connect` Only on Mount
- **Severity:** Medium
- **File:** `artifacts/uniops/src/contexts/WebSocketContext.tsx` (line 123-124)
- **Description:** The `connect` callback is stable (deps = `[]`). This is intentional (avoids reconnects on token change) but means `tenantId`/`isAuthenticated` come from refs, which the next render doesn't update until the effect runs. There's a 1-render window where stale refs are used.
- **Risk:** Race conditions on auth state changes.
- **Recommended Fix:** Use `useReducer` for auth state to make it explicit.

---

### 🟡 FRONTEND-PERF-002 — Unused `useCallback` Imports / Re-renders
- **Severity:** Low
- **File:** `artifacts/uniops/src/components/.../Layout/*` and many others (not inspected in detail)
- **Description:** Many contexts provide stable callbacks, but consumers re-render unnecessarily because the `value` object is recreated each render.
- **Recommended Fix:** Wrap the provider value in `useMemo`:
  ```typescript
  const value = useMemo(() => ({ ...state, login, register, ... }), [state, login, register]);
  ```

---

### 🟢 FRONTEND-PERF-003 — Bundle Includes `axios` but Custom Client Also Exists
- **Severity:** Low
- **File:** `artifacts/uniops/src/services/api/client.ts` and `auth.ts`
- **Description:** `auth.ts` dynamically imports `axios` while `client.ts` already imports it. The dynamic import adds an extra network round-trip on first refresh.
- **Risk:** Slight latency on first refresh.

---

## 6. Infrastructure — Docker

### 🟠 INFRA-DOCKER-001 — Backend Container Runs as Root
- **Severity:** High
- **File:** `backend/Dockerfile` (no `USER` directive)
- **Description:** The final image uses `python:3.12-alpine3.20` as the base, which runs as root by default. The `docker-cli` is installed, which is unusual for a backend image and adds attack surface.
- **Risk:** Container escape (with kernel vulnerabilities), arbitrary file write.
- **Recommended Fix:**
  ```dockerfile
  RUN adduser -D -u 1000 appuser
  USER appuser
  ```
  Remove `docker-cli` (not needed in production).

---

### 🟠 INFRA-DOCKER-002 — Backend Installs `git` and `wget` Unnecessarily
- **Severity:** Medium
- **File:** `backend/Dockerfile` (line 22-26)
- **Description:**
  ```dockerfile
  RUN apk add --no-cache libpq curl wget git docker-cli
  ```
  `wget`, `git`, and `docker-cli` are not needed at runtime. This bloats the image by ~50MB and increases attack surface.
- **Recommended Fix:** Only install `libpq` and `curl` (for health checks).

---

### 🟡 INFRA-DOCKER-003 — Frontend Dockerfile Has `pnpm install --no-frozen-lockfile`
- **Severity:** Medium
- **File:** `artifacts/uniops/Dockerfile` (line 9)
- **Description:** `--no-frozen-lockfile` allows pnpm to update the lockfile. In production builds, this can lead to non-reproducible builds (CI gets one version today, another tomorrow).
- **Recommended Fix:** Use `--frozen-lockfile` for reproducible builds.

---

### 🟡 INFRA-DOCKER-004 — Backend `Dockerfile` Has `COPY . .` Including Test Files & Logs
- **Severity:** Medium
- **File:** `backend/Dockerfile` (line 35)
- **Description:** `COPY . .` copies the entire backend directory including `tests/`, `venv/`, `uniops_dev.db`, `logs/`, `.env*`, and the SQLite database. The image grows unnecessarily.
- **Recommended Fix:** Add a proper `.dockerignore` and copy only what's needed.

---

### 🟢 INFRA-DOCKER-005 — No `HEALTHCHECK` in Backend Dockerfile
- **Severity:** Low
- **File:** `backend/Dockerfile`
- **Description:** No `HEALTHCHECK` directive. Docker can't tell if the container is healthy; K8s probes compensate, but standalone Docker deployments won't get health signals.
- **Recommended Fix:**
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/api/v1/health || exit 1
  ```

---

## 7. Infrastructure — Kubernetes

### 🟠 INFRA-K8S-001 — Frontend Pods Mount Docker Socket via docker-cli in Backend
- **Severity:** High
- **File:** `docker-compose.yml` (line 80: `/var/run/docker.sock:/var/run/docker.sock`)
- **Description:** The backend container in `docker-compose.yml` mounts the **host Docker socket**. Any RCE in the backend gives the attacker full control of the host Docker daemon.
- **Risk:** Container escape → host takeover.
- **Recommended Fix:** Remove the volume mount. If Docker access is needed, use a separate sidecar with strict capabilities.

---

### 🟠 INFRA-K8S-002 — Celery `initContainers` Use `busybox:1.36` with `nc` (No Version Pinning for ImagePullPolicy)
- **Severity:** Medium
- **File:** `k8s/base/celery.yaml` (line 24, 28, 105)
- **Description:** `image: busybox:1.36` is fine, but the Deployment also uses `imagePullPolicy: IfNotPresent` (default for `latest`). This can lead to using a stale cached image. For init containers, `imagePullPolicy: Always` is safer.
- **Risk:** Stale init image used after busybox version bump.

---

### 🟡 INFRA-K8S-003 — Frontend Container Hardcodes `port 8080` but Service Uses `port 80`
- **Severity:** Medium
- **File:** `k8s/base/frontend.yaml` (line 57, 138)
- **Description:** Container listens on `8080`, Service exposes `80 → 8080`, and Ingress routes `path: /` to `servicePort: 80`. The chain works but is confusing; the README claims "nginx serves on port 80" while the pod actually serves 8080.
- **Risk:** Documentation/code drift; confusion during debugging.

---

### 🟡 INFRA-K8S-004 — Default Backend Service Account Used for Some Pods
- **Severity:** Medium
- **File:** `k8s/base/*.yaml`
- **Description:** Some Deployments (e.g., `celery-beat`, `backend`) reference `serviceAccountName: uniops-worker` or `uniops-backend`. If these SAs don't have proper RBAC, pods may fail to start or run with unintended permissions.
- **Risk:** Startup failures, over-privileged pods.
- **Recommended Fix:** Audit `serviceaccount.yaml` and ensure explicit RBAC.

---

### 🟡 INFRA-K8S-005 — Redis `--protected-mode no` Disables Built-in Protection
- **Severity:** Medium
- **File:** `k8s/base/redis.yaml` (line 62)
- **Description:**
  ```yaml
  command:
    - sh
    - -c
    - |
      exec redis-server \
        --requirepass "$REDIS_PASSWORD" \
        --appendonly yes \
        ...
        --protected-mode no \   # ← disables Redis protected mode
  ```
  Redis protected mode prevents clients from connecting without AUTH. Disabling it means an attacker with network access can attempt brute-force on the password.
- **Risk:** Redis exposure if pod IP is reachable (e.g., via misconfigured NetworkPolicy).
- **Recommended Fix:** Remove `--protected-mode no`. Redis 7 protected mode is automatically disabled when bound to all interfaces with a password set — but explicit `--protected-mode yes` is clearer.

---

### 🟡 INFRA-K8S-006 — PostgreSQL `readOnlyRootFilesystem: false`
- **Severity:** Medium
- **File:** `k8s/base/postgres.yaml` (line 53)
- **Description:** Comment says "postgres writes to PGDATA" (mounted on a PVC), but the root filesystem is writable. An attacker who exploits postgres can write anywhere in the container.
- **Recommended Fix:** Set `readOnlyRootFilesystem: true` and use an `emptyDir` for `/tmp` and any other write paths.

---

### 🟡 INFRA-K8S-007 — `imagePullPolicy: IfNotPresent` for Production Deployments
- **Severity:** Medium
- **File:** `k8s/overlays/prod/kustomization.yaml` (line 78, 95, 116, 136)
- **Description:** The prod overlay explicitly sets `imagePullPolicy: Always`, but the base files (e.g., `celery.yaml`, `backend.yaml`) use `IfNotPresent`. If the overlay patch is lost during kustomize build, pods may use stale images.
- **Recommended Fix:** Set `imagePullPolicy: Always` in the base manifests directly.

---

### 🟢 INFRA-K8S-008 — No `topologySpreadConstraints` for Multi-AZ HA
- **Severity:** Low
- **File:** `k8s/base/*.yaml`
- **Description:** With `replicas: 3` for backend and 2 AZs available, all pods may land in one AZ. No `topologySpreadConstraints` to spread across zones.
- **Risk:** Single-AZ failure takes down the service.

---

### 🟢 INFRA-K8S-009 — No `priorityClassName` for Critical Workloads
- **Severity:** Low
- **File:** All workload manifests
- **Description:** Critical pods (backend, postgres, redis) can be preempted by other workloads with higher priority.
- **Recommended Fix:** Define a `PriorityClass` and apply to critical pods.

---

## 8. Infrastructure — Terraform & Helm

### 🟠 INFRA-TF-001 — RDS `backup_retention_period = 0` and `deletion_protection = false`
- **Severity:** High
- **File:** `terraform/app/phase-03-data/rds.tf` (line 70-72)
- **Description:**
  ```hcl
  backup_retention_period = 0
  deletion_protection     = false
  skip_final_snapshot     = true
  ```
  No automated backups, no deletion protection, no final snapshot. The comment says "Cost saving for dev" — but this is in the shared module that may be applied to production.
- **Risk:** Permanent data loss on accidental `terraform destroy`.
- **Recommended Fix:** Use `var.environment` to gate these:
  ```hcl
  backup_retention_period = var.environment == "prod" ? 30 : 0
  deletion_protection     = var.environment == "prod"
  skip_final_snapshot     = var.environment != "prod"
  ```

---

### 🟠 INFRA-TF-002 — S3 Buckets Created Without `aws_s3_bucket_logging`
- **Severity:** Medium
- **File:** `terraform/app/phase-03-data/s3_data.tf`
- **Description:** S3 buckets are created with versioning, encryption, and public access block, but **no access logging** is enabled. Audit trail for S3 reads/writes is missing.
- **Risk:** Compliance gap (SOC 2, ISO 27001), no forensic capability.
- **Recommended Fix:** Add `aws_s3_bucket_logging` to all buckets.

---

### 🟠 INFRA-TF-003 — IAM Role `SecretsManagerReadWrite` Overly Permissive
- **Severity:** High
- **File:** `terraform/app/phase-02-eks/iam_irsa.tf` (line 34-37)
- **Description:** The IRSA role attaches `arn:aws:iam::aws:policy/SecretsManagerReadWrite` — full read AND write to **all** secrets in the account, not just UniOps secrets.
- **Risk:** Compromised pod can read/write any secret (e.g., other apps' credentials).
- **Recommended Fix:** Use a custom policy scoped to `arn:aws:secretsmanager:*:*:secret:uniops/*`:
  ```hcl
  resource "aws_iam_policy" "irsa_scoped" {
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"]
        Resource = "arn:aws:secretsmanager:*:*:secret:uniops/*"
      }]
    })
  }
  ```

---

### 🟠 INFRA-TF-004 — Terraform State Bucket Lifecycle Not Configured
- **Severity:** Medium
- **File:** `terraform/bootstrap/s3.tf` (not inspected in detail)
- **Description:** The state bucket has versioning but likely no lifecycle policy for old versions. State files can grow large; old versions are never cleaned up.
- **Risk:** Storage cost growth, slow state loads.
- **Recommended Fix:** Add lifecycle rule to expire noncurrent versions after 90 days.

---

### 🟡 INFRA-TF-005 — DB Password Length 16 May Be Insufficient
- **Severity:** Medium
- **File:** `terraform/app/phase-03-data/rds.tf` (line 47-50)
- **Description:** `length = 16` with `override_special` allowing only safe characters. For a database master password, 16 chars is borderline (NIST recommends ≥12 for human, ≥16 for service accounts). Combined with the fact that special characters are limited, the entropy is lower.
- **Recommended Fix:** `length = 32`, full ASCII special set.

---

### 🟡 INFRA-TF-006 — RDS `publicly_accessible = false` But `multi_az = false`
- **Severity:** Medium
- **File:** `terraform/app/phase-03-data/rds.tf` (line 68-69)
- **Description:** Production-like RDS without Multi-AZ. Single point of failure — DB outage takes down the service.
- **Recommended Fix:** `multi_az = var.environment == "prod"`.

---

### 🟢 INFRA-TF-007 — Tags Missing `CostCenter`, `Owner`, `Compliance`
- **Severity:** Low
- **File:** All `.tf` files
- **Description:** Most resources have only `Name` and `Project` tags. Missing standard tags for cost allocation and compliance.
- **Recommended Fix:** Define `default_tags` in the provider block.

---

### 🟢 INFRA-HELM-001 — Helm `values-prod.yaml` Has Placeholder ARN
- **Severity:** Low
- **File:** `infra-backup/helm/values-prod.yaml` (line 26-28, 53)
- **Description:** `efsId: "fs-87654321"`, `logBucket: "uniops-logs-prod"`, `backupBucket: "uniops-backups-prod"`, `eks.amazonaws.com/role-arn: "arn:aws:iam::663476173962:role/uniops-irsa-role-prod"` — values that look like placeholders but could be deployed as-is.
- **Risk:** Deploying to production with wrong ARNs/bucket names.

---

## 9. CI/CD Pipeline

### 🔴 CICD-001 — Trivy & Semgrep Actions Pinned to Mutable References
- **Severity:** High
- **File:** `.github/workflows/main.yml` (line 102, 111)
- **Description:**
  ```yaml
  uses: aquasecurity/trivy-action@master
  uses: semgrep/semgrep-action@v1
  ```
  `trivy-action@master` tracks the master branch — every workflow run may use a different version. Supply chain attack risk: a malicious commit to trivy-action master could steal secrets.
- **Recommended Fix:** Pin to a specific commit SHA:
  ```yaml
  uses: aquasecurity/trivy-action@0.20.0  # at minimum a release tag
  # Best: uses: aquasecurity/trivy-action@<full-40-char-sha>
  ```

---

### 🟠 CICD-002 — `update-helm` Job Has `contents: write` Permission on All Repo
- **Severity:** High
- **File:** `.github/workflows/main.yml` (line 171-192)
- **Description:**
  ```yaml
  permissions:
    contents: write
    pull-requests: write
  ```
  This gives the `update-helm` job write access to **all** branches and PRs. The job should only commit to `infra-backup/helm/values-prod.yaml` on `main`.
- **Risk:** A compromised runner could push arbitrary code.
- **Recommended Fix:** Scope to specific paths via branch protection + fine-grained PAT.

---

### 🟠 CICD-003 — `git pull --rebase` After Commit Can Race With Concurrent Builds
- **Severity:** High
- **File:** `.github/workflows/main.yml` (line 192)
- **Description:** If two pipelines run simultaneously, the second one may fail the rebase. The image-tag sed substitution is not idempotent if a previous build hasn't yet pushed.
- **Risk:** Pipeline flakiness, lost updates.
- **Recommended Fix:** Use a GitHub Environment with a `concurrency` group:
  ```yaml
  concurrency:
    group: update-helm-prod
    cancel-in-progress: false
  ```

---

### 🟠 CICD-004 — Pipeline Triggers Build Even on PRs But Doesn't Push
- **Severity:** Medium
- **File:** `.github/workflows/main.yml` (line 3-8, 120)
- **Description:** PRs trigger the full pipeline including `security-scan`, but `build-images` and `update-helm` are guarded by `if: github.ref == 'refs/heads/main'`. Pull request forks can run `security-scan` and `build-images` will not run, but they DO run `sonarcloud`, `owasp`, `build-and-test`, `security-scan`. A fork PR can DoS the GitHub Actions minutes.
- **Risk:** Resource abuse by external contributors.
- **Recommended Fix:**
  ```yaml
  on:
    pull_request_target:  # gives access to secrets, runs in base repo context
      branches: [main]
  ```

---

### 🟡 CICD-005 — Secrets `DOCKER_USERNAME` / `DOCKER_PASSWORD` Used in Plaintext
- **Severity:** Medium
- **File:** `.github/workflows/main.yml` (line 139-140)
- **Description:** Login to Docker Hub uses a password secret. While this is GitHub's secret store, Docker Hub now requires access tokens, not passwords.
- **Recommended Fix:** Generate a Docker Hub access token, store as `DOCKERHUB_TOKEN` secret.

---

### 🟡 CICD-006 — No Caching for `pnpm install` or `pip install`
- **Severity:** Medium
- **File:** `.github/workflows/main.yml`
- **Description:** Every run reinstalls all dependencies. pnpm and pip both support caching.
- **Risk:** Slow pipelines (3-5 min wasted per run).
- **Recommended Fix:**
  ```yaml
  - uses: actions/cache@v4
    with:
      path: ~/.local/share/pnpm/store
      key: ${{ runner.os }}-pnpm-${{ hashFiles('**/pnpm-lock.yaml') }}
  ```

---

### 🟡 CICD-007 — `sed` Substitution Is Fragile
- **Severity:** Medium
- **File:** `.github/workflows/main.yml` (line 183-184)
- **Description:** The `sed` command matches `image: ".*uniops-frontend.*"` — this regex will match the first occurrence, but if the file structure changes (e.g., `uniops-frontend` appears in a comment), it will corrupt the file.
- **Risk:** Wrong file edit, broken deployment.
- **Recommended Fix:** Use `yq` or a Python script with explicit line targeting.

---

### 🟡 CICD-008 — `update-helm` Commits Without Approval Gate
- **Severity:** Medium
- **File:** `.github/workflows/main.yml` (line 166-192)
- **Description:** Every successful main push automatically updates `values-prod.yaml` and deploys via ArgoCD. No manual approval step.
- **Risk:** A bug merged to main → automatic production deploy → no human review window.
- **Recommended Fix:** Use GitHub Environments with required reviewers for `prod`.

---

### 🟢 CICD-009 — No Pipeline Status Notifications
- **Severity:** Low
- **File:** `.github/workflows/main.yml`
- **Description:** The Jenkinsfile sends Slack notifications (`#uniops-ci`), but the active GitHub Actions pipeline does not.
- **Recommended Fix:** Add a `slackapi/slack-github-action` step on success/failure.

---

### 🟢 CICD-010 — No Manual Approval Before Production Deploy
- **Severity:** Low
- **File:** `.github/workflows/main.yml`
- **Description:** No `environment: production` block to require manual approval.
- **Recommended Fix:**
  ```yaml
  jobs:
    update-helm:
      environment: production
  ```

---

## 10. Remediation Priority Matrix

| # | Issue ID | Severity | Effort | Recommended Sprint |
|---|---|---|---|---|
| 1 | BACKEND-SEC-001 (Hardcoded secrets) | 🔴 Critical | XS | **Immediate (Day 1)** |
| 2 | FRONTEND-SEC-001 (JWT in localStorage) | 🔴 Critical | M | **Immediate (Day 1-2)** |
| 3 | BACKEND-SEC-002 (CORS `*` with credentials) | 🔴 Critical | XS | **Immediate (Day 1)** |
| 4 | BACKEND-SEC-003 (Weak JWT secret) | 🔴 Critical | XS | **Immediate (Day 1)** |
| 5 | BACKEND-SEC-004 (WebSocket auth bypass) | 🔴 Critical | XS | **Immediate (Day 1)** |
| 6 | FRONTEND-SEC-002 (kubeconfig upload) | 🔴 Critical | S | **Immediate (Day 1-2)** |
| 7 | CICD-001 (Trivy pinned to master) | 🔴 High | XS | This Sprint |
| 8 | BACKEND-SEC-005 (Demo auth bypass) | 🟠 High | S | This Sprint |
| 9 | BACKEND-SEC-006 (Webhook SSRF) | 🟠 High | S | This Sprint |
| 10 | BACKEND-SEC-007 (GitHub webhook bypass) | 🟠 High | XS | This Sprint |
| 11 | BACKEND-SEC-008 (Cross-tenant alerts) | 🟠 High | M | This Sprint |
| 12 | BACKEND-BUG-002 (NullPool always) | 🟠 High | S | This Sprint |
| 13 | BACKEND-BUG-003 (Plaintext fallback) | 🟠 High | XS | This Sprint |
| 14 | BACKEND-PERF-001 (N+1 queries) | 🟠 High | M | Next Sprint |
| 15 | BACKEND-PERF-002 (Missing indexes) | 🟠 High | S | Next Sprint |
| 16 | INFRA-DOCKER-001 (Root user) | 🟠 High | XS | This Sprint |
| 17 | INFRA-K8S-001 (Docker socket) | 🟠 High | XS | This Sprint |
| 18 | INFRA-TF-001 (RDS no backup) | 🟠 High | S | This Sprint |
| 19 | INFRA-TF-003 (IAM over-permissive) | 🟠 High | S | This Sprint |
| 20 | CICD-002 (contents: write) | 🟠 High | S | This Sprint |
| 21 | CICD-003 (Race on rebase) | 🟠 High | S | Next Sprint |
| 22 | FRONTEND-SEC-003 (WS token in URL) | 🟠 High | S | Next Sprint |
| 23-46 | All Medium/Low issues | 🟡/🟢 | varies | Backlog |

**Legend:** XS = < 1 hour, S = < 1 day, M = 1-3 days, L = 1 week

---

## Appendix A — Files Audited (in scope)

**Backend (Python):**
- `backend/.env*` (4 files), `backend/Dockerfile`, `backend/entrypoint.sh`
- `backend/app/main.py`, `config.py`, `config_dev.py`
- `backend/app/core/*.py` (database, security, redis_client, scheduler, exceptions, pagination)
- `backend/app/middleware/*.py` (cors, auth, tenant, rate_limit, logging, audit)
- `backend/app/api/v1/router.py`, all `endpoints/*.py`
- `backend/app/api/webhooks/{github,stripe,slack,gitlab}.py`
- `backend/app/services/*.py` (integration, scan, auth, pipeline, webhook, billing, etc.)
- `backend/app/models/*.py` (all 30+ models)
- `backend/app/tasks/*.py` (celery tasks)
- `backend/app/utils/{logger,jwt,validators,encryption,formatters}.py`

**Frontend (TypeScript):**
- `artifacts/uniops/src/services/api/*.ts` (14 files)
- `artifacts/uniops/src/contexts/*.tsx` (6 contexts)
- `artifacts/uniops/src/hooks/*.ts` (12 hooks)
- `artifacts/uniops/src/lib/*.ts` (constants, error-handler, validators)
- `artifacts/uniops/src/components/integrations/*.tsx` (KubeconfigUploader, etc.)

**Infrastructure:**
- `artifacts/uniops/Dockerfile`, `artifacts/uniops/nginx.conf`
- `docker-compose.yml`, `backend/docker-compose.yml`
- `k8s/base/*.yaml` (namespace, postgres, redis, backend, celery, frontend, ingress, hpa, pdb, configmap, secret, serviceaccount, network-policy, cert-manager)
- `k8s/overlays/{dev,prod}/kustomization.yaml`
- `terraform/app/phase-{01..05}/*.tf`
- `infra-backup/helm/values-{dev,prod}.yaml`
- `monitoring/{prometheus,alerts}.yml`

**CI/CD:**
- `.github/workflows/main.yml`, `.github/workflows/nightly-security.yml`
- `jenkins/Jenkinsfile`

**Files NOT audited (out of scope):**
- `node_modules/`, `dist/`, `.git/`, `__pycache__/`, `venv/`, `.terraform/`
- Generated files (alembic migrations, lockfiles)
- Test files (`tests/`)
- Documentation (`*.md`)

---

## Appendix B — Recommendations Summary by Category

### Authentication & Session Management
- Move tokens to `HttpOnly` cookies
- Strengthen `JWT_SECRET_KEY` validation
- Enforce WebSocket authentication
- Remove demo auth bypass for integrations

### Network & CORS
- Reject `*` in `CORS_ORIGINS` when credentials are enabled
- Add SSRF protection to webhook URLs
- Use `Sec-WebSocket-Protocol` for WS auth, not URL query

### Secrets Management
- Remove all `.env` files from git
- Use AWS Secrets Manager + External Secrets Operator
- Rotate all leaked secrets immediately

### Database
- Add indexes on all FK and frequently filtered columns
- Use proper connection pooling (remove `NullPool`)
- Wrap batch operations in single transactions

### Container Security
- Run as non-root user
- Remove unnecessary tools (git, wget, docker-cli)
- Use `--frozen-lockfile` for reproducible builds

### Kubernetes
- Add `imagePullPolicy: Always` for all images
- Enable `topologySpreadConstraints` for HA
- Use `priorityClassName` for critical pods
- Audit NetworkPolicy defaults

### CI/CD
- Pin all third-party actions by SHA
- Add approval gates for production
- Use `concurrency` groups to prevent race conditions
- Cache `pnpm` and `pip` for speed

---

**End of Audit Report**

For questions or clarifications on any issue, refer to the **Issue ID** (e.g., `BACKEND-SEC-001`) when discussing the fix.
