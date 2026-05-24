"""Slack webhook receiver — handles Slack events and slash commands."""
import json
import hashlib
import hmac
import time
from fastapi import APIRouter, Request, HTTPException, Header
from app.config import settings
from app.utils.logger import logger

router = APIRouter()


@router.post("/slack")
async def slack_webhook(
    request: Request,
    x_slack_request_timestamp: str = Header(None),
    x_slack_signature: str = Header(None),
):
    body = await request.body()

    if settings.SLACK_BOT_TOKEN and x_slack_request_timestamp and x_slack_signature:
        try:
            ts = int(x_slack_request_timestamp)
            if abs(time.time() - ts) > 300:
                raise HTTPException(status_code=401, detail="Request timestamp too old")

            sig_basestring = f"v0:{ts}:{body.decode()}"
            expected = "v0=" + hmac.new(
                settings.SLACK_BOT_TOKEN.encode(), sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected, x_slack_signature):
                raise HTTPException(status_code=401, detail="Invalid Slack signature")
        except HTTPException:
            raise
        except Exception:
            pass

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = json.loads(body)
    else:
        from urllib.parse import parse_qs
        form_data = parse_qs(body.decode())
        payload = {k: v[0] if len(v) == 1 else v for k, v in form_data.items()}
        if "payload" in payload:
            payload = json.loads(payload["payload"])

    event_type = payload.get("type")

    if event_type == "url_verification":
        return {"challenge": payload.get("challenge")}

    if event_type == "event_callback":
        event = payload.get("event", {})
        logger.info(f"Slack event: {event.get('type')}")
        await _handle_slack_event(event)
        return {"ok": True}

    logger.debug(f"Slack webhook: type={event_type}")
    return {"ok": True}


async def _handle_slack_event(event: dict):
    event_type = event.get("type")
    if event_type == "app_mention":
        text = event.get("text", "")
        logger.info(f"Slack mention received: {text[:100]}")
    elif event_type == "message":
        logger.debug("Slack message event received")
