from app.integrations.github.client import GitHubClient, GITHUB_API


class GitHubActions(GitHubClient):
    async def list_workflows(self, owner: str, repo: str) -> list[dict]:
        try:
            import httpx
            headers = self._build_headers()
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows",
                    headers=headers,
                )
                return r.json().get("workflows", []) if r.status_code == 200 else []
        except Exception:
            return []

    async def list_runs(self, owner: str, repo: str, workflow_id: int) -> list[dict]:
        try:
            import httpx
            headers = self._build_headers()
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs",
                    headers=headers,
                )
                return r.json().get("workflow_runs", []) if r.status_code == 200 else []
        except Exception:
            return []
