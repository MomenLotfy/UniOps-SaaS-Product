"""Pattern Discoverer — finds recurring patterns in time-series data."""
from datetime import datetime, timezone
from typing import Optional
import numpy as np
from scipy import stats

from app.ml.base import BaseMLModel


class PatternDiscoverer(BaseMLModel):
    def __init__(self):
        super().__init__("pattern_discoverer")

    def train(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> "PatternDiscoverer":
        self.model = {"fitted": True}
        self.is_fitted = True
        self.trained_at = datetime.now(timezone.utc)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return X

    def find_daily_pattern(self, hourly_data: list[float]) -> dict:
        if len(hourly_data) < 24:
            return {"type": "insufficient_data", "confidence": 0.0}

        arr = np.array(hourly_data)
        hours = len(arr)
        days = hours // 24
        if days < 2:
            daily_avg = arr[:24].tolist()
            peak_hour = int(np.argmax(arr[:24]))
            return {
                "type": "daily",
                "peak_hour": peak_hour,
                "trough_hour": int(np.argmin(arr[:24])),
                "daily_avg": [round(float(v), 3) for v in daily_avg],
                "confidence": 0.5,
            }

        reshaped = arr[:days * 24].reshape(days, 24)
        daily_avg = np.mean(reshaped, axis=0)
        daily_std = np.std(reshaped, axis=0)

        consistency = 1 - float(np.mean(daily_std / (daily_avg + 1e-9)))
        confidence = max(0.3, min(0.95, consistency))

        return {
            "type": "daily",
            "peak_hour": int(np.argmax(daily_avg)),
            "trough_hour": int(np.argmin(daily_avg)),
            "daily_avg": [round(float(v), 3) for v in daily_avg],
            "daily_std": [round(float(v), 3) for v in daily_std],
            "confidence": round(confidence, 2),
            "days_analyzed": days,
        }

    def find_weekly_pattern(self, daily_data: list[float]) -> dict:
        if len(daily_data) < 14:
            return {"type": "insufficient_data", "confidence": 0.0}

        arr = np.array(daily_data)
        weeks = len(arr) // 7
        reshaped = arr[:weeks * 7].reshape(weeks, 7)
        weekly_avg = np.mean(reshaped, axis=0)
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        return {
            "type": "weekly",
            "peak_day": days[int(np.argmax(weekly_avg))],
            "trough_day": days[int(np.argmin(weekly_avg))],
            "weekly_profile": {days[i]: round(float(v), 3) for i, v in enumerate(weekly_avg)},
            "confidence": min(0.9, 0.6 + weeks * 0.05),
            "weeks_analyzed": weeks,
        }

    def detect_trend(self, series: list[float]) -> dict:
        if len(series) < 3:
            return {"trend": "stable", "slope": 0.0, "confidence": 0.3}

        x = np.arange(len(series))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, series)

        mean_val = float(np.mean(series)) or 1
        relative_slope = float(slope) / abs(mean_val)

        trend = "stable"
        if relative_slope > 0.02:
            trend = "increasing"
        elif relative_slope < -0.02:
            trend = "decreasing"

        return {
            "trend": trend,
            "slope": round(float(slope), 4),
            "relative_slope_pct": round(relative_slope * 100, 2),
            "r_squared": round(float(r_value ** 2), 4),
            "p_value": round(float(p_value), 4),
            "significant": float(p_value) < 0.05,
            "confidence": round(min(0.95, float(r_value ** 2)), 2),
        }

    def find_all_patterns(self, data: list[float], granularity: str = "hourly") -> list[dict]:
        patterns = []
        trend = self.detect_trend(data)
        patterns.append({
            "name": "trend",
            "pattern_type": "trend",
            "description": f"Data shows a {trend['trend']} trend (slope={trend['slope']:.4f})",
            "confidence": trend["confidence"],
            "data": trend,
        })
        if granularity == "hourly" and len(data) >= 48:
            daily = self.find_daily_pattern(data)
            if daily.get("confidence", 0) > 0.5:
                patterns.append({
                    "name": "daily_cycle",
                    "pattern_type": "cyclical",
                    "description": f"Daily peak at hour {daily.get('peak_hour', 0)}",
                    "confidence": daily["confidence"],
                    "data": daily,
                })
        elif granularity == "daily" and len(data) >= 14:
            weekly = self.find_weekly_pattern(data)
            if weekly.get("confidence", 0) > 0.5:
                patterns.append({
                    "name": "weekly_cycle",
                    "pattern_type": "cyclical",
                    "description": f"Weekly peak on {weekly.get('peak_day', 'Unknown')}",
                    "confidence": weekly["confidence"],
                    "data": weekly,
                })
        return patterns
