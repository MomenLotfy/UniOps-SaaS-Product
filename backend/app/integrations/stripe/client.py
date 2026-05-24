from __future__ import annotations
"""Stripe client — full subscription and billing management."""
from typing import Optional
import httpx
from app.utils.logger import logger


PLAN_PRICE_IDS: dict[str, str] = {
    # Replace these with your real Stripe Price IDs from dashboard.stripe.com
    "starter":      "price_starter_monthly",
    "professional": "price_professional_monthly",
    "enterprise":   "price_enterprise_monthly",
}

PLAN_NAMES = {
    "starter":      "Starter",
    "professional": "Professional",
    "enterprise":   "Enterprise",
}


class StripeClient:
    BASE = "https://api.stripe.com/v1"

    def __init__(self, secret_key: str):
        self._auth = (secret_key, "")

    async def _get(self, path: str, params: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{self.BASE}{path}", auth=self._auth, params=params)
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{self.BASE}{path}", auth=self._auth, data=data)
            r.raise_for_status()
            return r.json()

    # ── Account ───────────────────────────────────────────────────────────────
    async def test_connection(self) -> bool:
        try:
            await self._get("/account")
            return True
        except Exception as e:
            logger.warning(f"Stripe connection failed: {e}")
            return False

    # ── Customer ──────────────────────────────────────────────────────────────
    async def create_customer(self, email: str, name: str, tenant_id: str) -> Optional[dict]:
        try:
            return await self._post("/customers", {
                "email": email,
                "name": name,
                "metadata[tenant_id]": tenant_id,
            })
        except Exception as e:
            logger.error(f"Stripe create_customer: {e}")
            return None

    async def get_customer(self, customer_id: str) -> Optional[dict]:
        try:
            return await self._get(f"/customers/{customer_id}")
        except Exception:
            return None

    # ── Checkout ──────────────────────────────────────────────────────────────
    async def create_checkout_session(
        self,
        plan: str,
        customer_id: str,
        success_url: str,
        cancel_url: str,
        tenant_id: str,
    ) -> Optional[dict]:
        price_id = PLAN_PRICE_IDS.get(plan)
        if not price_id:
            raise ValueError(f"Unknown plan: {plan}. Valid: {list(PLAN_PRICE_IDS)}")
        try:
            return await self._post("/checkout/sessions", {
                "mode": "subscription",
                "customer": customer_id,
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata[tenant_id]": tenant_id,
                "metadata[plan]": plan,
                "subscription_data[metadata][tenant_id]": tenant_id,
                "subscription_data[metadata][plan]": plan,
                # Allow promo codes
                "allow_promotion_codes": "true",
            })
        except Exception as e:
            logger.error(f"Stripe create_checkout_session: {e}")
            return None

    # ── Billing portal ────────────────────────────────────────────────────────
    async def create_portal_session(self, customer_id: str, return_url: str) -> Optional[dict]:
        try:
            return await self._post("/billing_portal/sessions", {
                "customer": customer_id,
                "return_url": return_url,
            })
        except Exception as e:
            logger.error(f"Stripe create_portal_session: {e}")
            return None

    # ── Subscription ──────────────────────────────────────────────────────────
    async def get_subscription(self, sub_id: str) -> Optional[dict]:
        try:
            return await self._get(f"/subscriptions/{sub_id}")
        except Exception:
            return None

    async def cancel_subscription(self, sub_id: str, at_period_end: bool = True) -> Optional[dict]:
        try:
            return await self._post(f"/subscriptions/{sub_id}", {
                "cancel_at_period_end": "true" if at_period_end else "false",
            })
        except Exception as e:
            logger.error(f"Stripe cancel_subscription: {e}")
            return None

    async def update_subscription_plan(self, sub_id: str, new_plan: str) -> Optional[dict]:
        """Upgrade or downgrade to a different plan."""
        price_id = PLAN_PRICE_IDS.get(new_plan)
        if not price_id:
            raise ValueError(f"Unknown plan: {new_plan}")
        try:
            # First get the subscription to find the item ID
            sub = await self.get_subscription(sub_id)
            if not sub:
                return None
            item_id = sub["items"]["data"][0]["id"]
            return await self._post(f"/subscriptions/{sub_id}", {
                f"items[0][id]": item_id,
                f"items[0][price]": price_id,
                "proration_behavior": "always_invoice",
                "metadata[plan]": new_plan,
            })
        except Exception as e:
            logger.error(f"Stripe update_subscription_plan: {e}")
            return None

    # ── Invoices ──────────────────────────────────────────────────────────────
    async def list_invoices(self, customer_id: str, limit: int = 10) -> list[dict]:
        try:
            r = await self._get("/invoices", {
                "customer": customer_id,
                "limit": limit,
                "status": "paid",
            })
            return r.get("data", [])
        except Exception as e:
            logger.warning(f"Stripe list_invoices: {e}")
            return []

    async def get_upcoming_invoice(self, customer_id: str) -> Optional[dict]:
        try:
            return await self._get("/invoices/upcoming", {"customer": customer_id})
        except Exception:
            return None
