import { useState, useCallback, useEffect } from 'react';
import {
  Server, RefreshCw, Search, ChevronLeft, ChevronRight,
  GitBranch, Cloud, Database, Box, Layers, HardDrive,
  AlertTriangle, CheckCircle, Clock, ExternalLink, X,
  ChevronDown, ChevronUp, Link2, Shield, User, Globe,
  MoreHorizontal, Play, Activity, Network, List,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';
import AssetGraph from './AssetGraph';

// ─── helpers ──────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)}d ago`;
  return d.toLocaleDateString();
}

const RISK_BADGE: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border border-red-500/30',
  high:     'bg-orange-500/15 text-orange-400 border border-orange-500/30',
  medium:   'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
  low:      'bg-blue-500/15 text-blue-400 border border-blue-500/30',
  none:     'bg-green-500/15 text-green-400 border border-green-500/30',
};

const RISK_DOT: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
  none: 'bg-green-500',
};

function TypeIcon({ type }: { type: string }) {
  const cls = 'w-4 h-4 flex-shrink-0';
  switch (type) {
    case 'github_repo':
    case 'gitlab_repo':   return <GitBranch className={clsx(cls, 'text-purple-400')} />;
    case 'aws_ec2':       return <Cloud className={clsx(cls, 'text-orange-400')} />;
    case 'aws_s3':        return <HardDrive className={clsx(cls, 'text-yellow-400')} />;
    case 'aws_iam_user':
    case 'aws_iam_role':  return <User className={clsx(cls, 'text-blue-400')} />;
    case 'aws_rds':       return <Database className={clsx(cls, 'text-cyan-400')} />;
    case 'docker_image':  return <Box className={clsx(cls, 'text-sky-400')} />;
    case 'k8s_cluster':   return <Layers className={clsx(cls, 'text-indigo-400')} />;
    case 'k8s_namespace': return <Layers className={clsx(cls, 'text-violet-400')} />;
    case 'k8s_pod':       return <Server className={clsx(cls, 'text-fuchsia-400')} />;
    default:              return <Globe className={clsx(cls, 'text-muted-foreground')} />;
  }
}

const SOURCE_LABEL: Record<string, string> = {
  github: 'GitHub', gitlab: 'GitLab', aws: 'AWS',
  kubernetes: 'Kubernetes', docker: 'Docker',
};

const TYPE_LABEL: Record<string, string> = {
  github_repo: 'GitHub Repo', gitlab_repo: 'GitLab Repo',
  aws_ec2: 'EC2', aws_s3: 'S3 Bucket', aws_iam_user: 'IAM User',
  aws_iam_role: 'IAM Role', aws_rds: 'RDS', docker_image: 'Docker Image',
  k8s_cluster: 'K8s Cluster', k8s_namespace: 'Namespace', k8s_pod: 'Pod',
};

const ENV_BADGE: Record<string, string> = {
  production: 'text-red-400',
  staging:    'text-yellow-400',
  development:'text-green-400',
  unknown:    'text-muted-foreground',
};

// ─── Asset Detail Drawer ───────────────────────────────────────────────────────

