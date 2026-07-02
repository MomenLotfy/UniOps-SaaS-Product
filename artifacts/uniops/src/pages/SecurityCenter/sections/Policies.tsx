import { useState, useCallback, useRef, useEffect, useMemo, memo } from 'react';
import {
  Shield, ShieldAlert, ShieldCheck, ShieldOff, AlertTriangle, CheckCircle2,
  Clock, Zap, Eye, Lock, Plus, RefreshCw, Loader2, Trash2, Download,
  Search, Filter, ChevronDown, X, BookOpen, BarChart3, GitBranch,
  Server, Cloud, Box, Code, FileText, Activity, History, Bell,
  Settings, ExternalLink, Copy, ChevronRight, Info, Layers,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Policy {
  id: string;
  name: string;
  description?: string;
  category: string;
  severity: string;
  status: string;
  enforcement: string;
  scope: Record<string, any>;
  rules: { key: string; description?: string; threshold?: number }[];
  exceptions_count: number;
  violations_count: number;
  created_by?: string;
  updated_by?: string;
  effective_date?: string;
  review_date?: string;
  frameworks: string[];
  tags: Record<string, any>;
  is_builtin: boolean;
  policy_type?: string;
  created_at: string;
  updated_at: string;
}

interface Violation {
  id: string;
  policy_id: string;
  entity_type: string;
  entity_id: string;
  entity_title?: string;
  rule_key: string;
  rule_description?: string;
  severity: string;
  enforcement_mode: string;
  was_blocked: boolean;
  is_suppressed: boolean;
  status: string;
  context: Record<string, any>;
  created_at: string;
}

interface Exception {
  id: string;
  policy_id?: string;
  title: string;
  justification: string;
  status: string;
  exception_type: string;
  requested_by: string;
  approved_by?: string;
  expires_at?: string;
  created_at: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SEV_STYLE: Record<string, string> = {
  critical: 'text-red-400 bg-red-500/10 border-red-500/25',
  high:     'text-orange-400 bg-orange-500/10 border-orange-500/25',
  medium:   'text-yellow-400 bg-yellow-500/10 border-yellow-500/25',
  low:      'text-green-400 bg-green-500/10 border-green-500/25',
};
const ENF_STYLE: Record<string, string> = {
  enforce:   'text-red-400 bg-red-500/10 border-red-500/20',
  audit:     'text-blue-400 bg-blue-500/10 border-blue-500/20',
  advisory:  'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
};
const STATUS_STYLE: Record<string, string> = {
  active:   'text-green-400',
  inactive: 'text-gray-400',
  draft:    'text-yellow-400',
};
const CATEGORY_ICON: Record<string, React.ReactNode> = {
  secrets:        <Lock size={10} />,
  dependencies:   <Box size={10} />,
  container:      <Box size={10} />,
  iam:            <Shield size={10} />,
  network:        <Cloud size={10} />,
  code_quality:   <Code size={10} />,
  compliance:     <FileText size={10} />,
  posture:        <BarChart3 size={10} />,
  risk:           <AlertTriangle size={10} />,
  kubernetes:     <Server size={10} />,
  cloud:          <Cloud size={10} />,
  custom:         <Settings size={10} />,
};
const CATEGORY_COLOR: Record<string, string> = {
  secrets:       'text-purple-400',
  dependencies:  'text-blue-400',
  container:     'text-cyan-400',
  iam:           'text-orange-400',
  network:       'text-teal-400',
  code_quality:  'text-green-400',
  compliance:    'text-indigo-400',
  posture:       'text-yellow-400',
  risk:          'text-red-400',
};
const BUILTIN_META: Record<string, { icon: string; desc: string }> = {
  no_secrets:                { icon: '🔑', desc: 'Block secrets, credentials, API keys in source code' },
  block_critical_cves:       { icon: '🛡️', desc: 'Block scans with critical-severity CVEs (CVSS ≥ 9)' },
  require_signed_images:     { icon: '✍️', desc: 'Flag unsigned container images (Cosign / Notary)' },
  require_mfa:               { icon: '📱', desc: 'Enforce MFA on all privileged IAM accounts' },
  require_private_repos:     { icon: '🔒', desc: 'Block public repositories from passing scans' },
  min_security_score:        { icon: '📊', desc: 'Repositories must maintain a minimum security score' },
  block_high_risk_repos:     { icon: '🚫', desc: 'Prevent deployment of high/critical risk repositories' },
  require_passing_compliance: { icon: '✅', desc: 'Require a minimum compliance score for active repos' },
};

const CATEGORIES = ['secrets','dependencies','container','iam','network','code_quality','compliance','posture','risk','kubernetes','cloud','custom'];
const SEVERITIES  = ['critical','high','medium','low'];
const STATUSES    = ['active','draft','inactive'];
const ENFORCEMENTS = ['enforce','audit','advisory'];
const ENGINES     = ['Custom Rules Engine','OPA','Kyverno','Trivy'];

function getEngine(p: Policy): string {
  return p.tags?.engine ?? (p.is_builtin ? 'Custom Rules Engine' : p.tags?.engine ?? 'Custom Rules Engine');
}
function fmt(ts?: string): string {
  if (!ts) return '—';
  const d = new Date(ts);
  const diff = Date.now() - d.getTime();
  if (diff < 60000)  return 'just now';
  if (diff < 3600000) return `${Math.floor(diff/60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff/3600000)}h ago`;
  if (diff < 604800000) return `${Math.floor(diff/86400000)}d ago`;
  return d.toLocaleDateString(undefined, { month:'short', day:'numeric', year:'numeric' });
}
function scopeLabel(scope: Record<string, any>): string {
  if (!scope || Object.keys(scope).length === 0) return 'All Resources';
  const parts: string[] = [];
  if (scope.repositories?.length) parts.push(`${scope.repositories.length} repo${scope.repositories.length > 1 ? 's' : ''}`);
  if (scope.clusters?.length)     parts.push(`${scope.clusters.length} cluster${scope.clusters.length > 1 ? 's' : ''}`);
  if (scope.cloud)                parts.push(scope.cloud);
  return parts.join(' · ') || 'Custom Scope';
}

// ─── Small reusable components ────────────────────────────────────────────────

const Skel = ({ className }: { className?: string }) =>
  <div className={clsx('animate-pulse rounded-lg bg-white/5', className)} />;

const SevBadge = memo(({ s }: { s: string }) => (
  <span className={clsx('inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase border', SEV_STYLE[s] ?? 'text-muted-foreground border-white/10')}>
    {s}
  </span>
));

const EnfBadge = memo(({ e }: { e: string }) => (
  <span className={clsx('inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold border', ENF_STYLE[e] ?? 'text-muted-foreground border-white/10')}>
    {e === 'enforce' ? <Zap size={9} /> : e === 'audit' ? <Eye size={9} /> : <Bell size={9} />}
    {e}
  </span>
));

const CatBadge = memo(({ c }: { c: string }) => (
  <span className={clsx('inline-flex items-center gap-1 text-[10px] capitalize', CATEGORY_COLOR[c] ?? 'text-muted-foreground')}>
    {CATEGORY_ICON[c]}
    {(c || '').replace(/_/g, ' ')}
  </span>
));

const StatusDot = memo(({ s }: { s: string }) => (
  <span className={clsx('flex items-center gap-1 text-[11px] capitalize', STATUS_STYLE[s] ?? 'text-muted-foreground')}>
    <span className={clsx('w-1.5 h-1.5 rounded-full', s === 'active' ? 'bg-green-400' : s === 'draft' ? 'bg-yellow-400' : 'bg-gray-500')} />
    {s}
  </span>
));

// ─── Enforcement toggle ───────────────────────────────────────────────────────

const EnfToggle = memo(({ policy, onDone }: { policy: Policy; onDone: () => void }) => {
  const [loading, setLoading] = useState(false);
  const cycle: Record<string, string> = { enforce: 'audit', audit: 'advisory', advisory: 'enforce' };
  const next = cycle[policy.enforcement] ?? 'audit';
  const handle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setLoading(true);
    try {
      await apiClient.patch(`/security-policies/${policy.id}/enforcement`, { enforcement: next });
      onDone();
    } finally { setLoading(false); }
  };
  return (
    <button onClick={handle} disabled={loading}
      title={`Switch to ${next}`}
      className={clsx('inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold border transition-all hover:opacity-80',
        ENF_STYLE[policy.enforcement] ?? 'text-muted-foreground border-white/10')}>
      {loading ? <Loader2 size={9} className="animate-spin" /> : (
        policy.enforcement === 'enforce' ? <Zap size={9} /> : policy.enforcement === 'audit' ? <Eye size={9} /> : <Bell size={9} />
      )}
      {policy.enforcement}
    </button>
  );
});

// ─── Summary Cards ────────────────────────────────────────────────────────────

const SummaryCards = memo(({ stats, violSum, excStats }: { stats: any; violSum: any; excStats: any }) => {
  const cards = [
    { label: 'Total Policies',         value: stats.total ?? 0,                      color: 'text-foreground',   icon: Shield },
    { label: 'Active Policies',        value: stats.active ?? 0,                     color: 'text-green-400',    icon: ShieldCheck },
    { label: 'Inactive / Draft',       value: (stats.inactive ?? 0) + (stats.draft ?? 0), color: 'text-gray-400', icon: ShieldOff },
    { label: 'Enforce Mode',           value: stats.by_enforcement?.enforce ?? 0,    color: 'text-red-400',      icon: ShieldAlert },
    { label: 'Open Violations',        value: violSum.open ?? 0,                     color: 'text-orange-400',   icon: AlertTriangle },
    { label: 'Scans Blocked',          value: violSum.blocked ?? 0,                  color: 'text-red-400',      icon: Lock },
    { label: 'Policy Exceptions',      value: excStats.total ?? 0,                   color: 'text-yellow-400',   icon: Clock },
    { label: 'Pending Approvals',      value: excStats.pending ?? 0,                 color: 'text-blue-400',     icon: Bell },
    { label: 'Violations This Week',   value: violSum.total ?? 0,                    color: 'text-purple-400',   icon: Activity },
  ];
  return (
    <div className="grid grid-cols-3 lg:grid-cols-9 gap-2">
      {cards.map(({ label, value, color, icon: Icon }) => (
        <div key={label} className="bg-surface-2 border border-white/5 rounded-xl p-3 flex flex-col gap-1.5">
          <div className={clsx('flex items-center gap-1.5', color)}>
            <Icon size={12} />
            <span className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground">{label}</span>
          </div>
          <p className={clsx('text-xl font-bold', color)}>{value.toLocaleString()}</p>
        </div>
      ))}
    </div>
  );
});

// ─── Policy Drawer ────────────────────────────────────────────────────────────

const PolicyDrawer = memo(({ policy, onClose, onUpdate }: {
  policy: Policy;
  onClose: () => void;
  onUpdate: () => void;
}) => {
  const [tab, setTab] = useState<'overview' | 'logic' | 'violations' | 'exceptions' | 'timeline'>('overview');
  const [deleting, setDeleting] = useState(false);

  const { data: violRaw } = useApi<any>(`/security-policies/violations?policy_id=${policy.id}&limit=50`);
  const { data: excRaw }  = useApi<any>(`/security-exceptions?policy_id=${policy.id}&page_size=20`);
  const violations = useMemo(() => Array.isArray(violRaw?.data ?? violRaw) ? (violRaw?.data ?? violRaw) : [], [violRaw]);
  const exceptions = useMemo(() => (excRaw?.data?.data ?? excRaw?.data ?? []), [excRaw]);

  const handleDelete = async () => {
    if (!confirm(`Delete policy "${policy.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    try { await apiClient.delete(`/security-policies/${policy.id}`); onClose(); onUpdate(); }
    finally { setDeleting(false); }
  };

  const TABS = [
    { id: 'overview',   label: 'Overview',   icon: Info },
    { id: 'logic',      label: 'Policy Logic', icon: Code },
    { id: 'violations', label: `Violations (${policy.violations_count})`, icon: AlertTriangle },
    { id: 'exceptions', label: `Exceptions (${policy.exceptions_count})`, icon: Clock },
    { id: 'timeline',   label: 'Timeline',   icon: History },
  ] as const;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-full max-w-2xl z-50 flex flex-col bg-surface-1 border-l border-white/8 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-start gap-3 p-5 border-b border-white/8 shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              {policy.is_builtin && (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-purple-500/15 text-purple-400 border border-purple-500/20 font-bold uppercase tracking-wider">
                  Built-in
                </span>
              )}
              <SevBadge s={policy.severity} />
              <EnfBadge e={policy.enforcement} />
            </div>
            <h2 className="text-base font-bold text-foreground truncate">{policy.name}</h2>
            {policy.description && (
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{policy.description}</p>
            )}
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {!policy.is_builtin && (
              <button onClick={handleDelete} disabled={deleting}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40">
                {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
              </button>
            )}
            <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors">
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Tab nav */}
        <div className="flex items-center gap-1 px-4 pt-3 pb-0 border-b border-white/8 shrink-0 overflow-x-auto">
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
              <div className="grid grid-cols-2 gap-3">
                {[
                  ['Category',    <CatBadge c={policy.category} />],
                  ['Status',      <StatusDot s={policy.status} />],
                  ['Engine',      <span className="text-xs text-foreground">{getEngine(policy)}</span>],
                  ['Enforcement', <EnfToggle policy={policy} onDone={onUpdate} />],
                  ['Violations',  <span className="text-xs font-bold text-orange-400">{policy.violations_count}</span>],
                  ['Exceptions',  <span className="text-xs font-bold text-yellow-400">{policy.exceptions_count}</span>],
                  ['Created',     <span className="text-xs text-muted-foreground">{fmt(policy.created_at)}</span>],
                  ['Updated',     <span className="text-xs text-muted-foreground">{fmt(policy.updated_at)}</span>],
                ].map(([label, val], i) => (
                  <div key={i} className="bg-surface-2 border border-white/5 rounded-xl p-3">
                    <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-1">{label as string}</p>
                    <div className="text-sm">{val as React.ReactNode}</div>
                  </div>
                ))}
              </div>

              {policy.frameworks.length > 0 && (
                <div className="bg-surface-2 border border-white/5 rounded-xl p-3">
                  <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-2">Compliance Frameworks</p>
                  <div className="flex flex-wrap gap-1.5">
                    {policy.frameworks.map(f => (
                      <span key={f} className="px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-400 text-[10px] font-medium">{f}</span>
                    ))}
                  </div>
                </div>
              )}

              <div className="bg-surface-2 border border-white/5 rounded-xl p-3">
                <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-2">Scope</p>
                <p className="text-xs text-foreground">{scopeLabel(policy.scope)}</p>
                {Object.keys(policy.scope).length > 0 && (
                  <pre className="mt-2 text-[10px] text-muted-foreground bg-black/20 rounded-lg p-2 overflow-x-auto">
                    {JSON.stringify(policy.scope, null, 2)}
                  </pre>
                )}
              </div>
            </>
          )}

          {/* Policy Logic */}
          {tab === 'logic' && (
            <>
              <div className="bg-surface-2 border border-white/5 rounded-xl p-4">
                <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-3">Rules ({policy.rules.length})</p>
                {policy.rules.length === 0 ? (
                  <p className="text-xs text-muted-foreground italic">No rules defined.</p>
                ) : (
                  <div className="space-y-2">
                    {policy.rules.map((r, i) => (
                      <div key={i} className="bg-black/20 border border-white/5 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-1">
                          <code className="text-xs font-mono text-blue-400">{r.key}</code>
                          {r.threshold !== undefined && (
                            <span className="text-[10px] px-1.5 py-0.5 bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 rounded">
                              threshold: {r.threshold}
                            </span>
                          )}
                        </div>
                        {r.description && <p className="text-[11px] text-muted-foreground">{r.description}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="bg-surface-2 border border-white/5 rounded-xl p-4">
                <p className="text-[9px] uppercase font-semibold tracking-wider text-muted-foreground mb-2">Raw Rule Definition</p>
                <pre className="text-[10px] font-mono text-muted-foreground bg-black/20 rounded-lg p-3 overflow-x-auto">
                  {JSON.stringify(policy.rules, null, 2)}
                </pre>
              </div>
            </>
          )}

          {/* Violations */}
          {tab === 'violations' && (
            violations.length === 0 ? (
              <div className="py-16 flex flex-col items-center gap-2">
                <CheckCircle2 size={32} className="text-green-400 opacity-40" />
                <p className="text-sm text-muted-foreground">No violations for this policy</p>
              </div>
            ) : (
              <div className="space-y-2">
                {violations.map((v: Violation) => (
                  <div key={v.id} className={clsx('bg-surface-2 border rounded-xl p-3', v.was_blocked ? 'border-red-500/20' : 'border-white/5')}>
                    <div className="flex items-start gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <SevBadge s={v.severity} />
                          <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border', ENF_STYLE[v.enforcement_mode] ?? 'border-white/10 text-muted-foreground')}>
                            {v.enforcement_mode}
                          </span>
                          {v.was_blocked && <span className="text-[10px] text-red-400 font-bold">BLOCKED</span>}
                        </div>
                        <p className="text-xs font-medium text-foreground truncate">{v.entity_title || v.entity_id}</p>
                        <p className="text-[11px] text-muted-foreground">{v.entity_type} · {v.rule_key}</p>
                        {v.rule_description && <p className="text-[10px] text-muted-foreground/70 mt-0.5">{v.rule_description}</p>}
                      </div>
                      <span className="text-[10px] text-muted-foreground shrink-0">{fmt(v.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )
          )}

          {/* Exceptions */}
          {tab === 'exceptions' && (
            exceptions.length === 0 ? (
              <div className="py-16 flex flex-col items-center gap-2">
                <CheckCircle2 size={32} className="text-green-400 opacity-40" />
                <p className="text-sm text-muted-foreground">No exceptions for this policy</p>
              </div>
            ) : (
              <div className="space-y-2">
                {exceptions.map((e: Exception) => (
                  <div key={e.id} className="bg-surface-2 border border-white/5 rounded-xl p-3">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <p className="text-xs font-medium text-foreground">{e.title}</p>
                      <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border shrink-0',
                        e.status === 'approved' ? 'text-green-400 border-green-500/20 bg-green-500/10'
                        : e.status === 'pending' ? 'text-yellow-400 border-yellow-500/20 bg-yellow-500/10'
                        : 'text-red-400 border-red-500/20 bg-red-500/10')}>
                        {e.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-muted-foreground">{e.justification}</p>
                    <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted-foreground/60">
                      <span>{e.exception_type}</span>
                      {e.expires_at && <span>Expires {fmt(e.expires_at)}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )
          )}

          {/* Timeline */}
          {tab === 'timeline' && (
            <div className="space-y-0">
              {[
                { ts: policy.created_at, label: 'Policy created', icon: Plus, color: 'text-green-400' },
                ...(policy.updated_at !== policy.created_at ? [{ ts: policy.updated_at, label: 'Policy updated', icon: Settings, color: 'text-blue-400' }] : []),
                ...(policy.violations_count > 0 ? [{ ts: null, label: `${policy.violations_count} total violations recorded`, icon: AlertTriangle, color: 'text-orange-400' }] : []),
                ...(policy.exceptions_count > 0 ? [{ ts: null, label: `${policy.exceptions_count} exceptions filed`, icon: Clock, color: 'text-yellow-400' }] : []),
              ].map((ev, i) => (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <div className={clsx('w-6 h-6 rounded-full bg-surface-2 border border-white/10 flex items-center justify-center shrink-0', ev.color)}>
                      <ev.icon size={10} />
                    </div>
                    <div className="w-px flex-1 bg-white/8 my-1" />
                  </div>
                  <div className="pb-4 pt-0.5">
                    <p className="text-xs text-foreground">{ev.label}</p>
                    {ev.ts && <p className="text-[10px] text-muted-foreground">{fmt(ev.ts)}</p>}
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

// ─── Violations View ──────────────────────────────────────────────────────────

const ViolationsView = memo(() => {
  const [status, setStatus] = useState('open');
  const [entityType, setEntityType] = useState('');
  const qs = new URLSearchParams({ limit: '100', offset: '0' });
  if (status)     qs.set('status', status);
  if (entityType) qs.set('entity_type', entityType);
  const { data: raw, loading } = useApi<any>(`/security-policies/violations?${qs}`);
  const violations: Violation[] = useMemo(() => Array.isArray(raw?.data ?? raw) ? (raw?.data ?? raw) : [], [raw]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {['', 'open', 'resolved', 'suppressed'].map(s => (
            <button key={s} onClick={() => setStatus(s)}
              className={clsx('px-3 py-1.5 text-[11px] font-medium capitalize transition-colors',
                status === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              {s || 'All'}
            </button>
          ))}
        </div>
        <select value={entityType} onChange={e => setEntityType(e.target.value)}
          className="bg-surface-2 border border-white/10 rounded-lg px-2.5 py-1.5 text-[11px] text-foreground focus:outline-none">
          <option value="">All Entity Types</option>
          {['threat','vulnerability','repository','asset','tenant'].map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skel key={i} className="h-16" />)}</div>
      ) : violations.length === 0 ? (
        <div className="py-20 flex flex-col items-center gap-2">
          <CheckCircle2 size={40} className="text-green-400 opacity-30" />
          <p className="text-sm text-muted-foreground">No violations — all policies passing</p>
        </div>
      ) : (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-surface-1/30">
                {['Resource', 'Policy', 'Rule', 'Severity', 'Mode', 'Blocked', 'Status', 'Detected'].map(h => (
                  <th key={h} className="px-3 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {violations.map(v => (
                <tr key={v.id} className={clsx('border-b border-white/4 hover:bg-white/3 transition-colors', v.was_blocked && 'bg-red-500/5')}>
                  <td className="px-3 py-2.5 max-w-[160px]">
                    <p className="truncate text-foreground font-medium">{v.entity_title || v.entity_id}</p>
                    <p className="text-[10px] text-muted-foreground capitalize">{v.entity_type}</p>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground max-w-[120px]">
                    <p className="truncate">{v.context?.policy_name || '—'}</p>
                  </td>
                  <td className="px-3 py-2.5">
                    <code className="text-[10px] text-blue-400">{v.rule_key}</code>
                  </td>
                  <td className="px-3 py-2.5"><SevBadge s={v.severity} /></td>
                  <td className="px-3 py-2.5"><EnfBadge e={v.enforcement_mode} /></td>
                  <td className="px-3 py-2.5">
                    {v.was_blocked
                      ? <span className="text-red-400 font-bold text-[10px]">YES</span>
                      : <span className="text-muted-foreground/40 text-[10px]">—</span>}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={clsx('text-[10px] capitalize', v.status === 'open' ? 'text-orange-400' : v.status === 'resolved' ? 'text-green-400' : 'text-muted-foreground')}>
                      {v.status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">{fmt(v.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
});

// ─── Exceptions View ──────────────────────────────────────────────────────────

const ExceptionsView = memo(() => {
  const [status, setStatus] = useState('');
  const qs = new URLSearchParams({ page: '1', page_size: '50' });
  if (status) qs.set('status', status);
  const { data: raw, loading } = useApi<any>(`/security-exceptions?${qs}`);
  const exceptions: Exception[] = useMemo(() => (raw?.data?.data ?? raw?.data ?? []), [raw]);
  const total = raw?.data?.total ?? raw?.total ?? 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground flex-1">{total.toLocaleString()} exception{total !== 1 ? 's' : ''}</span>
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {['', 'pending', 'approved', 'rejected'].map(s => (
            <button key={s} onClick={() => setStatus(s)}
              className={clsx('px-3 py-1.5 text-[11px] font-medium capitalize transition-colors',
                status === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              {s || 'All'}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skel key={i} className="h-20" />)}</div>
      ) : exceptions.length === 0 ? (
        <div className="py-20 flex flex-col items-center gap-2">
          <CheckCircle2 size={40} className="text-green-400 opacity-30" />
          <p className="text-sm text-muted-foreground">No exceptions found</p>
        </div>
      ) : (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-surface-1/30">
                {['Exception', 'Type', 'Reason', 'Expiration', 'Approved By', 'Status', 'Filed'].map(h => (
                  <th key={h} className="px-3 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {exceptions.map(ex => (
                <tr key={ex.id} className="border-b border-white/4 hover:bg-white/3 transition-colors">
                  <td className="px-3 py-2.5 max-w-[160px]">
                    <p className="truncate font-medium text-foreground">{ex.title}</p>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground capitalize">{ex.exception_type}</td>
                  <td className="px-3 py-2.5 max-w-[200px]">
                    <p className="truncate text-muted-foreground">{ex.justification}</p>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">{ex.expires_at ? fmt(ex.expires_at) : '—'}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{ex.approved_by ? ex.approved_by.slice(0, 8) + '…' : '—'}</td>
                  <td className="px-3 py-2.5">
                    <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border capitalize',
                      ex.status === 'approved' ? 'text-green-400 border-green-500/20 bg-green-500/10'
                      : ex.status === 'pending' ? 'text-yellow-400 border-yellow-500/20 bg-yellow-500/10'
                      : 'text-red-400 border-red-500/20 bg-red-500/10')}>
                      {ex.status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">{fmt(ex.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
});

// ─── Templates View ───────────────────────────────────────────────────────────

const TemplatesView = memo(({ onSeed, seeding }: { onSeed: () => void; seeding: boolean }) => (
  <div className="space-y-4">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-semibold text-foreground">Built-in Policy Templates</p>
        <p className="text-xs text-muted-foreground mt-0.5">{Object.keys(BUILTIN_META).length} production-ready policies covering key security domains.</p>
      </div>
      <button onClick={onSeed} disabled={seeding}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors disabled:opacity-50">
        {seeding ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
        {seeding ? 'Seeding…' : 'Load All Built-ins'}
      </button>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {Object.entries(BUILTIN_META).map(([key, { icon, desc }]) => (
        <div key={key} className="bg-surface-2 border border-white/5 hover:border-purple-500/20 rounded-xl p-4 transition-colors">
          <div className="flex items-start gap-3">
            <span className="text-2xl shrink-0">{icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <p className="text-sm font-semibold text-foreground capitalize">{key.replace(/_/g, ' ')}</p>
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-purple-500/15 text-purple-400 border border-purple-500/20 font-bold uppercase">Built-in</span>
              </div>
              <p className="text-xs text-muted-foreground">{desc}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
));

// ─── Create Policy Modal ──────────────────────────────────────────────────────

const CreatePolicyModal = memo(({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) => {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '', category: 'secrets', severity: 'high',
    enforcement: 'audit', description: '', engine: 'Custom Rules Engine',
    frameworks: '',
  });

  const handle = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const fw = form.frameworks.split(',').map(s => s.trim()).filter(Boolean);
      await apiClient.post('/security-policies', {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        category: form.category,
        severity: form.severity,
        enforcement: form.enforcement,
        status: 'active',
        frameworks: fw,
        tags: { engine: form.engine },
        scope: {}, rules: [],
      });
      onCreated(); onClose();
    } finally { setSaving(false); }
  };

  const sel = (label: string, key: keyof typeof form, opts: string[]) => (
    <div>
      <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">{label}</label>
      <select value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        className="w-full px-2.5 py-2 text-xs rounded-lg border border-white/10 bg-surface-2 text-foreground focus:outline-none focus:border-blue-500/50 capitalize">
        {opts.map(o => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
      </select>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg mx-4 bg-surface-1 border border-white/8 rounded-xl p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2"><Plus size={14} /> Create Security Policy</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X size={14} /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Policy Name *</label>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border border-white/10 bg-surface-2 text-foreground focus:outline-none focus:border-blue-500/50"
              placeholder="e.g. No Public S3 Buckets" />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Description</label>
            <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border border-white/10 bg-surface-2 text-foreground focus:outline-none focus:border-blue-500/50 resize-none"
              rows={2} placeholder="What does this policy enforce?" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            {sel('Category', 'category', CATEGORIES)}
            {sel('Severity', 'severity', SEVERITIES)}
            {sel('Enforcement Mode', 'enforcement', ENFORCEMENTS)}
            {sel('Engine', 'engine', ENGINES)}
          </div>
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Compliance Frameworks</label>
            <input value={form.frameworks} onChange={e => setForm(f => ({ ...f, frameworks: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border border-white/10 bg-surface-2 text-foreground focus:outline-none focus:border-blue-500/50"
              placeholder="SOC2, PCI-DSS, NIST (comma separated)" />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-lg border border-white/10 text-muted-foreground hover:text-foreground transition-colors">Cancel</button>
          <button onClick={handle} disabled={saving || !form.name.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition-colors disabled:opacity-50">
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            {saving ? 'Creating…' : 'Create Policy'}
          </button>
        </div>
      </div>
    </div>
  );
});

// ─── Policies Table ───────────────────────────────────────────────────────────

const PoliciesTable = memo(({ policies, loading, total, page, pages, onPageChange, onSelect, onUpdate, canWrite }: {
  policies: Policy[];
  loading: boolean;
  total: number;
  page: number;
  pages: number;
  onPageChange: (p: number) => void;
  onSelect: (p: Policy) => void;
  onUpdate: () => void;
  canWrite: boolean;
}) => {
  const [deleting, setDeleting] = useState<string | null>(null);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setDeleting(id);
    try { await apiClient.delete(`/security-policies/${id}`); onUpdate(); }
    finally { setDeleting(null); }
  };

  if (loading && policies.length === 0) {
    return <div className="space-y-1.5">{Array.from({ length: 8 }).map((_, i) => <Skel key={i} className="h-12" />)}</div>;
  }
  if (policies.length === 0) {
    return (
      <div className="py-20 flex flex-col items-center gap-3">
        <BookOpen size={40} className="text-muted-foreground opacity-25" />
        <p className="text-sm font-medium text-foreground">No policies match your filters</p>
        <p className="text-xs text-muted-foreground">Adjust filters or create your first policy.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{total.toLocaleString()} polic{total === 1 ? 'y' : 'ies'}</span>
      </div>
      <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/8 bg-surface-1/30">
              {['Policy Name', 'Category', 'Engine', 'Severity', 'Scope', 'Status', 'Violations', 'Mode', 'Frameworks', 'Last Updated', ''].map(h => (
                <th key={h} className="px-3 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {policies.map(p => (
              <tr key={p.id}
                onClick={() => onSelect(p)}
                className="border-b border-white/4 hover:bg-white/3 transition-colors cursor-pointer group">
                <td className="px-3 py-3 max-w-[200px]">
                  <div className="flex items-center gap-1.5">
                    {p.is_builtin && (
                      <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-purple-400" title="Built-in" />
                    )}
                    <p className="font-medium text-foreground truncate">{p.name}</p>
                  </div>
                </td>
                <td className="px-3 py-3"><CatBadge c={p.category} /></td>
                <td className="px-3 py-3 text-muted-foreground">{getEngine(p)}</td>
                <td className="px-3 py-3"><SevBadge s={p.severity} /></td>
                <td className="px-3 py-3 text-muted-foreground max-w-[120px]">
                  <p className="truncate">{scopeLabel(p.scope)}</p>
                </td>
                <td className="px-3 py-3"><StatusDot s={p.status} /></td>
                <td className="px-3 py-3">
                  {p.violations_count > 0
                    ? <span className="text-orange-400 font-bold">{p.violations_count}</span>
                    : <span className="text-green-400 text-[10px]">✓ 0</span>}
                </td>
                <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                  <EnfToggle policy={p} onDone={onUpdate} />
                </td>
                <td className="px-3 py-3">
                  <div className="flex flex-wrap gap-1">
                    {p.frameworks.slice(0, 2).map(f => (
                      <span key={f} className="px-1 py-0.5 rounded bg-indigo-500/10 text-indigo-400 text-[9px]">{f}</span>
                    ))}
                    {p.frameworks.length > 2 && (
                      <span className="text-[9px] text-muted-foreground">+{p.frameworks.length - 2}</span>
                    )}
                  </div>
                </td>
                <td className="px-3 py-3 text-muted-foreground whitespace-nowrap">{fmt(p.updated_at)}</td>
                <td className="px-3 py-3">
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={e => { e.stopPropagation(); onSelect(p); }}
                      className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors" title="View details">
                      <ChevronRight size={12} />
                    </button>
                    {canWrite && !p.is_builtin && (
                      <button onClick={e => handleDelete(e, p.id)} disabled={deleting === p.id}
                        className="p-1 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40" title="Delete">
                        {deleting === p.id ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
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

// ─── Main Component ───────────────────────────────────────────────────────────

const MAIN_TABS = [
  { id: 'policies',    label: 'Policies',          icon: Shield },
  { id: 'violations',  label: 'Violations',         icon: AlertTriangle },
  { id: 'exceptions',  label: 'Exceptions',         icon: Clock },
  { id: 'templates',   label: 'Built-in Templates', icon: BookOpen },
] as const;

export default function PoliciesSection() {
  const { role }  = usePermissions();
  const canWrite  = canWriteSecurity(role);

  const [tab, setTab]           = useState<'policies' | 'violations' | 'exceptions' | 'templates'>('policies');
  const [search, setSearch]     = useState('');
  const [dSearch, setDSearch]   = useState('');
  const [category, setCategory] = useState('');
  const [severity, setSeverity] = useState('');
  const [status, setStatus]     = useState('active');
  const [enforcement, setEnf]   = useState('');
  const [page, setPage]         = useState(1);
  const [selected, setSelected] = useState<Policy | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [seeding, setSeeding]   = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { setDSearch(search); setPage(1); }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  const qs = useMemo(() => {
    const p: Record<string, string> = { page: String(page), page_size: '25' };
    if (dSearch)    p.search = dSearch;
    if (category)   p.category = category;
    if (severity)   p.severity = severity;
    if (status)     p.status = status;
    if (enforcement) p.enforcement = enforcement;
    return new URLSearchParams(p).toString();
  }, [page, dSearch, category, severity, status, enforcement]);

  const { data: rawPolicies, loading, refetch } = useApi<any>(`/security-policies?${qs}`);
  const { data: statsRaw,    refetch: refetchStats } = useApi<any>('/security-policies/stats');
  const { data: violSumRaw } = useApi<any>('/security-policies/violations/summary');
  const { data: excStatsRaw } = useApi<any>('/security-exceptions/stats');

  const result    = rawPolicies?.data ?? rawPolicies;
  const policies: Policy[] = useMemo(() => result?.data ?? [], [result]);
  const total     = result?.total ?? 0;
  const pages     = result?.pages ?? 1;
  const stats     = statsRaw?.data ?? statsRaw ?? {};
  const violSum   = violSumRaw?.data ?? violSumRaw ?? {};
  const excStats  = excStatsRaw?.data ?? excStatsRaw ?? {};

  const handleRefresh = useCallback(() => { refetch(); refetchStats(); }, [refetch, refetchStats]);
  const handleCreated = useCallback(() => { refetch(); refetchStats(); }, [refetch, refetchStats]);

  const handleSeed = useCallback(async () => {
    setSeeding(true);
    try { await apiClient.post('/security-policies/seed-defaults'); await refetch(); refetchStats(); }
    finally { setSeeding(false); }
  }, [refetch, refetchStats]);

  const clearFilters = () => { setSearch(''); setDSearch(''); setCategory(''); setSeverity(''); setStatus('active'); setEnf(''); setPage(1); };
  const hasFilters = !!(dSearch || category || severity || (status && status !== 'active') || enforcement);

  return (
    <div className="space-y-5">
      {showCreate && <CreatePolicyModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />}
      {selected && (
        <PolicyDrawer
          policy={selected}
          onClose={() => setSelected(null)}
          onUpdate={() => { setSelected(null); handleRefresh(); }}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Shield size={16} className="text-blue-400" />
            Security Policy Management Center
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {stats.total ?? 0} policies · {stats.active ?? 0} active · {violSum.open ?? 0} open violations
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={handleRefresh}
            className="p-1.5 rounded-lg border border-white/10 text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>
          {canWrite && (
            <>
              <button onClick={handleSeed} disabled={seeding}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors disabled:opacity-50">
                {seeding ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                Load Built-ins
              </button>
              <button onClick={() => setShowCreate(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition-colors">
                <Plus size={12} /> New Policy
              </button>
            </>
          )}
        </div>
      </div>

      {/* Summary cards */}
      <SummaryCards stats={stats} violSum={violSum} excStats={excStats} />

      {/* Tabs */}
      <div className="flex items-center gap-1 p-1 bg-surface-2 rounded-xl border border-white/5 w-fit overflow-x-auto">
        {MAIN_TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={clsx('flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-lg transition-all whitespace-nowrap',
              tab === t.id ? 'bg-surface-1 text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
            <t.icon size={11} />
            {t.label}
          </button>
        ))}
      </div>

      {/* Policies tab */}
      {tab === 'policies' && (
        <>
          {/* Filter bar */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[200px] max-w-xs">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search policies, rules, frameworks…"
                className="w-full pl-7 pr-3 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/50"
              />
            </div>
            <select value={category} onChange={e => { setCategory(e.target.value); setPage(1); }}
              className="bg-surface-2 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-foreground focus:outline-none capitalize min-w-[120px]">
              <option value="">All Categories</option>
              {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
            </select>
            <select value={severity} onChange={e => { setSeverity(e.target.value); setPage(1); }}
              className="bg-surface-2 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-foreground focus:outline-none capitalize">
              <option value="">All Severities</option>
              {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
              className="bg-surface-2 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-foreground focus:outline-none capitalize">
              <option value="">All Statuses</option>
              {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={enforcement} onChange={e => { setEnf(e.target.value); setPage(1); }}
              className="bg-surface-2 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-foreground focus:outline-none capitalize">
              <option value="">All Modes</option>
              {ENFORCEMENTS.map(e => <option key={e} value={e}>{e}</option>)}
            </select>
            {hasFilters && (
              <button onClick={clearFilters} className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] text-muted-foreground hover:text-foreground border border-white/10 rounded-lg hover:bg-white/5 transition-colors">
                <X size={10} /> Clear
              </button>
            )}
          </div>

          <PoliciesTable
            policies={policies}
            loading={loading}
            total={total}
            page={page}
            pages={pages}
            onPageChange={setPage}
            onSelect={setSelected}
            onUpdate={handleRefresh}
            canWrite={canWrite}
          />
        </>
      )}

      {tab === 'violations'  && <ViolationsView />}
      {tab === 'exceptions'  && <ExceptionsView />}
      {tab === 'templates'   && <TemplatesView onSeed={handleSeed} seeding={seeding} />}
    </div>
  );
}
