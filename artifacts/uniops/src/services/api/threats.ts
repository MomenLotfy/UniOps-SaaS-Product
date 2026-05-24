import { apiClient } from './client';
import type { Threat, ThreatStats } from '@/types/threat';

interface ListParams {
  severity?: string;
  status?: string;
  category?: string;
  assignedTo?: string;
  page?: number;
  limit?: number;
  search?: string;
}

// FastAPI router: /threats/*
export const threatsApi = {
  list: (params?: ListParams) =>
    apiClient.get<{ data: Threat[]; total: number }>('/threats', { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Threat>(`/threats/${id}`).then((r) => r.data),

  getStats: () =>
    apiClient.get<ThreatStats>('/threats/stats').then((r) => r.data),

  // FastAPI uses PATCH /{id} with status in body (no /status sub-path)
  updateStatus: (id: string, status: Threat['status'], notes?: string) =>
    apiClient.patch<Threat>(`/threats/${id}`, { status, notes }).then((r) => r.data),

  // FastAPI uses PATCH /{id} with assigned_to in body
  assign: (id: string, userId: string) =>
    apiClient.patch<Threat>(`/threats/${id}`, { assigned_to: userId }).then((r) => r.data),

  addComment: (id: string, comment: string) =>
    apiClient.patch(`/threats/${id}`, { comment }).then((r) => r.data),

  // /resolve and /suppress are explicit endpoints in FastAPI
  resolve: (id: string, notes?: string) =>
    apiClient.post(`/threats/${id}/resolve`, { notes }).then((r) => r.data),

  suppress: (id: string, reason?: string) =>
    apiClient.post(`/threats/${id}/suppress`, { reason }).then((r) => r.data),

  getTimeline: (id: string) =>
    apiClient.get(`/threats/${id}`).then((r) => r.data),

  // Bulk via individual PATCH calls
  bulkUpdate: (ids: string[], status: Threat['status']) =>
    Promise.all(ids.map((id) =>
      apiClient.patch<Threat>(`/threats/${id}`, { status }).then((r) => r.data)
    )),
};
