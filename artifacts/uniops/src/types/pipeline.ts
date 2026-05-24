export type PipelineStatus = 'running' | 'success' | 'failed' | 'pending' | 'cancelled' | 'skipped';

export type PipelineProvider = 'github_actions' | 'gitlab_ci' | 'jenkins' | 'circleci' | 'argocd';

export interface PipelineStage {
  id: string;
  name: string;
  status: PipelineStatus;
  duration: number;
  startedAt?: string;
  finishedAt?: string;
  logs?: string[];
  jobs: PipelineJob[];
}

export interface PipelineJob {
  id: string;
  name: string;
  status: PipelineStatus;
  duration: number;
  runner?: string;
  allowFailure: boolean;
}

export interface Pipeline {
  id: string;
  name: string;
  repository: string;
  branch: string;
  commit: string;
  commitMessage: string;
  author: string;
  authorAvatar?: string;
  status: PipelineStatus;
  provider: PipelineProvider;
  stages: PipelineStage[];
  duration: number;
  triggeredAt: string;
  finishedAt?: string;
  url?: string;
  companyId: string;
  integrationId: string;
}

export interface PipelineStats {
  total: number;
  success: number;
  failed: number;
  running: number;
  successRate: number;
  avgDuration: number;
}
