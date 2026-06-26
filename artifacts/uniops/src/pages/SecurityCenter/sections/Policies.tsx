import { useState } from 'react';
import {
  BookOpen, Plus, RefreshCw, Loader2, Trash2, Shield,
  AlertTriangle, CheckCircle2, Clock, ToggleLeft, ToggleRight,
  ChevronDown, ChevronRight, Zap, Lock, Eye, Download,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

/* ── colour helpers ──────────────────────────────────────────────────── */
const ENFORCEMENT_COLOR: Record<string, string> = {
  enforce:   'text-red-400 bg-red-500/10 border-red-500/20',
  audit:     'text-blue-400 bg-blue-500/10 border-blue-500/20',
  advisory:  'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  mandatory: 'text-red-400 bg-red-500/10 border-red-500/20',
};
const SEV_COLOR: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-green-400',
};
const STATUS_COLOR: Record<string, string> = {
  active:   'text-green-400',
  inactive: 'text-gray-400',
  draft:    'text-yellow-400',
};

/* ── Built-in policy descriptions ───────────────────────────────────── */
const BUILTIN_META: Record<string, { icon: string; desc: string }> = {
  no_secrets:             { icon: '🔑', desc: 'Block secrets, credentials, API keys in source code' },
  block_critical_cves:    { icon: '🛡️', desc: 'Block scans with critical-severity CVEs (CVSS ≥ 9)' },
  require_signed_images:  { icon: '✍️', desc: 'Flag unsigned container images (Cosign / Notary)' },
  require_mfa:            { icon: '📱', desc: 'Enforce MFA on all privileged IAM accounts' },
  require_private_repos:  { icon: '🔒', desc: 'Block public repositories from passing scans' },
};

const RULE_LABELS: Record<string, string> = {
  no_secrets:            'No Secrets',
  block_critical_cves:   'Block Critical CVEs',
  require_signed_images: 'Require Signed Images',
  require_mfa:           'Require MFA',
  require_private_repos: 'Require Private Repos',
};

