"""
Sprint 4 — Production-grade rate limiting.

Replaces the per-IP only ``RateLimitMiddleware`` with a per-tenant +
per-endpoint Redis-backed limiter.

Design:

  - **Burst window**   — 60-second sliding window measured by a
    Redis counter keyed on ``(scope, identity, bucket_id)``.  Burst
    limit configurable via ``RATE_LIMIT_BURST_PER_MINUTE``.
  - **Sustained window** — 3600-second sliding window measured by a
    second Redis counter.  Sustained limit configurable via
    ``RATE_LIMIT_SUSTAINED_PER_HOUR``.
  - **Identity**       — tenant_id from the JWT (preferred), else
    client IP from ``X-Forwarded-For`` (when the immediate hop is a
    trusted proxy), else ``request.client.host``.
  - **Endpoint**       — normalises ``request.method`` + the first
    route segment after the version prefix (e.g. ``POST /api/v1/auth``
    -> ``POST:/api/v1/auth``).  This keeps cardinality bounded while
    still giving per-endpoint limits.
  - **Fail-open**      — Redis outages MUST NOT take the API down.
    On exception we log + increment a counter and fall through to
    the next handler.  Metrics (not blocking requests) let the
    on-call see the failure.
  - **Trusted proxies** — ``X-Forwarded-For`` is honored only when
    ``request.client.host`` matches an entry in
    ``RATE_LIMIT_TRUSTED_PROXIES``.  Otherwise the header is ignored.
  - **Headers**        — 429 responses include:
      ``Retry-After``, ``X-RateLimit-Limit``,
      ``X-RateLimit-Remaining``, ``X-RateLimit-Reset``,
      ``X-RateLimit-Scope`` (which window tripped).

The limiter is wired in ``app/main.py`` as ASGI middleware so it
sees the original ``Request`` (not the wrapped one) and runs BEFORE
all other middleware.
"""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

# Window lengths in seconds
_BURST_WINDOW_SECONDS = 60
_SUSTAINED_WINDOW_SECONDS = 3600

