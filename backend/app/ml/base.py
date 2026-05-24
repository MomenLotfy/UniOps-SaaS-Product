"""Base ML model class — defines the interface for all ML models in UniOps."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional
import os
import numpy as np
import joblib

from app.utils.logger import logger


class BaseMLModel(ABC):
    def __init__(self, model_name: str, version: str = "1.0.0"):
        self.model_name = model_name
        self.version = version
        self.model = None
        self.is_fitted = False
        self.metadata: dict = {}
        self.trained_at: Optional[datetime] = None

    @abstractmethod
    def train(self, X: np.ndarray, y: np.ndarray) -> "BaseMLModel":
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        pass

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Override in subclasses for model-specific evaluation metrics."""
        if not self.is_fitted:
            return {"error": "Model not fitted"}
        predictions = self.predict(X)
        if hasattr(y, "__len__") and len(y) > 0:
            from sklearn.metrics import mean_absolute_error, r2_score
            try:
                return {
                    "mae": float(mean_absolute_error(y, predictions)),
                    "r2": float(r2_score(y, predictions)),
                }
            except Exception:
                pass
        return {}

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bundle = {
            "model": self.model,
            "version": self.version,
            "metadata": self.metadata,
            "trained_at": self.trained_at,
        }
        joblib.dump(bundle, path)
        logger.info(f"Model {self.model_name} saved to {path}")

    def load(self, path: str) -> "BaseMLModel":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")
        bundle = joblib.load(path)
        self.model = bundle["model"]
        self.version = bundle.get("version", self.version)
        self.metadata = bundle.get("metadata", {})
        self.trained_at = bundle.get("trained_at")
        self.is_fitted = True
        logger.info(f"Model {self.model_name} loaded from {path}")
        return self

    def get_info(self) -> dict:
        return {
            "name": self.model_name,
            "version": self.version,
            "is_fitted": self.is_fitted,
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "metadata": self.metadata,
        }
