import json
from app.core.redis_client import get_redis
from app.events.events import EventType


class EventBus:
    async def publish(self, event: EventType, payload: dict, tenant_id: str | None = None) -> None:
        redis = await get_redis()
        message = json.dumps({"event": event.value, "tenant_id": tenant_id, "payload": payload})
        await redis.publish(f"events:{event.value}", message)

    async def subscribe(self, *channels: str):
        redis = await get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(*channels)
        return pubsub


event_bus = EventBus()
