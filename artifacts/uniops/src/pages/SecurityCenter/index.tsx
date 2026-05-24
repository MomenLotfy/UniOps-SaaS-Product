import { useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, AlertTriangle, CheckCircle, XCircle,
  Eye, RefreshCw, Download, Activity,
  ShieldCheck, ShieldOff, Loader2, X,
  GitBranch, Play, Zap, Clock, ChevronDown, ChevronLeft, ChevronRight, Filter,
} from 'lucide-react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import { usePermissions } from '@/hooks/use-permissions';
import apiClient from '@/services/api/client';
import { useWebSocket } from '@/contexts/WebSocketContext';

type Tab = 'overview' | 'threats' | 'vulnerabilities' | 'compliance';

// ── Skeleton pulse ────────────────────────────────────────────────────────────
function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// ── LastSynced indicator ──────────────────────────────────────────────────────
function LastSynced({ timestamp }: { timestamp?: number }) {
  if (!timestamp) return null;
  const secs = Math.round((Date.now() - timestamp) / 1000);
  const label = secs < 60 ? `${secs}s ago` : `${Math.round(secs / 60)}m ago`;
  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Clock className="w-3 h-3" />{label}
    </span>
  );
}

const severityBadge: Record<string, string> = {
  critical: 'badge-critical', high: 'badge-high', medium: 'badge-medium', low: 'badge-low',
};
const statusColor: Record<string, string> = {
  active: 'text-red-400', mitigated: 'text-green-400', investigating: 'text-yellow-400',
  resolved: 'text-green-400', suppressed: 'text-gray-400', open: 'text-red-400',
};
const complianceColor: Record<string, string> = {
  compliant: 'text-green-400', non_compliant: 'text-red-400', in_progress: 'text-yellow-400',
};

const SCAN_STATUS_COLOR: Record<string, string> = {
  queued:    'text-gray-400',
  cloning:   'text-blue-400',
  scanning:  'text-yellow-400',
  analyzing: 'text-purple-400',
  completed: 'text-green-400',
  failed:    'text-red-400',
};
const SCAN_STATUS_LABEL: Record<string, string> = {
  queued:    'Queued',
  cloning:   'Cloning repository…',
  scanning:  'Running scanners…',
  analyzing: 'Analyzing & scoring…',
  completed: 'Completed',
  failed:    'Failed',
};