function AssetDrawer({ asset, onClose }: { asset: any; onClose: () => void }) {
  const { data: raw } = useApi<any>(asset ? `/assets/${asset.id}` : null);
  const detail = raw?.data ?? raw;
  const relationships = detail?.relationships;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-md bg-[hsl(230_15%_10%)] border-l border-border overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="sticky top-0 bg-[hsl(230_15%_10%)] border-b border-border px-5 py-4 flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0 mt-0.5">
            <TypeIcon type={asset.type} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground truncate">{asset.name}</p>
            <p className="text-[11px] text-muted-foreground">{TYPE_LABEL[asset.type] ?? asset.type}</p>
          </div>
          <button onClick={onClose} className="p-1 rounded text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Risk + Status */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className={clsx('text-xs px-2 py-1 rounded-md font-medium', RISK_BADGE[asset.risk_level ?? 'none'])}>
              {(asset.risk_level ?? 'none').toUpperCase()} RISK
            </span>
            {asset.is_critical && (
              <span className="text-xs px-2 py-1 rounded-md bg-red-500/10 text-red-400 border border-red-500/30 font-medium">
                CRITICAL ASSET
              </span>
            )}
            <span className="text-xs px-2 py-1 rounded-md bg-white/5 text-muted-foreground capitalize">
              {asset.status ?? 'active'}
            </span>
          </div>

          {/* Core fields */}
          <div className="space-y-2.5">
            {[
              { label: 'Source', value: SOURCE_LABEL[asset.source] ?? asset.source },
              { label: 'Environment', value: asset.environment },
              { label: 'Owner', value: asset.owner ?? '—' },
              { label: 'Team', value: asset.team ?? '—' },
              { label: 'Region', value: asset.region ?? '—' },
              { label: 'Account', value: asset.account_id ?? '—' },
              { label: 'Cluster', value: asset.cluster ?? '—' },
              { label: 'Namespace', value: asset.namespace ?? '—' },
              { label: 'Open Findings', value: asset.open_findings ?? 0 },
              { label: 'Last Synced', value: fmtDate(asset.last_synced_at) },
              { label: 'Last Scanned', value: fmtDate(asset.last_scanned_at) },
            ].filter(f => f.value && f.value !== '—' || typeof f.value === 'number').map(f => (
              <div key={f.label} className="flex justify-between items-center gap-2">
                <span className="text-xs text-muted-foreground">{f.label}</span>
                <span className="text-xs text-foreground text-right">{String(f.value)}</span>
              </div>
            ))}
          </div>

          {/* URL */}
          {asset.url && (
            <a href={asset.url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors">
              <ExternalLink className="w-3 h-3" /> Open in console
            </a>
          )}

          {/* Description */}
          {asset.description && (
            <div>
              <p className="text-[11px] text-muted-foreground mb-1">Description</p>
              <p className="text-xs text-foreground">{asset.description}</p>
            </div>
          )}

          {/* Tags */}
          {asset.tags && Object.keys(asset.tags).length > 0 && (
            <div>
              <p className="text-[11px] text-muted-foreground mb-2">Tags</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(asset.tags).filter(([, v]) => v !== null && v !== false && v !== '').map(([k, v]) => (
                  <span key={k} className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-muted-foreground">
                    {k}: {String(v)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Relationships */}
          {relationships && (
            <div>
              <p className="text-[11px] text-muted-foreground mb-2 flex items-center gap-1.5">
                <Link2 className="w-3 h-3" /> Relationships
              </p>
              {[...(relationships.outgoing ?? []), ...(relationships.incoming ?? [])].length === 0 ? (
                <p className="text-xs text-muted-foreground">No relationships</p>
              ) : (
                <div className="space-y-1.5">
                  {(relationships.outgoing ?? []).map((rel: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 capitalize">{rel.relationship_type}</span>
                      <span className="text-foreground truncate">{rel.target?.name ?? rel.target_asset_id}</span>
                    </div>
                  ))}
                  {(relationships.incoming ?? []).map((rel: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 capitalize">← {rel.relationship_type}</span>
                      <span className="text-foreground truncate">{rel.source?.name ?? rel.source_asset_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Metadata */}
          {detail?.meta && Object.keys(detail.meta).length > 0 && (
            <div>
              <p className="text-[11px] text-muted-foreground mb-2">Metadata</p>
              <div className="rounded-lg bg-white/3 border border-border p-3 space-y-1.5">
                {Object.entries(detail.meta).filter(([, v]) => v !== null && v !== '' && v !== false).map(([k, v]) => (
                  <div key={k} className="flex justify-between items-start gap-3">
                    <span className="text-[10px] text-muted-foreground flex-shrink-0">{k.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] text-foreground text-right break-all">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, accent }: {
  label: string; value: number | string; sub?: string; accent?: string;
}) {
  return (
    <div className="card-base px-4 py-3">
      <div className={clsx('text-2xl font-bold tabular-nums', accent ?? 'text-foreground')}>{value}</div>
      <div className="text-[11px] font-medium text-foreground mt-0.5">{label}</div>
      {sub && <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

// ─── Sort header cell ─────────────────────────────────────────────────────────

function TH({ label, field, sort, setSort }: {
  label: string; field: string;
  sort: { by: string; dir: string };
  setSort: (s: { by: string; dir: string }) => void;
}) {
  const active = sort.by === field;
  return (
    <th
      className={clsx(
        'text-left text-[11px] font-medium text-muted-foreground px-3 py-2.5 cursor-pointer select-none whitespace-nowrap',
        'hover:text-foreground transition-colors',
        active && 'text-foreground',
      )}
      onClick={() => setSort(active
        ? { by: field, dir: sort.dir === 'asc' ? 'desc' : 'asc' }
        : { by: field, dir: 'desc' }
      )}
    >
      <span className="flex items-center gap-1">
        {label}
        {active ? (
          sort.dir === 'asc'
            ? <ChevronUp className="w-3 h-3" />
            : <ChevronDown className="w-3 h-3" />
        ) : (
          <span className="w-3 h-3 opacity-0">▲</span>
        )}
      </span>
    </th>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────

const SOURCES = ['', 'github', 'gitlab', 'aws', 'kubernetes', 'docker'];
const RISKS   = ['', 'critical', 'high', 'medium', 'low', 'none'];
const ENVS    = ['', 'production', 'staging', 'development', 'unknown'];
const TYPES   = [
  '', 'github_repo', 'gitlab_repo', 'aws_ec2', 'aws_s3',
  'aws_iam_user', 'aws_iam_role', 'aws_rds',
  'docker_image', 'k8s_cluster', 'k8s_namespace', 'k8s_pod',
];

export default function Assets() {
  const { role } = usePermissions();
  const canSync = canWriteSecurity(role);

  const [search,    setSearch]    = useState('');
  const [source,    setSource]    = useState('');
  const [risk,      setRisk]      = useState('');
  const [env,       setEnv]       = useState('');
  const [typeF,     setTypeF]     = useState('');
  const [page,      setPage]      = useState(1);
  const [sort,      setSort]      = useState({ by: 'risk_level', dir: 'desc' });
  const [syncing,   setSyncing]   = useState(false);
  const [syncMsg,   setSyncMsg]   = useState<{ ok: boolean; text: string } | null>(null);
  const [selected,  setSelected]  = useState<any | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [viewMode, setViewMode] = useState<'table' | 'graph'>('table');

  const PAGE_SIZE = 20;

  const qs = new URLSearchParams({
    page: String(page),
    page_size: String(PAGE_SIZE),
    sort_by: sort.by,
    sort_dir: sort.dir,
  });
  if (search)  qs.set('search', search);
  if (source)  qs.set('source', source);
  if (risk)    qs.set('risk_level', risk);
  if (env)     qs.set('environment', env);
  if (typeF)   qs.set('type', typeF);

  const { data: raw, loading, refetch } = useApi<any>(`/assets?${qs}`);
  const { data: statsRaw, refetch: refetchStats } = useApi<any>('/assets/stats');
  const { data: syncStatusRaw, refetch: refetchSyncStatus } = useApi<any>('/assets/sync/status');

  const result  = raw?.data ?? raw;
  const assets  = result?.data ?? [];
  const total   = result?.total ?? 0;
  const pages   = result?.pages ?? 1;
  const stats   = statsRaw?.data ?? statsRaw;
  const syncStatus = syncStatusRaw?.data ?? syncStatusRaw;

  // Poll sync status while running
  useEffect(() => {
    if (!syncStatus?.running) return;
    const t = setInterval(() => {
      refetchSyncStatus();
      refetch();
      refetchStats();
    }, 3000);
    return () => clearInterval(t);
  }, [syncStatus?.running]);

  const handleSync = useCallback(async (src?: string) => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const endpoint = src ? `/assets/sync/${src}` : '/assets/sync';
      await apiPost(endpoint, {});
      setSyncMsg({ ok: true, text: `Sync started${src ? ` for ${SOURCE_LABEL[src] ?? src}` : ' for all sources'}` });
      setTimeout(() => { refetch(); refetchStats(); refetchSyncStatus(); }, 1500);
    } catch (e: any) {
      setSyncMsg({ ok: false, text: e?.message ?? 'Sync failed' });
    } finally {
      setSyncing(false);
    }
  }, []);

  const resetPage = () => setPage(1);

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-lg font-bold text-foreground">Asset Inventory</h1>
          <p className="text-xs text-muted-foreground">
            {total.toLocaleString()} assets · syncs every 6 hours
            {syncStatus?.last_sync_at && (
              <> · last sync {fmtDate(syncStatus.last_sync_at)}</>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Sync status indicator */}
          {(syncStatus?.running || syncing) && (
            <span className="flex items-center gap-1.5 text-xs text-blue-400">
              <Activity className="w-3.5 h-3.5 animate-pulse" /> Syncing…
            </span>
          )}

          {/* View mode toggle */}
          <div className="flex items-center rounded-lg border border-border overflow-hidden">
            <button
              onClick={() => setViewMode('table')}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs transition-colors',
                viewMode === 'table'
                  ? 'bg-blue-600 text-white'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <List className="w-3.5 h-3.5" /> Table
            </button>
            <button
              onClick={() => setViewMode('graph')}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs transition-colors border-l border-border',
                viewMode === 'graph'
                  ? 'bg-blue-600 text-white'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Network className="w-3.5 h-3.5" /> Graph
            </button>
          </div>

          <button
            onClick={() => setShowFilters(f => !f)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors',
              showFilters
                ? 'border-blue-500/40 text-blue-400 bg-blue-500/10'
                : 'border-border text-muted-foreground hover:text-foreground',
            )}
          >
            <Shield className="w-3.5 h-3.5" /> Filters
          </button>

          <button onClick={() => { refetch(); refetchStats(); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>

          {canSync && (
            <button
              onClick={() => handleSync()}
              disabled={syncing || syncStatus?.running}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-40"
            >
              <Play className="w-3.5 h-3.5" />
              {syncing || syncStatus?.running ? 'Syncing…' : 'Sync All'}
            </button>
          )}
        </div>
      </div>

      {/* Sync feedback */}
      {syncMsg && (
        <div className={clsx(
          'flex items-center gap-2 px-3 py-2 rounded-lg text-xs',
          syncMsg.ok ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400',
        )}>
          {syncMsg.ok ? <CheckCircle className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
          {syncMsg.text}
        </div>
      )}

      {/* ── Stats ── */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          <StatCard label="Total Assets" value={stats.total ?? 0} />
          <StatCard label="Critical" value={stats.by_risk?.critical ?? 0} accent="text-red-400" />
          <StatCard label="High" value={stats.by_risk?.high ?? 0} accent="text-orange-400" />
          {Object.entries(stats.by_source ?? {}).slice(0, 3).map(([src, cnt]) => (
            <StatCard key={src} label={SOURCE_LABEL[src] ?? src} value={cnt as number} />
          ))}
        </div>
      )}

      {/* ── Search ── */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
        <input
          type="text"
          placeholder="Search by name…"
          value={search}
          onChange={e => { setSearch(e.target.value); resetPage(); }}
          className="w-full pl-9 pr-4 py-2 text-sm bg-white/5 border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/50"
        />
        {search && (
          <button onClick={() => { setSearch(''); resetPage(); }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* ── Filters ── */}
      {showFilters && (
        <div className="card-base p-4 space-y-3">
          <div>
            <p className="text-[11px] text-muted-foreground mb-2">Source</p>
            <div className="flex flex-wrap gap-1.5">
              {SOURCES.map(s => (
                <button key={s} onClick={() => { setSource(s); resetPage(); }}
                  className={clsx(
                    'px-2.5 py-1 text-xs rounded-md transition-colors',
                    source === s ? 'bg-blue-600 text-white' : 'bg-white/5 text-muted-foreground hover:text-foreground',
                  )}>
                  {s ? (SOURCE_LABEL[s] ?? s) : 'All Sources'}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-[11px] text-muted-foreground mb-2">Risk Level</p>
            <div className="flex flex-wrap gap-1.5">
              {RISKS.map(r => (
                <button key={r} onClick={() => { setRisk(r); resetPage(); }}
                  className={clsx(
                    'flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md transition-colors',
                    risk === r ? 'bg-blue-600 text-white' : 'bg-white/5 text-muted-foreground hover:text-foreground',
                  )}>
                  {r && <span className={clsx('w-2 h-2 rounded-full', RISK_DOT[r])} />}
                  {r ? r.charAt(0).toUpperCase() + r.slice(1) : 'All Risks'}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[11px] text-muted-foreground mb-2">Environment</p>
              <select value={env} onChange={e => { setEnv(e.target.value); resetPage(); }}
                className="w-full text-xs px-2.5 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
                {ENVS.map(e => <option key={e} value={e}>{e || 'All Environments'}</option>)}
              </select>
            </div>
            <div>
              <p className="text-[11px] text-muted-foreground mb-2">Asset Type</p>
              <select value={typeF} onChange={e => { setTypeF(e.target.value); resetPage(); }}
                className="w-full text-xs px-2.5 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
                {TYPES.map(t => <option key={t} value={t}>{t ? (TYPE_LABEL[t] ?? t) : 'All Types'}</option>)}
              </select>
            </div>
          </div>

          {/* Per-source sync buttons */}
          {canSync && (
            <div>
              <p className="text-[11px] text-muted-foreground mb-2">Sync by Source</p>
              <div className="flex flex-wrap gap-1.5">
                {['github', 'gitlab', 'aws', 'kubernetes', 'docker'].map(src => (
                  <button key={src} onClick={() => handleSync(src)}
                    disabled={syncing || syncStatus?.running}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-white/5 text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors">
                    <Play className="w-2.5 h-2.5" />
                    {SOURCE_LABEL[src]}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Graph view ── */}
      {viewMode === 'graph' && <AssetGraph />}

      {/* ── Table ── */}
      {viewMode === 'table' && (
      <div className="card-base overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px]">
            <thead>
              <tr className="border-b border-border bg-white/2">
                <TH label="Asset Name"  field="name"          sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                <TH label="Type"        field="type"          sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                <TH label="Environment" field="environment"   sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                <TH label="Owner"       field="owner"         sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                <TH label="Risk Level"  field="risk_level"    sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                <TH label="Last Scan"   field="last_scanned_at" sort={sort} setSort={s => { setSort(s); resetPage(); }} />
                <th className="text-left text-[11px] font-medium text-muted-foreground px-3 py-2.5 whitespace-nowrap">
                  Relationships
                </th>
                <th className="w-8 px-2 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i} className="border-b border-border/50">
                    {[...Array(8)].map((_, j) => (
                      <td key={j} className="px-3 py-3">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : assets.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-16 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center">
                        <Server className="w-6 h-6 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground mb-1">No assets found</p>
                        <p className="text-xs text-muted-foreground max-w-xs">
                          {search || source || risk || env || typeF
                            ? 'No assets match the current filters. Try clearing some.'
                            : 'Connect integrations and click Sync All to populate your inventory.'}
                        </p>
                      </div>
                      {canSync && !search && !source && !risk && !env && !typeF && (
                        <button onClick={() => handleSync()}
                          disabled={syncing}
                          className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-40">
                          <Play className="w-3.5 h-3.5" /> Sync All Sources
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : assets.map((a: any) => (
                <tr
                  key={a.id}
                  onClick={() => setSelected(a)}
                  className="border-b border-border/50 hover:bg-white/2 cursor-pointer transition-colors group"
                >
                  {/* Asset Name */}
                  <td className="px-3 py-2.5 min-w-[180px]">
                    <div className="flex items-center gap-2">
                      <TypeIcon type={a.type} />
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-foreground truncate max-w-[200px]">{a.name}</p>
                        {a.url && (
                          <a href={a.url} target="_blank" rel="noopener noreferrer"
                            onClick={e => e.stopPropagation()}
                            className="text-[10px] text-blue-400 hover:underline flex items-center gap-0.5">
                            <ExternalLink className="w-2.5 h-2.5" />
                            {a.source}
                          </a>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Type */}
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <span className="text-xs text-muted-foreground">{TYPE_LABEL[a.type] ?? a.type}</span>
                  </td>

                  {/* Environment */}
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <span className={clsx('text-xs capitalize', ENV_BADGE[a.environment] ?? 'text-muted-foreground')}>
                      {a.environment ?? '—'}
                    </span>
                  </td>

                  {/* Owner */}
                  <td className="px-3 py-2.5 min-w-[100px]">
                    {a.owner ? (
                      <div className="flex items-center gap-1.5">
                        <div className="w-5 h-5 rounded-full bg-white/10 flex items-center justify-center flex-shrink-0">
                          <User className="w-2.5 h-2.5 text-muted-foreground" />
                        </div>
                        <span className="text-xs text-foreground truncate max-w-[120px]">{a.owner}</span>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>

                  {/* Risk Level */}
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <span className={clsx('w-2 h-2 rounded-full flex-shrink-0', RISK_DOT[a.risk_level ?? 'none'])} />
                      <span className={clsx(
                        'text-xs px-1.5 py-0.5 rounded text-center min-w-[50px]',
                        RISK_BADGE[a.risk_level ?? 'none'],
                      )}>
                        {a.risk_level ?? 'none'}
                      </span>
                      {a.open_findings > 0 && (
                        <span className="text-[10px] text-orange-400">{a.open_findings}</span>
                      )}
                    </div>
                  </td>

                  {/* Last Scan */}
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      {fmtDate(a.last_scanned_at ?? a.last_synced_at)}
                    </div>
                  </td>

                  {/* Relationships */}
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {(a.relationship_count ?? 0) > 0 ? (
                      <div className="flex items-center gap-1 text-xs text-blue-400">
                        <Link2 className="w-3 h-3" />
                        {a.relationship_count}
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>

                  {/* Row action */}
                  <td className="px-2 py-2.5">
                    <MoreHorizontal className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <span className="text-xs text-muted-foreground">
              {((page - 1) * PAGE_SIZE + 1).toLocaleString()}–{Math.min(page * PAGE_SIZE, total).toLocaleString()} of {total.toLocaleString()} assets
            </span>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(1)} disabled={page === 1}
                className="px-2 py-1 text-xs rounded text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
                ««
              </button>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30">
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs text-foreground px-2">
                {page} / {pages}
              </span>
              <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30">
                <ChevronRight className="w-4 h-4" />
              </button>
              <button onClick={() => setPage(pages)} disabled={page === pages}
                className="px-2 py-1 text-xs rounded text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
                »»
              </button>
            </div>
          </div>
        )}
      </div>
      )}

      {/* Asset detail drawer */}
      {selected && <AssetDrawer asset={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
