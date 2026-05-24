"""Recommendation Engine — generates actionable DevOps and cost optimization recommendations."""
from datetime import datetime, timezone
from typing import Optional
import numpy as np

from app.ml.base import BaseMLModel


class RecommendationEngine(BaseMLModel):
    def __init__(self):
        super().__init__("recommendation_engine")

    def train(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> "RecommendationEngine":
        self.model = {"rules": self._get_rules()}
        self.is_fitted = True
        self.trained_at = datetime.now(timezone.utc)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return X

    def _get_rules(self) -> list[dict]:
        return [
            {"id": "cost_rightsize", "category": "cost", "threshold": {"waste_pct": 0.3}},
            {"id": "security_unpatched", "category": "security", "threshold": {"critical_cve": 1}},
            {"id": "perf_high_restart", "category": "reliability", "threshold": {"restart_count": 5}},
            {"id": "ci_low_success", "category": "devops", "threshold": {"success_rate": 0.8}},
        ]

    def generate_cost_recommendations(self, cost_data: dict) -> list[dict]:
        recommendations = []
        total_cost = cost_data.get("total_cost", 0)
        if total_cost <= 0:
            return recommendations

        by_service = cost_data.get("by_service", {})
        for service, cost in sorted(by_service.items(), key=lambda x: x[1], reverse=True)[:5]:
            pct = (cost / total_cost) * 100
            if pct > 30:
                recommendations.append({
                    "title": f"Review high-spend service: {service}",
                    "description": f"{service} accounts for {pct:.1f}% of total cloud spend (${cost:.2f}).",
                    "category": "cost",
                    "priority": 1,
                    "confidence": 0.85,
                    "impact": "high",
                    "effort": "medium",
                    "action": f"Audit {service} usage patterns and consider reserved instances or rightsizing.",
                })

        trend_pct = cost_data.get("trend_pct", 0)
        if trend_pct > 15:
            recommendations.append({
                "title": "Investigate accelerating cost growth",
                "description": f"Cloud costs increased by {trend_pct:.1f}% compared to last month.",
                "category": "cost",
                "priority": 2,
                "confidence": 0.90,
                "impact": "high",
                "effort": "low",
                "action": "Review recent deployments and usage spikes to identify cost drivers.",
            })
        return recommendations

    def generate_security_recommendations(self, security_data: dict) -> list[dict]:
        recommendations = []
        critical_vulns = security_data.get("critical_vulnerabilities", 0)
        if critical_vulns > 0:
            recommendations.append({
                "title": f"Patch {critical_vulns} critical vulnerabilities immediately",
                "description": "Critical vulnerabilities expose your infrastructure to high-risk exploits.",
                "category": "security",
                "priority": 1,
                "confidence": 0.98,
                "impact": "critical",
                "effort": "medium",
                "action": "Run vulnerability scan and apply patches using your CI/CD pipeline.",
            })

        open_threats = security_data.get("open_threats", 0)
        if open_threats > 5:
            recommendations.append({
                "title": f"Review {open_threats} open security threats",
                "description": "Multiple open threats indicate potential attack surface.",
                "category": "security",
                "priority": 2,
                "confidence": 0.88,
                "impact": "high",
                "effort": "medium",
                "action": "Triage threats by MITRE ATT&CK framework and address critical ones first.",
            })
        return recommendations

    def generate_devops_recommendations(self, devops_data: dict) -> list[dict]:
        recommendations = []
        success_rate = devops_data.get("pipeline_success_rate", 1.0)
        if success_rate < 0.8:
            recommendations.append({
                "title": f"Improve pipeline success rate (currently {success_rate*100:.1f}%)",
                "description": "Low pipeline success rate impacts developer productivity.",
                "category": "devops",
                "priority": 2,
                "confidence": 0.90,
                "impact": "medium",
                "effort": "medium",
                "action": "Review failing pipeline stages, add retry logic, and fix flaky tests.",
            })

        high_restart_pods = devops_data.get("high_restart_pods", 0)
        if high_restart_pods > 0:
            recommendations.append({
                "title": f"{high_restart_pods} pods with high restart counts",
                "description": "Frequent pod restarts indicate resource constraints or application errors.",
                "category": "reliability",
                "priority": 1,
                "confidence": 0.85,
                "impact": "high",
                "effort": "medium",
                "action": "Check pod logs, review resource limits, and fix OOM issues.",
            })
        return recommendations

    def generate_all(self, context: dict) -> list[dict]:
        recommendations = []
        if "cost" in context:
            recommendations.extend(self.generate_cost_recommendations(context["cost"]))
        if "security" in context:
            recommendations.extend(self.generate_security_recommendations(context["security"]))
        if "devops" in context:
            recommendations.extend(self.generate_devops_recommendations(context["devops"]))

        recommendations.sort(key=lambda r: (r.get("priority", 5), -r.get("confidence", 0)))
        return recommendations
