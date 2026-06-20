// ─────────────────────────────────────────────────────────────────────────────
// DevOpsCenter — shared types
// ─────────────────────────────────────────────────────────────────────────────

export type DevOpsSection =
  | 'control-plane'
  | 'observability'
  | 'delivery'
  | 'catalog';

export type DevOpsTab =
  | 'clusters'
  | 'observability'
  | 'alerts'
  | 'gitops'
  | 'kubernetes'
  | 'workloads'
  | 'network'
  | 'jobs'
  | 'config'
  | 'hpa'
  | 'pipelines'
  | 'history';

// ── Cluster ───────────────────────────────────────────────────────────────────
export type ClusterProvider = 'eks' | 'aks' | 'gke' | 'oke' | 'on-prem';
export type ClusterStatus   = 'connected' | 'disconnected' | 'error' | 'pending';
export type ClusterEnv      = 'production' | 'staging' | 'dev' | 'sandbox';

export interface Cluster {
  id:               string;
  name:             string;
  provider:         ClusterProvider;
  region:           string;
  environment:      ClusterEnv;
  api_server_url?:  string;
  status:           ClusterStatus;
  k8s_version?:     string;
  node_count:       number;
  pod_count:        number;
  cpu_usage_pct:    number;
  memory_usage_pct: number;
  last_health_check?: string;
  error_message?:   string;
  created_at:       string;
}

export interface ClusterNode {
  name:               string;
  status:             'Ready' | 'NotReady' | 'Unknown';
  roles:              string[];
  cpu_capacity?:      string;
  memory_capacity?:   string;
  cpu_allocatable?:   string;
  memory_allocatable?: string;
  os_image?:          string;
  kubelet_version?:   string;
  conditions:         { type: string; status: string }[];
  age?:               string;
}

export interface ClusterNamespace {
  name:   string;
  status: string;
  age?:   string;
  labels: Record<string, string>;
}

export interface ClusterDeployment {
  name:               string;
  namespace:          string;
  replicas:           number;
  ready_replicas:     number;
  available_replicas: number;
  image?:             string;
  age?:               string;
  status:             'Healthy' | 'Degraded' | 'Progressing';
}

export interface ClusterService {
  name:         string;
  namespace:    string;
  type:         string;
  cluster_ip?:  string;
  external_ip?: string;
  ports:        string[];
  age?:         string;
}

export interface ClusterIngress {
  name:      string;
  namespace: string;
  class_?:   string;
  hosts:     string[];
  paths:     string[];
  tls:       boolean;
  age?:      string;
}

export interface ClusterCreatePayload {
  name:           string;
  provider:       ClusterProvider;
  region:         string;
  environment:    ClusterEnv;
  api_server_url?: string;
  kubeconfig?:    string;
}

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

// ── Service Catalog (Epic 6) ──────────────────────────────────────────────────
export type ServiceType   = 'Microservice' | 'Database' | 'Worker' | 'Queue' | 'Gateway';
export type ServiceStatus = 'Running' | 'Failed' | 'Deploying' | 'Pending' | 'Stopped';
export type TechStack     =
  | 'Node.js' | 'Python' | 'Go' | 'Java' | 'Rust'
  | 'React' | 'Next.js' | 'FastAPI' | 'Django' | 'Spring Boot' | 'Other';

export interface CatalogService {
  id:               string;
  name:             string;
  type:             ServiceType;
  status:           ServiceStatus;
  tech_stack:       TechStack;
  cluster:          string;
  namespace:        string;
  git_repo?:        string;
  last_deployment?: string;
  replicas:         number;
  created_at:       string;
  owner?:           string;
  description?:     string;
  tags:             string[];
}

export interface CreateServicePayload {
  name:         string;
  type:         ServiceType;
  tech_stack:   TechStack;
  git_repo:     string;
  cluster:      string;
  namespace:    string;
  replicas:     number;
  description?: string;
  tags:         string[];
}
