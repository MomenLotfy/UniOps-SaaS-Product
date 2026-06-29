import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { clsx } from 'clsx';
import {
  X, GitBranch, Lock, Unlock, Code2, Shield, Bug, Key, Container,
  AlertTriangle, Clock, CheckCircle, TrendingUp, TrendingDown, Minus,
  Cpu, ExternalLink, Star, GitPullRequest, Tag, Activity,
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar,
} from 'recharts';
import { useApi } from '@/hooks/use-api';
import type { MergedRepo, ScanHistoryEntry, RepoScore } from './types';
import { RISK_STYLES } from './types';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/6', className)} />;
}

const SECTION = 'px-5 py-4 border-b';
const BORDER  = { borderColor: 'hsl(230 15% 14%)' };

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 mb-3">
      {children}
    </p>
  );
}

function ScoreGauge({ score, label }: { score: number; label: string }) {
  const color =
    score >= 80 ? '#22c55e' : score >= 60 ? '#eab308' : score >= 40 ? '#f97316' : '#ef4444';
  const pct = Math.min(100, score);
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-14 h-14">
        <svg viewBox="0 0 56 56" className="w-full h-full -rotate-90">
          <circle cx="28" cy="28" r="22" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
          <circle cx="28" cy="28" r="22" fill="none" stroke={color} strokeWidth="6"
            strokeDasharray={2 * Math.PI * 22}
            strokeDashoffset={2 * Math.PI * 22 * (1 - pct / 100)}
            strokeLinecap="round" />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center"
          style={{ color, fontSize: 13, fontWeight: 700 }}>
          {Math.round(score)}
        </span>
      </div>
      <span className="text-[10px] text-muted-foreground text-center leading-tight">{label}</span>
    </div>
  );
}

function StatRow({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b last:border-0" style={BORDER}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={clsx('text-xs font-semibold', color ?? 'text-foreground')}>{value}</span>
    </div>
  );
}

