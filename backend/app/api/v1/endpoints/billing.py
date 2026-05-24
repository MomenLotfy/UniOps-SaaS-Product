from __future__ import annotations
"""Billing API — Stripe subscriptions, checkout, invoices, and portal."""
from pydantic import BaseModel
from fastapi import APIRouter, Query
from app.api.deps import CurrentUser, AdminUser, TenantID, DBSession
from app.schemas.common import APIResponse
from app.services.billing_service import BillingService

router = APIRouter()


class CheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str


class PortalRequest(BaseModel):
    return_url: str


class ChangePlanRequest(BaseModel):
    plan: str


# ── Read ──────────────────────────────────────────────────────────────────────

@router.get("/subscription")
async def get_subscription(current_user: CurrentUser, tenant_id: TenantID, db: DBSession):
    svc = BillingService(db)
    sub = await svc.get_subscription(tenant_id)
    return APIResponse(data=sub)


@router.get("/invoices")
async def list_invoices(
    current_user: CurrentUser, tenant_id: TenantID, db: DBSession,
    page_size: int = Query(default=10, ge=1, le=50),
):
    svc = BillingService(db)
    invoices = await svc.list_invoices(tenant_id, limit=page_size)
    return APIResponse(data=invoices)


@router.get("/plans")
async def list_plans(current_user: CurrentUser):
    """Return available plans with features and pricing."""
    from app.constants.plans import PLANS
    from app.integrations.stripe.client import PLAN_PRICE_IDS
    plans = []
    for key, plan in PLANS.items():
        if key == "free":
            continue
        plans.append({
            "id":           key,
            "name":         plan["name"],
            "price":        plan["price"],
            "seats":        plan["seats"],
            "integrations": plan["integrations"],
            "api_calls":    plan["api_calls_per_month"],
            "features":     plan.get("feature_list", []),
            "stripe_price_id": PLAN_PRICE_IDS.get(key),
        })
    return APIResponse(data=plans)


# ── Checkout ──────────────────────────────────────────────────────────────────

@router.post("/checkout")
async def create_checkout(
    data: CheckoutRequest, current_user: AdminUser,
    tenant_id: TenantID, db: DBSession,
):
    """Create a Stripe Checkout session. Returns checkout_url to redirect user."""
    svc = BillingService(db)
    result = await svc.create_checkout_session(
        tenant_id, data.plan, data.success_url, data.cancel_url
    )
    return APIResponse(data=result, message="Redirect to checkout_url")


@router.post("/portal")
async def create_portal(
    data: PortalRequest, current_user: AdminUser,
    tenant_id: TenantID, db: DBSession,
):
    """Create a Stripe Billing Portal session for managing subscription."""
    svc = BillingService(db)
    result = await svc.create_portal_session(tenant_id, data.return_url)
    return APIResponse(data=result)


@router.post("/cancel")
async def cancel_subscription(
    current_user: AdminUser, tenant_id: TenantID, db: DBSession,
    at_period_end: bool = Query(default=True),
):
    svc = BillingService(db)
    result = await svc.cancel_subscription(tenant_id, at_period_end)
    return APIResponse(data=result, message="Subscription cancellation scheduled")


@router.post("/change-plan")
async def change_plan(
    data: ChangePlanRequest, current_user: AdminUser,
    tenant_id: TenantID, db: DBSession,
):
    svc = BillingService(db)
    result = await svc.change_plan(tenant_id, data.plan)
    return APIResponse(data=result, message=f"Plan changed to {data.plan}")
