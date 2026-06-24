import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Server, GitBranch, Box, Database, Shield, Cloud,
  Container, Cpu, Network, RefreshCw, Search, Filter,
  ChevronDown, ExternalLink, GitFork, AlertTriangle,
  CheckCircle, XCircle, Clock, Link2, Loader2, X,
  Info, Tag, User, Layers,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import apiClient from '@/services/api/client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Asset {
  id: string;
  name: string;
  type: string;
  source: string;
  environment: string;
  status: string;
  risk_level: string;
  owner: string | null;
  team: string | null;
  description: string | null;
  region: string | null;
  account_id: string | null;
  namespace: string | null;
  cluster: string | null;
  url: string | null;
  is_critical: boolean;
  open_findings: number;
  last_scanned_at: string | null;
  last_synced_at: string | null;
  tags: Record<string, unknown>;
  meta: Record<string, unknown>;
  relationship_count: number;
}

interface AssetStats {
  total: number;
  critical_assets: number;
  by_type: Record<string, number>;
  by_risk: Record<string, number>;
  by_environment: Record<string, number>;
  by_source: Record<string, number>;
}

interface SyncStatus {
  running: boolean;
  last_sync_at: string | null;
  last_result: Record<string, unknown> | null;
  error: string | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ASSET_TYPE_ICONS: Record<string, React.FC<{ className?: string }>> = {
  github_repo:   GitBranch,
  gitlab_repo:   GitFork,
  aws_ec2:       Server,
  aws_s3:        Database,
  aws_iam_user:  User,
  aws_iam_role:  Shield,
  aws_rds:       Database,
  docker_image:  Container,
  k8s_cluster:   Layers,
  k8s_namespace: Network,
  k8s_pod:       Cpu,
};

const ASSET_TYPE_LABELS: Record<string, string> = {
  github_repo:   'GitHub Repo',
  gitlab_repo:   'GitLab Repo',
  aws_ec2:       'EC2 Instance',
  aws_s3:        'S3 Bucket',
  aws_iam_user:  'IAM User',
  aws_iam_role:  'IAM Role',
  aws_rds:       'RDS Instance',
  docker_image:  'Docker Image',
  k8s_cluster:   'K8s Cluster',
  k8s_namespace: 'K8s Namespace',
  k8s_pod:       'K8s Pod',
};

const SOURCE_COLORS: Record<string, string> = {
  github:     'text-purple-400 bg-purple-400/10',
  gitlab:     'text-orange-400 bg-orange-400/10',
  aws:        'text-yellow-400 bg-yellow-400/10',
  kubernetes: 'text-blue-400 bg-blue-400/10',
  docker:     'text-cyan-400 bg-cyan-400/10',
};

const RISK_COLORS: Record<string, string> = {
  critical: 'text-red-400    bg-red-400/10    border-red-400/20',
  high:     'text-orange-400 bg-orange-400/10 border-orange-400/20',
  medium:   'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  low:      'text-blue-400   bg-blue-400/10   border-blue-400/20',
  none:     'text-gray-500   bg-gray-500/10   border-gray-500/20',
};

const ENV_COLORS: Record<string, string> = {
  production:  'text-green-400 bg-green-400/10',
  staging:     'text-yellow-400 bg-yellow-400/10',
  development: 'text-blue-400 bg-blue-400/10',
  unknown:     'text-gray-500 bg-gray-500/10',
};

const ALL_TYPES = Object.keys(ASSET_TYPE_LABELS);
const ALL_SOURCES = ['github', 'gitlab', 'aws', 'kubernetes', 'docker'];
const ALL_ENVS = ['production', 'staging', 'development', 'unknown'];
const ALL_RISKS = ['critical', 'high', 'medium', 'low', 'none'];

// ── Helpers ───────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function relativeTime(iso: string | null): string {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ── Asset Detail Panel ────────────────────────────────────────────────────────

function AssetDetailPanel({ asset, onClose }: { asset: Asset; onClose: () => void }) {
  const { data: detail, loading } = useApi<any>(`/assets/${asset.id}`);
  const Icon = ASSET_TYPE_ICONS[asset.type] || Box;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="w-96 flex-shrink-0 border-l overflow-y-auto"
      style={{ borderColor: 'hsl(230 15% 16%)', background: 'hsl(230 15% 7%)' }}
    >
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
        <div className="flex items-center gap-3 min-w-0">
          <div className={clsx('p-2 rounded-lg flex-shrink-0', SOURCE_COLORS[asset.source] || 'bg-gray-500/10')}>
            <Icon className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-white truncate">{asset.name}</h3>
            <p className="text-xs text-gray-500">{ASSET_TYPE_LABELS[asset.type] || asset.type}</p>
          </div>
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-white flex-shrink-0 ml-2">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Risk + Status */}
        <div className="flex gap-2 flex-wrap">
          <span className={clsx('text-xs px-2 py-0.5 rounded-full border font-medium', RISK_COLORS[asset.risk_level])}>
            {asset.risk_level === 'none' ? 'No Risk' : `${asset.risk_level.charAt(0).toUpperCase() + asset.risk_level.slice(1)} Risk`}
          </span>
          {asset.open_findings > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
              {asset.open_findings} finding{asset.open_findings !== 1 ? 's' : ''}
            </span>
          )}
          {asset.is_critical && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 font-semibold">
              CRITICAL ASSET
            </span>
          )}
        </div>

        {/* Metadata Grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          {[
            { label: 'Environment', value: asset.environment },
            { label: 'Source', value: asset.source },
            { label: 'Owner', value: asset.owner || '—' },
            { label: 'Team', value: asset.team || '—' },
            { label: 'Region', value: asset.region || '—' },
            { label: 'Account', value: asset.account_id || '—' },
            { label: 'Namespace', value: asset.namespace || '—' },
            { label: 'Cluster', value: asset.cluster || '—' },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-lg p-2" style={{ background: 'hsl(230 15% 10%)' }}>
              <p className="text-gray-500 mb-0.5">{label}</p>
              <p className="text-white font-medium truncate">{value}</p>
            </div>
          ))}
        </div>

        {/* Description */}
        {asset.description && (
          <div>
            <p className="text-xs text-gray-500 mb-1">Description</p>
            <p className="text-xs text-gray-300 leading-relaxed">{asset.description}</p>
          </div>
        )}

        {/* URL */}
        {asset.url && (
          <a href={asset.url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 transition-colors">
            <ExternalLink className="w-3 h-3 flex-shrink-0" />
            <span className="truncate">{asset.url}</span>
          </a>
        )}

        {/* Tags */}
        {Object.keys(asset.tags || {}).length > 0 && (
          <div>
            <p className="text-xs text-gray-500 mb-2 flex items-center gap-1"><Tag className="w-3 h-3" />Tags</p>
            <div className="flex flex-wrap gap-1">
              {Object.entries(asset.tags).slice(0, 12).map(([k, v]) => (
                <span key={k} className="text-xs px-2 py-0.5 rounded bg-white/5 text-gray-400">
                  {k}: {String(v)}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Relationships */}
        {loading ? (
          <Skeleton className="h-20 w-full" />
        ) : detail?.relationships && (
          <div>
            <p className="text-xs text-gray-500 mb-2 flex items-center gap-1"><Link2 className="w-3 h-3" />Relationships</p>
            <div className="space-y-1">
              {detail.relationships.outgoing?.map((rel: any) => (
                <div key={rel.id} className="flex items-center gap-2 text-xs p-2 rounded-lg" style={{ background: 'hsl(230 15% 10%)' }}>
                  <span className="text-gray-400 font-mono bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded text-xs">{rel.relationship_type}</span>
                  <span className="text-white truncate">{rel.target?.name || rel.target_asset_id?.slice(0, 12)}</span>
                </div>
              ))}
              {detail.relationships.incoming?.map((rel: any) => (
                <div key={rel.id} className="flex items-center gap-2 text-xs p-2 rounded-lg" style={{ background: 'hsl(230 15% 10%)' }}>
                  <span className="text-gray-400 font-mono bg-purple-500/10 text-purple-400 px-1.5 py-0.5 rounded text-xs">← {rel.relationship_type}</span>
                  <span className="text-white truncate">{rel.source?.name || rel.source_asset_id?.slice(0, 12)}</span>
                </div>
              ))}
              {!detail.relationships.outgoing?.length && !detail.relationships.incoming?.length && (
                <p className="text-xs text-gray-600">No relationships mapped</p>
              )}
            </div>
          </div>
        )}

        {/* Sync info */}
        <div className="pt-2 border-t text-xs text-gray-600 space-y-0.5" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <p>Last synced: {relativeTime(asset.last_synced_at)}</p>
          <p>Last scanned: {relativeTime(asset.last_scanned_at)}</p>
        </div>
      </div>
    </motion.div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color }: { label: string; value: number | string; sub?: string; color?: string }) {
  return (
    <div className="card-base">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className={clsx('text-2xl font-bold', color || 'text-white')}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function AssetsTab() {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [envFilter, setEnvFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [page, setPage] = useState(1);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncSource, setSyncSource] = useState<string>('');
  const [showSourceDropdown, setShowSourceDropdown] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [statsRefresh, setStatsRefresh] = useState(0);

  // Build query string
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('page_size', '25');
  if (search) params.set('search', search);
  if (typeFilter) params.set('type', typeFilter);
  if (sourceFilter) params.set('source', sourceFilter);
  if (envFilter) params.set('environment', envFilter);
  if (riskFilter) params.set('risk_level', riskFilter);

  const { data: assetsData, loading, error, refetch } = useApi<any>(`/assets?${params}`, [
    search, typeFilter, sourceFilter, envFilter, riskFilter, page
  ]);

  const { data: stats, refetch: refetchStats } = useApi<AssetStats>(`/assets/stats`, [statsRefresh]);
  const { data: syncStatus, refetch: refetchSyncStatus } = useApi<SyncStatus>(`/assets/sync/status`);

  const assets: Asset[] = assetsData?.data ?? [];
  const total: number = assetsData?.total ?? 0;
  const pages: number = assetsData?.pages ?? 1;

  // Poll sync status when running
  useEffect(() => {
    if (!syncStatus?.running) return;
    const timer = setInterval(() => refetchSyncStatus(), 2000);
    return () => clearInterval(timer);
  }, [syncStatus?.running, refetchSyncStatus]);

  // When sync finishes, reload data
  useEffect(() => {
    if (syncStatus && !syncStatus.running && syncStatus.last_sync_at) {
      refetch(true);
      setStatsRefresh(n => n + 1);
      setSyncing(false);
    }
  }, [syncStatus?.running]);

  const handleSync = useCallback(async (source?: string) => {
    try {
      setSyncing(true);
      setSyncMsg(null);
      setShowSourceDropdown(false);
      const endpoint = source ? `/assets/sync/${source}` : '/assets/sync';
      await apiPost(endpoint, {});
      setSyncMsg(source ? `Syncing ${source}…` : 'Syncing all sources…');
      refetchSyncStatus();
    } catch (err: any) {
      setSyncing(false);
      setSyncMsg(err?.response?.data?.detail || 'Sync failed');
    }
  }, []);

  const resetFilters = () => {
    setSearch('');
    setTypeFilter('');
    setSourceFilter('');
    setEnvFilter('');
    setRiskFilter('');
    setPage(1);
  };

  const hasFilters = search || typeFilter || sourceFilter || envFilter || riskFilter;

  return (
    <div className="flex gap-4 h-full">
      <div className="flex-1 min-w-0 space-y-4">

        {/* Stats Row */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Total Assets" value={stats.total} />
            <StatCard label="Critical Risk" value={stats.critical_assets}
              color={stats.critical_assets > 0 ? 'text-red-400' : 'text-green-400'}
              sub={stats.critical_assets > 0 ? 'Need attention' : 'All clear'} />
            <StatCard
              label="Sources"
              value={Object.keys(stats.by_source || {}).length}
              sub={Object.entries(stats.by_source || {}).map(([s,c]) => `${s} (${c})`).join(', ').slice(0, 30) || 'None connected'}
            />
            <StatCard
              label="Environments"
              value={Object.keys(stats.by_environment || {}).length}
              sub={`${stats.by_environment?.production ?? 0} prod`}
            />
          </div>
        )}

        {/* Toolbar */}
        <div className="card-base">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="relative flex-1 min-w-48">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
              <input
                value={search}
                onChange={e => { setSearch(e.target.value); setPage(1); }}
                placeholder="Search assets…"
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border bg-transparent text-white placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all"
                style={{ borderColor: 'hsl(230 15% 16%)' }}
              />
            </div>

            {/* Filters */}
            {[
              { value: typeFilter,   setter: setTypeFilter,   options: ALL_TYPES,   placeholder: 'All types',   labels: ASSET_TYPE_LABELS },
              { value: sourceFilter, setter: setSourceFilter, options: ALL_SOURCES, placeholder: 'All sources', labels: null },
              { value: envFilter,    setter: setEnvFilter,    options: ALL_ENVS,    placeholder: 'All envs',    labels: null },
              { value: riskFilter,   setter: setRiskFilter,   options: ALL_RISKS,   placeholder: 'All risks',   labels: null },
            ].map(({ value, setter, options, placeholder, labels }) => (
              <select
                key={placeholder}
                value={value}
                onChange={e => { setter(e.target.value); setPage(1); }}
                className="text-xs rounded-lg border bg-transparent text-gray-300 px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                style={{ borderColor: 'hsl(230 15% 16%)', background: 'hsl(230 15% 8%)' }}
              >
                <option value="">{placeholder}</option>
                {options.map(o => (
                  <option key={o} value={o}>{labels ? (labels[o] || o) : o}</option>
                ))}
              </select>
            ))}

            {hasFilters && (
              <button onClick={resetFilters}
                className="text-xs text-gray-500 hover:text-white flex items-center gap-1 transition-colors">
                <X className="w-3 h-3" /> Clear
              </button>
            )}

            <div className="ml-auto flex items-center gap-2">
              {syncMsg && (
                <span className={clsx('text-xs', syncStatus?.error ? 'text-red-400' : 'text-blue-400')}>
                  {syncMsg}
                </span>
              )}

              {/* Sync button with dropdown */}
              <div className="relative">
                <div className="flex">
                  <button
                    onClick={() => handleSync()}
                    disabled={syncing || syncStatus?.running}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-l-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {(syncing || syncStatus?.running) ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3 h-3" />
                    )}
                    Sync All
                  </button>
                  <button
                    onClick={() => setShowSourceDropdown(!showSourceDropdown)}
                    disabled={syncing || syncStatus?.running}
                    className="flex items-center px-1.5 py-1.5 text-xs rounded-r-lg bg-blue-700 hover:bg-blue-800 text-white border-l border-blue-500 transition-colors disabled:opacity-50"
                  >
                    <ChevronDown className="w-3 h-3" />
                  </button>
                </div>

                {showSourceDropdown && (
                  <div className="absolute right-0 top-full mt-1 z-30 w-40 rounded-lg border shadow-xl py-1"
                    style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 18%)' }}>
                    {ALL_SOURCES.map(src => (
                      <button key={src}
                        onClick={() => handleSync(src)}
                        className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:text-white hover:bg-white/5 transition-colors capitalize">
                        {src}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Last sync info */}
          {syncStatus?.last_sync_at && !syncStatus.running && (
            <p className="text-xs text-gray-600 mt-2">
              Last sync: {relativeTime(syncStatus.last_sync_at)}
              {syncStatus.error && <span className="text-red-500 ml-2">Error: {syncStatus.error.slice(0, 80)}</span>}
            </p>
          )}
        </div>

        {/* Table */}
        <div className="card-base overflow-hidden">
          {loading ? (
            <div className="space-y-2">
              {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <XCircle className="w-8 h-8 text-red-400 mb-3" />
              <p className="text-sm text-red-400 font-medium">Failed to load assets</p>
              <p className="text-xs text-gray-500 mt-1">{error}</p>
              <button onClick={() => refetch()} className="mt-3 text-xs text-blue-400 hover:text-blue-300">Try again</button>
            </div>
          ) : assets.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Server className="w-10 h-10 text-gray-700 mb-3" />
              <p className="text-sm font-medium text-gray-400">
                {hasFilters ? 'No assets match your filters' : 'No assets discovered yet'}
              </p>
              <p className="text-xs text-gray-600 mt-1 max-w-sm">
                {hasFilters
                  ? 'Try adjusting your filters or clearing them.'
                  : 'Connect GitHub, GitLab, AWS, or Kubernetes integrations then click Sync All to discover your assets.'
                }
              </p>
              {!hasFilters && (
                <button onClick={() => handleSync()}
                  disabled={syncing}
                  className="mt-4 flex items-center gap-2 px-4 py-2 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50">
                  <RefreshCw className={clsx('w-3 h-3', syncing && 'animate-spin')} />
                  Run Discovery
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                    {['Asset Name', 'Type', 'Environment', 'Owner', 'Risk Level', 'Last Scan', 'Relationships'].map(h => (
                      <th key={h} className="text-left py-3 px-3 text-gray-500 font-medium whitespace-nowrap first:pl-0">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence mode="popLayout">
                    {assets.map((asset) => {
                      const Icon = ASSET_TYPE_ICONS[asset.type] || Box;
                      const isSelected = selectedAsset?.id === asset.id;
                      return (
                        <motion.tr
                          key={asset.id}
                          layout
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          onClick={() => setSelectedAsset(isSelected ? null : asset)}
                          className={clsx(
                            'border-b cursor-pointer transition-colors',
                            isSelected
                              ? 'bg-blue-500/5 border-blue-500/20'
                              : 'border-transparent hover:bg-white/3',
                          )}
                          style={!isSelected ? { borderBottomColor: 'hsl(230 15% 11%)' } : {}}
                        >
                          {/* Asset Name */}
                          <td className="py-3 px-3 first:pl-0">
                            <div className="flex items-center gap-2 min-w-0">
                              <div className={clsx('p-1.5 rounded-md flex-shrink-0', SOURCE_COLORS[asset.source] || 'bg-gray-500/10')}>
                                <Icon className="w-3 h-3" />
                              </div>
                              <div className="min-w-0">
                                <p className="font-medium text-white truncate max-w-[180px]">{asset.name}</p>
                                {asset.description && (
                                  <p className="text-gray-600 truncate max-w-[180px]">{asset.description}</p>
                                )}
                              </div>
                              {asset.is_critical && (
                                <span className="flex-shrink-0 text-[10px] px-1 py-0.5 rounded bg-red-500/10 text-red-400 font-semibold">CRIT</span>
                              )}
                            </div>
                          </td>

                          {/* Type */}
                          <td className="py-3 px-3">
                            <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', SOURCE_COLORS[asset.source] || 'text-gray-400 bg-gray-400/10')}>
                              {ASSET_TYPE_LABELS[asset.type] || asset.type}
                            </span>
                          </td>

                          {/* Environment */}
                          <td className="py-3 px-3">
                            <span className={clsx('text-xs px-2 py-0.5 rounded-full', ENV_COLORS[asset.environment] || 'text-gray-500')}>
                              {asset.environment}
                            </span>
                          </td>

                          {/* Owner */}
                          <td className="py-3 px-3">
                            <span className="text-gray-400">{asset.owner || '—'}</span>
                          </td>

                          {/* Risk Level */}
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-1.5">
                              <span className={clsx('text-xs px-2 py-0.5 rounded-full border font-medium capitalize', RISK_COLORS[asset.risk_level])}>
                                {asset.risk_level}
                              </span>
                              {asset.open_findings > 0 && (
                                <span className="text-xs text-red-400">({asset.open_findings})</span>
                              )}
                            </div>
                          </td>

                          {/* Last Scan */}
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-1 text-gray-500">
                              <Clock className="w-3 h-3 flex-shrink-0" />
                              <span>{relativeTime(asset.last_scanned_at)}</span>
                            </div>
                          </td>

                          {/* Relationships */}
                          <td className="py-3 px-3">
                            {asset.relationship_count > 0 ? (
                              <div className="flex items-center gap-1 text-blue-400">
                                <Link2 className="w-3 h-3" />
                                <span>{asset.relationship_count}</span>
                              </div>
                            ) : (
                              <span className="text-gray-600">—</span>
                            )}
                          </td>
                        </motion.tr>
                      );
                    })}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t mt-4 text-xs"
              style={{ borderColor: 'hsl(230 15% 14%)' }}>
              <span className="text-gray-500">
                {(page - 1) * 25 + 1}–{Math.min(page * 25, total)} of {total} assets
              </span>
              <div className="flex gap-1">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="px-2 py-1 rounded border text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
                  style={{ borderColor: 'hsl(230 15% 16%)' }}>←</button>
                {[...Array(Math.min(5, pages))].map((_, i) => {
                  const p = i + 1;
                  return (
                    <button key={p} onClick={() => setPage(p)}
                      className={clsx('w-6 h-6 rounded border text-xs transition-colors',
                        page === p ? 'bg-blue-600 border-blue-600 text-white' : 'text-gray-400 hover:text-white')}
                      style={{ borderColor: page === p ? undefined : 'hsl(230 15% 16%)' }}>
                      {p}
                    </button>
                  );
                })}
                <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                  className="px-2 py-1 rounded border text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
                  style={{ borderColor: 'hsl(230 15% 16%)' }}>→</button>
              </div>
            </div>
          )}
        </div>

        {/* Type Breakdown */}
        {stats && Object.keys(stats.by_type || {}).length > 0 && (
          <div className="card-base">
            <h3 className="text-xs font-semibold text-gray-400 mb-3">Asset Type Breakdown</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              {Object.entries(stats.by_type).sort(([,a],[,b]) => b - a).map(([type, count]) => {
                const Icon = ASSET_TYPE_ICONS[type] || Box;
                return (
                  <button key={type}
                    onClick={() => { setTypeFilter(type === typeFilter ? '' : type); setPage(1); }}
                    className={clsx(
                      'flex items-center gap-2 p-2.5 rounded-lg border text-left transition-all',
                      typeFilter === type
                        ? 'border-blue-500/40 bg-blue-500/10'
                        : 'border-transparent hover:border-white/10',
                    )}
                    style={typeFilter !== type ? { background: 'hsl(230 15% 10%)' } : {}}>
                    <div className={clsx('p-1.5 rounded-md', SOURCE_COLORS[type.split('_')[0]] || 'bg-gray-500/10')}>
                      <Icon className="w-3 h-3" />
                    </div>
                    <div>
                      <p className="text-white font-semibold text-sm">{count}</p>
                      <p className="text-gray-500 text-[10px] leading-tight">{ASSET_TYPE_LABELS[type] || type}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Detail Panel */}
      <AnimatePresence>
        {selectedAsset && (
          <AssetDetailPanel asset={selectedAsset} onClose={() => setSelectedAsset(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}
