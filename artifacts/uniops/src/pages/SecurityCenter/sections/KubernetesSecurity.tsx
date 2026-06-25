import { useState, useCallback } from 'react';
import {
  Server, RefreshCw, Play, Shield, AlertTriangle,
  ChevronDown, ChevronUp, ChevronRight, X,
  CheckCircle, Clock, ExternalLink, Filter,
  Layers, Box, Cpu, Lock, Globe, Network,
  Eye, EyeOff, Activity, BarChart3,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost, apiPatch } from '@/hooks/use-api';

// ─── Constants ────────────────────────────────────────────────────────────────

const SEV_COLOR: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-blue-400',
  info:     'text-slate-400',
};
const SEV_BG: Record<string, string> = {
  critical: 'bg-red-500/15 border-red-500/30',
  high:     'bg-orange-500/15 border-orange-500/30',
  medium:   'bg-yellow-500/15 border-yellow-500/30',
  low:      'bg-blue-500/15 border-blue-500/30',
  info:     'bg-slate-500/15 border-slate-500/30',
};
const SEV_DOT: Record<string, string> = {
  critical: 'bg-red-500',
  high:     'bg-orange-500',
  medium:   'bg-yellow-500',
  low:      'bg-blue-500',
  info:     'bg-slate-500',
};

const CAT_LABEL: Record<string, string> = {
  privileged_containers: 'Privileged Containers',
  rbac:                  'RBAC Misconfigurations',
  exposed_services:      'Exposed Services',
  network_policy:        'Network Policies',
  secrets:               'Secrets Exposure',
  cis_benchmark:         'CIS Benchmark',
  runtime:               'Runtime Security',
};

const CAT_ICON: Record<string, React.ElementType> = {
  privileged_containers: Box,
  rbac:                  Lock,
  exposed_services:      Globe,
  network_policy:        Network,
  secrets:               Eye,
  cis_benchmark:         Shield,
  runtime:               Activity,
};

const SCANNER_LABEL: Record<string, string> = {
  native:      'Native K8s API',
  kubescape:   'Kubescape',
  'kube-bench': 'kube-bench',
  'kube-hunter': 'kube-hunter',
};

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// ─── Risk ring ────────────────────────────────────────────────────────────────

