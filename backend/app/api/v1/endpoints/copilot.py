from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.api.deps import (
    CurrentUser, SecurityReadUser, SecurityWriteUser,
    TenantID, DBSession,
)
from app.schemas.common import APIResponse
from app.services.copilot_service import CopilotService

router = APIRouter()

class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    repo_id: Optional[str] = None
    finding_id: Optional[str] = None
    scan_id: Optional[str] = None

class ConversationCreate(BaseModel):
    title: str
    metadata: Optional[dict] = None

@router.get("/conversations", response_model=APIResponse)
async def list_conversations(
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = CopilotService(db)
    data = await svc.list_conversations(
        tenant_id=tenant_id,
        user_id=current_user["user_id"],
        limit=page_size,
        offset=(page - 1) * page_size
    )
    return APIResponse(data=data)

@router.post("/conversations", response_model=APIResponse)
async def create_conversation(
    data: ConversationCreate,
    current_user: SecurityWriteUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = CopilotService(db)
    conv = await svc.create_conversation(
        tenant_id=tenant_id,
        user_id=current_user["user_id"],
        title=data.title,
        metadata=data.metadata
    )
    return APIResponse(data={"id": conv.id, "title": conv.title}, message="Conversation started")

@router.get("/conversations/{conv_id}/messages", response_model=APIResponse)
async def get_messages(
    conv_id: str,
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = CopilotService(db)
    data = await svc.get_conversation_messages(tenant_id, conv_id)
    return APIResponse(data=[{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in data])

@router.delete("/conversations/{conv_id}", response_model=APIResponse)
async def delete_conversation(
    conv_id: str,
    current_user: SecurityWriteUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = CopilotService(db)
    success = await svc.delete_conversation(tenant_id, conv_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return APIResponse(data=None, message="Conversation deleted")

@router.post("/chat", response_model=APIResponse)
async def chat(
    data: ChatRequest,
    current_user: SecurityReadUser,
    tenant_id: TenantID,
    db: DBSession,
):
    svc = CopilotService(db)
    result = await svc.chat(
        tenant_id=tenant_id,
        user_id=current_user["user_id"],
        conversation_id=data.conversation_id,
        message=data.message,
        context_params={
            "repo_id": data.repo_id,
            "finding_id": data.finding_id,
            "scan_id": data.scan_id
        }
    )
    return APIResponse(data=result)
