/**
 * useCostData — React Query hooks for the FinOps Cost Center.
 *
 * Replaces the manual useApi + setInterval polling pattern with:
 *   - staleTime: 30s  (don't refetch if data is fresh)
 *   - refetchInterval: 30s background polling (only while tab is visible)
 *   - refetchIntervalInBackground: false  (stops when tab hidden)
 *   - refetchOnWindowFocus: true  (refetch on tab re-focus)
 *   - Mutations with automatic cache invalidation + toast feedback
 */
import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';
import { apiClient } from '@/services/api/client';
import { toast } from 'sonner';

// ── Types ──────────────────────────────────────────────────────────────────

export interface CostSummary {
  // Frontend-facing fields (fixed in backend)
  mtd:          number;
  projected:    number;
  daily_avg:    number;
  ytd:          number;
  connected:    boolean;
  has_data:     boolean;
  prev_month:   number;
  trend_pct:    number;
  // Integration health — drives precise UI state
  integration_status: 'connected' | 'error' | 'pending' | 'disconnected' | null;
  integration_error:  string | null;
  last_sync:          string | null;
  // Legacy fields (kept for backwards compat)
  total_cost:   number;
  mtd_cost:     number;
  forecast_eom: number;
  by_provider:  Record<string, number>;
}

export interface CostBreakdownItem {
  service:      string;
  provider:     string;
  mtd:          number;
  pct_of_total: number;
  change_pct:   number;
  prev_month:   number;
}

export interface ForecastPoint {
  date:       string;   // "May 23"
  day:        string;   // alias
  actual?:    number;
  predicted?: number;
  projected?: number;   // alias
}

export interface CostForecast {
  accuracy:     number;
  eom_forecast: number;
  budget:       number;
  over_budget:  boolean;
  daily_avg:    number;
  points:       ForecastPoint[];
  insight:      string;
}

export interface CostAnomaly {
  id:              string;
  service:         string;
  severity:        'low' | 'medium' | 'high' | 'critical';
  status:          'open' | 'investigating' | 'resolved' | 'dismissed';
  description:     string;
  expected_amount: number;
  actual_amount:   number;
  deviation_pct:   number;
  detected_date:   string | null;
  root_cause:      string | null;
  recommendation:  string | null;
}

export interface Saving {
  id:                string;
  title:             string;
  description:       string | null;
  category:          string;
  provider:          string;
  potential_savings: number;
  currency:          string;
  effort:            'low' | 'medium' | 'high';
  status:            'pending' | 'open' | 'applied' | 'dismissed';
  resource:          string | null;
  recommendation:    string | null;
}

// ── Query key factory ──────────────────────────────────────────────────────

export const costKeys = {
  all:       ['costs'] as const,
  summary:   () => [...costKeys.all, 'summary'] as const,
  breakdown: () => [...costKeys.all, 'breakdown'] as const,
  forecast:  () => [...costKeys.all, 'forecast'] as const,
  anomalies: (status?: string) => [...costKeys.all, 'anomalies', status] as const,
  savings:   (status?: string) => [...costKeys.all, 'savings', status] as const,
};

// ── Shared query config ────────────────────────────────────────────────────

const REFETCH_INTERVAL   = 30_000;   // 30 s
const STALE_TIME         = 30_000;   // data fresh for 30 s
const ERROR_RETRY        = 2;        // retry failed requests twice

const sharedQueryConfig = {
  staleTime:                   STALE_TIME,
  refetchInterval:             REFETCH_INTERVAL,
  refetchIntervalInBackground: false,   // ← stops polling when tab hidden
  refetchOnWindowFocus:        true,    // ← re-fetches when user returns
  retry:                       ERROR_RETRY,
  retryDelay: (attempt: number) => Math.min(1000 * 2 ** attempt, 10_000),
} as const;

// ── API helper ─────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string): Promise<T> {
  const res = await apiClient.get<{ data: T }>(path);
  return res.data.data;
}

// ── Hooks ──────────────────────────────────────────────────────────────────

/** Summary: MTD, projected, daily_avg, ytd, connected flag */
export function useCostSummary(): UseQueryResult<CostSummary> {
  return useQuery({
    ...sharedQueryConfig,
    queryKey: costKeys.summary(),
    queryFn:  () => apiFetch<CostSummary>('/costs/summary'),
  });
}

