from __future__ import annotations
"""
Prometheus Integration — query real cluster metrics via Prometheus HTTP API.

Falls back to synthetic data when no Prometheus server is configured.
Configured via integration record:
  config.server_url  — Prometheus base URL (e.g. http://prometheus:9090)
  credentials.token  — optional Bearer token
"""
import math
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(15.0)


class PrometheusClient:
    """Async query client for the Prometheus HTTP API."""

    def __init__(self, server_url: str, token: str = "", insecure: bool = False):
        self.server_url = server_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._verify = not insecure

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _query_range(
        self,
        promql: str,
        start: datetime,
        end: datetime,
        step: str = "60s",
    ) -> list[dict]:
        """Run a range query. Returns list of {metric, values} dicts."""
        params = {
            "query": promql,
            "start": start.timestamp(),
            "end":   end.timestamp(),
            "step":  step,
        }
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, verify=self._verify
            ) as c:
                r = await c.get(
                    f"{self.server_url}/api/v1/query_range",
                    params=params,
                    headers=self._headers,
                )
                if r.status_code != 200:
                    logger.warning(f"[prometheus] query_range status {r.status_code}")
                    return []
                data = r.json()
                return data.get("data", {}).get("result", [])
        except Exception as exc:
            logger.warning(f"[prometheus] query_range error: {exc}")
            return []

    async def _query_instant(self, promql: str) -> list[dict]:
        """Instant query. Returns Prometheus result list."""
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, verify=self._verify
            ) as c:
                r = await c.get(
                    f"{self.server_url}/api/v1/query",
                    params={"query": promql},
                    headers=self._headers,
                )
                if r.status_code != 200:
                    return []
                return r.json().get("data", {}).get("result", [])
        except Exception as exc:
            logger.warning(f"[prometheus] instant query error: {exc}")
            return []

    # ── Public API ────────────────────────────────────────────────────────────

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as c:
                r = await c.get(
                    f"{self.server_url}/-/healthy", headers=self._headers
                )
                return r.status_code == 200
        except Exception:
            return False

    async def get_pod_cpu_timeseries(
        self,
        pod_name: str,
        namespace: str,
        duration_hours: int = 1,
        step: str = "60s",
    ) -> list[dict]:
        """
        CPU usage as percentage of requests over time.
        Returns list of {"timestamp": ISO-str, "cpu": float (0-100)}.
        """
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=duration_hours)

        promql = (
            f'rate(container_cpu_usage_seconds_total'
            f'{{pod="{pod_name}",namespace="{namespace}",container!="POD",container!=""}}[5m])'
            f' * 100'
        )
        results = await self._query_range(promql, start, end, step)
        if not results:
            return []

        series = results[0].get("values", [])
        return [
            {
                "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "cpu": round(float(val), 2),
            }
            for ts, val in series
        ]

    async def get_pod_memory_timeseries(
        self,
        pod_name: str,
        namespace: str,
        duration_hours: int = 1,
        step: str = "60s",
    ) -> list[dict]:
        """
        Memory usage as percentage of container memory limit.
        Returns list of {"timestamp": ISO-str, "memory": float (0-100)}.
        """
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=duration_hours)

        usage_promql = (
            f'container_memory_working_set_bytes'
            f'{{pod="{pod_name}",namespace="{namespace}",container!="POD",container!=""}}'
        )
        limit_promql = (
            f'container_spec_memory_limit_bytes'
            f'{{pod="{pod_name}",namespace="{namespace}",container!="POD",container!=""}}'
        )

        usage_res, limit_res = await _gather(
            self._query_range(usage_promql, start, end, step),
            self._query_range(limit_promql, start, end, step),
        )
        if not usage_res:
            return []

        usage_series = usage_res[0].get("values", [])
        limit_bytes = 0.0
        if limit_res:
            try:
                raw = limit_res[0].get("values", [])
                limit_bytes = float(raw[-1][1]) if raw else 0.0
            except Exception:
                pass

        def _mem_pct(bytes_val: float) -> float:
            if limit_bytes and limit_bytes > 0:
                return round(bytes_val / limit_bytes * 100, 2)
            return round(bytes_val / (1024 ** 3) * 10, 2)

        return [
            {
                "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "memory": _mem_pct(float(val)),
            }
            for ts, val in usage_series
        ]

    async def get_pod_metrics(
        self,
        pod_name: str,
        namespace: str,
        duration_hours: int = 1,
        step: str = "60s",
    ) -> list[dict]:
        """
        Combined CPU + Memory timeseries.
        Returns list of {"timestamp", "cpu", "memory"} merged by timestamp.
        """
        cpu_series, mem_series = await _gather(
            self.get_pod_cpu_timeseries(pod_name, namespace, duration_hours, step),
            self.get_pod_memory_timeseries(pod_name, namespace, duration_hours, step),
        )

        mem_by_ts = {p["timestamp"]: p["memory"] for p in mem_series}
        merged = []
        for p in cpu_series:
            merged.append({
                "timestamp": p["timestamp"],
                "cpu":       p["cpu"],
                "memory":    mem_by_ts.get(p["timestamp"], 0.0),
            })
        return merged

    async def get_cluster_cpu_pct(self, namespace: str | None = None) -> float:
        """Current cluster-wide CPU usage as a percentage."""
        try:
            ns_filter = f',namespace="{namespace}"' if namespace else ""
            results = await self._query_instant(
                f'avg(rate(container_cpu_usage_seconds_total'
                f'{{container!="POD",container!=""{ns_filter}}}[5m])) * 100'
            )
            if results:
                return round(float(results[0]["value"][1]), 1)
        except Exception:
            pass
        return 0.0

    async def get_cluster_memory_pct(self, namespace: str | None = None) -> float:
        """Current cluster-wide Memory usage as a percentage."""
        try:
            ns_filter = f',namespace="{namespace}"' if namespace else ""
            usage = await self._query_instant(
                f'sum(container_memory_working_set_bytes'
                f'{{container!="POD",container!=""{ns_filter}}})'
            )
            total = await self._query_instant(
                'sum(machine_memory_bytes)'
            )
            if usage and total:
                u = float(usage[0]["value"][1])
                t = float(total[0]["value"][1])
                if t > 0:
                    return round(u / t * 100, 1)
        except Exception:
            pass
        return 0.0


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _gather(*coros):
    import asyncio
    return await asyncio.gather(*coros, return_exceptions=False)


