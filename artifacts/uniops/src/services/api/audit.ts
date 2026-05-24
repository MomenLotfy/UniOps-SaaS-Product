import { apiClient } from './client';
import type { AuditLog } from '@/types/audit';

interface ListParams {
  userId?: string;
  action?: string;
  resource?: string;
  startDate?: string;
  endDate?: string;
  page?: number;
  limit?: number;
  search?: string;
}

// FastAPI mounts audit router at /audit-logs (not /audit/logs)
export const auditApi = {
  list: (params?: ListParams) =>
    apiClient.get<{ data: AuditLog[]; total: number }>('/audit-logs', { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<AuditLog>(`/audit-logs/${id}`).then((r) => r.data),

  exportCSV: (params?: ListParams) =>
    apiClient.get('/audit-logs/export/csv', { params, responseType: 'blob' }).then((r) => r.data),

  exportPDF: (params?: ListParams) =>
    apiClient.get('/audit-logs/export/pdf', { params, responseType: 'blob' }).then((r) => r.data),

  getStats: (params?: { startDate?: string; endDate?: string }) =>
    apiClient.get('/audit-logs/summary', { params }).then((r) => r.data),

  getByUser: (userId: string, params?: { page?: number; limit?: number }) =>
    apiClient.get<{ data: AuditLog[]; total: number }>(`/audit-logs`, {
      params: { ...params, user_id: userId },
    }).then((r) => r.data),
};
