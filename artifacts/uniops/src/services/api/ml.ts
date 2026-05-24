import { apiClient } from './client';
import type {
  WorkloadForecast,
  MetricCorrelation,
  AnomalyDetection,
  MLPattern,
  MLRecommendation,
  MLInsightSummary,
} from '@/types/ml';

// FastAPI router: /ml/*
export const mlApi = {
  // /ml/predictions/summary replaces /ml/insights/summary
  getSummary: () =>
    apiClient.get<MLInsightSummary>('/ml/predictions/summary').then((r) => r.data),

  // /ml/predictions replaces /ml/forecasts
  getForecasts: (metricNames?: string[], horizonHours = 48) =>
    apiClient.get<WorkloadForecast[]>('/ml/predictions', {
      params: { metrics: metricNames?.join(','), horizon: horizonHours },
    }).then((r) => r.data),

  getForecast: (id: string) =>
    apiClient.get<WorkloadForecast>(`/ml/predictions`).then((r) => r.data),

  getCorrelations: (metrics?: string[], minStrength?: number) =>
    apiClient.get<MetricCorrelation[]>('/ml/correlations', {
      params: { metrics: metrics?.join(','), min_strength: minStrength },
    }).then((r) => r.data),

  // /ml/detect/anomalies (POST) for on-demand; GET from predictions for history
  getAnomalies: (params?: { startDate?: string; endDate?: string; metric?: string; severity?: string }) =>
    apiClient.post<AnomalyDetection[]>('/ml/detect/anomalies', params ?? {}).then((r) => r.data),

  getPatterns: () =>
    apiClient.get<MLPattern[]>('/ml/patterns').then((r) => r.data),

  getRecommendations: () =>
    apiClient.get<MLRecommendation[]>('/ml/recommendations').then((r) => r.data),

  applyRecommendation: (id: string) =>
    apiClient.post<MLRecommendation>(`/ml/recommendations/${id}/apply`).then((r) => r.data),

  dismissRecommendation: (id: string) =>
    apiClient.post(`/ml/recommendations/${id}/dismiss`).then((r) => r.data),

  dismissPattern: (id: string) =>
    apiClient.post(`/ml/patterns/${id}/dismiss`).then((r) => r.data),

  // /ml/models/retrain (POST)
  triggerTraining: (modelType?: string) =>
    apiClient.post('/ml/models/retrain', { model_type: modelType }).then((r) => r.data),

  // /ml/models/status (GET)
  getModelMetrics: () =>
    apiClient.get('/ml/models/status').then((r) => r.data),

  getStats: () =>
    apiClient.get('/ml/stats').then((r) => r.data),

  getRadar: () =>
    apiClient.get('/ml/radar').then((r) => r.data),
};
