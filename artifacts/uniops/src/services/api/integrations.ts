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

  // ── Generic token connect (idempotent) ────────────────────────────────────
  // For all token-style providers (Bitbucket, Azure DevOps, Slack, Teams,
  // Discord, Snyk, Okta, Auth0, Entra, Jira, ServiceNow, Linear, PagerDuty,
  // Prometheus, Grafana, Datadog, Loki, Trivy, DefectDojo, Wiz, Jenkins,
  // ArgoCD, GCS, Azure Blob, Docker Registry, Harbor, Email, Webhook).
  // Backend's create() merges singleton types, so this never produces dupes.
  connectByToken: async (
    provider: string,
    token: string,
    name?: string,
    extraConfig: Record<string, string> = {},
  ): Promise<Integration | undefined> => {
    const res = await apiClient.post<any>('/integrations', {
      name: name ?? provider,
      type: provider,
      credentials: { token },
      config: extraConfig,
      is_active: true,
    });
    const integrationId = res.data?.data?.id ?? res.data?.id;
    if (integrationId) {
      await apiClient.post(`/integrations/${integrationId}/test`).catch(() => {});
    }
    return integrationId ? integrationsApi.get(integrationId) : undefined;
  },

  // ── VCS ───────────────────────────────────────────────────────────────────
  connectBitbucket: (token: string, name: string = 'Bitbucket', host?: string) =>
    integrationsApi.connectByToken('bitbucket', token, name, host ? { url: host } : {}),

  connectAzureDevOps: (token: string, name: string = 'Azure DevOps', host?: string) =>
    integrationsApi.connectByToken('azure_devops', token, name, host ? { url: host } : {}),

  // ── Communication ─────────────────────────────────────────────────────────
  connectSlack: (webhookUrl: string, channel: string) =>
    integrationsApi.connectByToken('slack', webhookUrl, 'Slack', { channel }),

  connectTeams: (webhookUrl: string) =>
    integrationsApi.connectByToken('teams', webhookUrl, 'Microsoft Teams', {}),

  connectDiscord: (webhookUrl: string) =>
    integrationsApi.connectByToken('discord', webhookUrl, 'Discord', {}),

  // ── Monitoring ────────────────────────────────────────────────────────────
  connectPrometheus: (token: string, name: string, url: string) =>
    integrationsApi.connectByToken('prometheus', token, name, { url }),

  connectGrafana: (token: string, name: string, url: string) =>
    integrationsApi.connectByToken('grafana', token, name, { url }),

  connectDatadog: (apiKey: string, name: string, site: string = 'datadoghq.com') =>
    integrationsApi.connectByToken('datadog', apiKey, name, { site }),

  connectLoki: (token: string, name: string, url: string) =>
    integrationsApi.connectByToken('loki', token, name, { url }),

  // ── Security ──────────────────────────────────────────────────────────────
  connectTrivy: (token: string, name: string = 'Trivy') =>
    integrationsApi.connectByToken('trivy', token, name, {}),

  connectDefectDojo: (token: string, name: string, host: string) =>
    integrationsApi.connectByToken('defectdojo', token, name, { host }),

  connectSnyk: (token: string, name: string = 'Snyk') =>
    integrationsApi.connectByToken('snyk', token, name, {}),

  connectWiz: (clientId: string, clientSecret: string, name: string = 'Wiz') =>
    integrationsApi.connectByToken('wiz', clientSecret, name, { client_id: clientId }),

  // ── Identity ──────────────────────────────────────────────────────────────
  connectOkta: (token: string, name: string, domain: string) =>
    integrationsApi.connectByToken('okta', token, name, { domain }),

  connectAuth0: (clientSecret: string, name: string, domain: string) =>
    integrationsApi.connectByToken('auth0', clientSecret, name, { domain }),

  connectEntraId: (clientSecret: string, name: string, tenantId: string) =>
    integrationsApi.connectByToken('entra_id', clientSecret, name, { tenant_id: tenantId }),

  // ── Ticketing ─────────────────────────────────────────────────────────────
  connectJira: (token: string, name: string, jiraUrl: string) =>
    integrationsApi.connectByToken('jira', token, name, { url: jiraUrl }),

  connectServiceNow: (token: string, name: string = 'ServiceNow') =>
    integrationsApi.connectByToken('servicenow', token, name, {}),

  connectLinear: (token: string, name: string = 'Linear') =>
    integrationsApi.connectByToken('linear', token, name, {}),

  connectPagerDuty: (token: string, name: string = 'PagerDuty') =>
    integrationsApi.connectByToken('pagerduty', token, name, {}),

  // ── CI/CD ─────────────────────────────────────────────────────────────────
  connectJenkins: (token: string, name: string, host: string) =>
    integrationsApi.connectByToken('jenkins', token, name, { host }),

  connectArgoCD: (token: string, name: string, serverUrl: string) =>
    integrationsApi.connectByToken('argocd', token, name, { url: serverUrl }),

  connectGitHubActions: (token: string, name: string = 'GitHub Actions') =>
    integrationsApi.connectByToken('github_actions', token, name, {}),

  connectGitLabCI: (token: string, name: string = 'GitLab CI', url?: string) =>
    integrationsApi.connectByToken('gitlab_ci', token, name, url ? { url } : {}),

  // ── Containers ────────────────────────────────────────────────────────────
  connectDockerRegistry: (token: string, name: string, registryUrl: string) =>
    integrationsApi.connectByToken('docker_registry', token, name, { url: registryUrl }),

  connectHarbor: (token: string, name: string, harborUrl: string) =>
    integrationsApi.connectByToken('harbor', token, name, { url: harborUrl }),

  // ── Storage ───────────────────────────────────────────────────────────────
  connectAzureBlob: (accountKey: string, name: string, accountName: string) =>
    integrationsApi.connectByToken('azure_blob', accountKey, name, { account_name: accountName }),

  connectGCS: (serviceAccountJson: string, name: string, projectId: string) =>
    integrationsApi.connectByToken('gcs', serviceAccountJson, name, { project_id: projectId }),

  // ── Email ─────────────────────────────────────────────────────────────────
  connectEmail: (smtpPassword: string, name: string) =>
    integrationsApi.connectByToken('email', smtpPassword, name, {}),

  // ── Webhook ───────────────────────────────────────────────────────────────
  connectWebhook: (webhookUrl: string, name: string = 'Webhook') =>
    integrationsApi.connectByToken('webhook', webhookUrl, name, {}),
};
