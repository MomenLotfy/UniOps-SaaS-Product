import redis.asyncio as aioredis

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        from app.config import get_settings

        settings = get_settings()
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


async def cache_set(key: str, value: str, ttl: int = 300) -> None:
    r = await get_redis()
    await r.set(key, value, ex=ttl)


async def cache_get(key: str) -> str | None:
    r = await get_redis()
    return await r.get(key)


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


async def publish(channel: str, message: str) -> None:
    r = await get_redis()
    await r.publish(channel, message)
