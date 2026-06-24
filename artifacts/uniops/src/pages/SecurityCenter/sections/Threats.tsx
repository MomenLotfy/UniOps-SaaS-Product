import { useState, useCallback } from 'react';
import { AlertTriangle, Shield, ShieldCheck, ShieldOff, Filter, RefreshCw, ChevronLeft, ChevronRight, Loader2, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';
import { motion, AnimatePresence } from 'framer-motion';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const SEV_CLASS: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border border-red-500/20',
  high:     'bg-orange-500/15 text-orange-400 border border-orange-500/20',
  medium:   'bg-yellow-500/15 text-yellow-400 border border-yellow-500/20',
  low:      'bg-blue-500/15 text-blue-400 border border-blue-500/20',
};
const STATUS_COLOR: Record<string, string> = {
  open: 'text-red-400', active: 'text-red-400', mitigated: 'text-green-400',
  investigating: 'text-yellow-400', resolved: 'text-green-400', suppressed: 'text-gray-400',
};

export default function Threats() {
  const { role } = usePermissions();
  const canAct = canWriteSecurity(role);

  const [severity, setSeverity] = useState('');
  const [status, setStatus]     = useState('');
  const [page, setPage]         = useState(1);
  const [acting, setActing]     = useState<string | null>(null);

  const qs = new URLSearchParams({ page: String(page), page_size: '15' });
  if (severity) qs.set('severity', severity);
  if (status)   qs.set('status', status);

  const { data: raw, loading, refetch } = useApi<any>(`/threats?${qs}`);
  const { data: statsRaw } = useApi<any>('/threats/stats');

  const result   = raw?.data ?? raw;
  const threats  = result?.data ?? [];
  const total    = result?.total ?? 0;
  const pages    = result?.pages ?? 1;
  const stats    = statsRaw?.data ?? statsRaw;

  const act = useCallback(async (threatId: string, action: 'resolve' | 'suppress') => {
    setActing(threatId + action);
    try {
      await apiClient.post(`/threats/${threatId}/${action}`, {});
      refetch();
    } catch (e) { /* handled by global error */ }
    finally { setActing(null); }
  }, [refetch]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Threats</h1>
          <p className="text-xs text-muted-foreground">{total} findings · tenant-isolated</p>
        </div>
        <button onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
          style={{ borderColor: 'hsl(230 15% 20%)' }}>
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-4 gap-2">
          {(['critical','high','medium','low'] as const).map(s => (
            <div key={s} className="card-base px-3 py-2 text-center">
              <p className={clsx('text-base font-bold', s === 'critical' ? 'text-red-400' : s === 'high' ? 'text-orange-400' : s === 'medium' ? 'text-yellow-400' : 'text-blue-400')}>
                {stats?.[`${s}_count`] ?? stats?.by_severity?.[s] ?? 0}
              </p>
              <p className="text-[10px] text-muted-foreground capitalize">{s}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="w-3.5 h-3.5 text-muted-foreground" />
        {['', 'critical', 'high', 'medium', 'low'].map(s => (
          <button key={s} onClick={() => { setSeverity(s); setPage(1); }}
            className={clsx('px-2.5 py-1 rounded text-xs capitalize transition-colors',
              severity === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {s || 'All'}
          </button>
        ))}
        <div className="w-px h-4 bg-border mx-1" />
        {['', 'open', 'resolved', 'suppressed'].map(s => (
          <button key={s} onClick={() => { setStatus(s); setPage(1); }}
            className={clsx('px-2.5 py-1 rounded text-xs capitalize transition-colors',
              status === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {s || 'All Status'}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="space-y-2">
        {loading ? (
          [...Array(5)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
        ) : threats.length === 0 ? (
          <div className="card-base py-12 text-center">
            <Shield className="w-8 h-8 text-green-400 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No threats match current filters.</p>
          </div>
        ) : threats.map((t: any) => (
          <div key={t.id} className="card-base p-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-md bg-red-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <AlertTriangle className="w-4 h-4 text-red-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <code className="text-[10px] text-muted-foreground font-mono">{t.id?.slice(0, 8)}</code>
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-medium', SEV_CLASS[t.severity] ?? SEV_CLASS.low)}>
                    {t.severity}
                  </span>
                  <span className={clsx('text-xs font-medium', STATUS_COLOR[t.status] ?? 'text-muted-foreground')}>
                    {t.status}
                  </span>
                  {t.mitre_tactic && (
                    <span className="text-[10px] text-muted-foreground font-mono">{t.mitre_tactic}</span>
                  )}
                  {t.source && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground">{t.source}</span>
                  )}
                </div>
                <p className="text-sm font-medium text-foreground">{t.title}</p>
                {t.resource && <p className="text-xs text-muted-foreground mt-0.5 font-mono truncate">{t.resource}</p>}
                {canAct && !['resolved', 'suppressed'].includes(t.status) && (
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => act(t.id, 'resolve')}
                      disabled={acting === t.id + 'resolve'}
                      className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-green-500/10 text-green-400 hover:bg-green-500/20 border border-green-500/20 transition-colors disabled:opacity-50">
                      {acting === t.id + 'resolve' ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldCheck className="w-3 h-3" />}
                      Resolve
                    </button>
                    <button
                      onClick={() => act(t.id, 'suppress')}
                      disabled={acting === t.id + 'suppress'}
                      className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 border border-yellow-500/20 transition-colors disabled:opacity-50">
                      {acting === t.id + 'suppress' ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldOff className="w-3 h-3" />}
                      Suppress
                    </button>
                  </div>
                )}
                {['resolved', 'suppressed'].includes(t.status) && (
                  <div className="flex items-center gap-1.5 mt-2 text-xs text-green-400">
                    <CheckCircle className="w-3 h-3" />
                    {t.status === 'resolved' ? 'Resolved' : 'Suppressed'}
                  </div>
                )}
              </div>
              <span className="text-[10px] text-muted-foreground flex-shrink-0">
                {t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-muted-foreground">Page {page} of {pages} · {total} total</span>
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
