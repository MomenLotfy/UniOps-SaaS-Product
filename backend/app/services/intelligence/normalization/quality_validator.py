from __future__ import annotations
from typing import Any, Dict, Tuple
from app.schemas.intelligence import CanonicalCVE, CanonicalPackage, CanonicalExploit

class DataQualityValidator:
    """
    Validates the integrity of canonical objects and calculates a quality score.
    """
    def __init__(self):
        # Weights for different field requirements
        self.weights = {
            "description": 0.3,
            "cvss_score": 0.3,
            "published_at": 0.2,
            "references": 0.2
        }

    def validate_cve(self, cve: CanonicalCVE) -> Tuple[float, List[str]]:
        """
        Validates a CanonicalCVE and returns (quality_score, missing_fields).
        """
        missing = []
        score = 1.0

        if not cve.description:
            missing.append("description")
            score -= self.weights.get("description", 0.1)

        if cve.cvss_score is None:
            missing.append("cvss_score")
            score -= self.weights.get("cvss_score", 0.1)

        if not cve.published_at:
            missing.append("published_at")
            score -= self.weights.get("published_at", 0.1)

        if not cve.references:
            missing.append("references")
            score -= self.weights.get("references", 0.1)

        return max(0.0, score), missing

    def validate_package(self, pkg: CanonicalPackage) -> Tuple[float, List[str]]:
        """Validates a CanonicalPackage."""
        missing = []
        score = 1.0
        if not pkg.name:
            missing.append("name")
            score -= 0.5
        if not pkg.version.normalized:
            missing.append("version")
            score -= 0.5
        return max(0.0, score), missing
