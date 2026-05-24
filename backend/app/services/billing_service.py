from __future__ import annotations
"""Billing service — full Stripe subscription lifecycle."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User
from app.core.exceptions import NotFoundError, IntegrationError, ConflictError
from app.config import settings
from app.services.base import BaseService
from app.utils.logger import logger


def _stripe_client():
    if not settings.STRIPE_SECRET_KEY:
        raise IntegrationError("Stripe", "STRIPE_SECRET_KEY is not configured in .env")
    from app.integrations.stripe.client import StripeClient
    return StripeClient(settings.STRIPE_SECRET_KEY)


class BillingService(BaseService):

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_subscription(self, tenant_id: str) -> Optional[dict]:
        result = await self.db.execute(
            select(Subscription)
            .where(Subscription.tenant_id == tenant_id)
            .order_by(Subscription.created_at.desc())
        )
        sub = result.scalar_one_or_none()
        if not sub:
            return None
        return {
            "id": sub.id,
            "plan": sub.plan,
            "status": sub.status,
            "stripe_subscription_id": sub.stripe_subscription_id,
            "stripe_customer_id": sub.stripe_customer_id,
            "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
            "current_period_end":   sub.current_period_end.isoformat()   if sub.current_period_end   else None,
            "seats": sub.seats,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }

    async def list_invoices(self, tenant_id: str, limit: int = 10) -> list[dict]:
        """Get real invoices from Stripe."""
        sub = await self._get_sub(tenant_id)
        if not sub or not sub.stripe_customer_id:
            return []
        try:
            client = _stripe_client()
            invoices = await client.list_invoices(sub.stripe_customer_id, limit)
            return [
                {
                    "id":          inv.get("id"),
                    "number":      inv.get("number"),
                    "amount":      inv.get("amount_paid", 0),
                    "currency":    inv.get("currency", "usd").upper(),
                    "status":      inv.get("status"),
                    "period":      _period_label(inv),
                    "pdf_url":     inv.get("invoice_pdf"),
                    "created_at":  datetime.fromtimestamp(inv.get("created", 0), tz=timezone.utc).isoformat(),
                }
                for inv in invoices
            ]
        except IntegrationError:
            return []
        except Exception as e:
            logger.warning(f"Could not fetch Stripe invoices: {e}")
            return []

    # ── Checkout ──────────────────────────────────────────────────────────────

    async def create_checkout_session(
        self, tenant_id: str, plan: str, success_url: str, cancel_url: str
    ) -> dict:
        client = _stripe_client()

        # Get or create Stripe customer for this tenant
        customer_id = await self._get_or_create_customer(tenant_id, client)

        session = await client.create_checkout_session(
            plan=plan,
            customer_id=customer_id,
            success_url=success_url,
            cancel_url=cancel_url,
            tenant_id=tenant_id,
        )
        if not session:
            raise IntegrationError("Stripe", "Failed to create checkout session")

        return {
            "checkout_url": session.get("url"),
            "session_id":   session.get("id"),
            "plan":         plan,
        }

    # ── Portal ────────────────────────────────────────────────────────────────

    async def create_portal_session(self, tenant_id: str, return_url: str) -> dict:
        client = _stripe_client()
        sub = await self._get_sub(tenant_id)

        if not sub or not sub.stripe_customer_id:
            # No subscription yet — send to pricing page
            return {"portal_url": f"{settings.FRONTEND_URL}/pricing"}

        session = await client.create_portal_session(sub.stripe_customer_id, return_url)
        if not session:
            raise IntegrationError("Stripe", "Failed to create portal session")

        return {"portal_url": session.get("url")}

    # ── Cancel ────────────────────────────────────────────────────────────────

    async def cancel_subscription(self, tenant_id: str, at_period_end: bool = True) -> dict:
        client = _stripe_client()
        sub = await self._get_sub(tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise NotFoundError("Subscription", tenant_id)

        result = await client.cancel_subscription(sub.stripe_subscription_id, at_period_end)
        if result:
            sub.cancel_at_period_end = at_period_end
            if not at_period_end:
                sub.status = "canceled"
            await self.db.flush()

        return {"canceled": True, "at_period_end": at_period_end}

    # ── Upgrade / Downgrade ───────────────────────────────────────────────────

    async def change_plan(self, tenant_id: str, new_plan: str) -> dict:
        client = _stripe_client()
        sub = await self._get_sub(tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise ConflictError("No active subscription to upgrade")

        result = await client.update_subscription_plan(sub.stripe_subscription_id, new_plan)
        if result:
            sub.plan = new_plan
            await self.db.flush()

            # Also update tenant plan
            tenant = await self._get_by_id(Tenant, tenant_id)
            tenant.plan = new_plan
            await self.db.flush()

        return {"plan": new_plan, "status": "updated"}

    # ── Webhook handlers ──────────────────────────────────────────────────────

    async def handle_webhook(self, event_type: str, data: dict) -> None:
        handlers = {
            "checkout.session.completed":       self._on_checkout_completed,
            "invoice.payment_succeeded":        self._on_payment_succeeded,
            "invoice.payment_failed":           self._on_payment_failed,
            "customer.subscription.updated":    self._on_subscription_updated,
            "customer.subscription.deleted":    self._on_subscription_deleted,
            "customer.subscription.trial_will_end": self._on_trial_ending,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(data)

    async def _on_checkout_completed(self, data: dict) -> None:
        """Stripe checkout paid → create subscription record."""
        tenant_id  = data.get("metadata", {}).get("tenant_id")
        plan       = data.get("metadata", {}).get("plan", "starter")
        customer_id = data.get("customer")
        sub_id     = data.get("subscription")

        if not tenant_id or not sub_id:
            logger.warning("checkout.session.completed missing tenant_id or subscription")
            return

        # Fetch full subscription from Stripe
        client = _stripe_client()
        stripe_sub = await client.get_subscription(sub_id)

        existing = await self._get_sub(tenant_id)
        now = datetime.now(timezone.utc)

        if existing:
            existing.plan                  = plan
            existing.status                = "active"
            existing.stripe_subscription_id = sub_id
            existing.stripe_customer_id    = customer_id
            existing.cancel_at_period_end  = False
            if stripe_sub:
                existing.current_period_start = _ts(stripe_sub.get("current_period_start"))
                existing.current_period_end   = _ts(stripe_sub.get("current_period_end"))
        else:
            from app.constants.plans import PLANS
            plan_seats = PLANS.get(plan, {}).get("seats", 5)
            self.db.add(Subscription(
                tenant_id              = tenant_id,
                plan                   = plan,
                status                 = "active",
                stripe_subscription_id = sub_id,
                stripe_customer_id     = customer_id,
                seats                  = plan_seats,
                cancel_at_period_end   = False,
                current_period_start   = _ts(stripe_sub.get("current_period_start")) if stripe_sub else now,
                current_period_end     = _ts(stripe_sub.get("current_period_end"))   if stripe_sub else now,
            ))

        # Upgrade tenant plan
        tenant = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant.scalar_one_or_none()
        if tenant:
            tenant.plan = plan

        await self.db.flush()
        logger.info(f"Subscription activated: tenant={tenant_id} plan={plan}")

        # Send confirmation email to admin user
        try:
            from app.models.user import User
            from sqlalchemy import select
            user_r = await self.db.execute(
                select(User).where(User.tenant_id == tenant_id, User.role == "admin")
                .order_by(User.created_at)
            )
            admin = user_r.scalar_one_or_none()
            if admin:
                from app.services.notification_service import NotificationService
                from app.constants.plans import PLANS
                plan_price = PLANS.get(plan, {}).get("price", 0)
                period_end = _ts(stripe_sub.get("current_period_end")) if stripe_sub else None
                next_billing = period_end.strftime("%B %d, %Y") if period_end else "next month"
                await NotificationService().send_subscription_confirmed(
                    to_email          = admin.email,
                    user_name         = admin.full_name,
                    plan_name         = PLANS.get(plan, {}).get("name", plan.title()),
                    amount            = float(plan_price),
                    next_billing_date = next_billing,
                )
        except Exception as e:
            logger.warning(f"Subscription confirmation email failed (non-fatal): {e}")

    async def _on_payment_succeeded(self, data: dict) -> None:
        customer_id = data.get("customer")
        if not customer_id:
            return
        sub = await self._get_sub_by_customer(customer_id)
        if sub:
            sub.status = "active"
            await self.db.flush()
            logger.info(f"Payment succeeded: customer={customer_id}")

    async def _on_payment_failed(self, data: dict) -> None:
        customer_id = data.get("customer")
        if not customer_id:
            return
        sub = await self._get_sub_by_customer(customer_id)
        if sub:
            sub.status = "past_due"
            await self.db.flush()
            logger.warning(f"Payment failed: customer={customer_id}")

    async def _on_subscription_updated(self, data: dict) -> None:
        stripe_sub_id = data.get("id")
        if not stripe_sub_id:
            return
        sub = await self._get_sub_by_stripe_id(stripe_sub_id)
        if sub:
            sub.status               = data.get("status", sub.status)
            sub.cancel_at_period_end = data.get("cancel_at_period_end", False)
            if data.get("current_period_start"):
                sub.current_period_start = _ts(data["current_period_start"])
            if data.get("current_period_end"):
                sub.current_period_end = _ts(data["current_period_end"])
            # Sync plan from metadata
            new_plan = data.get("metadata", {}).get("plan")
            if new_plan and new_plan != sub.plan:
                sub.plan = new_plan
                tenant = await self.db.execute(select(Tenant).where(Tenant.id == sub.tenant_id))
                tenant = tenant.scalar_one_or_none()
                if tenant:
                    tenant.plan = new_plan
            await self.db.flush()
            logger.info(f"Subscription updated: {stripe_sub_id} → {sub.status}")

    async def _on_subscription_deleted(self, data: dict) -> None:
        stripe_sub_id = data.get("id")
        if not stripe_sub_id:
            return
        sub = await self._get_sub_by_stripe_id(stripe_sub_id)
        if sub:
            sub.status = "canceled"
            # Downgrade tenant to free
            tenant = await self.db.execute(select(Tenant).where(Tenant.id == sub.tenant_id))
            tenant = tenant.scalar_one_or_none()
            if tenant:
                tenant.plan = "free"
            await self.db.flush()
            logger.info(f"Subscription canceled: {stripe_sub_id}")

    async def _on_trial_ending(self, data: dict) -> None:
        customer_id = data.get("customer")
        logger.info(f"Trial ending soon: customer={customer_id} — send reminder email")
        # TODO: trigger email notification

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_sub(self, tenant_id: str) -> Optional[Subscription]:
        result = await self.db.execute(
            select(Subscription)
            .where(Subscription.tenant_id == tenant_id)
            .order_by(Subscription.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def _get_sub_by_customer(self, customer_id: str) -> Optional[Subscription]:
        result = await self.db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    async def _get_sub_by_stripe_id(self, stripe_sub_id: str) -> Optional[Subscription]:
        result = await self.db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
        )
        return result.scalar_one_or_none()

    async def _get_or_create_customer(self, tenant_id: str, client) -> str:
        """Get existing Stripe customer ID or create a new one."""
        sub = await self._get_sub(tenant_id)
        if sub and sub.stripe_customer_id:
            return sub.stripe_customer_id

        # Fetch tenant + admin user details
        tenant_r = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_r.scalar_one_or_none()

        user_r = await self.db.execute(
            select(User)
            .where(User.tenant_id == tenant_id, User.role == "admin")
            .order_by(User.created_at)
        )
        user = user_r.scalar_one_or_none()

        email = user.email if user else f"tenant-{tenant_id}@uniops.io"
        name  = tenant.name if tenant else "Unknown Company"

        customer = await client.create_customer(email, name, tenant_id)
        if not customer:
            raise IntegrationError("Stripe", "Failed to create Stripe customer")

        # Save customer ID to subscription if exists, or create free subscription record
        if sub:
            sub.stripe_customer_id = customer["id"]
        else:
            self.db.add(Subscription(
                tenant_id          = tenant_id,
                plan               = "free",
                status             = "active",
                stripe_customer_id = customer["id"],
                seats              = 3,
            ))
        await self.db.flush()
        return customer["id"]


# ── Utility functions ─────────────────────────────────────────────────────────

def _ts(unix_timestamp) -> Optional[datetime]:
    """Convert Unix timestamp to datetime."""
    if not unix_timestamp:
        return None
    try:
        return datetime.fromtimestamp(int(unix_timestamp), tz=timezone.utc)
    except (ValueError, TypeError):
        return None


def _period_label(invoice: dict) -> str:
    """Format invoice period as 'Month Year'."""
    start = invoice.get("period_start")
    if start:
        try:
            dt = datetime.fromtimestamp(start, tz=timezone.utc)
            return dt.strftime("%B %Y")
        except Exception:
            pass
    return invoice.get("number", "")
