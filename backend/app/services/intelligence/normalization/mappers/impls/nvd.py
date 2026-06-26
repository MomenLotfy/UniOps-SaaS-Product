from __future__ import annotations
from typing import Any, Dict, Optional
from ..base import ProviderMapper

class NvdMapper(ProviderMapper):
    def map_vulnerability(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Mock NVD mapping logic
        cve_id = raw_data.get("cve", {}).get("id")
        if not cve_id: return None

        return {
            "cve_id": cve_id,
            "cvss_score": raw_data.get("metrics", {}).get("cvss_v3", {}).get("score"),
            "severity": raw_data.get("metrics", {}).get("cvss_v3", {}).get("severity", "MEDIUM"),
            "description": raw_data.get("descriptions", [{}])[0].get("value", ""),
            "published_at": raw_data.get("published"),
            "last_modified": raw_data.get("lastModified"),
            "references": [ref.get("url") for ref in raw_data.get("references", [])],
            "provenance": {"description": self.create_provenance()}
        }

    def map_package(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None # NVD primarily focuses on CVEs

    def map_exploit(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None # Handled by specialized exploit providers
