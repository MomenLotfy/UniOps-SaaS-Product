export type ModelType = 'lstm' | 'arima' | 'prophet' | 'xgboost' | 'isolation_forest' | 'autoencoder';

export type InsightCategory = 'performance' | 'cost' | 'security' | 'reliability' | 'capacity';

export type CorrelationType = 'positive' | 'negative' | 'none';

export interface ForecastPoint {
  timestamp: string;
  value: number;
  lowerBound: number;
  upperBound: number;
  isHistorical: boolean;
}

export interface WorkloadForecast {
  id: string;
  metricName: string;
  unit: string;
  modelType: ModelType;
  accuracy: number;
  mape: number;
  horizon: number;
  dataPoints: ForecastPoint[];
  generatedAt: string;
  companyId: string;
}

export interface MetricCorrelation {
  metricA: string;
  metricB: string;
  correlationCoefficient: number;
  type: CorrelationType;
  strength: 'strong' | 'moderate' | 'weak';
  pValue: number;
  lagMinutes?: number;
}

export interface AnomalyDetection {
  id: string;
  metricName: string;
  timestamp: string;
  actualValue: number;
  expectedValue: number;
  anomalyScore: number;
  isAnomaly: boolean;
  severity: 'critical' | 'high' | 'medium' | 'low';
}

export interface MLPattern {
  id: string;
  name: string;
  description: string;
  category: InsightCategory;
  confidence: number;
  impact: 'high' | 'medium' | 'low';
  frequency: string;
  metrics: string[];
  detectedAt: string;
}

export interface MLRecommendation {
  id: string;
  title: string;
  description: string;
  category: InsightCategory;
  confidence: number;
  estimatedImpact: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  actionItems: string[];
  appliedAt?: string;
}

export interface MLInsightSummary {
  forecasts: WorkloadForecast[];
  correlations: MetricCorrelation[];
  anomalies: AnomalyDetection[];
  patterns: MLPattern[];
  recommendations: MLRecommendation[];
  modelAccuracy: number;
  lastTrainedAt: string;
  companyId: string;
}