/* ── Create modal ────────────────────────────────────────────────────── */
function CreatePolicyModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '', category: 'secrets', severity: 'high',
    enforcement: 'audit', description: '',
  });
  const handle = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await apiClient.post('/security-policies', { ...form, status: 'active' });
      onCreated(); onClose();
    } finally { setSaving(false); }
  };
  const field = (label: string, key: string, opts: string[]) => (
    <div key={key}>
      <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">{label}</label>
      <select value={(form as any)[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        className="w-full px-2 py-1.5 text-xs rounded-lg border outline-none capitalize"
        style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}>
        {opts.map(o => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
      </select>
    </div>
  );
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md mx-4 rounded-xl border p-5 shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <h3 className="text-sm font-semibold text-foreground mb-4">Create Security Policy</h3>
        <div className="space-y-3">
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Name *</label>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              placeholder="Policy name" />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Description</label>
            <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 resize-none"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              rows={2} placeholder="What does this policy enforce?" />
          </div>
          <div className="grid grid-cols-3 gap-2">
            {field('Category', 'category', ['secrets','dependencies','container','iam','network','code_quality','compliance'])}
            {field('Severity', 'severity', ['critical','high','medium','low'])}
            {field('Mode', 'enforcement', ['enforce','audit','advisory'])}
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>Cancel</button>
          <button onClick={handle} disabled={saving || !form.name.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors disabled:opacity-50">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
            {saving ? 'Creating…' : 'Create Policy'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Enforcement toggle pill ─────────────────────────────────────────── */
function EnforcementPill({ policy, onToggle }: { policy: any; onToggle: () => void }) {
  const [loading, setLoading] = useState(false);
  const next = policy.enforcement === 'enforce' ? 'audit' : 'enforce';
  const handle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setLoading(true);
    try {
      await apiClient.patch(`/security-policies/${policy.id}/enforcement`, { enforcement: next });
      onToggle();
    } finally { setLoading(false); }
  };
  const isEnforce = policy.enforcement === 'enforce';
  return (
    <button onClick={handle} disabled={loading}
      className={clsx(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border transition-all',
        isEnforce ? 'text-red-400 bg-red-500/10 border-red-500/20 hover:bg-red-500/20'
                  : 'text-blue-400 bg-blue-500/10 border-blue-500/20 hover:bg-blue-500/20',
      )}>
      {loading ? <Loader2 className="w-2.5 h-2.5 animate-spin" />
        : isEnforce ? <Zap className="w-2.5 h-2.5" /> : <Eye className="w-2.5 h-2.5" />}
      {isEnforce ? 'Enforce' : 'Audit'}
    </button>
  );
}

/* ── Main component ──────────────────────────────────────────────────── */
export default function Policies() {
  const { role }    = usePermissions();
  const canWrite    = canWriteSecurity(role);

  const [tab, setTab]             = useState<'policies' | 'violations' | 'templates'>('policies');
  const [enforcement, setEnforcement] = useState('');
  const [status, setStatus]       = useState('active');
  const [page, setPage]           = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [deleting, setDeleting]   = useState<string | null>(null);
  const [seeding, setSeeding]     = useState(false);

  /* data */
  const qs = new URLSearchParams({ page: String(page), page_size: '20' });
  if (enforcement) qs.set('enforcement', enforcement);
  if (status)      qs.set('status', status);

  const { data: raw,  loading, refetch }     = useApi<any>(`/security-policies?${qs}`);
  const { data: statsRaw }                   = useApi<any>('/security-policies/stats');
  const { data: violSumRaw, refetch: refetchViol } = useApi<any>('/security-policies/violations/summary');
  const { data: violRaw, loading: violLoad } = useApi<any>('/security-policies/violations?limit=50&status=open');

  const result     = raw?.data ?? raw;
  const policies   = result?.data ?? [];
  const total      = result?.total ?? 0;
  const pages      = result?.pages ?? 1;
  const stats      = statsRaw?.data ?? statsRaw ?? {};
  const violSum    = violSumRaw?.data ?? violSumRaw ?? {};
  const violations = Array.isArray(violRaw?.data ?? violRaw) ? (violRaw?.data ?? violRaw) : [];

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try { await apiClient.delete(`/security-policies/${id}`); refetch(); }
    finally { setDeleting(null); }
  };

  const handleSeedDefaults = async () => {
    setSeeding(true);
    try {
      await apiClient.post('/security-policies/seed-defaults');
      await refetch();
    } finally { setSeeding(false); }
  };

  /* ── render ── */
  return (
    <div className="space-y-4">
      {showCreate && <CreatePolicyModal onClose={() => setShowCreate(false)} onCreated={refetch} />}

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Policy Engine</h1>
          <p className="text-xs text-muted-foreground">
            {total} policies · {stats.active ?? 0} active · {violSum.open ?? 0} open violations
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { refetch(); refetchViol(); }}
            className="p-1.5 rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          {canWrite && (
            <>
              <button onClick={handleSeedDefaults} disabled={seeding}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors disabled:opacity-50">
                {seeding ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                Load Built-ins
              </button>
              <button onClick={() => setShowCreate(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors">
                <Plus className="w-3 h-3" /> New Policy
              </button>
            </>
          )}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Enforce Mode',  value: stats.by_enforcement?.enforce ?? 0,  color: 'text-red-400',    icon: <Zap className="w-3.5 h-3.5" /> },
          { label: 'Audit Mode',    value: stats.by_enforcement?.audit ?? 0,    color: 'text-blue-400',   icon: <Eye className="w-3.5 h-3.5" /> },
          { label: 'Open Violations',value: violSum.open ?? 0,                  color: 'text-orange-400', icon: <AlertTriangle className="w-3.5 h-3.5" /> },
          { label: 'Scans Blocked', value: violSum.blocked ?? 0,               color: 'text-red-400',    icon: <Lock className="w-3.5 h-3.5" /> },
        ].map(({ label, value, color, icon }) => (
          <div key={label} className="card-base p-4 flex items-center gap-3">
            <span className={clsx('w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center', color)}>{icon}</span>
            <div>
              <p className={clsx('text-xl font-bold', color)}>{value}</p>
              <p className="text-[10px] text-muted-foreground">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Violations by rule */}
      {violSum.by_rule && Object.keys(violSum.by_rule).length > 0 && (
        <div className="card-base p-4">
          <p className="text-xs font-semibold text-foreground mb-3">Violations by Rule</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(violSum.by_rule).map(([rule, count]) => (
              <div key={rule} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10">
                <span className="text-[10px] text-muted-foreground">{RULE_LABELS[rule] || rule}</span>
                <span className="text-xs font-bold text-orange-400">{count as number}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-0 rounded-lg border border-white/10 overflow-hidden w-fit">
        {([['policies', 'Policies'], ['violations', 'Violations'], ['templates', 'Built-in Templates']] as const).map(([v, label]) => (
          <button key={v} onClick={() => setTab(v)}
            className={clsx('px-4 py-2 text-xs font-medium transition-colors',
              tab === v ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
            {label}
          </button>
        ))}
      </div>

      {/* ── Policies tab ── */}
      {tab === 'policies' && (
        <>
          <div className="flex gap-2 flex-wrap">
            <div className="flex rounded-lg border border-white/10 overflow-hidden">
              {['', 'enforce', 'audit', 'advisory'].map(e => (
                <button key={e} onClick={() => { setEnforcement(e); setPage(1); }}
                  className={clsx('px-3 py-1.5 text-[11px] font-medium capitalize transition-colors',
                    enforcement === e ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
                  {e || 'All Modes'}
                </button>
              ))}
            </div>
            <div className="flex rounded-lg border border-white/10 overflow-hidden">
              {['active', 'draft', 'inactive', ''].map(s => (
                <button key={s} onClick={() => { setStatus(s); setPage(1); }}
                  className={clsx('px-3 py-1.5 text-[11px] font-medium capitalize transition-colors',
                    status === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
                  {s || 'All Status'}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            {loading ? [...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />) :
              policies.length === 0 ? (
                <div className="card-base py-14 text-center">
                  <BookOpen className="w-8 h-8 text-muted-foreground opacity-30 mx-auto mb-2" />
                  <p className="text-sm font-medium text-foreground mb-1">No policies yet</p>
                  <p className="text-xs text-muted-foreground mb-3">Start with built-in templates or create your own.</p>
                  {canWrite && (
                    <button onClick={handleSeedDefaults} disabled={seeding}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium transition-colors disabled:opacity-50 mx-auto">
                      {seeding ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                      Load 5 Built-in Policies
                    </button>
                  )}
                </div>
              ) : policies.map((p: any) => (
                <div key={p.id} className={clsx('card-base p-4 transition-colors',
                  p.is_builtin && 'border-l-2 border-purple-500/40')}>
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        {p.is_builtin && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-purple-500/15 text-purple-400 border border-purple-500/20 font-bold uppercase tracking-wider">
                            Built-in
                          </span>
                        )}
                        <p className="text-sm font-semibold text-foreground">{p.name}</p>
                        <EnforcementPill policy={p} onToggle={refetch} />
                        <span className={clsx('text-[10px] font-medium capitalize', STATUS_COLOR[p.status] ?? 'text-muted-foreground')}>
                          {p.status}
                        </span>
                      </div>
                      {p.description && <p className="text-xs text-muted-foreground mb-1">{p.description}</p>}
                      <div className="flex items-center gap-3 text-[10px] text-muted-foreground flex-wrap">
                        <span className="capitalize">{(p.category || '').replace(/_/g, ' ')}</span>
                        <span>·</span>
                        <span className={clsx('capitalize font-medium', SEV_COLOR[p.severity] ?? 'text-foreground')}>{p.severity}</span>
                        {p.violations_count > 0 && <>
                          <span>·</span>
                          <span className="text-orange-400">{p.violations_count} violations</span>
                        </>}
                        {p.exceptions_count > 0 && <>
                          <span>·</span>
                          <span className="text-yellow-400">{p.exceptions_count} exceptions</span>
                        </>}
                        {p.frameworks?.length > 0 && <>
                          <span>·</span>
                          <span>{p.frameworks.join(', ')}</span>
                        </>}
                      </div>
                    </div>
                    {canWrite && !p.is_builtin && (
                      <button onClick={() => handleDelete(p.id)} disabled={deleting === p.id}
                        className="text-muted-foreground hover:text-red-400 transition-colors disabled:opacity-40 flex-shrink-0">
                        {deleting === p.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                      </button>
                    )}
                  </div>
                </div>
              ))
            }
          </div>
          {pages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-muted-foreground">Page {page} of {pages}</span>
              <div className="flex gap-1">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="px-2 py-1 rounded text-xs text-muted-foreground hover:text-foreground disabled:opacity-30">Prev</button>
                <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                  className="px-2 py-1 rounded text-xs text-muted-foreground hover:text-foreground disabled:opacity-30">Next</button>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Violations tab ── */}
      {tab === 'violations' && (
        <div className="space-y-2">
          {violLoad ? [...Array(5)].map((_, i) => <Skeleton key={i} className="h-14 rounded-xl" />) :
            violations.length === 0 ? (
              <div className="card-base py-14 text-center">
                <CheckCircle2 className="w-8 h-8 text-green-400 opacity-40 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No open violations — all policies passing!</p>
              </div>
            ) : (
              <div className="card-base overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                      {['Rule', 'Entity', 'Policy', 'Severity', 'Mode', 'Blocked', 'Date'].map(h => (
                        <th key={h} className="px-3 py-2.5 text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y" style={{ borderColor: 'hsl(230 15% 12%)' }}>
                    {violations.map((v: any) => (
                      <tr key={v.id} className={clsx('transition-colors hover:bg-white/[0.02]',
                        v.was_blocked && 'bg-red-500/5')}>
                        <td className="px-3 py-2.5">
                          <span className="font-medium text-foreground">{RULE_LABELS[v.rule_key] || v.rule_key}</span>
                        </td>
                        <td className="px-3 py-2.5 max-w-[160px]">
                          <p className="truncate text-muted-foreground">{v.entity_title || v.entity_id}</p>
                          <p className="text-[10px] text-muted-foreground/60 capitalize">{v.entity_type}</p>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="text-muted-foreground">{v.context?.policy_name || '—'}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={clsx('capitalize font-semibold', SEV_COLOR[v.severity] ?? 'text-foreground')}>{v.severity}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border capitalize',
                            ENFORCEMENT_COLOR[v.enforcement_mode] ?? ENFORCEMENT_COLOR.audit)}>
                            {v.enforcement_mode}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          {v.was_blocked
                            ? <span className="text-red-400 font-semibold text-[10px]">YES</span>
                            : <span className="text-muted-foreground/50 text-[10px]">no</span>}
                        </td>
                        <td className="px-3 py-2.5 text-muted-foreground">
                          {v.created_at ? new Date(v.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </div>
      )}

      {/* ── Templates tab ── */}
      {tab === 'templates' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {Object.entries(BUILTIN_META).map(([key, { icon, desc }]) => (
            <div key={key} className="card-base p-4 border border-white/5 hover:border-purple-500/20 transition-colors">
              <div className="flex items-start gap-3">
                <span className="text-2xl">{icon}</span>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-foreground">{RULE_LABELS[key]}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-[10px] px-1.5 py-0.5 rounded border text-purple-400 bg-purple-500/10 border-purple-500/20">Built-in</span>
                    <span className="text-[10px] text-muted-foreground">Rule: <code className="text-blue-400">{key}</code></span>
                  </div>
                </div>
              </div>
            </div>
          ))}
          {canWrite && (
            <div className="card-base p-4 border border-dashed border-purple-500/20 flex items-center justify-center col-span-full">
              <button onClick={handleSeedDefaults} disabled={seeding}
                className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-purple-600/20 text-purple-400 hover:bg-purple-600/30 border border-purple-500/30 transition-colors disabled:opacity-50 font-medium">
                {seeding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                {seeding ? 'Seeding…' : 'Load All Built-in Policies'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
