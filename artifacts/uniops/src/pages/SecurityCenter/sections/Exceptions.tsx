import { useState } from 'react';
import {
  ClipboardList, Plus, RefreshCw, Loader2, CheckCircle, XCircle,
  AlertTriangle, Clock, User, Calendar, Shield, Timer,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { usePermissions } from '@/hooks/use-permissions';
import { canManageCompliance } from '@/lib/permissions';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const STATUS_STYLE: Record<string, string> = {
  pending:  'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  approved: 'bg-green-500/10 text-green-400 border-green-500/20',
  rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
  expired:  'bg-gray-500/10 text-gray-400 border-gray-500/20',
};

function daysUntil(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null;
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.ceil(diff / 86400000);
}

function ExpiryBadge({ expiresAt }: { expiresAt: string | null }) {
  const days = daysUntil(expiresAt);
  if (days === null) return <span className="text-muted-foreground/40 text-[10px] italic">no expiry</span>;
  if (days < 0)  return <span className="text-[10px] font-medium text-red-400">Expired {Math.abs(days)}d ago</span>;
  if (days <= 7) return <span className="text-[10px] font-medium text-orange-400">Expires in {days}d</span>;
  if (days <= 30) return <span className="text-[10px] font-medium text-yellow-400">Expires in {days}d</span>;
  return <span className="text-[10px] text-muted-foreground">Expires {new Date(expiresAt!).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>;
}

/* ── Create/Request modal ─────────────────────────────────────────────── */
function CreateExceptionModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    title: '', justification: '', risk_acceptance: '', owner: '',
    exception_type: 'temporary', finding_type: '', expires_at: '',
  });
  const handle = async () => {
    if (!form.title.trim() || !form.justification.trim()) return;
    setSaving(true);
    try {
      const payload: any = { ...form };
      if (!payload.expires_at) delete payload.expires_at;
      if (!payload.finding_type) delete payload.finding_type;
      await apiClient.post('/security-exceptions', payload);
      onCreated(); onClose();
    } finally { setSaving(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg mx-4 rounded-xl border p-5 shadow-2xl overflow-y-auto max-h-[90vh]"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <h3 className="text-sm font-semibold text-foreground mb-4">Request Security Exception</h3>
        <div className="space-y-3">
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Title *</label>
            <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              placeholder="Brief description of the exception needed" />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Reason / Justification *</label>
            <textarea value={form.justification} onChange={e => setForm(f => ({ ...f, justification: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 resize-none"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              rows={3} placeholder="Why is this exception required? Business context?" />
          </div>
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Risk Acceptance / Compensating Controls</label>
            <textarea value={form.risk_acceptance} onChange={e => setForm(f => ({ ...f, risk_acceptance: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 resize-none"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              rows={2} placeholder="What mitigations are in place to reduce risk?" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Owner</label>
              <input value={form.owner} onChange={e => setForm(f => ({ ...f, owner: e.target.value }))}
                className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50"
                style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
                placeholder="owner@company.com" />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Expiration Date</label>
              <input type="date" value={form.expires_at} onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))}
                className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50"
                style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Type</label>
              <select value={form.exception_type} onChange={e => setForm(f => ({ ...f, exception_type: e.target.value }))}
                className="w-full px-2 py-1.5 text-xs rounded-lg border outline-none"
                style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}>
                <option value="temporary">Temporary</option>
                <option value="permanent">Permanent</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">Finding Type</label>
              <select value={form.finding_type} onChange={e => setForm(f => ({ ...f, finding_type: e.target.value }))}
                className="w-full px-2 py-1.5 text-xs rounded-lg border outline-none"
                style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}>
                <option value="">General</option>
                <option value="threat">Threat</option>
                <option value="vulnerability">Vulnerability</option>
                <option value="compliance">Compliance</option>
                <option value="policy">Policy Violation</option>
              </select>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>Cancel</button>
          <button onClick={handle} disabled={saving || !form.title.trim() || !form.justification.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors disabled:opacity-50">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
            {saving ? 'Submitting…' : 'Submit Request'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Review modal ─────────────────────────────────────────────────────── */
function ReviewModal({ exc, action, onClose, onDone }: {
  exc: any; action: 'approve' | 'reject'; onClose: () => void; onDone: () => void;
}) {
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
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md mx-4 rounded-xl border p-5 shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <h3 className="text-sm font-semibold text-foreground mb-1">
          {action === 'approve' ? '✅ Approve' : '❌ Reject'} Exception
        </h3>
        <p className="text-xs text-muted-foreground mb-4">{exc.title}</p>
        <div>
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
            Reviewer Note {action === 'reject' ? '(required)' : '(optional)'}
          </label>
          <textarea value={note} onChange={e => setNote(e.target.value)}
            className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 resize-none"
            style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
            rows={3} placeholder={action === 'reject' ? 'Why is this being rejected?' : 'Any conditions or notes?'} />
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>Cancel</button>
          <button onClick={handle} disabled={saving || (action === 'reject' && !note.trim())}
            className={clsx('flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg text-white font-semibold transition-colors disabled:opacity-50',
              action === 'approve' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700')}>
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : action === 'approve' ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
            {saving ? 'Saving…' : action === 'approve' ? 'Approve' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────── */
export default function Exceptions() {
  const { role }   = usePermissions();
  const canApprove = canManageCompliance(role);

  const [status, setStatus]     = useState('');
  const [type, setType]         = useState('');
  const [page, setPage]         = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [reviewModal, setReviewModal] = useState<{ exc: any; action: 'approve' | 'reject' } | null>(null);

  const qs = new URLSearchParams({ page: String(page), page_size: '15' });
  if (status) qs.set('status', status);
  if (type)   qs.set('exception_type', type);

  const { data: raw, loading, refetch } = useApi<any>(`/security-exceptions?${qs}`);
  const { data: statsRaw }              = useApi<any>('/security-exceptions/stats');

  const result     = raw?.data ?? raw;
  const exceptions = result?.data ?? [];
  const total      = result?.total ?? 0;
  const pages      = result?.pages ?? 1;
  const stats      = statsRaw?.data ?? statsRaw ?? {};

  /* Expiring soon */
  const expiringSoon = exceptions.filter((e: any) => {
    const d = daysUntil(e.expires_at);
    return e.status === 'approved' && d !== null && d >= 0 && d <= 14;
  }).length;

  return (
    <div className="space-y-4">
      {showCreate && <CreateExceptionModal onClose={() => setShowCreate(false)} onCreated={refetch} />}
      {reviewModal && (
        <ReviewModal
          exc={reviewModal.exc}
          action={reviewModal.action}
          onClose={() => setReviewModal(null)}
          onDone={refetch}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Exception Management</h1>
          <p className="text-xs text-muted-foreground">
            {total} total · {stats.pending ?? 0} pending review · {expiringSoon} expiring in 14d
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()}
            className="p-1.5 rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors">
            <Plus className="w-3 h-3" /> New Request
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Pending Review',  value: stats.pending  ?? 0, color: 'text-yellow-400', icon: <Clock className="w-3.5 h-3.5" /> },
          { label: 'Approved',        value: stats.approved ?? 0, color: 'text-green-400',  icon: <CheckCircle className="w-3.5 h-3.5" /> },
          { label: 'Rejected',        value: stats.rejected ?? 0, color: 'text-red-400',    icon: <XCircle className="w-3.5 h-3.5" /> },
          { label: 'Expiring ≤14d',   value: expiringSoon,        color: 'text-orange-400', icon: <Timer className="w-3.5 h-3.5" /> },
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

      {/* Pending approval queue */}
      {canApprove && (stats.pending ?? 0) > 0 && (
        <div className="card-base p-4 border border-yellow-500/20 bg-yellow-500/5">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            <p className="text-xs font-semibold text-yellow-400">
              {stats.pending} exception{(stats.pending ?? 0) > 1 ? 's' : ''} awaiting your approval
            </p>
          </div>
          <p className="text-[11px] text-muted-foreground">Use the approve/reject buttons below to action the pending requests.</p>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {['', 'pending', 'approved', 'rejected', 'expired'].map(s => (
            <button key={s} onClick={() => { setStatus(s); setPage(1); }}
              className={clsx('px-3 py-1.5 text-[11px] font-medium capitalize transition-colors',
                status === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              {s || 'All'}
            </button>
          ))}
        </div>
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {['', 'temporary', 'permanent'].map(t => (
            <button key={t} onClick={() => { setType(t); setPage(1); }}
              className={clsx('px-3 py-1.5 text-[11px] font-medium capitalize transition-colors',
                type === t ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              {t || 'All Types'}
            </button>
          ))}
        </div>
      </div>

      {/* Exception list */}
      <div className="space-y-2">
        {loading ? [...Array(4)].map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />) :
          exceptions.length === 0 ? (
            <div className="card-base py-14 text-center">
              <ClipboardList className="w-8 h-8 text-muted-foreground opacity-30 mx-auto mb-2" />
              <p className="text-sm font-medium text-foreground mb-1">No exception requests</p>
              <p className="text-xs text-muted-foreground">Submit a request when a policy violation needs a sanctioned exception.</p>
            </div>
          ) : exceptions.map((e: any) => {
            const isPending = e.status === 'pending';
            const days = daysUntil(e.expires_at);
            const isExpiringSoon = e.status === 'approved' && days !== null && days >= 0 && days <= 14;
            return (
              <div key={e.id} className={clsx('card-base p-4 transition-colors',
                isPending && 'border-l-2 border-yellow-500/40',
                isExpiringSoon && 'border-l-2 border-orange-500/40',
              )}>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-semibold text-foreground">{e.title}</p>
                    <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border capitalize font-medium', STATUS_STYLE[e.status] ?? STATUS_STYLE.pending)}>
                      {e.status}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground capitalize border border-white/10">
                      {e.exception_type}
                    </span>
                    {e.finding_type && (
                      <span className="text-[10px] text-muted-foreground capitalize">{e.finding_type}</span>
                    )}
                  </div>
                  <span className="text-[10px] text-muted-foreground flex-shrink-0">
                    {new Date(e.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                  </span>
                </div>

                <p className="text-xs text-muted-foreground mb-2 line-clamp-2">{e.justification}</p>

                {/* Meta row */}
                <div className="flex items-center gap-4 text-[10px] text-muted-foreground mb-2 flex-wrap">
                  {e.owner && (
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3" /> {e.owner}
                    </span>
                  )}
                  {e.expires_at && (
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" /> <ExpiryBadge expiresAt={e.expires_at} />
                    </span>
                  )}
                </div>

                {e.reviewer_note && (
                  <p className="text-xs text-muted-foreground italic border-l-2 border-white/10 pl-2 mb-2">
                    "{e.reviewer_note}"
                  </p>
                )}

                {/* Approval actions */}
                {canApprove && isPending && (
                  <div className="flex gap-2 mt-2">
                    <button onClick={() => setReviewModal({ exc: e, action: 'approve' })}
                      className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-green-500/10 text-green-400 hover:bg-green-500/20 border border-green-500/20 transition-colors font-medium">
                      <CheckCircle className="w-3 h-3" /> Approve
                    </button>
                    <button onClick={() => setReviewModal({ exc: e, action: 'reject' })}
                      className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors font-medium">
                      <XCircle className="w-3 h-3" /> Reject
                    </button>
                  </div>
                )}
              </div>
            );
          })
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
    </div>
  );
}
