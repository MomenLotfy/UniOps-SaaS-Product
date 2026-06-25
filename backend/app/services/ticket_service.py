"""
Ticket service — dispatches to Jira / Linear / Azure DevOps.
Stores results in security_tickets table.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_ticket import SecurityTicket
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.services.ticket_clients import jira_client, linear_client, azure_devops_client
from app.utils.logger import logger

Provider = Literal["jira", "linear", "azure_devops"]

SEVERITY_TO_PRIORITY = {
    "critical": "Highest",
    "high":     "High",
    "medium":   "Medium",
    "low":      "Low",
}


def _providers_status() -> dict:
    return {
        "jira":          jira_client.is_configured(),
        "linear":        linear_client.is_configured(),
        "azure_devops":  azure_devops_client.is_configured(),
    }


class TicketService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ticket ─────────────────────────────────────────────────────────

    async def create_ticket(
        self,
        tenant_id:   str,
        created_by:  str,
        entity_type: str,
        entity_id:   str,
        provider:    Provider,
        title:       str,
        description: str,
        severity:    str = "high",
        # Provider-specific options
        jira_project_key:    str | None = None,
        jira_issue_type:     str        = "Bug",
        linear_team_id:      str | None = None,
        ado_work_item_type:  str        = "Bug",
        extra: dict | None = None,
    ) -> dict:
        priority = SEVERITY_TO_PRIORITY.get(severity.lower(), "High")
        result: dict

        if provider == "jira":
            if not jira_project_key:
                raise ValueError("jira_project_key is required for Jira tickets")
            result = await jira_client.create_issue(
                project_key=jira_project_key,
                summary=title,
                description=description,
                issue_type=jira_issue_type,
                priority=priority,
                labels=["uniops-security", entity_type],
            )

        elif provider == "linear":
            team_id = linear_team_id or ""
            if not team_id:
                teams = await linear_client.get_teams()
                if not teams:
                    raise ValueError("No Linear teams found. Set LINEAR_TEAM_ID or configure workspace.")
                team_id = teams[0]["id"]
            result = await linear_client.create_issue(
                team_id=team_id,
                title=title,
                description=description,
                priority=severity,
                label_names=["security", entity_type],
            )

        elif provider == "azure_devops":
            result = await azure_devops_client.create_work_item(
                title=title,
                description=description,
                work_item_type=ado_work_item_type,
                severity=severity,
                tags=["uniops-security", entity_type],
            )

        else:
            raise ValueError(f"Unknown provider: {provider}")

        ticket = SecurityTicket(
            tenant_id=    tenant_id,
            created_by=   created_by,
            entity_type=  entity_type,
            entity_id=    entity_id,
            provider=     provider,
            external_id=  result["external_id"],
            ticket_key=   result["ticket_key"],
            ticket_url=   result["ticket_url"],
            ticket_title= result["ticket_title"],
            ticket_status="open",
            link_type=    "created",
            synced_at=    datetime.now(timezone.utc),
            provider_meta=result.get("provider_meta", {}),
        )
        self.db.add(ticket)
        await self.db.commit()
        logger.info(f"[ticket:create] provider={provider} key={result['ticket_key']} entity={entity_type}/{entity_id}")
        return _ticket_dict(ticket)

    # ── Link existing ticket ──────────────────────────────────────────────────

    async def link_ticket(
        self,
        tenant_id:    str,
        created_by:   str,
        entity_type:  str,
        entity_id:    str,
        provider:     Provider,
        ticket_key:   str,
        ticket_url:   str,
        ticket_title: str = "",
    ) -> dict:
        ticket = SecurityTicket(
            tenant_id=    tenant_id,
            created_by=   created_by,
            entity_type=  entity_type,
            entity_id=    entity_id,
            provider=     provider,
            external_id=  ticket_key,
            ticket_key=   ticket_key,
            ticket_url=   ticket_url,
            ticket_title= ticket_title,
            ticket_status="linked",
            link_type=    "linked",
        )
        self.db.add(ticket)
        await self.db.commit()
        # Immediately sync status from provider
        try:
            await self._sync_one(ticket)
        except Exception as e:
            logger.warning(f"[ticket:link] sync failed: {e}")
        return _ticket_dict(ticket)

    # ── Sync ticket status from provider ─────────────────────────────────────

    async def sync_ticket(self, tenant_id: str, ticket_id: str) -> dict:
        ticket = (await self.db.execute(
            select(SecurityTicket).where(
                SecurityTicket.id        == ticket_id,
                SecurityTicket.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")
        await self._sync_one(ticket)
        return _ticket_dict(ticket)

    async def _sync_one(self, ticket: SecurityTicket) -> None:
        now = datetime.now(timezone.utc)
        try:
            if ticket.provider == "jira":
                info = await jira_client.get_issue(ticket.ticket_key or ticket.external_id or "")
            elif ticket.provider == "linear":
                info = await linear_client.get_issue(ticket.external_id or "")
            elif ticket.provider == "azure_devops":
                info = await azure_devops_client.get_work_item(ticket.external_id or "")
            else:
                return

            ticket.ticket_status = info.get("ticket_status", ticket.ticket_status)
            ticket.assignee      = info.get("assignee")
            ticket.provider_meta = info.get("provider_meta", ticket.provider_meta)
            ticket.synced_at     = now
            await self.db.commit()
        except Exception as e:
            logger.warning(f"[ticket:sync] {ticket.provider}/{ticket.ticket_key}: {e}")

    # ── List tickets ──────────────────────────────────────────────────────────

    async def list_tickets(
        self,
        tenant_id:   str,
        entity_type: str | None = None,
        entity_id:   str | None = None,
        provider:    str | None = None,
        limit:       int        = 100,
        offset:      int        = 0,
    ) -> list[dict]:
        q = select(SecurityTicket).where(SecurityTicket.tenant_id == tenant_id)
        if entity_type: q = q.where(SecurityTicket.entity_type == entity_type)
        if entity_id:   q = q.where(SecurityTicket.entity_id   == entity_id)
        if provider:    q = q.where(SecurityTicket.provider     == provider)
        q = q.order_by(SecurityTicket.created_at.desc()).limit(limit).offset(offset)
        rows = (await self.db.execute(q)).scalars().all()
        return [_ticket_dict(t) for t in rows]

    def providers_status(self) -> dict:
        return _providers_status()


def _ticket_dict(t: SecurityTicket) -> dict:
    return {
        "id":           t.id,
        "entity_type":  t.entity_type,
        "entity_id":    t.entity_id,
        "provider":     t.provider,
        "external_id":  t.external_id,
        "ticket_key":   t.ticket_key,
        "ticket_url":   t.ticket_url,
        "ticket_title": t.ticket_title,
        "ticket_status":t.ticket_status,
        "assignee":     t.assignee,
        "priority":     t.priority,
        "link_type":    t.link_type,
        "synced_at":    t.synced_at.isoformat() if t.synced_at else None,
        "created_at":   t.created_at.isoformat() if t.created_at else None,
    }
