import { useState } from 'react';
import { ClipboardList, Plus, RefreshCw, Filter, ChevronLeft, ChevronRight, Loader2, CheckCircle, XCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { usePermissions } from '@/hooks/use-permissions';
import { canManageCompliance } from '@/lib/permissions';
import type { SecurityException } from '@/services/api/security';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const STATUS_STYLE: Record<string, string> = {
  pending:  'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  approved: 'bg-green-500/10 text-green-400 border-green-500/20',
  rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
  expired:  'bg-gray-500/10 text-gray-400 border-gray-500/20',
};

function CreateExceptionModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    title: '', justification: '', risk_acceptance: '',
    exception_type: 'temporary', finding_type: '',
  });

  const handle = async () => {
    if (!form.title.trim() || !form.justification.trim()) return;
    setSaving(true);
    try {
      await apiClient.post('/security-exceptions', form);
      onCreated();
      onClose();
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg mx-4 rounded-xl border p-5 shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <h3 className="text-sm font-semibold text-foreground mb-4">Request Security Exception</h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Title *</label>
            <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              placeholder="Brief description of the exception" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Justification *</label>
            <textarea value={form.justification} onChange={e => setForm(f => ({ ...f, justification: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 resize-none"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              rows={3} placeholder="Why is this exception needed?" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Risk Acceptance</label>
            <textarea value={form.risk_acceptance} onChange={e => setForm(f => ({ ...f, risk_acceptance: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 resize-none"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              rows={2} placeholder="Compensating controls or risk mitigation measures" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Type</label>
              <select value={form.exception_type} onChange={e => setForm(f => ({ ...f, exception_type: e.target.value }))}
                className="w-full px-2 py-1.5 text-xs rounded-lg border outline-none"
                style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}>
                <option value="temporary">Temporary</option>
                <option value="permanent">Permanent</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Finding Type</label>
              <select value={form.finding_type} onChange={e => setForm(f => ({ ...f, finding_type: e.target.value }))}
                className="w-full px-2 py-1.5 text-xs rounded-lg border outline-none"
                style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}>
                <option value="">General</option>
                <option value="threat">Threat</option>
                <option value="vulnerability">Vulnerability</option>
                <option value="compliance">Compliance</option>
                <option value="policy">Policy</option>
              </select>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>Cancel</button>
          <button onClick={handle} disabled={saving || !form.title.trim() || !form.justification.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors disabled:opacity-50">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
            {saving ? 'Submitting…' : 'Submit Request'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Exceptions() {
  const { role } = usePermissions();
  const canApprove = canManageCompliance(role);

  const [status, setStatus]   = useState('');
  const [type, setType]       = useState('');
  const [page, setPage]       = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [reviewing, setReviewing]   = useState<string | null>(null);

  const qs = new URLSearchParams({ page: String(page), page_size: '15' });
  if (status) qs.set('status', status);
  if (type)   qs.set('exception_type', type);

  const { data: raw, loading, refetch } = useApi<any>(`/security-exceptions?${qs}`);
  const { data: statsRaw } = useApi<any>('/security-exceptions/stats');

  const result     = raw?.data ?? raw;
  const exceptions = result?.data ?? [];
  const total      = result?.total ?? 0;
  const pages      = result?.pages ?? 1;
  const stats      = statsRaw?.data ?? statsRaw;

  const handleReview = async (id: string, action: 'approve' | 'reject') => {
    setReviewing(id + action);
    try {
      await apiClient.post(`/security-exceptions/${id}/review`, { action });
      refetch();
    } finally { setReviewing(null); }
  };

  return (
    <div className="space-y-4">
      {showCreate && <CreateExceptionModal onClose={() => setShowCreate(false)} onCreated={refetch} />}

      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Exception Requests</h1>
          <p className="text-xs text-muted-foreground">{total} total · {stats?.pending ?? 0} pending review</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors">
            <Plus className="w-3.5 h-3.5" /> New Request
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="flex gap-3 flex-wrap">
          {[
            { label: 'Pending',  value: stats.pending ?? 0,  cls: 'text-yellow-400' },
            { label: 'Approved', value: stats.approved ?? 0, cls: 'text-green-400' },
            { label: 'Rejected', value: stats.rejected ?? 0, cls: 'text-red-400' },
          ].map(({ label, value, cls }) => (
            <div key={label} className="card-base px-4 py-2.5 text-center min-w-[80px]">
              <p className={clsx('text-lg font-bold', cls)}>{value}</p>
              <p className="text-[10px] text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <Filter className="w-3.5 h-3.5 text-muted-foreground" />
        {['', 'pending', 'approved', 'rejected', 'expired'].map(s => (
          <button key={s} onClick={() => { setStatus(s); setPage(1); }}
            className={clsx('px-2.5 py-1 rounded capitalize transition-colors',
              status === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {s || 'All'}
          </button>
        ))}
        <div className="w-px h-4 bg-border mx-1" />
        {['', 'temporary', 'permanent'].map(t => (
          <button key={t} onClick={() => { setType(t); setPage(1); }}
            className={clsx('px-2.5 py-1 rounded capitalize transition-colors',
              type === t ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {t || 'All Types'}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="space-y-2">
        {loading ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)
        ) : exceptions.length === 0 ? (
          <div className="card-base py-12 text-center">
            <ClipboardList className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground mb-1">No exception requests</p>
            <p className="text-xs text-muted-foreground">Submit a request to get an exception to a security policy.</p>
          </div>
        ) : exceptions.map((e: SecurityException) => (
          <div key={e.id} className="card-base p-4">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-foreground">{e.title}</p>
                <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border capitalize', STATUS_STYLE[e.status] ?? STATUS_STYLE.pending)}>
                  {e.status}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground capitalize">
                  {e.exception_type}
                </span>
                {e.finding_type && (
                  <span className="text-[10px] text-muted-foreground capitalize">{e.finding_type}</span>
                )}
              </div>
              <span className="text-[10px] text-muted-foreground flex-shrink-0">
                {new Date(e.created_at).toLocaleDateString()}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mb-2 line-clamp-2">{e.justification}</p>
            {e.reviewer_note && (
              <p className="text-xs text-muted-foreground italic border-l-2 border-white/10 pl-2 mb-2">"{e.reviewer_note}"</p>
            )}
            {canApprove && e.status === 'pending' && (
              <div className="flex gap-2">
                <button onClick={() => handleReview(e.id, 'approve')} disabled={!!reviewing}
                  className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-green-500/10 text-green-400 hover:bg-green-500/20 border border-green-500/20 transition-colors disabled:opacity-50">
                  {reviewing === e.id + 'approve' ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                  Approve
                </button>
                <button onClick={() => handleReview(e.id, 'reject')} disabled={!!reviewing}
                  className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors disabled:opacity-50">
                  {reviewing === e.id + 'reject' ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
                  Reject
                </button>
              </div>
            )}
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
