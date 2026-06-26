from __future__ import annotations
from typing import Any, Dict, Optional
from ..base import ProviderMapper

class OsvMapper(ProviderMapper):
    def map_vulnerability(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Mock OSV mapping logic
        cve_id = raw_data.get("id")
        if not cve_id: return None

        return {
            "cve_id": cve_id,
            "description": raw_data.get("details", ""),
            "published_at": raw_data.get("published"),
            "last_modified": raw_data.get("modified"),
            "references": [ref.get("url") for ref in raw_data.get("references", [])],
            "provenance": {"description": self.create_provenance()}
        }

    def map_package(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        package = raw_data.get("affected", [{}])[0].get("package", {})
        if not package: return None

        return {
            "purl": package.get("purl"),
            "name": package.get("name"),
            "version": package.get("version"),
            "ecosystem": package.get("ecosystem"),
            "provenance": {"purl": self.create_provenance()}
        }

    def map_exploit(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None
