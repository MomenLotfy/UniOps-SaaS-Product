import { useState } from 'react';
import { Bug, Shield, Filter, RefreshCw, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const SEV_CLASS: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border border-red-500/20',
  high:     'bg-orange-500/15 text-orange-400 border border-orange-500/20',
  medium:   'bg-yellow-500/15 text-yellow-400 border border-yellow-500/20',
  low:      'bg-blue-500/15 text-blue-400 border border-blue-500/20',
};

export default function Vulnerabilities() {
  const [severity, setSeverity] = useState('');
  const [status, setStatus]     = useState('');
  const [page, setPage]         = useState(1);

  const qs = new URLSearchParams({ page: String(page), page_size: '15' });
  if (severity) qs.set('severity', severity);
  if (status)   qs.set('status', status);

  const { data: raw, loading, refetch } = useApi<any>(`/vulnerabilities?${qs}`);
  const { data: statsRaw } = useApi<any>('/vulnerabilities/stats');

  const result = raw?.data ?? raw;
  const vulns  = result?.data ?? [];
  const total  = result?.total ?? 0;
  const pages  = result?.pages ?? 1;
  const stats  = statsRaw?.data ?? statsRaw;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Vulnerabilities</h1>
          <p className="text-xs text-muted-foreground">{total} CVEs and package findings</p>
        </div>
        <button onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
          style={{ borderColor: 'hsl(230 15% 20%)' }}>
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {[
            { label: 'Critical', key: 'critical_count', cls: 'text-red-400' },
            { label: 'High',     key: 'high_count',     cls: 'text-orange-400' },
            { label: 'Medium',   key: 'medium_count',   cls: 'text-yellow-400' },
            { label: 'Low',      key: 'low_count',      cls: 'text-blue-400' },
          ].map(({ label, key, cls }) => (
            <div key={key} className="card-base px-3 py-2.5 text-center">
              <p className={clsx('text-xl font-bold', cls)}>{stats?.[key] ?? 0}</p>
              <p className="text-[10px] text-muted-foreground">{label}</p>
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
        {['', 'open', 'fixed', 'accepted'].map(s => (
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
        ) : vulns.length === 0 ? (
          <div className="card-base py-12 text-center">
            <Shield className="w-8 h-8 text-green-400 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No vulnerabilities match current filters.</p>
          </div>
        ) : vulns.map((v: any) => (
          <div key={v.id} className="card-base p-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-md bg-orange-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bug className="w-4 h-4 text-orange-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  {v.cve_id && (
                    <code className="text-xs font-mono text-blue-400">{v.cve_id}</code>
                  )}
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-medium', SEV_CLASS[v.severity] ?? SEV_CLASS.low)}>
                    {v.severity}
                  </span>
                  <span className={clsx('text-xs',
                    v.status === 'open' ? 'text-red-400' : v.status === 'fixed' ? 'text-green-400' : 'text-muted-foreground')}>
                    {v.status}
                  </span>
                  {v.cvss_score != null && (
                    <span className="text-[10px] text-muted-foreground">CVSS {v.cvss_score}</span>
                  )}
                </div>
                <p className="text-sm font-medium text-foreground">{v.title}</p>
                {v.package_name && (
                  <p className="text-xs text-muted-foreground mt-0.5 font-mono">
                    {v.package_name}@{v.package_version}
                    {v.fixed_version && <span className="text-green-400 ml-1">→ {v.fixed_version}</span>}
                  </p>
                )}
                {v.target && <p className="text-xs text-muted-foreground font-mono truncate">{v.target}</p>}
              </div>
              <span className="text-[10px] text-muted-foreground flex-shrink-0">
                {v.created_at ? new Date(v.created_at).toLocaleDateString() : ''}
              </span>
            </div>
          </div>
        ))}
      </div>

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
