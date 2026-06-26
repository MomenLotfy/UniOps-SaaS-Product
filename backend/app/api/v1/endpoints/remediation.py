from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional
import uuid

from app.api.deps import get_db, get_current_user, get_tenant_id
from app.remediation.manager import RemediationManager
from app.remediation.registry.provider import get_remediation_registry
from app.remediation.interfaces.base import RemediationContext, ExecutionPlan
from app.remediation.models.models import RemediationPlan, RemediationExecutionHistory, RemediationStateHistory, RemediationExecutionMetrics, PluginMetadata
from sqlalchemy import select

from app.services.copilot_service import CopilotService
from app.remediation.engine.orchestrator import ExecutionOrchestrator
from app.remediation.engine.controller import ExecutionController
from app.remediation.engine.locks import LockManager, InMemoryLockProvider

router = APIRouter()

async def get_remediation_manager(db: AsyncSession = Depends(get_db)):
    registry = get_remediation_registry()
    copilot_service = CopilotService(db)
    return RemediationManager(db, registry, copilot_service=copilot_service)

async def get_orchestrator(db: AsyncSession = Depends(get_db)):
    registry = get_remediation_registry()
    return ExecutionOrchestrator(registry, db, lock_manager=LockManager(InMemoryLockProvider()))

async def get_controller(
    db: AsyncSession = Depends(get_db),
    orchestrator: ExecutionOrchestrator = Depends(get_orchestrator)
):
    return ExecutionController(orchestrator, db)

