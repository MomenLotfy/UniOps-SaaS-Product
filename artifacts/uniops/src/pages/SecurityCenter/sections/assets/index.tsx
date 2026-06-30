import { useState, useCallback, useEffect, useMemo } from 'react';
import { clsx } from 'clsx';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Server, RefreshCw, Search, ChevronLeft, ChevronRight,
  Cloud, Database, Box, Layers, HardDrive,
  AlertTriangle, CheckCircle, Clock, X,
  ChevronDown, ChevronUp, Shield, Play, Activity,
  List, Grid3X3, Network, Filter, Star, Globe,
  GitBranch, User, Cpu, Container, Image, ArchiveX,
  BarChart3, Zap, TrendingUp,
} from 'lucide-react';
import { useApi, apiPost } from '@/hooks/use-api';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';
import AssetGraph    from '../AssetGraph';
import AssetKPIs     from './AssetKPIs';
import AssetCharts   from './AssetCharts';
import AssetDrawer   from './AssetDrawer';
import AssetCardView from './AssetCardView';

// ── helpers ────────────────────────────────────────────────────────────────────
function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000)     return 'just now';
  if (diff < 3_600_000)  return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)}d ago`;
  return new Date(iso).toLocaleDateString();
}

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
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

// ── Risk / Env visuals ─────────────────────────────────────────────────────────
const RISK_BADGE: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border border-red-500/30',
  high:     'bg-orange-500/15 text-orange-400 border border-orange-500/30',
  medium:   'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
  low:      'bg-blue-500/15 text-blue-400 border border-blue-500/30',
  none:     'bg-green-500/15 text-green-400 border border-green-500/30',
};
const RISK_DOT: Record<string, string> = {
  critical: 'bg-red-500', high: 'bg-orange-500', medium: 'bg-yellow-500',
  low: 'bg-blue-500', none: 'bg-green-500',
};
const ENV_COLOR: Record<string, string> = {
  production: 'text-red-400', staging: 'text-yellow-400',
  development: 'text-green-400', unknown: 'text-muted-foreground',
};

// ── Type metadata ──────────────────────────────────────────────────────────────
const TYPE_LABEL: Record<string, string> = {
  github_repo: 'GitHub Repo', gitlab_repo: 'GitLab Repo',
  aws_ec2: 'EC2', aws_s3: 'S3 Bucket',
  aws_iam_user: 'IAM User', aws_iam_role: 'IAM Role',
  aws_rds: 'RDS', docker_image: 'Docker Image',
  k8s_cluster: 'K8s Cluster', k8s_namespace: 'Namespace', k8s_pod: 'Pod',
};
const SOURCE_LABEL: Record<string, string> = {
  github: 'GitHub', gitlab: 'GitLab', aws: 'AWS', kubernetes: 'Kubernetes', docker: 'Docker',
};

function TypeIcon({ type }: { type: string }) {
  const cls = 'w-4 h-4 flex-shrink-0';
  switch (type) {
    case 'github_repo':
    case 'gitlab_repo':   return <GitBranch className={clsx(cls, 'text-purple-400')} />;
    case 'aws_ec2':       return <Cloud     className={clsx(cls, 'text-orange-400')} />;
    case 'aws_s3':        return <HardDrive className={clsx(cls, 'text-yellow-400')} />;
    case 'aws_iam_user':
    case 'aws_iam_role':  return <User      className={clsx(cls, 'text-blue-400')}   />;
    case 'aws_rds':       return <Database  className={clsx(cls, 'text-cyan-400')}   />;
    case 'docker_image':  return <Box       className={clsx(cls, 'text-sky-400')}    />;
    case 'k8s_cluster':
    case 'k8s_namespace': return <Layers    className={clsx(cls, 'text-indigo-400')} />;
    case 'k8s_pod':       return <Server    className={clsx(cls, 'text-fuchsia-400')}/>;
    default:              return <Globe     className={clsx(cls, 'text-muted-foreground')} />;
  }
}

// ── Sort header ────────────────────────────────────────────────────────────────
function TH({ label, field, sort, setSort }: {
  label: string; field: string;
  sort: { by: string; dir: string };
  setSort: (s: { by: string; dir: string }) => void;
}) {
  const active = sort.by === field;
  return (
    <th className={clsx(
      'text-left text-[10px] font-semibold text-muted-foreground px-3 py-2.5 cursor-pointer select-none whitespace-nowrap uppercase tracking-wide',
      'hover:text-foreground transition-colors', active && 'text-foreground',
    )}
      onClick={() => setSort(active
        ? { by: field, dir: sort.dir === 'asc' ? 'desc' : 'asc' }
        : { by: field, dir: 'desc' }
      )}>
      <span className="flex items-center gap-1">
        {label}
        {active
          ? sort.dir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
          : <span className="w-3 h-3 opacity-0">▲</span>}
      </span>
    </th>
  );
}

// ── Risk score bar ─────────────────────────────────────────────────────────────
function RiskBar({ score }: { score?: number }) {
  if (score == null) return null;
  const color = score >= 80 ? 'bg-red-500' : score >= 60 ? 'bg-orange-500' : score >= 40 ? 'bg-yellow-500' : 'bg-green-500';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-12 rounded-full bg-white/6 overflow-hidden">
        <div className={clsx('h-full rounded-full', color)} style={{ width: `${score}%` }} />
      </div>
      <span className="text-[10px] font-mono text-muted-foreground">{Math.round(score)}</span>
    </div>
  );
}

// ── Asset type overview ────────────────────────────────────────────────────────
const ASSET_TYPE_DEFS = [
  { key: 'aws_ec2',        label: 'Virtual Machines', icon: <Cloud      className="w-3.5 h-3.5 text-orange-400" />, color: 'text-orange-400' },
  { key: 'docker_image',   label: 'Containers',       icon: <Box        className="w-3.5 h-3.5 text-sky-400"    />, color: 'text-sky-400'    },
  { key: 'k8s_pod',        label: 'K8s Pods',         icon: <Server     className="w-3.5 h-3.5 text-fuchsia-400"/>, color: 'text-fuchsia-400'},
  { key: 'k8s_cluster',    label: 'Nodes/Clusters',   icon: <Layers     className="w-3.5 h-3.5 text-indigo-400" />, color: 'text-indigo-400' },
  { key: 'image',          label: 'Images',           icon: <Image      className="w-3.5 h-3.5 text-green-400"  />, color: 'text-green-400'  },
  { key: 'github_repo',    label: 'Repositories',     icon: <GitBranch  className="w-3.5 h-3.5 text-purple-400" />, color: 'text-purple-400' },
  { key: 'aws_rds',        label: 'Databases',        icon: <Database   className="w-3.5 h-3.5 text-cyan-400"   />, color: 'text-cyan-400'   },
  { key: 'aws_s3',         label: 'Buckets',          icon: <ArchiveX   className="w-3.5 h-3.5 text-yellow-400" />, color: 'text-yellow-400' },
  { key: 'function',       label: 'Functions',        icon: <Zap        className="w-3.5 h-3.5 text-pink-400"   />, color: 'text-pink-400'   },
  { key: 'load_balancer',  label: 'Load Balancers',   icon: <Network    className="w-3.5 h-3.5 text-teal-400"   />, color: 'text-teal-400'   },
];

function AssetTypeOverview({
  stats, assets, onFilter, activeType,
}: {
  stats: any; assets: any[]; onFilter: (t: string) => void; activeType: string;
}) {
  const s = (stats ?? {}) as any;
  const byType = s.by_type ?? {};

  // Fallback: count from current page assets
  const fallbackCounts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const a of assets) { const k = a.type ?? ''; m[k] = (m[k] ?? 0) + 1; }
    return m;
  }, [assets]);

  return (
    <div className="grid grid-cols-5 xl:grid-cols-10 gap-2">
      {ASSET_TYPE_DEFS.map(def => {
        const count = byType[def.key] ?? fallbackCounts[def.key] ?? 0;
        const active = activeType === def.key;
        return (
          <button key={def.key} onClick={() => onFilter(active ? '' : def.key)}
            className={clsx(
              'card-base p-3 text-center flex flex-col items-center gap-1.5 transition-all border',
              active ? 'border-blue-500/40 bg-blue-500/8' : 'border-transparent hover:border-white/10 hover:bg-white/3',
            )}>
            {def.icon}
            <p className={clsx('text-sm font-bold', def.color)}>{count || '—'}</p>
            <p className="text-[8px] text-muted-foreground leading-tight">{def.label}</p>
          </button>
        );
      })}
    </div>
  );
}

// ── High risk panel ────────────────────────────────────────────────────────────
function HighRiskPanel({ assets, loading, onSelect }: { assets: any[]; loading: boolean; onSelect: (a: any) => void }) {
  const highRisk = useMemo(() =>
    assets.filter((a: any) => ['critical','high'].includes((a.risk_level ?? '').toLowerCase()))
      .sort((a: any, b: any) => {
        const ord = { critical: 0, high: 1 };
        return (ord[a.risk_level as 'critical' | 'high'] ?? 2) - (ord[b.risk_level as 'critical' | 'high'] ?? 2);
      }).slice(0, 8),
    [assets],
  );

  if (loading) return <Skeleton className="h-40 w-full rounded-xl" />;
  if (highRisk.length === 0) return (
    <div className="card-base py-6 text-center">
      <CheckCircle className="w-6 h-6 text-green-400 mx-auto mb-1.5 opacity-60" />
      <p className="text-xs font-medium text-foreground">No high-risk assets</p>
    </div>
  );

  return (
    <div className="card-base overflow-hidden">
      <div className="p-3 border-b border-white/6 flex items-center gap-2">
        <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
        <p className="text-xs font-semibold text-foreground">Highest Risk Assets</p>
        <span className="ml-auto text-[10px] text-muted-foreground">{highRisk.length} items</span>
      </div>
      <div className="divide-y divide-white/5">
        {highRisk.map((a: any) => (
          <div key={a.id} onClick={() => onSelect(a)}
            className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/3 cursor-pointer transition-colors group">
            <TypeIcon type={a.type} />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-foreground truncate">{a.name}</p>
              <p className="text-[9px] text-muted-foreground">{TYPE_LABEL[a.type] ?? a.type} · {a.environment ?? '—'}</p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {a.risk_score != null && <RiskBar score={a.risk_score} />}
              <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full font-bold border uppercase', RISK_BADGE[a.risk_level ?? 'none'])}>
                {a.risk_level}
              </span>
              {(a.open_findings ?? 0) > 0 && (
                <span className="text-[9px] text-orange-400 font-mono">{a.open_findings}f</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Recently discovered timeline ───────────────────────────────────────────────
function RecentTimeline({ assets, loading, onSelect }: { assets: any[]; loading: boolean; onSelect: (a: any) => void }) {
  const recent = useMemo(() =>
    [...assets].sort((a: any, b: any) => {
      const ta = a.last_synced_at ?? a.created_at ?? '';
      const tb = b.last_synced_at ?? b.created_at ?? '';
      return tb.localeCompare(ta);
    }).slice(0, 10),
    [assets],
  );

  if (loading) return <Skeleton className="h-40 w-full rounded-xl" />;
  if (recent.length === 0) return (
    <div className="card-base py-6 text-center">
      <Clock className="w-6 h-6 text-muted-foreground mx-auto mb-1.5 opacity-30" />
      <p className="text-xs font-medium text-foreground">No recent assets</p>
    </div>
  );

  return (
    <div className="card-base overflow-hidden">
      <div className="p-3 border-b border-white/6 flex items-center gap-2">
        <Clock className="w-3.5 h-3.5 text-purple-400" />
        <p className="text-xs font-semibold text-foreground">Recently Discovered</p>
        <span className="ml-auto text-[10px] text-muted-foreground">{recent.length} items</span>
      </div>
      <div className="divide-y divide-white/5">
        {recent.map((a: any) => (
          <div key={a.id} onClick={() => onSelect(a)}
            className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/3 cursor-pointer transition-colors">
            <div className="flex-shrink-0 relative">
              <TypeIcon type={a.type} />
              <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-purple-400 ring-1 ring-[hsl(230_15%_9%)]" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-foreground truncate">{a.name}</p>
              <p className="text-[9px] text-muted-foreground">{SOURCE_LABEL[a.source] ?? a.source} · {TYPE_LABEL[a.type] ?? a.type}</p>
            </div>
            <span className="text-[9px] text-muted-foreground flex-shrink-0">
              {fmtDate(a.last_synced_at ?? a.created_at)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Empty state ────────────────────────────────────────────────────────────────
function EmptyState({ canSync, onSync }: { canSync: boolean; onSync: () => void }) {
  return (
    <div className="card-base py-16 text-center border border-dashed border-white/10">
      <div className="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center mx-auto mb-4">
        <Server className="w-7 h-7 text-muted-foreground opacity-50" />
      </div>
      <p className="text-base font-semibold text-foreground mb-1">No assets discovered yet</p>
      <p className="text-xs text-muted-foreground/70 max-w-sm mx-auto mb-6">
        Connect your cloud providers, Kubernetes clusters, and Git repositories to automatically populate your asset inventory.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {[
          { label: 'Connect Cloud Provider',    icon: <Cloud     className="w-3.5 h-3.5" /> },
          { label: 'Connect Kubernetes',        icon: <Layers    className="w-3.5 h-3.5" /> },
          { label: 'Connect Git Repository',    icon: <GitBranch className="w-3.5 h-3.5" /> },
        ].map(({ label, icon }) => (
          <button key={label}
            className="flex items-center gap-2 px-4 py-2 text-xs rounded-lg border border-white/12 text-muted-foreground hover:text-foreground hover:border-white/25 transition-colors">
            {icon} {label}
          </button>
        ))}
        {canSync && (
          <button onClick={onSync}
            className="flex items-center gap-2 px-4 py-2 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
            <Play className="w-3.5 h-3.5" /> Run First Discovery
          </button>
        )}
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────
type ViewMode = 'table' | 'cards' | 'graph';

const SOURCES  = ['', 'github', 'gitlab', 'aws', 'kubernetes', 'docker'];
const RISKS    = ['', 'critical', 'high', 'medium', 'low', 'none'];
const ENVS     = ['', 'production', 'staging', 'development', 'unknown'];
const TYPES    = ['', 'github_repo', 'gitlab_repo', 'aws_ec2', 'aws_s3', 'aws_iam_user', 'aws_iam_role', 'aws_rds', 'docker_image', 'k8s_cluster', 'k8s_namespace', 'k8s_pod'];
const STATUSES = ['', 'active', 'inactive', 'decommissioned'];
const PAGE_SIZE = 20;

export default function AssetsPage() {
  const { role }  = usePermissions();
  const canSync   = canWriteSecurity(role);

  // Filter state
  const [search,   setSearch]   = useState('');
  const [source,   setSource]   = useState('');
  const [risk,     setRisk]     = useState('');
  const [env,      setEnv]      = useState('');
  const [typeF,    setTypeF]    = useState('');
  const [status,   setStatus]   = useState('');
  const [page,     setPage]     = useState(1);
  const [sort,     setSort]     = useState({ by: 'risk_level', dir: 'desc' });

  // UI state
  const [syncing,      setSyncing]      = useState(false);
  const [syncMsg,      setSyncMsg]      = useState<{ ok: boolean; text: string } | null>(null);
  const [selected,     setSelected]     = useState<any | null>(null);
  const [showFilters,  setShowFilters]  = useState(false);
  const [viewMode,     setViewMode]     = useState<ViewMode>('table');
  const [activeTypeOv, setActiveTypeOv] = useState('');

  const resetPage = () => setPage(1);

  // ── Query string ───────────────────────────────────────────────────────────
  const qs = new URLSearchParams({
    page: String(page), page_size: String(PAGE_SIZE),
    sort_by: sort.by, sort_dir: sort.dir,
  });
  if (search) qs.set('search', search);
  if (source) qs.set('source', source);
  if (risk)   qs.set('risk_level', risk);
  if (env)    qs.set('environment', env);
  if (typeF || activeTypeOv) qs.set('type', typeF || activeTypeOv);
  if (status) qs.set('status', status);

  // ── API calls ──────────────────────────────────────────────────────────────
  const { data: raw,          loading,         refetch }            = useApi<any>(`/assets?${qs}`);
  const { data: statsRaw,                       refetch: refetchStats }   = useApi<any>('/assets/stats');
  const { data: syncStatusRaw,                  refetch: refetchSync }    = useApi<any>('/assets/sync/status');

  const result     = (raw as any)?.data ?? raw;
  const assets     = result?.data         ?? [];
  const total      = result?.total        ?? 0;
  const pages      = result?.pages        ?? 1;
  const stats      = (statsRaw as any)?.data    ?? statsRaw;
  const syncStatus = (syncStatusRaw as any)?.data ?? syncStatusRaw;

  // Poll while syncing
  useEffect(() => {
    if (!syncStatus?.running) return;
    const t = setInterval(() => { refetchSync(); refetch(); refetchStats(); }, 3000);
    return () => clearInterval(t);
  }, [syncStatus?.running]);

  // ── Sync ──────────────────────────────────────────────────────────────────
  const handleSync = useCallback(async (src?: string) => {
    setSyncing(true); setSyncMsg(null);
    try {
      await apiPost(src ? `/assets/sync/${src}` : '/assets/sync', {});
      setSyncMsg({ ok: true, text: `Sync started${src ? ` for ${SOURCE_LABEL[src] ?? src}` : ''}` });
      setTimeout(() => { refetch(); refetchStats(); refetchSync(); }, 1500);
    } catch (e: any) {
      setSyncMsg({ ok: false, text: e?.message ?? 'Sync failed' });
    } finally { setSyncing(false); }
  }, []);

  const activeFilterCount = [search, source, risk, env, typeF || activeTypeOv, status].filter(Boolean).length;

  return (
    <div className="space-y-5 pb-8">

      {/* ── Page header ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
        <div>
          <h1 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-400" />
            Asset Inventory
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {total.toLocaleString()} assets
            {syncStatus?.last_sync_at && <> · synced {fmtDate(syncStatus.last_sync_at)}</>}
            {(syncStatus?.running || syncing) && (
              <span className="inline-flex items-center gap-1 text-blue-400 ml-2">
                <Activity className="w-3 h-3 animate-pulse" /> Syncing…
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* View toggle */}
          <div className="flex items-center rounded-lg border border-white/10 overflow-hidden">
            {([
              { mode: 'table' as ViewMode, icon: <List    className="w-3.5 h-3.5" />, label: 'Table' },
              { mode: 'cards' as ViewMode, icon: <Grid3X3 className="w-3.5 h-3.5" />, label: 'Cards' },
              { mode: 'graph' as ViewMode, icon: <Network className="w-3.5 h-3.5" />, label: 'Graph' },
            ]).map(v => (
              <button key={v.mode} onClick={() => setViewMode(v.mode)}
                className={clsx(
                  'flex items-center gap-1.5 px-2.5 py-1.5 text-xs transition-colors border-r border-white/10 last:border-0',
                  viewMode === v.mode ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground',
                )}>
                {v.icon} {v.label}
              </button>
            ))}
          </div>

          {/* Filters toggle */}
          <button onClick={() => setShowFilters(f => !f)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors',
              showFilters || activeFilterCount > 0
                ? 'border-blue-500/40 text-blue-400 bg-blue-500/10'
                : 'border-white/10 text-muted-foreground hover:text-foreground',
            )}>
            <Filter className="w-3.5 h-3.5" />
            Filters
            {activeFilterCount > 0 && (
              <span className="w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-bold flex items-center justify-center">
                {activeFilterCount}
              </span>
            )}
          </button>

          <button onClick={() => { refetch(); refetchStats(); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-white/10 text-muted-foreground hover:text-foreground transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>

          {canSync && (
            <button onClick={() => handleSync()} disabled={syncing || syncStatus?.running}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-40">
              <Play className="w-3.5 h-3.5" />
              {syncing || syncStatus?.running ? 'Syncing…' : 'Sync All'}
            </button>
          )}
        </div>
      </div>

      {/* Sync feedback */}
      <AnimatePresence>
        {syncMsg && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
            className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg text-xs',
              syncMsg.ok ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400')}>
            {syncMsg.ok ? <CheckCircle className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
            {syncMsg.text}
            <button onClick={() => setSyncMsg(null)} className="ml-auto"><X className="w-3 h-3" /></button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── KPI Bar ─────────────────────────────────────────────────────────── */}
      <AssetKPIs stats={stats} loading={!stats && loading} />

      {/* ── Asset Type Overview ──────────────────────────────────────────────── */}
      <SectionDivider label="Asset Types" />
      {loading && !stats ? (
        <div className="grid grid-cols-5 xl:grid-cols-10 gap-2">
          {[...Array(10)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
      ) : (
        <AssetTypeOverview
          stats={stats}
          assets={assets}
          onFilter={t => { setActiveTypeOv(t); setTypeF(''); resetPage(); }}
          activeType={activeTypeOv}
        />
      )}

      {/* ── Search bar ──────────────────────────────────────────────────────── */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
        <input type="text" placeholder="Search by name, type, region, owner…"
          value={search}
          onChange={e => { setSearch(e.target.value); resetPage(); }}
          className="w-full pl-9 pr-10 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/50 transition-colors"
        />
        {search && (
          <button onClick={() => { setSearch(''); resetPage(); }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* ── Advanced filters ─────────────────────────────────────────────────── */}
      <AnimatePresence>
        {showFilters && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
            <div className="card-base p-4 space-y-4 border border-blue-500/15">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <Filter className="w-3.5 h-3.5" /> Advanced Filters
                </p>
                {activeFilterCount > 0 && (
                  <button onClick={() => { setSearch(''); setSource(''); setRisk(''); setEnv(''); setTypeF(''); setStatus(''); setActiveTypeOv(''); resetPage(); }}
                    className="text-[10px] text-red-400 hover:text-red-300 flex items-center gap-1">
                    <X className="w-3 h-3" /> Clear all ({activeFilterCount})
                  </button>
                )}
              </div>

              {/* Source */}
              <div>
                <p className="text-[10px] text-muted-foreground mb-2 uppercase tracking-wide font-semibold">Source / Cloud</p>
                <div className="flex flex-wrap gap-1.5">
                  {SOURCES.map(s => (
                    <button key={s} onClick={() => { setSource(s); resetPage(); }}
                      className={clsx('px-2.5 py-1 text-xs rounded-md transition-colors',
                        source === s ? 'bg-blue-600 text-white' : 'bg-white/5 text-muted-foreground hover:text-foreground')}>
                      {s ? (SOURCE_LABEL[s] ?? s) : 'All Sources'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Risk */}
              <div>
                <p className="text-[10px] text-muted-foreground mb-2 uppercase tracking-wide font-semibold">Risk Level</p>
                <div className="flex flex-wrap gap-1.5">
                  {RISKS.map(r => (
                    <button key={r} onClick={() => { setRisk(r); resetPage(); }}
                      className={clsx('flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md transition-colors',
                        risk === r ? 'bg-blue-600 text-white' : 'bg-white/5 text-muted-foreground hover:text-foreground')}>
                      {r && <span className={clsx('w-2 h-2 rounded-full', RISK_DOT[r])} />}
                      {r ? r.charAt(0).toUpperCase() + r.slice(1) : 'All Risks'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Grid filters */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Environment', opts: ENVS,     val: env,    set: (v: string) => { setEnv(v); resetPage(); }   },
                  { label: 'Asset Type',  opts: TYPES,    val: typeF,  set: (v: string) => { setTypeF(v); setActiveTypeOv(''); resetPage(); } },
                  { label: 'Status',      opts: STATUSES, val: status, set: (v: string) => { setStatus(v); resetPage(); } },
                ].map(f => (
                  <div key={f.label}>
                    <p className="text-[10px] text-muted-foreground mb-1.5 uppercase tracking-wide font-semibold">{f.label}</p>
                    <select value={f.val} onChange={e => f.set(e.target.value)}
                      className="w-full text-xs px-2.5 py-1.5 bg-white/5 border border-white/10 rounded-md text-foreground focus:outline-none focus:border-blue-500/50">
                      {f.opts.map(o => (
                        <option key={o} value={o} className="bg-[hsl(230_15%_10%)] capitalize">
                          {o ? (TYPE_LABEL[o] ?? o) : `All ${f.label}s`}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>

              {/* Per-source sync (for authorized users) */}
              {canSync && (
                <div>
                  <p className="text-[10px] text-muted-foreground mb-2 uppercase tracking-wide font-semibold">Sync by Source</p>
                  <div className="flex flex-wrap gap-1.5">
                    {['github','gitlab','aws','kubernetes','docker'].map(src => (
                      <button key={src} onClick={() => handleSync(src)} disabled={syncing || syncStatus?.running}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-white/5 text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors border border-white/8">
                        <Play className="w-2.5 h-2.5" /> {SOURCE_LABEL[src]}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Charts ──────────────────────────────────────────────────────────── */}
      {(assets.length > 0 || stats) && (
        <>
          <SectionDivider label="Analytics" />
          <AssetCharts assets={assets} stats={stats} loading={loading && !stats} />
        </>
      )}

      {/* ── High risk + Recent timeline (side by side) ────────────────────── */}
      {assets.length > 0 && (
        <>
          <SectionDivider label="Risk & Discovery" />
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <HighRiskPanel  assets={assets} loading={loading} onSelect={setSelected} />
            <RecentTimeline assets={assets} loading={loading} onSelect={setSelected} />
          </div>
        </>
      )}

      {/* ── Graph view ──────────────────────────────────────────────────────── */}
      {viewMode === 'graph' && (
        <>
          <SectionDivider label="Asset Graph" />
          <AssetGraph />
        </>
      )}

      {/* ── Inventory (table / cards) ─────────────────────────────────────── */}
      <SectionDivider label={`Inventory · ${total.toLocaleString()} assets`} />

      {/* Card view */}
      {viewMode === 'cards' && (
        <>
          <AssetCardView assets={assets} loading={loading} onSelect={setSelected} />
          {!loading && assets.length === 0 && (
            <EmptyState canSync={canSync} onSync={() => handleSync()} />
          )}
        </>
      )}

      {/* Table view */}
      {(viewMode === 'table' || viewMode === 'graph') && (
        <div className="card-base overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px]">
              <thead>
                <tr className="border-b border-white/8 bg-white/2">
                  <TH label="Asset Name"    field="name"            sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                  <TH label="Type"          field="type"            sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                  <TH label="Source"        field="source"          sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                  <TH label="Environment"   field="environment"     sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                  <TH label="Risk"          field="risk_level"      sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                  <TH label="Risk Score"    field="risk_score"      sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                  <TH label="Findings"      field="open_findings"   sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                  <TH label="Owner"         field="owner"           sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                  <TH label="Last Seen"     field="last_synced_at"  sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                  <th className="text-left text-[10px] font-semibold text-muted-foreground px-3 py-2.5 whitespace-nowrap uppercase tracking-wide">Status</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  [...Array(8)].map((_, i) => (
                    <tr key={i} className="border-b border-white/5">
                      {[...Array(11)].map((_, j) => (
                        <td key={j} className="px-3 py-3"><Skeleton className="h-3.5 w-full" /></td>
                      ))}
                    </tr>
                  ))
                ) : assets.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="py-0">
                      <EmptyState canSync={canSync} onSync={() => handleSync()} />
                    </td>
                  </tr>
                ) : assets.map((a: any) => (
                  <tr key={a.id} onClick={() => setSelected(a)}
                    className="border-b border-white/4 hover:bg-white/2 cursor-pointer transition-colors group">

                    {/* Name */}
                    <td className="px-3 py-2.5 min-w-[180px]">
                      <div className="flex items-center gap-2">
                        <TypeIcon type={a.type} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-1">
                            <p className="text-xs font-medium text-foreground truncate max-w-[180px]">{a.name}</p>
                            {a.is_critical && <Star className="w-3 h-3 text-yellow-400 fill-yellow-400 flex-shrink-0" />}
                          </div>
                          {a.url && (
                            <a href={a.url} target="_blank" rel="noopener noreferrer"
                              onClick={e => e.stopPropagation()}
                              className="text-[9px] text-blue-400 hover:underline flex items-center gap-0.5">
                              {a.source}
                            </a>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Type */}
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <span className="text-[10px] text-muted-foreground">{TYPE_LABEL[a.type] ?? a.type}</span>
                    </td>

                    {/* Source */}
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <span className="text-[10px] text-muted-foreground uppercase">{SOURCE_LABEL[a.source] ?? a.source ?? '—'}</span>
                    </td>

                    {/* Environment */}
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <span className={clsx('text-[10px] capitalize', ENV_COLOR[a.environment ?? 'unknown'] ?? 'text-muted-foreground')}>
                        {a.environment ?? '—'}
                      </span>
                    </td>

                    {/* Risk level */}
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full font-bold border uppercase', RISK_BADGE[a.risk_level ?? 'none'])}>
                        {a.risk_level ?? 'none'}
                      </span>
                    </td>

                    {/* Risk score bar */}
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      {a.risk_score != null ? <RiskBar score={a.risk_score} /> : <span className="text-[10px] text-muted-foreground/40">—</span>}
                    </td>

                    {/* Open findings */}
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      {(a.open_findings ?? 0) > 0 ? (
                        <div className="flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3 text-orange-400" />
                          <span className="text-xs font-bold text-orange-400">{a.open_findings}</span>
                        </div>
                      ) : (
                        <span className="text-[10px] text-muted-foreground/40">—</span>
                      )}
                    </td>

                    {/* Owner */}
                    <td className="px-3 py-2.5 min-w-[100px]">
                      {a.owner ? (
                        <div className="flex items-center gap-1.5">
                          <div className="w-5 h-5 rounded-full bg-white/8 flex items-center justify-center flex-shrink-0">
                            <User className="w-2.5 h-2.5 text-muted-foreground" />
                          </div>
                          <span className="text-[10px] text-foreground truncate max-w-[100px]">{a.owner}</span>
                        </div>
                      ) : (
                        <span className="text-[10px] text-muted-foreground/40">—</span>
                      )}
                    </td>

                    {/* Last seen */}
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        {fmtDate(a.last_synced_at ?? a.last_scanned_at)}
                      </div>
                    </td>

                    {/* Status */}
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full border capitalize',
                        a.status === 'active' ? 'bg-green-500/10 text-green-400 border-green-500/20'
                        : a.status === 'inactive' ? 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                        : 'bg-white/5 text-muted-foreground border-white/8'
                      )}>{a.status ?? 'active'}</span>
                    </td>

                    {/* Row actions */}
                    <td className="px-2 py-2.5">
                      <ChevronRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-white/6">
              <span className="text-[10px] text-muted-foreground">
                {((page - 1) * PAGE_SIZE + 1).toLocaleString()}–{Math.min(page * PAGE_SIZE, total).toLocaleString()} of {total.toLocaleString()} assets
              </span>
              <div className="flex items-center gap-1">
                <button onClick={() => setPage(1)} disabled={page === 1}
                  className="px-2 py-1 text-xs rounded text-muted-foreground hover:text-foreground disabled:opacity-30">««</button>
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs text-foreground px-2">{page} / {pages}</span>
                <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                  className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30">
                  <ChevronRight className="w-4 h-4" />
                </button>
                <button onClick={() => setPage(pages)} disabled={page === pages}
                  className="px-2 py-1 text-xs rounded text-muted-foreground hover:text-foreground disabled:opacity-30">»»</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Asset Drawer ─────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {selected && (
          <AssetDrawer asset={selected} onClose={() => setSelected(null)} canSync={canSync} />
        )}
      </AnimatePresence>
    </div>
  );
}
