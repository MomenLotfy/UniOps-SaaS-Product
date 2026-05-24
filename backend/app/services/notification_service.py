from __future__ import annotations
"""
Notification service — coordinates email, Slack, and WebSocket notifications.
Called by: auth_service, billing_service, alert_service, user_service.
"""
from typing import Optional
from app.utils.logger import logger
from app.config import settings


def _email() -> "EmailClient":
    from app.integrations.email.client import EmailClient
    return EmailClient(
        api_key    = settings.SENDGRID_API_KEY,
        from_email = settings.EMAIL_FROM,
        from_name  = "UniOps",
    )


def _app_url(path: str = "") -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}{path}"


class NotificationService:

    # ── Auth emails ───────────────────────────────────────────────────────────

    async def send_welcome(self, to_email: str, user_name: str, company_name: str) -> bool:
        try:
            return await _email().send_welcome(
                to_email    = to_email,
                user_name   = user_name,
                company_name= company_name,
                login_url   = _app_url("/auth/login"),
            )
        except Exception as e:
            logger.error(f"send_welcome failed: {e}")
            return False

    async def send_password_reset(self, to_email: str, user_name: str, reset_token: str) -> bool:
        reset_url = _app_url(f"/auth/reset-password?token={reset_token}")
        try:
            return await _email().send_password_reset(to_email, user_name, reset_url)
        except Exception as e:
            logger.error(f"send_password_reset failed: {e}")
            return False

    async def send_invite(
        self,
        to_email: str,
        invited_by_name: str,
        company_name: str,
        role: str,
        invite_token: str,
    ) -> bool:
        accept_url = _app_url(f"/auth/register?invite={invite_token}&email={to_email}")
        try:
            return await _email().send_invite(
                to_email        = to_email,
                invited_by_name = invited_by_name,
                company_name    = company_name,
                role            = role,
                accept_url      = accept_url,
            )
        except Exception as e:
            logger.error(f"send_invite failed: {e}")
            return False

    # ── Billing emails ────────────────────────────────────────────────────────

    async def send_subscription_confirmed(
        self,
        to_email: str,
        user_name: str,
        plan_name: str,
        amount: float,
        next_billing_date: str,
    ) -> bool:
        portal_url = _app_url("/settings/billing")
        try:
            return await _email().send_subscription_confirmation(
                to_email, user_name, plan_name, amount, next_billing_date, portal_url
            )
        except Exception as e:
            logger.error(f"send_subscription_confirmed failed: {e}")
            return False

    async def send_trial_ending(self, to_email: str, user_name: str, days_left: int) -> bool:
        upgrade_url = _app_url("/settings/billing")
        try:
            return await _email().send_trial_ending(to_email, user_name, days_left, upgrade_url)
        except Exception as e:
            logger.error(f"send_trial_ending failed: {e}")
            return False

    # ── Alert notifications ───────────────────────────────────────────────────

    async def notify_alert(self, tenant_id: str, alert: dict) -> None:
        """Send alert via WebSocket (always) + email + Slack (for critical/high)."""
        # 1. WebSocket — real-time in-app notification
        await self._ws(tenant_id, "alert.new", alert)

        severity = alert.get("severity", "low")
        if severity not in ("critical", "high"):
            return

        # 2. Email — to all admin users of this tenant
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.user import User
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(User).where(
                        User.tenant_id == tenant_id,
                        User.is_active == True,
                        User.role.in_(["admin", "security"]),
                    )
                )
                users = result.scalars().all()

            for user in users:
                await _email().send_alert_notification(
                    to_email      = user.email,
                    user_name     = user.full_name,
                    alert_title   = alert.get("title", "Security Alert"),
                    alert_severity= severity,
                    alert_message = alert.get("message", alert.get("description", "")),
                    dashboard_url = _app_url("/security"),
                )
        except Exception as e:
            logger.error(f"Alert email notification failed: {e}")

        # 3. Slack
        await self._slack(
            f":{severity}: *[{severity.upper()}]* {alert.get('title', 'Alert')}\n"
            f"{alert.get('message', alert.get('description', ''))}\n"
            f"<{_app_url('/security')}|View in UniOps →>"
        )

    async def notify_pipeline_failure(self, tenant_id: str, pipeline: dict) -> None:
        await self._ws(tenant_id, "pipeline.failed", pipeline)
        await self._slack(
            f":x: Pipeline *{pipeline.get('name')}* failed on `{pipeline.get('branch', 'main')}`\n"
            f"<{_app_url('/devops')}|View in UniOps →>"
        )

    async def notify_cost_anomaly(self, tenant_id: str, anomaly: dict) -> None:
        await self._ws(tenant_id, "cost.anomaly", anomaly)
        deviation = anomaly.get("deviation", 0)
        if deviation >= 30:
            await self._slack(
                f":moneybag: Cost anomaly: *{anomaly.get('service')}* is "
                f"*{deviation:.0f}%* above expected\n"
                f"Expected: ${anomaly.get('expected_cost', 0):.0f} | "
                f"Actual: ${anomaly.get('actual_cost', 0):.0f}\n"
                f"<{_app_url('/cost')}|View in UniOps →>"
            )

    async def notify_pod_crash(self, tenant_id: str, pod: dict) -> None:
        await self._ws(tenant_id, "pod.crashed", pod)
        if pod.get("restart_count", 0) >= 3:
            await self._slack(
                f":warning: Pod *{pod.get('name')}* in `{pod.get('namespace')}` "
                f"has restarted *{pod.get('restart_count')}* times\n"
                f"<{_app_url('/devops')}|View in UniOps →>"
            )

    # ── Low-level helpers ─────────────────────────────────────────────────────

    async def _ws(self, tenant_id: str, event: str, payload: dict) -> None:
        try:
            from app.api.v1.websocket.manager import ws_manager
            await ws_manager.send_to_tenant(tenant_id, {"event": event, "data": payload})
        except Exception as e:
            logger.debug(f"WebSocket notify failed: {e}")

    async def _slack(self, message: str, channel: Optional[str] = None) -> None:
        if not settings.SLACK_WEBHOOK_URL and not settings.SLACK_BOT_TOKEN:
            logger.debug(f"Slack not configured. Would send: {message[:80]}")
            return
        try:
            from app.integrations.slack.client import SlackClient
            client = SlackClient({
                "webhook_url": settings.SLACK_WEBHOOK_URL,
                "bot_token":   settings.SLACK_BOT_TOKEN,
            })
            await client.send_message(message, channel)
        except Exception as e:
            logger.error(f"Slack notify failed: {e}")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> bool:
        """Generic send — used by other services."""
        try:
            return await _email().send(to_email, subject, body_html, body_text)
        except Exception as e:
            logger.error(f"send_email failed: {e}")
            return False
