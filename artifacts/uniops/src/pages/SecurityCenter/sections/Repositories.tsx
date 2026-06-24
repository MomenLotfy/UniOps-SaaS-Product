import { useState, useRef, useEffect } from 'react';
import { GitBranch, Play, RefreshCw, ChevronDown, Loader2, CheckCircle, XCircle, Filter } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { AnimatePresence, motion } from 'framer-motion';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const SCAN_STATUS_COLOR: Record<string, string> = {
  queued: 'text-gray-400', cloning: 'text-blue-400', scanning: 'text-yellow-400',
  analyzing: 'text-purple-400', completed: 'text-green-400', failed: 'text-red-400',
};

export default function Repositories() {
  const { role } = usePermissions();
  const canScan = canWriteSecurity(role);

  const { data: reposRaw, loading: reposLoading, refetch: refetchRepos } = useApi<any>('/security/repos');
  const repos = Array.isArray(reposRaw) ? reposRaw : (reposRaw?.data ?? []);

  const [selectedRepo, setSelectedRepo] = useState<any>(null);
  const [branch, setBranch]             = useState('');
  const [repoOpen, setRepoOpen]         = useState(false);
  const [scanning, setScanning]         = useState(false);
  const [syncing, setSyncing]           = useState(false);
  const [activeScan, setActiveScan]     = useState<any>(null);
  const [scanError, setScanError]       = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [providerFilter, setProviderFilter] = useState('');
  const filtered = repos.filter((r: any) => !providerFilter || r.provider === providerFilter);

  useEffect(() => {
    if (!activeScan?.id || ['completed', 'failed'].includes(activeScan?.status)) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      if (activeScan?.status === 'completed') refetchRepos();
      return;
    }
    pollRef.current = setInterval(async () => {
      if (document.hidden) return;
      try {
        const res = await apiClient.get<any>(`/security/scan/${activeScan.id}`);
        setActiveScan(res.data?.data ?? res.data);
      } catch { /* ignore */ }
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [activeScan?.id, activeScan?.status]);

  const handleSync = async () => {
    setSyncing(true); setScanError(null);
    try {
      await apiPost('/security/repos/sync', {});
      await refetchRepos();
    } catch (e: any) {
      setScanError(e?.message ?? 'Sync failed');
    } finally { setSyncing(false); }
  };

  const handleScan = async () => {
    if (!selectedRepo) return;
    setScanning(true); setScanError(null);
    try {
      const res = await apiPost<any>('/security/scan', {
        repo_id: selectedRepo.id,
        branch:  branch || selectedRepo.default_branch || 'main',
      });
      setActiveScan({ id: res?.scan_id ?? res?.data?.scan_id ?? res?.id, status: 'queued' });
    } catch (e: any) { setScanError(e?.message ?? 'Scan failed'); }
    finally { setScanning(false); }
  };

  const isRunning = activeScan && !['completed', 'failed'].includes(activeScan?.status ?? '');

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Repositories</h1>
          <p className="text-xs text-muted-foreground">{filtered.length} repositories connected</p>
        </div>
        <button onClick={handleSync} disabled={syncing || reposLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
          style={{ borderColor: 'hsl(230 15% 20%)' }}>
          <RefreshCw className={clsx('w-3.5 h-3.5', syncing && 'animate-spin')} />
          {syncing ? 'Syncing…' : 'Sync Repos'}
        </button>
      </div>

      {/* Scanner panel */}
      {canScan && (
        <div className="card-base p-4 border border-blue-500/20" style={{ background: 'hsl(230 15% 8%)' }}>
          <p className="text-xs font-semibold text-blue-400 mb-3">DevSecOps Scanner · SAST · Deps · Secrets · Container · CI/CD</p>
          <div className="flex gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <button onClick={() => setRepoOpen(v => !v)}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs rounded-lg border text-left hover:border-blue-500/50 transition-colors"
                style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: selectedRepo ? 'white' : 'hsl(215 16% 47%)' }}>
                <GitBranch className="w-3.5 h-3.5 flex-shrink-0" />
                <span className="flex-1 truncate">{selectedRepo ? selectedRepo.full_name : 'Select repository…'}</span>
                <ChevronDown className="w-3.5 h-3.5 flex-shrink-0" />
              </button>
              <AnimatePresence>
                {repoOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setRepoOpen(false)} />
                    <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      className="absolute top-full left-0 right-0 z-20 mt-1 rounded-lg border shadow-xl max-h-48 overflow-y-auto"
                      style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 20%)' }}>
                      {repos.length === 0
                        ? <p className="p-3 text-xs text-muted-foreground">No repos — click Sync Repos first.</p>
                        : repos.map((r: any) => (
                          <button key={r.id} onClick={() => { setSelectedRepo(r); setBranch(r.default_branch ?? 'main'); setRepoOpen(false); }}
                            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-white/5 transition-colors">
                            <GitBranch className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                            <span className="flex-1 truncate text-white">{r.full_name}</span>
                            {r.last_scan_score != null && (
                              <span className={clsx('font-mono text-xs', r.last_scan_score >= 80 ? 'text-green-400' : r.last_scan_score >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                                {r.last_scan_score}
                              </span>
                            )}
                          </button>
                        ))}
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>
            <input value={branch} onChange={e => setBranch(e.target.value)} placeholder="branch (default)"
              className="px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 w-36"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }} />
            <button onClick={handleScan} disabled={!selectedRepo || scanning || !!isRunning}
              className={clsx('flex items-center gap-2 px-4 py-2 text-xs rounded-lg font-semibold transition-all',
                !selectedRepo || scanning || isRunning
                  ? 'bg-blue-500/20 text-blue-400/50 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700 text-white')}>
              {scanning || isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              {scanning ? 'Starting…' : isRunning ? 'Scanning…' : 'Scan'}
            </button>
          </div>
          {activeScan && (
            <div className="mt-3 p-3 rounded-lg flex items-center gap-3" style={{ background: 'hsl(230 15% 12%)' }}>
              {isRunning ? <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                : activeScan.status === 'completed' ? <CheckCircle className="w-4 h-4 text-green-400" />
                : <XCircle className="w-4 h-4 text-red-400" />}
              <div>
                <p className={clsx('text-xs font-medium', SCAN_STATUS_COLOR[activeScan.status] ?? 'text-gray-400')}>
                  {activeScan.status}
                </p>
                {activeScan.status === 'completed' && (
                  <p className="text-xs text-muted-foreground">
                    Score: {activeScan.security_score ?? '—'} · {activeScan.critical_count ?? 0} critical · {activeScan.high_count ?? 0} high
                  </p>
                )}
              </div>
            </div>
          )}
          {scanError && <p className="mt-2 text-xs text-red-400">{scanError}</p>}
        </div>
      )}

      {/* Provider filter */}
      <div className="flex items-center gap-2">
        <Filter className="w-3.5 h-3.5 text-muted-foreground" />
        {['', 'github', 'gitlab'].map(p => (
          <button key={p} onClick={() => setProviderFilter(p)}
            className={clsx('px-2.5 py-1 rounded text-xs capitalize transition-colors',
              providerFilter === p ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {p || 'All'}
          </button>
        ))}
      </div>

      {/* Repo list */}
      <div className="space-y-2">
        {reposLoading ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)
        ) : filtered.length === 0 ? (
          <div className="card-base py-10 text-center">
            <GitBranch className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No repositories. Click Sync Repos to connect GitHub or GitLab.</p>
          </div>
        ) : filtered.map((r: any) => (
          <div key={r.id} className="card-base p-4 flex items-center gap-4">
            <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
              <GitBranch className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">{r.full_name}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-muted-foreground capitalize">{r.provider}</span>
                <span className="text-[10px] text-muted-foreground">·</span>
                <span className="text-[10px] text-muted-foreground">{r.default_branch ?? 'main'}</span>
                {r.language && <><span className="text-[10px] text-muted-foreground">·</span>
                  <span className="text-[10px] text-muted-foreground">{r.language}</span></>}
                {r.is_private && <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground">private</span>}
              </div>
            </div>
            <div className="text-right flex-shrink-0">
              {r.last_scan_score != null ? (
                <>
                  <p className={clsx('text-sm font-bold',
                    r.last_scan_score >= 80 ? 'text-green-400' : r.last_scan_score >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                    {r.last_scan_score}
                  </p>
                  <p className="text-[10px] text-muted-foreground">score</p>
                </>
              ) : (
                <p className="text-xs text-muted-foreground">Not scanned</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
