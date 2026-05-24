import { apiClient } from './client';
import type { Pipeline, PipelineStats } from '@/types/pipeline';

interface ListParams {
  page?: number;
  limit?: number;
  status?: string;
  repository?: string;
  branch?: string;
  integrationId?: string;
  search?: string;
}

// FastAPI router: /pipelines/*
export const pipelinesApi = {
  list: (params?: ListParams) =>
    apiClient.get<{ data: Pipeline[]; total: number }>('/pipelines', { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Pipeline>(`/pipelines/${id}`).then((r) => r.data),

  getStats: () =>
    apiClient.get<PipelineStats>('/pipelines/stats').then((r) => r.data),

  // FastAPI uses /rerun (not /retry)
  retry: (id: string) =>
    apiClient.post<Pipeline>(`/pipelines/${id}/rerun`).then((r) => r.data),

  // cancel not in FastAPI — graceful no-op
  cancel: (id: string) =>
    Promise.reject(new Error('Pipeline cancel not yet available')),

  // Logs via jobs endpoint
  getLogs: (id: string, stageId: string, jobId: string) =>
    apiClient.get<{ lines: string[] }>(`/pipelines/${id}/jobs`).then((r) => r.data),

  // History via list with repository filter
  getHistory: (repository: string, branch?: string, limit = 20) =>
    apiClient.get<Pipeline[]>('/pipelines', {
      params: { repository, branch, page_size: limit },
    }).then((r) => r.data),

  // Trigger manual sync
  sync: () =>
    apiClient.post('/pipelines/sync').then((r) => r.data),

  // List repositories
  getRepositories: () =>
    apiClient.get('/pipelines/repositories').then((r) => r.data),
};
