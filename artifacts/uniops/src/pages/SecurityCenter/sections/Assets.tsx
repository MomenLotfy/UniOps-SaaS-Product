import { useState } from 'react';
import { Server, RefreshCw, Filter, ChevronLeft, ChevronRight, AlertTriangle, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const RISK_CLASS: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/20',
  high:     'bg-orange-500/15 text-orange-400 border-orange-500/20',
  medium:   'bg-yellow-500/15 text-yellow-400 border-yellow-500/20',
  low:      'bg-blue-500/15 text-blue-400 border-blue-500/20',
  none:     'bg-green-500/15 text-green-400 border-green-500/20',
};

const TYPE_ICONS: Record<string, string> = {
  github_repo: '⌥', gitlab_repo: '⌥', aws_ec2: '☁', aws_s3: '🪣',
  aws_rds: '🗄', k8s_pod: '📦', k8s_cluster: '⚙', docker_image: '🐳',
};

export default function Assets() {
  const { role } = usePermissions();
  const canSync = canWriteSecurity(role);

  const [typeFilter, setTypeFilter]   = useState('');
  const [riskFilter, setRiskFilter]   = useState('');
  const [srcFilter, setSrcFilter]     = useState('');
  const [page, setPage]               = useState(1);
  const [syncing, setSyncing]         = useState(false);
  const [syncError, setSyncError]     = useState<string | null>(null);

  const qs = new URLSearchParams({ page: String(page), page_size: '20' });
  if (typeFilter) qs.set('type', typeFilter);
  if (riskFilter) qs.set('risk_level', riskFilter);
  if (srcFilter)  qs.set('source', srcFilter);

  const { data: raw, loading, refetch } = useApi<any>(`/assets?${qs}`);
  const { data: statsRaw } = useApi<any>('/assets/stats');

  const result = raw?.data ?? raw;
  const assets = result?.data ?? [];
  const total  = result?.total ?? 0;
  const pages  = result?.pages ?? 1;
  const stats  = statsRaw?.data ?? statsRaw;

  const handleSync = async () => {
    setSyncing(true); setSyncError(null);
    try {
      await apiPost('/assets/discover', {});
      await refetch();
    } catch (e: any) { setSyncError(e?.message ?? 'Discovery failed'); }
    finally { setSyncing(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Assets</h1>
          <p className="text-xs text-muted-foreground">{total} assets in inventory</p>
        </div>
        <div className="flex gap-2">
          {canSync && (
            <button onClick={handleSync} disabled={syncing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
              style={{ borderColor: 'hsl(230 15% 20%)' }}>
              <RefreshCw className={clsx('w-3.5 h-3.5', syncing && 'animate-spin')} />
              {syncing ? 'Discovering…' : 'Discover'}
            </button>
          )}
          <button onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      {syncError && <p className="text-xs text-red-400">{syncError}</p>}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          <div className="card-base px-3 py-2.5 text-center">
            <p className="text-xl font-bold text-foreground">{stats.total ?? 0}</p>
            <p className="text-[10px] text-muted-foreground">Total Assets</p>
          </div>
          <div className="card-base px-3 py-2.5 text-center">
            <p className="text-xl font-bold text-red-400">{stats.critical_assets ?? 0}</p>
            <p className="text-[10px] text-muted-foreground">Critical</p>
          </div>
          {Object.entries(stats.by_source ?? {}).slice(0, 2).map(([src, count]) => (
            <div key={src} className="card-base px-3 py-2.5 text-center">
              <p className="text-xl font-bold text-foreground">{count as number}</p>
              <p className="text-[10px] text-muted-foreground capitalize">{src}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <Filter className="w-3.5 h-3.5 text-muted-foreground" />
        {['', 'critical', 'high', 'medium', 'low', 'none'].map(r => (
          <button key={r} onClick={() => { setRiskFilter(r); setPage(1); }}
            className={clsx('px-2.5 py-1 rounded capitalize transition-colors',
              riskFilter === r ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {r || 'All Risk'}
          </button>
        ))}
        <div className="w-px h-4 bg-border mx-1" />
        {['', 'github', 'aws', 'kubernetes'].map(s => (
          <button key={s} onClick={() => { setSrcFilter(s); setPage(1); }}
            className={clsx('px-2.5 py-1 rounded capitalize transition-colors',
              srcFilter === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {s || 'All Sources'}
          </button>
        ))}
      </div>

      {/* Asset list */}
      <div className="space-y-2">
        {loading ? (
          [...Array(5)].map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)
        ) : assets.length === 0 ? (
          <div className="card-base py-12 text-center">
            <Server className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground mb-1">No assets discovered</p>
            <p className="text-xs text-muted-foreground">Connect integrations and click Discover to populate your inventory.</p>
          </div>
        ) : assets.map((a: any) => (
          <div key={a.id} className="card-base p-4 flex items-center gap-4">
            <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0 text-sm">
              {TYPE_ICONS[a.type] ?? '📄'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-0.5">
                <p className="text-sm font-medium text-foreground truncate">{a.name}</p>
                <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border', RISK_CLASS[a.risk_level ?? 'none'])}>
                  {a.risk_level ?? 'none'}
                </span>
                {a.is_critical && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">
                    critical asset
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                <span className="capitalize">{a.type?.replace(/_/g, ' ')}</span>
                <span>·</span>
                <span className="capitalize">{a.source}</span>
                {a.environment && <><span>·</span><span className="capitalize">{a.environment}</span></>}
                {a.region && <><span>·</span><span>{a.region}</span></>}
                {a.open_findings > 0 && <><span>·</span><span className="text-orange-400">{a.open_findings} findings</span></>}
              </div>
            </div>
            <div className="flex-shrink-0">
              {a.status === 'active' || a.status === 'running'
                ? <CheckCircle className="w-4 h-4 text-green-400" />
                : a.status === 'error' || a.status === 'failed'
                  ? <AlertTriangle className="w-4 h-4 text-red-400" />
                  : <div className="w-4 h-4 rounded-full bg-white/10" />}
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
