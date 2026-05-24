"""Unit tests for ML models — prediction quality and edge cases."""
import pytest
import numpy as np


class TestCostPredictor:
    def test_predict_next_month_stable_data(self):
        from app.ml.cost_predictor import CostPredictor
        predictor = CostPredictor()
        costs = [1000.0] * 12
        result = predictor.predict_next_month(costs)
        assert "prediction" in result
        assert "confidence" in result
        assert result["prediction"] >= 0
        assert 0 <= result["confidence"] <= 1

    def test_predict_increasing_trend(self):
        from app.ml.cost_predictor import CostPredictor
        predictor = CostPredictor()
        costs = [1000.0 + i * 100 for i in range(12)]
        result = predictor.predict_next_month(costs)
        assert result["trend"] == "increasing"

    def test_predict_with_minimal_data(self):
        from app.ml.cost_predictor import CostPredictor
        predictor = CostPredictor()
        result = predictor.predict_next_month([500.0])
        assert "prediction" in result
        assert result["confidence"] < 0.5

    def test_multi_month_prediction_length(self):
        from app.ml.cost_predictor import CostPredictor
        predictor = CostPredictor()
        costs = [1000.0 + i * 50 for i in range(8)]
        results = predictor.predict_multi_month(costs, months=3)
        assert len(results) == 3
        for r in results:
            assert "prediction" in r
            assert "month_offset" in r


class TestAnomalyDetector:
    def test_detect_no_anomalies_in_stable_data(self):
        from app.ml.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector(contamination=0.05)
        normal = np.array([[100.0 + i * 0.1] for i in range(100)])
        labels = detector.detect(normal)
        assert len(labels) == 100
        anomalies = [l for l in labels if l == -1]
        assert len(anomalies) < 15

    def test_detect_anomaly_in_spike_data(self):
        from app.ml.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector(contamination=0.1)
        data = [[100.0]] * 90 + [[99999.0]] * 5 + [[-99999.0]] * 5
        X = np.array(data)
        labels = detector.detect(X)
        extreme_indices = list(range(90, 100))
        anomalous = [labels[i] for i in extreme_indices]
        assert -1 in anomalous

    def test_score_samples_returns_floats(self):
        from app.ml.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector()
        X = np.array([[float(i)] for i in range(50)])
        detector.train(X)
        scores = detector.score_samples(X)
        assert len(scores) == 50
        assert all(isinstance(s, float) for s in scores)


class TestCorrelationAnalyzer:
    def test_perfect_positive_correlation(self):
        from app.ml.correlation_analyzer import CorrelationAnalyzer
        analyzer = CorrelationAnalyzer()
        x = [float(i) for i in range(20)]
        y = [float(i) for i in range(20)]
        result = analyzer.compute_pearson(x, y)
        assert abs(result["coefficient"] - 1.0) < 0.001
        assert result["significant"]
        assert result["strength"] == "very_strong"

    def test_perfect_negative_correlation(self):
        from app.ml.correlation_analyzer import CorrelationAnalyzer
        analyzer = CorrelationAnalyzer()
        x = [float(i) for i in range(20)]
        y = [float(20 - i) for i in range(20)]
        result = analyzer.compute_pearson(x, y)
        assert abs(result["coefficient"] + 1.0) < 0.001

    def test_insufficient_data_returns_zero(self):
        from app.ml.correlation_analyzer import CorrelationAnalyzer
        analyzer = CorrelationAnalyzer()
        result = analyzer.compute_pearson([1.0], [1.0])
        assert result["coefficient"] == 0.0

    def test_correlation_matrix(self):
        from app.ml.correlation_analyzer import CorrelationAnalyzer
        analyzer = CorrelationAnalyzer()
        metrics = {
            "cpu": [float(i) for i in range(20)],
            "memory": [float(i * 2) for i in range(20)],
            "cost": [float(i * 0.5) for i in range(20)],
        }
        results = analyzer.compute_matrix(metrics)
        assert len(results) == 3
        assert results[0]["coefficient"] >= results[-1]["coefficient"]


class TestWorkloadPredictor:
    def test_predict_next_n_returns_correct_length(self):
        from app.ml.workload_predictor import WorkloadPredictor
        predictor = WorkloadPredictor()
        historical = [float(i % 10) for i in range(30)]
        results = predictor.predict_next_n(historical, steps=5)
        assert len(results) == 5
        for r in results:
            assert "step" in r
            assert "value" in r
            assert "confidence" in r

    def test_predict_empty_data_returns_defaults(self):
        from app.ml.workload_predictor import WorkloadPredictor
        predictor = WorkloadPredictor()
        results = predictor.predict_next_n([], steps=3)
        assert len(results) == 3

    def test_detect_peak(self):
        from app.ml.workload_predictor import WorkloadPredictor
        predictor = WorkloadPredictor()
        data = [10.0, 20.0, 15.0, 5.0, 30.0, 8.0]
        result = predictor.detect_peak(data)
        assert result["peak_value"] == 30.0
        assert result["peak_index"] == 4
