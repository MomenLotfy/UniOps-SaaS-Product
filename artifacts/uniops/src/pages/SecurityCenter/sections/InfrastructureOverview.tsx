import { useApi } from '@/hooks/use-api';
import { clsx } from 'clsx';
import { Server, Layers, Cloud, Activity, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const STATUS_STYLES: Record<string, { text: string; icon: React.ElementType; color: string }> = {
  connected: { text: 'text-green-400',  icon: CheckCircle,    color: 'bg-green-500/15' },
  healthy:   { text: 'text-green-400',  icon: CheckCircle,    color: 'bg-green-500/15' },
  error:     { text: 'text-red-400',    icon: XCircle,        color: 'bg-red-500/15'   },
  degraded:  { text: 'text-orange-400', icon: AlertTriangle,  color: 'bg-orange-500/15' },
  unknown:   { text: 'text-gray-400',   icon: Activity,       color: 'bg-white/5'      },
};

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status?.toLowerCase()] ?? STATUS_STYLES.unknown;
  const Icon = s.icon;
  return (
    <span className={clsx('flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-medium', s.color, s.text)}>
      <Icon className="w-3 h-3" />
      {status}
    </span>
  );
}

export default function InfrastructureOverview() {
  const { data: clustersRaw, loading: clustersLoading } = useApi<any>('/clusters');
  const { data: assetsRaw,   loading: assetsLoading }   = useApi<any>('/assets');

  const clusters = (() => {
    const raw = clustersRaw?.data ?? clustersRaw;
    return Array.isArray(raw) ? raw : (raw?.items ?? []);
  })();

  const assets = (() => {
    const raw = assetsRaw?.data ?? assetsRaw;
    return Array.isArray(raw) ? raw : (raw?.items ?? []);
  })();

  const assetsByType: Record<string, number> = {};
  for (const a of assets) {
    const t = a.asset_type ?? a.type ?? 'other';
    assetsByType[t] = (assetsByType[t] ?? 0) + 1;
  }
  const assetChartData = Object.entries(assetsByType)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  const clustersByStatus: Record<string, number> = {};
  for (const c of clusters) {
    const s = c.status ?? 'unknown';
    clustersByStatus[s] = (clustersByStatus[s] ?? 0) + 1;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-lg font-bold text-foreground">Infrastructure Overview</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Cloud clusters, assets, and infrastructure health
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Total Clusters',   value: clusters.length,  icon: Layers, color: 'text-purple-400 bg-purple-500/15', loading: clustersLoading },
          { label: 'Total Assets',     value: assets.length,    icon: Server, color: 'text-blue-400   bg-blue-500/15',   loading: assetsLoading   },
          { label: 'Cloud Accounts',   value: undefined,        icon: Cloud,  color: 'text-cyan-400   bg-cyan-500/15',   loading: true            },
          { label: 'Healthy Clusters', value: clusters.filter((c: any) => ['connected', 'healthy'].includes(c.status?.toLowerCase())).length,
            icon: CheckCircle, color: 'text-green-400 bg-green-500/15', loading: clustersLoading },
        ].map(({ label, value, icon: Icon, color, loading }) => (
          <div key={label} className="card-base p-4 flex items-center gap-3">
            <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0', color.split(' ')[1])}>
              <Icon className={clsx('w-4.5 h-4.5', color.split(' ')[0])} />
            </div>
            <div className="min-w-0">
              {loading ? <Skeleton className="h-5 w-10 mb-1" /> : (
                <p className={clsx('text-xl font-bold', color.split(' ')[0])}>{value ?? '—'}</p>
              )}
              <p className="text-xs text-muted-foreground">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Clusters table */}
      <div className="card-base overflow-hidden">
        <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Layers className="w-4 h-4 text-purple-400" />
            Kubernetes Clusters
          </p>
          <span className="text-xs text-muted-foreground">{clusters.length} clusters</span>
        </div>
        <div className="overflow-x-auto">
          {clustersLoading ? (
            <div className="p-4 space-y-2">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10 w-full rounded-lg" />)}
            </div>
          ) : clusters.length === 0 ? (
            <div className="py-12 text-center">
              <Layers className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-40" />
              <p className="text-sm text-muted-foreground">No clusters connected yet</p>
              <p className="text-xs text-muted-foreground/60 mt-1">Connect a Kubernetes cluster from the Integrations page</p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                  {['Name', 'Provider', 'Region', 'Nodes', 'Pods', 'CPU', 'Memory', 'Status'].map(h => (
                    <th key={h} className="px-4 py-2.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'hsl(230 15% 12%)' }}>
                {clusters.map((c: any) => (
                  <tr key={c.id} className="hover:bg-white/3 transition-colors">
                    <td className="px-4 py-3 font-medium text-foreground whitespace-nowrap">{c.name}</td>
                    <td className="px-4 py-3 text-muted-foreground capitalize">{c.provider}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.region ?? '—'}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.node_count ?? '—'}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.pod_count ?? '—'}</td>
                    <td className="px-4 py-3">
                      {c.cpu_usage_pct != null ? (
                        <span className={c.cpu_usage_pct > 80 ? 'text-red-400' : c.cpu_usage_pct > 60 ? 'text-yellow-400' : 'text-green-400'}>
                          {c.cpu_usage_pct.toFixed(1)}%
                        </span>
                      ) : <span className="text-muted-foreground">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      {c.memory_usage_pct != null ? (
                        <span className={c.memory_usage_pct > 80 ? 'text-red-400' : c.memory_usage_pct > 60 ? 'text-yellow-400' : 'text-green-400'}>
                          {c.memory_usage_pct.toFixed(1)}%
                        </span>
                      ) : <span className="text-muted-foreground">—</span>}
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={c.status ?? 'unknown'} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Assets by type chart */}
      {!assetsLoading && assetChartData.length > 0 && (
        <div className="card-base p-4">
          <p className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
            <Server className="w-4 h-4 text-blue-400" />
            Assets by Type
          </p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={assetChartData} layout="vertical" margin={{ left: 40, right: 20, top: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 16%)" horizontal={false} />
              <XAxis type="number" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} />
              <YAxis type="category" dataKey="name" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} width={80} />
              <Tooltip
                contentStyle={{ background: 'hsl(230 15% 10%)', border: '1px solid hsl(230 15% 18%)', borderRadius: 8, fontSize: 11 }}
                formatter={(v: any) => [v, 'Assets']}
              />
              <Bar dataKey="count" fill="#3b82f6" fillOpacity={0.8} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {assetsLoading && (
        <div className="card-base p-4">
          <Skeleton className="h-6 w-32 mb-4" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}
    </div>
  );
}
