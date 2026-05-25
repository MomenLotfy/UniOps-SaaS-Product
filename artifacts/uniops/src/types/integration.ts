export type IntegrationProvider =
  | 'aws' | 'gcp' | 'azure'
  | 'github' | 'gitlab' | 'bitbucket'
  | 'kubernetes' | 'terraform'
  | 'slack' | 'teams' | 'pagerduty'
  | 'datadog' | 'grafana' | 'prometheus'
  | 'webhook';

export type IntegrationStatus =
  | 'connected'          // credentials verified — all systems go
  | 'sync_failed'        // credentials valid but last data sync failed (permissions/rate-limit)
  | 'credentials_invalid' // wrong Access Key / Secret Key
  | 'pending'            // saved — background test in progress
  | 'error'              // legacy generic error (mapped to credentials_invalid in UI)
  | 'disconnected';      // explicitly removed by user

export interface Integration {
  id: string;
  provider: IntegrationProvider;
  name: string;
  description: string;
  status: IntegrationStatus;
  lastSync?: string;
  error?: string;
  config: Record<string, unknown>;
  createdAt: string;
  createdBy: string;
}

export interface IntegrationMeta {
  provider: IntegrationProvider;
  label: string;
  description: string;
  icon: string;
  category: 'cloud' | 'vcs' | 'orchestration' | 'communication' | 'monitoring';
  authType: 'oauth' | 'api_key' | 'iam_role' | 'kubeconfig' | 'webhook';
  docsUrl: string;
}

export interface AWSConfig {
  accountId: string;
  region: string;
  roleArn: string;
  externalId: string;
}

export interface GitHubConfig {
  accessToken: string;
  organization: string;
  selectedRepos: string[];
}

export interface KubernetesConfig {
  clusterName: string;
  serverUrl: string;
  certificateAuthorityData: string;
  namespace: string;
}

export interface WebhookConfig {
  url: string;
  secret: string;
  events: string[];
  method: 'POST' | 'PUT';
}
