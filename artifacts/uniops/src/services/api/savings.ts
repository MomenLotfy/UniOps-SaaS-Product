import { apiClient } from './client';
import type { SavingsRecommendation } from '@/types/cost';

interface ListParams {
  provider?: string;
  category?: string;
  effort?: string;
  applied?: boolean;
}

// FastAPI router: /savings/* (was /finops/savings/*)
export const savingsApi = {
  list: (params?: ListParams) =>
    apiClient.get<SavingsRecommendation[]>('/savings', { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<SavingsRecommendation>(`/savings/${id}`).then((r) => r.data),

  apply: (id: string) =>
    apiClient.post<SavingsRecommendation>(`/savings/${id}/apply`).then((r) => r.data),

  // /dismiss not in FastAPI yet — no-op with graceful fallback
  dismiss: (id: string, reason?: string) =>
    apiClient.post(`/savings/${id}/dismiss`, { reason })
      .then((r) => r.data)
      .catch(() => null),

  getTotalSavings: () =>
    apiClient.get<{ applied: number; potential: number; currency: string }>('/savings/total').then((r) => r.data),

  // /refresh not in FastAPI yet — no-op
  refresh: () =>
    Promise.resolve(null),
};
