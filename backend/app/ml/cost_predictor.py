"""Cost Predictor — uses Random Forest to forecast cloud costs."""
from datetime import datetime, timezone
from typing import Optional
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline as SKPipeline

from app.ml.base import BaseMLModel


class CostPredictor(BaseMLModel):
    def __init__(self):
        super().__init__("cost_predictor")
        self.pipeline = None

    def _build_features(self, costs: list[float]) -> np.ndarray:
        """Build time-series features: rolling mean, std, lag features, trend."""
        n = len(costs)
        features = []
        for i in range(n):
            window_3 = costs[max(0, i - 3):i] if i > 0 else [costs[0]]
            window_6 = costs[max(0, i - 6):i] if i > 0 else [costs[0]]
            feat = [
                costs[i - 1] if i > 0 else costs[0],
                costs[i - 2] if i > 1 else costs[0],
                costs[i - 3] if i > 2 else costs[0],
                np.mean(window_3),
                np.std(window_3) if len(window_3) > 1 else 0,
                np.mean(window_6),
                np.std(window_6) if len(window_6) > 1 else 0,
                i,
            ]
            features.append(feat)
        return np.array(features)

    def train(self, X: np.ndarray, y: np.ndarray) -> "CostPredictor":
        self.pipeline = SKPipeline([
            ("scaler", StandardScaler()),
            ("model", RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)),
        ])
        self.pipeline.fit(X, y)
        self.model = self.pipeline
        self.is_fitted = True
        self.trained_at = datetime.now(timezone.utc)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self.model is None:
            return np.array([0.0])
        return self.model.predict(X)

    def predict_next_month(self, historical_costs: list[float]) -> dict:
        if len(historical_costs) < 2:
            avg = historical_costs[0] if historical_costs else 0
            return {"prediction": round(avg, 2), "confidence": 0.3, "trend": "stable"}

        arr = np.array(historical_costs[-12:])
        trend = float(np.polyfit(range(len(arr)), arr, 1)[0])
        rolling_avg = float(np.mean(arr[-3:]))
        std = float(np.std(arr))

        if self.is_fitted and self.model:
            features = self._build_features(list(arr))
            next_features = features[-1].reshape(1, -1)
            prediction = float(self.model.predict(next_features)[0])
        else:
            prediction = rolling_avg + trend * 0.5

        prediction = max(0, prediction)
        confidence = max(0.4, min(0.95, 1 - (std / rolling_avg) if rolling_avg > 0 else 0.5))

        trend_label = "increasing" if trend > rolling_avg * 0.02 else "decreasing" if trend < -rolling_avg * 0.02 else "stable"

        return {
            "prediction": round(prediction, 2),
            "confidence": round(confidence, 2),
            "trend": trend_label,
            "lower_bound": round(max(0, prediction - std), 2),
            "upper_bound": round(prediction + std, 2),
            "months_of_data": len(historical_costs),
        }

    def predict_multi_month(self, historical_costs: list[float], months: int = 3) -> list[dict]:
        results = []
        costs = list(historical_costs)
        for m in range(1, months + 1):
            result = self.predict_next_month(costs)
            result["month_offset"] = m
            results.append(result)
            costs.append(result["prediction"])
        return results
