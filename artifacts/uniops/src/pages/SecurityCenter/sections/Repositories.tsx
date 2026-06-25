import { useState, useRef, useEffect } from 'react';
import {
  GitBranch, Play, RefreshCw, ChevronDown, Loader2, CheckCircle, XCircle,
  Filter, TrendingUp, TrendingDown, Minus, Shield, AlertTriangle, Users,
  Bug, Key, Container, ClipboardList, Info,
} from 'lucide-react';
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

const RISK_STYLES: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  critical: { bg: 'bg-red-500/15',    text: 'text-red-400',    border: 'border-red-500/30',    dot: 'bg-red-400' },
  high:     { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', dot: 'bg-orange-400' },
  medium:   { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30', dot: 'bg-yellow-400' },
  low:      { bg: 'bg-green-500/15',  text: 'text-green-400',  border: 'border-green-500/30',  dot: 'bg-green-400' },
};

const RISK_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function RiskBadge({ level }: { level: string }) {
  const s = RISK_STYLES[level] ?? RISK_STYLES.low;
  return (
    <span className={clsx('flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold border uppercase tracking-wide', s.bg, s.text, s.border)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', s.dot)} />
      {level}
    </span>
  );
}

function TrendIcon({ trend }: { trend?: string }) {
  if (!trend || trend === 'stable') return <Minus className="w-3.5 h-3.5 text-muted-foreground" />;
  if (trend === 'worsening')  return <TrendingUp   className="w-3.5 h-3.5 text-red-400" />;
  if (trend === 'improving')  return <TrendingDown  className="w-3.5 h-3.5 text-green-400" />;
  return null;
}

function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const pct = Math.min(100, (score / max) * 100);
  const color = score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : score >= 40 ? 'bg-orange-500' : 'bg-red-500';
  return (
    <div className="w-16 h-1.5 rounded-full bg-white/10 overflow-hidden">
      <div className={clsx('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

function FactorPill({ icon: Icon, label, count, color }: { icon: any; label: string; count: number; color: string }) {
  if (!count) return null;
  return (
    <span className={clsx('flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded border font-mono', color)}>
      <Icon className="w-2.5 h-2.5" />
      {count} {label}
    </span>
  );
}

export default function Repositories() {
  const { role } = usePermissions();
  const canScan = canWriteSecurity(role);

  const { data: reposRaw,  loading: reposLoading,  refetch: refetchRepos } = useApi<any>('/security/repos');
  const { data: riskRaw,   loading: riskLoading,   refetch: refetchRisk  } = useApi<any>('/repos/risk');

  const repos    = Array.isArray(reposRaw) ? reposRaw : (reposRaw?.data ?? []);
  const riskList = Array.isArray(riskRaw?.data) ? riskRaw.data : (Array.isArray(riskRaw) ? riskRaw : []);

  // Build risk map: repo_id → risk record
  const riskMap = new Map<string, any>(riskList.map((r: any) => [r.repo_id, r]));

  const [selectedRepo, setSelectedRepo] = useState<any>(null);
  const [branch, setBranch]             = useState('');
  const [repoOpen, setRepoOpen]         = useState(false);
  const [scanning, setScanning]         = useState(false);
  const [syncing, setSyncing]           = useState(false);
  const [activeScan, setActiveScan]     = useState<any>(null);
  const [scanError, setScanError]       = useState<string | null>(null);
  const [providerFilter, setProviderFilter] = useState('');
  const [riskFilter, setRiskFilter]         = useState('');
  const [expandedRepo, setExpandedRepo]     = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Merged + sorted repos
  const merged = repos
    .map((r: any) => ({ ...r, risk: riskMap.get(r.id) }))
    .filter((r: any) => {
      if (providerFilter && r.provider !== providerFilter) return false;
      if (riskFilter && (r.risk?.risk_level ?? 'unscanned') !== riskFilter) return false;
      return true;
    })
    .sort((a: any, b: any) => {
      const ra = RISK_ORDER[a.risk?.risk_level ?? 'low'] ?? 3;
      const rb = RISK_ORDER[b.risk?.risk_level ?? 'low'] ?? 3;
      if (ra !== rb) return ra - rb;
      return (b.risk?.risk_score ?? 0) - (a.risk?.risk_score ?? 0);
    });

  useEffect(() => {
    if (!activeScan?.id || ['completed', 'failed'].includes(activeScan?.status)) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      if (activeScan?.status === 'completed') { refetchRepos(); refetchRisk(); }
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
    try { await apiPost('/security/repos/sync', {}); await refetchRepos(); }
    catch (e: any) { setScanError(e?.message ?? 'Sync failed'); }
    finally { setSyncing(false); }
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

  // Summary stats
  const riskCounts = { critical: 0, high: 0, medium: 0, low: 0, unscanned: 0 };
  for (const r of merged) {
    const lvl = r.risk?.risk_level;
    if (lvl && riskCounts[lvl as keyof typeof riskCounts] !== undefined) {
      (riskCounts as any)[lvl]++;
    } else {
      riskCounts.unscanned++;
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Repositories</h1>
          <p className="text-xs text-muted-foreground">
            {merged.length} repositories · sorted by risk
          </p>
        </div>
        <button onClick={handleSync} disabled={syncing || reposLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
          style={{ borderColor: 'hsl(230 15% 20%)' }}>
          <RefreshCw className={clsx('w-3.5 h-3.5', syncing && 'animate-spin')} />
          {syncing ? 'Syncing…' : 'Sync Repos'}
        </button>
      </div>

      {/* Risk summary bar */}
      <div className="grid grid-cols-4 gap-2">
        {(['critical', 'high', 'medium', 'low'] as const).map(level => {
          const s = RISK_STYLES[level];
          return (
            <button
              key={level}
              onClick={() => setRiskFilter(riskFilter === level ? '' : level)}
              className={clsx(
                'card-base px-3 py-2.5 text-center transition-all border',
                riskFilter === level ? `${s.bg} ${s.border}` : 'border-transparent hover:border-white/10'
              )}
            >
              <p className={clsx('text-xl font-bold', s.text)}>{riskCounts[level]}</p>
              <p className="text-[10px] text-muted-foreground capitalize">{level} risk</p>
            </button>
          );
        })}
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
                        : repos.map((r: any) => {
                          const risk = riskMap.get(r.id);
                          return (
                            <button key={r.id}
                              onClick={() => { setSelectedRepo(r); setBranch(r.default_branch ?? 'main'); setRepoOpen(false); }}
                              className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-white/5 transition-colors">
                              <GitBranch className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                              <span className="flex-1 truncate text-white">{r.full_name}</span>
                              {risk && <RiskBadge level={risk.risk_level} />}
                              {!risk && r.last_scan_score != null && (
                                <span className={clsx('font-mono text-xs', r.last_scan_score >= 80 ? 'text-green-400' : r.last_scan_score >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                                  {r.last_scan_score}
                                </span>
                              )}
                            </button>
                          );
                        })}
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

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="w-3.5 h-3.5 text-muted-foreground" />
        {['', 'github', 'gitlab'].map(p => (
          <button key={p} onClick={() => setProviderFilter(p)}
            className={clsx('px-2.5 py-1 rounded text-xs capitalize transition-colors',
              providerFilter === p ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {p || 'All Providers'}
          </button>
        ))}
        {riskFilter && (
          <>
            <div className="w-px h-4 bg-border" />
            <button onClick={() => setRiskFilter('')}
              className="px-2.5 py-1 rounded text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
              <XCircle className="w-3 h-3" /> Clear risk filter
            </button>
          </>
        )}
      </div>

      {/* Repository list — sorted by risk */}
      <div className="space-y-2">
        {(reposLoading || riskLoading) ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)
        ) : merged.length === 0 ? (
          <div className="card-base py-10 text-center">
            <GitBranch className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No repositories. Click Sync Repos to connect GitHub or GitLab.</p>
          </div>
        ) : merged.map((r: any) => {
          const risk = r.risk;
          const isExpanded = expandedRepo === r.id;
          const riskStyle = RISK_STYLES[risk?.risk_level ?? 'low'];

          return (
            <div key={r.id} className={clsx('card-base overflow-hidden transition-all',
              risk?.risk_level === 'critical' && 'border-red-500/20',
              risk?.risk_level === 'high'     && 'border-orange-500/15',
            )}>
              <button
                className="w-full text-left p-4 flex items-center gap-4"
                onClick={() => setExpandedRepo(isExpanded ? null : r.id)}
              >
                {/* Risk indicator stripe */}
                <div className={clsx('w-1 self-stretch rounded-full flex-shrink-0', riskStyle?.dot ?? 'bg-gray-600')} />

                {/* Repo icon */}
                <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
                  <GitBranch className="w-4 h-4 text-muted-foreground" />
                </div>

                {/* Repo info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <p className="text-sm font-medium text-foreground truncate">{r.full_name}</p>
                    {risk ? <RiskBadge level={risk.risk_level} /> : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground border border-white/10">
                        Not rated
                      </span>
                    )}
                    {risk && (
                      <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground" title={`Trend: ${risk.trend}`}>
                        <TrendIcon trend={risk.trend} />
                        <span className="capitalize">{risk.trend}</span>
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-wrap text-[10px] text-muted-foreground">
                    <span className="capitalize">{r.provider}</span>
                    <span>·</span>
                    <span>{r.default_branch ?? 'main'}</span>
                    {r.language && <><span>·</span><span>{r.language}</span></>}
                    {r.is_private && <span className="px-1 py-0.5 rounded bg-white/5 border border-white/10">private</span>}
                    {risk?.owner && (
                      <><span>·</span>
                      <span className="flex items-center gap-0.5"><Users className="w-2.5 h-2.5" /> {risk.owner}</span></>
                    )}
                  </div>
                </div>

                {/* Stats column */}
                <div className="flex flex-col items-end gap-1 flex-shrink-0 min-w-[80px]">
                  {/* Security score */}
                  {(risk?.security_score ?? r.last_scan_score) != null && (
                    <div className="flex items-center gap-2">
                      <ScoreBar score={risk?.security_score ?? r.last_scan_score} />
                      <span className={clsx('text-sm font-bold',
                        (risk?.security_score ?? r.last_scan_score) >= 80 ? 'text-green-400'
                        : (risk?.security_score ?? r.last_scan_score) >= 60 ? 'text-yellow-400'
                        : 'text-red-400'
                      )}>
                        {Math.round(risk?.security_score ?? r.last_scan_score)}
                      </span>
                    </div>
                  )}
                  {/* Open findings */}
                  {risk?.open_findings > 0 && (
                    <span className="text-[10px] text-muted-foreground">
                      <span className="text-orange-400 font-medium">{risk.open_findings}</span> open findings
                    </span>
                  )}
                  {!(risk?.security_score ?? r.last_scan_score) && (
                    <p className="text-xs text-muted-foreground">Not scanned</p>
                  )}
                </div>
              </button>

              {/* Expanded: factor breakdown */}
              <AnimatePresence>
                {isExpanded && risk && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className="overflow-hidden"
                  >
                    <div className="px-4 pb-4 border-t flex flex-col gap-3" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                      {/* Factor pills */}
                      <div className="pt-3 flex flex-wrap gap-1.5">
                        <FactorPill icon={AlertTriangle} label="critical" count={risk.critical_count} color="bg-red-500/10 text-red-400 border-red-500/20" />
                        <FactorPill icon={AlertTriangle} label="high"     count={risk.high_count}     color="bg-orange-500/10 text-orange-400 border-orange-500/20" />
                        <FactorPill icon={Key}          label="secrets"   count={risk.secret_count}   color="bg-yellow-500/10 text-yellow-400 border-yellow-500/20" />
                        <FactorPill icon={Bug}          label="container" count={risk.container_count} color="bg-blue-500/10 text-blue-400 border-blue-500/20" />
                        <FactorPill icon={ClipboardList} label="violations" count={risk.compliance_violations} color="bg-purple-500/10 text-purple-400 border-purple-500/20" />
                        {risk.exposure_risk > 0 && (
                          <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded border font-mono bg-white/5 text-muted-foreground border-white/10">
                            <Shield className="w-2.5 h-2.5" />
                            {risk.exposure_risk} exposure
                          </span>
                        )}
                      </div>

                      {/* Score progression */}
                      <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
                        <span>Risk score: <span className={clsx('font-bold', riskStyle.text)}>{risk.risk_score}</span>/100</span>
                        {risk.previous_risk_score != null && (
                          <span>
                            Previous: <span className="text-foreground font-medium">{risk.previous_risk_score}</span>
                            {' '}
                            <span className={clsx(
                              risk.trend === 'improving' ? 'text-green-400' : risk.trend === 'worsening' ? 'text-red-400' : 'text-muted-foreground'
                            )}>
                              ({risk.trend === 'improving' ? '↓' : risk.trend === 'worsening' ? '↑' : '→'})
                            </span>
                          </span>
                        )}
                        {risk.last_scan_at && (
                          <span>Last scanned: {new Date(risk.last_scan_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}
