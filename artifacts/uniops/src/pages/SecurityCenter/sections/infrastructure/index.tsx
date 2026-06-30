import { useMemo, useState } from 'react';
import { clsx } from 'clsx';
import { motion } from 'framer-motion';
import {
  Cloud, Server, Cpu, Container, Monitor,
  ShieldAlert, RefreshCw, Filter, X, Activity,
} from 'lucide-react';
import { useApi } from '@/hooks/use-api';
import InfraProviders  from './InfraProviders';
import InfraInventory  from './InfraInventory';
import InfraHealth     from './InfraHealth';
import InfraCharts     from './InfraCharts';
import InfraCost       from './InfraCost';
import InfraAlerts     from './InfraAlerts';

/* ── helpers ─────────────────────────────────────────────────────────── */
function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function fmtDate(d?: string) {
  if (!d) return '—';
  return new Date(d).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="h-px flex-1 bg-white/6" />
      <span className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-widest">{label}</span>
      <div className="h-px flex-1 bg-white/6" />
    </div>
  );
}

/* ── KPI card ────────────────────────────────────────────────────────── */
interface KpiDef {
  label: string; value: string | number;
  icon: React.ReactNode; color: string; sub?: string; alarm?: boolean;
}

function KpiCard({ k, idx }: { k: KpiDef; idx: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.04 }}
      className={clsx('card-base p-4 border',
        k.alarm ? 'border-red-500/25 bg-red-500/5' : 'border-transparent')}
    >
      <div className="flex items-start justify-between mb-2">
        <span className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', k.color)}>
          {k.icon}
        </span>
        {k.alarm && <span className="w-2 h-2 rounded-full bg-red-400 mt-1 animate-pulse" />}
      </div>
      <p className="text-2xl font-bold text-foreground leading-none">{k.value}</p>
      <p className="text-xs text-muted-foreground mt-1">{k.label}</p>
      {k.sub && <p className="text-[10px] text-muted-foreground/60 mt-0.5">{k.sub}</p>}
    </motion.div>
  );
}

/* ── Filter bar ──────────────────────────────────────────────────────── */
const PROVIDER_OPTS    = ['aws','azure','gcp','kubernetes','vmware','on-prem'];
const ENV_OPTS         = ['production','staging','development','test'];
const STATUS_OPTS      = ['active','stopped','degraded','offline'];
const SEVERITY_OPTS    = ['critical','high','medium','low'];

function FilterBar({
  filters, onChange, onClear,
}: {
  filters: Record<string, string>;
  onChange: (k: string, v: string) => void;
  onClear: () => void;
}) {
  const activeCount = Object.values(filters).filter(Boolean).length;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {([
        { key: 'provider', label: 'Provider',    opts: PROVIDER_OPTS },
        { key: 'env',      label: 'Environment', opts: ENV_OPTS      },
        { key: 'status',   label: 'Status',      opts: STATUS_OPTS   },
        { key: 'severity', label: 'Severity',    opts: SEVERITY_OPTS },
      ] as const).map(({ key, label, opts }) => (
        <select key={key}
          value={filters[key] ?? ''}
          onChange={e => onChange(key, e.target.value)}
          className="h-7 px-2 text-xs rounded-lg bg-white/5 border border-white/10 text-muted-foreground
                     hover:border-white/20 focus:outline-none focus:border-blue-500/50 cursor-pointer"
        >
          <option value="">{label}</option>
          {opts.map(o => (
            <option key={o} value={o} className="bg-[hsl(230_15%_10%)] capitalize">{o}</option>
          ))}
        </select>
      ))}
      {activeCount > 0 && (
        <button onClick={onClear}
          className="h-7 px-2 text-xs rounded-lg bg-red-500/10 border border-red-500/20
                     text-red-400 hover:bg-red-500/20 flex items-center gap-1 transition-colors">
          <X className="w-3 h-3" /> Clear ({activeCount})
        </button>
      )}
    </div>
  );
}