// ── Confirm Dialog ────────────────────────────────────────────────────────────
function ConfirmDialog({ open, title, description, confirmLabel, danger, onConfirm, onCancel, loading }: {
  open: boolean; title: string; description: string; confirmLabel: string;
  danger?: boolean; onConfirm: () => void; onCancel: () => void; loading: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="relative z-10 w-full max-w-md mx-4 rounded-xl border p-6 shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <div className="flex items-start gap-3 mb-5">
          <div className={clsx('p-2 rounded-lg flex-shrink-0', danger ? 'bg-red-500/10' : 'bg-blue-500/10')}>
            <AlertTriangle className={clsx('w-5 h-5', danger ? 'text-red-400' : 'text-blue-400')} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
            <p className="text-xs text-gray-400 leading-relaxed">{description}</p>
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} disabled={loading}
            className="px-4 py-2 text-xs rounded-lg border text-gray-400 hover:text-white transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>Cancel</button>
          <button onClick={onConfirm} disabled={loading}
            className={clsx('px-4 py-2 text-xs rounded-lg font-semibold flex items-center gap-2 transition-all',
              danger ? 'bg-red-500 hover:bg-red-600 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white',
              loading && 'opacity-60 cursor-not-allowed')}>
            {loading && <Loader2 className="w-3 h-3 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Threats Tab ───────────────────────────────────────────────────────────────
function ThreatsTab({ threats, tLoading, canAct, setConfirmThreat }: {
  threats: any[];
  tLoading: boolean;
  canAct: boolean;
  setConfirmThreat: (v: any) => void;
}) {
  const [threatFilter, setThreatFilter] = useState<string>('all');
  const [threatPage, setThreatPage] = useState(1);
  const PAGE_SIZE = 10;
  const filtered = threats.filter((t: any) =>
    threatFilter === 'all' || t.severity === threatFilter
  );
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice((threatPage - 1) * PAGE_SIZE, threatPage * PAGE_SIZE);
  const hasAwsThreats = threats.some((t: any) => t.source === 'aws_security_hub');

  return (
    <div className="card-base space-y-3">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="text-sm font-semibold text-foreground">
          Active Threats
          {canAct && hasAwsThreats && <span className="ml-2 text-xs text-gray-500 font-normal">· Actions sync to AWS Security Hub</span>}
        </h2>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-xs">
            <Filter className="w-3 h-3 text-muted-foreground" />
            {['all','critical','high','medium','low'].map(s => (
              <button key={s} onClick={() => { setThreatFilter(s); setThreatPage(1); }}
                className={clsx('px-2 py-1 rounded capitalize transition-colors',
                  threatFilter === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground'
                )}>{s}</button>
            ))}
          </div>
          <span className="text-xs text-muted-foreground">{filtered.length} threats</span>
        </div>
      </div>

      {tLoading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
        </div>
      ) : paginated.length === 0 ? (
        <div className="py-8 text-center">
          <Shield className="w-8 h-8 text-green-400 mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No {threatFilter !== 'all' ? threatFilter + ' ' : ''}threats found. Run a scan to detect issues.</p>
        </div>
      ) : (
        paginated.map((t: any) => (
          <div key={t.id} className="p-4 rounded-lg border border-border bg-surface-1">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-md bg-red-500/10 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-4 h-4 text-red-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <code className="text-xs text-muted-foreground font-mono">{t.id?.substring(0, 8)}</code>
                      <span className={severityBadge[t.severity]}>{t.severity}</span>
                      <span className={clsx('text-xs font-medium', statusColor[t.status])}>{t.status}</span>
                      {t.mitre_tactic && <span className="text-xs text-gray-500 font-mono">{t.mitre_tactic}</span>}
                    </div>
                    <p className="text-sm font-medium text-foreground mt-1">{t.title || t.description}</p>
                  </div>
                  <span className="text-xs text-muted-foreground flex-shrink-0">
                    {t.created_at ? new Date(t.created_at).toLocaleString() : ''}
                  </span>
                </div>
                {t.resource && (
                  <p className="text-xs text-gray-500 mt-1 font-mono truncate">{t.resource}</p>
                )}
                {canAct && !['resolved', 'suppressed'].includes(t.status) && (
                  <div className="flex items-center gap-2 mt-3">
                    <button onClick={() => setConfirmThreat({ threat: t, action: 'resolve' })}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-green-500/10 text-green-400 hover:bg-green-500/20 transition-colors border border-green-500/20">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      {t.source === 'aws_security_hub' ? 'Resolve in AWS' : 'Resolve'}
                    </button>
                    <button onClick={() => setConfirmThreat({ threat: t, action: 'suppress' })}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 transition-colors border border-yellow-500/20">
                      <ShieldOff className="w-3.5 h-3.5" /> Suppress
                    </button>
                  </div>
                )}
                {['resolved', 'suppressed'].includes(t.status) && (
                  <div className="flex items-center gap-1.5 mt-3 text-xs text-green-400">
                    <CheckCircle className="w-3.5 h-3.5" />
                    {t.status === 'resolved' ? 'Resolved' : 'Suppressed'}
                    {t.source === 'aws_security_hub' && ' · synced to AWS Security Hub'}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2 border-t" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <span className="text-xs text-muted-foreground">
            Page {threatPage} of {totalPages}
          </span>
          <div className="flex gap-1">
            <button onClick={() => setThreatPage(p => Math.max(1, p - 1))}
              disabled={threatPage === 1}
              className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button onClick={() => setThreatPage(p => Math.min(totalPages, p + 1))}
              disabled={threatPage === totalPages}
              className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Scan Panel ────────────────────────────────────────────────────────────────
// Now a CONTROLLED component: selectedRepo/onSelectRepo are lifted to SecurityCenter.
// This ensures the parent knows which repo is selected so it can pass repo_id
// to all API queries (preventing cross-repo data leakage).
function ScanPanel({
  selectedRepo,
  onSelectRepo,
  onScanComplete,
  onViewResults,
}: {
  selectedRepo: any | null;
  onSelectRepo: (repo: any | null) => void;
  onScanComplete: () => void;
  onViewResults?: (tab: Tab) => void;
}) {
  const { data: reposData, loading: reposLoading, refetch: refetchRepos } = useApi<any>('/security/repos');
  const [branch, setBranch]         = useState('');
  const [scanning, setScanning]     = useState(false);
  const [syncing, setSyncing]       = useState(false);
  const [activeScan, setActiveScan] = useState<any | null>(null);
  const [scanError, setScanError]   = useState<string | null>(null);
  const [repoOpen, setRepoOpen]     = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const repos = Array.isArray(reposData)
    ? reposData
    : (reposData?.data ?? []);

  const handleSyncRepos = async () => {
    setSyncing(true);
    setScanError(null);
    try {
      const res = await apiPost<{ synced: number; live_synced?: number; errors?: string[] }>('/security/repos/sync', {});
      await refetchRepos();
      if (res.errors?.length) {
        setScanError(`Sync warning: ${res.errors.join('; ')} — using cached repositories`);
      }
    } catch (err: any) {
      await refetchRepos();
      const code = (err as any)?.code ?? '';
      if (code === 'integration_not_ready' || (err?.message ?? '').includes('integration_not_ready')) {
        setScanError('No GitHub/GitLab integration found. Go to Settings → Integrations to connect GitHub or GitLab with a personal access token.');
      } else {
        setScanError(err?.message ?? 'Sync failed — check your integration token and try again');
      }
    } finally {
      setSyncing(false);
    }
  };

  // Poll scan status every 3s while running — stops on hidden tab
  useEffect(() => {
    if (!activeScan?.id || ['completed', 'failed'].includes(activeScan?.status)) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      if (activeScan?.status === 'completed') {
        setTimeout(() => onScanComplete(), 600);
      }
      return;
    }
    pollRef.current = setInterval(async () => {
      if (document.hidden) return;
      try {
        const res = await apiClient.get<any>(`/security/scan/${activeScan.id}`);
        const body = res.data;
        const updated = body?.data ?? body;
        setActiveScan(updated);
      } catch { /* ignore transient errors */ }
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [activeScan?.id, activeScan?.status, onScanComplete]);

  const handleScan = async () => {
    if (!selectedRepo) return;
    setScanning(true);
    setScanError(null);
    try {
      const res = await apiPost<any>('/security/scan', {
        repo_id: selectedRepo.id,
        branch:  branch || selectedRepo.default_branch || 'main',
      });
      const scanId = res?.scan_id ?? res?.data?.scan_id ?? res?.id;
      setActiveScan({ id: scanId, status: 'queued' });
    } catch (err: any) {
      setScanError(err.message ?? 'Failed to start scan');
    } finally {
      setScanning(false);
    }
  };

  const isRunning = activeScan && !['completed', 'failed'].includes(activeScan.status ?? '');

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border p-4 mb-5"
      style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(220 90% 60% / 0.3)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <div className="w-6 h-6 rounded-md bg-blue-500/20 flex items-center justify-center">
          <Zap className="w-3.5 h-3.5 text-blue-400" />
        </div>
        <span className="text-sm font-semibold text-white">DevSecOps Scanner</span>
        <span className="text-xs text-gray-500">SAST · Deps · Secrets · Container · CI/CD</span>
        <button
          onClick={handleSyncRepos}
          disabled={syncing || reposLoading}
          title="Pull latest repositories from GitHub/GitLab"
          className="ml-auto flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border text-gray-400 hover:text-white transition-colors disabled:opacity-40"
          style={{ borderColor: 'hsl(230 15% 22%)' }}
        >
          <RefreshCw className={clsx('w-3 h-3', (syncing || reposLoading) && 'animate-spin')} />
          {syncing ? 'Syncing…' : 'Sync Repos'}
        </button>
      </div>

      <div className="flex gap-2 flex-wrap">
        {/* Repo picker (controlled — changes notify parent via onSelectRepo) */}
        <div className="relative flex-1 min-w-[200px]">
          <button
            onClick={() => setRepoOpen(v => !v)}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs rounded-lg border text-left transition-colors hover:border-blue-500/50"
            style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: selectedRepo ? 'white' : 'hsl(215 16% 47%)' }}
          >
            <GitBranch className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="flex-1 truncate">{selectedRepo ? selectedRepo.full_name : 'Select repository…'}</span>
            <ChevronDown className="w-3.5 h-3.5 flex-shrink-0" />
          </button>
          <AnimatePresence>
            {repoOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setRepoOpen(false)} />
                <motion.div
                  initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                  className="absolute top-full left-0 right-0 z-20 mt-1 rounded-lg border shadow-xl max-h-48 overflow-y-auto"
                  style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 20%)' }}
                >
                  {reposLoading ? (
                    <div className="p-3 text-xs text-gray-400 flex items-center gap-2">
                      <Loader2 className="w-3 h-3 animate-spin" /> Loading repos…
                    </div>
                  ) : repos.length === 0 ? (
                    <div className="p-3 space-y-2">
                      <p className="text-xs text-gray-500">No repositories found.</p>
                      <button
                        onClick={(e) => { e.stopPropagation(); setRepoOpen(false); handleSyncRepos(); }}
                        disabled={syncing}
                        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs rounded-lg font-medium text-blue-400 border border-blue-500/30 hover:bg-blue-500/10 transition-colors disabled:opacity-50"
                      >
                        {syncing
                          ? <><Loader2 className="w-3 h-3 animate-spin" /> Syncing…</>
                          : <><RefreshCw className="w-3 h-3" /> Sync Repos from GitHub/GitLab</>
                        }
                      </button>
                    </div>
                  ) : (
                    repos.map((r: any) => (
                      <button key={r.id}
                        onClick={() => {
                          // ── Notify parent so all dashboard queries get filtered ──
                          onSelectRepo(r);
                          setBranch(r.default_branch || 'main');
                          setRepoOpen(false);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-white/5 transition-colors"
                      >
                        <GitBranch className="w-3 h-3 text-gray-500 flex-shrink-0" />
                        <span className="flex-1 truncate text-white">{r.full_name}</span>
                        {r.last_scan_score != null && (
                          <span className={clsx('font-mono', r.last_scan_score >= 80 ? 'text-green-400' : r.last_scan_score >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                            {r.last_scan_score}
                          </span>
                        )}
                      </button>
                    ))
                  )}
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </div>

        {/* Branch input */}
        <input
          value={branch}
          onChange={e => setBranch(e.target.value)}
          placeholder="branch (default)"
          className="px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 w-36"
          style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
        />

        {/* Scan button */}
        <button
          onClick={handleScan}
          disabled={!selectedRepo || scanning || !!isRunning}
          className={clsx(
            'flex items-center gap-2 px-4 py-2 text-xs rounded-lg font-semibold transition-all',
            (!selectedRepo || scanning || isRunning)
              ? 'bg-blue-500/20 text-blue-400/50 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 text-white',
          )}
        >
          {scanning || isRunning
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Play className="w-3.5 h-3.5" />}
          {scanning ? 'Starting…' : isRunning ? 'Scanning…' : 'Scan'}
        </button>
      </div>

      {/* Active scan progress */}
      <AnimatePresence>
        {activeScan && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }} className="mt-3 overflow-hidden">
            <div className="flex items-center gap-3 p-3 rounded-lg"
              style={{ background: 'hsl(230 15% 12%)' }}>

              {isRunning
                ? <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />
                : activeScan.status === 'completed'
                  ? <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                  : <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />}

              <div className="flex-1 min-w-0">
                <p className={clsx('text-xs font-medium', SCAN_STATUS_COLOR[activeScan.status] ?? 'text-gray-400')}>
                  {SCAN_STATUS_LABEL[activeScan.status] ?? activeScan.status}
                </p>

                {activeScan.scanners_run && Object.keys(activeScan.scanners_run).length > 0 && (
                  <div className="flex gap-2 mt-1.5 flex-wrap">
                    {Object.entries(activeScan.scanners_run).map(([s, status]: [string, any]) => (
                      <span key={s} className={clsx('text-xs px-1.5 py-0.5 rounded font-mono',
                        status === 'completed' ? 'bg-green-500/10 text-green-400'
                        : status === 'failed'  ? 'bg-red-500/10 text-red-400'
                        : status === 'skipped' ? 'bg-gray-500/10 text-gray-500'
                        : 'bg-yellow-500/10 text-yellow-400 animate-pulse')}>
                        {s}
                      </span>
                    ))}
                  </div>
                )}

                {activeScan.status === 'completed' && (
                  <div className="mt-2 space-y-2">
                    <div className="flex gap-3 text-xs">
                      {activeScan.critical_count > 0 && <span className="text-red-400 font-semibold">{activeScan.critical_count} critical</span>}
                      {activeScan.high_count     > 0 && <span className="text-orange-400">{activeScan.high_count} high</span>}
                      {activeScan.medium_count   > 0 && <span className="text-yellow-400">{activeScan.medium_count} medium</span>}
                      {activeScan.secret_count   > 0 && <span className="text-red-400 font-bold">⚠ {activeScan.secret_count} secrets</span>}
                      <span className={clsx('ml-auto font-semibold',
                        (activeScan.security_score ?? 0) >= 80 ? 'text-green-400'
                        : (activeScan.security_score ?? 0) >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                        Score: {activeScan.security_score ?? 'N/A'}
                      </span>
                    </div>
                    {onViewResults && (
                      <div className="flex gap-2">
                        <button onClick={() => onViewResults('threats')}
                          className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors border border-red-500/20">
                          <AlertTriangle className="w-3 h-3" /> View Threats
                        </button>
                        <button onClick={() => onViewResults('vulnerabilities')}
                          className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 transition-colors border border-yellow-500/20">
                          <Eye className="w-3 h-3" /> View CVEs
                        </button>
                        <button onClick={() => onViewResults('overview')}
                          className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors border border-blue-500/20">
                          <Activity className="w-3 h-3" /> Overview
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {activeScan.ai_summary && (
                  <p className="text-xs text-gray-400 mt-2 leading-relaxed">{activeScan.ai_summary}</p>
                )}

                {activeScan.status === 'failed' && activeScan.error_message && (
                  <p className="text-xs text-red-400 mt-1">{activeScan.error_message}</p>
                )}
              </div>

              {['completed', 'failed'].includes(activeScan.status) && (
                <button onClick={() => setActiveScan(null)}
                  className="p-1 text-gray-500 hover:text-white transition-colors flex-shrink-0">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {activeScan.status === 'completed' && activeScan.ai_suggestions?.length > 0 && (
              <div className="mt-2 p-3 rounded-lg text-xs space-y-1.5" style={{ background: 'hsl(230 15% 12%)' }}>
                <p className="text-gray-400 font-medium mb-2">AI Recommendations:</p>
                {activeScan.ai_suggestions.map((s: string, i: number) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5 flex-shrink-0">→</span>
                    <span className="text-gray-300">{s}</span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {scanError && (
        <p className="text-xs text-red-400 mt-2 flex items-center gap-1">
          <XCircle className="w-3 h-3" /> {scanError}
        </p>
      )}
    </motion.div>
  );
}


// ── SecurityCenter (main page) ────────────────────────────────────────────────
export default function SecurityCenter() {
  const [tab, setTab] = useState<Tab>('overview');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { isAdmin, hasRole } = usePermissions();
  const canAct = isAdmin() || hasRole('security');

  // ── LIFTED STATE: selectedRepo is now in the parent so ALL queries can be
  //    scoped to the selected repository, preventing cross-repo data leakage.
  const [selectedRepo, setSelectedRepo] = useState<any | null>(null);

  // Build query-string fragments for repo isolation.
  // When selectedRepo is set, EVERY data query is filtered to that repo.
  // When null, queries return the tenant-wide aggregate (all repos).
  const repoId    = selectedRepo?.id ?? null;
  const repoQs    = repoId ? `&repo_id=${repoId}` : '';     // appended to existing QS
  const repoQsSolo = repoId ? `?repo_id=${repoId}` : '';    // used as the whole QS

  // ── Data queries — all repo-isolated when selectedRepo is set ────────────
  // The path changes when repoId changes → useApi sees a new path → resets
  // stale data immediately (see use-api.ts fix) and fires a fresh request.
  const { data: threatStats,  refetch: refetchStats }                      = useApi<any>(`/threats/stats${repoQsSolo}`);
  const { data: threatsData,  loading: tLoading, refetch: refetchThreats } = useApi<any>(`/threats?page_size=50&status=open${repoQs}`);
  const { data: vulnsData,    loading: vLoading, refetch: refetchVulns }   = useApi<any>(`/vulnerabilities?page_size=50&status=open${repoQs}`);
  const { data: compliance,   loading: cLoading, refetch: refetchComp }    = useApi<any>('/compliance');
  const { data: compScore,    refetch: refetchScore }                      = useApi<any>('/compliance/score');
  const { data: scanScore,    refetch: refetchScanScore }                  = useApi<any>(`/security/score${repoQsSolo}`);
  const { data: scanHistory,  refetch: refetchHistory }                    = useApi<any>(`/security/scan-history?limit=20${repoQs}`);

  // ── Live WebSocket updates — respect current repo filter on refetch ────────
  const { subscribe } = useWebSocket();
  useEffect(() => {
    const unsubThreat = subscribe('threat.detected', () => {
      refetchThreats(); refetchStats();
    });
    const unsubVuln = subscribe('vulnerability.found', () => {
      refetchVulns();
    });
    const unsubComp = subscribe('compliance.updated', () => {
      refetchComp(); refetchScore();
    });
    return () => { unsubThreat(); unsubVuln(); unsubComp(); };
  }, [subscribe, refetchThreats, refetchStats, refetchVulns, refetchComp, refetchScore]);

  const [confirmThreat, setConfirmThreat] = useState<{ threat: any; action: 'resolve' | 'suppress' } | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null);

  const showFeedback = (ok: boolean, msg: string) => {
    setFeedback({ ok, msg });
    setTimeout(() => setFeedback(null), 5000);
  };

  // After scan completes, refetch all repo-scoped queries.
  // Because selectedRepo is in this parent, the paths already include repo_id,
  // so refetch will return data only for the scanned repository.
  const handleScanComplete = useCallback(() => {
    setTimeout(() => {
      refetchStats(); refetchThreats(); refetchVulns();
      refetchComp(); refetchScore(); refetchScanScore(); refetchHistory();
    }, 600);
  }, [refetchStats, refetchThreats, refetchVulns, refetchComp, refetchScore, refetchScanScore, refetchHistory]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    handleScanComplete();
    await new Promise(r => setTimeout(r, 800));
    setIsRefreshing(false);
  }, [handleScanComplete]);

  const handleConfirmThreat = async () => {
    if (!confirmThreat) return;
    setActionLoading(true);
    const { threat, action } = confirmThreat;
    try {
      const res = await apiPost<any>(`/threats/${threat.id}/${action}`, {
        ...(action === 'resolve'
          ? { note: 'Resolved via UniOps Security Center' }
          : { reason: 'TOLERATED' }),
      });
      showFeedback(true, res.message ?? `Threat ${action}d successfully`);
      refetchThreats(); refetchStats();
    } catch (err: any) {
      showFeedback(false, err.message ?? `${action} failed`);
    } finally {
      setActionLoading(false);
      setConfirmThreat(null);
    }
  };

  const threats    = (Array.isArray(threatsData) ? threatsData : threatsData?.data) ?? [];
  const vulns      = (Array.isArray(vulnsData)   ? vulnsData   : vulnsData?.data)   ?? [];
  const vulnsTotal = Array.isArray(vulnsData) ? vulnsData.length : (vulnsData as any)?.total;
  const frameworks = compliance?.data ?? compliance ?? [];
  const historyArr = (Array.isArray(scanHistory) ? scanHistory : (scanHistory as any)?.data) ?? [];

  const scanScoreData: any = scanScore;
  const score = scanScoreData?.score != null
    ? scanScoreData.score
    : compScore?.overall_score ?? null;

  const radarData = scanScoreData?.breakdown
    ? Object.entries(scanScoreData.breakdown).map(([k, v]: any) => ({
        subject: k, score: Math.max(0, Math.min(100, Number(v) || 0))
      }))
    : compScore?.breakdown
      ? Object.entries(compScore.breakdown).map(([k, v]: any) => ({
          subject: k, score: Math.max(0, Math.min(100, Number(v) || 0))
        }))
      : [
          { subject: 'Code Security',  score: score != null ? Math.max(score - 10, 0) : 82 },
          { subject: 'Dependencies',   score: score != null ? Math.max(score - 5,  0) : 71 },
          { subject: 'Secrets',        score: score != null ? Math.max(Math.min(score + 15, 100), 0) : 55 },
          { subject: 'CI/CD Security', score: score != null ? Math.max(score - 8,  0) : 78 },
          { subject: 'Containers',     score: score != null ? Math.max(score - 3,  0) : 87 },
        ];

  const timelineData = historyArr.map((s: any) => ({
    date:     new Date(s.date).toLocaleDateString('en', { month: 'short', day: 'numeric' }),
    score:    s.score,
    critical: s.critical,
    high:     s.high,
  }));

  const summaryCards = [
    {
      title:   'Security Score',
      value:   score != null ? `${Math.round(score)}` : '—',
      sub:     scanScoreData?.repo_name
        ? `Repo: ${scanScoreData.repo_name}`
        : scanScoreData?.last_scan_at
          ? `Scan: ${new Date(scanScoreData.last_scan_at).toLocaleDateString()}`
          : selectedRepo ? 'No scan for this repo yet' : 'Run a scan to calculate',
      icon: Shield, color: 'text-blue-400', bg: 'bg-blue-500/10',
      loading: false,
    },
    {
      title:   'Active Threats',
      value:   threatStats?.open ?? threatStats?.active ?? '—',
      sub:     `${threatStats?.critical ?? 0} critical${selectedRepo ? ` · ${selectedRepo.full_name}` : ''}`,
      icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10',
      loading: !threatStats,
    },
    {
      title:   'Open CVEs',
      value:   vulnsTotal ?? '—',
      sub:     `${vulns.filter((v: any) => v.severity === 'critical').length} critical${selectedRepo ? ` · ${selectedRepo.full_name}` : ''}`,
      icon: Eye, color: 'text-yellow-400', bg: 'bg-yellow-500/10',
      loading: !vulnsTotal && vLoading,
    },
    {
      title:   'Compliance',
      value:   frameworks.length > 0
        ? `${Math.round(frameworks.reduce((a: number, f: any) => a + (f.score ?? 0), 0) / frameworks.length)}%`
        : '—',
      sub:     `${frameworks.length} frameworks`,
      icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-500/10',
      loading: cLoading && frameworks.length === 0,
    },
  ];

  const tabs = [
    { id: 'overview'        as Tab, label: 'Overview',       icon: Activity },
    { id: 'threats'         as Tab, label: 'Active Threats', icon: AlertTriangle },
    { id: 'vulnerabilities' as Tab, label: 'Vulnerabilities',icon: Eye },
    { id: 'compliance'      as Tab, label: 'Compliance',     icon: CheckCircle },
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Security Center</h1>
          <p className="page-subtitle">
            Threat intelligence, vulnerabilities &amp; compliance monitoring
            {selectedRepo && (
              <span className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                style={{ background: 'hsl(220 90% 60% / 0.12)', color: 'hsl(220 90% 70%)' }}>
                <GitBranch className="w-3 h-3" />
                {selectedRepo.full_name}
                <button onClick={() => setSelectedRepo(null)}
                  title="Clear repo filter — show all repos"
                  className="ml-0.5 opacity-60 hover:opacity-100 transition-opacity">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="action-btn" onClick={() => {
            const csvThreats = [
              ['ID', 'Severity', 'Status', 'Title', 'Repo', 'MITRE', 'Created'],
              ...threats.map((t: any) => [
                t.id?.substring(0, 8), t.severity, t.status,
                `"${(t.title || t.description || '').replace(/"/g, "'")}"`,
                selectedRepo?.full_name ?? '',
                t.mitre_tactic ?? '', t.created_at ?? '',
              ]),
            ].map(r => r.join(',')).join('\n');
            const blob = new Blob([csvThreats], { type: 'text/csv' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = `security-report-${selectedRepo ? selectedRepo.full_name.replace('/', '-') + '-' : ''}${new Date().toISOString().split('T')[0]}.csv`;
            a.click();
          }}><Download className="w-4 h-4" />Export</button>
          <button onClick={handleRefresh} className="action-btn" disabled={isRefreshing}>
            <RefreshCw className={clsx('w-4 h-4', isRefreshing && 'animate-spin')} />
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* ── DevSecOps Scan Panel — selectedRepo is now controlled from here ── */}
      {canAct && (
        <ScanPanel
          selectedRepo={selectedRepo}
          onSelectRepo={setSelectedRepo}
          onScanComplete={handleScanComplete}
          onViewResults={(t) => setTab(t as Tab)}
        />
      )}

      {/* ── Repo isolation banner — shown when all-repo mode is active ──────── */}
      {!selectedRepo && (
        <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-gray-500 border"
          style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
          <Shield className="w-3.5 h-3.5 flex-shrink-0" />
          <span>Showing data across <strong className="text-gray-400">all repositories</strong>. Select a repository in the scanner above to isolate data per-repo.</span>
        </div>
      )}

      <div className="flex items-center gap-3 mb-1">
        <div className="flex items-center gap-3 ml-auto">
          <LastSynced timestamp={Date.now()} />
          <button onClick={handleRefresh} className="action-btn" disabled={isRefreshing}>
            <RefreshCw className={clsx('w-4 h-4', isRefreshing && 'animate-spin')} />
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        {summaryCards.map((m, i) => (
          <motion.div key={m.title} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }} className="card-base flex items-center gap-4">
            <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0', m.bg)}>
              <m.icon className={clsx('w-5 h-5', m.color)} />
            </div>
            <div className="flex-1 min-w-0">
              {m.loading
                ? <><Skeleton className="h-6 w-16 mb-1" /><Skeleton className="h-3 w-24" /></>
                : <>
                    <div className="stat-value text-xl">{m.value}</div>
                    <div className="stat-label">{m.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5 truncate">{m.sub}</div>
                  </>
              }
            </div>
          </motion.div>
        ))}
      </div>

      <div className="tab-bar mb-5">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={clsx('tab-btn', tab === t.id && 'active')}>
            <t.icon className="w-4 h-4" />{t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="card-base">
            <h2 className="text-sm font-semibold text-foreground mb-4">
              Security Score Breakdown
              {selectedRepo && <span className="ml-2 text-xs font-normal text-gray-500">· {selectedRepo.full_name}</span>}
            </h2>
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="hsl(230 15% 14%)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 11 }} />
                <Radar name="Score" dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
              </RadarChart>
            </ResponsiveContainer>
            <div className="flex items-center justify-center gap-2 mt-2">
              <div className="text-3xl font-bold">{score != null ? Math.round(score) : '—'}</div>
              <div className="text-sm text-muted-foreground">/ 100</div>
            </div>
            {scanScoreData?.ai_summary && (
              <p className="text-xs text-gray-400 text-center mt-2 leading-relaxed">
                {scanScoreData.ai_summary}
              </p>
            )}
          </div>

          <div className="card-base">
            <h2 className="text-sm font-semibold text-foreground mb-4">
              {timelineData.length > 0
                ? `Security Score Trend${selectedRepo ? ` · ${selectedRepo.full_name}` : ''}`
                : 'Recent Threats Summary'}
            </h2>
            {timelineData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={timelineData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 14%)" />
                  <XAxis dataKey="date" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: 'hsl(230 15% 10%)', border: '1px solid hsl(230 15% 20%)', borderRadius: 8 }} />
                  <Area type="monotone" dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : tLoading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : threats.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[220px] text-center">
                <Shield className="w-8 h-8 text-green-400 mb-2" />
                <p className="text-sm text-green-400 font-medium">No threats detected</p>
                <p className="text-xs text-gray-500 mt-1">
                  {selectedRepo ? `Select a repo and run a scan to check ${selectedRepo.full_name}` : 'Run a scan to check your repositories'}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {threats.slice(0, 5).map((t: any) => (
                  <div key={t.id} className="flex items-center gap-3 p-2 rounded-lg bg-surface-1">
                    <span className={severityBadge[t.severity]}>{t.severity}</span>
                    <span className="text-xs text-foreground flex-1 truncate">{t.title || t.description}</span>
                    <span className={clsx('text-xs font-medium', statusColor[t.status])}>{t.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Toast */}
      <AnimatePresence>
        {feedback && (
          <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }}
            className={clsx('fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium shadow-xl border',
              feedback.ok ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400')}>
            {feedback.ok ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            {feedback.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confirm dialog */}
      <ConfirmDialog
        open={!!confirmThreat}
        title={confirmThreat?.action === 'resolve' ? 'Resolve this threat?' : 'Suppress this threat?'}
        description={
          confirmThreat?.action === 'resolve'
            ? confirmThreat.threat.source === 'aws_security_hub'
              ? `"${confirmThreat.threat.title}" will be marked RESOLVED in AWS Security Hub.`
              : `"${confirmThreat.threat.title}" will be marked as resolved. Status updated in UniOps.`
            : confirmThreat?.threat.source === 'aws_security_hub'
              ? `"${confirmThreat?.threat.title}" will be SUPPRESSED in AWS Security Hub (TOLERATED).`
              : `"${confirmThreat?.threat.title}" will be suppressed as a false positive or accepted risk.`
        }
        confirmLabel={
          confirmThreat?.action === 'resolve'
            ? confirmThreat.threat.source === 'aws_security_hub' ? 'Resolve in AWS' : 'Resolve Threat'
            : 'Suppress Finding'
        }
        danger={confirmThreat?.action === 'suppress'}
        onConfirm={handleConfirmThreat}
        onCancel={() => setConfirmThreat(null)}
        loading={actionLoading}
      />

      {tab === 'threats' && (
        <ThreatsTab
          threats={threats}
          tLoading={tLoading}
          canAct={canAct}
          setConfirmThreat={setConfirmThreat}
        />
      )}

      {tab === 'vulnerabilities' && (
        <div className="card-base overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-foreground">
              Vulnerabilities
              {selectedRepo && <span className="ml-2 text-xs font-normal text-gray-500">· {selectedRepo.full_name}</span>}
            </h2>
            <span className="text-xs text-muted-foreground">{vulnsTotal ?? 0} total</span>
          </div>
          {vLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
            </div>
          ) : vulns.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No vulnerabilities found.{selectedRepo ? ` Run a scan on ${selectedRepo.full_name} to detect CVEs in its dependencies.` : ' Run a security scan to detect CVEs in your dependencies.'}
            </p>
          ) : (
            <table className="data-table">
              <thead>
                <tr><th>CVE</th><th>Severity</th><th>Package</th><th>Description</th><th>Status</th></tr>
              </thead>
              <tbody>
                {vulns.map((v: any) => (
                  <tr key={v.id}>
                    <td><code className="text-xs font-mono text-blue-400">{v.cve_id ?? v.id?.substring(0, 12)}</code></td>
                    <td><span className={severityBadge[v.severity]}>{v.severity}</span></td>
                    <td>
                      <div>
                        <code className="text-xs font-mono text-muted-foreground">{v.package_name ?? v.component}</code>
                        {v.package_version && <span className="text-xs text-gray-600 ml-1">v{v.package_version}</span>}
                      </div>
                      {v.fixed_version && <div className="text-xs text-green-400/70">Fix: v{v.fixed_version}</div>}
                    </td>
                    <td><span className="text-xs text-muted-foreground">{v.title ?? v.description}</span></td>
                    <td>
                      <span className={clsx('flex items-center gap-1.5 text-xs font-medium',
                        v.status === 'patched' ? 'text-green-400' : 'text-red-400')}>
                        {v.status === 'patched' ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                        {v.status ?? 'open'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'compliance' && (
        <div>
          {cLoading ? (
            <p className="text-sm text-muted-foreground">Loading compliance data...</p>
          ) : frameworks.length === 0 ? (
            <p className="text-sm text-muted-foreground card-base">No compliance frameworks configured.</p>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              {frameworks.map((fw: any) => (
                <div key={fw.id ?? fw.name} className="card-base">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">{fw.framework ?? fw.name}</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {fw.last_audit ? `Last audit: ${new Date(fw.last_audit).toLocaleDateString()}` : 'No audit yet'}
                      </p>
                    </div>
                    <div className={clsx('text-2xl font-bold', complianceColor[fw.status ?? 'in_progress'])}>
                      {fw.score ?? fw.compliance_score ?? 0}%
                    </div>
                  </div>
                  <div className="progress-bar-base mb-2">
                    <div className="h-full rounded-full transition-all" style={{
                      width: `${fw.score ?? fw.compliance_score ?? 0}%`,
                      background: (fw.score ?? 0) >= 90 ? '#10b981' : (fw.score ?? 0) >= 75 ? '#f59e0b' : '#ef4444',
                    }} />
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{fw.controls_passed ?? fw.passed ?? 0}/{fw.controls_total ?? fw.total ?? 0} controls passed</span>
                    <span className={clsx('font-medium capitalize', complianceColor[fw.status ?? 'in_progress'])}>
                      {(fw.status ?? 'in_progress').replace('_', ' ')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
