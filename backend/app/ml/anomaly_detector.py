"""Anomaly Detector — uses Isolation Forest to detect anomalous metrics."""
from datetime import datetime, timezone
from typing import Optional
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline as SKPipeline

from app.ml.base import BaseMLModel


class AnomalyDetector(BaseMLModel):
    def __init__(self, contamination: float = 0.05):
        super().__init__("anomaly_detector")
        self.contamination = contamination

    def train(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> "AnomalyDetector":
        self.model = SKPipeline([
            ("scaler", StandardScaler()),
            ("detector", IsolationForest(
                contamination=self.contamination,
                n_estimators=200,
                random_state=42,
                n_jobs=-1,
            )),
        ])
        self.model.fit(X)
        self.is_fitted = True
        self.trained_at = datetime.now(timezone.utc)
        self.metadata["contamination"] = self.contamination
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Returns -1 for anomalies, 1 for normal."""
        if not self.is_fitted or self.model is None:
            if len(X) > 0:
                return np.ones(len(X), dtype=int)
            return np.array([], dtype=int)
        return self.model.predict(X)

    def detect(self, X: np.ndarray) -> np.ndarray:
        if X.shape[0] < 10:
            model = IsolationForest(contamination=self.contamination, random_state=42)
            model.fit(X)
            return model.predict(X)
        if not self.is_fitted:
            self.train(X)
        return self.predict(X)

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """Returns anomaly scores (lower = more anomalous)."""
        if not self.is_fitted or self.model is None:
            return np.zeros(len(X))
        return self.model.named_steps["detector"].score_samples(
            self.model.named_steps["scaler"].transform(X)
        )

    def detect_with_scores(self, X: np.ndarray) -> list[dict]:
        labels = self.detect(X)
        scores = self.score_samples(X) if self.is_fitted else np.zeros(len(X))

        results = []
        for i, (label, score) in enumerate(zip(labels, scores)):
            results.append({
                "index": i,
                "is_anomaly": bool(label == -1),
                "anomaly_score": round(float(score), 4),
                "severity": "high" if score < -0.3 else "medium" if score < -0.1 else "low",
            })
        return results

    def detect_from_series(self, series: list[float], window: int = 1) -> list[dict]:
        if not series:
            return []
        if window == 1:
            X = np.array(series).reshape(-1, 1)
        else:
            X = []
            for i in range(window, len(series) + 1):
                X.append(series[i - window:i])
            X = np.array(X)

        return self.detect_with_scores(X)
