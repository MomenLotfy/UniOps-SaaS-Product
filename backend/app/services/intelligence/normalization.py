from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.schemas.intelligence import (
    CanonicalCVE, CanonicalPackage, CanonicalExploit,
    CanonicalWeakness, CanonicalAttackPattern, CanonicalRemediationReference,
    RiskLevel
)
from app.utils.logger import logger

class NormalizationLayer:
    """
    Transforms provider-specific raw data into canonical models.
    Acts as the anti-corruption layer for the Intelligence domain.
    """

    def normalize_vulnerability(self, provider_id: str, raw_data: Dict[str, Any]) -> Optional[CanonicalCVE]:
        """
        Maps raw vulnerability data to CanonicalCVE.
        In a real impl, this would use provider-specific mapping functions.
        """
        try:
            # This is a generic fallback mapper. Actual providers would provide
            # specific mapping logic via their class.
            return CanonicalCVE(
                cve_id=raw_data.get("id") or raw_data.get("cve_id"),
                cvss_score=raw_data.get("cvss") or raw_data.get("score"),
                cvss_vector=raw_data.get("vector"),
                severity=self._map_severity(raw_data.get("severity")),
                description=raw_data.get("description", "No description available"),
                published_at=raw_data.get("published"),
                last_modified=raw_data.get("modified"),
                references=raw_data.get("references", [])
            )
        except Exception as e:
            logger.error(f"[Normalization] Failed to normalize vulnerability from {provider_id}: {e}")
            return None

    def normalize_package(self, provider_id: str, raw_data: Dict[str, Any]) -> Optional[CanonicalPackage]:
        """Maps raw package data to CanonicalPackage."""
        try:
            return CanonicalPackage(
                purl=raw_data.get("purl"),
                name=raw_data.get("name"),
                version=raw_data.get("version"),
                ecosystem=raw_data.get("ecosystem", "unknown"),
                vendor=raw_data.get("vendor")
            )
        except Exception as e:
            logger.error(f"[Normalization] Failed to normalize package from {provider_id}: {e}")
            return None

    def normalize_exploit(self, provider_id: str, raw_data: Dict[str, Any]) -> Optional[CanonicalExploit]:
        """Maps raw exploit data to CanonicalExploit."""
        try:
            return CanonicalExploit(
                exploit_id=raw_data.get("id"),
                maturity=raw_data.get("maturity", "unknown"),
                source=provider_id,
                first_seen=raw_data.get("first_seen"),
                last_seen=raw_data.get("last_seen"),
                url=raw_data.get("url")
            )
        except Exception as e:
            logger.error(f"[Normalization] Failed to normalize exploit from {provider_id}: {e}")
            return None

    def _map_severity(self, severity: Any) -> RiskLevel:
        if not severity:
            return RiskLevel.MEDIUM

        s = str(severity).upper()
        if "CRITICAL" in s or "10" in s: return RiskLevel.CRITICAL
        if "HIGH" in s: return RiskLevel.HIGH
        if "LOW" in s: return RiskLevel.LOW
        if "INFO" in s: return RiskLevel.INFORMATIONAL
        return RiskLevel.MEDIUM