@router.post("/propose", status_code=status.HTTP_200_OK)
async def propose_remediation(
    payload: dict,
    tenant_id: str = Depends(get_tenant_id),
    manager: RemediationManager = Depends(get_remediation_manager)
):
    """
    Proposes a remediation plan based on the provided finding context.
    """
    try:
        context = RemediationContext(
            tenant_id=tenant_id,
            finding_id=payload.get("finding_id"),
            repo_id=payload.get("repo_id"),
            scan_id=payload.get("scan_id"),
            metadata=payload.get("metadata", {})
        )

        plan = await manager.propose_remediation(context)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No suitable remediation plan could be generated for this finding."
            )

        return plan
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/execute/{plan_id}/start", status_code=status.HTTP_200_OK)
async def start_execution(
    plan_id: str,
    tenant_id: str = Depends(get_tenant_id),
    controller: ExecutionController = Depends(get_controller),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers the execution of a specific plan.
    """
    query = select(RemediationPlan).where(
        RemediationPlan.id == plan_id,
        RemediationPlan.tenant_id == tenant_id
    )
    result = await db.execute(query)
    plan_db = result.scalar_one_or_none()
    if not plan_db:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = ExecutionPlan(**plan_db.__dict__)
    context = RemediationContext(
        tenant_id=tenant_id,
        finding_id=plan.finding_id,
        repo_id="unknown",
        correlation_id=str(uuid.uuid4())
    )

    return await controller.start_execution(context, plan)

@router.post("/execute/{plan_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_execution(
    plan_id: str,
    tenant_id: str = Depends(get_tenant_id),
    controller: ExecutionController = Depends(get_controller)
):
    """
    Cancels a running execution.
    """
    success = await controller.cancel_execution(plan_id, tenant_id)
    return {"status": "cancelled" if success else "failed"}

@router.post("/execute/{plan_id}/rollback", status_code=status.HTTP_200_OK)
async def rollback_execution(
    plan_id: str,
    tenant_id: str = Depends(get_tenant_id),
    controller: ExecutionController = Depends(get_controller),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually triggers a rollback for a completed/failed plan.
    """
    context = RemediationContext(
        tenant_id=tenant_id,
        finding_id="unknown",
        repo_id="unknown",
        correlation_id=str(uuid.uuid4())
    )
    return await controller.trigger_rollback(plan_id, tenant_id, context)

@router.post("/execute/{plan_id}", status_code=status.HTTP_200_OK)
async def execute_remediation(
    plan_id: str,
    tenant_id: str = Depends(get_tenant_id),
    manager: RemediationManager = Depends(get_remediation_manager),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers the execution of a previously proposed remediation plan.
    """
    query = select(RemediationPlan).where(
        RemediationPlan.id == plan_id,
        RemediationPlan.tenant_id == tenant_id
    )
    result = await db.execute(query)
    plan_db = result.scalar_one_or_none()

    if not plan_db:
        raise HTTPException(status_code=404, detail="Plan not found")

    context = RemediationContext(
        tenant_id=tenant_id,
        finding_id=plan_db.finding_id,
        repo_id="unknown",
        metadata={
            "finding_type": plan_db.finding_type,
            "technology": plan_db.target_technology
        }
    )

    execution_plan = ExecutionPlan(**plan_db.__dict__)
    res = await manager.run_remediation(context, execution_plan)

    if res["status"] == "failed":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=res["error"])

    return res

@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(RemediationPlan).where(
        RemediationPlan.id == plan_id,
        RemediationPlan.tenant_id == tenant_id
    )
    result = await db.execute(query)
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan

@router.get("/history/{plan_id}")
async def get_plan_history(
    plan_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(RemediationExecutionHistory).where(
        RemediationExecutionHistory.plan_id == plan_id,
        RemediationExecutionHistory.tenant_id == tenant_id
    ).order_by(RemediationExecutionHistory.start_time.desc())

    result = await db.execute(query)
    return result.scalars().all()

@router.get("/capabilities")
async def list_capabilities(
    manager: RemediationManager = Depends(get_remediation_manager)
):
    return manager.registry.list_plugins()

@router.get("/status/{plan_id}")
async def get_execution_status(
    plan_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(RemediationPlan).where(
        RemediationPlan.id == plan_id,
        RemediationPlan.tenant_id == tenant_id
    )
    result = await db.execute(query)
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return {
        "plan_id": plan.id,
        "current_state": plan.status,
        "updated_at": plan.updated_at
    }

@router.get("/timeline/{plan_id}")
async def get_execution_timeline(
    plan_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(RemediationStateHistory).where(
        RemediationStateHistory.plan_id == plan_id,
        RemediationStateHistory.tenant_id == tenant_id
    ).order_by(RemediationStateHistory.transition_timestamp.asc())

    result = await db.execute(query)
    history = result.scalars().all()

    return [
        {
            "from": h.from_state,
            "to": h.to_state,
            "timestamp": h.transition_timestamp,
            "reason": h.reason,
            "by": h.transitioned_by
        } for h in history
    ]

@router.get("/metrics")
async def get_remediation_metrics(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(RemediationExecutionMetrics).where(
        RemediationExecutionMetrics.tenant_id == tenant_id
    )
    result = await db.execute(query)
    metrics = result.scalars().all()

    return {
        "metrics": {m.metric_name: m.value for m in metrics}
    }

@router.get("/plugins/compatibility")
async def get_plugin_compatibility(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(PluginMetadata).where(
        PluginMetadata.is_active == True
    )
    result = await db.execute(query)
    plugins = result.scalars().all()

    return [
        {
            "plugin_id": p.plugin_id,
            "version": p.version,
            "min_engine": p.min_engine_version,
            "max_engine": p.max_engine_version,
            "required_apis": p.required_apis,
            "supported_features": p.supported_features
        } for p in plugins
    ]

@router.get("/capabilities/health")
async def get_capability_health(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(PluginMetadata)
    result = await db.execute(query)
    plugins = result.scalars().all()

    return [
        {
            "plugin_id": p.plugin_id,
            "name": p.name,
            "health": p.health_status,
            "maintenance": p.maintenance_mode,
            "deprecation": p.deprecation_status
        } for p in plugins
    ]

@router.get("/plans/{plan_id}/versions")
async def get_plan_versions(
    plan_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    query = select(RemediationPlan).where(
        (RemediationPlan.id == plan_id) | (RemediationPlan.parent_version_id == plan_id),
        RemediationPlan.tenant_id == tenant_id
    ).order_by(RemediationPlan.version.asc())

    result = await db.execute(query)
    versions = result.scalars().all()

    return [
        {
            "version": v.version,
            "created_at": v.created_at,
            "created_by": v.created_by,
            "change_reason": v.change_reason
        } for v in versions
    ]

@router.get("/policies")
async def get_execution_policies(
    tenant_id: str = Depends(get_tenant_id)
):
    return {
        "policies": [
            {"id": "POL-001", "type": "manual_approval", "description": "Production repositories require manual approval."},
            {"id": "POL-002", "type": "production_freeze", "description": "Peak Hour ConstraintsC"},
            {"id": "POL-003", "type": "security_approval", "description": "SVP Security Sign-off"},
        ]
    }

@router.get("/workers/status")
async def get_worker_status():
    return {
        "workers": [
            {"name": "PlanningWorker", "status": "active", "load": "low"},
            {"name": "ExecutionWorker", "status": "active", "load": "medium"},
            {"name": "ValidationWorker", "status": "active", "load": "low"},
            {"name": "NotificationWorker", "status": "active", "load": "low"},
            {"name": "MetricsWorker", "status": "active", "load": "low"},
        ],
        "queue_status": {
            "remediation.planning": 0,
            "remediation.execution": 2,
            "remediation.validation": 0,
        }
    }