/* ── Main page ───────────────────────────────────────────────────────── */
export default function InfrastructurePage() {
  const [filters, setFilters] = useState<Record<string, string>>({});

  /* ── API calls ──────────────────────────────────────────────────────── */
  const { data: clustersRaw,  loading: clustersLoading  } = useApi('/clusters');
  const { data: assetsRaw,    loading: assetsLoading    } = useApi('/assets');
  const { data: syncRaw,      loading: syncLoading      } = useApi('/assets/sync/status');
  const { data: postureRaw,   loading: postureLoading   } = useApi('/security-posture/summary');
  const { data: vulnRaw,      loading: vulnLoading      } = useApi('/vulnerabilities/stats');
  const { data: costSumRaw,   loading: costSumLoading   } = useApi('/costs/summary');
  const { data: costBrkRaw,   loading: costBrkLoading   } = useApi('/costs/breakdown');
  const { data: alertsRaw,    loading: alertsLoading    } = useApi('/alerts');
  const { data: podsRaw,      loading: podsLoading      } = useApi('/kubernetes/pods?page_size=100');

  /* ── Normalise arrays ───────────────────────────────────────────────── */
  const clusters = useMemo(() => {
    const raw = clustersRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [clustersRaw]);

  const assets = useMemo(() => {
    const raw = assetsRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [assetsRaw]);

  const alerts = useMemo(() => {
    const raw = alertsRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [alertsRaw]);

  const pods = useMemo(() => {
    const raw = podsRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [podsRaw]);

  const syncStatus  = (syncRaw  ?? null) as any;
  const postureData = (postureRaw ?? {}) as any;
  const vulnStats   = (vulnRaw  ?? {}) as any;
  const costSummary = (costSumRaw ?? null) as any;
  const costBreakdown = (costBrkRaw ?? null) as any;

  /* ── Apply client filters ───────────────────────────────────────────── */
  const filteredClusters = useMemo(() =>
    clusters.filter((c: any) => {
      if (filters.provider && (c.provider ?? '').toLowerCase() !== filters.provider) return false;
      if (filters.env && (c.environment ?? '').toLowerCase() !== filters.env) return false;
      if (filters.status && (c.status ?? '').toLowerCase() !== filters.status) return false;
      return true;
    }), [clusters, filters]);

  const filteredAssets = useMemo(() =>
    assets.filter((a: any) => {
      if (filters.provider && (a.cloud_provider ?? a.provider ?? '').toLowerCase() !== filters.provider) return false;
      if (filters.env && (a.environment ?? '').toLowerCase() !== filters.env) return false;
      if (filters.status && (a.status ?? '').toLowerCase() !== filters.status) return false;
      return true;
    }), [assets, filters]);

  /* ── Derived KPI values ─────────────────────────────────────────────── */
  const cloudAccounts = useMemo(() => {
    const set = new Set<string>();
    for (const a of assets) {
      const id = a.account_id ?? a.subscription_id ?? a.project_id;
      if (id) set.add(id);
    }
    return set.size || clusters.length;
  }, [assets, clusters]);

  const environments = useMemo(() => {
    const set = new Set<string>();
    for (const a of assets) { if (a.environment) set.add(a.environment); }
    for (const c of clusters) { if (c.environment) set.add(c.environment); }
    return set.size;
  }, [assets, clusters]);

  const totalNodes      = useMemo(() => clusters.reduce((s: number, c: any) => s + (c.node_count ?? 0), 0), [clusters]);
  const totalPods       = useMemo(() => clusters.reduce((s: number, c: any) => s + (c.pod_count ?? 0), 0), [clusters]);
  const totalContainers = useMemo(() =>
    pods.reduce((s: number, p: any) => s + ((p.containers as any[])?.length ?? 1), 0) || totalPods,
    [pods, totalPods],
  );
  const totalVMs = useMemo(() =>
    assets.filter((a: any) => ['vm','virtual_machine','instance','ec2'].some(k =>
      (a.asset_type ?? a.type ?? '').toLowerCase().includes(k)
    )).length,
    [assets],
  );
  const riskScore  = Math.round(postureData.current_score ?? 0);
  const lastSync   = syncStatus?.last_sync ?? syncStatus?.updated_at
    ?? clusters.reduce((latest: string | undefined, c: any) => {
      const t = c.last_health_check ?? c.updated_at;
      return !latest || (t && t > latest) ? t : latest;
    }, undefined);

  const anyLoading = clustersLoading || assetsLoading;

  const kpis: KpiDef[] = [
    { label: 'Cloud Accounts',     value: clustersLoading ? '…' : cloudAccounts,    icon: <Cloud    className="w-4 h-4 text-blue-400"   />, color: 'bg-blue-500/10'   },
    { label: 'Environments',       value: assetsLoading   ? '…' : environments || '—', icon: <Activity className="w-4 h-4 text-teal-400"   />, color: 'bg-teal-500/10'   },
    { label: 'Active Clusters',    value: clustersLoading ? '…' : clusters.length,  icon: <Server   className="w-4 h-4 text-purple-400" />, color: 'bg-purple-500/10' },
    { label: 'Running Nodes',      value: clustersLoading ? '…' : totalNodes || '—',icon: <Cpu      className="w-4 h-4 text-cyan-400"   />, color: 'bg-cyan-500/10'   },
    { label: 'Running Containers', value: podsLoading     ? '…' : totalContainers || '—', icon: <Container className="w-4 h-4 text-green-400"  />, color: 'bg-green-500/10'  },
    { label: 'Virtual Machines',   value: assetsLoading   ? '…' : totalVMs || '—',  icon: <Monitor  className="w-4 h-4 text-orange-400" />, color: 'bg-orange-500/10' },
    {
      label: 'Infrastructure Risk Score', value: postureLoading ? '…' : riskScore,
      icon: <ShieldAlert className="w-4 h-4 text-red-400" />, color: 'bg-red-500/10',
      alarm: !postureLoading && riskScore > 0 && riskScore < 60,
    },
    {
      label: 'Last Infrastructure Sync',
      value: syncLoading || clustersLoading ? '…' : (lastSync ? fmtDate(lastSync) : 'Never'),
      icon: <RefreshCw className="w-4 h-4 text-indigo-400" />, color: 'bg-indigo-500/10',
      sub: syncStatus?.status ? `Status: ${syncStatus.status}` : undefined,
    },
  ];

  return (
    <div className="space-y-6 pb-8">

      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
        <div>
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Cloud className="w-5 h-5 text-blue-400" />
            Infrastructure
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {anyLoading ? 'Loading…' :
              `${clusters.length} clusters · ${assets.length} assets across ${environments || '—'} environment${environments !== 1 ? 's' : ''}`}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
          <FilterBar
            filters={filters}
            onChange={(k, v) => setFilters(prev => ({ ...prev, [k]: v }))}
            onClear={() => setFilters({})}
          />
        </div>
      </div>

      {/* KPI bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-3">
        {kpis.map((k, i) => <KpiCard key={k.label} k={k} idx={i} />)}
      </div>

      {/* Connected Providers */}
      <SectionDivider label="Cloud Providers" />
      <InfraProviders
        clusters={clusters}
        assets={assets}
        syncStatus={syncStatus}
        vulnStats={vulnStats}
        loading={anyLoading}
      />

      {/* Charts */}
      <SectionDivider label="Analytics" />
      <InfraCharts
        clusters={filteredClusters}
        assets={filteredAssets}
        loading={anyLoading}
      />

      {/* Inventory + Accounts */}
      <SectionDivider label="Inventory" />
      <InfraInventory
        clusters={filteredClusters}
        assets={filteredAssets}
        loading={anyLoading}
      />

      {/* Health + Security Summary */}
      <SectionDivider label="Health & Security" />
      <InfraHealth
        clusters={filteredClusters}
        assets={filteredAssets}
        vulnStats={vulnStats}
        loading={anyLoading || vulnLoading}
      />

      {/* Cloud Cost — conditional on backend returning cost data */}
      <SectionDivider label="Cost" />
      <InfraCost
        costSummary={costSummary}
        costBreakdown={costBreakdown}
        loading={costSumLoading || costBrkLoading}
      />

      {/* Alerts */}
      <SectionDivider label="Alerts & Events" />
      <InfraAlerts
        clusters={filteredClusters}
        syncStatus={syncStatus}
        alerts={alerts}
        loading={anyLoading || alertsLoading}
      />
    </div>
  );
}
