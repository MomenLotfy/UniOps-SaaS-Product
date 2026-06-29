import { useState, useCallback, useMemo, useRef } from 'react';
import { clsx } from 'clsx';
import { motion, AnimatePresence } from 'framer-motion';
import {
  GitBranch, RefreshCw, Search, Filter, X, ChevronDown,
  Shield, AlertTriangle, CheckCircle, Activity, ScanLine,
  Play, Loader2, CheckSquare, Github, Gitlab,
} from 'lucide-react';
import { useApi, apiPost } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';
import type { Repo, RepoRisk, MergedRepo, ScanHistoryEntry } from './types';
import { RISK_ORDER } from './types';
import RepoCard from './RepoCard';
import RepoDrawer from './RepoDrawer';
import RepoCharts from './RepoCharts';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded-xl bg-white/5', className)} />;
}

// ── KPI card ─────────────────────────────────────────────────────────────────
function KPICard({
  label, value, sub, icon: Icon, color, loading,
}: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; color: string; loading?: boolean;
}) {
  return (
    <div className={clsx('card-base p-4 flex items-center gap-3 border-l-2', color)}>
      <div className={clsx(
        'w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0',
        color.replace('border-l-', 'bg-').replace('-500', '-500/15'),
      )}>
        <Icon className="w-4.5 h-4.5" style={{ color: 'currentColor' }} />
      </div>
      <div className="min-w-0">
        {loading
          ? <div className="animate-pulse h-5 w-10 rounded bg-white/10 mb-1" />
          : <p className="text-xl font-bold text-foreground tabular-nums">{value}</p>
        }
        <p className="text-xs text-muted-foreground">{label}</p>
        {sub && <p className="text-[10px] text-muted-foreground/60">{sub}</p>}
      </div>
    </div>
  );
}

