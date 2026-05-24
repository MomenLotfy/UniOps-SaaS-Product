"""Feature Store — caches and retrieves ML features from Redis."""
import json
from typing import Optional, Any
from datetime import datetime, timezone, timedelta

from app.utils.logger import logger


class FeatureStore:
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._local_cache: dict = {}

    async def get(self, feature_set: str, entity_id: str) -> Optional[dict]:
        key = f"features:{feature_set}:{entity_id}"
        try:
            from app.core.redis_client import cache_get
            value = await cache_get(key)
            if value:
                return json.loads(value)
        except Exception:
            pass
        return self._local_cache.get(key)

    async def set(self, feature_set: str, entity_id: str, features: dict, ttl: Optional[int] = None) -> None:
        key = f"features:{feature_set}:{entity_id}"
        value = json.dumps(features)
        self._local_cache[key] = features
        try:
            from app.core.redis_client import cache_set
            await cache_set(key, value, ttl or self.ttl)
        except Exception as e:
            logger.warning(f"Feature store Redis write failed: {e}")

    async def delete(self, feature_set: str, entity_id: str) -> None:
        key = f"features:{feature_set}:{entity_id}"
        self._local_cache.pop(key, None)
        try:
            from app.core.redis_client import cache_delete
            await cache_delete(key)
        except Exception:
            pass

    async def get_or_compute(self, feature_set: str, entity_id: str, compute_fn, ttl: Optional[int] = None) -> dict:
        cached = await self.get(feature_set, entity_id)
        if cached:
            return cached
        features = await compute_fn()
        await self.set(feature_set, entity_id, features, ttl)
        return features

    def build_cost_features(self, cost_history: list[float]) -> dict:
        if not cost_history:
            return {}
        import numpy as np
        arr = np.array(cost_history)
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "trend": float(np.polyfit(range(len(arr)), arr, 1)[0]) if len(arr) > 1 else 0.0,
            "last_3_mean": float(np.mean(arr[-3:])) if len(arr) >= 3 else float(np.mean(arr)),
            "last_6_mean": float(np.mean(arr[-6:])) if len(arr) >= 6 else float(np.mean(arr)),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    def build_workload_features(self, metrics: dict) -> dict:
        features = {}
        import numpy as np
        for metric_name, values in metrics.items():
            if values:
                arr = np.array(values)
                features[f"{metric_name}_mean"] = float(np.mean(arr))
                features[f"{metric_name}_p95"] = float(np.percentile(arr, 95))
                features[f"{metric_name}_p99"] = float(np.percentile(arr, 99))
        features["computed_at"] = datetime.now(timezone.utc).isoformat()
        return features


feature_store = FeatureStore()
