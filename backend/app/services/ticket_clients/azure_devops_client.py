"""
Azure DevOps Work Items REST API client (production-ready).

Required env vars:
  ADO_ORG      — e.g. mycompany
  ADO_PROJECT  — e.g. MyProject
  ADO_PAT      — Personal Access Token (Base64 encoded with : prefix)
"""
from __future__ import annotations
import os
import base64
from typing import Optional
import httpx
from app.utils.logger import logger

ADO_API_VERSION = "7.1-preview.3"


def _auth_header() -> str:
    pat   = os.environ.get("ADO_PAT", "")
    token = base64.b64encode(f":{pat}".encode()).decode()
    return f"Basic {token}"


def _base_url() -> str:
    org     = os.environ.get("ADO_ORG", "").strip("/")
    project = os.environ.get("ADO_PROJECT", "").strip("/")
    return f"https://dev.azure.com/{org}/{project}"


def _configured() -> bool:
    return bool(
        os.environ.get("ADO_ORG")
        and os.environ.get("ADO_PROJECT")
        and os.environ.get("ADO_PAT")
    )


SEVERITY_MAP = {
    "critical": "1 - Critical",
    "high":     "2 - High",
    "medium":   "3 - Medium",
    "low":      "4 - Low",
}

PRIORITY_MAP = {
    "critical": 1,
    "high":     2,
    "medium":   3,
    "low":      4,
}


async def create_work_item(
    *,
    title: str,
    description: str,
    work_item_type: str = "Bug",
    severity: str = "high",
    tags: list[str] | None = None,
    area_path: str | None = None,
) -> dict:
    """Create an ADO work item and return {external_id, ticket_key, ticket_url, ticket_title}."""
    if not _configured():
        raise ValueError("Azure DevOps not configured. Set ADO_ORG, ADO_PROJECT, ADO_PAT.")

    ops = [
        {"op": "add", "path": "/fields/System.Title",       "value": title},
        {"op": "add", "path": "/fields/System.Description", "value": f"<p>{description}</p>"},
        {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": PRIORITY_MAP.get(severity.lower(), 2)},
        {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Severity", "value": SEVERITY_MAP.get(severity.lower(), "2 - High")},
    ]
    if tags:
        ops.append({"op": "add", "path": "/fields/System.Tags", "value": "; ".join(tags)})
    if area_path:
        ops.append({"op": "add", "path": "/fields/System.AreaPath", "value": area_path})

    url = f"{_base_url()}/_apis/wit/workitems/${work_item_type}?api-version={ADO_API_VERSION}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=ops, headers={
            "Authorization": _auth_header(),
            "Content-Type":  "application/json-patch+json",
            "Accept":        "application/json",
        })
        resp.raise_for_status()
        data = resp.json()

    item_id  = data["id"]
    org      = os.environ.get("ADO_ORG", "")
    project  = os.environ.get("ADO_PROJECT", "")
    item_url = f"https://dev.azure.com/{org}/{project}/_workitems/edit/{item_id}"
    key      = f"#{item_id}"
    logger.info(f"[ado:create] id={item_id} url={item_url}")
    return {
        "external_id":  str(item_id),
        "ticket_key":   key,
        "ticket_url":   item_url,
        "ticket_title": title,
        "provider_meta": data,
    }


async def get_work_item(item_id: str) -> dict:
    """Fetch an ADO work item status."""
    if not _configured():
        raise ValueError("Azure DevOps not configured.")

    url = f"{_base_url()}/_apis/wit/workitems/{item_id}?api-version={ADO_API_VERSION}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers={
            "Authorization": _auth_header(),
            "Accept":        "application/json",
        })
        resp.raise_for_status()
        data = resp.json()

    fields = data.get("fields", {})
    state  = fields.get("System.State", "unknown")
    assignee = (fields.get("System.AssignedTo") or {}).get("displayName")
    return {"ticket_status": state, "assignee": assignee, "provider_meta": data}


def is_configured() -> bool:
    return _configured()
