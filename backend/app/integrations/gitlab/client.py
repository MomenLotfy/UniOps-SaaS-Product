"""GitLab integration client — API v4 wrapper for pipelines and repositories."""
from typing import Optional
import httpx
from app.integrations.base import BaseIntegration
from app.utils.logger import logger


class GitLabClient(BaseIntegration):
    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get("url", "https://gitlab.com")
        self.token = config.get("token", "")
        self._headers = {"PRIVATE-TOKEN": self.token, "Content-Type": "application/json"}

    async def test_connection(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/api/v4/user", headers=self._headers)
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"GitLab connection test failed: {e}")
            return False

    async def sync(self) -> dict:
        projects = await self.list_projects()
        return {"projects_synced": len(projects)}

    async def list_projects(self, per_page: int = 50) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v4/projects",
                    headers=self._headers,
                    params={"per_page": per_page, "membership": True, "order_by": "updated_at"},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"GitLab list projects failed: {e}")
            return []

    async def list_pipelines(self, project_id: str, per_page: int = 20) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v4/projects/{project_id}/pipelines",
                    headers=self._headers,
                    params={"per_page": per_page, "order_by": "updated_at", "sort": "desc"},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"GitLab list pipelines failed for project {project_id}: {e}")
            return []

    async def get_pipeline(self, project_id: str, pipeline_id: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}",
                    headers=self._headers,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"GitLab get pipeline failed: {e}")
            return None

    async def retry_pipeline(self, project_id: str, pipeline_id: str) -> dict:
        """
        Retry a GitLab pipeline — creates a new pipeline run with same ref/SHA.
        GitLab API: POST /projects/{id}/pipelines/{pipeline_id}/retry
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/retry",
                    headers=self._headers,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info(f"GitLab pipeline retried: project={project_id} new_id={data.get('id')}")
                    return {
                        "success":      True,
                        "new_run_id":   str(data.get("id", "")),
                        "status":       data.get("status", "pending"),
                        "web_url":      data.get("web_url"),
                    }
                try:
                    msg = resp.json().get("message", f"HTTP {resp.status_code}")
                except Exception:
                    msg = f"HTTP {resp.status_code}"
                logger.warning(f"GitLab retry failed (project={project_id}, pipeline={pipeline_id}): {msg}")
                return {"success": False, "error": msg}
        except Exception as e:
            logger.error(f"GitLab retry_pipeline exception: {e}")
            return {"success": False, "error": str(e)}

    async def cancel_pipeline(self, project_id: str, pipeline_id: str) -> dict:
        """
        Cancel a running GitLab pipeline.
        GitLab API: POST /projects/{id}/pipelines/{pipeline_id}/cancel
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/cancel",
                    headers=self._headers,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info(f"GitLab pipeline cancelled: project={project_id} id={pipeline_id}")
                    return {"success": True, "status": data.get("status", "cancelled")}
                try:
                    msg = resp.json().get("message", f"HTTP {resp.status_code}")
                except Exception:
                    msg = f"HTTP {resp.status_code}"
                return {"success": False, "error": msg}
        except Exception as e:
            logger.error(f"GitLab cancel_pipeline exception: {e}")
            return {"success": False, "error": str(e)}

    async def get_pipeline_jobs(self, project_id: str, pipeline_id: str) -> list[dict]:
        """Fetch all jobs for a GitLab pipeline."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs",
                    headers=self._headers,
                    params={"per_page": 50},
                )
                if resp.status_code != 200:
                    return []
                return [
                    {
                        "id":           str(j["id"]),
                        "name":         j.get("name", ""),
                        "stage":        j.get("stage", ""),
                        "status":       _map_gitlab_status(j.get("status", "")),
                        "started_at":   j.get("started_at"),
                        "finished_at":  j.get("finished_at"),
                        "duration":     j.get("duration"),
                        "web_url":      j.get("web_url"),
                        "allow_failure": j.get("allow_failure", False),
                    }
                    for j in resp.json()
                ]
        except Exception as e:
            logger.error(f"GitLab get_pipeline_jobs failed: {e}")
            return []

    async def trigger_pipeline(self, project_id: str, ref: str, variables: dict = None) -> Optional[dict]:
        try:
            payload = {"ref": ref, "variables": [{"key": k, "value": v} for k, v in (variables or {}).items()]}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v4/projects/{project_id}/pipeline",
                    headers=self._headers,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"GitLab trigger pipeline failed: {e}")
            return None


def _map_gitlab_status(status: str) -> str:
    return {
        "created":   "pending",
        "pending":   "pending",
        "running":   "running",
        "success":   "success",
        "failed":    "failed",
        "canceled":  "cancelled",
        "skipped":   "skipped",
        "manual":    "pending",
    }.get(status, "unknown")