function RiskRing({ score }: { score: number | null }) {
  if (score === null) return (
    <div className="w-16 h-16 rounded-full border-4 border-white/10 flex items-center justify-center">
      <span className="text-[10px] text-muted-foreground">N/A</span>
    </div>
  );
  const pct = Math.min(100, score);
  const color = pct >= 70 ? '#ef4444' : pct >= 40 ? '#f97316' : pct >= 20 ? '#eab308' : '#22c55e';
  const r = 22, circ = 2 * Math.PI * r;
  const dash = circ * (pct / 100);
  return (
    <div className="relative w-16 h-16 flex-shrink-0">
      <svg viewBox="0 0 56 56" className="w-16 h-16 -rotate-90">
        <circle cx="28" cy="28" r={r} fill="none" stroke="hsl(230 15% 15%)" strokeWidth="5" />
        <circle cx="28" cy="28" r={r} fill="none" stroke={color}
          strokeWidth="5" strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`} />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[11px] font-bold" style={{ color }}>{Math.round(score)}</span>
      </div>
    </div>
  );
}

// ─── Severity bar strip ───────────────────────────────────────────────────────

function SevBar({ by_severity }: { by_severity: Record<string, number> }) {
  const total = Object.values(by_severity).reduce((a, b) => a + b, 0) || 1;
  const order = ['critical', 'high', 'medium', 'low', 'info'];
  return (
    <div className="flex h-1.5 rounded-full overflow-hidden w-full">
      {order.map(sev => {
        const pct = ((by_severity[sev] ?? 0) / total) * 100;
        if (!pct) return null;
        return (
          <div key={sev} style={{ width: `${pct}%` }}
            className={clsx(SEV_DOT[sev])} title={`${sev}: ${by_severity[sev]}`} />
        );
      })}
    </div>
  );
}

// ─── Cluster card ─────────────────────────────────────────────────────────────

function ClusterCard({
  cluster, selected, onSelect, onScan, scanning,
}: {
  cluster: any;
  selected: boolean;
  onSelect: () => void;
  onScan: () => void;
  scanning: boolean;
}) {
  const statusColor: Record<string, string> = {
    connected: 'text-green-400',
    disconnected: 'text-red-400',
    error: 'text-red-400',
    pending: 'text-yellow-400',
  };

  return (
    <button
      onClick={onSelect}
      className={clsx(
        'w-full text-left p-4 rounded-xl border transition-all',
        selected
          ? 'border-blue-500/40 bg-blue-500/8'
          : 'border-border hover:border-white/20 bg-surface-1',
      )}
    >
      <div className="flex items-start gap-3">
        <RiskRing score={cluster.risk_score} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <p className="text-sm font-semibold text-foreground truncate">{cluster.name}</p>
            <span className={clsx('text-[10px] font-medium capitalize', statusColor[cluster.status] ?? 'text-muted-foreground')}>
              ● {cluster.status}
            </span>
          </div>
          <p className="text-[10px] text-muted-foreground mb-2">
            {cluster.provider} · {cluster.environment} · {cluster.region || 'no region'}
          </p>
          <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
            <span>{cluster.node_count} nodes</span>
            <span>{cluster.pod_count} pods</span>
            {cluster.findings_count > 0 && (
              <span className="text-red-400 font-medium">{cluster.findings_count} open findings</span>
            )}
          </div>
          {cluster.last_scan && (
            <p className="text-[10px] text-muted-foreground mt-1">
              Last scan: {fmtDate(cluster.last_scan)}
            </p>
          )}
        </div>

        <button
          onClick={e => { e.stopPropagation(); onScan(); }}
          disabled={scanning || cluster.status === 'disconnected'}
          className="flex-shrink-0 flex items-center gap-1 px-2.5 py-1.5 text-[11px] rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/20 transition-colors disabled:opacity-40"
        >
          <Play className={clsx('w-3 h-3', scanning && 'animate-spin')} />
          {scanning ? 'Scanning…' : 'Scan'}
        </button>
      </div>
    </button>
  );
}

// ─── Stats strip ──────────────────────────────────────────────────────────────

function StatsStrip({ stats }: { stats: any }) {
  const items = [
    { label: 'Critical', value: stats?.by_severity?.critical ?? 0, cls: 'text-red-400' },
    { label: 'High',     value: stats?.by_severity?.high ?? 0,     cls: 'text-orange-400' },
    { label: 'Medium',   value: stats?.by_severity?.medium ?? 0,   cls: 'text-yellow-400' },
    { label: 'Low',      value: stats?.by_severity?.low ?? 0,      cls: 'text-blue-400' },
  ];
  return (
    <div className="grid grid-cols-4 gap-2">
      {items.map(it => (
        <div key={it.label} className="card-base px-3 py-2.5 text-center">
          <div className={clsx('text-2xl font-bold tabular-nums', it.cls)}>{it.value}</div>
          <div className="text-[11px] text-muted-foreground">{it.label}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Finding row ─────────────────────────────────────────────────────────────

function FindingRow({
  finding, onSuppress, onResolve, expanded, onToggle,
}: {
  finding: any;
  onSuppress: () => void;
  onResolve: () => void;
  expanded: boolean;
  onToggle: () => void;
}) {
  const sev = finding.severity as string;

  return (
    <>
      <tr
        onClick={onToggle}
        className="border-b border-border/50 hover:bg-white/2 cursor-pointer transition-colors"
      >
        <td className="px-3 py-2.5">
          <span className={clsx(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border',
            SEV_BG[sev],
            SEV_COLOR[sev],
          )}>
            <span className={clsx('w-1.5 h-1.5 rounded-full', SEV_DOT[sev])} />
            {sev}
          </span>
        </td>
        <td className="px-3 py-2.5">
          <p className="text-xs text-foreground font-medium leading-snug">{finding.title}</p>
          {finding.namespace && (
            <p className="text-[10px] text-muted-foreground mt-0.5">ns: {finding.namespace}</p>
          )}
        </td>
        <td className="px-3 py-2.5">
          <span className="text-[10px] text-muted-foreground">
            {CAT_LABEL[finding.category] ?? finding.category}
          </span>
        </td>
        <td className="px-3 py-2.5">
          {finding.resource_kind && (
            <span className="text-[10px] font-mono text-muted-foreground">
              {finding.resource_kind}/{finding.resource_name}
            </span>
          )}
        </td>
        <td className="px-3 py-2.5">
          {finding.cis_control && (
            <span className="text-[10px] font-mono text-blue-400/80">{finding.cis_control}</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-[10px] text-muted-foreground whitespace-nowrap">
          {fmtDate(finding.last_seen_at)}
        </td>
        <td className="px-3 py-2.5">
          {expanded ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                    : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
        </td>
      </tr>

      {expanded && (
        <tr className="border-b border-border/50 bg-white/1">
          <td colSpan={7} className="px-4 py-3">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <p className="text-[11px] font-medium text-muted-foreground mb-1">Description</p>
                <p className="text-xs text-foreground leading-relaxed">{finding.description || '—'}</p>
              </div>
              <div>
                <p className="text-[11px] font-medium text-green-400 mb-1">Remediation</p>
                <p className="text-xs text-foreground leading-relaxed">{finding.remediation || '—'}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/50">
              <span className="text-[10px] text-muted-foreground mr-2">
                Scanner: {SCANNER_LABEL[finding.scanner] ?? finding.scanner}
                {finding.framework && ` · Framework: ${finding.framework}`}
              </span>
              <button onClick={onResolve}
                className="flex items-center gap-1 px-2.5 py-1 text-[11px] rounded-md bg-green-500/10 text-green-400 border border-green-500/20 hover:bg-green-500/20 transition-colors">
                <CheckCircle className="w-3 h-3" /> Resolve
              </button>
              <button onClick={onSuppress}
                className="flex items-center gap-1 px-2.5 py-1 text-[11px] rounded-md bg-white/5 text-muted-foreground border border-border hover:text-foreground transition-colors">
                <EyeOff className="w-3 h-3" /> Suppress
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Category summary ─────────────────────────────────────────────────────────

function CategorySummary({ by_category }: { by_category: Record<string, number> }) {
  const cats = Object.entries(by_category).sort((a, b) => b[1] - a[1]);
  if (cats.length === 0) return null;
  const max = cats[0]?.[1] ?? 1;

  return (
    <div className="card-base p-4">
      <p className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
        <BarChart3 className="w-3.5 h-3.5 text-muted-foreground" /> By Category
      </p>
      <div className="space-y-2">
        {cats.map(([cat, count]) => {
          const Icon = CAT_ICON[cat] ?? Shield;
          return (
            <div key={cat} className="flex items-center gap-2">
              <Icon className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
              <span className="text-[11px] text-muted-foreground w-40 truncate">{CAT_LABEL[cat] ?? cat}</span>
              <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                <div className="h-full rounded-full bg-blue-500/60" style={{ width: `${(count / max) * 100}%` }} />
              </div>
              <span className="text-[11px] font-medium text-foreground w-6 text-right">{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Scan history mini-list ───────────────────────────────────────────────────

function ScanHistory({ clusterId }: { clusterId: string }) {
  const { data: raw } = useApi<any>(`/k8s/clusters/${clusterId}/scan-history?limit=5`);
  const history = raw?.data ?? raw ?? [];

  if (!history.length) return null;

  return (
    <div className="card-base p-4">
      <p className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
        <Clock className="w-3.5 h-3.5 text-muted-foreground" /> Recent Scans
      </p>
      <div className="space-y-2">
        {history.map((scan: any) => (
          <div key={scan.id} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {scan.status === 'completed'
                ? <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                : scan.status === 'running'
                  ? <RefreshCw className="w-3.5 h-3.5 text-blue-400 animate-spin" />
                  : <AlertTriangle className="w-3.5 h-3.5 text-red-400" />}
              <span className="text-[10px] text-muted-foreground">{fmtDate(scan.completed_at ?? scan.started_at)}</span>
            </div>
            <div className="flex items-center gap-3 text-[10px]">
              <span className="text-foreground">{scan.findings_count} findings</span>
              {scan.risk_score !== null && (
                <span className="font-medium" style={{
                  color: scan.risk_score >= 70 ? '#ef4444' : scan.risk_score >= 40 ? '#f97316' : '#22c55e'
                }}>
                  Risk {Math.round(scan.risk_score)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function KubernetesSecurity() {
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const [scanningCluster, setScanningCluster] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [severityFilter, setSeverityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('open');
  const [page, setPage] = useState(1);
  const [expandedFinding, setExpandedFinding] = useState<string | null>(null);

  const PAGE_SIZE = 20;

  const { data: clustersRaw, loading: clustersLoading, refetch: refetchClusters } =
    useApi<any>('/k8s/clusters');
  const clusters: any[] = clustersRaw?.data ?? clustersRaw ?? [];

  const statsQs = new URLSearchParams();
  if (selectedCluster) statsQs.set('cluster_id', selectedCluster);
  const { data: statsRaw, refetch: refetchStats } =
    useApi<any>(`/k8s/findings/stats?${statsQs}`);
  const stats = statsRaw?.data ?? statsRaw;

  const findingsQs = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
  if (selectedCluster) findingsQs.set('cluster_id', selectedCluster);
  if (severityFilter) findingsQs.set('severity', severityFilter);
  if (categoryFilter) findingsQs.set('category', categoryFilter);
  if (statusFilter)   findingsQs.set('status', statusFilter);
  const { data: findingsRaw, loading: findingsLoading, refetch: refetchFindings } =
    useApi<any>(`/k8s/findings?${findingsQs}`);
  const findingsResult = findingsRaw?.data ?? findingsRaw;
  const findings: any[] = findingsResult?.data ?? [];
  const findingsTotal = findingsResult?.total ?? 0;
  const findingsPages = findingsResult?.pages ?? 1;

  const handleScan = useCallback(async (clusterId: string) => {
    setScanningCluster(clusterId);
    try {
      await apiPost(`/k8s/clusters/${clusterId}/scan`, {});
      setTimeout(() => {
        refetchClusters();
        refetchStats();
        refetchFindings();
      }, 2000);
    } catch (e) {
      console.error('Scan failed', e);
    } finally {
      setTimeout(() => setScanningCluster(null), 3000);
    }
  }, [refetchClusters, refetchStats, refetchFindings]);

  const handleSuppress = useCallback(async (findingId: string) => {
    try {
      await apiPatch(`/k8s/findings/${findingId}/suppress`, {});
      refetchFindings();
    } catch (e) {
      console.error('Suppress failed', e);
    }
  }, [refetchFindings]);

  const handleResolve = useCallback(async (findingId: string) => {
    try {
      await apiPatch(`/k8s/findings/${findingId}/resolve`, {});
      refetchFindings();
      refetchStats();
    } catch (e) {
      console.error('Resolve failed', e);
    }
  }, [refetchFindings, refetchStats]);

  const selectedClusterObj = clusters.find(c => c.id === selectedCluster);

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-bold text-foreground flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-indigo-500/15 flex items-center justify-center">
              <Layers className="w-4 h-4 text-indigo-400" />
            </div>
            Kubernetes Security
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {clusters.length} cluster{clusters.length !== 1 ? 's' : ''} monitored
            {stats && ` · ${stats.total_findings ?? 0} open findings`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowFilters(f => !f)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors',
              showFilters ? 'border-blue-500/40 text-blue-400 bg-blue-500/10' : 'border-border text-muted-foreground hover:text-foreground',
            )}>
            <Filter className="w-3.5 h-3.5" /> Filters
          </button>
          <button onClick={() => { refetchClusters(); refetchStats(); refetchFindings(); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      {/* ── Severity stats ── */}
      {stats && <StatsStrip stats={stats} />}

      {/* ── Main grid ── */}
      <div className="grid lg:grid-cols-[280px_1fr] gap-4">

        {/* Left: Cluster list */}
        <div className="space-y-2">
          <p className="text-[11px] font-medium text-muted-foreground px-1">Clusters</p>
          {clustersLoading ? (
            [...Array(3)].map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)
          ) : clusters.length === 0 ? (
            <div className="card-base p-6 text-center">
              <Server className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-50" />
              <p className="text-xs font-medium text-foreground mb-1">No clusters connected</p>
              <p className="text-[10px] text-muted-foreground">Add Kubernetes integrations to start scanning.</p>
            </div>
          ) : (
            <>
              {/* "All clusters" option */}
              <button
                onClick={() => { setSelectedCluster(null); setPage(1); }}
                className={clsx(
                  'w-full text-left px-3 py-2 rounded-lg text-xs border transition-colors',
                  !selectedCluster
                    ? 'border-blue-500/40 text-blue-400 bg-blue-500/8'
                    : 'border-border text-muted-foreground hover:text-foreground',
                )}>
                All Clusters ({clusters.length})
              </button>

              {clusters.map(c => (
                <ClusterCard
                  key={c.id}
                  cluster={c}
                  selected={selectedCluster === c.id}
                  onSelect={() => { setSelectedCluster(c.id); setPage(1); }}
                  onScan={() => handleScan(c.id)}
                  scanning={scanningCluster === c.id}
                />
              ))}
            </>
          )}

          {/* Category breakdown */}
          {stats?.by_category && Object.keys(stats.by_category).length > 0 && (
            <CategorySummary by_category={stats.by_category} />
          )}

          {/* Scan history for selected cluster */}
          {selectedCluster && <ScanHistory clusterId={selectedCluster} />}
        </div>

        {/* Right: Findings panel */}
        <div className="space-y-3">
          {/* Selected cluster header */}
          {selectedClusterObj && (
            <div className="card-base p-3 flex items-center gap-3">
              <RiskRing score={selectedClusterObj.risk_score} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-foreground">{selectedClusterObj.name}</p>
                <p className="text-[10px] text-muted-foreground">
                  {selectedClusterObj.provider} · v{selectedClusterObj.k8s_version ?? '?'}
                  {selectedClusterObj.api_server_url && (
                    <> · <span className="font-mono">{selectedClusterObj.api_server_url}</span></>
                  )}
                </p>
                {stats && <SevBar by_severity={stats.by_severity} />}
              </div>
            </div>
          )}

          {/* Filters */}
          {showFilters && (
            <div className="card-base p-3 grid sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Severity</label>
                <select value={severityFilter} onChange={e => { setSeverityFilter(e.target.value); setPage(1); }}
                  className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
                  <option value="">All Severities</option>
                  {['critical','high','medium','low','info'].map(s => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Category</label>
                <select value={categoryFilter} onChange={e => { setCategoryFilter(e.target.value); setPage(1); }}
                  className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
                  <option value="">All Categories</option>
                  {Object.entries(CAT_LABEL).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Status</label>
                <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
                  className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
                  <option value="">All Statuses</option>
                  {['open','resolved','suppressed'].map(s => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* Findings table */}
          <div className="card-base overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px]">
                <thead>
                  <tr className="border-b border-border bg-white/2">
                    {['Severity','Finding','Category','Resource','CIS','Last Seen',''].map(h => (
                      <th key={h} className="text-left text-[11px] font-medium text-muted-foreground px-3 py-2.5 whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {findingsLoading ? (
                    [...Array(6)].map((_, i) => (
                      <tr key={i} className="border-b border-border/50">
                        {[...Array(7)].map((_, j) => (
                          <td key={j} className="px-3 py-3">
                            <Skeleton className="h-4" />
                          </td>
                        ))}
                      </tr>
                    ))
                  ) : findings.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-16 text-center">
                        <div className="flex flex-col items-center gap-3">
                          <Shield className="w-10 h-10 text-green-400 opacity-60" />
                          <div>
                            <p className="text-sm font-medium text-foreground mb-1">
                              {statusFilter === 'open' ? 'No open findings' : 'No findings found'}
                            </p>
                            <p className="text-xs text-muted-foreground max-w-xs">
                              {clusters.length === 0
                                ? 'Connect Kubernetes clusters first, then trigger a scan.'
                                : statusFilter === 'open'
                                  ? 'Your clusters are clean! Run a scan to refresh.'
                                  : 'No findings match the current filters.'}
                            </p>
                          </div>
                          {clusters.length > 0 && (
                            <button
                              onClick={() => clusters[0] && handleScan(clusters[0].id)}
                              className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
                              <Play className="w-3.5 h-3.5" /> Scan First Cluster
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ) : (
                    findings.map(f => (
                      <FindingRow
                        key={f.id}
                        finding={f}
                        expanded={expandedFinding === f.id}
                        onToggle={() => setExpandedFinding(expandedFinding === f.id ? null : f.id)}
                        onSuppress={() => handleSuppress(f.id)}
                        onResolve={() => handleResolve(f.id)}
                      />
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {findingsPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                <span className="text-xs text-muted-foreground">
                  {Math.min((page - 1) * PAGE_SIZE + 1, findingsTotal)}–{Math.min(page * PAGE_SIZE, findingsTotal)} of {findingsTotal} findings
                </span>
                <div className="flex items-center gap-1">
                  <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                    className="px-2 py-1 text-xs rounded text-muted-foreground hover:text-foreground disabled:opacity-30">‹</button>
                  <span className="text-xs text-foreground px-2">{page} / {findingsPages}</span>
                  <button onClick={() => setPage(p => Math.min(findingsPages, p + 1))} disabled={page === findingsPages}
                    className="px-2 py-1 text-xs rounded text-muted-foreground hover:text-foreground disabled:opacity-30">›</button>
                </div>
              </div>
            )}
          </div>

          {/* Detection capabilities legend */}
          <div className="card-base p-4">
            <p className="text-[11px] font-semibold text-foreground mb-3">Detection Capabilities</p>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {[
                { icon: Box,     label: 'Privileged Containers',   desc: 'hostPID, privileged, runAsRoot' },
                { icon: Lock,    label: 'RBAC Misconfigurations',  desc: 'Wildcard roles, cluster-admin SAs' },
                { icon: Globe,   label: 'Exposed Services',        desc: 'LoadBalancer, NodePort, no-TLS Ingress' },
                { icon: Network, label: 'Network Policy Gaps',     desc: 'Unprotected namespaces, allow-all policies' },
                { icon: Eye,     label: 'Secrets Exposure',        desc: 'Plaintext env vars, ConfigMap secrets' },
                { icon: Shield,  label: 'CIS Benchmark',           desc: 'Resource limits, default namespace workloads' },
              ].map(item => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="flex items-start gap-2 p-2 rounded-lg bg-white/3">
                    <Icon className="w-3.5 h-3.5 text-indigo-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-[11px] font-medium text-foreground">{item.label}</p>
                      <p className="text-[10px] text-muted-foreground">{item.desc}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-3 pt-3 border-t border-border/50 flex flex-wrap gap-2">
              <p className="text-[10px] text-muted-foreground mr-1">External scanners (if installed):</p>
              {['Kubescape', 'kube-bench', 'kube-hunter'].map(s => (
                <span key={s} className="px-2 py-0.5 text-[10px] rounded-full border border-indigo-500/30 text-indigo-400 bg-indigo-500/10">
                  {s}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
