from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional

from app.api.deps import get_db, get_current_user, get_tenant_id
from app.remediation.manager import RemediationManager
from app.remediation.registry.provider import get_remediation_registry
from app.remediation.interfaces.base import RemediationContext, ExecutionPlan
from app.remediation.models.models import RemediationPlan, RemediationExecutionHistory
from sqlalchemy import select

router = APIRouter()

async def get_remediation_manager(db: AsyncSession = Depends(get_db)):
    registry = get_remediation_registry()
    return RemediationManager(db, registry)

@router.post("/propose", status_code=status.HTTP_200_OK)
async def propose_remediation(
    payload: dict,
    tenant_id: str = Depends(get_tenant_id),
    manager: RemediationManager = Depends(get_remediation_manager)
):
    """
    Proposes a remediation plan based on the provided finding context.
    Payload should contain finding_id, repo_id, and optional metadata.
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
    # 1. Fetch the plan from DB to validate it belongs to the tenant
    query = select(RemediationPlan).where(
        RemediationPlan.id == plan_id,
        RemediationPlan.tenant_id == tenant_id
    )
    result = await db.execute(query)
    plan_db = result.scalar_one_or_none()

    if not plan_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    # 2. Reconstruct the context (In a real system, context would be persisted)
    # For this architecture, we assume the caller provides context or we retrieve it.
    # Simplified: we'll use the plan's metadata to build a basic context.
    context = RemediationContext(
        tenant_id=tenant_id,
        finding_id=plan_db.finding_id,
        repo_id="unknown", # Would be retrieved from plan metadata in real impl
        metadata={
            "finding_type": plan_db.finding_type,
            "technology": plan_db.target_technology
        }
    )

    # Convert DB model to ExecutionPlan Pydantic model
    execution_plan = ExecutionPlan(
        plan_id=plan_db.id,
        finding_type=plan_db.finding_type,
        target_technology=plan_db.target_technology,
        capability_id=plan_db.capability_id,
        strategy_id=plan_db.strategy_id,
        priority=plan_db.priority,
        required_inputs=plan_db.required_inputs,
        expected_outputs=plan_db.expected_outputs,
        status=plan_db.status
    )

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
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
    """
    Lists all available remediation capabilities registered in the system.
    """
    return manager.registry.list_plugins()
