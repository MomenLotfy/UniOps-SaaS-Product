/**
 * Decision Engine types — mirrors backend/app/modules/security/decision_engine/api/schemas.py.
 *
 * Sprint 3 R33: types are kept in lock-step with the Pydantic schemas produced
 * by the backend.  No `any`, no inline interfaces in components.
 *
 * Backend shape (verbatim from schemas.py):
 *   DecisionRead        : tenant_id, created_at, updated_at, version,
 *                         correlation_id, trace_id, metadata, id, status,
 *                         final_result, context_id
 *   DecisionDetailRead  : + plan_steps: List[dict], reasons: List[dict],
 *                          context_summary: dict, policy_ref: Optional[dict]
 *   DecisionHistoryRead : + decision_id, from_state, to_state,
 *                          changed_by, change_reason
 *   DecisionStatsRead   : state, count, avg_duration_ms
 */

// ── enums ─────────────────────────────────────────────────────────────────

/**
 * Mirrors `app/modules/security/decision_engine/constants.py:DecisionState`.
 * Decision state machine values emitted by the engine pipeline.
 */
export type DecisionStatus =
  | 'CREATED'
  | 'CONTEXT_BUILDING'
  | 'VALIDATING'
  | 'READY'
  | 'REJECTED'
  | 'ARCHIVED';

/**
 * Mirrors the `final_result` enum produced by the strategy engine.
 * `null` until the decision is finalized.
 */
export type DecisionResult =
  | 'MITIGATE'
  | 'ACCEPT'
  | 'TRANSFER'
  | 'AVOID'
  | 'NO_ACTION';

// ── schemas ───────────────────────────────────────────────────────────────

/** DecisionRead — list-item payload. */
export interface Decision {
  id: string;
  tenant_id: string;
  created_at: string;
  updated_at: string;
  version: number;
  correlation_id: string;
  trace_id: string | null;
  metadata: Record<string, unknown>;
  status: DecisionStatus;
  final_result: DecisionResult | null;
  context_id: string;
}

/**
 * DecisionDetailRead — full detail.  Backend returns:
 *   plan_steps: List[{type, result}]
 *   reasons:    List[{code, desc}]
 *   context_summary: dict
 *   policy_ref: { id, version } | null
 */
export interface DecisionPlanStep {
  type: string;
  result?: unknown;
  step_number?: number;
  description?: string;
  estimated_duration_minutes?: number;
}

export interface DecisionReason {
  code: string;
  desc?: string;
  reason_code?: string;
  description?: string;
  category?: string;
  weight?: number;
}

export interface DecisionPolicyRef {
  id: string;
  version: string;
}

export interface DecisionDetailResponse extends Decision {
  plan_steps: DecisionPlanStep[];
  reasons: DecisionReason[];
  context_summary: Record<string, unknown>;
  policy_ref: DecisionPolicyRef | null;
  history: Array<{
    id: string;
    from_state: DecisionStatus | null;
    to_state: DecisionStatus;
    changed_by: string;
    change_reason: string | null;
    created_at: string;
  }>;
}

// ── list params / response ────────────────────────────────────────────────

/**
 * Query parameters accepted by `GET /api/v1/security/decisions`.
 * Backend currently honours `status` (filter).  Pagination / sort params
 * are forward-compatible — the API silently ignores unknown keys.
 */
export interface DecisionListParams {
  status?: DecisionStatus;
  page?: number;
  page_size?: number;
  sort_by?: 'created_at' | 'status' | 'final_result';
  sort_dir?: 'asc' | 'desc';
}

/**
 * Response envelope: FastAPI's `APIResponse` wraps the list in
 * `{ success, data, message, code }`.  When the backend uses
 * `PaginatedResponse` it double-wraps as `{ data: [...], total, ... }`.
 * Both shapes are accepted; the API client unwraps as needed.
 */
export interface DecisionListResponse {
  items?: Decision[];
  data?: Decision[];
  total?: number;
  page?: number;
  page_size?: number;
}

// ── stats ─────────────────────────────────────────────────────────────────

/** DecisionStatsRead — one row per state. */
export interface DecisionStats {
  state: DecisionStatus;
  count: number;
  avg_duration_ms: number;
}
