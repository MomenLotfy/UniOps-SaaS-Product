import { apiClient } from './client';
import type { CostMetric, CostBreakdown, CostDataPoint, BudgetAlert } from '@/types/cost';

interface CostParams {
  provider?: string;
  period?: string;
  startDate?: string;
  endDate?: string;
  groupBy?: 'service' | 'provider' | 'region' | 'tag';
}

// FastAPI router: /costs/* (was /finops/costs/*)
export const costsApi = {
  getSummary: (params?: CostParams) =>
    apiClient.get<CostMetric>('/costs/summary', { params }).then((r) => r.data),

  getBreakdown: (params?: CostParams) =>
    apiClient.get<CostBreakdown[]>('/costs/breakdown', { params }).then((r) => r.data),

  // /costs/forecast serves time-series data in FastAPI (replaces /finops/costs/timeseries)
  getTimeSeries: (params?: CostParams) =>
    apiClient.get<CostDataPoint[]>('/costs/forecast', { params }).then((r) => r.data),

  // Budget endpoints are not yet in FastAPI — return empty arrays gracefully
  getBudgets: (): Promise<BudgetAlert[]> =>
    Promise.resolve([]),

  createBudget: (data: Partial<BudgetAlert>): Promise<BudgetAlert> =>
    Promise.reject(new Error('Budget management not yet available')),

  updateBudget: (id: string, data: Partial<BudgetAlert>): Promise<BudgetAlert> =>
    Promise.reject(new Error('Budget management not yet available')),

  deleteBudget: (id: string): Promise<void> =>
    Promise.reject(new Error('Budget management not yet available')),

  getAnomalies: (params?: CostParams) =>
    apiClient.get('/costs/anomalies', { params }).then((r) => r.data),

  exportReport: (params?: CostParams, format: 'pdf' | 'csv' = 'pdf') =>
    apiClient.get('/costs/export', { params: { ...params, format }, responseType: 'blob' })
      .then((r) => r.data)
      .catch(() => null), // graceful fallback if not available
};
