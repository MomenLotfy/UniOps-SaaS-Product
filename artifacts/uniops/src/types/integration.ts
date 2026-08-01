export type IntegrationProvider =
  // Cloud
  | 'aws' | 'gcp' | 'azure'
  // VCS
  | 'github' | 'gitlab' | 'bitbucket' | 'azure_devops'
  // Containers
  | 'kubernetes' | 'docker_registry' | 'harbor'
  // CI/CD
  | 'github_actions' | 'gitlab_ci' | 'jenkins' | 'argocd'
  // Communication
  | 'slack' | 'teams' | 'discord' | 'email'
  // Monitoring
  | 'prometheus' | 'grafana' | 'datadog' | 'loki'
  // Security
  | 'trivy' | 'defectdojo' | 'snyk' | 'wiz'
  // Identity
  | 'okta' | 'auth0' | 'entra_id'
  // Ticketing
  | 'jira' | 'servicenow' | 'linear' | 'pagerduty'
  // Storage
  | 's3' | 'azure_blob' | 'gcs'
  // Misc
  | 'terraform' | 'webhook';

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
  category: 'cloud' | 'vcs' | 'orchestration' | 'communication' | 'monitoring' | 'security' | 'identity' | 'ticketing' | 'storage';
  authType: 'oauth' | 'api_key' | 'iam_role' | 'kubeconfig' | 'webhook' | 'none';
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
