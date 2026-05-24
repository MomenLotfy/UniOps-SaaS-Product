import { apiClient } from './client';
import type { Alert } from '@/types/alert';

interface ListParams {
  severity?: string;
  status?: string;
  category?: string;
  page?: number;
  limit?: number;
  search?: string;
  startDate?: string;
  endDate?: string;
}

// FastAPI router: /alerts/*
export const alertsApi = {
  list: (params?: ListParams) =>
    apiClient.get<{ data: Alert[]; total: number }>('/alerts', { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Alert>(`/alerts/${id}`).then((r) => r.data),

  // FastAPI uses PATCH /{id} — acknowledge maps to status: 'acknowledged'
  acknowledge: (id: string) =>
    apiClient.patch<Alert>(`/alerts/${id}`, { status: 'acknowledged', is_read: true }).then((r) => r.data),

  // resolve maps to status: 'resolved'
  resolve: (id: string, notes?: string) =>
    apiClient.patch<Alert>(`/alerts/${id}`, { status: 'resolved', notes }).then((r) => r.data),

  // snooze not directly in FastAPI — maps to PATCH with snoozed_until
  snooze: (id: string, until: string) =>
    apiClient.patch<Alert>(`/alerts/${id}`, { snoozed_until: until }).then((r) => r.data),

  bulkAcknowledge: (ids: string[]) =>
    apiClient.post('/alerts/bulk/mark-read', { ids }).then((r) => r.data),

  bulkResolve: (ids: string[]) =>
    apiClient.post('/alerts/bulk/resolve', { ids }).then((r) => r.data),

  getStats: () =>
    apiClient.get('/alerts/stats').then((r) => r.data),

  // Alert rules not in FastAPI yet — graceful no-ops
  createRule: (rule: { name: string; condition: string; severity: string; channels: string[] }) =>
    Promise.reject(new Error('Alert rules not yet available')),

  getRules: (): Promise<any[]> =>
    Promise.resolve([]),

  deleteRule: (id: string) =>
    Promise.reject(new Error('Alert rules not yet available')),
};
