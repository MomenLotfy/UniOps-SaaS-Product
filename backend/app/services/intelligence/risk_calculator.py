from __future__ import annotations
from typing import Any, Dict, Optional
from app.schemas.intelligence import CanonicalRisk, RiskLevel, ConfidenceLevel

class RiskCalculator:
    """
    Calculates the a unified risk score for a finding.
    Combines technical severity, exploitability, and business impact.
    """

    def calculate_risk(
        self,
        cvss_score: Optional[float],
        exploit_maturity: str,
        is_known_exploited: bool,
        asset_criticality: float = 1.0
    ) -> CanonicalRisk:
        """
        Calculates the risk score (0-100).
        """
        # 1. Base Technical Score (0-60)
        base_score = (cvss_score or 5.0) * 6.0

        # 2. Exploitability Multiplier (0-20)
        exploit_bonus = 0.0
        if is_known_exploited:
            exploit_bonus = 20.0
        elif exploit_maturity == "Weaponized":
            exploit_bonus = 15.0
        elif exploit_maturity == "Functional":
            exploit_bonus = 10.0
        elif exploit_maturity == "PoC":
            exploit_bonus = 5.0

        # 3. Asset Context Bonus (0-20)
        context_bonus = (asset_criticality - 1.0) * 10.0
        context_bonus = max(0, min(20, context_bonus))

        total_score = min(100.0, base_score + exploit_bonus + context_bonus)

        # Determine Risk Level
        if total_score >= 90: level = RiskLevel.CRITICAL
        elif total_score >= 70: level = RiskLevel.HIGH
        elif total_score >= 40: level = RiskLevel.MEDIUM
        elif total_score >= 20: level = RiskLevel.LOW
        else: level = RiskLevel.INFORMATIONAL

        return CanonicalRisk(
            score=total_score,
            level=level,
            factors={
                "base_tech": base_score,
                "exploitability": exploit_bonus,
                "asset_impact": context_bonus
            },
            confidence=ConfidenceLevel.HIGH if cvss_score else ConfidenceLevel.MEDIUM
        )
