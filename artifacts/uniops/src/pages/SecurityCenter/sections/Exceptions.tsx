import { useState, useCallback, useRef, useEffect, useMemo, memo } from 'react';
import {
  ClipboardList, Plus, RefreshCw, Loader2, CheckCircle, XCircle,
  AlertTriangle, Clock, User, Calendar, Shield, Timer, Search, X,
  ChevronRight, Info, Activity, History, FileText, Lock, Box,
  Server, Cloud, Code, GitBranch, Layers, Bell, ShieldAlert,
  ShieldCheck, ShieldOff, RotateCcw, Ban, Download,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { usePermissions } from '@/hooks/use-permissions';
import { canManageCompliance } from '@/lib/permissions';

// ─── Types ────────────────────────────────────────────────────────────────────

interface SecurityException {
  id: string;
  tenant_id: string;
  policy_id?: string;
  finding_id?: string;
  finding_type?: string;
  title: string;
  justification: string;
  risk_acceptance: string;
  status: string;
  exception_type: string;
  requested_by: string;
  approved_by?: string;
  rejected_by?: string;
  reviewer_note?: string;
  expires_at?: string;
  reviewed_at?: string;
  scope: Record<string, any>;
  tags: Record<string, any>;
  created_at: string;
  updated_at: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const EXCEPTION_CATEGORIES = [
  { value: 'policy',        label: 'Policy Exception',       icon: Shield,     color: 'text-blue-400' },
  { value: 'vulnerability', label: 'Vulnerability Exception', icon: ShieldAlert,color: 'text-red-400' },
  { value: 'compliance',    label: 'Compliance Waiver',       icon: FileText,   color: 'text-indigo-400' },
  { value: 'threat',        label: 'Threat Exception',        icon: AlertTriangle, color: 'text-orange-400' },
  { value: 'secret',        label: 'Secret Exception',        icon: Lock,       color: 'text-purple-400' },
  { value: 'kubernetes',    label: 'Kubernetes Exception',    icon: Server,     color: 'text-cyan-400' },
  { value: 'cloud',         label: 'Cloud Exception',         icon: Cloud,      color: 'text-sky-400' },
  { value: 'container',     label: 'Container Exception',     icon: Box,        color: 'text-teal-400' },
  { value: 'sbom',          label: 'SBOM Exception',          icon: Layers,     color: 'text-green-400' },
  { value: 'runtime',       label: 'Runtime Exception',       icon: Activity,   color: 'text-yellow-400' },
  { value: 'repository',    label: 'Repository Exception',    icon: GitBranch,  color: 'text-pink-400' },
  { value: 'custom',        label: 'Custom Exception',        icon: Code,       color: 'text-gray-400' },
];

const CAT_MAP = Object.fromEntries(EXCEPTION_CATEGORIES.map(c => [c.value, c]));

const STATUS_STYLE: Record<string, string> = {
  pending:  'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  approved: 'bg-green-500/10 text-green-400 border-green-500/20',
  rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
  expired:  'bg-gray-500/10 text-gray-400 border-gray-500/20',
  revoked:  'bg-red-900/20 text-red-300 border-red-900/30',
};

const WORKFLOW_STEPS = [
  { key: 'requested',     label: 'Requested',    icon: Plus },
  { key: 'under_review',  label: 'Under Review', icon: Clock },
  { key: 'approved',      label: 'Approved',     icon: CheckCircle },
  { key: 'rejected',      label: 'Rejected',     icon: XCircle },
  { key: 'expired',       label: 'Expired',      icon: Timer },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function daysUntil(dateStr?: string | null): number | null {
  if (!dateStr) return null;
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86400000);
}

function avgDays(exceptions: SecurityException[]): string {
  const timed = exceptions.filter(e => e.expires_at && e.created_at);
  if (!timed.length) return '—';
  const avg = timed.reduce((sum, e) => {
    const diff = new Date(e.expires_at!).getTime() - new Date(e.created_at).getTime();
    return sum + diff / 86400000;
  }, 0) / timed.length;
  return `${Math.round(avg)}d`;
}

function fmt(ts?: string | null): string {
  if (!ts) return '—';
  const d = new Date(ts);
  const diff = Date.now() - d.getTime();
  if (diff < 60000)    return 'just now';
  if (diff < 3600000)  return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function getCategory(e: SecurityException) {
  const key = e.tags?.category ?? e.finding_type ?? 'custom';
  return CAT_MAP[key] ?? CAT_MAP.custom;
}

const Skel = ({ className }: { className?: string }) =>
  <div className={clsx('animate-pulse rounded-lg bg-white/5', className)} />;

// ─── Expiry Badge ─────────────────────────────────────────────────────────────

const ExpiryBadge = memo(({ expiresAt, showFull }: { expiresAt?: string | null; showFull?: boolean }) => {
  const days = daysUntil(expiresAt);
  if (days === null) return <span className="text-muted-foreground/40 text-[10px] italic">No expiry</span>;
  if (days < 0)  return <span className="text-[10px] font-semibold text-red-400 flex items-center gap-1"><Timer size={9} />Expired {Math.abs(days)}d ago</span>;
  if (days === 0) return <span className="text-[10px] font-bold text-red-400 animate-pulse flex items-center gap-1"><Timer size={9} />Expires TODAY</span>;
  if (days <= 7)  return <span className="text-[10px] font-semibold text-orange-400 flex items-center gap-1"><Timer size={9} />{days}d left</span>;
  if (days <= 30) return <span className="text-[10px] font-medium text-yellow-400 flex items-center gap-1"><Timer size={9} />{days}d left</span>;
  if (showFull)   return <span className="text-[10px] text-muted-foreground">{new Date(expiresAt!).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>;
  return <span className="text-[10px] text-muted-foreground">{days}d left</span>;
});

// ─── Status Badge ─────────────────────────────────────────────────────────────

const StatusBadge = memo(({ status }: { status: string }) => (
  <span className={clsx('inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-semibold capitalize',
    STATUS_STYLE[status] ?? 'bg-white/5 text-muted-foreground border-white/10')}>
    {status === 'approved' ? <CheckCircle size={9} /> : status === 'rejected' ? <XCircle size={9} /> :
     status === 'pending' ? <Clock size={9} /> : status === 'expired' ? <Timer size={9} /> : null}
    {status}
  </span>
));

// ─── Approval Workflow ────────────────────────────────────────────────────────

const ApprovalWorkflow = memo(({ exc }: { exc: SecurityException }) => {
  const activeStep = exc.status === 'pending' ? 'under_review'
    : exc.status === 'approved' ? 'approved'
    : exc.status === 'rejected' ? 'rejected'
    : exc.status === 'expired'  ? 'expired'
    : 'requested';

  const stepOrder = ['requested', 'under_review', 'approved'];
  const currentIdx = stepOrder.indexOf(activeStep);

  return (
    <div className="space-y-3">
      {/* Visual stepper */}
      <div className="flex items-center gap-0">
        {['Requested', 'Under Review', 'Decision'].map((label, i) => {
          const done = i < currentIdx || (i === 2 && (exc.status === 'approved' || exc.status === 'rejected' || exc.status === 'expired'));
          const active = i === currentIdx && exc.status === 'pending';
          return (
            <div key={label} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                <div className={clsx('w-7 h-7 rounded-full border-2 flex items-center justify-center text-[10px] font-bold transition-all',
                  done   ? 'bg-green-500 border-green-400 text-white'
                  : active ? 'bg-blue-500/20 border-blue-400 text-blue-400 animate-pulse'
                  : 'bg-surface-2 border-white/15 text-muted-foreground')}>
                  {done ? <CheckCircle size={12} /> : i + 1}
                </div>
                <span className="text-[9px] text-muted-foreground mt-1 whitespace-nowrap">{label}</span>
              </div>
              {i < 2 && <div className={clsx('flex-1 h-0.5 mx-1 -mt-4', done ? 'bg-green-500/50' : 'bg-white/10')} />}
            </div>
          );
        })}
      </div>

      {/* Decision outcome */}
      {exc.status !== 'pending' && (
        <div className={clsx('rounded-xl border p-3', STATUS_STYLE[exc.status] ?? '')}>
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-semibold capitalize">{exc.status}</p>
              {exc.reviewed_at && <p className="text-[10px] text-muted-foreground">{fmt(exc.reviewed_at)}</p>}
            </div>
            {exc.approved_by && <span className="text-[10px] text-muted-foreground">by {exc.approved_by.slice(0, 8)}…</span>}
            {exc.rejected_by && <span className="text-[10px] text-muted-foreground">by {exc.rejected_by.slice(0, 8)}…</span>}
          </div>
          {exc.reviewer_note && (
            <p className="text-[11px] text-muted-foreground mt-1.5 italic border-l-2 border-current/30 pl-2">"{exc.reviewer_note}"</p>
          )}
        </div>
      )}
    </div>
  );
});

// ─── Exception Detail Drawer ──────────────────────────────────────────────────

const ExceptionDrawer = memo(({ exc, onClose, onReview, onRefresh, canApprove }: {
  exc: SecurityException;
  onClose: () => void;
  onReview: (e: SecurityException, action: 'approve' | 'reject') => void;
  onRefresh: () => void;
  canApprove: boolean;
}) => {
  const [tab, setTab] = useState<'overview' | 'risk' | 'approval' | 'timeline'>('overview');
  const cat = getCategory(exc);
  const CatIcon = cat.icon;
  const days = daysUntil(exc.expires_at);

  const TABS = [
    { id: 'overview', label: 'Overview',          icon: Info },
    { id: 'risk',     label: 'Risk Information',   icon: ShieldAlert },
    { id: 'approval', label: 'Approval Workflow',  icon: CheckCircle },
    { id: 'timeline', label: 'Timeline',           icon: History },
  ] as const;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-full max-w-xl z-50 flex flex-col bg-surface-1 border-l border-white/8 shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="p-5 border-b border-white/8 shrink-0">
          <div className="flex items-start gap-3">
            <div className={clsx('w-9 h-9 rounded-xl bg-surface-2 border border-white/10 flex items-center justify-center shrink-0', cat.color)}>
              <CatIcon size={16} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <StatusBadge status={exc.status} />
                <span className="text-[10px] px-1.5 py-0.5 rounded border border-white/10 text-muted-foreground capitalize">{exc.exception_type}</span>
                {days !== null && days <= 7 && <ExpiryBadge expiresAt={exc.expires_at} />}
              </div>
              <h2 className="text-sm font-bold text-foreground line-clamp-2">{exc.title}</h2>
              <p className={clsx('text-[10px] font-medium mt-0.5', cat.color)}>{cat.label}</p>
            </div>
            <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors shrink-0">
              <X size={14} />
            </button>
          </div>

          {/* Quick actions for pending */}
          {canApprove && exc.status === 'pending' && (
            <div className="flex gap-2 mt-3">
              <button onClick={() => onReview(exc, 'approve')}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-green-600 hover:bg-green-500 text-white font-semibold transition-colors">
                <CheckCircle size={12} /> Approve
              </button>
              <button onClick={() => onReview(exc, 'reject')}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-red-600 hover:bg-red-500 text-white font-semibold transition-colors">
                <XCircle size={12} /> Reject
              </button>
            </div>
          )}
        </div>

        {/* Tab nav */}
        <div className="flex items-center gap-1 px-4 pt-3 border-b border-white/8 shrink-0 overflow-x-auto">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id as any)}
              className={clsx('flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium whitespace-nowrap border-b-2 transition-all -mb-px',
                tab === t.id ? 'border-blue-500 text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground')}>
              <t.icon size={10} />
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">

          {/* Overview */}
          {tab === 'overview' && (
            <>
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['Exception ID',  <code className="text-[10px] text-muted-foreground font-mono">{exc.id.slice(0,8)}…</code>],
                  ['Status',        <StatusBadge status={exc.status} />],
                  ['Category',      <span className={clsx('text-xs font-medium', cat.color)}>{cat.label}</span>],
                  ['Duration Type', <span className="text-xs text-foreground capitalize">{exc.exception_type}</span>],
                  ['Requested By',  <span className="text-xs text-muted-foreground">{exc.requested_by.slice(0,8)}…</span>],
                  ['Approved By',   <span className="text-xs text-muted-foreground">{exc.approved_by ? exc.approved_by.slice(0,8)+'…' : '—'}</span>],
                  ['Created',       <span className="text-xs text-muted-foreground">{fmt(exc.created_at)}</span>],
                  ['Expiration',    <ExpiryBadge expiresAt={exc.expires_at} showFull />],
                ].map(([label, val], i) => (
                  <div key={i} className="bg-surface-2 border border-white/5 rounded-xl p-3">
                    <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-1">{label as string}</p>
                    <div>{val as React.ReactNode}</div>
                  </div>
                ))}
              </div>

              <div className="bg-surface-2 border border-white/5 rounded-xl p-3">
                <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-2">Business Justification</p>
                <p className="text-xs text-foreground leading-relaxed">{exc.justification || '—'}</p>
              </div>

              {exc.policy_id && (
                <div className="bg-surface-2 border border-white/5 rounded-xl p-3">
                  <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-1">Linked Policy</p>
                  <code className="text-xs text-blue-400 font-mono">{exc.policy_id.slice(0,8)}…</code>
                </div>
              )}

              {exc.finding_id && (
                <div className="bg-surface-2 border border-white/5 rounded-xl p-3">
                  <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-1">Linked Finding</p>
                  <div className="flex items-center gap-2">
                    <code className="text-xs text-orange-400 font-mono">{exc.finding_id.slice(0,8)}…</code>
                    {exc.finding_type && <span className="text-[10px] capitalize text-muted-foreground">{exc.finding_type}</span>}
                  </div>
                </div>
              )}

              {Object.keys(exc.scope).length > 0 && (
                <div className="bg-surface-2 border border-white/5 rounded-xl p-3">
                  <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-2">Scope / Affected Resources</p>
                  <pre className="text-[10px] font-mono text-muted-foreground bg-black/20 rounded-lg p-2 overflow-x-auto">
                    {JSON.stringify(exc.scope, null, 2)}
                  </pre>
                </div>
              )}

              {exc.reviewer_note && (
                <div className="bg-surface-2 border border-white/5 rounded-xl p-3">
                  <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-2">Reviewer Note</p>
                  <p className="text-xs text-muted-foreground italic">"{exc.reviewer_note}"</p>
                </div>
              )}
            </>
          )}

          {/* Risk Information */}
          {tab === 'risk' && (
            <>
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['Risk Acceptance Level', <span className="text-xs text-foreground capitalize">{exc.tags?.risk_level ?? 'Accepted'}</span>],
                  ['Original Severity',     <span className={clsx('text-xs font-semibold capitalize', exc.tags?.severity === 'critical' ? 'text-red-400' : exc.tags?.severity === 'high' ? 'text-orange-400' : exc.tags?.severity === 'medium' ? 'text-yellow-400' : 'text-green-400')}>{exc.tags?.severity ?? '—'}</span>],
                  ['Residual Risk',         <span className="text-xs text-foreground">{exc.tags?.residual_risk ?? '—'}</span>],
                  ['Business Impact',       <span className="text-xs text-foreground capitalize">{exc.tags?.business_impact ?? '—'}</span>],
                  ['Likelihood',            <span className="text-xs text-foreground capitalize">{exc.tags?.likelihood ?? '—'}</span>],
                  ['Risk Owner',            <span className="text-xs text-muted-foreground">{exc.tags?.owner ?? exc.tags?.risk_owner ?? '—'}</span>],
                ].map(([label, val], i) => (
                  <div key={i} className="bg-surface-2 border border-white/5 rounded-xl p-3">
                    <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-1">{label as string}</p>
                    <div>{val as React.ReactNode}</div>
                  </div>
                ))}
              </div>

              <div className="bg-surface-2 border border-white/5 rounded-xl p-3">
                <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-2">Risk Acceptance / Compensating Controls</p>
                <p className="text-xs text-foreground leading-relaxed">{exc.risk_acceptance || <span className="text-muted-foreground italic">No compensating controls documented.</span>}</p>
              </div>

              {/* Expiration risk warning */}
              {(() => {
                const d = daysUntil(exc.expires_at);
                if (d === null) return null;
                if (d < 0) return (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 flex items-start gap-2">
                    <AlertTriangle size={14} className="text-red-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-semibold text-red-400">Exception Expired</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">This exception expired {Math.abs(d)} day{Math.abs(d) !== 1 ? 's' : ''} ago. Policy enforcement may now apply.</p>
                    </div>
                  </div>
                );
                if (d <= 7) return (
                  <div className="bg-orange-500/10 border border-orange-500/20 rounded-xl p-3 flex items-start gap-2">
                    <Timer size={14} className="text-orange-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-semibold text-orange-400">Expiring in {d} day{d !== 1 ? 's' : ''}</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">Consider submitting a renewal request before expiration.</p>
                    </div>
                  </div>
                );
                return null;
              })()}
            </>
          )}

          {/* Approval Workflow */}
          {tab === 'approval' && (
            <>
              <div className="bg-surface-2 border border-white/5 rounded-xl p-4">
                <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-4">Approval Progress</p>
                <ApprovalWorkflow exc={exc} />
              </div>

              <div className="space-y-2">
                {[
                  { label: 'Requested',    ts: exc.created_at,   by: exc.requested_by,  status: 'done' },
                  { label: 'Under Review', ts: exc.created_at,   by: null,               status: exc.status === 'pending' ? 'active' : exc.status !== 'pending' ? 'done' : 'pending' },
                  { label: exc.status === 'approved' ? 'Approved' : exc.status === 'rejected' ? 'Rejected' : 'Pending Decision',
                    ts: exc.reviewed_at,   by: exc.approved_by ?? exc.rejected_by,
                    status: exc.reviewed_at ? 'done' : 'pending' },
                ].map((step, i) => (
                  <div key={i} className="bg-surface-2 border border-white/5 rounded-xl p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={clsx('w-5 h-5 rounded-full flex items-center justify-center',
                          step.status === 'done' ? 'bg-green-500/20 text-green-400' : step.status === 'active' ? 'bg-blue-500/20 text-blue-400' : 'bg-white/5 text-muted-foreground')}>
                          {step.status === 'done' ? <CheckCircle size={10} /> : step.status === 'active' ? <Clock size={10} /> : <Clock size={10} />}
                        </div>
                        <span className="text-xs text-foreground">{step.label}</span>
                      </div>
                      {step.ts && <span className="text-[10px] text-muted-foreground">{fmt(step.ts)}</span>}
                    </div>
                    {step.by && <p className="text-[10px] text-muted-foreground mt-1 ml-7">by {step.by.slice(0, 8)}…</p>}
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Timeline */}
          {tab === 'timeline' && (
            <div className="space-y-0">
              {[
                { ts: exc.created_at, label: 'Exception requested', icon: Plus, color: 'text-blue-400' },
                { ts: exc.created_at, label: 'Entered review queue', icon: Clock, color: 'text-yellow-400' },
                ...(exc.reviewed_at ? [{
                  ts: exc.reviewed_at,
                  label: exc.status === 'approved' ? 'Exception approved' : 'Exception rejected',
                  icon: exc.status === 'approved' ? CheckCircle : XCircle,
                  color: exc.status === 'approved' ? 'text-green-400' : 'text-red-400',
                }] : []),
                ...(exc.expires_at && daysUntil(exc.expires_at)! < 0 ? [{
                  ts: exc.expires_at!,
                  label: 'Exception expired',
                  icon: Timer,
                  color: 'text-red-400',
                }] : []),
              ].sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
               .map((ev, i, arr) => (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <div className={clsx('w-6 h-6 rounded-full bg-surface-2 border border-white/10 flex items-center justify-center shrink-0', ev.color)}>
                      <ev.icon size={10} />
                    </div>
                    {i < arr.length - 1 && <div className="w-px flex-1 bg-white/8 my-1" />}
                  </div>
                  <div className="pb-4 pt-0.5 flex-1">
                    <p className="text-xs text-foreground">{ev.label}</p>
                    <p className="text-[10px] text-muted-foreground">{fmt(ev.ts)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
});

// ─── Summary Cards ────────────────────────────────────────────────────────────

const SummaryCards = memo(({ stats, exceptions }: { stats: any; exceptions: SecurityException[] }) => {
  const expiringSoon = exceptions.filter(e => {
    const d = daysUntil(e.expires_at);
    return e.status === 'approved' && d !== null && d >= 0 && d <= 7;
  }).length;
  const policiesWaived = exceptions.filter(e => e.policy_id && e.status === 'approved').length;

  const cards = [
    { label: 'Total Exceptions',   value: stats.total    ?? 0, color: 'text-foreground',   icon: ClipboardList },
    { label: 'Active (Approved)',   value: stats.approved ?? 0, color: 'text-green-400',    icon: ShieldCheck },
    { label: 'Expired',            value: stats.expired  ?? 0, color: 'text-gray-400',     icon: ShieldOff },
    { label: 'Pending Approval',   value: stats.pending  ?? 0, color: 'text-yellow-400',   icon: Clock },
    { label: 'Rejected',           value: stats.rejected ?? 0, color: 'text-red-400',      icon: XCircle },
    { label: 'Policies Waived',    value: policiesWaived,      color: 'text-blue-400',     icon: Shield },
    { label: 'Avg Duration',       value: avgDays(exceptions), color: 'text-purple-400',   icon: Timer, isStr: true },
    { label: 'Expiring ≤ 7d',      value: expiringSoon,        color: 'text-orange-400',   icon: AlertTriangle },
  ];

  return (
    <div className="grid grid-cols-4 lg:grid-cols-8 gap-2">
      {cards.map(({ label, value, color, icon: Icon, isStr }) => (
        <div key={label} className="bg-surface-2 border border-white/5 rounded-xl p-3 flex flex-col gap-1.5">
          <div className={clsx('flex items-center gap-1.5', color)}>
            <Icon size={11} />
            <span className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground">{label}</span>
          </div>
          <p className={clsx('text-xl font-bold', color)}>{isStr ? value : (value as number).toLocaleString()}</p>
        </div>
      ))}
    </div>
  );
});

// ─── Exceptions Table ─────────────────────────────────────────────────────────

const ExceptionsTable = memo(({ exceptions, loading, total, page, pages, onPageChange, onSelect, onReview, canApprove }: {
  exceptions: SecurityException[];
  loading: boolean;
  total: number;
  page: number;
  pages: number;
  onPageChange: (p: number) => void;
  onSelect: (e: SecurityException) => void;
  onReview: (e: SecurityException, action: 'approve' | 'reject') => void;
  canApprove: boolean;
}) => {
  if (loading && exceptions.length === 0) {
    return <div className="space-y-1.5">{Array.from({ length: 8 }).map((_, i) => <Skel key={i} className="h-12" />)}</div>;
  }
  if (exceptions.length === 0) {
    return (
      <div className="py-20 flex flex-col items-center gap-3">
        <ClipboardList size={40} className="text-muted-foreground opacity-25" />
        <p className="text-sm font-medium text-foreground">No security exceptions found</p>
        <p className="text-xs text-muted-foreground">Submit a request when a policy violation needs a sanctioned exception.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{total.toLocaleString()} exception{total !== 1 ? 's' : ''}</span>
      </div>
      <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/8 bg-surface-1/30">
              {['Title', 'Type', 'Category', 'Severity', 'Status', 'Expiration', 'Days Left', 'Requested', 'Filed', ''].map(h => (
                <th key={h} className="px-3 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {exceptions.map(e => {
              const days = daysUntil(e.expires_at);
              const isExpiringSoon = e.status === 'approved' && days !== null && days >= 0 && days <= 7;
              const isExpired = days !== null && days < 0;
              const cat = getCategory(e);
              const CatIcon = cat.icon;

              return (
                <tr key={e.id}
                  onClick={() => onSelect(e)}
                  className={clsx('border-b border-white/4 hover:bg-white/3 transition-colors cursor-pointer group',
                    isExpiringSoon && 'bg-orange-500/3',
                    isExpired && 'bg-red-500/3')}>
                  <td className="px-3 py-3 max-w-[200px]">
                    <div className="flex items-center gap-1.5">
                      {e.status === 'pending' && <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 shrink-0 animate-pulse" />}
                      <p className="font-medium text-foreground truncate">{e.title}</p>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-white/10 text-muted-foreground capitalize">{e.exception_type}</span>
                  </td>
                  <td className="px-3 py-3">
                    <span className={clsx('flex items-center gap-1 text-[10px] font-medium', cat.color)}>
                      <CatIcon size={10} />
                      {cat.label}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    {e.tags?.severity ? (
                      <span className={clsx('text-[10px] font-semibold capitalize',
                        e.tags.severity === 'critical' ? 'text-red-400' : e.tags.severity === 'high' ? 'text-orange-400'
                        : e.tags.severity === 'medium' ? 'text-yellow-400' : 'text-green-400')}>
                        {e.tags.severity}
                      </span>
                    ) : <span className="text-muted-foreground/40">—</span>}
                  </td>
                  <td className="px-3 py-3"><StatusBadge status={e.status} /></td>
                  <td className="px-3 py-3 whitespace-nowrap">
                    <ExpiryBadge expiresAt={e.expires_at} showFull />
                  </td>
                  <td className="px-3 py-3">
                    {days === null ? <span className="text-muted-foreground/40">—</span>
                      : days < 0 ? <span className="text-red-400 font-bold text-[10px]">Expired</span>
                      : <span className={clsx('font-mono font-semibold text-[10px]', days <= 7 ? 'text-orange-400' : days <= 30 ? 'text-yellow-400' : 'text-muted-foreground')}>
                          {days}d
                        </span>}
                  </td>
                  <td className="px-3 py-3 text-muted-foreground max-w-[80px]">
                    <p className="truncate">{e.requested_by.slice(0, 8)}…</p>
                  </td>
                  <td className="px-3 py-3 text-muted-foreground whitespace-nowrap">{fmt(e.created_at)}</td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={ev => { ev.stopPropagation(); onSelect(e); }}
                        className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors" title="View details">
                        <ChevronRight size={12} />
                      </button>
                      {canApprove && e.status === 'pending' && (
                        <>
                          <button onClick={ev => { ev.stopPropagation(); onReview(e, 'approve'); }}
                            className="p-1 rounded text-green-400 hover:bg-green-500/10 transition-colors" title="Approve">
                            <CheckCircle size={12} />
                          </button>
                          <button onClick={ev => { ev.stopPropagation(); onReview(e, 'reject'); }}
                            className="p-1 rounded text-red-400 hover:bg-red-500/10 transition-colors" title="Reject">
                            <XCircle size={12} />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">Page {page} of {pages}</span>
          <div className="flex gap-1">
            <button onClick={() => onPageChange(page - 1)} disabled={page <= 1}
              className="px-2.5 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-md hover:bg-white/8 disabled:opacity-40">Prev</button>
            <button onClick={() => onPageChange(page + 1)} disabled={page >= pages}
              className="px-2.5 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-md hover:bg-white/8 disabled:opacity-40">Next</button>
          </div>
        </div>
      )}
    </div>
  );
});

// ─── Review Modal ─────────────────────────────────────────────────────────────

const ReviewModal = memo(({ exc, action, onClose, onDone }: {
  exc: SecurityException; action: 'approve' | 'reject'; onClose: () => void; onDone: () => void;
}) => {
  const [note, setNote]     = useState('');
  const [saving, setSaving] = useState(false);
  const handle = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/security-exceptions/${exc.id}/review`, { action, reviewer_note: note });
      onDone(); onClose();
    } finally { setSaving(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md mx-4 bg-surface-1 border border-white/8 rounded-xl p-5 shadow-2xl">
        <div className="flex items-center gap-2 mb-1">
          {action === 'approve' ? <CheckCircle size={16} className="text-green-400" /> : <XCircle size={16} className="text-red-400" />}
          <h3 className="text-sm font-bold text-foreground">
            {action === 'approve' ? 'Approve Exception' : 'Reject Exception'}
          </h3>
        </div>
        <p className="text-xs text-muted-foreground mb-4 line-clamp-2">{exc.title}</p>

        {action === 'approve' && (
          <div className="bg-green-500/5 border border-green-500/15 rounded-xl p-3 mb-4">
            <p className="text-[11px] text-green-400">Approving will allow this exception to waive the associated policy or finding until its expiration date.</p>
          </div>
        )}
        {action === 'reject' && (
          <div className="bg-red-500/5 border border-red-500/15 rounded-xl p-3 mb-4">
            <p className="text-[11px] text-red-400">Rejecting will keep the policy or finding in enforcement mode. A rejection reason is required.</p>
          </div>
        )}

        <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
          Reviewer Note {action === 'reject' ? '(required)' : '(optional)'}
        </label>
        <textarea value={note} onChange={e => setNote(e.target.value)}
          className="w-full px-3 py-2 text-xs rounded-lg border border-white/10 bg-surface-2 text-foreground focus:outline-none focus:border-blue-500/50 resize-none"
          rows={3} placeholder={action === 'reject' ? 'Why is this exception being rejected?' : 'Any conditions or additional notes?'} />

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-lg border border-white/10 text-muted-foreground hover:text-foreground transition-colors">
            Cancel
          </button>
          <button onClick={handle} disabled={saving || (action === 'reject' && !note.trim())}
            className={clsx('flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg text-white font-semibold transition-colors disabled:opacity-50',
              action === 'approve' ? 'bg-green-600 hover:bg-green-500' : 'bg-red-600 hover:bg-red-500')}>
            {saving ? <Loader2 size={12} className="animate-spin" /> : action === 'approve' ? <CheckCircle size={12} /> : <XCircle size={12} />}
            {saving ? 'Saving…' : action === 'approve' ? 'Approve' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  );
});

// ─── Create Exception Modal ───────────────────────────────────────────────────

const CreateExceptionModal = memo(({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) => {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    title: '', justification: '', risk_acceptance: '',
    exception_type: 'temporary', category: 'policy',
    severity: 'high', expires_at: '', policy_id: '', finding_id: '',
    business_impact: '', likelihood: '',
  });

  const handle = async () => {
    if (!form.title.trim() || !form.justification.trim()) return;
    setSaving(true);
    try {
      const payload: any = {
        title: form.title.trim(),
        justification: form.justification.trim(),
        risk_acceptance: form.risk_acceptance.trim(),
        exception_type: form.exception_type,
        finding_type: form.category,
        tags: {
          category: form.category,
          severity: form.severity,
          business_impact: form.business_impact || undefined,
          likelihood: form.likelihood || undefined,
        },
        scope: {},
      };
      if (form.expires_at) payload.expires_at = form.expires_at;
      if (form.policy_id.trim()) payload.policy_id = form.policy_id.trim();
      if (form.finding_id.trim()) payload.finding_id = form.finding_id.trim();
      await apiClient.post('/security-exceptions', payload);
      onCreated(); onClose();
    } finally { setSaving(false); }
  };

  const inp = 'w-full px-3 py-2 text-xs rounded-lg border border-white/10 bg-surface-2 text-foreground focus:outline-none focus:border-blue-500/50';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg mx-4 bg-surface-1 border border-white/8 rounded-xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/8">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2"><Plus size={14} /> Request Security Exception</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X size={14} /></button>
        </div>
        <div className="p-5 space-y-3 overflow-y-auto max-h-[70vh]">
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Title *</label>
            <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className={inp} placeholder="Brief description of the exception needed" />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Business Justification *</label>
            <textarea value={form.justification} onChange={e => setForm(f => ({ ...f, justification: e.target.value }))}
              className={clsx(inp, 'resize-none')} rows={3}
              placeholder="Why is this exception required? What is the business context?" />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Risk Acceptance / Compensating Controls</label>
            <textarea value={form.risk_acceptance} onChange={e => setForm(f => ({ ...f, risk_acceptance: e.target.value }))}
              className={clsx(inp, 'resize-none')} rows={2}
              placeholder="What mitigations or compensating controls are in place?" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Exception Category</label>
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className={inp}>
                {EXCEPTION_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Duration Type</label>
              <select value={form.exception_type} onChange={e => setForm(f => ({ ...f, exception_type: e.target.value }))}
                className={inp}>
                <option value="temporary">Temporary</option>
                <option value="permanent">Permanent</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Original Severity</label>
              <select value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}
                className={inp}>
                {['critical','high','medium','low'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Expiration Date</label>
              <input type="date" value={form.expires_at} onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))}
                className={inp} />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Business Impact</label>
              <select value={form.business_impact} onChange={e => setForm(f => ({ ...f, business_impact: e.target.value }))}
                className={inp}>
                <option value="">Not specified</option>
                {['critical','high','medium','low'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Likelihood</label>
              <select value={form.likelihood} onChange={e => setForm(f => ({ ...f, likelihood: e.target.value }))}
                className={inp}>
                <option value="">Not specified</option>
                {['certain','likely','possible','unlikely','rare'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Policy ID (optional)</label>
              <input value={form.policy_id} onChange={e => setForm(f => ({ ...f, policy_id: e.target.value }))}
                className={inp} placeholder="UUID of linked policy" />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Finding ID (optional)</label>
              <input value={form.finding_id} onChange={e => setForm(f => ({ ...f, finding_id: e.target.value }))}
                className={inp} placeholder="UUID of linked finding" />
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-white/8">
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-lg border border-white/10 text-muted-foreground hover:text-foreground transition-colors">
            Cancel
          </button>
          <button onClick={handle} disabled={saving || !form.title.trim() || !form.justification.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition-colors disabled:opacity-50">
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            {saving ? 'Submitting…' : 'Submit Request'}
          </button>
        </div>
      </div>
    </div>
  );
});

// ─── Main Component ───────────────────────────────────────────────────────────

export default function ExceptionsSection() {
  const { role }   = usePermissions();
  const canApprove = canManageCompliance(role);

  const [search, setSearch]     = useState('');
  const [dSearch, setDSearch]   = useState('');
  const [status, setStatus]     = useState('');
  const [category, setCategory] = useState('');
  const [expiry, setExpiry]     = useState('');
  const [page, setPage]         = useState(1);
  const [selected, setSelected] = useState<SecurityException | null>(null);
  const [reviewModal, setReviewModal] = useState<{ exc: SecurityException; action: 'approve' | 'reject' } | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { setDSearch(search); setPage(1); }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  const qs = useMemo(() => {
    const p: Record<string, string> = { page: String(page), page_size: '20' };
    if (status)   p.status = status;
    if (category) p.exception_type = category;
    return new URLSearchParams(p).toString();
  }, [page, status, category]);

  const { data: raw, loading, refetch } = useApi<any>(`/security-exceptions?${qs}`);
  const { data: statsRaw, refetch: refetchStats } = useApi<any>('/security-exceptions/stats');

  const result     = raw?.data ?? raw;
  const allExceptions: SecurityException[] = useMemo(() => result?.data ?? [], [result]);
  const total      = result?.total ?? 0;
  const pages      = result?.pages ?? 1;
  const stats      = statsRaw?.data ?? statsRaw ?? {};

  // Client-side expiry + search filter
  const exceptions = useMemo(() => {
    let list = allExceptions;
    if (dSearch) {
      const q = dSearch.toLowerCase();
      list = list.filter(e =>
        e.title.toLowerCase().includes(q) ||
        e.id.toLowerCase().includes(q) ||
        e.justification.toLowerCase().includes(q) ||
        (e.requested_by ?? '').toLowerCase().includes(q) ||
        (e.approved_by ?? '').toLowerCase().includes(q)
      );
    }
    if (expiry) {
      list = list.filter(e => {
        const d = daysUntil(e.expires_at);
        if (expiry === 'expired')   return d !== null && d < 0;
        if (expiry === 'today')     return d === 0;
        if (expiry === '7d')        return d !== null && d >= 0 && d <= 7;
        if (expiry === '30d')       return d !== null && d >= 0 && d <= 30;
        return true;
      });
    }
    return list;
  }, [allExceptions, dSearch, expiry]);

  const handleRefresh = useCallback(() => { refetch(); refetchStats(); }, [refetch, refetchStats]);
  const handleCreated = useCallback(() => { handleRefresh(); }, [handleRefresh]);
  const clearFilters  = () => { setSearch(''); setDSearch(''); setStatus(''); setCategory(''); setExpiry(''); setPage(1); };
  const hasFilters    = !!(dSearch || status || category || expiry);

  // Pending alert bar
  const pendingCount = stats.pending ?? 0;

  return (
    <div className="space-y-5">
      {showCreate && <CreateExceptionModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />}
      {reviewModal && (
        <ReviewModal exc={reviewModal.exc} action={reviewModal.action}
          onClose={() => setReviewModal(null)} onDone={handleRefresh} />
      )}
      {selected && (
        <ExceptionDrawer
          exc={selected}
          onClose={() => setSelected(null)}
          onReview={(e, a) => { setSelected(null); setReviewModal({ exc: e, action: a }); }}
          onRefresh={handleRefresh}
          canApprove={canApprove}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <ClipboardList size={16} className="text-yellow-400" />
            Security Exceptions Management
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {total.toLocaleString()} total · {pendingCount} pending review · {stats.approved ?? 0} active
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleRefresh}
            className="p-1.5 rounded-lg border border-white/10 text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition-colors">
            <Plus size={12} /> New Request
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <SummaryCards stats={stats} exceptions={allExceptions} />

      {/* Pending approval alert */}
      {canApprove && pendingCount > 0 && (
        <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle size={16} className="text-yellow-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-yellow-400">
              {pendingCount} exception{pendingCount > 1 ? 's' : ''} awaiting your approval
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Filter by "Pending" below to review and take action on open requests.
            </p>
          </div>
          <button onClick={() => setStatus('pending')}
            className="ml-auto shrink-0 px-3 py-1.5 text-[11px] bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 rounded-lg hover:bg-yellow-500/20 transition-colors font-medium">
            Review Now
          </button>
        </div>
      )}

      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search exceptions, IDs, owners…"
            className="w-full pl-7 pr-3 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/50" />
        </div>

        {/* Status filter */}
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {(['', 'pending', 'approved', 'rejected', 'expired'] as const).map(s => (
            <button key={s} onClick={() => { setStatus(s); setPage(1); }}
              className={clsx('px-3 py-1.5 text-[11px] font-medium capitalize transition-colors',
                status === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              {s || 'All'}
            </button>
          ))}
        </div>

        {/* Category filter */}
        <select value={category} onChange={e => { setCategory(e.target.value); setPage(1); }}
          className="bg-surface-2 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-foreground focus:outline-none min-w-[160px]">
          <option value="">All Categories</option>
          {EXCEPTION_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>

        {/* Expiration filter */}
        <select value={expiry} onChange={e => setExpiry(e.target.value)}
          className="bg-surface-2 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-foreground focus:outline-none">
          <option value="">All Expirations</option>
          <option value="today">Expiring Today</option>
          <option value="7d">Expiring ≤ 7 days</option>
          <option value="30d">Expiring ≤ 30 days</option>
          <option value="expired">Already Expired</option>
        </select>

        {hasFilters && (
          <button onClick={clearFilters}
            className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] text-muted-foreground hover:text-foreground border border-white/10 rounded-lg hover:bg-white/5 transition-colors">
            <X size={10} /> Clear
          </button>
        )}
      </div>

      {/* Table */}
      <ExceptionsTable
        exceptions={exceptions}
        loading={loading}
        total={dSearch || expiry ? exceptions.length : total}
        page={page}
        pages={pages}
        onPageChange={setPage}
        onSelect={setSelected}
        onReview={(e, a) => setReviewModal({ exc: e, action: a })}
        canApprove={canApprove}
      />
    </div>
  );
}