// ── Onboarding empty state ────────────────────────────────────────────────────
function OnboardingCards({ onSync, syncing }: { onSync: () => void; syncing: boolean }) {
  const providers = [
    { name: 'GitHub',      color: 'from-gray-700/40 to-gray-800/40',    border: 'border-gray-600/30', text: 'text-gray-200',   initials: 'GH' },
    { name: 'GitLab',      color: 'from-orange-700/25 to-orange-900/30', border: 'border-orange-600/25', text: 'text-orange-300', initials: 'GL' },
    { name: 'Azure DevOps',color: 'from-blue-800/25 to-blue-900/30',    border: 'border-blue-600/25', text: 'text-blue-300',   initials: 'AZ' },
    { name: 'Bitbucket',   color: 'from-blue-900/25 to-indigo-900/30',  border: 'border-indigo-600/25',text: 'text-indigo-300', initials: 'BB' },
  ];

  return (
    <div className="py-12 px-4 flex flex-col items-center">
      <div className="w-14 h-14 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-4">
        <GitBranch className="w-7 h-7 text-blue-400" />
      </div>
      <h3 className="text-base font-bold text-foreground mb-1">Connect your repositories</h3>
      <p className="text-sm text-muted-foreground mb-8 text-center max-w-md">
        No repositories found. Connect a source control provider from Integrations, then sync to start scanning.
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full max-w-xl mb-8">
        {providers.map(p => (
          <div key={p.name}
            className={clsx(
              'flex flex-col items-center gap-2 p-4 rounded-xl border bg-gradient-to-br cursor-default select-none',
              p.color, p.border,
            )}
          >
            <span className={clsx('text-lg font-bold font-mono', p.text)}>{p.initials}</span>
            <span className="text-[10px] text-muted-foreground text-center leading-tight">{p.name}</span>
          </div>
        ))}
      </div>

      <button
        onClick={onSync}
        disabled={syncing}
        className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition-colors disabled:opacity-50"
      >
        {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
        {syncing ? 'Syncing…' : 'Sync Repositories'}
      </button>

      <p className="text-xs text-muted-foreground/60 mt-3">
        Configure integrations in Settings → Integrations first
      </p>
    </div>
  );
}

// ── Filter Dropdown ───────────────────────────────────────────────────────────
function FilterPill({
  label, value, options, onChange,
}: {
  label: string;
  value: string;
  options: { label: string; value: string }[];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={clsx(
          'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs transition-colors',
          value
            ? 'bg-blue-600/20 border-blue-500/30 text-blue-400'
            : 'border-white/10 text-muted-foreground hover:text-foreground hover:border-white/20',
        )}
      >
        <span>{value ? `${label}: ${value}` : label}</span>
        <ChevronDown className="w-3 h-3 opacity-60" />
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="absolute top-full left-0 mt-1 z-20 rounded-lg border shadow-xl min-w-[140px] overflow-hidden"
              style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 18%)' }}
            >
              {options.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => { onChange(opt.value); setOpen(false); }}
                  className={clsx(
                    'w-full text-left px-3 py-2 text-xs transition-colors',
                    opt.value === value
                      ? 'bg-blue-600/20 text-blue-400'
                      : 'text-muted-foreground hover:text-foreground hover:bg-white/5',
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Scan status bar ───────────────────────────────────────────────────────────
const SCAN_STATUS_COLOR: Record<string, string> = {
  queued:    'text-gray-400',
  cloning:   'text-blue-400',
  scanning:  'text-yellow-400',
  analyzing: 'text-purple-400',
  completed: 'text-green-400',
  failed:    'text-red-400',
};

export default function RepositoriesPage() {
  const { role }  = usePermissions();
  const canScan   = canWriteSecurity(role);

  // ── API data ────────────────────────────────────────────────────────────────
  const { data: reposRaw,  loading: reposLoading,  refetch: refetchRepos } = useApi<any>('/security/repos');
  const { data: riskRaw,   loading: riskLoading,   refetch: refetchRisk  } = useApi<any>('/repos/risk');
  const { data: histRaw,   loading: histLoading }                          = useApi<any>('/security/scan-history?limit=30');

  const repos: Repo[]              = useMemo(() =>
    Array.isArray(reposRaw) ? reposRaw : (reposRaw?.data ?? reposRaw?.items ?? []),
    [reposRaw],
  );
  const riskList: RepoRisk[]       = useMemo(() =>
    Array.isArray(riskRaw?.data) ? riskRaw.data : (Array.isArray(riskRaw) ? riskRaw : []),
    [riskRaw],
  );
  const history: ScanHistoryEntry[] = useMemo(() =>
    Array.isArray(histRaw) ? histRaw : (histRaw?.data ?? histRaw?.history ?? []),
    [histRaw],
  );

  const riskMap = useMemo(
    () => new Map<string, RepoRisk>(riskList.map(r => [r.repo_id, r])),
    [riskList],
  );

  // ── Filters ─────────────────────────────────────────────────────────────────
  const [search,     setSearch]     = useState('');
  const [provider,   setProvider]   = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [langFilter, setLangFilter] = useState('');
  const [visFilter,  setVisFilter]  = useState('');

  // ── Scan state ───────────────────────────────────────────────────────────────
  const [scanningRepo, setScanningRepo] = useState<string | null>(null);
  const [activeScan,   setActiveScan]   = useState<any>(null);
  const [syncing,      setSyncing]      = useState(false);
  const [syncError,    setSyncError]    = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Drawer ───────────────────────────────────────────────────────────────────
  const [selectedRepo, setSelectedRepo] = useState<MergedRepo | null>(null);

  // ── Merged repos ─────────────────────────────────────────────────────────────
  const merged: MergedRepo[] = useMemo(() => {
    return repos
      .map(r => ({ ...r, risk: riskMap.get(r.id) }))
      .filter(r => {
        if (search && !r.full_name.toLowerCase().includes(search.toLowerCase())) return false;
        if (provider && r.provider !== provider) return false;
        if (riskFilter && (r.risk?.risk_level ?? 'unscanned') !== riskFilter) return false;
        if (langFilter && (r.language?.toLowerCase() ?? '') !== langFilter.toLowerCase()) return false;
        if (visFilter === 'private'  && !r.is_private)  return false;
        if (visFilter === 'public'   &&  r.is_private)  return false;
        return true;
      })
      .sort((a, b) => {
        const ra = RISK_ORDER[a.risk?.risk_level ?? 'low'] ?? 3;
        const rb = RISK_ORDER[b.risk?.risk_level ?? 'low'] ?? 3;
        if (ra !== rb) return ra - rb;
        return (b.risk?.risk_score ?? 0) - (a.risk?.risk_score ?? 0);
      });
  }, [repos, riskMap, search, provider, riskFilter, langFilter, visFilter]);

  // ── KPI derived values ───────────────────────────────────────────────────────
  const kpis = useMemo(() => {
    const total      = repos.length;
    const scanned    = repos.filter(r => !!r.last_scan_at).length;
    const atRisk     = merged.filter(r => ['critical', 'high'].includes(r.risk?.risk_level ?? '')).length;
    const healthy    = merged.filter(r => r.risk?.risk_level === 'low' || (r.last_scan_score ?? 0) >= 80).length;
    const coverage   = total > 0 ? Math.round((scanned / total) * 100) : 0;
    return { total, atRisk, healthy, coverage };
  }, [repos, merged]);

  // ── Filter options derived from data ─────────────────────────────────────────
  const providerOpts = useMemo(() => {
    const ps = [...new Set(repos.map(r => r.provider).filter(Boolean))];
    return [{ label: 'All Providers', value: '' }, ...ps.map(p => ({ label: p, value: p }))];
  }, [repos]);

  const langOpts = useMemo(() => {
    const ls = [...new Set(repos.map(r => r.language ?? '').filter(Boolean))].sort();
    return [{ label: 'All Languages', value: '' }, ...ls.map(l => ({ label: l, value: l }))];
  }, [repos]);

  const riskOpts = [
    { label: 'All Risk Levels', value: '' },
    { label: 'Critical',        value: 'critical' },
    { label: 'High',            value: 'high' },
    { label: 'Medium',          value: 'medium' },
    { label: 'Low',             value: 'low' },
  ];

  const visOpts = [
    { label: 'All Visibility', value: '' },
    { label: 'Private',        value: 'private' },
    { label: 'Public',         value: 'public' },
  ];

  // ── Scan handlers ─────────────────────────────────────────────────────────────
  const handleSync = useCallback(async () => {
    setSyncing(true); setSyncError(null);
    try {
      await apiPost('/security/repos/sync', {});
      await refetchRepos();
      await refetchRisk();
    } catch (e: any) {
      setSyncError(e?.response?.data?.detail ?? e?.message ?? 'Sync failed');
    } finally {
      setSyncing(false);
    }
  }, [refetchRepos, refetchRisk]);

  const handleScan = useCallback(async (repo: MergedRepo) => {
    setScanningRepo(repo.id);
    try {
      const res = await apiPost<any>('/security/scan', {
        repo_id: repo.id,
        branch:  repo.default_branch ?? 'main',
      });
      const scanId = res?.scan_id ?? res?.data?.scan_id ?? res?.id;
      if (scanId) {
        setActiveScan({ id: scanId, status: 'queued', repo_id: repo.id });
        // Poll for status
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(async () => {
          try {
            const r = await apiClient.get<any>(`/security/scan/${scanId}`);
            const s = r.data?.data ?? r.data;
            setActiveScan(s);
            if (['completed', 'failed'].includes(s?.status ?? '')) {
              clearInterval(pollRef.current!);
              pollRef.current = null;
              if (s?.status === 'completed') { refetchRepos(); refetchRisk(); }
            }
          } catch { /* ignore */ }
        }, 3000);
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? e?.message ?? 'Scan failed';
      if (msg !== 'integration_not_ready') setSyncError(msg);
    } finally {
      setScanningRepo(null);
    }
  }, [refetchRepos, refetchRisk]);

  const clearFilters = useCallback(() => {
    setSearch(''); setProvider(''); setRiskFilter(''); setLangFilter(''); setVisFilter('');
  }, []);

  const hasFilters = search || provider || riskFilter || langFilter || visFilter;
  const isLoading  = reposLoading || riskLoading;

  return (
    <div className="space-y-5">
      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-bold text-foreground flex items-center gap-2">
            <GitBranch className="w-5 h-5 text-blue-400" />
            Repositories
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {isLoading ? 'Loading…' : `${repos.length} repositories · sorted by risk`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canScan && merged.filter(r => !r.risk?.risk_level).length > 0 && (
            <button
              onClick={async () => {
                try {
                  await apiPost('/security/scan/batch', { max_repos: 5 });
                  setTimeout(() => { refetchRepos(); refetchRisk(); }, 5000);
                } catch { /* ignore */ }
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-purple-600/20 border border-purple-500/30 text-purple-400 hover:bg-purple-600/30 transition-colors"
            >
              <ScanLine className="w-3.5 h-3.5" />
              Scan All (Top 5)
            </button>
          )}
          <button
            onClick={handleSync} disabled={syncing || reposLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
            style={{ borderColor: 'hsl(230 15% 20%)' }}
          >
            <RefreshCw className={clsx('w-3.5 h-3.5', syncing && 'animate-spin')} />
            {syncing ? 'Syncing…' : 'Sync Repos'}
          </button>
        </div>
      </div>

      {syncError && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          {syncError}
          <button onClick={() => setSyncError(null)} className="ml-auto"><X className="w-3.5 h-3.5" /></button>
        </div>
      )}

      {/* Active scan status banner */}
      {activeScan && (
        <motion.div
          initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 px-4 py-2.5 rounded-lg border"
          style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 18%)' }}
        >
          {['completed', 'failed'].includes(activeScan.status)
            ? activeScan.status === 'completed'
              ? <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
              : <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
            : <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />}
          <div className="text-xs">
            <span className={clsx('font-medium', SCAN_STATUS_COLOR[activeScan.status] ?? 'text-muted-foreground')}>
              Scan {activeScan.status}
            </span>
            {activeScan.status === 'completed' && activeScan.security_score != null && (
              <span className="text-muted-foreground ml-2">
                Score: {activeScan.security_score} · {activeScan.critical_count ?? 0} critical · {activeScan.high_count ?? 0} high
              </span>
            )}
            {activeScan.ai_summary && (
              <span className="text-muted-foreground ml-2">· {activeScan.ai_summary.slice(0, 80)}…</span>
            )}
          </div>
          {['completed', 'failed'].includes(activeScan.status) && (
            <button onClick={() => setActiveScan(null)} className="ml-auto text-muted-foreground hover:text-foreground">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </motion.div>
      )}

      {/* ── KPI cards ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPICard icon={GitBranch}     label="Total Repositories"  value={kpis.total}
          color="border-l-blue-500"   loading={reposLoading} />
        <KPICard icon={CheckCircle}   label="Healthy Repositories" value={kpis.healthy}
          color="border-l-green-500"  loading={reposLoading}
          sub={repos.length > 0 ? `${Math.round(kpis.healthy / Math.max(repos.length, 1) * 100)}% of total` : undefined} />
        <KPICard icon={AlertTriangle} label="Repositories At Risk"  value={kpis.atRisk}
          color="border-l-red-500"    loading={reposLoading} />
        <KPICard icon={Activity}      label="Scan Coverage"        value={`${kpis.coverage}%`}
          color="border-l-purple-500" loading={reposLoading}
          sub={`${repos.filter(r => !!r.last_scan_at).length} of ${repos.length} scanned`} />
      </div>

      {/* ── Charts ───────────────────────────────────────────────────────── */}
      {!isLoading && repos.length > 0 && (
        <RepoCharts repos={merged} history={history} loading={histLoading} />
      )}

      {/* ── Filters toolbar ──────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search repositories…"
            className="pl-8 pr-3 py-1.5 text-xs rounded-lg border outline-none focus:border-blue-500/50 w-52 bg-transparent transition-all"
            style={{ borderColor: 'hsl(230 15% 20%)', color: 'hsl(215 16% 80%)' }}
          />
        </div>
        <Filter className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
        <FilterPill label="Provider"   value={provider}   options={providerOpts} onChange={setProvider}   />
        <FilterPill label="Risk"       value={riskFilter} options={riskOpts}     onChange={setRiskFilter} />
        <FilterPill label="Language"   value={langFilter} options={langOpts}     onChange={setLangFilter} />
        <FilterPill label="Visibility" value={visFilter}  options={visOpts}      onChange={setVisFilter}  />
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="w-3 h-3" />Clear
          </button>
        )}
        <span className="ml-auto text-[10px] text-muted-foreground/60">
          {merged.length} of {repos.length} repositories
        </span>
      </div>

      {/* ── Repository grid ──────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-44" />)}
        </div>
      ) : repos.length === 0 ? (
        <OnboardingCards onSync={handleSync} syncing={syncing} />
      ) : merged.length === 0 ? (
        <div className="card-base py-12 text-center">
          <Shield className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-30" />
          <p className="text-sm font-medium text-foreground">No repositories match your filters</p>
          <button onClick={clearFilters} className="mt-2 text-xs text-blue-400 hover:text-blue-300 transition-colors">
            Clear all filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          <AnimatePresence>
            {merged.map((repo, i) => (
              <motion.div
                key={repo.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.12, delay: i * 0.02 }}
              >
                <RepoCard
                  repo={repo}
                  onClick={() => setSelectedRepo(repo)}
                  onScan={() => handleScan(repo)}
                  canScan={canScan}
                  isScanning={scanningRepo === repo.id || (activeScan?.repo_id === repo.id && !['completed', 'failed'].includes(activeScan?.status ?? ''))}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* ── Repo drawer ──────────────────────────────────────────────────── */}
      <RepoDrawer
        repo={selectedRepo}
        onClose={() => setSelectedRepo(null)}
      />
    </div>
  );
}
