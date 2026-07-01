import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Wrench, Play, RotateCcw, XCircle, ChevronRight, ChevronLeft,
  CheckCircle2, Clock, Loader2, Search,
  RefreshCw, Shield, Cpu,
  ArrowRight, SkipForward, Layers, Hash, Zap,
  ExternalLink, User, Calendar,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface RemediationPlan {
  id: string;
  finding_id: string;
  finding_type: string;
  target_technology: string;
  capability_id: string;
  strategy_id: string;
  priority: string;
  status: string;
  version: number;
  created_by: string | null;
  change_reason: string | null;
  required_inputs: Record<string, unknown>;
  expected_outputs: unknown[];
  execution_context: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

interface Summary {
  total: number;
  open: number;
  critical: number;
  high: number;
  medium: number;
  executing: number;
  completed: number;
  failed: number;
  rolled_back: number;
  ready_for_execution: number;
  waiting_for_validation: number;
  planning: number;
  cancelled: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
}

interface TimelineEntry {
  from: string;
  to: string;
  timestamp: string;
  reason: string | null;
  by: string | null;
}

interface HistoryEntry {
  execution_id: string;
  start_time: string;
  end_time: string | null;
  latency: number | null;
  status: string;
  error_message: string | null;
  planner_version: string | null;
  engine_version: string | null;
  model_used: string | null;
  token_usage: number | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const PIPELINE_STAGES = [
  { key: 'CREATED',                 label: 'Created',    icon: Hash },
  { key: 'PLANNING',                label: 'Analysis',   icon: Search },
  { key: 'WAITING_FOR_CAPABILITY',  label: 'Fix Gen',    icon: Zap },
  { key: 'CAPABILITY_SELECTED',     label: 'Capability', icon: Layers },
  { key: 'WAITING_FOR_VALIDATION',  label: 'Validation', icon: Shield },
  { key: 'READY_FOR_EXECUTION',     label: 'Approval',   icon: CheckCircle2 },
  { key: 'EXECUTING',               label: 'Deploy',     icon: Play },
  { key: 'COMPLETED',               label: 'Verified',   icon: CheckCircle2 },
];

const STATUS_META: Record<string, { label: string; color: string; bg: string; border: string }> = {
  CREATED:                { label: 'Created',       color: 'text-slate-400',  bg: 'bg-slate-500/10', border: 'border-slate-500/20' },
  PLANNING:               { label: 'Planning',      color: 'text-blue-400',   bg: 'bg-blue-500/10',  border: 'border-blue-500/20' },
  WAITING_FOR_CAPABILITY: { label: 'Pending Cap.',  color: 'text-purple-400', bg: 'bg-purple-500/10',border: 'border-purple-500/20' },
  CAPABILITY_SELECTED:    { label: 'Cap. Selected', color: 'text-indigo-400', bg: 'bg-indigo-500/10',border: 'border-indigo-500/20' },
  WAITING_FOR_VALIDATION: { label: 'Validating',   color: 'text-yellow-400', bg: 'bg-yellow-500/10',border: 'border-yellow-500/20' },
  READY_FOR_EXECUTION:    { label: 'Ready',         color: 'text-cyan-400',   bg: 'bg-cyan-500/10',  border: 'border-cyan-500/20' },
  EXECUTING:              { label: 'Executing',     color: 'text-blue-300',   bg: 'bg-blue-500/15',  border: 'border-blue-400/30' },
  COMPLETED:              { label: 'Completed',     color: 'text-green-400',  bg: 'bg-green-500/10', border: 'border-green-500/20' },
  FAILED:                 { label: 'Failed',        color: 'text-red-400',    bg: 'bg-red-500/10',   border: 'border-red-500/20' },
  CANCELLED:              { label: 'Cancelled',     color: 'text-gray-400',   bg: 'bg-gray-500/10',  border: 'border-gray-500/20' },
  ROLLED_BACK:            { label: 'Rolled Back',   color: 'text-orange-400', bg: 'bg-orange-500/10',border: 'border-orange-500/20' },
};

const PRIORITY_META: Record<string, { color: string; dot: string }> = {
  critical: { color: 'text-red-400',    dot: 'bg-red-500' },
  high:     { color: 'text-orange-400', dot: 'bg-orange-500' },
  medium:   { color: 'text-yellow-400', dot: 'bg-yellow-500' },
  low:      { color: 'text-blue-400',   dot: 'bg-blue-500' },
};

const TERMINAL = new Set(['COMPLETED', 'CANCELLED', 'ROLLED_BACK']);
const ACTIVE   = new Set(['EXECUTING', 'PLANNING', 'WAITING_FOR_CAPABILITY', 'WAITING_FOR_VALIDATION', 'READY_FOR_EXECUTION', 'CAPABILITY_SELECTED']);

function fmt(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
}
function dur(start: string | null, end: string | null) {
  if (!start) return '—';
  const ms = (end ? new Date(end) : new Date()).getTime() - new Date(start).getTime();
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
  return `${(ms / 3_600_000).toFixed(1)}h`;
}

// ─── Shared UI primitives ─────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const m = STATUS_META[status] ?? { label: status, color: 'text-muted-foreground', bg: 'bg-white/5', border: 'border-white/10' };
  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border whitespace-nowrap', m.bg, m.color, m.border)}>
      {ACTIVE.has(status) && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />}
      {m.label}
    </span>
  );
}

