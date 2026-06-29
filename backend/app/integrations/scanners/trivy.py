"""
Trivy scanner integration.

Sprint 4: removed the previous fallback that invoked
``docker run -v /var/run/docker.sock:/var/run/docker.sock`` — that
mount gave the container raw host Docker access and was an explicit
production-blocker.  Trivy is now consumed strictly as a host
binary (``trivy`` on $PATH) or, when the operator wants to run it
out-of-process, via the dedicated Trivy sidecar exposed at
``TRIVY_REMOTE_URL`` (HTTP JSON endpoint).

The HTTP path is intentionally simple — Trivy's server mode
exposes ``/v1/scan/image`` and returns the same JSON shape the CLI
prints, so the rest of this adapter is unchanged.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any

import httpx

from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


def _binary_available(name: str) -> bool:
    try:
        result = subprocess.run(
            [name, "--version"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


class TrivyScanner(BaseIntegration):
    """Trivy integration.  Three execution paths, in order of preference:

      1. ``TRIVY_REMOTE_URL`` env var set — POST the image to the
         Trivy HTTP server (recommended for production).
      2. ``trivy`` binary on $PATH — invoke the CLI directly.
      3. Neither available — ``scan_image`` returns ``[]`` and
         ``test_connection`` returns ``False`` so the operator sees
         a clear failure rather than a silent mount of the Docker
         socket.
    """

    async def test_connection(self) -> bool:
        remote = (os.getenv("TRIVY_REMOTE_URL") or "").strip()
        if remote:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(f"{remote.rstrip('/')}/healthz")
                    return r.status_code == 200
            except Exception:
                return False
        return _binary_available("trivy")

    async def sync(self) -> dict:
        return {}

    async def scan_image(self, image: str) -> list[dict]:
        remote = (os.getenv("TRIVY_REMOTE_URL") or "").strip()
        if remote:
            return await self._scan_remote(remote, image)
        if _binary_available("trivy"):
            return self._scan_local(image)
        logger.warning(
            "Trivy unavailable — install the binary or set TRIVY_REMOTE_URL"
        )
        return []

    async def _scan_remote(self, base_url: str, image: str) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                r = await client.post(
                    f"{base_url.rstrip('/')}/v1/scan/image",
                    json={"image": image},
                )
                if r.status_code != 200:
                    return []
                return self._parse(r.json())
        except Exception:
            logger.exception("Trivy remote scan failed")
            return []

    def _scan_local(self, image: str) -> list[dict]:
        try:
            result = subprocess.run(
                ["trivy", "image", "--format", "json", "--quiet", image],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode != 0:
                return []
            return self._parse(json.loads(result.stdout))
        except Exception:
            return []

    @staticmethod
    def _parse(data: Any) -> list[dict]:
        vulns: list[dict] = []
        for r in data.get("Results", []) or []:
            for v in r.get("Vulnerabilities", []) or []:
                vulns.append(
                    {
                        "cve_id": v.get("VulnerabilityID"),
                        "title": v.get("Title", ""),
                        "severity": (v.get("Severity") or "UNKNOWN").lower(),
                        "cvss_score": (v.get("CVSS") or {}).get(
                            "nvd", {}
                        ).get("V3Score"),
                        "package_name": v.get("PkgName"),
                        "package_version": v.get("InstalledVersion"),
                        "fixed_version": v.get("FixedVersion", ""),
                        "target": r.get("Target"),
                    }
                )
        return vulns
