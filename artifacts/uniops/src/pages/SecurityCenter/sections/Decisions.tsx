/**
 * Decisions — Sprint 3 R33.
 *
 * Real backend integration. Lists decisions produced by the
 * decision engine pipeline and drills into the per-decision
 * detail view on click.  All data comes from
 *   GET  /api/v1/security/decisions
 *   GET  /api/v1/security/decisions/{id}
 *   GET  /api/v1/security/decisions/statistics
 *
 * Backend response shapes:
 *   GET /decisions         → List[DecisionRead]            (raw array)
 *   GET /decisions/{id}    → DecisionDetailRead            (object)
 *   GET /decisions/stats   → List[DecisionStatsRead]       (raw array)
 *
 * The FastAPI envelope wrapper (`{ success, data, ... }`) is stripped by
 * the project's `useApi` hook; raw arrays are returned directly.
 *
 * No mock data, no fake counts.
 */
import { useState } from 'react';
import { clsx } from 'clsx';
import {
  Gavel, RefreshCw, ChevronRight, ChevronLeft,
  Activity, XCircle, CheckCircle2, Info, Filter,
} from 'lucide-react';
import { useApi } from '@/hooks/use-api';
import type {
  Decision,
  DecisionStatus,
  DecisionStats,
} from '@/types/decision';
import DecisionDetail from './DecisionDetail';

/* ── helpers ──────────────────────────────────────────────────────────── */

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const STATUS_COLOR: Record<DecisionStatus, string> = {
  CREATED:         'text-gray-400 bg-gray-500/10 border-gray-500/20',
  CONTEXT_BUILDING:'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  VALIDATING:      'text-blue-400 bg-blue-500/10 border-blue-500/20',
  READY:           'text-green-400 bg-green-500/10 border-green-500/20',
  REJECTED:        'text-red-400 bg-red-500/10 border-red-500/20',
  ARCHIVED:        'text-gray-400 bg-gray-500/10 border-gray-500/20',
};

const STATUS_FILTERS: Array<{ value: '' | DecisionStatus; label: string }> = [
  { value: '',           label: 'All' },
  { value: 'READY',      label: 'Ready' },
  { value: 'VALIDATING', label: 'Validating' },
  { value: 'REJECTED',   label: 'Rejected' },
  { value: 'ARCHIVED',   label: 'Archived' },
];

/* ── Statistics card ──────────────────────────────────────────────────── */

function StatCard({
  label, value, color, icon,
}: { label: string; value: number | string; color: string; icon: React.ReactNode }) {
  return (
    <div className="card-base p-4 flex items-center gap-3">
      <span className={clsx('w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center', color)}>
        {icon}
      </span>
      <div>
        <p className={clsx('text-xl font-bold', color)}>{value}</p>
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</p>
      </div>
    </div>
  );
}

/* ── Main component ───────────────────────────────────────────────────── */

