from __future__ import annotations
"""Reports API - generate, schedule, and manage enterprise security reports."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, Body, Response
from app.api.deps import (
    SecurityReadUser, SecurityWriteUser, AuditReadUser,
    TenantID, DBSession,
)
from app.schemas.common import APIResponse
from app.services.reports_service import ReportsService
from app.core.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=APIResponse[dict])
async def list_reports(
    current_user: SecurityReadUser,
    tenant_id:    TenantID,
    db:           DBSession,
    page:         int = Query(1, ge=1),
    page_size:    int = Query(50, ge=1, le=200),
    report_type:  Optional[str] = Query(None, description="Filter by template type"),
    status:       Optional[str] = Query(None, description="Filter by status"),
    scheduled:    Optional[bool] = Query(None, description="Filter by scheduled reports"),
):
    """List all reports with pagination and filtering."""
    svc = ReportsService(db)
    result = await svc.list_reports(tenant_id, page, page_size,
        report_type=report_type, status=status, scheduled=scheduled)
    return APIResponse(data=result)


@router.get("/templates", response_model=APIResponse[List[dict]])
async def get_report_templates(
    current_user: SecurityReadUser,
):
    """Get all available report templates."""
    from app.models.report import REPORT_TEMPLATES
    return APIResponse(data=REPORT_TEMPLATES)


@router.get("/{report_id}", response_model=APIResponse[dict])
async def get_report(
    report_id:    str,
    current_user: SecurityReadUser,
    db:           DBSession,
):
    """Get report details including findings and metrics."""
    svc = ReportsService(db)
    report = await svc.get_report(report_id)
    if not report:
        raise NotFoundError("Report", report_id)
    return APIResponse(data=report)


@router.get("/{report_id}/download", response_model=APIResponse)
async def download_report(
    report_id:    str,
    current_user: SecurityReadUser,
    db:           DBSession,
    format:       str = Query("json", description="Export format: json, pdf, csv, excel, html"),
):
    """Download report in specified format."""
    svc = ReportsService(db)
    report = await svc.get_report(report_id)
    if not report:
        raise NotFoundError("Report", report_id)

    # Generate download content
    download_result = await svc.generate_download(report, format)
    if not download_result:
        raise NotFoundError("Report content", report_id)

    return Response(
        content=download_result["content"],
        media_type=download_result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{download_result["filename"]}"'},
    )


@router.post("", response_model=APIResponse[dict])
async def generate_report(
    current_user: SecurityWriteUser,
    tenant_id:    TenantID,
    db:           DBSession,
    data: Dict[str, Any] = Body(..., description="Report generation parameters"),
):
    """Generate a new report."""
    svc = ReportsService(db)
    report = await svc.generate_report(tenant_id, data, current_user["user_id"])
    return APIResponse(data=report, message="Report generated successfully")


@router.post("/schedule", response_model=APIResponse[dict])
async def schedule_report(
    current_user: SecurityWriteUser,
    tenant_id:    TenantID,
    db:           DBSession,
    data: Dict[str, Any] = Body(..., description="Report scheduling parameters"),
):
    """Schedule a recurring report."""
    svc = ReportsService(db)
    report = await svc.schedule_report(tenant_id, data, current_user["user_id"])
    return APIResponse(data=report, message="Report scheduled")


@router.post("/{report_id}/regenerate", response_model=APIResponse[dict])
async def regenerate_report(
    report_id:    str,
    current_user: SecurityWriteUser,
    tenant_id:    TenantID,
    db:           DBSession,
):
    """Regenerate an existing report."""
    svc = ReportsService(db)
    report = await svc.regenerate_report(report_id, tenant_id)
    return APIResponse(data=report, message="Report regenerated")


@router.delete("/{report_id}", response_model=APIResponse)
async def delete_report(
    report_id:    str,
    current_user: SecurityWriteUser,
    db:           DBSession,
):
    """Delete a report."""
    svc = ReportsService(db)
    await svc.delete_report(report_id)
    return APIResponse(data=None, message="Report deleted")


@router.get("/summary", response_model=APIResponse[dict])
async def get_report_summary(
    current_user: SecurityReadUser,
    tenant_id:    TenantID,
    db:           DBSession,
    days:         int = Query(30, ge=7, le=365),
):
    """Get report generation summary statistics."""
    svc = ReportsService(db)
    summary = await svc.get_summary(tenant_id, days=days)
    return APIResponse(data=summary)
