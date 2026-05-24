"""Workload Predictor — predicts future resource workloads using time-series analysis."""
from datetime import datetime, timezone
from typing import Optional
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.pipeline import Pipeline as SKPipeline

from app.ml.base import BaseMLModel


class WorkloadPredictor(BaseMLModel):
    def __init__(self, lookback: int = 24):
        super().__init__("workload_predictor")
        self.lookback = lookback
        self.scaler = MinMaxScaler()

    def _create_sequences(self, data: np.ndarray, lookback: int) -> tuple:
        X, y = [], []
        for i in range(lookback, len(data)):
            seq = data[i - lookback:i]
            features = [
                np.mean(seq), np.std(seq), np.min(seq), np.max(seq),
                seq[-1], seq[-2] if len(seq) > 1 else seq[-1],
                seq[-1] - seq[0],
                np.percentile(seq, 75) - np.percentile(seq, 25),
                float(i % 24),
                float(i % (24 * 7)),
            ]
            X.append(features)
            y.append(data[i])
        return np.array(X), np.array(y)

    def train(self, X: np.ndarray, y: np.ndarray) -> "WorkloadPredictor":
        self.model = GradientBoostingRegressor(
            n_estimators=150, learning_rate=0.1, max_depth=4, random_state=42
        )
        self.model.fit(X, y)
        self.is_fitted = True
        self.trained_at = datetime.now(timezone.utc)
        return self

    def train_from_series(self, series: list[float]) -> "WorkloadPredictor":
        if len(series) < self.lookback + 5:
            return self
        data = np.array(series)
        X, y = self._create_sequences(data, self.lookback)
        if len(X) == 0:
            return self
        return self.train(X, y)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self.model is None:
            return np.zeros(len(X))
        return self.model.predict(X)

    def predict_next_n(self, historical: list[float], steps: int = 24) -> list[dict]:
        if not historical:
            return [{"step": i + 1, "value": 0.0, "confidence": 0.3} for i in range(steps)]

        series = list(historical)
        std = float(np.std(series[-24:]) if len(series) >= 24 else np.std(series))
        predictions = []

        for step in range(steps):
            if len(series) >= 3:
                weights = np.exp(np.linspace(-1, 0, min(len(series), 12)))
                weights /= weights.sum()
                weighted_avg = float(np.average(series[-len(weights):], weights=weights))
                trend = (series[-1] - series[-min(6, len(series))]) / min(6, len(series))
                value = max(0, weighted_avg + trend * 0.3)
            else:
                value = float(np.mean(series))

            confidence = max(0.4, min(0.9, 0.85 - step * 0.02))
            predictions.append({
                "step": step + 1,
                "value": round(value, 3),
                "confidence": round(confidence, 2),
                "lower": round(max(0, value - std * 0.5), 3),
                "upper": round(value + std * 0.5, 3),
            })
            series.append(value)

        return predictions

    def detect_peak(self, historical: list[float]) -> dict:
        if len(historical) < 3:
            return {"peak_value": max(historical) if historical else 0, "peak_index": 0}

        arr = np.array(historical)
        peak_idx = int(np.argmax(arr))
        return {
            "peak_value": round(float(arr[peak_idx]), 3),
            "peak_index": peak_idx,
            "mean": round(float(np.mean(arr)), 3),
            "p95": round(float(np.percentile(arr, 95)), 3),
            "p99": round(float(np.percentile(arr, 99)), 3),
        }
