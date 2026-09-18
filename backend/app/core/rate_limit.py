from __future__ import annotations
"""
In-process sliding-window rate limiter for high-risk DevOps endpoints.

This complements the global middleware rate limiter (which is a coarse
per-IP budget and fails open when Redis is unavailable).  For destructive or
high-risk actions — pod exec, restart, delete, deployment scale, ArgoCD
sync/rollback, pipeline rerun/cancel, service creation — we enforce a strict
per-user (or per-tenant) budget that ALWAYS works, even without Redis.

Design:
  - Sliding window, in-memory, asyncio-safe.
  - Keyed by (scope, user_id) — one user cannot DOS the K8s API through
    repeated restarts/execs.
  - Returns 429 with a real error — never silently allows over-budget calls.

Limitation: budgets are enforced through Redis when reachable (shared
across ALL workers — the production topology).  The per-process memory path
is only a fallback for short Redis outages and is NOT enforced globally
across workers; production deployments MUST run Redis for globally-correct
budgets (P1_PRODUCTION_RELIABILITY_REPORT.md).
"""
import time
import asyncio
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_current_active_user


class _Bucket:
    __slots__ = ("hits",)

    def __init__(self) -> None:
        self.hits: deque[float] = deque()


_buckets: dict[tuple[str, str], _Bucket] = defaultdict(_Bucket)
_lock = asyncio.Lock()

# Prune bookkeeping so the dict doesn't grow unboundedly
_LAST_PRUNE: list[float] = [time.monotonic()]
_PRUNE_INTERVAL_S = 600.0



async def _redis_count(scope: str, identity: str, max_requests: int,
                       window_seconds: int, prefix: str) -> bool:
    """Fixed-window counter in Redis, shared across ALL workers.

    Returns True when the request is WITHIN budget (and increments),
    False when the budget is exceeded (and increments).  Raises on ANY
    Redis failure so callers can fail over to the per-process memory path.
    """
    from app.core.redis_client import get_redis

    bucket_id = int(time.monotonic() // window_seconds)
    key = f"rl:{prefix}:{scope}:{identity}:{bucket_id}"
    redis = await get_redis()
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    results = await pipe.execute()
    return int(results[0]) <= max_requests

def rate_limit(scope: str, max_requests: int, window_seconds: int):
    """
    FastAPI dependency factory enforcing a sliding-window rate limit.

    Usage:
        @router.post("/{pod_id}/exec",
                     dependencies=[Depends(rate_limit("pod.exec", 10, 60))])
    """

    async def _check(
        current_user: Annotated[dict, Depends(get_current_active_user)],
    ) -> None:
        user_id = str(current_user.get("user_id") or "anonymous")
        now = time.monotonic()
        try:
            within = await _redis_count(scope, user_id, max_requests,
                                        window_seconds, prefix="user")
        except Exception:
            within = None  # Redis down → per-process memory path below
        if within is False:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(f"Rate limit exceeded for scope '{scope}': max "
                        f"{max_requests} per {window_seconds}s."),
                headers={"Retry-After": str(window_seconds)},
            )
        if within is True:
            return
        key = (scope, user_id)
        cutoff = now - window_seconds

        async with _lock:
            # Periodic global prune of stale buckets
            if now - _LAST_PRUNE[0] > _PRUNE_INTERVAL_S:
                for k in list(_buckets.keys()):
                    b = _buckets[k]
                    while b.hits and b.hits[0] < now - 3600:
                        b.hits.popleft()
                    if not b.hits:
                        _buckets.pop(k, None)
                _LAST_PRUNE[0] = now

            bucket = _buckets[key]
            while bucket.hits and bucket.hits[0] < cutoff:
                bucket.hits.popleft()

            if len(bucket.hits) >= max_requests:
                retry_after = 0
                if bucket.hits:
                    retry_after = max(1, int(window_seconds - (now - bucket.hits[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Rate limit exceeded for '{scope}': "
                        f"max {max_requests} per {window_seconds}s. "
                        f"Retry in {retry_after}s."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.hits.append(now)

    return _check


def ip_rate_limit(scope: str, max_requests: int, window_seconds: int):
    """Always-on IP-keyed sliding-window limiter for UNAUTHENTICATED
    endpoints (login / register / password reset / 2FA).

    The global per-IP middleware intentionally fails OPEN when Redis is
    unavailable (availability over enforcement).  Credential attacks are
    too security-critical to share that trade-off, so these limits work
    without Redis — per-process budget, same documented limitation as the
    user-keyed limiter above.
    """

    async def _check(request: Request) -> None:
        # Honor X-Forwarded-For only behind the configured trusted proxies;
        # otherwise fall back to the direct peer.
        ip = request.client.host if request.client else "unknown"
        fwd = request.headers.get("x-forwarded-for")
        if fwd and ip in _trusted_proxy_pool():
            ip = fwd.split(",")[0].strip()

        now = time.monotonic()
        try:
            within = await _redis_count(scope, ip, max_requests,
                                        window_seconds, prefix="auth")
        except Exception:
            within = None  # Redis unavailable → per-process fallback
        if within is False:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(f"Too many attempts: max {max_requests} per "
                        f"{window_seconds}s."),
                headers={"Retry-After": str(window_seconds)},
            )
        if within is True:
            return
        key = (scope, ip)
        cutoff = now - window_seconds

        async with _lock:
            if now - _LAST_PRUNE[0] > _PRUNE_INTERVAL_S:
                for k in list(_buckets.keys()):
                    b = _buckets[k]
                    while b.hits and b.hits[0] < now - 3600:
                        b.hits.popleft()
                    if not b.hits:
                        _buckets.pop(k, None)
                _LAST_PRUNE[0] = now

            bucket = _buckets[key]
            while bucket.hits and bucket.hits[0] < cutoff:
                bucket.hits.popleft()

            if len(bucket.hits) >= max_requests:
                retry_after = max(1, int(window_seconds - (now - bucket.hits[0]))) if bucket.hits else 0
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(f"Too many attempts: max {max_requests} per "
                            f"{window_seconds}s. Retry in {retry_after}s."),
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.hits.append(now)

    return _check


def _trusted_proxy_pool() -> set[str]:
    from app.config import get_settings
    try:
        return set(get_settings().RATE_LIMIT_TRUSTED_PROXIES or [])
    except Exception:
        return set()