def _synthetic_pod_metrics(
    pod_id: str,
    points: int = 30,
    interval_minutes: int = 2,
) -> list[dict]:
    """
    Generate plausible synthetic metrics for a pod when Prometheus is unavailable.
    Seeded by pod_id so results are stable across calls.
    """
    seed = sum(ord(c) for c in pod_id)
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    base_cpu = rng.uniform(5, 70)
    base_mem = rng.uniform(20, 80)

    result = []
    for i in range(points):
        ts = now - timedelta(minutes=interval_minutes * (points - i - 1))
        phase = (i / points) * 2 * math.pi
        cpu = max(0.0, min(100.0, base_cpu + math.sin(phase) * base_cpu * 0.2
                           + rng.uniform(-3, 3)))
        mem = max(0.0, min(100.0, base_mem + math.sin(phase + 1) * base_mem * 0.1
                           + rng.uniform(-2, 2)))
        result.append({
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cpu":       round(cpu, 1),
            "memory":    round(mem, 1),
        })
    return result


def get_prometheus_client(integration: dict | None) -> Optional[PrometheusClient]:
    """
    Build a PrometheusClient from an integration record (from DB).
    Returns None when no Prometheus integration is configured.
    """
    if not integration:
        return None
    cfg    = integration.get("config") or {}
    creds  = integration.get("credentials") or {}
    server = cfg.get("server_url") or cfg.get("url") or ""
    token  = creds.get("token") or creds.get("prometheus_token") or ""
    insecure = cfg.get("insecure", False)
    if not server:
        return None
    return PrometheusClient(server, token, insecure=insecure)