/** Per-service breakdown with change_pct vs previous month */
export function useCostBreakdown(): UseQueryResult<CostBreakdownItem[]> {
  return useQuery({
    ...sharedQueryConfig,
    queryKey: costKeys.breakdown(),
    queryFn:  () => apiFetch<CostBreakdownItem[]>('/costs/breakdown'),
  });
}

/** Forecast chart data + accuracy + budget status */
export function useCostForecast(): UseQueryResult<CostForecast> {
  return useQuery({
    ...sharedQueryConfig,
    staleTime:       60_000,   // forecast is slower-changing, cache for 1 min
    refetchInterval: 60_000,
    queryKey: costKeys.forecast(),
    queryFn:  () => apiFetch<CostForecast>('/costs/forecast'),
  });
}

/** Anomaly list (filtered by status) */
export function useCostAnomalies(status?: string): UseQueryResult<CostAnomaly[]> {
  return useQuery({
    ...sharedQueryConfig,
    queryKey: costKeys.anomalies(status),
    queryFn:  () => {
      const qs = status ? `?status=${status}` : '';
      return apiFetch<CostAnomaly[]>(`/costs/anomalies${qs}`);
    },
  });
}

/** Savings list (filtered by status) */
export function useSavings(status?: string): UseQueryResult<Saving[]> {
  return useQuery({
    ...sharedQueryConfig,
    queryKey: costKeys.savings(status),
    queryFn:  () => {
      const qs = status ? `?status=${status}` : '';
      return apiFetch<Saving[]>(`/savings${qs}`);
    },
  });
}

// ── Mutations ──────────────────────────────────────────────────────────────

/** Investigate anomaly → status: "investigating" */
export function useInvestigateAnomaly() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (anomalyId: string) =>
      apiClient.post(`/costs/anomalies/${anomalyId}/investigate`),
    onSuccess: (_, anomalyId) => {
      qc.invalidateQueries({ queryKey: costKeys.anomalies() });
      toast.success('Investigation started');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? 'Failed to start investigation');
    },
  });
}

/** Resolve anomaly → status: "resolved" */
export function useResolveAnomaly() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (anomalyId: string) =>
      apiClient.post(`/costs/anomalies/${anomalyId}/resolve`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: costKeys.anomalies() });
      toast.success('Anomaly resolved');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? 'Failed to resolve anomaly');
    },
  });
}

/** Dismiss anomaly → status: "dismissed" */
export function useDismissAnomaly() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (anomalyId: string) =>
      apiClient.post(`/costs/anomalies/${anomalyId}/dismiss`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: costKeys.anomalies() });
      toast.success('Anomaly dismissed');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? 'Failed to dismiss anomaly');
    },
  });
}

/** Apply saving recommendation */
export function useApplySaving() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (savingId: string) =>
      apiClient.post(`/savings/${savingId}/apply`),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: costKeys.savings() });
      qc.invalidateQueries({ queryKey: costKeys.summary() });
      const msg = res.data?.data?.message ?? 'Saving applied successfully';
      toast.success(msg);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? 'Failed to apply saving';
      if (err?.response?.status === 429) {
        toast.error('Too many requests — please wait a moment');
      } else {
        toast.error(detail);
      }
    },
  });
}

/** Dismiss saving recommendation */
export function useDismissSaving() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (savingId: string) =>
      apiClient.post(`/savings/${savingId}/dismiss`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: costKeys.savings() });
      toast.info('Recommendation dismissed');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? 'Failed to dismiss recommendation');
    },
  });
}

/** Invalidate all cost data — e.g. after a manual sync trigger */
export function useInvalidateAllCostData() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: costKeys.all });
}

/**
 * Trigger a real AWS cost sync on the backend (POST /costs/sync).
 * On success, invalidates the full cost cache so all panels refresh.
 */
export function useTriggerCostSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post('/costs/sync'),
    onSuccess: (res) => {
      const triggered = res.data?.data?.triggered;
      const status    = res.data?.data?.status;
      if (!triggered) {
        toast.warning(res.data?.message ?? 'No AWS integration configured');
        return;
      }
      toast.success(
        status === 'error'
          ? 'Sync started — credentials will be re-tested'
          : 'Cost sync started — data will refresh in a few seconds',
      );
      // Delay re-fetch to give the background sync time to write data
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: costKeys.all });
      }, 5_000);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? 'Failed to trigger cost sync');
    },
  });
}
