import { useState } from 'react';
import { BookOpen, Plus, RefreshCw, Filter, ChevronLeft, ChevronRight, Loader2, Trash2 } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';
import type { SecurityPolicy } from '@/services/api/security';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const ENFORCEMENT_COLOR: Record<string, string> = {
  mandatory: 'text-red-400 bg-red-500/10 border-red-500/20',
  advisory:  'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  audit:     'text-blue-400 bg-blue-500/10 border-blue-500/20',
};
const STATUS_COLOR: Record<string, string> = {
  active:   'text-green-400',
  inactive: 'text-gray-400',
  draft:    'text-yellow-400',
};

function CreatePolicyModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '', category: 'code_quality', severity: 'medium',
    enforcement: 'advisory', description: '',
  });

  const handle = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await apiClient.post('/security-policies', { ...form, status: 'active' });
      onCreated();
      onClose();
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md mx-4 rounded-xl border p-5 shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <h3 className="text-sm font-semibold text-foreground mb-4">Create Security Policy</h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Name *</label>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              placeholder="Policy name" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Description</label>
            <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 resize-none"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              rows={2} placeholder="What does this policy enforce?" />
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'Category', key: 'category', options: ['code_quality','secrets','dependencies','container','network','iam','compliance'] },
              { label: 'Severity',  key: 'severity',    options: ['critical','high','medium','low'] },
              { label: 'Enforcement',key:'enforcement', options: ['mandatory','advisory','audit'] },
            ].map(({ label, key, options }) => (
              <div key={key}>
                <label className="text-xs text-muted-foreground mb-1 block">{label}</label>
                <select value={(form as any)[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                  className="w-full px-2 py-1.5 text-xs rounded-lg border outline-none capitalize"
                  style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}>
                  {options.map(o => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>Cancel</button>
          <button onClick={handle} disabled={saving || !form.name.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors disabled:opacity-50">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
            {saving ? 'Creating…' : 'Create Policy'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Policies() {
  const { role } = usePermissions();
  const canWrite = canWriteSecurity(role);

  const [category, setCategory]     = useState('');
  const [status, setStatus]         = useState('');
  const [enforcement, setEnforcement] = useState('');
  const [page, setPage]             = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [deleting, setDeleting]     = useState<string | null>(null);

  const qs = new URLSearchParams({ page: String(page), page_size: '15' });
  if (category)    qs.set('category', category);
  if (status)      qs.set('status', status);
  if (enforcement) qs.set('enforcement', enforcement);

  const { data: raw, loading, refetch } = useApi<any>(`/security-policies?${qs}`);
  const { data: statsRaw } = useApi<any>('/security-policies/stats');

  const result   = raw?.data ?? raw;
  const policies = result?.data ?? [];
  const total    = result?.total ?? 0;
  const pages    = result?.pages ?? 1;
  const stats    = statsRaw?.data ?? statsRaw;

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await apiClient.delete(`/security-policies/${id}`);
      refetch();
    } finally { setDeleting(null); }
  };

  return (
    <div className="space-y-4">
      {showCreate && <CreatePolicyModal onClose={() => setShowCreate(false)} onCreated={refetch} />}

      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Security Policies</h1>
          <p className="text-xs text-muted-foreground">{total} policies · {stats?.active ?? 0} active</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          {canWrite && (
            <button onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors">
              <Plus className="w-3.5 h-3.5" /> New Policy
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="flex gap-3 flex-wrap text-xs">
          {Object.entries(stats.by_status ?? {}).map(([s, count]) => (
            <div key={s} className="card-base px-3 py-2 text-center min-w-[70px]">
              <p className={clsx('text-sm font-bold', STATUS_COLOR[s] ?? 'text-foreground')}>{count as number}</p>
              <p className="text-[10px] text-muted-foreground capitalize">{s}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <Filter className="w-3.5 h-3.5 text-muted-foreground" />
        {['', 'mandatory', 'advisory', 'audit'].map(e => (
          <button key={e} onClick={() => { setEnforcement(e); setPage(1); }}
            className={clsx('px-2.5 py-1 rounded capitalize transition-colors',
              enforcement === e ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {e || 'All'}
          </button>
        ))}
        <div className="w-px h-4 bg-border mx-1" />
        {['', 'active', 'inactive', 'draft'].map(s => (
          <button key={s} onClick={() => { setStatus(s); setPage(1); }}
            className={clsx('px-2.5 py-1 rounded capitalize transition-colors',
              status === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {s || 'All Status'}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="space-y-2">
        {loading ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
        ) : policies.length === 0 ? (
          <div className="card-base py-12 text-center">
            <BookOpen className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground mb-1">No policies yet</p>
            {canWrite && <p className="text-xs text-muted-foreground">Click "New Policy" to create your first security policy.</p>}
          </div>
        ) : policies.map((p: SecurityPolicy) => (
          <div key={p.id} className="card-base p-4">
            <div className="flex items-start gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <p className="text-sm font-medium text-foreground">{p.name}</p>
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border capitalize', ENFORCEMENT_COLOR[p.enforcement] ?? ENFORCEMENT_COLOR.advisory)}>
                    {p.enforcement}
                  </span>
                  <span className={clsx('text-xs font-medium capitalize', STATUS_COLOR[p.status] ?? 'text-muted-foreground')}>
                    {p.status}
                  </span>
                </div>
                {p.description && <p className="text-xs text-muted-foreground">{p.description}</p>}
                <div className="flex items-center gap-3 mt-1 text-[10px] text-muted-foreground">
                  <span className="capitalize">{p.category?.replace(/_/g, ' ')}</span>
                  <span>·</span>
                  <span className="capitalize">{p.severity} severity</span>
                  {p.exceptions_count > 0 && <><span>·</span><span className="text-yellow-400">{p.exceptions_count} exceptions</span></>}
                  {p.frameworks?.length > 0 && <><span>·</span><span>{p.frameworks.join(', ')}</span></>}
                </div>
              </div>
              {canWrite && (
                <button onClick={() => handleDelete(p.id)} disabled={deleting === p.id}
                  className="text-muted-foreground hover:text-red-400 transition-colors disabled:opacity-40 flex-shrink-0">
                  {deleting === p.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-muted-foreground">Page {page} of {pages}</span>
          <div className="flex gap-1">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
              className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
