from __future__ import annotations
"""GitHub API client — repos, workflows, runs, Dependabot alerts."""
import httpx
from typing import Optional
from app.utils.logger import logger

GITHUB_API = "https://api.github.com"


class GitHubAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class GitHubClient:
    def __init__(self, config: dict):
        self.token = (config.get("token") or config.get("access_token") or "").strip()

    def _build_headers(self) -> dict:
        if not self.token:
            raise GitHubAPIError(401, "Missing GitHub token")

        return {
            "Authorization": f"Bearer {self.token}",
            "Accept":        "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _get(self, path: str, params: dict = None) -> dict | list:
        try:
            headers = self._build_headers()
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"{GITHUB_API}{path}", headers=headers, params=params)

            try:
                body = r.json()
            except ValueError:
                body = r.text

            if r.status_code == 200:
                return body

            message = body.get("message") if isinstance(body, dict) else str(body)
            logger.warning(f"GitHub API {path} → {r.status_code}: {message}")
            raise GitHubAPIError(r.status_code, message)
        except httpx.RequestError as e:
            logger.warning(f"GitHub API {path} failed: {e}")
            raise GitHubAPIError(0, str(e))

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def test_connection(self) -> bool:
        data = await self._get("/user")
        return bool(data and data.get("login"))

    async def get_authenticated_user(self) -> Optional[dict]:
        return await self._get("/user")

    # ── Repos ─────────────────────────────────────────────────────────────────

    async def list_repos(self, per_page: int = 30) -> list[dict]:
        """List repos the token has access to."""
        repos: list[dict] = []
        page = 1
        while True:
            data = await self._get(
                "/user/repos",
                {"per_page": per_page, "page": page, "sort": "updated"},
            )
            if not isinstance(data, list) or not data:
                break

            repos.extend(data)
            if len(data) < per_page:
                break
            page += 1
            if page > 5:
                break

        return [
            {
                "full_name":      r["full_name"],
                "owner":          r["owner"]["login"],
                "name":           r["name"],
                "default_branch": r.get("default_branch", "main"),
                "private":        r.get("private", False),
                "updated_at":     r.get("updated_at"),
                "html_url":       r.get("html_url"),
            }
            for r in repos
        ]

    async def list_org_repos(self, org: str, per_page: int = 50) -> list[dict]:
        data = await self._get(f"/orgs/{org}/repos", {"per_page": per_page, "sort": "updated"})
        if isinstance(data, list):
            return [
                {
                    "full_name":      r["full_name"],
                    "owner":          org,
                    "name":           r["name"],
                    "default_branch": r.get("default_branch", "main"),
                    "private":        r.get("private", False),
                    "html_url":       r.get("html_url"),
                }
                for r in data
            ]
        return []

    # ── Workflows ─────────────────────────────────────────────────────────────

    async def list_workflows(self, owner: str, repo: str) -> list[dict]:
        data = await self._get(f"/repos/{owner}/{repo}/actions/workflows")
        if data:
            return [
                {
                    "id":    w["id"],
                    "name":  w["name"],
                    "path":  w.get("path", ""),
                    "state": w.get("state", "active"),
                }
                for w in data.get("workflows", [])
                if w.get("state") == "active"
            ]
        return []

    async def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: int | str = None,
        per_page: int = 20,
        branch: str = None,
    ) -> list[dict]:
        """Fetch recent workflow runs — optionally filter by workflow or branch."""
        path   = f"/repos/{owner}/{repo}/actions/runs"
        params = {"per_page": per_page}
        if workflow_id:
            path   = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        if branch:
            params["branch"] = branch

        data = await self._get(path, params)
        if not data:
            return []

        runs = []
        for r in data.get("workflow_runs", []):
            # Map GitHub status/conclusion → UniOps status
            status = _map_status(r.get("status"), r.get("conclusion"))

            # Duration in seconds
            duration = None
            if r.get("run_started_at") and r.get("updated_at") and r.get("status") == "completed":
                from datetime import datetime
                try:
                    start = datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
                    end   = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                    duration = max(0, int((end - start).total_seconds()))
                except Exception:
                    pass

            runs.append({
                "id":             str(r["id"]),
                "name":           r.get("name", r.get("display_title", "Workflow")),
                "workflow_name":  r.get("name", ""),
                "repository":     f"{owner}/{repo}",
                "branch":         r.get("head_branch", "main"),
                "status":         status,
                "conclusion":     r.get("conclusion"),
                "commit_sha":     r.get("head_sha", "")[:7],
                "commit_message": r.get("display_title", r.get("head_commit", {}).get("message", "")),
                "triggered_by":   r.get("triggering_actor", {}).get("login", ""),
                "started_at":     r.get("run_started_at"),
                "finished_at":    r.get("updated_at") if r.get("status") == "completed" else None,
                "duration":       duration,
                "logs_url":       r.get("html_url"),
                "run_number":     r.get("run_number"),
                "event":          r.get("event"),
            })
        return runs

    async def get_run_jobs(self, owner: str, repo: str, run_id: int) -> list[dict]:
        data = await self._get(f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs")
        if not data:
            return []
        return [
            {
                "id":         j["id"],
                "name":       j["name"],
                "status":     _map_status(j.get("status"), j.get("conclusion")),
                "started_at": j.get("started_at"),
                "completed_at": j.get("completed_at"),
            }
            for j in data.get("jobs", [])
        ]

    # ── Security ──────────────────────────────────────────────────────────────

    async def list_dependabot_alerts(self, owner: str, repo: str) -> list[dict]:
        """Dependabot vulnerability alerts → UniOps vulnerabilities."""
        data = await self._get(
            f"/repos/{owner}/{repo}/dependabot/alerts",
            {"state": "open", "per_page": 50},
        )
        if not isinstance(data, list):
            return []

        return [
            {
                "number":     a.get("number"),
                "state":      a.get("state", "open"),
                "severity":   _map_severity(a.get("security_advisory", {}).get("severity")),
                "title":      a.get("security_advisory", {}).get("summary", ""),
                "description": a.get("security_advisory", {}).get("description", ""),
                "cve_id":     a.get("security_advisory", {}).get("cve_id"),
                "cvss":       a.get("security_advisory", {}).get("cvss", {}).get("score"),
                "package":    a.get("dependency", {}).get("package", {}).get("name"),
                "ecosystem":  a.get("dependency", {}).get("package", {}).get("ecosystem"),
                "version":    a.get("dependency", {}).get("manifest_path"),
                "fixed_in":   _first_fixed_version(a.get("security_advisory", {})),
                "html_url":   a.get("html_url"),
            }
            for a in data
        ]

    async def list_code_scanning_alerts(self, owner: str, repo: str) -> list[dict]:
        """Code scanning (CodeQL) alerts → UniOps threats."""
        data = await self._get(
            f"/repos/{owner}/{repo}/code-scanning/alerts",
            {"state": "open", "per_page": 50},
        )
        if not isinstance(data, list):
            return []
        return [
            {
                "number":   a.get("number"),
                "rule_id":  a.get("rule", {}).get("id"),
                "severity": _map_severity(a.get("rule", {}).get("severity")),
                "title":    a.get("rule", {}).get("name", "Code Scanning Alert"),
                "description": a.get("rule", {}).get("description", ""),
                "location": a.get("most_recent_instance", {}).get("location", {}),
                "html_url": a.get("html_url"),
            }
            for a in data
        ]

    async def rerun_workflow_run(self, owner: str, repo: str, run_id: int | str) -> dict:
        """
        Re-run ALL jobs in a workflow run (including successful ones).
        GitHub API: POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun
        Requires: workflow write permission on the token.
        Returns: {"success": bool, "run_id": int, "error": str | None}
        """
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(
                    f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/rerun",
                    headers=self._headers,
                )
            # 201 = queued, 403 = no permission, 409 = already running
            if r.status_code in (200, 201):
                logger.info(f"GitHub rerun queued: {owner}/{repo} run={run_id}")
                return {"success": True, "run_id": int(run_id)}

            # Parse GitHub error body
            try:
                body = r.json()
                msg = body.get("message", f"HTTP {r.status_code}")
            except Exception:
                msg = f"HTTP {r.status_code}"

            logger.warning(f"GitHub rerun failed ({owner}/{repo} run={run_id}): {msg}")
            return {"success": False, "run_id": int(run_id), "error": msg}

        except Exception as e:
            logger.error(f"GitHub rerun exception ({owner}/{repo} run={run_id}): {e}")
            return {"success": False, "run_id": int(run_id), "error": str(e)}

    async def rerun_failed_jobs(self, owner: str, repo: str, run_id: int | str) -> dict:
        """
        Re-run only FAILED jobs in a workflow run.
        GitHub API: POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs
        More efficient than full rerun — skips already-successful jobs.
        """
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(
                    f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs",
                    headers=self._headers,
                )
            if r.status_code in (200, 201):
                logger.info(f"GitHub rerun-failed-jobs queued: {owner}/{repo} run={run_id}")
                return {"success": True, "run_id": int(run_id)}

            try:
                msg = r.json().get("message", f"HTTP {r.status_code}")
            except Exception:
                msg = f"HTTP {r.status_code}"
            return {"success": False, "run_id": int(run_id), "error": msg}

        except Exception as e:
            return {"success": False, "run_id": int(run_id), "error": str(e)}

    async def cancel_workflow_run(self, owner: str, repo: str, run_id: int | str) -> dict:
        """
        Cancel a running workflow run.
        GitHub API: POST /repos/{owner}/{repo}/actions/runs/{run_id}/cancel
        Returns 202 Accepted with empty body on success.
        """
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(
                    f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/cancel",
                    headers=self._headers,
                )
            if r.status_code in (202, 200):
                logger.info(f"GitHub cancel accepted: {owner}/{repo} run={run_id}")
                return {"success": True, "run_id": int(run_id)}
            try:
                msg = r.json().get("message", f"HTTP {r.status_code}")
            except Exception:
                msg = f"HTTP {r.status_code}"
            logger.warning(f"GitHub cancel failed ({owner}/{repo} run={run_id}): {msg}")
            return {"success": False, "run_id": int(run_id), "error": msg}
        except Exception as e:
            logger.error(f"GitHub cancel exception ({owner}/{repo} run={run_id}): {e}")
            return {"success": False, "run_id": int(run_id), "error": str(e)}

    async def get_workflow_run(self, owner: str, repo: str, run_id: int | str) -> dict | None:
        """Fetch a single workflow run — used to poll status after rerun."""
        return await self._get(f"/repos/{owner}/{repo}/actions/runs/{run_id}")

    async def sync(self) -> dict:
        repos = await self.list_repos(per_page=100)
        return {"repos": len(repos), "status": "synced"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _map_status(status: str | None, conclusion: str | None) -> str:
    if status == "completed":
        return {
            "success":   "success",
            "failure":   "failed",
            "cancelled": "cancelled",
            "skipped":   "skipped",
            "timed_out": "failed",
            "action_required": "failed",
        }.get(conclusion or "", "failed")
    return {
        "in_progress": "running",
        "queued":      "queued",
        "waiting":     "queued",
        "requested":   "queued",
    }.get(status or "", "unknown")


def _map_severity(sev: str | None) -> str:
    return {
        "critical": "critical",
        "high":     "high",
        "medium":   "medium",
        "moderate": "medium",
        "low":      "low",
        "warning":  "low",
    }.get((sev or "").lower(), "medium")


def _first_fixed_version(advisory: dict) -> str | None:
    for vuln in advisory.get("vulnerabilities", []):
        fixed = vuln.get("first_patched_version", {})
        if fixed and fixed.get("identifier"):
            return fixed["identifier"]
    return None