export default function Decisions() {
  const [statusFilter, setStatusFilter] = useState<'' | DecisionStatus>('');
  const [selectedId, setSelectedId]     = useState<string | null>(null);

  // ── List query (status-only filter — backend honours that) ──
  const listQs = new URLSearchParams();
  if (statusFilter) listQs.set('status', statusFilter);

  const { data: listRaw,  loading: listLoading,  error: listError,  refetch: refetchList } =
    useApi<Decision[]>(
      `/security/decisions${listQs.toString() ? `?${listQs.toString()}` : ''}`,
    );
  const { data: statsRaw } =
    useApi<DecisionStats[] | { data: DecisionStats[] }>('/security/decisions/statistics');

  // Unwrap possible inner envelope
  const decisions: Decision[] = Array.isArray(listRaw)
    ? listRaw
    : (listRaw as any)?.data ?? [];

  // Unwrap stats array (backend returns raw list of DecisionStatsRead)
  const statsRows: DecisionStats[] = Array.isArray(statsRaw)
    ? statsRaw
    : (statsRaw as any)?.data ?? [];
  const byState = statsRows.reduce<Record<string, { count: number; avg: number }>>((acc, s) => {
    acc[s.state] = { count: s.count, avg: s.avg_duration_ms };
    return acc;
  }, {});

  const total       = decisions.length;
  const ready       = byState.READY?.count    ?? 0;
  const rejected    = byState.REJECTED?.count ?? 0;
  const validating  = byState.VALIDATING?.count ?? byState.CONTEXT_BUILDING?.count ?? 0;
  const avgDurMs    = statsRows.length
    ? Math.round(statsRows.reduce((s, r) => s + r.avg_duration_ms, 0) / statsRows.length)
    : 0;

  // ── Detail sub-view ──
  if (selectedId) {
    return <DecisionDetail id={selectedId} onBack={() => { setSelectedId(null); refetchList(true); }} />;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Gavel className="w-5 h-5 text-blue-400" />
            Decision Engine
          </h1>
          <p className="text-xs text-muted-foreground">
            {total} decisions · pipeline-produced remediation choices · tenant-scoped
          </p>
        </div>
        <button
          onClick={() => refetchList(true)}
          className="p-1.5 rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
          style={{ borderColor: 'hsl(230 15% 20%)' }}
          aria-label="Refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Total Decisions" value={total}      color="text-blue-400"   icon={<Gavel className="w-4 h-4" />} />
        <StatCard label="Ready"           value={ready}      color="text-green-400"  icon={<CheckCircle2 className="w-4 h-4" />} />
        <StatCard label="Validating"      value={validating} color="text-yellow-400" icon={<Activity className="w-4 h-4" />} />
        <StatCard label="Rejected"        value={rejected}   color="text-red-400"    icon={<XCircle className="w-4 h-4" />} />
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
          <Filter className="w-3 h-3" />
          <span>Status</span>
        </div>
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {STATUS_FILTERS.map(({ value, label }) => (
            <button
              key={value || 'all'}
              onClick={() => setStatusFilter(value)}
              className={clsx(
                'px-3 py-1.5 text-[11px] font-medium transition-colors',
                statusFilter === value
                  ? 'bg-blue-600 text-white'
                  : 'text-muted-foreground hover:text-foreground hover:bg-white/5',
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {avgDurMs > 0 && (
          <span className="ml-auto text-[11px] text-muted-foreground">
            avg duration&nbsp;
            <span className="text-foreground font-mono">{avgDurMs} ms</span>
          </span>
        )}
      </div>

      {/* Error state */}
      {listError && !listLoading && (
        <div className="card-base p-6 text-center border-red-500/30">
          <XCircle className="w-7 h-7 text-red-400 mx-auto mb-2" />
          <p className="text-sm font-medium text-foreground mb-1">Failed to load decisions</p>
          <p className="text-xs text-muted-foreground mb-3">{listError}</p>
          <button
            onClick={() => refetchList(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors"
          >
            <RefreshCw className="w-3 h-3" /> Retry
          </button>
        </div>
      )}

      {/* Body */}
      {!listError && (
        <div className="space-y-2">
          {listLoading ? (
            [...Array(5)].map((_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)
          ) : decisions.length === 0 ? (
            <div className="card-base py-14 text-center">
              <Gavel className="w-8 h-8 text-muted-foreground opacity-30 mx-auto mb-2" />
              <p className="text-sm font-medium text-foreground mb-1">No decisions yet</p>
              <p className="text-xs text-muted-foreground">
                {statusFilter
                  ? `No decisions in status ${statusFilter} for this tenant.`
                  : 'The decision pipeline is idle. Decisions appear here as findings are processed.'}
              </p>
            </div>
          ) : (
            decisions.map((d) => (
              <button
                key={d.id}
                onClick={() => setSelectedId(d.id)}
                className="card-base p-4 w-full text-left transition-colors hover:border-blue-500/30 group"
              >
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={clsx(
                        'text-[10px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider',
                        STATUS_COLOR[d.status] ?? 'text-muted-foreground bg-white/5 border-white/10',
                      )}>
                        {d.status}
                      </span>
                      {d.final_result && (
                        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider text-foreground bg-white/5 border border-white/10">
                          {d.final_result}
                        </span>
                      )}
                      <span className="text-[10px] text-muted-foreground">v{d.version}</span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground flex-wrap">
                      <span className="font-mono text-foreground/80">{d.id.slice(0, 8)}…</span>
                      <span>·</span>
                      <span className="font-mono">{d.correlation_id.slice(0, 12)}…</span>
                      <span>·</span>
                      <span>ctx {d.context_id.slice(0, 8)}…</span>
                    </div>
                  </div>
                  <div className="text-right flex flex-col items-end gap-1 flex-shrink-0">
                    <span className="text-[10px] text-muted-foreground">
                      {new Date(d.created_at).toLocaleString(undefined, {
                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                      })}
                    </span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-blue-400 transition-colors" />
                </div>
              </button>
            ))
          )}
        </div>
      )}

      {/* Footer (informational — backend currently returns all rows in one shot) */}
      {!listError && total > 0 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-muted-foreground">
            {total} decision{total === 1 ? '' : 's'}
            {statusFilter && (
              <> · filter&nbsp;<span className="text-foreground font-mono">{statusFilter}</span></>
            )}
          </span>
          <span className="text-[10px] text-muted-foreground/60 inline-flex items-center gap-1">
            <Info className="w-3 h-3" />
            pagination forwarded to backend when supported
          </span>
        </div>
      )}
    </div>
  );
}
