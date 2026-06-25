"""
Jira Cloud REST API client (production-ready).

Required env vars:
  JIRA_BASE_URL  — e.g. https://mycompany.atlassian.net
  JIRA_EMAIL     — Atlassian account email
  JIRA_API_TOKEN — API token from id.atlassian.com/manage-profile/security/api-tokens
"""
from __future__ import annotations
import os
import base64
import httpx
from app.utils.logger import logger


def _auth_header() -> str:
    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    encoded = base64.b64encode(f"{email}:{token}".encode()).decode()
    return f"Basic {encoded}"


def _base_url() -> str:
    return os.environ.get("JIRA_BASE_URL", "").rstrip("/")


def _configured() -> bool:
    return bool(_base_url() and os.environ.get("JIRA_EMAIL") and os.environ.get("JIRA_API_TOKEN"))


async def create_issue(
    *,
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Bug",
    priority: str = "High",
    labels: list[str] | None = None,
    extra_fields: dict | None = None,
) -> dict:
    """Create a Jira issue. Returns {external_id, ticket_key, ticket_url, ticket_title, provider_meta}."""
    if not _configured():
        raise ValueError("Jira not configured. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN.")

    payload: dict = {
        "fields": {
            "project":   {"key": project_key},
            "summary":   summary,
            "issuetype": {"name": issue_type},
            "priority":  {"name": priority},
            "description": {
                "type":    "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            },
        }
    }
    if labels:
        payload["fields"]["labels"] = labels
    if extra_fields:
        payload["fields"].update(extra_fields)

    headers = {
        "Authorization": _auth_header(),
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{_base_url()}/rest/api/3/issue", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    key      = data["key"]
    issue_id = data["id"]
    url      = f"{_base_url()}/browse/{key}"
    logger.info(f"[jira:create] key={key}")
    return {"external_id": issue_id, "ticket_key": key, "ticket_url": url, "ticket_title": summary, "provider_meta": data}


async def get_issue(ticket_key: str) -> dict:
    """Fetch Jira issue status. Returns {ticket_status, assignee, provider_meta}."""
    if not _configured():
        raise ValueError("Jira not configured.")

    headers = {"Authorization": _auth_header(), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{_base_url()}/rest/api/3/issue/{ticket_key}", headers=headers)
        resp.raise_for_status()
        data = resp.json()

    fields   = data.get("fields", {})
    status   = fields.get("status", {}).get("name", "unknown")
    assignee = (fields.get("assignee") or {}).get("displayName")
    return {"ticket_status": status, "assignee": assignee, "provider_meta": data}


def is_configured() -> bool:
    return _configured()
