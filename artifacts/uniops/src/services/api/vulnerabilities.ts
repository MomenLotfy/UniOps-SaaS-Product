import { apiClient } from './client';
import type { Vulnerability, VulnerabilityStats } from '@/types/vulnerability';

interface ListParams {
  severity?: string;
  status?: string;
  type?: string;
  assetType?: string;
  page?: number;
  limit?: number;
  search?: string;
}

// FastAPI router: /vulnerabilities/* (was /security/vulnerabilities/*)
export const vulnerabilitiesApi = {
  list: (params?: ListParams) =>
    apiClient.get<{ data: Vulnerability[]; total: number }>('/vulnerabilities', { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Vulnerability>(`/vulnerabilities/${id}`).then((r) => r.data),

  getStats: () =>
    apiClient.get<VulnerabilityStats>('/vulnerabilities/stats').then((r) => r.data),

  // FastAPI uses PATCH /{id} with status/notes in body (no /status sub-path)
  updateStatus: (id: string, status: Vulnerability['status'], notes?: string) =>
    apiClient.patch<Vulnerability>(`/vulnerabilities/${id}`, { status, notes }).then((r) => r.data),

  // FastAPI uses PATCH /{id} with assigned_to in body (no /assign sub-path)
  assign: (id: string, userId: string) =>
    apiClient.patch<Vulnerability>(`/vulnerabilities/${id}`, { assigned_to: userId }).then((r) => r.data),

  // Scan triggers security_scan endpoint
  scan: (integrationId: string) =>
    apiClient.post('/security/scan', { integration_id: integrationId }).then((r) => r.data),

  exportReport: (params?: ListParams, format: 'pdf' | 'csv' | 'json' = 'pdf') =>
    apiClient.get('/vulnerabilities/export', { params: { ...params, format }, responseType: 'blob' })
      .then((r) => r.data)
      .catch(() => null),

  // FastAPI uses PATCH /{id} for each — bulk via individual calls
  bulkUpdateStatus: (ids: string[], status: Vulnerability['status']) =>
    Promise.all(ids.map((id) =>
      apiClient.patch<Vulnerability>(`/vulnerabilities/${id}`, { status }).then((r) => r.data)
    )),
};
