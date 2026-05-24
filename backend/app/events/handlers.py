import json
from app.events.events import EventType
from app.utils.logger import logger


async def handle_event(channel: str, message: str) -> None:
    try:
        data = json.loads(message)
        event_type = data.get("event")
        payload = data.get("payload", {})
        tenant_id = data.get("tenant_id")
        logger.debug(f"Event received: {event_type} for tenant {tenant_id}")
    except Exception as e:
        logger.error(f"Error handling event: {e}")
