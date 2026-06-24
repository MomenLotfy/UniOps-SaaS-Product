from __future__ import annotations
"""Security Reports API — generate and retrieve security reports."""
from typing import Optional
from fastapi import APIRouter, Query
from app.api.deps import (
    SecurityReadUser, SecurityWriteUser, AuditReadUser,
    TenantID, DBSession,
)
from app.schemas.security_report import SecurityReportGenerate, SecurityReportResponse
from app.schemas.common import APIResponse
from app.services.security_report_service import SecurityReportService
from app.utils.logger import logger

router = APIRouter()


@router.get("", response_model=APIResponse)
async def list_reports(
    current_user: AuditReadUser,
    tenant_id: TenantID,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    report_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    logger.info(f"[reports:list] tenant={tenant_id[:8]} type={report_type}")
    svc = SecurityReportService(db)
    result = await svc.list_reports(tenant_id, page, page_size, report_type=report_type, status=status)
    return APIResponse(data=result)


@router.post("", response_model=APIResponse[SecurityReportResponse])
async def generate_report(
    data: SecurityReportGenerate,
    current_user: SecurityWriteUser,
    tenant_id: TenantID,
    db: DBSession,
):
    logger.info(f"[reports:generate] tenant={tenant_id[:8]} type={data.report_type} by={current_user['user_id'][:8]}")
    svc = SecurityReportService(db)
    report = await svc.generate_report(tenant_id, data, current_user["user_id"])
    return APIResponse(data=report, message="Report generated")


@router.get("/{report_id}", response_model=APIResponse[SecurityReportResponse])
async def get_report(
    report_id: str,
    current_user: AuditReadUser,
    db: DBSession,
):
    svc = SecurityReportService(db)
    report = await svc.get_report(report_id)
    return APIResponse(data=report)


@router.delete("/{report_id}", response_model=APIResponse)
async def delete_report(
    report_id: str,
    current_user: SecurityWriteUser,
    db: DBSession,
):
    svc = SecurityReportService(db)
    await svc.delete_report(report_id)
    return APIResponse(data=None, message="Report deleted")
