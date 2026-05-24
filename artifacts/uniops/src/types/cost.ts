export type CloudProvider = 'aws' | 'gcp' | 'azure' | 'oci' | 'alibaba';

export type CostPeriod = 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly';

export type AnomalyType = 'spike' | 'drop' | 'unusual_pattern' | 'budget_exceeded';

export interface CostDataPoint {
  date: string;
  amount: number;
  provider: CloudProvider;
  service?: string;
}

export interface CostBreakdown {
  service: string;
  provider: CloudProvider;
  amount: number;
  percentage: number;
  trend: number;
  region?: string;
}

export interface BudgetAlert {
  id: string;
  name: string;
  threshold: number;
  current: number;
  percentage: number;
  provider?: CloudProvider;
  alertAt: number;
  notified: boolean;
}

export interface CostAnomaly {
  id: string;
  type: AnomalyType;
  service: string;
  provider: CloudProvider;
  expectedAmount: number;
  actualAmount: number;
  deviation: number;
  deviationPercentage: number;
  detectedAt: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  resolved: boolean;
}

export interface SavingsRecommendation {
  id: string;
  title: string;
  description: string;
  provider: CloudProvider;
  service: string;
  estimatedSavings: number;
  effort: 'low' | 'medium' | 'high';
  category: 'rightsizing' | 'reserved_instances' | 'unused_resources' | 'storage_optimization' | 'networking';
  applied: boolean;
  appliedAt?: string;
}

export interface CostMetric {
  period: CostPeriod;
  totalCost: number;
  previousPeriodCost: number;
  trend: number;
  breakdown: CostBreakdown[];
  dataPoints: CostDataPoint[];
  budgets: BudgetAlert[];
  anomalies: CostAnomaly[];
  recommendations: SavingsRecommendation[];
  companyId: string;
}
