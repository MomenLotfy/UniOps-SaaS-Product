import apiClient from './client';
import type {
  Decision,
  DecisionDetailResponse,
  DecisionListParams,
  DecisionStats,
} from '@/types/decision';

// ── Types ──────────────────────────────────────────────────────────────────

export interface SecurityPolicy {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  category: string;
  severity: string;
  status: string;
  enforcement: string;
  scope: Record<string, unknown>;
  rules: unknown[];
  exceptions_count: number;
  violations_count: number;
  created_by: string | null;
  updated_by: string | null;
  effective_date: string | null;
  review_date: string | null;
  frameworks: string[];
  tags: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface SecurityException {
  id: string;
  tenant_id: string;
  policy_id: string | null;
  finding_id: string | null;
  finding_type: string | null;
  title: string;
  justification: string;
  risk_acceptance: string;
  status: string;
  exception_type: string;
  requested_by: string;
  approved_by: string | null;
  rejected_by: string | null;
  reviewer_note: string | null;
  expires_at: string | null;
  reviewed_at: string | null;
  scope: Record<string, unknown>;
  tags: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface SecurityReport {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  report_type: string;
  status: string;
  format: string;
  generated_by: string;
  parameters: Record<string, unknown>;
  summary: Record<string, unknown>;
  findings: Record<string, unknown>;
  period_start: string | null;
  period_end: string | null;
  completed_at: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface SecurityPostureSummary {
  current_score: number;
  trend: string;
  threat_score: number;
  vulnerability_score: number;
  compliance_score: number;
  asset_score: number;
  policy_score: number;
  breakdown: {
    threats: { open: number; critical: number; total: number };
    vulnerabilities: { open: number; critical: number; total: number };
    assets: { total: number; critical_risk: number };
    policies: { total: number; active: number };
  };
  history: Array<{ date: string; overall: number; threat: number; vulnerability: number; compliance: number }>;
  open_threats: number;
  open_vulns: number;
  critical_assets: number;
  active_policies: number;
  pending_exceptions: number;
}

export interface PolicyStats {
  total: number;
  active: number;
  inactive: number;
  draft: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  by_enforcement: Record<string, number>;
}

export interface ExceptionStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  expired: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
}

// ── Policies ──────────────────────────────────────────────────────────────

export const policiesApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get('/security-policies', { params }).then(r => r.data),

  create: (data: Partial<SecurityPolicy>) =>
    apiClient.post('/security-policies', data).then(r => r.data),

  get: (id: string) =>
    apiClient.get(`/security-policies/${id}`).then(r => r.data),

  update: (id: string, data: Partial<SecurityPolicy>) =>
    apiClient.patch(`/security-policies/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    apiClient.delete(`/security-policies/${id}`).then(r => r.data),

  stats: () =>
    apiClient.get('/security-policies/stats').then(r => r.data),
};

// ── Exceptions ────────────────────────────────────────────────────────────

export const exceptionsApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get('/security-exceptions', { params }).then(r => r.data),

  create: (data: Partial<SecurityException>) =>
    apiClient.post('/security-exceptions', data).then(r => r.data),

  get: (id: string) =>
    apiClient.get(`/security-exceptions/${id}`).then(r => r.data),

  update: (id: string, data: Partial<SecurityException>) =>
    apiClient.patch(`/security-exceptions/${id}`, data).then(r => r.data),

  review: (id: string, action: 'approve' | 'reject', reviewer_note?: string) =>
    apiClient.post(`/security-exceptions/${id}/review`, { action, reviewer_note }).then(r => r.data),

  stats: () =>
    apiClient.get('/security-exceptions/stats').then(r => r.data),
};

// ── Reports ───────────────────────────────────────────────────────────────

export const reportsApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get('/security-reports', { params }).then(r => r.data),

  generate: (data: {
    name: string;
    report_type: string;
    description?: string;
    format?: string;
    parameters?: Record<string, unknown>;
    period_start?: string;
    period_end?: string;
  }) =>
    apiClient.post('/security-reports', data).then(r => r.data),

  get: (id: string) =>
    apiClient.get(`/security-reports/${id}`).then(r => r.data),

  delete: (id: string) =>
    apiClient.delete(`/security-reports/${id}`).then(r => r.data),
};

// ── Posture ───────────────────────────────────────────────────────────────

export const postureApi = {
  summary: () =>
    apiClient.get('/security-posture/summary').then(r => r.data),

  history: (days = 30) =>
    apiClient.get('/security-posture/history', { params: { days } }).then(r => r.data),

  snapshot: () =>
    apiClient.post('/security-posture/snapshot').then(r => r.data),
};

// ── Decisions (Sprint 3 R33) ───────────────────────────────────────────────

export const decisionsApi = {
  /**
   * List decisions for the current tenant.
   * Backed by `GET /api/v1/security/decisions`.
   * Backend returns `List[DecisionRead]` (raw array; possibly wrapped in the
   * FastAPI `{success, data, ...}` envelope — `client.ts` does not unwrap
   * arrays, so callers receive either an array or `{data: [...]}`).
   */
  list: (params: DecisionListParams = {}) =>
    apiClient.get<Decision[] | { data: Decision[] }>('/security/decisions', { params })
      .then(r => r.data),

  /**
   * Full decision detail.
   * Backed by `GET /api/v1/security/decisions/{id}`.
   */
  getDetail: (id: string) =>
    apiClient
      .get<DecisionDetailResponse>(`/security/decisions/${id}`)
      .then(r => r.data),

  /**
   * Tenant-wide aggregate metrics (one row per state).
   * Backed by `GET /api/v1/security/decisions/statistics`.
   */
  statistics: () =>
    apiClient
      .get<DecisionStats[] | { data: DecisionStats[] }>('/security/decisions/statistics')
      .then(r => r.data),
};