function FindingBar({ label, count, max, color }: { label: string; count: number; max: number; color: string }) {
  const pct = max > 0 ? (count / max) * 100 : 0;
  return (
    <div className="flex items-center gap-2 mb-2">
      <span className={clsx('text-[10px] font-medium w-14 text-right capitalize', color)}>{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-white/6 overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all', color.replace('text-', 'bg-'))} style={{ width: `${pct}%` }} />
      </div>
      <span className={clsx('text-[10px] font-mono font-bold w-6 text-right', color)}>{count}</span>
    </div>
  );
}

interface RepoDrawerProps {
  repo: MergedRepo | null;
  onClose: () => void;
}

export default function RepoDrawer({ repo, onClose }: RepoDrawerProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Per-repo scan history
  const { data: histRaw, loading: histLoading } = useApi<any>(
    repo ? `/security/scan-history?repo_id=${repo.id}&limit=20` : null,
    [repo?.id],
  );
  // Per-repo security score (with AI summary)
  const { data: scoreRaw, loading: scoreLoading } = useApi<any>(
    repo ? `/security/score?repo_id=${repo.id}` : null,
    [repo?.id],
  );

  const history: ScanHistoryEntry[] = Array.isArray(histRaw) ? histRaw : (histRaw?.data ?? histRaw?.history ?? []);
  const scoreData: RepoScore | null = scoreRaw?.data ?? scoreRaw;

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const risk  = repo?.risk;
  const rl    = risk?.risk_level ?? 'low';
  const rs    = RISK_STYLES[rl as keyof typeof RISK_STYLES] ?? RISK_STYLES.low;
  const score = risk?.security_score ?? repo?.last_scan_score;

  const maxFindings = Math.max(
    risk?.critical_count ?? 0,
    risk?.high_count ?? 0,
    Math.max(0, (risk?.open_findings ?? 0) - (risk?.critical_count ?? 0) - (risk?.high_count ?? 0)),
    1,
  );

  const radarData = scoreData?.breakdown ? [
    { s: 'SAST',      v: scoreData.breakdown.sast      ?? 0 },
    { s: 'Deps',      v: scoreData.breakdown.deps      ?? 0 },
    { s: 'Secrets',   v: scoreData.breakdown.secrets   ?? 0 },
    { s: 'Container', v: scoreData.breakdown.container ?? 0 },
    { s: 'CI/CD',     v: scoreData.breakdown.cicd      ?? 0 },
  ] : [];

  const chartData = history.map(h => ({
    date:     new Date(h.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    score:    h.score,
    critical: h.critical,
    high:     h.high,
  })).reverse();

  return (
    <AnimatePresence>
      {repo && (
        <>
          {/* Backdrop */}
          <motion.div
            ref={overlayRef}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/60"
            onClick={onClose}
          />

          {/* Drawer panel */}
          <motion.div
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 z-50 flex flex-col shadow-2xl overflow-hidden"
            style={{ width: 480, background: 'hsl(230 15% 7%)', borderLeft: '1px solid hsl(230 15% 14%)' }}
          >
            {/* ── Header ────────────────────────────────────────────── */}
            <div className="flex items-start justify-between px-5 py-4 border-b flex-shrink-0" style={BORDER}>
              <div className="flex items-start gap-3 min-w-0">
                {/* Risk stripe */}
                <div className={clsx('w-1 self-stretch rounded-full flex-shrink-0 mt-0.5', rs.dot)} />
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-sm font-bold text-foreground truncate">{repo.full_name}</h2>
                    <span className={clsx(
                      'text-[9px] px-2 py-0.5 rounded-full font-bold border uppercase tracking-wider',
                      rs.bg, rs.text, rs.border,
                    )}>
                      {rl}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground mt-0.5 flex-wrap">
                    <span className="capitalize">{repo.provider}</span>
                    <span className="opacity-30">·</span>
                    {repo.is_private
                      ? <><Lock className="w-2.5 h-2.5" /> Private</>
                      : <><Unlock className="w-2.5 h-2.5" /> Public</>}
                    <span className="opacity-30">·</span>
                    <GitBranch className="w-2.5 h-2.5" />
                    <span>{repo.default_branch}</span>
                    {repo.language && (
                      <>
                        <span className="opacity-30">·</span>
                        <Code2 className="w-2.5 h-2.5" />
                        <span>{repo.language}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <button onClick={onClose}
                className="text-muted-foreground hover:text-foreground transition-colors flex-shrink-0 mt-0.5">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* ── Scrollable body ───────────────────────────────────── */}
            <div className="flex-1 overflow-y-auto">

              {/* Security overview gauges */}
              <div className={clsx(SECTION, 'flex items-center justify-around gap-4')} style={BORDER}>
                {score != null
                  ? <ScoreGauge score={score} label="Health Score" />
                  : <div className="w-14 h-14 rounded-full border border-dashed border-white/15 flex items-center justify-center">
                      <span className="text-[9px] text-muted-foreground">N/A</span>
                    </div>
                }
                {risk?.risk_score != null && (
                  <ScoreGauge score={100 - risk.risk_score} label="Risk Score" />
                )}
                {scoreLoading && !scoreData && (
                  <div className="flex gap-6">
                    <Skeleton className="w-14 h-14 rounded-full" />
                    <Skeleton className="w-14 h-14 rounded-full" />
                  </div>
                )}
                {/* Breakdown radar */}
                {radarData.length > 0 && (
                  <div className="w-28 h-28">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
                        <PolarGrid stroke="hsl(230 15% 18%)" />
                        <PolarAngleAxis dataKey="s" tick={{ fill: 'hsl(215 16% 45%)', fontSize: 8 }} />
                        <Radar dataKey="v" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={1.5} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>

              {/* AI Summary */}
              {(scoreLoading || scoreData?.ai_summary) && (
                <div className={clsx(SECTION)} style={BORDER}>
                  <SectionLabel>AI Security Summary</SectionLabel>
                  {scoreLoading && !scoreData ? (
                    <div className="space-y-1.5">
                      <Skeleton className="h-3 w-full" />
                      <Skeleton className="h-3 w-5/6" />
                      <Skeleton className="h-3 w-4/5" />
                    </div>
                  ) : scoreData?.ai_summary ? (
                    <p className="text-xs text-muted-foreground leading-relaxed">{scoreData.ai_summary}</p>
                  ) : null}
                  {scoreData?.ai_suggestions && scoreData.ai_suggestions.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {scoreData.ai_suggestions.map((s, i) => (
                        <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                          <span className="text-blue-400 mt-0.5 flex-shrink-0">•</span>
                          {s}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* Repository Details */}
              <div className={clsx(SECTION)} style={BORDER}>
                <SectionLabel>Repository Details</SectionLabel>
                <StatRow label="Full Name"     value={repo.full_name} />
                <StatRow label="Provider"      value={repo.provider} />
                <StatRow label="Visibility"    value={repo.is_private ? 'Private' : 'Public'} />
                <StatRow label="Branch"        value={repo.default_branch} />
                {repo.language && <StatRow label="Language"     value={repo.language} />}
                {risk?.owner && <StatRow label="Owner"         value={risk.owner} />}
                <StatRow label="Dockerfile"    value={repo.has_dockerfile ? 'Yes' : 'No'}
                  color={repo.has_dockerfile ? 'text-blue-400' : 'text-muted-foreground'} />
                <StatRow label="CI/CD Config"  value={repo.has_cicd ? 'Yes' : 'No'}
                  color={repo.has_cicd ? 'text-green-400' : 'text-muted-foreground'} />
              </div>

              {/* Security findings breakdown */}
              {risk && (
                <div className={clsx(SECTION)} style={BORDER}>
                  <SectionLabel>Security Findings</SectionLabel>
                  <FindingBar label="Critical" count={risk.critical_count}  max={maxFindings} color="text-red-400" />
                  <FindingBar label="High"     count={risk.high_count}      max={maxFindings} color="text-orange-400" />
                  <FindingBar
                    label="Med/Low"
                    count={Math.max(0, risk.open_findings - risk.critical_count - risk.high_count)}
                    max={maxFindings}
                    color="text-yellow-400"
                  />
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <div className="p-2 rounded-lg text-center" style={{ background: 'hsl(230 15% 11%)' }}>
                      <Key className="w-3.5 h-3.5 text-yellow-400 mx-auto mb-1" />
                      <p className="text-sm font-bold text-yellow-400">{risk.secret_count}</p>
                      <p className="text-[9px] text-muted-foreground">Secrets</p>
                    </div>
                    <div className="p-2 rounded-lg text-center" style={{ background: 'hsl(230 15% 11%)' }}>
                      <Container className="w-3.5 h-3.5 text-blue-400 mx-auto mb-1" />
                      <p className="text-sm font-bold text-blue-400">{risk.container_count}</p>
                      <p className="text-[9px] text-muted-foreground">Container</p>
                    </div>
                    <div className="p-2 rounded-lg text-center" style={{ background: 'hsl(230 15% 11%)' }}>
                      <AlertTriangle className="w-3.5 h-3.5 text-purple-400 mx-auto mb-1" />
                      <p className="text-sm font-bold text-purple-400">{risk.compliance_violations}</p>
                      <p className="text-[9px] text-muted-foreground">Violations</p>
                    </div>
                  </div>
                  <div className="mt-3 space-y-0">
                    <StatRow
                      label="Total Open Findings"
                      value={risk.open_findings}
                      color={risk.open_findings > 0 ? 'text-orange-400' : 'text-green-400'}
                    />
                    <StatRow label="Exposure Risk"  value={`${risk.exposure_risk.toFixed(1)}/100`}
                      color={risk.exposure_risk > 60 ? 'text-red-400' : risk.exposure_risk > 30 ? 'text-yellow-400' : 'text-green-400'} />
                    <StatRow label="Risk Score"     value={`${Math.round(risk.risk_score)}/100`}
                      color={risk.risk_score > 60 ? 'text-red-400' : risk.risk_score > 30 ? 'text-yellow-400' : 'text-green-400'} />
                    <StatRow label="Trend"          value={risk.trend}
                      color={risk.trend === 'improving' ? 'text-green-400' : risk.trend === 'worsening' ? 'text-red-400' : 'text-muted-foreground'} />
                    {risk.previous_risk_score != null && (
                      <StatRow label="Previous Score" value={`${Math.round(risk.previous_risk_score)}/100`} />
                    )}
                  </div>
                </div>
              )}

              {/* Scanner details (factors) */}
              {risk?.factors && Object.keys(risk.factors).length > 0 && (
                <div className={clsx(SECTION)} style={BORDER}>
                  <SectionLabel>Scanner Details</SectionLabel>
                  <div className="space-y-0">
                    {Object.entries(risk.factors).map(([scanner, detail]) => (
                      <div key={scanner} className="flex items-center justify-between py-1.5 border-b last:border-0" style={BORDER}>
                        <span className="text-xs text-muted-foreground capitalize">{scanner}</span>
                        <span className="text-xs font-medium text-foreground">
                          {typeof detail === 'object' && detail !== null
                            ? JSON.stringify(detail)
                            : String(detail)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Scan History Chart */}
              <div className={clsx(SECTION)} style={BORDER}>
                <SectionLabel>Scan History</SectionLabel>
                {histLoading ? (
                  <Skeleton className="h-28 w-full rounded-lg" />
                ) : chartData.length > 1 ? (
                  <ResponsiveContainer width="100%" height={110}>
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 16%)" />
                      <XAxis dataKey="date" tick={{ fill: 'hsl(215 16% 45%)', fontSize: 9 }} />
                      <YAxis domain={[0, 100]} tick={{ fill: 'hsl(215 16% 45%)', fontSize: 9 }} />
                      <Tooltip
                        contentStyle={{ background: 'hsl(230 15% 10%)', border: '1px solid hsl(230 15% 18%)', borderRadius: 8, fontSize: 11 }}
                        formatter={(v: any, name: string) => [v, name === 'score' ? 'Score' : name]}
                      />
                      <Area type="monotone" dataKey="score"    stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={1.5} />
                      <Area type="monotone" dataKey="critical" stroke="#ef4444" fill="#ef4444" fillOpacity={0.06} strokeWidth={1} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="py-6 text-center rounded-lg" style={{ background: 'hsl(230 15% 9%)' }}>
                    <Activity className="w-5 h-5 text-muted-foreground mx-auto mb-1 opacity-40" />
                    <p className="text-xs text-muted-foreground">No scan history yet</p>
                    <p className="text-[10px] text-muted-foreground/50 mt-0.5">Run a scan to see history</p>
                  </div>
                )}

                {/* Recent scan entries */}
                {history.length > 0 && (
                  <div className="mt-3 space-y-1.5">
                    {history.slice(0, 5).map((h, i) => (
                      <div key={i} className="flex items-center justify-between text-[10px] py-1.5 border-b last:border-0" style={BORDER}>
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Clock className="w-3 h-3" />
                          <span>{new Date(h.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' })}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={clsx('font-bold',
                            h.score >= 80 ? 'text-green-400' : h.score >= 60 ? 'text-yellow-400' : 'text-red-400'
                          )}>
                            {Math.round(h.score)}
                          </span>
                          {h.critical > 0 && <span className="text-red-400">{h.critical}C</span>}
                          {h.high > 0    && <span className="text-orange-400">{h.high}H</span>}
                          {h.secrets > 0 && <span className="text-yellow-400">{h.secrets}S</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Last scan info */}
              {(repo.last_scan_at || risk?.last_scan_at) && (
                <div className={clsx(SECTION)} style={BORDER}>
                  <SectionLabel>Last Scan</SectionLabel>
                  <StatRow label="Scanned at"
                    value={new Date(repo.last_scan_at ?? risk?.last_scan_at ?? '').toLocaleString()} />
                  {repo.last_scan_score != null && (
                    <StatRow label="Score" value={`${Math.round(repo.last_scan_score)}/100`}
                      color={repo.last_scan_score >= 80 ? 'text-green-400' : repo.last_scan_score >= 60 ? 'text-yellow-400' : 'text-red-400'} />
                  )}
                  {scoreData?.scan_id && (
                    <StatRow label="Scan ID" value={scoreData.scan_id.slice(0, 8) + '…'} />
                  )}
                </div>
              )}

              {/* Integrations / capabilities */}
              <div className={clsx(SECTION)} style={BORDER}>
                <SectionLabel>Capabilities</SectionLabel>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: 'Docker',      active: repo.has_dockerfile, color: 'text-blue-400'  },
                    { label: 'CI/CD',       active: repo.has_cicd,       color: 'text-green-400' },
                    { label: 'Risk Scored', active: !!risk,              color: 'text-purple-400' },
                    { label: 'AI Summary',  active: !!scoreData?.ai_summary, color: 'text-cyan-400' },
                  ].map(({ label, active, color }) => (
                    <div key={label} className="flex items-center gap-2 text-xs py-1.5">
                      {active
                        ? <CheckCircle className={clsx('w-3.5 h-3.5', color)} />
                        : <div className="w-3.5 h-3.5 rounded-full border border-white/15" />}
                      <span className={active ? 'text-foreground' : 'text-muted-foreground/50'}>{label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* No risk data state */}
              {!risk && !histLoading && history.length === 0 && (
                <div className={clsx(SECTION, 'text-center')} style={BORDER}>
                  <Shield className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-30" />
                  <p className="text-sm font-medium text-muted-foreground">No security data yet</p>
                  <p className="text-xs text-muted-foreground/60 mt-1">
                    Run a scan to generate security findings and risk scores.
                  </p>
                </div>
              )}

              <div className="h-8" />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
