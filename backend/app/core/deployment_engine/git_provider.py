"""
Git Provider — GitHub and GitLab API integration for the Deployment Engine.
Creates repos, pushes initial commits, creates branches.

All methods are graceful: they log and return None/False rather than raising
when the API token is missing or the call fails. The engine handles the result.
"""
from __future__ import annotations
import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Timeout for all GitHub/GitLab calls
_TIMEOUT = httpx.Timeout(30.0)


class GitHubProvider:
    """Thin async wrapper around the GitHub REST API v3."""

    BASE = "https://api.github.com"

    def __init__(self, token: str, org: Optional[str] = None):
        self.token = token
        self.org   = org
        self._headers = {
            "Authorization":        f"Bearer {token}",
            "Accept":               "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ── Repo lifecycle ────────────────────────────────────────────────────────

    async def create_repo(
        self,
        name:        str,
        description: str = "",
        private:     bool = True,
    ) -> Optional[dict]:
        """Create a GitHub repository. Returns the response JSON or None."""
        if self.org:
            url  = f"{self.BASE}/orgs/{self.org}/repos"
            body = {"name": name, "description": description, "private": private, "auto_init": False}
        else:
            url  = f"{self.BASE}/user/repos"
            body = {"name": name, "description": description, "private": private, "auto_init": False}

        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            try:
                r = await c.post(url, json=body, headers=self._headers)
                if r.status_code in (200, 201):
                    data = r.json()
                    logger.info(f"[git_provider] GitHub repo created: {data.get('full_name')}")
                    return data
                logger.warning(f"[git_provider] GitHub create_repo {r.status_code}: {r.text[:200]}")
                return None
            except Exception as exc:
                logger.error(f"[git_provider] GitHub create_repo error: {exc}")
                return None

    async def push_file(
        self,
        owner:   str,
        repo:    str,
        path:    str,
        content: str,
        message: str,
        branch:  str = "main",
        sha:     Optional[str] = None,
    ) -> bool:
        """Create or update a single file in the repo."""
        url  = f"{self.BASE}/repos/{owner}/{repo}/contents/{path}"
        body: dict = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch":  branch,
        }
        if sha:
            body["sha"] = sha

        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            try:
                r = await c.put(url, json=body, headers=self._headers)
                ok = r.status_code in (200, 201)
                if not ok:
                    logger.warning(f"[git_provider] push_file {path} → {r.status_code}: {r.text[:200]}")
                return ok
            except Exception as exc:
                logger.error(f"[git_provider] push_file error: {exc}")
                return False

    async def push_files_batch(
        self,
        owner:   str,
        repo:    str,
        files:   list[tuple[str, str]],   # [(path, content), ...]
        branch:  str = "main",
        message: str = "chore: initial commit by UniOps Deployment Engine",
    ) -> int:
        """Push multiple files sequentially. Returns count of successes."""
        ok = 0
        for path, content in files:
            if await self.push_file(owner, repo, path, content, message=message, branch=branch):
                ok += 1
        logger.info(f"[git_provider] pushed {ok}/{len(files)} files to {owner}/{repo}")
        return ok

    async def get_file_sha(self, owner: str, repo: str, path: str, branch: str = "main") -> Optional[str]:
        url = f"{self.BASE}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            try:
                r = await c.get(url, headers=self._headers)
                return r.json().get("sha") if r.status_code == 200 else None
            except Exception:
                return None

    async def get_authenticated_user(self) -> Optional[str]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            try:
                r = await c.get(f"{self.BASE}/user", headers=self._headers)
                return r.json().get("login") if r.status_code == 200 else None
            except Exception:
                return None

    async def repo_exists(self, owner: str, repo: str) -> bool:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            try:
                r = await c.get(f"{self.BASE}/repos/{owner}/{repo}", headers=self._headers)
                return r.status_code == 200
            except Exception:
                return False


class GitLabProvider:
    """Thin async wrapper around the GitLab REST API v4."""

    BASE = "https://gitlab.com/api/v4"

    def __init__(self, token: str, base_url: str = "https://gitlab.com"):
        self.token    = token
        self.BASE     = f"{base_url.rstrip('/')}/api/v4"
        self._headers = {"PRIVATE-TOKEN": token}

    async def create_repo(
        self,
        name:        str,
        namespace:   Optional[int] = None,
        description: str = "",
        visibility:  str = "private",
    ) -> Optional[dict]:
        body: dict = {"name": name, "description": description, "visibility": visibility, "initialize_with_readme": False}
        if namespace:
            body["namespace_id"] = namespace

        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            try:
                r = await c.post(f"{self.BASE}/projects", json=body, headers=self._headers)
                if r.status_code in (200, 201):
                    data = r.json()
                    logger.info(f"[git_provider] GitLab repo created: {data.get('path_with_namespace')}")
                    return data
                logger.warning(f"[git_provider] GitLab create_repo {r.status_code}: {r.text[:200]}")
                return None
            except Exception as exc:
                logger.error(f"[git_provider] GitLab create_repo error: {exc}")
                return None

    async def push_file(self, project_id: int | str, path: str, content: str, message: str, branch: str = "main") -> bool:
        url  = f"{self.BASE}/projects/{project_id}/repository/files/{path.replace('/', '%2F')}"
        body = {"branch": branch, "content": content, "commit_message": message}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            try:
                # Try create first, then update on 400
                r = await c.post(url, json=body, headers=self._headers)
                if r.status_code in (200, 201):
                    return True
                if r.status_code == 400:
                    r2 = await c.put(url, json=body, headers=self._headers)
                    return r2.status_code in (200, 201)
                return False
            except Exception as exc:
                logger.error(f"[git_provider] GitLab push_file error: {exc}")
                return False


def get_provider_from_integration(integration: dict) -> Optional[GitHubProvider | GitLabProvider]:
    """
    Factory: given an integration dict (from DB), return the appropriate provider.
    Returns None when the integration is missing or has no token.
    """
    if not integration:
        return None
    provider = integration.get("provider", "")
    creds    = integration.get("credentials") or {}
    token    = creds.get("token") or creds.get("access_token") or ""
    if not token:
        return None

    if provider == "github":
        org = (integration.get("config") or {}).get("org")
        return GitHubProvider(token, org=org)
    if provider == "gitlab":
        base_url = (integration.get("config") or {}).get("base_url", "https://gitlab.com")
        return GitLabProvider(token, base_url=base_url)

    return None
