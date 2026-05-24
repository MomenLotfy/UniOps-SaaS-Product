from __future__ import annotations
"""Stripe webhook receiver — handles full subscription lifecycle."""
from fastapi import APIRouter, Request, Header, HTTPException
from app.config import settings
from app.utils.logger import logger

router = APIRouter()

HANDLED_EVENTS = {
    "checkout.session.completed",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.trial_will_end",
}


@router.post("/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None, alias="stripe-signature")):
    body = await request.body()

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — rejecting webhook")
        raise HTTPException(status_code=400, detail="Stripe webhook not configured")

    # Verify signature
    try:
        import stripe as stripe_lib
        event = stripe_lib.Webhook.construct_event(
            body, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.warning(f"Stripe webhook signature invalid: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    event_data = event["data"]["object"]
    logger.info(f"Stripe webhook: {event_type} id={event['id']}")

    if event_type not in HANDLED_EVENTS:
        return {"received": True, "handled": False}

    try:
        from app.core.database import AsyncSessionLocal
        from app.services.billing_service import BillingService
        async with AsyncSessionLocal() as db:
            svc = BillingService(db)
            await svc.handle_webhook(event_type, event_data)
            await db.commit()
        logger.info(f"Stripe webhook processed: {event_type}")
    except Exception as e:
        logger.error(f"Stripe webhook error ({event_type}): {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"received": True, "handled": True, "type": event_type}
