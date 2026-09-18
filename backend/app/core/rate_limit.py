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

Limitation: in multi-process deployments the budget applies per-process.
Documented in DEVOPS_CENTER_PRODUCTION_VERIFICATION.md.
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
        key = (scope, user_id)
        now = time.monotonic()
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

        key = (scope, ip)
        now = time.monotonic()
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