# Exempt paths (probes, OpenAPI docs, static)
_EXEMPT_PATHS = frozenset(
    {
        "/api/v1/health",
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/health/startup",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }
)


def _extract_tenant_id(request: Request) -> str | None:
    """Read tenant_id from the bearer token WITHOUT invoking the
    ``Depends(get_current_user)`` machinery (which would fail the
    request on expired tokens before rate-limiting has a chance to
    run).  We do a best-effort decode; failures are not rate-limited
    by tenant.

    Note: this is intentionally lightweight — the JWT is decoded
    here only for the tenant_id claim so the limiter can key on it.
    Full authentication happens later in the dependency stack.
    """
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    try:
        # Local import keeps the middleware import graph small.
        from app.core.security import decode_token

        payload = decode_token(token)
        tid = payload.get("tenant_id") if isinstance(payload, dict) else None
        return str(tid) if tid else None
    except Exception:
        return None


def _extract_client_ip(request: Request, trusted_proxies: list[str]) -> str:
    """
    Best-effort client IP extraction.

      1. If the immediate peer (``request.client.host``) is a trusted
         proxy, read ``X-Forwarded-For`` and take the first entry.
      2. Otherwise use ``request.client.host``.

    Trusted-proxy matching is by exact string equality OR by CIDR
    membership (e.g. ``10.0.0.0/8``).
    """
    peer = request.client.host if request.client else "unknown"

    if trusted_proxies:
        # Caller configured at least one trusted-proxy entry.  Walk
        # the list — first match wins (this lets a more-specific
        # entry override a broad CIDR).
        trusted = False
        for entry in trusted_proxies:
            try:
                if "/" in entry:
                    if ipaddress.ip_address(peer) in ipaddress.ip_network(entry, strict=False):
                        trusted = True
                        break
                elif peer == entry:
                    trusted = True
                    break
            except ValueError:
                continue
        if not trusted:
            return peer
    else:
        # No trusted proxies configured — never honour X-Forwarded-For.
        return peer

    fwd = request.headers.get("x-forwarded-for")
    if not fwd:
        return peer
    first = fwd.split(",")[0].strip()
    return first or peer


def _endpoint_key(request: Request) -> str:
    """Normalise the endpoint for rate-limit keying.

    We use the first three path segments so requests to
    ``/api/v1/security/decisions/{uuid}`` all share the same
    endpoint key (low cardinality).
    """
    path = request.url.path.rstrip("/") or "/"
    parts = path.strip("/").split("/")
    if len(parts) <= 3:
        endpoint = "/" + "/".join(parts)
    else:
        endpoint = "/" + "/".join(parts[:4])
    return f"{request.method.upper()}:{endpoint}"


class _SlidingWindow:
    """One Redis-backed sliding window counter."""

    def __init__(self, redis_key: str, limit: int, window_seconds: int) -> None:
        self.key = redis_key
        self.limit = limit
        self.window = window_seconds

    async def hit(self) -> tuple[bool, int, int]:
        """
        Increment the counter and return ``(allowed, remaining, reset_seconds)``.

        ``allowed`` is False when ``count > limit``.  ``reset_seconds``
        is the number of seconds until the current window expires
        (used as the ``Retry-After`` value).
        """
        redis = await get_redis()
        # Atomic-ish: INCR + EXPIRE-on-first-write + TTL read.
        pipe = redis.pipeline()
        pipe.incr(self.key)
        pipe.expire(self.key, self.window, nx=True)  # set TTL only on first incr
        pipe.ttl(self.key)
        results = await pipe.execute()
        count = int(results[0])
        ttl = int(results[2])
        if ttl < 0:
            ttl = self.window
        remaining = max(self.limit - count, 0)
        return (count <= self.limit, remaining, ttl)


class RateLimiter:
    """Composite limiter: burst (60s) + sustained (3600s).

    Both windows are checked per ``(scope, identity)`` pair and a
    per-endpoint burst window is also enforced.  ``scope`` is one of
    ``tenant`` or ``ip``.
    """

    def __init__(self) -> None:
        # Disable everything if explicitly turned off OR if the
        # baseline per-minute value is non-positive — both are the
        # supported way for operators to opt out.
        per_minute = int(getattr(settings, "RATE_LIMIT_PER_MINUTE", 60) or 60)
        self._enabled = bool(getattr(settings, "RATE_LIMIT_ENABLED", True))
        if per_minute <= 0:
            self._enabled = False

        self._prefix = settings.RATE_LIMIT_KEY_PREFIX
        # Per-IP caps (the established baseline).  Sustained is
        # derived from the per-minute number so operators only have
        # to think about one knob.
        self._ip_burst = per_minute
        self._ip_sustained = per_minute * 60
        # Per-tenant overrides
        self._tenant_burst = int(settings.RATE_LIMIT_TENANT_BURST_PER_MINUTE)
        self._tenant_sustained = int(settings.RATE_LIMIT_TENANT_SUSTAINED_PER_HOUR)
        # Per-endpoint caps
        self._endpoint_burst = int(settings.RATE_LIMIT_BURST_PER_MINUTE)
        # Trusted proxies
        self._trusted: list[str] = list(settings.RATE_LIMIT_TRUSTED_PROXIES or [])

    async def check(self, request: Request) -> tuple[bool, dict[str, str]]:
        """
        Run the rate-limit policy.

        Returns ``(allowed, headers)``.  When ``allowed`` is False
        the caller MUST respond 429 with the returned headers.
        """
        if not self._enabled:
            return True, {}

        path = request.url.path
        if path in _EXEMPT_PATHS:
            return True, {}
        if path.startswith("/ws/"):
            return True, {}

        tenant_id = _extract_tenant_id(request)
        client_ip = _extract_client_ip(request, self._trusted)
        endpoint = _endpoint_key(request)

        if tenant_id:
            scope = "tenant"
            identity = tenant_id
            burst_limit = self._tenant_burst
            sustained_limit = self._tenant_sustained
        else:
            scope = "ip"
            identity = client_ip
            burst_limit = self._ip_burst
            sustained_limit = self._ip_sustained

        burst_key = f"{self._prefix}:burst:{scope}:{identity}:{_BURST_WINDOW_SECONDS}"
        sustained_key = f"{self._prefix}:sust:{scope}:{identity}:{_SUSTAINED_WINDOW_SECONDS}"

        try:
            burst = _SlidingWindow(burst_key, burst_limit, _BURST_WINDOW_SECONDS)
            sustained = _SlidingWindow(sustained_key, sustained_limit, _SUSTAINED_WINDOW_SECONDS)

            burst_ok, burst_remaining, burst_ttl = await burst.hit()
            if not burst_ok:
                return False, _build_headers(
                    scope="burst",
                    limit=burst_limit,
                    remaining=0,
                    reset=burst_ttl,
                    identity=identity,
                    endpoint=endpoint,
                )

            sustained_ok, sustained_remaining, sustained_ttl = await sustained.hit()
            if not sustained_ok:
                return False, _build_headers(
                    scope="sustained",
                    limit=sustained_limit,
                    remaining=0,
                    reset=sustained_ttl,
                    identity=identity,
                    endpoint=endpoint,
                )

            ep_burst_key = (
                f"{self._prefix}:epburst:{scope}:{identity}:{_BURST_WINDOW_SECONDS}:{endpoint}"
            )
            ep_burst = _SlidingWindow(ep_burst_key, self._endpoint_burst, _BURST_WINDOW_SECONDS)
            ep_ok, ep_remaining, ep_ttl = await ep_burst.hit()
            if not ep_ok:
                return False, _build_headers(
                    scope="endpoint-burst",
                    limit=self._endpoint_burst,
                    remaining=0,
                    reset=ep_ttl,
                    identity=identity,
                    endpoint=endpoint,
                )

        except Exception:
            # Fail-open: never 5xx the world because Redis is down.
            logger.exception("rate limiter degraded (fail-open)")
            return True, {}

        return True, {
            "X-RateLimit-Limit": str(burst_limit),
            "X-RateLimit-Remaining": str(min(burst_remaining, sustained_remaining, ep_remaining)),
            "X-RateLimit-Reset": str(burst_ttl),
            "X-RateLimit-Scope": scope,
        }


def _build_headers(
    *,
    scope: str,
    limit: int,
    remaining: int,
    reset: int,
    identity: str,
    endpoint: str,
) -> dict[str, str]:
    return {
        "Retry-After": str(reset),
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset),
        "X-RateLimit-Scope": scope,
        # Standard rate-limit headers (draft-ietf-httpapi-ratelimit-headers)
        "RateLimit-Limit": str(limit),
        "RateLimit-Remaining": str(remaining),
        "RateLimit-Reset": str(reset),
        "X-RateLimit-Policy": f"{scope};{identity};{endpoint}",
    }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that delegates policy decisions to ``RateLimiter``."""

    def __init__(self, app: Any, limiter: RateLimiter | None = None) -> None:
        super().__init__(app)
        self._limiter = limiter or RateLimiter()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            allowed, headers = await self._limiter.check(request)
        except Exception:
            logger.exception("RateLimitMiddleware.check crashed (fail-open)")
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Rate limit exceeded",
                    "code": "RATE_LIMITED",
                    "scope": headers.get("X-RateLimit-Scope"),
                    "retry_after_seconds": int(headers.get("Retry-After", "1")),
                },
                headers=headers,
            )

        response = await call_next(request)
        for k, v in headers.items():
            # Don't overwrite headers the app deliberately set
            if k.lower() not in {h.lower() for h in response.headers.keys()}:
                response.headers[k] = v
        return response


__all__ = ["RateLimiter", "RateLimitMiddleware"]
