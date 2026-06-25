"""
Linear GraphQL API client (production-ready).

Required env vars:
  LINEAR_API_KEY  — personal API key from linear.app/settings/api
  LINEAR_TEAM_ID  — (optional) default team UUID; can be overridden per request
"""
from __future__ import annotations
import os
from typing import Optional
import httpx
from app.utils.logger import logger

LINEAR_GQL = "https://api.linear.app/graphql"

PRIORITY_MAP = {
    "critical": 1,
    "high":     2,
    "medium":   3,
    "low":      4,
}


def _headers() -> dict:
    return {
        "Authorization": os.environ.get("LINEAR_API_KEY", ""),
        "Content-Type":  "application/json",
    }


def _configured() -> bool:
    return bool(os.environ.get("LINEAR_API_KEY"))


async def _gql(query: str, variables: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            LINEAR_GQL,
            json={"query": query, "variables": variables},
            headers=_headers(),
        )
        resp.raise_for_status()
        body = resp.json()
    if "errors" in body:
        raise ValueError(f"Linear GraphQL error: {body['errors']}")
    return body["data"]


async def get_teams() -> list[dict]:
    """Return available teams — used to resolve team_id from name."""
    data = await _gql("query { teams { nodes { id name key } } }", {})
    return data["teams"]["nodes"]


async def create_issue(
    *,
    team_id: str,
    title: str,
    description: str,
    priority: str = "high",
    label_names: list[str] | None = None,
) -> dict:
    """Create a Linear issue and return {external_id, ticket_key, ticket_url, ticket_title}."""
    if not _configured():
        raise ValueError("Linear not configured. Set LINEAR_API_KEY.")

    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue {
          id
          identifier
          title
          url
          state { name }
        }
      }
    }
    """
    inp: dict = {
        "teamId":      team_id,
        "title":       title,
        "description": description,
        "priority":    PRIORITY_MAP.get(priority.lower(), 2),
    }
    data    = await _gql(mutation, {"input": inp})
    result  = data["issueCreate"]
    if not result["success"]:
        raise ValueError("Linear issueCreate returned success=false")

    issue = result["issue"]
    logger.info(f"[linear:create] id={issue['identifier']} url={issue['url']}")
    return {
        "external_id":  issue["id"],
        "ticket_key":   issue["identifier"],
        "ticket_url":   issue["url"],
        "ticket_title": issue["title"],
        "provider_meta": issue,
    }


async def get_issue(issue_id: str) -> dict:
    """Fetch a Linear issue status."""
    if not _configured():
        raise ValueError("Linear not configured.")

    query = """
    query GetIssue($id: String!) {
      issue(id: $id) {
        id
        identifier
        title
        url
        state { name }
        assignee { name }
      }
    }
    """
    data  = await _gql(query, {"id": issue_id})
    issue = data["issue"]
    return {
        "ticket_status": (issue.get("state") or {}).get("name", "unknown"),
        "assignee":      (issue.get("assignee") or {}).get("name"),
        "provider_meta": issue,
    }


def is_configured() -> bool:
    return _configured()
