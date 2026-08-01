export interface Repo {
  id: string;
  full_name: string;
  name: string;
  provider: string;
  default_branch: string;
  is_private: boolean;
  language: string | null;
  has_dockerfile: boolean;
  has_cicd: boolean;
  last_scan_at: string | null;
  last_scan_score: number | null;
  clone_url?: string | null;
  integration_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface RepoRisk {
  repo_id: string;
  risk_level: 'critical' | 'high' | 'medium' | 'low';
  risk_score: number;
  trend: 'worsening' | 'stable' | 'improving';
  previous_risk_level?: string | null;
  previous_risk_score?: number | null;
  critical_count: number;
  high_count: number;
  secret_count: number;
  container_count: number;
  compliance_violations: number;
  open_findings: number;
  exposure_risk: number;
  security_score: number | null;
  owner: string | null;
  factors: Record<string, unknown>;
  last_scan_at?: string | null;
}

export interface MergedRepo extends Repo {
  risk?: RepoRisk;
}

export interface ScanHistoryEntry {
  date: string;
  score: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  secrets: number;
  repo?: string;
  repo_id?: string;
  scan_id?: string;
  status?: 'queued' | 'cloning' | 'scanning' | 'analyzing' | 'completed' | 'failed';
  error_message?: string | null;
  duration_secs?: number | null;
  branch?: string | null;
  commit_sha?: string | null;
}

export interface RepoScore {
  score: number;
  breakdown?: {
    sast?: number;
    deps?: number;
    secrets?: number;
    container?: number;
    cicd?: number;
  };
  ai_summary?: string | null;
  ai_suggestions?: string[];
  repo?: string;
  repo_id?: string;
  scan_id?: string;
  scanned_at?: string;
}

export type RiskLevel = 'critical' | 'high' | 'medium' | 'low';

export const RISK_STYLES: Record<RiskLevel, { bg: string; text: string; border: string; dot: string; bar: string }> = {
  critical: { bg: 'bg-red-500/15',    text: 'text-red-400',    border: 'border-red-500/30',    dot: 'bg-red-400',    bar: 'bg-red-500' },
  high:     { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', dot: 'bg-orange-400', bar: 'bg-orange-500' },
  medium:   { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30', dot: 'bg-yellow-400', bar: 'bg-yellow-500' },
  low:      { bg: 'bg-green-500/15',  text: 'text-green-400',  border: 'border-green-500/30',  dot: 'bg-green-400',  bar: 'bg-green-500' },
};

export const RISK_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
