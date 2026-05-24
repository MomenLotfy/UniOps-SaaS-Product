import { useState } from 'react';
import { Server, CheckCircle, AlertTriangle, RefreshCw, Settings, Cpu, HardDrive, Activity, XCircle, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import { useIntegrationsCtx } from '@/contexts/IntegrationsContext';
import { formatRelative } from '@/lib/formatters';

const statusBar = (val: number) => {
  const color = val > 85 ? 'hsl(0 80% 60%)' : val > 70 ? 'hsl(25 80% 55%)' : 'hsl(220 90% 60%)';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${val}%`, background: color }} />
      </div>
      <span className="text-xs font-mono w-8 text-right" style={{ color }}>{val}%</span>
    </div>
  );
};

export default function KubernetesIntegration() {
  const [syncing, setSyncing] = useState(false);
  const [selectedNs, setSelectedNs] = useState<string | null>(null);

  const { data: clusterRaw, loading: clusterLoading, refetch: refetchCluster } = useApi<any>('/kubernetes/pods/cluster/summary');
  const { data: nsRaw,      loading: nsLoading }                                = useApi<any>('/kubernetes/pods/namespaces');
  const { data: podsRaw,    loading: podsLoading }                              = useApi<any>('/kubernetes/pods?limit=100');

  // ── Global context (no extra HTTP request) ────────────────────────────────
  const { integrations, isConnected } = useIntegrationsCtx();
  const k8sIntg = integrations.find(
    (i) => i.provider === 'kubernetes' && i.status === 'connected'
  );
  const connected = isConnected('kubernetes');

  const cluster    = clusterRaw ?? null;
  const namespaces = (Array.isArray(nsRaw) ? nsRaw : nsRaw?.data ?? nsRaw?.namespaces) ?? [];
  const allPods    = (Array.isArray(podsRaw) ? podsRaw : podsRaw?.data ?? podsRaw?.pods) ?? [];

  const handleSync = async () => {
    setSyncing(true);
    try {
      if (k8sIntg?.id) await apiPost(`/integrations/${k8sIntg.id}/sync`, {});
      await refetchCluster();
    } finally {
      setSyncing(false);
    }
  };

  if (!connected) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="card-base py-16 text-center space-y-3">
          <XCircle className="w-10 h-10 text-muted-foreground mx-auto" />
          <p className="text-sm font-semibold text-foreground">Kubernetes not connected</p>
          <p className="text-xs text-muted-foreground">Paste a kubeconfig in Settings → Integrations to connect your cluster.</p>
        </div>
      </div>
    );
  }

  const totalNodes = cluster?.totalNodes ?? k8sIntg?.config?.node_count ?? 0;
  const totalPods  = cluster?.totalPods  ?? k8sIntg?.config?.pod_count  ?? 0;
  const clusterName = cluster?.name ?? k8sIntg?.config?.cluster_name ?? 'Cluster';

  // Aggregate namespace pod stats from pods list (if available)
  const nsList: any[] = namespaces.length > 0 ? namespaces : [];

  // Derive CPU/memory from cluster health data
  const cpuPct = cluster?.cpuUsage  ?? cluster?.cpu_usage_percent  ?? null;
  const memPct = cluster?.memUsage  ?? cluster?.mem_usage_percent  ?? null;

  // Filter pods by selected namespace
  const filteredPods = selectedNs
    ? allPods.filter((p: any) => p.namespace === selectedNs)
    : allPods;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'hsl(220 80% 55% / 0.2)' }}>
            <Server className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h1 className="page-title">Kubernetes</h1>
            <p className="page-subtitle">
              {clusterName} · {totalNodes} nodes · {totalPods} pods
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSync} disabled={syncing} className="action-btn">
            {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {syncing ? 'Syncing…' : 'Sync'}
          </button>
          <button className="action-btn"><Settings className="w-4 h-4" /> Configure</button>
        </div>
      </div>

      {/* Summary stats */}
      {clusterLoading ? (
        <div className="grid grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="card-base h-20 animate-pulse bg-surface-2 rounded-xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Total Nodes',   value: totalNodes,            icon: Server,    color: 'hsl(220 90% 60%)' },
            { label: 'Running Pods',  value: totalPods,             icon: Activity,  color: 'hsl(140 60% 45%)' },
            { label: 'CPU Usage',     value: cpuPct != null ? `${Math.round(cpuPct)}%` : '—',  icon: Cpu,       color: 'hsl(25 80% 55%)' },
            { label: 'Memory Usage',  value: memPct != null ? `${Math.round(memPct)}%` : '—', icon: HardDrive, color: 'hsl(260 70% 60%)' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="card-base rounded-xl p-4 border border-border">
              <div className="flex items-center gap-2 mb-2">
                <Icon className="w-4 h-4" style={{ color }} />
                <span className="text-xs text-muted-foreground">{label}</span>
              </div>
              <div className="text-2xl font-bold text-foreground">{value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Cluster status card */}
        <div className="col-span-2 space-y-4">
          <div className="card-base rounded-xl p-5 border border-border">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-foreground">Cluster Status</h3>
              {cluster?.status && (
                <span className={clsx('text-xs px-2 py-0.5 rounded-full border',
                  cluster.status === 'healthy'
                    ? 'text-green-400 bg-green-400/10 border-green-400/20'
                    : 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20')}>
                  {cluster.status}
                </span>
              )}
            </div>
            {clusterLoading ? (
              <div className="space-y-3">{[1,2].map(i => <div key={i} className="h-8 rounded bg-surface-2 animate-pulse" />)}</div>
            ) : cluster ? (
              <div className="space-y-4">
                <div>
                  <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1"><Cpu className="w-3 h-3" />CPU</div>
                  {cpuPct != null ? statusBar(Math.round(cpuPct)) : <span className="text-xs text-muted-foreground">No data</span>}
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1"><HardDrive className="w-3 h-3" />Memory</div>
                  {memPct != null ? statusBar(Math.round(memPct)) : <span className="text-xs text-muted-foreground">No data</span>}
                </div>
                {cluster.version && (
                  <div className="flex items-center gap-2 pt-1 border-t border-border">
                    <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                    <span className="text-xs text-muted-foreground">Kubernetes {cluster.version}</span>
                    {k8sIntg?.lastSync && (
                      <span className="text-xs text-muted-foreground ml-auto">Synced {formatRelative(k8sIntg.lastSync)}</span>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">Could not load cluster details.</p>
            )}
          </div>

          {/* Pods list */}
          {allPods.length > 0 && (
            <div className="card-base rounded-xl p-5 border border-border">
              <h3 className="text-sm font-semibold text-foreground mb-4">
                Pods {selectedNs ? `· ${selectedNs}` : ''}
                {selectedNs && (
                  <button onClick={() => setSelectedNs(null)} className="ml-2 text-xs text-blue-400 hover:underline">Clear</button>
                )}
              </h3>
              {podsLoading ? (
                <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-8 rounded bg-surface-2 animate-pulse" />)}</div>
              ) : (
                <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
                  {filteredPods.slice(0, 20).map((pod: any, i: number) => (
                    <div key={pod.name ?? i} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-accent">
                      <div className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0',
                        pod.status === 'Running' ? 'bg-green-400' : pod.status === 'Pending' ? 'bg-yellow-400' : 'bg-red-400')} />
                      <span className="text-xs font-mono text-foreground truncate flex-1">{pod.name}</span>
                      <span className="text-xs text-muted-foreground">{pod.namespace}</span>
                      <span className="text-xs text-muted-foreground">{pod.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Namespaces */}
        <div className="card-base rounded-xl p-5 border border-border">
          <h3 className="text-sm font-semibold text-foreground mb-4">Namespaces</h3>
          {nsLoading ? (
            <div className="space-y-3">{[1,2,3,4].map(i => <div key={i} className="h-10 rounded bg-surface-2 animate-pulse" />)}</div>
          ) : nsList.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-6">No namespaces found.</p>
          ) : (
            <div className="space-y-3">
              {nsList.map((ns: any, i: number) => {
                const name    = ns.name ?? ns;
                const running = ns.runningPods ?? ns.running ?? 0;
                const total   = ns.totalPods   ?? ns.pods    ?? 0;
                const healthy = running >= total;
                return (
                  <button key={name ?? i} onClick={() => setSelectedNs(name === selectedNs ? null : name)}
                    className={clsx('w-full flex items-center justify-between rounded-lg px-2 py-1.5 transition-colors',
                      selectedNs === name ? 'bg-primary/10' : 'hover:bg-accent')}>
                    <div className="text-left">
                      <div className="text-xs font-medium text-foreground">{name}</div>
                      {total > 0 && <div className="text-xs text-muted-foreground">{running}/{total} pods</div>}
                    </div>
                    <div className={clsx('text-xs px-2 py-0.5 rounded-full border',
                      healthy
                        ? 'text-green-400 bg-green-400/10 border-green-400/20'
                        : 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20')}>
                      {healthy ? 'Healthy' : 'Degraded'}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
