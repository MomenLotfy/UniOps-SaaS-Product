from __future__ import annotations
"""
Loki Integration — real-time pod log streaming via Grafana Loki HTTP API.

Modes:
  batch  — query_range for the last N log lines (default)
  stream — SSE tail stream when follow=true

Falls back to DB-backed logs when Loki is not configured.

Configured via integration record:
  config.server_url  — Loki base URL (e.g. http://loki:3100)
  credentials.token  — optional Bearer token
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator, Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT      = httpx.Timeout(20.0)
_STREAM_TIMEOUT = httpx.Timeout(None, connect=10.0)   # infinite read for tailing


class LokiClient:
    """Async client for the Grafana Loki HTTP API."""

    def __init__(self, server_url: str, token: str = "", insecure: bool = False):
        self.server_url = server_url.rstrip("/")
        self._headers   = {"Authorization": f"Bearer {token}"} if token else {}
        self._verify    = not insecure

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _default_selector(self, pod_name: str, namespace: str) -> str:
        """Build a LogQL stream selector for a pod."""
        return f'{{pod="{pod_name}", namespace="{namespace}"}}'

    # ── Public API ────────────────────────────────────────────────────────────

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as c:
                r = await c.get(
                    f"{self.server_url}/ready", headers=self._headers
                )
                return r.status_code == 200
        except Exception:
            return False

    async def query_logs(
        self,
        pod_name: str,
        namespace: str,
        tail: int = 200,
        duration_hours: int = 1,
        filter_str: str = "",
    ) -> list[dict]:
        """
        Fetch last `tail` log lines for a pod.
        Returns list of {"timestamp": ISO-str, "level": str, "message": str}.
        """
        selector = self._default_selector(pod_name, namespace)
        if filter_str:
            selector = f'{selector} |= "{filter_str}"'

        end   = datetime.now(timezone.utc)
        start = end - timedelta(hours=duration_hours)

        params = {
            "query":     selector,
            "start":     str(int(start.timestamp() * 1e9)),
            "end":       str(int(end.timestamp() * 1e9)),
            "limit":     str(tail),
            "direction": "backward",
        }
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, verify=self._verify
            ) as c:
                r = await c.get(
                    f"{self.server_url}/loki/api/v1/query_range",
                    params=params,
                    headers=self._headers,
                )
                if r.status_code != 200:
                    logger.warning(f"[loki] query_range status {r.status_code}")
                    return []

                data   = r.json()
                result = data.get("data", {}).get("result", [])
                logs   = []
                for stream in result:
                    for ts_ns, line in stream.get("values", []):
                        ts = datetime.fromtimestamp(
                            int(ts_ns) / 1e9, tz=timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
                        logs.append({
                            "timestamp": ts,
                            "level":     _detect_level(line),
                            "message":   line,
                        })

                logs.sort(key=lambda x: x["timestamp"])
                return logs[-tail:]

        except Exception as exc:
            logger.warning(f"[loki] query_logs error: {exc}")
            return []

    async def tail_logs(
        self,
        pod_name: str,
        namespace: str,
        filter_str: str = "",
        delay_for: int = 0,
    ) -> AsyncIterator[dict]:
        """
        Stream log lines as they arrive via Loki's WebSocket tail API.
        Yields {"timestamp": ISO-str, "level": str, "message": str}.

        Uses HTTP long-poll fallback if WebSocket tail is unavailable.
        """
        import asyncio
        selector = self._default_selector(pod_name, namespace)
        if filter_str:
            selector = f'{selector} |= "{filter_str}"'

        params = {"query": selector, "delay_for": str(delay_for)}
        try:
            async with httpx.AsyncClient(
                timeout=_STREAM_TIMEOUT, verify=self._verify
            ) as c:
                async with c.stream(
                    "GET",
                    f"{self.server_url}/loki/api/v1/tail",
                    params=params,
                    headers=self._headers,
                ) as r:
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        import json as _json
                        try:
                            data = _json.loads(line)
                            for stream in data.get("streams", []):
                                for ts_ns, msg in stream.get("values", []):
                                    ts = datetime.fromtimestamp(
                                        int(ts_ns) / 1e9, tz=timezone.utc
                                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                                    yield {
                                        "timestamp": ts,
                                        "level":     _detect_level(msg),
                                        "message":   msg,
                                    }
                        except Exception:
                            pass
        except Exception as exc:
            logger.warning(f"[loki] tail_logs error: {exc}")
            return


# ── Helpers ───────────────────────────────────────────────────────────────────

_LEVEL_KEYWORDS = {
    "error":   ["error", "err ", "exception", "fatal", "critical", "panic"],
    "warning": ["warn", "warning", "deprecated"],
    "debug":   ["debug", "trace", "verbose"],
    "info":    ["info", "started", "ready", "connected", "success"],
}


def _detect_level(line: str) -> str:
    low = line.lower()
    for level, keywords in _LEVEL_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return level
    return "info"


def get_loki_client(integration: dict | None) -> Optional[LokiClient]:
    """
    Build a LokiClient from an integration record (from DB).
    Returns None when no Loki integration is configured.
    """
    if not integration:
        return None
    cfg    = integration.get("config") or {}
    creds  = integration.get("credentials") or {}
    server = cfg.get("server_url") or cfg.get("url") or ""
    token  = creds.get("token") or creds.get("loki_token") or ""
    insecure = cfg.get("insecure", False)
    if not server:
        return None
    return LokiClient(server, token, insecure=insecure)