function PriorityDot({ priority }: { priority: string }) {
  const m = PRIORITY_META[priority] ?? { color: 'text-muted-foreground', dot: 'bg-gray-500' };
  return (
    <span className={clsx('inline-flex items-center gap-1.5 text-xs font-medium capitalize', m.color)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', m.dot)} />
      {priority}
    </span>
  );
}

function KpiCard({ label, value, color = 'text-foreground', sub }: {
  label: string; value: number | string; color?: string; sub?: string;
}) {
  return (
    <div className="card-base flex flex-col gap-1 min-w-0">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold truncate">{label}</span>
      <span className={clsx('text-2xl font-bold tabular-nums', color)}>{value ?? '—'}</span>
      {sub && <span className="text-[10px] text-muted-foreground">{sub}</span>}
    </div>
  );
}

// ─── Pipeline Bar ─────────────────────────────────────────────────────────────

function PipelineBar({ summary }: { summary: Summary | null }) {
  const counts = summary?.by_status ?? {};
  return (
    <div className="card-base">
      <div className="text-[10px] font-semibold text-muted-foreground mb-3 uppercase tracking-wider">Remediation Pipeline</div>
      <div className="flex items-stretch gap-0 overflow-x-auto pb-1">
        {PIPELINE_STAGES.map((stage, i) => {
          const cnt = counts[stage.key] ?? 0;
          const Icon = stage.icon;
          return (
            <div key={stage.key} className="flex items-center min-w-0">
              <div className={clsx(
                'flex flex-col items-center gap-1 px-3 py-2 rounded-lg min-w-[68px] transition-all',
                cnt > 0 ? 'bg-blue-500/10 border border-blue-500/20' : 'opacity-35',
              )}>
                <Icon className={clsx('w-3.5 h-3.5', cnt > 0 ? 'text-blue-400' : 'text-muted-foreground')} />
                <span className={clsx('text-sm font-bold tabular-nums', cnt > 0 ? 'text-blue-300' : 'text-muted-foreground')}>{cnt}</span>
                <span className="text-[9px] text-muted-foreground text-center leading-tight whitespace-nowrap">{stage.label}</span>
              </div>
              {i < PIPELINE_STAGES.length - 1 && (
                <ArrowRight className={clsx('w-3 h-3 mx-0.5 flex-shrink-0', cnt > 0 ? 'text-blue-500/40' : 'text-white/8')} />
              )}
            </div>
          );
        })}
        {/* Terminal states */}
        <div className="flex items-center ml-3 gap-2 border-l border-white/10 pl-3">
          {[
            { key: 'FAILED',       label: 'Failed',      clr: 'text-red-400',    bg: 'bg-red-500/10 border border-red-500/20' },
            { key: 'ROLLED_BACK',  label: 'Rolled Back', clr: 'text-orange-400', bg: 'bg-orange-500/10 border border-orange-500/20' },
            { key: 'CANCELLED',    label: 'Cancelled',   clr: 'text-gray-400',   bg: 'bg-gray-500/10 border border-gray-500/20' },
          ].map(s => {
            const cnt = counts[s.key] ?? 0;
            return (
              <div key={s.key} className={clsx('flex flex-col items-center gap-1 px-3 py-2 rounded-lg min-w-[68px]', cnt > 0 ? s.bg : 'opacity-30')}>
                <span className={clsx('text-sm font-bold tabular-nums', cnt > 0 ? s.clr : 'text-muted-foreground')}>{cnt}</span>
                <span className="text-[9px] text-muted-foreground whitespace-nowrap">{s.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Propose Modal ────────────────────────────────────────────────────────────

function ProposeModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState({ finding_id: '', repo_id: '', scan_id: '', metadata: '' });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.finding_id.trim()) { setErr('Finding ID is required'); return; }
    setLoading(true); setErr(null);
    try {
      let meta: Record<string, unknown> = {};
      if (form.metadata.trim()) {
        try { meta = JSON.parse(form.metadata); } catch { setErr('Metadata must be valid JSON'); setLoading(false); return; }
      }
      await apiPost('/remediation/propose', {
        finding_id: form.finding_id.trim(),
        ...(form.repo_id.trim() && { repo_id: form.repo_id.trim() }),
        ...(form.scan_id.trim() && { scan_id: form.scan_id.trim() }),
        metadata: meta,
      });
      onSuccess();
    } catch (e: any) { setErr(e?.message ?? 'Proposal failed — check finding_id is valid'); }
    finally { setLoading(false); }
  };

  const inp = 'w-full px-3 py-2 rounded-lg text-xs border outline-none focus:ring-2 focus:ring-blue-500/40 text-foreground font-mono';
  const sty = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
        className="card-base w-full max-w-md mx-4 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-400" /> Propose Remediation Plan
          </h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1 block">
              Finding ID <span className="text-red-400 normal-case">*</span>
            </label>
            <input value={form.finding_id} onChange={e => setForm(f => ({ ...f, finding_id: e.target.value }))}
              placeholder="vuln-uuid / threat-uuid / CVE-2024-…" className={inp} style={sty} required autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1 block">Repository ID</label>
              <input value={form.repo_id} onChange={e => setForm(f => ({ ...f, repo_id: e.target.value }))}
                placeholder="repo-uuid" className={inp} style={sty} />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1 block">Scan ID</label>
              <input value={form.scan_id} onChange={e => setForm(f => ({ ...f, scan_id: e.target.value }))}
                placeholder="scan-uuid" className={inp} style={sty} />
            </div>
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1 block">Metadata JSON</label>
            <textarea value={form.metadata} onChange={e => setForm(f => ({ ...f, metadata: e.target.value }))}
              placeholder='{"finding_type": "dependency_vulnerability"}' rows={3}
              className={clsx(inp, 'resize-none')} style={sty} />
          </div>
          {err && (
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-300">
              <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              {err}
            </div>
          )}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="action-btn flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="action-btn-primary flex-1">
              {loading ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Proposing…</> : <><Zap className="w-3.5 h-3.5" /> Propose Plan</>}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

// ─── Inline Action Button ─────────────────────────────────────────────────────

function ActionBtn({ icon, title, colorClass, planId, action, onDone }: {
  icon: React.ReactNode; title: string; colorClass: string;
  planId: string; action: string; onDone: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const run = async () => {
    setLoading(true);
    try {
      if (action === 'execute')  await apiPost(`/remediation/execute/${planId}`, {});
      if (action === 'start')    await apiPost(`/remediation/execute/${planId}/start`, {});
      if (action === 'cancel')   await apiPost(`/remediation/execute/${planId}/cancel`, {});
      if (action === 'rollback') await apiPost(`/remediation/execute/${planId}/rollback`, {});
      onDone();
    } catch { /* errors shown in detail drawer */ }
    finally { setLoading(false); }
  };
  return (
    <button onClick={run} disabled={loading} title={title}
      className={clsx('p-1.5 rounded-md text-muted-foreground transition-all disabled:opacity-50', colorClass)}>
      {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : icon}
    </button>
  );
}

// ─── Detail Drawer ────────────────────────────────────────────────────────────

function DetailDrawer({ plan, onClose, onAction }: {
  plan: RemediationPlan; onClose: () => void; onAction: () => void;
}) {
  const [tab, setTab] = useState<'overview' | 'timeline' | 'history' | 'context'>('overview');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);

  const { data: tlRaw,   loading: tlLoading   } = useApi<TimelineEntry[]>(`/remediation/timeline/${plan.id}`);
  const { data: histRaw, loading: histLoading } = useApi<HistoryEntry[]>(`/remediation/history/${plan.id}`);

  const timeline: TimelineEntry[] = Array.isArray(tlRaw)   ? tlRaw   : [];
  const history:  HistoryEntry[]  = Array.isArray(histRaw) ? histRaw : [];

  const canExecute  = plan.status === 'READY_FOR_EXECUTION';
  const canStart    = plan.status === 'CREATED' || plan.status === 'PLANNING';
  const canCancel   = ACTIVE.has(plan.status);
  const canRollback = plan.status === 'FAILED';

  const doAction = async (action: string) => {
    setActionLoading(action); setActionErr(null);
    try {
      if (action === 'execute')  await apiPost(`/remediation/execute/${plan.id}`, {});
      if (action === 'start')    await apiPost(`/remediation/execute/${plan.id}/start`, {});
      if (action === 'cancel')   await apiPost(`/remediation/execute/${plan.id}/cancel`, {});
      if (action === 'rollback') await apiPost(`/remediation/execute/${plan.id}/rollback`, {});
      onAction();
    } catch (e: any) { setActionErr(e?.message ?? 'Action failed'); }
    finally { setActionLoading(null); }
  };

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'timeline', label: `Timeline (${timeline.length})` },
    { key: 'history',  label: `History (${history.length})` },
    { key: 'context',  label: 'Context' },
  ] as const;

  return (
    <motion.div
      initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 30, stiffness: 300 }}
      className="fixed right-0 top-0 bottom-0 w-full max-w-lg z-40 flex flex-col border-l shadow-2xl"
      style={{ background: 'hsl(230 18% 6%)', borderColor: 'hsl(230 15% 14%)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b flex-shrink-0"
        style={{ borderColor: 'hsl(230 15% 14%)' }}>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <Wrench className="w-4 h-4 text-blue-400 flex-shrink-0" />
            <span className="text-sm font-bold text-foreground">Remediation Plan</span>
            <StatusBadge status={plan.status} />
          </div>
          <div className="flex items-center gap-3 text-[10px] text-muted-foreground font-mono flex-wrap">
            <span className="truncate">{plan.id}</span>
            <PriorityDot priority={plan.priority} />
          </div>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors ml-3 flex-shrink-0">
          <XCircle className="w-4 h-4" />
        </button>
      </div>

      {/* Action row */}
      <div className="flex items-center gap-2 px-5 py-3 border-b flex-shrink-0 flex-wrap"
        style={{ borderColor: 'hsl(230 15% 14%)' }}>
        {canStart && (
          <button onClick={() => doAction('start')} disabled={!!actionLoading}
            className="action-btn-primary text-xs py-1.5 px-3 gap-1.5">
            {actionLoading === 'start' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            Start
          </button>
        )}
        {canExecute && (
          <button onClick={() => doAction('execute')} disabled={!!actionLoading}
            className="action-btn-primary text-xs py-1.5 px-3 gap-1.5">
            {actionLoading === 'execute' ? <Loader2 className="w-3 h-3 animate-spin" /> : <SkipForward className="w-3 h-3" />}
            Execute
          </button>
        )}
        {canCancel && (
          <button onClick={() => doAction('cancel')} disabled={!!actionLoading}
            className="action-btn text-xs py-1.5 px-3 gap-1.5">
            {actionLoading === 'cancel' ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
            Cancel
          </button>
        )}
        {canRollback && (
          <button onClick={() => doAction('rollback')} disabled={!!actionLoading}
            className="action-btn text-xs py-1.5 px-3 gap-1.5">
            {actionLoading === 'rollback' ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
            Rollback
          </button>
        )}
        {TERMINAL.has(plan.status) && !canRollback && (
          <span className="text-xs text-muted-foreground italic">No actions available — terminal state.</span>
        )}
        {actionErr && (
          <span className="text-xs text-red-400 flex items-center gap-1">
            <XCircle className="w-3 h-3" /> {actionErr}
          </span>
        )}
      </div>

      {/* Tab nav */}
      <div className="flex border-b flex-shrink-0" style={{ borderColor: 'hsl(230 15% 14%)' }}>
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={clsx(
              'px-4 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap',
              tab === t.key
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

        {tab === 'overview' && (
          <>
            {/* Field grid */}
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Finding ID',   value: plan.finding_id,         mono: true  },
                { label: 'Type',         value: plan.finding_type,        mono: false },
                { label: 'Technology',   value: plan.target_technology,   mono: false },
                { label: 'Capability',   value: plan.capability_id,       mono: true  },
                { label: 'Strategy',     value: plan.strategy_id,         mono: true  },
                { label: 'Version',      value: `v${plan.version}`,       mono: true  },
                { label: 'Created By',   value: plan.created_by ?? '—',   mono: false },
                { label: 'Priority',     value: plan.priority,            mono: false },
              ].map(f => (
                <div key={f.label} className="p-3 rounded-lg" style={{ background: 'hsl(230 18% 9%)' }}>
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{f.label}</div>
                  <div className={clsx('text-xs text-foreground break-all capitalize', f.mono && 'font-mono normal-case')}>
                    {f.value ?? '—'}
                  </div>
                </div>
              ))}
            </div>

            {/* Timestamps */}
            <div className="p-3 rounded-lg space-y-2.5" style={{ background: 'hsl(230 18% 9%)' }}>
              {[
                { icon: <Calendar className="w-3 h-3" />, label: 'Created',  value: fmt(plan.created_at) },
                { icon: <RefreshCw className="w-3 h-3" />, label: 'Updated', value: fmt(plan.updated_at) },
                { icon: <Clock className="w-3 h-3" />,     label: 'Age',     value: dur(plan.created_at, null) },
              ].map(row => (
                <div key={row.label} className="flex justify-between text-xs">
                  <span className="text-muted-foreground flex items-center gap-1.5">{row.icon}{row.label}</span>
                  <span className="text-foreground font-mono">{row.value}</span>
                </div>
              ))}
            </div>

            {/* Change reason */}
            {plan.change_reason && (
              <div className="p-3 rounded-lg" style={{ background: 'hsl(230 18% 9%)' }}>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Change Reason</div>
                <p className="text-xs text-foreground">{plan.change_reason}</p>
              </div>
            )}

            {/* Expected outputs */}
            {Array.isArray(plan.expected_outputs) && plan.expected_outputs.length > 0 && (
              <div className="p-3 rounded-lg" style={{ background: 'hsl(230 18% 9%)' }}>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Expected Outputs</div>
                <div className="space-y-1">
                  {plan.expected_outputs.map((o: any, i) => (
                    <div key={i} className="text-xs text-foreground flex items-start gap-1.5">
                      <ChevronRight className="w-3 h-3 text-blue-400 mt-0.5 flex-shrink-0" />
                      <span className="font-mono break-all">{typeof o === 'object' ? JSON.stringify(o) : String(o)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {tab === 'timeline' && (
          <div>
            {tlLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground py-10 justify-center">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading timeline…
              </div>
            ) : timeline.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground text-sm">No state transitions recorded yet.</div>
            ) : (
              <div className="relative pl-5">
                <div className="absolute left-2 top-0 bottom-0 w-px bg-white/10" />
                {timeline.map((entry, i) => (
                  <div key={i} className="relative mb-5 pl-5">
                    <div className="absolute left-[-9px] top-1.5 w-2.5 h-2.5 rounded-full border-2 border-blue-500"
                      style={{ background: 'hsl(230 18% 6%)' }} />
                    <div className="text-[10px] text-muted-foreground font-mono mb-1.5">{fmt(entry.timestamp)}</div>
                    <div className="flex items-center gap-1.5 flex-wrap mb-1">
                      <StatusBadge status={entry.from} />
                      <ArrowRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                      <StatusBadge status={entry.to} />
                    </div>
                    {entry.by && (
                      <div className="text-[10px] text-muted-foreground flex items-center gap-1 mt-1">
                        <User className="w-2.5 h-2.5" /> {entry.by}
                      </div>
                    )}
                    {entry.reason && (
                      <div className="text-[10px] text-muted-foreground italic mt-0.5">{entry.reason}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'history' && (
          <div className="space-y-3">
            {histLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground py-10 justify-center">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading history…
              </div>
            ) : history.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground text-sm">No execution history yet.</div>
            ) : history.map(h => (
              <div key={h.execution_id} className="p-3 rounded-lg space-y-2.5"
                style={{ background: 'hsl(230 18% 9%)' }}>
                <div className="flex items-center justify-between">
                  <StatusBadge status={h.status.toUpperCase()} />
                  <span className="text-[10px] text-muted-foreground font-mono">{dur(h.start_time, h.end_time)}</span>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                  {[
                    { k: 'Started', v: fmt(h.start_time) },
                    { k: 'Ended',   v: fmt(h.end_time) },
                    { k: 'Engine',  v: h.engine_version ?? '—' },
                    { k: 'Planner', v: h.planner_version ?? '—' },
                    { k: 'Model',   v: h.model_used ?? '—' },
                    { k: 'Tokens',  v: h.token_usage != null ? String(h.token_usage) : '—' },
                  ].map(row => (
                    <div key={row.k} className="text-[10px]">
                      <span className="text-muted-foreground">{row.k}: </span>
                      <span className="text-foreground font-mono">{row.v}</span>
                    </div>
                  ))}
                </div>
                {h.error_message && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded p-2 text-[10px] text-red-300 font-mono break-all">
                    {h.error_message}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {tab === 'context' && (
          <div className="space-y-4">
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Required Inputs</div>
              {Object.keys(plan.required_inputs ?? {}).length === 0 ? (
                <p className="text-xs text-muted-foreground">No required inputs captured.</p>
              ) : (
                <pre className="text-[10px] font-mono rounded-lg p-3 overflow-auto text-green-300 leading-relaxed"
                  style={{ background: 'hsl(230 18% 4%)' }}>
                  {JSON.stringify(plan.required_inputs, null, 2)}
                </pre>
              )}
            </div>
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Execution Context</div>
              {Object.keys(plan.execution_context ?? {}).length === 0 ? (
                <p className="text-xs text-muted-foreground">No execution context captured yet.</p>
              ) : (
                <pre className="text-[10px] font-mono rounded-lg p-3 overflow-auto text-blue-300 leading-relaxed"
                  style={{ background: 'hsl(230 18% 4%)' }}>
                  {JSON.stringify(plan.execution_context, null, 2)}
                </pre>
              )}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function Remediation() {
  const [search, setSearch]           = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [page, setPage]               = useState(1);
  const [selected, setSelected]       = useState<RemediationPlan | null>(null);
  const [showPropose, setShowPropose] = useState(false);

  const qs = useMemo(() => {
    const p = new URLSearchParams({ page: String(page), page_size: '20' });
    if (statusFilter) p.set('status', statusFilter);
    if (priorityFilter) p.set('priority', priorityFilter);
    if (search.trim()) p.set('search', search.trim());
    return p.toString();
  }, [page, statusFilter, priorityFilter, search]);

  const { data: plansRaw,   loading: plansLoading,   refetch: refetchPlans   } = useApi<any>(`/remediation/plans?${qs}`);
  const { data: summaryRaw, refetch: refetchSummary } = useApi<Summary>('/remediation/summary');
  const { data: workersRaw } = useApi<any>('/remediation/workers/status');

  // 30-second polling
  useEffect(() => {
    const id = setInterval(() => { refetchPlans(); refetchSummary(); }, 30_000);
    return () => clearInterval(id);
  }, [refetchPlans, refetchSummary]);

  // Reset page when filters change
  useEffect(() => { setPage(1); }, [search, statusFilter, priorityFilter]);

  const plans: RemediationPlan[] = plansRaw?.data ?? [];
  const total: number            = plansRaw?.total ?? 0;
  const pages: number            = plansRaw?.pages ?? 1;
  const summary: Summary | null  = summaryRaw ?? null;
  const workers: any[]           = workersRaw?.workers ?? [];

  const refresh = useCallback(() => { refetchPlans(); refetchSummary(); }, [refetchPlans, refetchSummary]);
  const onProposed = useCallback(() => { setShowPropose(false); refresh(); }, [refresh]);
  const onAction   = useCallback(() => { refresh(); setSelected(null); }, [refresh]);

  return (
    <div className="space-y-4 relative">

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <Wrench className="w-5 h-5 text-blue-400" /> Remediation Center
          </h1>
          <p className="page-subtitle">
            Closed-loop remediation lifecycle — find, fix, validate, deploy, verify.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={refresh} className="action-btn" title="Refresh data">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setShowPropose(true)} className="action-btn-primary">
            <Zap className="w-3.5 h-3.5" /> Propose Remediation
          </button>
        </div>
      </div>

      {/* KPI Cards — row 1 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <KpiCard label="Total Plans"  value={summary?.total ?? '—'} />
        <KpiCard label="Open"         value={summary?.open ?? '—'}  color="text-blue-400" />
        <KpiCard label="Critical"     value={summary?.critical ?? '—'} color="text-red-400" />
        <KpiCard label="High"         value={summary?.high ?? '—'}  color="text-orange-400" />
        <KpiCard label="Executing"    value={summary?.executing ?? '—'} color="text-cyan-400" sub="running now" />
        <KpiCard label="Completed"    value={summary?.completed ?? '—'} color="text-green-400" />
      </div>

      {/* KPI Cards — row 2 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <KpiCard label="Ready to Run" value={summary?.ready_for_execution ?? '—'} color="text-cyan-300" />
        <KpiCard label="Validating"   value={summary?.waiting_for_validation ?? '—'} color="text-yellow-400" />
        <KpiCard label="Failed"       value={summary?.failed ?? '—'}    color="text-red-400" />
        <KpiCard label="Rolled Back"  value={summary?.rolled_back ?? '—'} color="text-orange-400" />
        <KpiCard label="Cancelled"    value={summary?.cancelled ?? '—'} color="text-gray-400" />
        <KpiCard label="Planning"     value={summary?.planning ?? '—'}  color="text-blue-300" />
      </div>

      {/* Pipeline Visual */}
      <PipelineBar summary={summary} />

      {/* Worker fleet strip */}
      {workers.length > 0 && (
        <div className="card-base py-2.5">
          <div className="flex items-center gap-4 flex-wrap">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold flex items-center gap-1">
              <Cpu className="w-3 h-3" /> Workers
            </span>
            {workers.map((w: any) => (
              <div key={w.name} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                <span className={clsx('w-1.5 h-1.5 rounded-full', w.status === 'active' ? 'bg-green-500 animate-pulse' : 'bg-red-500')} />
                <span className="text-foreground">{w.name}</span>
                <span className="text-white/20">·</span>
                <span className="capitalize">{w.load ?? 'unknown'} load</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search finding, type, tech, strategy…"
            className="w-full pl-8 pr-3 py-2 rounded-lg text-xs border outline-none focus:ring-2 focus:ring-blue-500/40 text-foreground"
            style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' }}
          />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-lg text-xs border outline-none text-foreground cursor-pointer"
          style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' }}>
          <option value="">All Statuses</option>
          {Object.entries(STATUS_META).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
        <select value={priorityFilter} onChange={e => setPriorityFilter(e.target.value)}
          className="px-3 py-2 rounded-lg text-xs border outline-none text-foreground cursor-pointer"
          style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' }}>
          <option value="">All Priorities</option>
          {['critical', 'high', 'medium', 'low'].map(p => (
            <option key={p} value={p} className="capitalize">{p.charAt(0).toUpperCase() + p.slice(1)}</option>
          ))}
        </select>
        <span className="text-xs text-muted-foreground ml-auto tabular-nums">{total} plan{total !== 1 ? 's' : ''}</span>
      </div>

      {/* Plans Table */}
      <div className="card-base overflow-hidden p-0">
        {plansLoading && plans.length === 0 ? (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-16">
            <Loader2 className="w-5 h-5 animate-spin" /> Loading remediation plans…
          </div>
        ) : plans.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4 text-center px-6">
            <div className="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center">
              <Wrench className="w-7 h-7 text-muted-foreground opacity-40" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground mb-1">No remediation tasks available</p>
              <p className="text-xs text-muted-foreground max-w-sm">
                {search || statusFilter || priorityFilter
                  ? 'No plans match your current filters. Try clearing the filters.'
                  : 'Propose a remediation plan by providing a finding ID from a vulnerability or threat. The engine will automatically generate a fix strategy.'}
              </p>
            </div>
            {!search && !statusFilter && !priorityFilter && (
              <button onClick={() => setShowPropose(true)} className="action-btn-primary">
                <Zap className="w-3.5 h-3.5" /> Propose First Remediation
              </button>
            )}
            {(search || statusFilter || priorityFilter) && (
              <button onClick={() => { setSearch(''); setStatusFilter(''); setPriorityFilter(''); }} className="action-btn">
                Clear Filters
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead style={{ background: 'hsl(230 18% 7%)' }}>
                <tr className="text-muted-foreground uppercase tracking-wider text-[10px] font-semibold border-b"
                  style={{ borderColor: 'hsl(230 15% 14%)' }}>
                  <th className="px-4 py-3">Finding ID</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Technology</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Strategy</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'hsl(230 15% 11%)' }}>
                {plans.map(plan => (
                  <tr
                    key={plan.id}
                    onClick={() => setSelected(plan)}
                    className={clsx(
                      'transition-colors cursor-pointer group',
                      selected?.id === plan.id
                        ? 'bg-blue-500/5'
                        : 'hover:bg-white/[0.02]'
                    )}
                  >
                    {/* Finding ID */}
                    <td className="px-4 py-3">
                      <div className="font-mono text-foreground text-[11px] max-w-[130px] truncate" title={plan.finding_id}>
                        {plan.finding_id.length > 16 ? plan.finding_id.slice(0, 14) + '…' : plan.finding_id}
                      </div>
                      <div className="text-[10px] text-muted-foreground">v{plan.version}</div>
                    </td>
                    {/* Priority */}
                    <td className="px-4 py-3 whitespace-nowrap"><PriorityDot priority={plan.priority} /></td>
                    {/* Type */}
                    <td className="px-4 py-3">
                      <span className="capitalize text-foreground">{plan.finding_type.replace(/_/g, ' ')}</span>
                    </td>
                    {/* Technology */}
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-white/5 border border-white/10 text-foreground">
                        {plan.target_technology}
                      </span>
                    </td>
                    {/* Status */}
                    <td className="px-4 py-3"><StatusBadge status={plan.status} /></td>
                    {/* Strategy */}
                    <td className="px-4 py-3">
                      <span className="text-muted-foreground font-mono text-[10px] max-w-[110px] block truncate" title={plan.strategy_id}>
                        {plan.strategy_id}
                      </span>
                    </td>
                    {/* Updated */}
                    <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">{fmt(plan.updated_at)}</td>
                    {/* Actions */}
                    <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center gap-1">
                        {(plan.status === 'CREATED' || plan.status === 'PLANNING') && (
                          <ActionBtn icon={<Play className="w-3 h-3" />} title="Start" colorClass="hover:bg-blue-500/15 hover:text-blue-400"
                            planId={plan.id} action="start" onDone={refresh} />
                        )}
                        {plan.status === 'READY_FOR_EXECUTION' && (
                          <ActionBtn icon={<SkipForward className="w-3 h-3" />} title="Execute" colorClass="hover:bg-blue-500/15 hover:text-blue-400"
                            planId={plan.id} action="execute" onDone={refresh} />
                        )}
                        {ACTIVE.has(plan.status) && (
                          <ActionBtn icon={<XCircle className="w-3 h-3" />} title="Cancel" colorClass="hover:bg-red-500/15 hover:text-red-400"
                            planId={plan.id} action="cancel" onDone={refresh} />
                        )}
                        {plan.status === 'FAILED' && (
                          <ActionBtn icon={<RotateCcw className="w-3 h-3" />} title="Rollback" colorClass="hover:bg-orange-500/15 hover:text-orange-400"
                            planId={plan.id} action="rollback" onDone={refresh} />
                        )}
                        <button onClick={() => setSelected(plan)} title="View details"
                          className="p-1.5 rounded-md text-muted-foreground hover:text-blue-400 hover:bg-blue-500/10 transition-all">
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t text-xs"
            style={{ borderColor: 'hsl(230 15% 14%)' }}>
            <span className="text-muted-foreground">Page {page} of {pages} · {total} plans</span>
            <div className="flex gap-1">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                className="action-btn py-1 px-2.5 disabled:opacity-40">
                <ChevronLeft className="w-3 h-3" /> Prev
              </button>
              <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page >= pages}
                className="action-btn py-1 px-2.5 disabled:opacity-40">
                Next <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Overlay + Detail Drawer */}
      <AnimatePresence>
        {selected && (
          <>
            <motion.div
              key="overlay"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 z-30 bg-black/40 backdrop-blur-[2px]"
              onClick={() => setSelected(null)}
            />
            <DetailDrawer key="drawer" plan={selected} onClose={() => setSelected(null)} onAction={onAction} />
          </>
        )}
      </AnimatePresence>

      {/* Propose Modal */}
      <AnimatePresence>
        {showPropose && (
          <ProposeModal key="propose" onClose={() => setShowPropose(false)} onSuccess={onProposed} />
        )}
      </AnimatePresence>
    </div>
  );
}
