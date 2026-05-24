import { apiClient } from './client';
import type { Pod, ClusterSummary } from '@/types/pod';

interface ListParams {
  namespace?: string;
  phase?: string;
  node?: string;
  search?: string;
  integrationId?: string;
}

// FastAPI router: /kubernetes/pods/*
export const podsApi = {
  list: (params?: ListParams) =>
    apiClient.get<{ data: Pod[]; total: number }>('/kubernetes/pods', { params }).then((r) => r.data),

  // FastAPI uses pod_id (not namespace/name combo)
  get: (namespace: string, name: string) =>
    apiClient.get<Pod>(`/kubernetes/pods/${name}`).then((r) => r.data),

  getLogs: (namespace: string, name: string, container?: string, tail = 100) =>
    apiClient.get<{ lines: string[] }>(`/kubernetes/pods/${name}/logs`, {
      params: { container, tail },
    }).then((r) => r.data),

  delete: (namespace: string, name: string) =>
    apiClient.delete(`/kubernetes/pods/${name}`),

  exec: (namespace: string, name: string, command: string, container?: string) =>
    apiClient.post<{ output: string }>(`/kubernetes/pods/${name}/exec`, { command, container }).then((r) => r.data),

  getMetrics: (namespace: string, name: string) =>
    apiClient.get(`/kubernetes/pods/${name}/events`).then((r) => r.data),

  // FastAPI: /kubernetes/pods/cluster/summary
  getClusterSummary: (integrationId?: string) =>
    apiClient.get<ClusterSummary>('/kubernetes/pods/cluster/summary', { params: { integrationId } }).then((r) => r.data),

  // FastAPI: /kubernetes/pods/namespaces
  getNamespaces: () =>
    apiClient.get<string[]>('/kubernetes/pods/namespaces').then((r) => r.data),

  restart: (podId: string) =>
    apiClient.post(`/kubernetes/pods/${podId}/restart`).then((r) => r.data),

  getStats: () =>
    apiClient.get('/kubernetes/pods/stats').then((r) => r.data),
};
