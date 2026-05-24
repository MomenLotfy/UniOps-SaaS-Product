from __future__ import annotations
"""
Email client — sends transactional emails via SendGrid.
Falls back to console logging when SENDGRID_API_KEY is not set (dev mode).
"""
from typing import Optional
import httpx
from app.utils.logger import logger


class EmailClient:
    SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self, api_key: str, from_email: str = "noreply@uniops.io", from_name: str = "UniOps"):
        self.api_key    = api_key
        self.from_email = from_email
        self.from_name  = from_name

    # ── Core send ─────────────────────────────────────────────────────────────

    async def send(
        self,
        to_email: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        if not self.api_key:
            # Dev mode — just log it
            logger.info(f"[EMAIL — no key] To: {to_email} | Subject: {subject}")
            return True   # return True so callers don't fail in dev

        payload: dict = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from":    {"email": self.from_email, "name": self.from_name},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        }
        if text:
            payload["content"].insert(0, {"type": "text/plain", "value": text})
        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self.SENDGRID_URL,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            if resp.status_code in (200, 202):
                logger.info(f"Email sent → {to_email}: {subject}")
                return True
            logger.error(f"SendGrid {resp.status_code}: {resp.text[:300]}")
            return False
        except Exception as e:
            logger.error(f"Email send failed to {to_email}: {e}")
            return False

    # ── Templates ─────────────────────────────────────────────────────────────

    async def send_welcome(
        self,
        to_email: str,
        user_name: str,
        company_name: str,
        login_url: str,
    ) -> bool:
        return await self.send(
            to_email,
            subject=f"Welcome to UniOps, {user_name.split()[0]}! 🚀",
            html=_template("Welcome to UniOps", f"""
                <p>Hi <strong>{user_name}</strong>,</p>
                <p>Your UniOps account for <strong>{company_name}</strong> is ready.</p>
                <p>UniOps gives your team a unified view of DevOps, Security, Cost, and ML insights — all in one dashboard.</p>
                {_button("Open Dashboard", login_url)}
                <p style="color:#888;font-size:13px;margin-top:24px;">
                    Need help getting started? Reply to this email — we're here.
                </p>
            """),
        )

    async def send_invite(
        self,
        to_email: str,
        invited_by_name: str,
        company_name: str,
        role: str,
        accept_url: str,
        expires_hours: int = 72,
    ) -> bool:
        return await self.send(
            to_email,
            subject=f"You're invited to join {company_name} on UniOps",
            html=_template("Team Invitation", f"""
                <p><strong>{invited_by_name}</strong> invited you to join
                <strong>{company_name}</strong> on UniOps as a
                <strong>{role.replace('_', ' ').title()}</strong>.</p>
                <p>UniOps is a unified DevOps + Security + Cost management platform.</p>
                {_button("Accept Invitation", accept_url)}
                <p style="color:#888;font-size:13px;margin-top:16px;">
                    This invitation expires in {expires_hours} hours.
                    If you didn't expect this, you can ignore this email.
                </p>
            """),
        )

    async def send_password_reset(
        self,
        to_email: str,
        user_name: str,
        reset_url: str,
    ) -> bool:
        return await self.send(
            to_email,
            subject="Reset your UniOps password",
            html=_template("Password Reset", f"""
                <p>Hi <strong>{user_name}</strong>,</p>
                <p>We received a request to reset your UniOps password.
                Click the button below to choose a new password.</p>
                {_button("Reset Password", reset_url)}
                <p style="color:#888;font-size:13px;margin-top:16px;">
                    This link expires in 1 hour. If you didn't request a
                    password reset, you can safely ignore this email.
                </p>
            """),
        )

    async def send_alert_notification(
        self,
        to_email: str,
        user_name: str,
        alert_title: str,
        alert_severity: str,
        alert_message: str,
        dashboard_url: str,
    ) -> bool:
        severity_color = {
            "critical": "#ef4444",
            "high":     "#f97316",
            "medium":   "#f59e0b",
            "low":      "#3b82f6",
        }.get(alert_severity, "#6b7280")

        return await self.send(
            to_email,
            subject=f"[{alert_severity.upper()}] UniOps Alert: {alert_title}",
            html=_template("Security Alert", f"""
                <p>Hi <strong>{user_name}</strong>,</p>
                <div style="border-left:4px solid {severity_color};padding:12px 16px;
                     background:#1a1a2e;border-radius:0 8px 8px 0;margin:16px 0;">
                    <div style="font-size:11px;font-weight:600;color:{severity_color};
                         text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">
                        {alert_severity} severity
                    </div>
                    <div style="font-size:16px;font-weight:600;color:#e2e8f0;margin-bottom:6px;">
                        {alert_title}
                    </div>
                    <div style="font-size:14px;color:#94a3b8;">{alert_message}</div>
                </div>
                {_button("View Alert →", dashboard_url)}
                <p style="color:#888;font-size:13px;margin-top:16px;">
                    To manage alert preferences, go to Settings → Notifications.
                </p>
            """),
        )

    async def send_subscription_confirmation(
        self,
        to_email: str,
        user_name: str,
        plan_name: str,
        amount: float,
        next_billing_date: str,
        portal_url: str,
    ) -> bool:
        return await self.send(
            to_email,
            subject=f"UniOps {plan_name} Plan — Subscription Confirmed",
            html=_template("Subscription Confirmed ✓", f"""
                <p>Hi <strong>{user_name}</strong>,</p>
                <p>Your <strong>UniOps {plan_name} Plan</strong> subscription is now active.</p>
                <div style="background:#1a2744;border:1px solid #2d3f6b;border-radius:8px;
                     padding:16px;margin:16px 0;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                        <span style="color:#94a3b8">Plan</span>
                        <span style="color:#e2e8f0;font-weight:600">{plan_name}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                        <span style="color:#94a3b8">Amount</span>
                        <span style="color:#e2e8f0;font-weight:600">${amount:.2f}/month</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;">
                        <span style="color:#94a3b8">Next billing</span>
                        <span style="color:#e2e8f0">{next_billing_date}</span>
                    </div>
                </div>
                {_button("Manage Subscription", portal_url)}
            """),
        )

    async def send_trial_ending(
        self,
        to_email: str,
        user_name: str,
        days_left: int,
        upgrade_url: str,
    ) -> bool:
        return await self.send(
            to_email,
            subject=f"Your UniOps trial ends in {days_left} day{'s' if days_left != 1 else ''}",
            html=_template("Trial Ending Soon", f"""
                <p>Hi <strong>{user_name}</strong>,</p>
                <p>Your UniOps free trial ends in <strong>{days_left} day{'s' if days_left != 1 else ''}</strong>.</p>
                <p>Upgrade now to keep access to all dashboards, integrations, and ML insights.</p>
                {_button("Upgrade Now →", upgrade_url)}
                <p style="color:#888;font-size:13px;margin-top:16px;">
                    Questions? Reply to this email — we'd love to help.
                </p>
            """),
        )


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _button(text: str, url: str) -> str:
    return f"""
        <div style="margin:24px 0;">
            <a href="{url}" style="background:#3b82f6;color:#ffffff;padding:12px 24px;
               border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;
               display:inline-block;">{text}</a>
        </div>
    """


def _template(title: str, body: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
    <body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="max-width:560px;margin:0 auto;padding:40px 20px;">
            <!-- Logo -->
            <div style="margin-bottom:32px;">
                <div style="display:inline-flex;align-items:center;gap:10px;">
                    <div style="width:36px;height:36px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);
                         border-radius:8px;display:flex;align-items:center;justify-content:center;">
                        <span style="color:white;font-weight:700;font-size:16px;">U</span>
                    </div>
                    <span style="color:#e2e8f0;font-size:18px;font-weight:700;">UniOps</span>
                </div>
            </div>
            <!-- Card -->
            <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:32px;">
                <h1 style="color:#f1f5f9;font-size:22px;font-weight:700;margin:0 0 20px;">{title}</h1>
                <div style="color:#cbd5e1;font-size:15px;line-height:1.7;">
                    {body}
                </div>
            </div>
            <!-- Footer -->
            <div style="text-align:center;margin-top:24px;color:#475569;font-size:12px;">
                <p>UniOps Control Tower · <a href="https://uniops.io" style="color:#3b82f6;">uniops.io</a></p>
                <p>You're receiving this because you have an account at UniOps.</p>
            </div>
        </div>
    </body>
    </html>
    """
