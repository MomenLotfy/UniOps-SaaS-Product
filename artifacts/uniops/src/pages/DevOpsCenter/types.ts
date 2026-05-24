// ─────────────────────────────────────────────────────────────────────────────
// DevOpsCenter — shared types
// ─────────────────────────────────────────────────────────────────────────────

export type DevOpsTab =
  | 'kubernetes'
  | 'workloads'
  | 'network'
  | 'jobs'
  | 'config'
  | 'hpa'
  | 'pipelines'
  | 'history';

// ── Pod ──────────────────────────────────────────────────────────────────────
export type PodStatus =
  | 'Running' | 'Pending' | 'Failed'
  | 'CrashLoopBackOff' | 'Terminating' | 'OOMKilled'
  | 'Error' | 'Completed' | 'Unknown';

export interface PodContainer {
  name: string;
  image: string;
  ready: boolean;
  state: 'running' | 'waiting' | 'terminated';
  restartCount: number;
}

export interface K8sEvent {
  type: 'Normal' | 'Warning';
  reason: string;
  message: string;
  count: number;
  first_time: string | null;
  last_time: string | null;
}

export interface PodRow {
  id: string;
  name: string;
  namespace: string;
  cluster?: string;
  status: PodStatus;
  restart_count: number;
  cpu_usage?: number;
  cpu_limit?: number;
  cpu_usage_pct?: number;
  memory_usage?: number;
  memory_limit?: number;
  memory_usage_pct?: number;
  containers?: PodContainer[];
  created_at: string;
  node?: string;
}

// ── Pipeline ─────────────────────────────────────────────────────────────────
export type PipelineStatus =
  | 'success' | 'failed' | 'running' | 'pending'
  | 'cancelled' | 'canceled' | 'queued' | 'skipped'
  | 'in_progress' | 'waiting' | 'timed_out' | 'error';

export interface PipelineJob {
  id: string;
  name: string;
  stage?: string;
  status: PipelineStatus;
  duration?: number;
  web_url?: string;
  allow_failure?: boolean;
}

export interface PipelineRow {
  id: string;
  name: string;
  repository: string;
  branch: string;
  commit_sha?: string;
  commit_message?: string;
  author?: string;
  status: PipelineStatus;
  duration?: number;
  logs_url?: string;
  started_at?: string;
  finished_at?: string;
  stages?: PipelineStage[];
}

export interface PipelineStage {
  id: string;
  name: string;
  status: PipelineStatus;
  duration?: number;
  jobs: PipelineJob[];
}

// ── Stats ─────────────────────────────────────────────────────────────────────
export interface PodStats {
  total: number;
  running: number;
  pending: number;
  failed: number;
  cpu_usage_pct: number;
  memory_usage_pct: number;
  high_restart_count: number;
}

export interface PipelineStats {
  total: number;
  success: number;
  failed: number;
  running: number;
  success_rate: number;
  avg_duration_seconds: number;
}

// ── Log streaming ─────────────────────────────────────────────────────────────
export interface LogLine {
  timestamp?: string;
  text: string;
}
