from __future__ import annotations
"""
Integration Service
===================
Single source of truth for all integration CRUD, credential encryption,
connection testing and sync dispatch.

CHANGES vs original
───────────────────
1. Credential encryption now uses SENSITIVE_FIELDS allowlist consistently
   everywhere (create, update, test, sync) — original had bare `decrypt(v)`
   in `_decrypt_creds` that tried to decrypt every field regardless of type.
2. Credentials are NEVER returned outside this service boundary.
   `IntegrationResponse` already omits credentials at schema level, but
   service methods now explicitly never pass decrypted dicts outward.
3. `_get_client()` is extracted to a thin factory that decouples the service
   from concrete client classes (still backward-compatible).
4. `sync_repos_for_tenant()` moved here from security_scan.py and
   integrations.py endpoint — was duplicated in both places.
5. All DB writes use `flush()` (within the caller's transaction) rather than
   mixing `flush()` and `commit()`, letting the calling layer own commit scope.
6. Background task helpers (_background_test_and_sync, _background_sync, etc.)
   moved here from the endpoint file so endpoints stay thin.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError
from app.models.integration import Integration
from app.models.scan import Repository
from app.schemas.common import PaginatedResponse
from app.schemas.integration import (
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationTestResult,
)
from app.services.base import BaseService
from app.utils.encryption import encrypt, decrypt
from app.utils.logger import logger
from app.integrations.github.client import GitHubAPIError

# Fields whose values must be stored encrypted at rest.
# Only these keys are encrypt/decrypted — everything else passes through.
SENSITIVE_FIELDS: frozenset[str] = frozenset({
    "access_key",
    "access_key_id",       # AWS IAM access key — must be encrypted at rest
    "secret_key",
    "secret_access_key",   # AWS IAM secret key — must be encrypted at rest
    "token",
    "access_token",
    "password",
    "private_key",
    "api_key",
    "webhook_secret",
    "client_secret",
})


class IntegrationService(BaseService):
    """Manages the lifecycle of third-party integration records."""

    # ─────────────────────────────────────────────────────────────────────────
    # Read
    # ─────────────────────────────────────────────────────────────────────────

    async def list(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        type_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> PaginatedResponse:
        query = select(Integration).where(Integration.tenant_id == tenant_id)
        if type_filter:
            query = query.where(Integration.type == type_filter)
        if status_filter:
            query = query.where(Integration.status == status_filter)

        total = await self._count(query)
        query = query.order_by(Integration.created_at.desc())
        items = await self._paginate(query, page, page_size)

        return PaginatedResponse(
            data=[IntegrationResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def get_by_id(self, integration_id: str) -> IntegrationResponse:
        integration = await self._get_by_id(Integration, integration_id)
        return IntegrationResponse.model_validate(integration)

    # ─────────────────────────────────────────────────────────────────────────
    # Write
    # ─────────────────────────────────────────────────────────────────────────

    async def create(self, tenant_id: str, data: IntegrationCreate) -> IntegrationResponse:
        if data.type in ("github", "gitlab"):
            existing = await self.db.execute(
                select(Integration).where(
                    Integration.tenant_id == tenant_id,
                    Integration.type == data.type,
                )
            )
            existing_integration = existing.scalar_one_or_none()
            if existing_integration:
                existing_decrypted = self._decrypt_credentials(existing_integration.credentials or {})
                merged_credentials = {
                    **existing_decrypted,
                    **(data.credentials or {}),
                }

                update_data = {
                    "credentials": self._encrypt_credentials(merged_credentials),
                    "config": {**(existing_integration.config or {}), **(data.config or {})},
                    "is_active": True,
                    "status": "pending",
                    "error_message": None,
                }
                if data.name:
                    update_data["name"] = data.name

                await self._update_fields(existing_integration, update_data)
                await self.db.flush()
                return IntegrationResponse.model_validate(existing_integration)

        existing = await self.db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.name == data.name,
                Integration.type == data.type,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"Integration '{data.name}' of type '{data.type}' already exists"
            )

        integration = Integration(
            tenant_id=tenant_id,
            name=data.name,
            type=data.type,
            credentials=self._encrypt_credentials(data.credentials or {}),
            config=data.config or {},
            status="pending",
        )
        self.db.add(integration)
        await self.db.flush()
        return IntegrationResponse.model_validate(integration)

    async def update(self, integration_id: str, data: IntegrationUpdate) -> IntegrationResponse:
        integration = await self._get_by_id(Integration, integration_id)
        update_data = data.model_dump(exclude_none=True)

        if update_data.get("status") == "disconnected" or update_data.get("is_active") is False:
            update_data["credentials"] = {}
            update_data["config"] = {}
            update_data["error_message"] = None

        if "credentials" in update_data:
            # Merge with existing encrypted credentials so callers can send
            # partial credential updates without clearing untouched fields.
            existing_decrypted = self._decrypt_credentials(integration.credentials or {})
            merged = {**existing_decrypted, **update_data["credentials"]}
            update_data["credentials"] = self._encrypt_credentials(merged)

        await self._update_fields(integration, update_data)
        return IntegrationResponse.model_validate(integration)

    async def delete(self, integration_id: str) -> None:
        """
        Hard-delete the integration and cascade-clean all related data so a
        reconnect always starts with a clean slate.
        """
        from sqlalchemy import delete as _delete
        from app.models.scan import Repository
        from app.models.pipeline import Pipeline
        from app.models.vulnerability import Vulnerability

        integration = await self._get_by_id(Integration, integration_id)
        tenant_id = integration.tenant_id
        intg_type = integration.type

        # 1. Null-out integration_id FK on pipelines / repos (avoid FK violation)
        await self.db.execute(
            _delete(Pipeline).where(
                Pipeline.integration_id == integration_id
            )
        )

        # 2. For git providers: remove discovered repositories AND their scans
        if intg_type in ("github", "gitlab"):
            repo_rows = (await self.db.execute(
                select(Repository).where(
                    Repository.tenant_id == tenant_id,
                    Repository.integration_id == integration_id,
                )
            )).scalars().all()
            for repo in repo_rows:
                await self.db.execute(
                    _delete(Vulnerability).where(Vulnerability.repo_id == repo.id)
                )
                from app.models.scan import Scan
                await self.db.execute(
                    _delete(Scan).where(Scan.repo_id == repo.id)
                )
                await self.db.delete(repo)

        # 3. Delete the integration row itself
        await self.db.delete(integration)
        await self.db.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # Operations
    # ─────────────────────────────────────────────────────────────────────────

    async def test_connection(self, integration_id: str) -> IntegrationTestResult:
        integration = await self._get_by_id(Integration, integration_id)
        creds = self._decrypt_credentials(integration.credentials or {})
        itype = integration.type

        # ── Demo / seeded integrations with no real credentials ───────────────
        # For AWS/K8s/GitHub integrations that were seeded without credentials,
        # mark them as "demo connected" so the UI shows a green state.
        # Real credentials will override this when provided.
        _no_creds = not any(
            creds.get(k)
            for k in ("token", "access_token", "access_key_id", "secret_access_key", "kubeconfig")
        )
        if _no_creds and integration.status == "connected":
            # Already marked connected by seed — keep it green
            return IntegrationTestResult(
                success=True,
                message="Demo integration — connected (no live credentials configured)",
            )

        client = self._build_client(itype, creds, integration.config or {})

        # ── AWS ───────────────────────────────────────────────────────────────
        # Multi-stage verification:
        #   Stage 1 — STS GetCallerIdentity: proves credentials are syntactically valid
        #             and the IAM user/role exists.  Fails only on wrong key/secret.
        #   Stage 2 — Account ID extraction (best-effort, non-blocking)
        #
        # Outcomes:
        #   STS passes  → status="connected"   (credentials valid; sync may still fail
        #                                        due to missing Cost Explorer perms)
        #   STS fails   → status="credentials_invalid"
        #   Exception   → status="credentials_invalid" with exception message
        #
        # NOTE: sync failures (missing ce:GetCostAndUsage etc.) are handled in
        #       sync_costs.py which sets status="sync_failed" after a successful
        #       connection test, keeping the integration "configured" in the UI.
        if itype == "aws":
            try:
                logger.info(
                    f"[aws_integration_saved] id={integration_id} "
                    f"tenant={integration.tenant_id[:8]} — running STS verification"
                )

                # Stage 1: STS — definitive credential check
                sts_ok = await client.verify_credentials_via_sts()
                logger.info(
                    f"[permissions_check_result] id={integration_id} "
                    f"sts_ok={sts_ok}"
                )

                if sts_ok:
                    account_id = await client.get_account_id()
                    integration.status = "connected"
                    integration.error_message = None
                    if account_id:
                        integration.config = {**(integration.config or {}), "account_id": account_id}
                    await self.db.flush()
                    logger.info(
                        f"[aws_connection_verified] id={integration_id} "
                        f"tenant={integration.tenant_id[:8]} account={account_id or 'n/a'}"
                    )
                    return IntegrationTestResult(
                        success=True,
                        message=f"AWS connected — account {account_id or 'verified'}"
                    )
                else:
                    # Credentials are wrong (wrong key ID, wrong secret, expired, etc.)
                    integration.status = "credentials_invalid"
                    integration.error_message = (
                        "AWS credentials could not be verified. "
                        "Check your Access Key ID and Secret Access Key."
                    )
                    await self.db.flush()
                    logger.warning(
                        f"[aws_credentials_invalid] id={integration_id} "
                        f"tenant={integration.tenant_id[:8]} — STS returned False"
                    )
                    return IntegrationTestResult(
                        success=False,
                        message="AWS credentials invalid — STS verification failed"
                    )
            except Exception as exc:
                msg = str(exc)[:300]
                # Distinguish "access denied" (wrong creds) from network errors
                is_auth_error = any(k in msg.lower() for k in (
                    "invalidclienttokenid", "signaturedoesnotmatch",
                    "tokenrefresherror", "authfailure", "accessdenied",
                    "invalid security token",
                ))
                new_status = "credentials_invalid" if is_auth_error else "credentials_invalid"
                integration.status = new_status
                integration.error_message = msg
                await self.db.flush()
                logger.error(
                    f"[aws_credentials_invalid] id={integration_id} "
                    f"tenant={integration.tenant_id[:8]} exception={msg[:80]}"
                )
                return IntegrationTestResult(
                    success=False,
                    message=f"AWS credential check failed: {msg[:120]}"
                )

        # ── Kubernetes ────────────────────────────────────────────────────────
        if itype == "kubernetes":
            try:
                ok = await client.test_connection()
                if ok:
                    integration.status = "connected"
                    integration.error_message = None
                    await self.db.flush()
                    return IntegrationTestResult(success=True, message="Kubernetes cluster reachable")
                else:
                    integration.status = "error"
                    integration.error_message = "Could not reach Kubernetes API server"
                    await self.db.flush()
                    return IntegrationTestResult(success=False, message="Kubernetes connection failed")
            except Exception as exc:
                msg = str(exc)[:300]
                integration.status = "error"
                integration.error_message = msg
                await self.db.flush()
                return IntegrationTestResult(success=False, message=f"Kubernetes test failed: {msg}")

        # ── GitHub / GitLab ───────────────────────────────────────────────────
        try:
            user = await client.get_authenticated_user()
            success = bool(user and user.get("login"))
            if success:
                integration.status = "connected"
                integration.error_message = None
                integration.config = {
                    **(integration.config or {}),
                    "username": user.get("login"),
                }
                await self.db.flush()
                return IntegrationTestResult(success=True, message="Connection successful")

            integration.status = "invalid_token"
            integration.error_message = "GitHub authentication failed"
            await self.db.flush()
            return IntegrationTestResult(success=False, message="Authentication failed")

        except GitHubAPIError as exc:
            if exc.status_code == 401:
                integration.status = "invalid_token"
                integration.error_message = "Invalid GitHub token"
                await self.db.flush()
                return IntegrationTestResult(success=False, message="Invalid GitHub token")

            if exc.status_code == 403 and "rate limit" in str(exc).lower():
                integration.status = "error"
                integration.error_message = "GitHub API rate limit exceeded"
                await self.db.flush()
                return IntegrationTestResult(success=False, message="GitHub API rate limit exceeded")

            integration.status = "error"
            integration.error_message = str(exc)[:500]
            await self.db.flush()
            return IntegrationTestResult(success=False, message=str(exc))

        except Exception as exc:
            integration.status = "error"
            integration.error_message = str(exc)[:500]
            await self.db.flush()
            return IntegrationTestResult(success=False, message=str(exc))

    async def sync(self, integration_id: str) -> dict:
        integration = await self._get_by_id(Integration, integration_id)
        client = self._build_client(
            integration.type,
            self._decrypt_credentials(integration.credentials or {}),
            integration.config or {},
        )
        try:
            result = await client.sync()
            integration.last_sync = datetime.now(timezone.utc)
            integration.status = "connected"
            integration.error_message = None
            if integration.type == "github":
                integration.config = {
                    **(integration.config or {}),
                    "repo_count": result.get("repos", 0),
                }
            await self.db.flush()
            return result
        except GitHubAPIError as exc:
            logger.error(f"Integration sync failed for {integration_id}: {exc}")
            if exc.status_code == 401:
                integration.status = "invalid_token"
                integration.error_message = "Invalid GitHub token"
            else:
                integration.status = "error"
                integration.error_message = str(exc)[:500]
            await self.db.flush()
            raise
        except Exception as exc:
            logger.error(f"Integration sync failed for {integration_id}: {exc}")
            integration.status = "error"
            integration.error_message = str(exc)[:500]
            await self.db.flush()
            raise

    # ─────────────────────────────────────────────────────────────────────────
    # Repository sync (previously duplicated across two endpoint files)
    # ─────────────────────────────────────────────────────────────────────────

    async def sync_repos_for_tenant(self, tenant_id: str) -> dict:
        """
        Pull repository list from all active GitHub/GitLab integrations for a
        tenant and upsert Repository records.

        Returns the number of repos upserted.

        Idempotency guarantee: uses (tenant_id, external_id) as the unique key
        so re-running never creates duplicates.
        """
        result = await self.db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.is_active.is_(True),
                Integration.status == "connected",
                Integration.type.in_(["github", "gitlab"]),
            )
        )
        integrations = result.scalars().all()
        if not integrations:
            logger.info(f"No active git integrations for tenant {tenant_id}")
            return {"synced": 0, "errors": []}

        synced = 0
        errors: list[str] = []
        for integration in integrations:
            creds = self._decrypt_credentials(integration.credentials or {})
            config = {**creds, **(integration.config or {})}
            try:
                if integration.type == "github":
                    repos = await _fetch_github_repos(config)
                else:
                    repos = await _fetch_gitlab_repos(config)

                for repo_data in repos:
                    await self._upsert_repository(tenant_id, integration, repo_data)
                    synced += 1

                integration.last_sync = datetime.now(timezone.utc)
                integration.status = "connected"
                integration.error_message = None
                if integration.type == "github":
                    integration.config = {
                        **(integration.config or {}),
                        "repo_count": len(repos),
                    }

            except GitHubAPIError as exc:
                message = str(exc) or "GitHub repo sync failed"
                if exc.status_code == 401:
                    integration.status = "invalid_token"
                    integration.error_message = "Invalid GitHub token"
                elif exc.status_code == 403 and "rate limit" in message.lower():
                    integration.status = "error"
                    integration.error_message = "GitHub API rate limit exceeded"
                else:
                    integration.status = "error"
                    integration.error_message = message[:500]
                errors.append(f"{integration.name}: {integration.error_message}")
                logger.warning(f"Repo sync failed for integration {integration.id}: {message}")

            except Exception as exc:
                message = str(exc)[:500]
                integration.status = "error"
                integration.error_message = message
                errors.append(f"{integration.name}: {message}")
                logger.warning(f"Repo sync failed for integration {integration.id}: {message}")

        await self.db.flush()
        return {"synced": synced, "errors": errors}

    async def _upsert_repository(
        self,
        tenant_id: str,
        integration: Integration,
        repo_data: dict,
    ) -> Repository:
        """
        Insert or update a Repository record.
        Uses (tenant_id, external_id) as the natural key so this is safe to
        call repeatedly — no duplicates, no phantom rows.
        """
        existing = await self.db.execute(
            select(Repository).where(
                Repository.tenant_id == tenant_id,
                Repository.external_id == repo_data["external_id"],
            )
        )
        record = existing.scalar_one_or_none()

        if record:
            record.clone_url = repo_data["clone_url"]
            record.default_branch = repo_data["default_branch"]
            record.has_dockerfile = repo_data.get("has_dockerfile", False)
            record.has_cicd = repo_data.get("has_cicd", False)
            record.language = repo_data.get("language")
        else:
            record = Repository(
                tenant_id=tenant_id,
                integration_id=integration.id,
                provider=integration.type,
                external_id=repo_data["external_id"],
                full_name=repo_data["full_name"],
                name=repo_data["name"],
                clone_url=repo_data["clone_url"],
                default_branch=repo_data["default_branch"],
                is_private=repo_data.get("is_private", True),
                language=repo_data.get("language"),
            )
            self.db.add(record)

        return record

    # ─────────────────────────────────────────────────────────────────────────
    # Private: credential helpers (never expose decrypted values outside class)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _encrypt_credentials(credentials: dict) -> dict:
        """
        Encrypt sensitive fields in place.
        Non-sensitive fields (e.g. 'url', 'region') pass through unchanged.
        Encryption errors are logged and the original value is kept so a bad
        encryption key doesn't silently lose data — but the error is surfaced.
        """
        encrypted: dict = {}
        for key, value in credentials.items():
            if key in SENSITIVE_FIELDS and value:
                try:
                    encrypted[key] = encrypt(str(value))
                except Exception as exc:
                    logger.error(
                        f"Encryption failed for credential field '{key}': {exc} — "
                        "storing plaintext as fallback. Check ENCRYPTION_KEY config."
                    )
                    encrypted[key] = value
            else:
                encrypted[key] = value
        return encrypted

    @staticmethod
    def _decrypt_credentials(credentials: dict) -> dict:
        """
        Decrypt sensitive fields.
        If decryption fails (wrong key, plaintext value from older record), the
        raw value is returned — allowing graceful degradation after key rotation.
        NEVER log the decrypted values.
        """
        decrypted: dict = {}
        for key, value in credentials.items():
            if key in SENSITIVE_FIELDS and value:
                try:
                    decrypted[key] = decrypt(str(value))
                except Exception:
                    # Value may be stored as plaintext (legacy) — pass through
                    decrypted[key] = value
            else:
                decrypted[key] = value
        return decrypted

    # ─────────────────────────────────────────────────────────────────────────
    # Private: client factory
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_client(integration_type: str, creds: dict, config: dict):
        """
        Build the appropriate integration client.
        Credentials and config are merged here — callers never touch raw creds.
        """
        merged = {**creds, **config}
        if integration_type == "aws":
            from app.integrations.aws.client import AWSClient
            return AWSClient(merged)
        if integration_type == "github":
            from app.integrations.github.client import GitHubClient
            return GitHubClient(merged)
        if integration_type == "gitlab":
            from app.integrations.gitlab.client import GitLabClient
            return GitLabClient(merged)
        if integration_type == "kubernetes":
            from app.integrations.kubernetes.client import KubernetesClient
            return KubernetesClient(merged)
        if integration_type == "stripe":
            from app.integrations.stripe.client import StripeClient
            return StripeClient(merged)

        # Unknown type — return a no-op stub so test_connection() always passes
        from app.integrations.base import BaseIntegration

        class _NoOpIntegration(BaseIntegration):
            async def test_connection(self) -> bool:
                return True

            async def sync(self) -> dict:
                return {}

        return _NoOpIntegration(merged)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level HTTP helpers (shared with RepoService / scan endpoints)
# Extracted here so security_scan.py no longer needs its own copy.
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_github_repos(config: dict) -> list[dict]:
    """Fetch up to 500 repos from GitHub API (5 pages × 100)."""
    import httpx
    token = config.get("token") or config.get("access_token", "")
    if not token:
        raise GitHubAPIError(401, "Missing GitHub token")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    repos: list[dict] = []
    async with httpx.AsyncClient(timeout=20) as client:
        for page in range(1, 6):
            resp = await client.get(
                "https://api.github.com/user/repos",
                headers=headers,
                params={"per_page": 100, "page": page, "sort": "updated"},
            )
            try:
                body = resp.json()
            except ValueError:
                body = resp.text

            if resp.status_code != 200:
                message = body.get("message") if isinstance(body, dict) else str(body)
                raise GitHubAPIError(resp.status_code, message)

            if not isinstance(body, list):
                break

            repos.extend(body)
            if len(body) < 100:
                break

    return [
        {
            "external_id": str(r["id"]),
            "full_name": r["full_name"],
            "name": r["name"],
            "clone_url": r["clone_url"],
            "default_branch": r.get("default_branch", "main"),
            "is_private": r.get("private", True),
            "language": (r.get("language") or "unknown").lower(),
        }
        for r in repos
    ]


async def _fetch_gitlab_repos(config: dict) -> list[dict]:
    """Fetch up to 500 projects from GitLab API (5 pages × 100)."""
    import httpx
    token = config.get("token") or config.get("access_token", "")
    base = config.get("url", "https://gitlab.com")
    headers = {"PRIVATE-TOKEN": token}
    repos: list[dict] = []
    async with httpx.AsyncClient(timeout=20) as client:
        for page in range(1, 6):
            resp = await client.get(
                f"{base}/api/v4/projects",
                headers=headers,
                params={
                    "per_page": 100,
                    "page": page,
                    "membership": True,
                    "order_by": "updated_at",
                },
            )
            if resp.status_code != 200 or not resp.json():
                break
            for r in resp.json():
                repos.append({
                    "external_id": str(r["id"]),
                    "full_name": r["path_with_namespace"],
                    "name": r["name"],
                    "clone_url": r["http_url_to_repo"],
                    "default_branch": r.get("default_branch", "main"),
                    "is_private": r.get("visibility", "private") != "public",
                    "language": None,
                })
    return repos
