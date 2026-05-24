"""Slack integration client — message delivery via Incoming Webhooks and Bot API."""
from typing import Optional
import httpx
from app.integrations.base import BaseIntegration
from app.utils.logger import logger


class SlackClient(BaseIntegration):
    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config.get("webhook_url", "")
        self.bot_token = config.get("bot_token", "")
        self._headers = {"Authorization": f"Bearer {self.bot_token}", "Content-Type": "application/json"}

    async def test_connection(self) -> bool:
        if self.bot_token:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://slack.com/api/auth.test",
                        headers=self._headers,
                    )
                    data = resp.json()
                    return data.get("ok", False)
            except Exception as e:
                logger.warning(f"Slack connection test failed: {e}")
                return False
        if self.webhook_url:
            return True
        return False

    async def sync(self) -> dict:
        return {"status": "ok"}

    async def send_message(self, text: str, channel: Optional[str] = None) -> bool:
        if self.webhook_url and not channel:
            return await self._send_via_webhook(text)
        if self.bot_token and channel:
            return await self._send_via_api(channel, text)
        return False

    async def _send_via_webhook(self, text: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.webhook_url, json={"text": text})
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Slack webhook send failed: {e}")
            return False

    async def _send_via_api(self, channel: str, text: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers=self._headers,
                    json={"channel": channel, "text": text},
                )
                data = resp.json()
                return data.get("ok", False)
        except Exception as e:
            logger.error(f"Slack API send failed: {e}")
            return False

    async def send_blocks(self, channel: str, blocks: list, text: str = "") -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers=self._headers,
                    json={"channel": channel, "blocks": blocks, "text": text},
                )
                data = resp.json()
                return data.get("ok", False)
        except Exception as e:
            logger.error(f"Slack blocks send failed: {e}")
            return False

    async def send_alert(self, title: str, message: str, severity: str, channel: Optional[str] = None) -> bool:
        emoji = {"critical": ":red_circle:", "high": ":orange_circle:", "medium": ":yellow_circle:", "low": ":white_circle:"}.get(severity, ":grey_circle:")
        text = f"{emoji} *[{severity.upper()}] {title}*\n{message}"
        return await self.send_message(text, channel)
