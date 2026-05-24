import { apiClient } from './client';
import type { Integration } from '@/types/integration';

/** Normalise a raw backend IntegrationResponse → frontend Integration shape. */
function normalise(raw: any): Integration {
  return {
    id:          raw.id,
    provider:    raw.provider ?? raw.type,
    name:        raw.name,
    description: raw.description ?? '',
    status:      raw.status,
    lastSync:    raw.lastSync ?? raw.last_sync ?? raw.updated_at,
    error:       raw.error_message ?? raw.error ?? undefined,
    config:      raw.config ?? {},
    createdAt:   raw.createdAt ?? raw.created_at,
    createdBy:   raw.createdBy ?? raw.created_by ?? '',
  };
}

export const integrationsApi = {
  list: () =>
    apiClient.get<any>('/integrations')
      .then((r) => {
        const body = r.data as any;
        const raw: any[] = Array.isArray(body) ? body : (body?.data ?? []);
        return raw.map(normalise);
      }),

  get: (id: string) =>
    apiClient.get<any>(`/integrations/${id}`)
      .then((r) => normalise(r.data?.data ?? r.data)),

  create: (data: Partial<Integration>) =>
    apiClient.post<any>('/integrations', data)
      .then((r) => normalise(r.data?.data ?? r.data)),

  update: (id: string, data: Partial<Integration>) =>
    apiClient.patch<any>(`/integrations/${id}`, data)
      .then((r) => normalise(r.data?.data ?? r.data)),

  delete: (id: string) =>
    apiClient.delete(`/integrations/${id}`),

  testConnection: (id: string) =>
    apiClient.post<{ success: boolean; message: string }>(`/integrations/${id}/test`)
      .then((r) => r.data),

  syncNow: (id: string) =>
    apiClient.post(`/integrations/${id}/sync`).then((r) => r.data),

  // ── GitHub (idempotent) ───────────────────────────────────────────────────
  connectGitHub: async (token: string, name: string = 'GitHub'): Promise<Integration | undefined> => {
    const existing = await integrationsApi.list()
      .then(list => list.find((i) => i.provider === 'github'))
      .catch(() => null);

    let integrationId: string;

    if (existing) {
      await apiClient.patch(`/integrations/${existing.id}`, { token, is_active: true });
      integrationId = existing.id;
    } else {
      const res = await apiClient.post<any>('/integrations', {
        name, type: 'github', credentials: { token }, is_active: true,
      });
      integrationId = res.data?.data?.id ?? res.data?.id;
      if (integrationId) {
        await apiClient.patch(`/integrations/${integrationId}`, { token }).catch(() => {});
      }
    }

    if (integrationId) {
      await apiClient.post(`/integrations/${integrationId}/test`).catch(() => {});
    }
    return integrationId ? integrationsApi.get(integrationId) : undefined;
  },

  // ── GitLab (idempotent) ───────────────────────────────────────────────────
  connectGitLab: async (token: string, name: string = 'GitLab'): Promise<Integration | undefined> => {
    const existing = await integrationsApi.list()
      .then(list => list.find((i) => i.provider === 'gitlab'))
      .catch(() => null);

    let integrationId: string;

    if (existing) {
      await apiClient.patch(`/integrations/${existing.id}`, { token, is_active: true });
      integrationId = existing.id;
    } else {
      const res = await apiClient.post<any>('/integrations', {
        name, type: 'gitlab', credentials: { token }, is_active: true,
      });
      integrationId = res.data?.data?.id ?? res.data?.id;
      if (integrationId) {
        await apiClient.patch(`/integrations/${integrationId}`, { token }).catch(() => {});
      }
    }

    if (integrationId) {
      await apiClient.post(`/integrations/${integrationId}/test`).catch(() => {});
    }
    return integrationId ? integrationsApi.get(integrationId) : undefined;
  },

  // ── Cloud providers — use generic POST /integrations with type ────────────
  connectAWS: (payload: { roleArn: string; externalId: string; region: string }) =>
    apiClient.post<any>('/integrations', {
      name: 'AWS',
      type: 'aws',
      credentials: payload,
      is_active: true,
    }).then((r) => normalise(r.data?.data ?? r.data)),

  connectGCP: (payload: { projectId: string; serviceAccountKey: string }) =>
    apiClient.post<any>('/integrations', {
      name: 'GCP',
      type: 'gcp',
      credentials: payload,
      is_active: true,
    }).then((r) => normalise(r.data?.data ?? r.data)),

  connectAzure: (payload: {
    tenantId: string; clientId: string; clientSecret: string; subscriptionId: string;
  }) =>
    apiClient.post<any>('/integrations', {
      name: 'Azure',
      type: 'azure',
      credentials: payload,
      is_active: true,
    }).then((r) => normalise(r.data?.data ?? r.data)),

  connectKubernetes: (kubeconfig: string, clusterName: string) =>
    apiClient.post<any>('/integrations', {
      name: clusterName,
      type: 'kubernetes',
      credentials: { kubeconfig },
      is_active: true,
    }).then((r) => normalise(r.data?.data ?? r.data)),

  connectSlack: (webhookUrl: string, channel: string) =>
    apiClient.post<any>('/integrations', {
      name: 'Slack',
      type: 'slack',
      credentials: { webhook_url: webhookUrl, channel },
      is_active: true,
    }).then((r) => normalise(r.data?.data ?? r.data)),

  connectTeams: (webhookUrl: string) =>
    apiClient.post<any>('/integrations', {
      name: 'Microsoft Teams',
      type: 'teams',
      credentials: { webhook_url: webhookUrl },
      is_active: true,
    }).then((r) => normalise(r.data?.data ?? r.data)),
};
