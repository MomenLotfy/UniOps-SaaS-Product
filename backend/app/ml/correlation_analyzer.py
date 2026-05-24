"""Correlation Analyzer — computes Pearson, Spearman, and Kendall correlations between metrics."""
from datetime import datetime, timezone
from typing import Optional
import numpy as np
from scipy import stats

from app.ml.base import BaseMLModel


class CorrelationAnalyzer(BaseMLModel):
    def __init__(self):
        super().__init__("correlation_analyzer")

    def train(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> "CorrelationAnalyzer":
        self.model = {"fitted": True}
        self.is_fitted = True
        self.trained_at = datetime.now(timezone.utc)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return X

    def compute_pearson(self, x: list[float], y: list[float]) -> dict:
        _zero = {"coefficient": 0.0, "p_value": 1.0, "significant": False, "method": "pearson", "strength": "negligible"}
        if len(x) < 3 or len(y) < 3 or len(x) != len(y):
            return _zero
        # Guard against zero-variance (constant) series which makes pearsonr raise
        if len(set(x)) < 2 or len(set(y)) < 2:
            return _zero
        try:
            coef, p_value = stats.pearsonr(x, y)
            if coef != coef:  # NaN check
                return _zero
        except Exception:
            return _zero
        return {
            "coefficient": round(float(coef), 4),
            "p_value": round(float(p_value), 4),
            "significant": float(p_value) < 0.05,
            "method": "pearson",
            "strength": self._classify_strength(coef),
        }

    def compute_spearman(self, x: list[float], y: list[float]) -> dict:
        if len(x) < 3 or len(y) < 3 or len(x) != len(y):
            return {"coefficient": 0.0, "p_value": 1.0, "significant": False, "method": "spearman"}
        coef, p_value = stats.spearmanr(x, y)
        return {
            "coefficient": round(float(coef), 4),
            "p_value": round(float(p_value), 4),
            "significant": float(p_value) < 0.05,
            "method": "spearman",
            "strength": self._classify_strength(coef),
        }

    def compute_all(self, x: list[float], y: list[float]) -> dict:
        pearson = self.compute_pearson(x, y)
        spearman = self.compute_spearman(x, y)
        best = pearson if abs(pearson["coefficient"]) >= abs(spearman["coefficient"]) else spearman
        return {
            "pearson": pearson,
            "spearman": spearman,
            "best": best,
            "recommended_method": "pearson" if self._is_normal(x) and self._is_normal(y) else "spearman",
        }

    def compute_matrix(self, metrics: dict[str, list[float]]) -> list[dict]:
        names = list(metrics.keys())
        results = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                result = self.compute_pearson(metrics[a], metrics[b])
                results.append({
                    "metric_a": a,
                    "metric_b": b,
                    **result,
                    "insight": self._generate_insight(a, b, result["coefficient"]),
                })
        return sorted(results, key=lambda r: abs(r["coefficient"]), reverse=True)

    def _classify_strength(self, coef: float) -> str:
        abs_coef = abs(coef)
        if abs_coef >= 0.8: return "very_strong"
        if abs_coef >= 0.6: return "strong"
        if abs_coef >= 0.4: return "moderate"
        if abs_coef >= 0.2: return "weak"
        return "negligible"

    def _is_normal(self, data: list[float]) -> bool:
        if len(data) < 8:
            return True
        _, p = stats.shapiro(data[:50])
        return float(p) > 0.05

    def _generate_insight(self, metric_a: str, metric_b: str, coef: float) -> str:
        direction = "positively" if coef > 0 else "negatively"
        strength = self._classify_strength(coef)
        if abs(coef) < 0.2:
            return f"{metric_a} and {metric_b} show no meaningful correlation."
        return f"{metric_a} is {strength}ly {direction} correlated with {metric_b} (r={coef:.2f})."
