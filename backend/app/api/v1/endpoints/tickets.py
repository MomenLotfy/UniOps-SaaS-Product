"""Security ticket integration — Jira / Linear / Azure DevOps."""
from __future__ import annotations
from fastapi import APIRouter, Query
from pydantic import BaseModel as PydanticModel
from app.api.deps import CurrentUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.ticket_service import TicketService

router = APIRouter()


class CreateTicketRequest(PydanticModel):
    entity_type: str            # threat | vulnerability | asset | repository
    entity_id:   str
    provider:    str            # jira | linear | azure_devops
    title:       str
    description: str
    severity:    str = "high"
    # Provider-specific
    jira_project_key:   str | None = None
    jira_issue_type:    str        = "Bug"
    linear_team_id:     str | None = None
    ado_work_item_type: str        = "Bug"


class LinkTicketRequest(PydanticModel):
    entity_type:  str
    entity_id:    str
    provider:     str
    ticket_key:   str
    ticket_url:   str
    ticket_title: str = ""


@router.get("/providers", response_model=APIResponse)
async def get_providers(
    current_user: CurrentUser,
    db:           DBSession,
):
    """Return which ticket providers are configured (have env vars set)."""
    svc = TicketService(db)
    return APIResponse(data=svc.providers_status())


@router.get("", response_model=APIResponse)
async def list_tickets(
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
    entity_type:  str | None = None,
    entity_id:    str | None = None,
    provider:     str | None = None,
    limit:        int = Query(100, le=500),
    offset:       int = 0,
):
    svc  = TicketService(db)
    data = await svc.list_tickets(
        tenant_id=tenant_id, entity_type=entity_type,
        entity_id=entity_id, provider=provider,
        limit=limit, offset=offset,
    )
    return APIResponse(data=data)


@router.post("", response_model=APIResponse)
async def create_ticket(
    body:         CreateTicketRequest,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Create a new ticket in Jira / Linear / Azure DevOps for a security finding."""
    svc  = TicketService(db)
    data = await svc.create_ticket(
        tenant_id=tenant_id,
        created_by=current_user.id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        provider=body.provider,
        title=body.title,
        description=body.description,
        severity=body.severity,
        jira_project_key=body.jira_project_key,
        jira_issue_type=body.jira_issue_type,
        linear_team_id=body.linear_team_id,
        ado_work_item_type=body.ado_work_item_type,
    )
    return APIResponse(data=data, message="Ticket created successfully")


@router.post("/link", response_model=APIResponse)
async def link_ticket(
    body:         LinkTicketRequest,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Link an existing external ticket to a security finding."""
    svc  = TicketService(db)
    data = await svc.link_ticket(
        tenant_id=tenant_id,
        created_by=current_user.id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        provider=body.provider,
        ticket_key=body.ticket_key,
        ticket_url=body.ticket_url,
        ticket_title=body.ticket_title,
    )
    return APIResponse(data=data, message="Ticket linked successfully")


@router.post("/{ticket_id}/sync", response_model=APIResponse)
async def sync_ticket(
    ticket_id:    str,
    current_user: CurrentUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Pull latest status from the external provider."""
    svc  = TicketService(db)
    data = await svc.sync_ticket(tenant_id, ticket_id)
    return APIResponse(data=data, message="Ticket status synced")
