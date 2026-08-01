import { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { clsx } from 'clsx';
import {
  X, GitBranch, Lock, Unlock, Code2, Shield, Bug, Key, Container,
  AlertTriangle, Clock, CheckCircle, TrendingUp, TrendingDown, Minus,
  ExternalLink, Tag, Activity, Info, Sparkles, Wrench,
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

const BORDER  = { borderColor: 'hsl(230 15% 14%)' };
const SUBTLE  = { background: 'hsl(230 15% 9%)' };

const SCANNER_LABELS: Record<string, { label: string; source: string }> = {
  sast:      { label: 'SAST (Code)',     source: 'Semgrep' },
  deps:      { label: 'Dependencies',    source: 'OWASP DC / pip-audit / npm audit' },
  secrets:   { label: 'Secrets',         source: 'Gitleaks' },
  container: { label: 'Container',       source: 'Trivy' },
  cicd:      { label: 'CI/CD Config',    source: 'Built-in' },
};

function SectionLabel({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
        {children}
      </p>
      {hint && <span className="text-[9px] text-muted-foreground/50">{hint}</span>}
    </div>
  );
}

function ScoreGauge({ score, label, sub }: { score: number; label: string; sub?: string }) {
  const color =
    score >= 80 ? '#22c55e' : score >= 60 ? '#eab308' : score >= 40 ? '#f97316' : '#ef4444';
  const pct = Math.min(100, score);
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative w-16 h-16">
        <svg viewBox="0 0 64 64" className="w-full h-full -rotate-90">
          <circle cx="32" cy="32" r="26" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
          <circle cx="32" cy="32" r="26" fill="none" stroke={color} strokeWidth="6"
            strokeDasharray={2 * Math.PI * 26}
            strokeDashoffset={2 * Math.PI * 26 * (1 - pct / 100)}
            strokeLinecap="round" />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center"
          style={{ color, fontSize: 16, fontWeight: 700 }}>
          {Math.round(score)}
        </span>
      </div>
      <span className="text-[10px] text-muted-foreground text-center leading-tight">{label}</span>
      {sub && <span className="text-[9px] text-muted-foreground/50 text-center">{sub}</span>}
    </div>
  );
}

function StatRow({ label, value, color, hint }: { label: string; value: string | number; color?: string; hint?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0" style={BORDER}>
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground">{label}</span>
        {hint && (
          <span title={hint} className="cursor-help">
            <Info className="w-2.5 h-2.5 text-muted-foreground/40" />
          </span>
        )}
      </div>
      <span className={clsx('text-xs font-semibold', color ?? 'text-foreground')}>{value}</span>
    </div>
  );
}

function FindingBar({ label, count, max, color }: { label: string; count: number; max: number; color: string }) {
  const pct = max > 0 ? (count / max) * 100 : 0;
  return (
    <div className="flex items-center gap-2 mb-2">
      <span className={clsx('text-[10px] font-medium w-16 text-right capitalize', color)}>{label}</span>
      <div className="flex-1 h-2 rounded-full bg-white/6 overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all', color.replace('text-', 'bg-'))} style={{ width: `${pct}%` }} />
      </div>
      <span className={clsx('text-[11px] font-mono font-bold w-8 text-right', color)}>{count}</span>
    </div>
  );
}

// ── Explainable factors table ─────────────────────────────────────────────────
type FactorRow = {
  scanner: keyof typeof SCANNER_LABELS | string;
  label: string;
  source: string;
  count: number;
  penalty: number;
  maxPenalty: number;
  contribution: number;  // 0..1
};

function FactorsTable({ factors, riskScore }: { factors: Record<string, any> | null | undefined; riskScore: number }) {
  if (!factors || Object.keys(factors).length === 0) {
    return (
      <div className="rounded-lg p-4 text-center" style={SUBTLE}>
        <p className="text-xs text-muted-foreground">No scanner factors available yet.</p>
        <p className="text-[10px] text-muted-foreground/50 mt-1">
          Run a scan to compute per-scanner penalties.
        </p>
      </div>
    );
  }

  // Normalise shape: backend may return either {scanner: {count, penalty, max}} or {scanner: N}
  const rows: FactorRow[] = Object.entries(factors).map(([key, val]) => {
    const meta = SCANNER_LABELS[key] ?? { label: key, source: 'Unknown' };
    if (typeof val === 'number') {
      return {
        scanner: key,
        label: meta.label,
        source: meta.source,
        count: val,
        penalty: val,
        maxPenalty: val || 1,
        contribution: 0,
      };
    }
    const count    = Number(val?.count ?? val?.findings ?? val?.value ?? 0);
    const penalty  = Number(val?.penalty ?? val?.weighted ?? val?.score ?? 0);
    const max      = Number(val?.max ?? val?.cap ?? val?.max_penalty ?? Math.max(penalty, 1));
    return {
      scanner: key,
      label: meta.label,
      source: meta.source,
      count,
      penalty,
      maxPenalty: max,
      contribution: 0,
    };
  });

  const totalPenalty = rows.reduce((s, r) => s + r.penalty, 0);
  rows.forEach(r => {
    r.contribution = totalPenalty > 0 ? r.penalty / totalPenalty : 0;
  });

  return (
    <div className="rounded-lg overflow-hidden" style={SUBTLE}>
      {/* Table header */}
      <div className="grid grid-cols-12 gap-1 px-3 py-2 text-[9px] font-bold uppercase tracking-wider text-muted-foreground/60 border-b" style={BORDER}>
        <div className="col-span-3">Scanner</div>
        <div className="col-span-1 text-right">Count</div>
        <div className="col-span-2 text-right">Penalty</div>
        <div className="col-span-2 text-right">Max</div>
        <div className="col-span-4">Contribution</div>
      </div>
      {rows.map((r, i) => {
        const pct = Math.round(r.contribution * 100);
        return (
          <div key={i} className="grid grid-cols-12 gap-1 px-3 py-2 items-center text-xs border-b last:border-0" style={BORDER}>
            <div className="col-span-3 min-w-0">
              <p className="text-foreground truncate font-medium">{r.label}</p>
              <p className="text-[9px] text-muted-foreground/60 truncate">{r.source}</p>
            </div>
            <div className="col-span-1 text-right font-mono tabular-nums text-foreground">
              {r.count}
            </div>
            <div className="col-span-2 text-right font-mono tabular-nums text-orange-400">
              {Math.round(r.penalty * 10) / 10}
            </div>
            <div className="col-span-2 text-right font-mono tabular-nums text-muted-foreground">
              {Math.round(r.maxPenalty * 10) / 10}
            </div>
            <div className="col-span-4 flex items-center gap-1.5">
              <div className="flex-1 h-1.5 rounded-full bg-white/6 overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full',
                    pct >= 40 ? 'bg-red-500' : pct >= 20 ? 'bg-orange-500' : 'bg-yellow-500',
                  )}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-[10px] font-mono tabular-nums w-9 text-right text-muted-foreground">
                {pct}%
              </span>
            </div>
          </div>
        );
      })}
      <div className="grid grid-cols-12 gap-1 px-3 py-2 text-[10px] border-t" style={{ ...BORDER, background: 'hsl(230 15% 8%)' }}>
        <div className="col-span-7 text-muted-foreground">Total weighted penalty → Risk score</div>
        <div className="col-span-2 text-right font-mono text-muted-foreground">{Math.round(totalPenalty * 10) / 10}</div>
        <div className="col-span-3 text-right font-mono text-orange-400">{Math.round(riskScore * 10) / 10}/100</div>
      </div>
    </div>
  );
}

// ── Per-scanner health radar (uses real per-scanner scores) ──────────────────
type ScannerHealth = { key: string; label: string; score: number | null; applicable: boolean; reason?: string };

function HealthRadar({ breakdown }: { breakdown: Record<string, number | null> | null | undefined }) {
  const categories: ScannerHealth[] = useMemo(() => {
    const order: Array<keyof typeof SCANNER_LABELS> = ['sast', 'deps', 'secrets', 'container', 'cicd'];
    return order.map(k => {
      const score = breakdown?.[k] ?? null;
      const applicable = score !== null;
      return {
        key: k,
        label: SCANNER_LABELS[k].label.split(' ')[0],
        score: applicable ? Math.max(0, Math.min(100, Number(score))) : 0,
        applicable,
        reason: applicable ? undefined : 'Scanner skipped (not applicable)',
      };
    });
  }, [breakdown]);

  const allSkipped = categories.every(c => !c.applicable);

  if (allSkipped) {
    return (
      <div className="rounded-lg p-4 text-center" style={SUBTLE}>
        <p className="text-xs text-muted-foreground">No scanner results yet</p>
        <p className="text-[10px] text-muted-foreground/50 mt-1">
          Run a scan to populate the per-scanner breakdown.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={categories} cx="50%" cy="50%" outerRadius="75%">
            <PolarGrid stroke="hsl(230 15% 18%)" />
            <PolarAngleAxis dataKey="label" tick={{ fill: 'hsl(215 16% 65%)', fontSize: 10 }} />
            <Radar
              dataKey="score"
              stroke="#3b82f6"
              fill="#3b82f6"
              fillOpacity={0.18}
              strokeWidth={1.5}
              isAnimationActive={false}
            />
            <Tooltip
              contentStyle={{ background: 'hsl(230 15% 10%)', border: '1px solid hsl(230 15% 18%)', borderRadius: 8, fontSize: 11 }}
              formatter={(v: any, _n: any, ctx: any) => {
                const c = categories[ctx.dataIndex];
                if (!c.applicable) return ['N/A', c.label];
                return [Math.round(Number(v)), c.label];
              }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {categories.map(c => (
          <div key={c.key} className="flex items-center justify-between px-2 py-1 rounded text-[10px]" style={SUBTLE}>
            <span className="text-muted-foreground truncate">{c.label}</span>
            {c.applicable
              ? <span className={clsx('font-mono font-semibold',
                  (c.score ?? 0) >= 80 ? 'text-green-400' :
                  (c.score ?? 0) >= 60 ? 'text-yellow-400' :
                  (c.score ?? 0) >= 40 ? 'text-orange-400' : 'text-red-400',
                )}>
                  {Math.round(c.score ?? 0)}
                </span>
              : <span className="text-muted-foreground/50 italic text-[9px]">N/A</span>
            }
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Tab system inside the right column ────────────────────────────────────────
type Tab = 'overview' | 'findings' | 'scanners' | 'history';

interface RepoDrawerProps {
  repo: MergedRepo | null;
  onClose: () => void;
}

export default function RepoDrawer({ repo, onClose }: RepoDrawerProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState<Tab>('overview');

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

  const history: ScanHistoryEntry[] = useMemo(
    () => Array.isArray(histRaw) ? histRaw : (histRaw?.data ?? histRaw?.history ?? []),
    [histRaw],
  );
  const scoreData: RepoScore | null = scoreRaw?.data ?? scoreRaw;

  // Close on Escape + lock body scroll
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    if (repo) document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose, repo]);

  const risk  = repo?.risk;
  const rl    = risk?.risk_level ?? 'low';
  const rs    = RISK_STYLES[rl as keyof typeof RISK_STYLES] ?? RISK_STYLES.low;
  const healthScore = risk?.security_score ?? repo?.last_scan_score ?? null;
  const riskScore   = risk?.risk_score ?? null;

  const maxFindings = Math.max(
    risk?.critical_count ?? 0,
    risk?.high_count ?? 0,
    Math.max(0, (risk?.open_findings ?? 0) - (risk?.critical_count ?? 0) - (risk?.high_count ?? 0)),
    1,
  );

  const chartData = useMemo(
    () => history.map(h => ({
      date: new Date(h.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      score: h.score,
      critical: h.critical,
      high: h.high,
    })).reverse(),
    [history],
  );

  const tabs: Array<{ id: Tab; label: string; icon: React.ElementType }> = [
    { id: 'overview', label: 'Overview',    icon: Shield },
    { id: 'findings', label: 'Findings',    icon: Bug },
    { id: 'scanners', label: 'Scanners',    icon: Wrench },
    { id: 'history',  label: 'History',     icon: Activity },
  ];

  return (
    <AnimatePresence>
      {repo && (
        <>
          {/* Backdrop */}
          <motion.div
            ref={overlayRef}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/70"
            onClick={onClose}
          />

          {/* Full-screen slide-over panel */}
          <motion.div
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 280 }}
            className="fixed inset-y-0 right-0 z-50 flex flex-col shadow-2xl overflow-hidden"
            style={{
              width: 'min(1400px, 100vw)',
              background: 'hsl(230 15% 6%)',
              borderLeft: '1px solid hsl(230 15% 14%)',
            }}
          >
            {/* ── Sticky header ────────────────────────────────────── */}
            <div className="flex items-start justify-between gap-4 px-6 py-4 border-b flex-shrink-0" style={BORDER}>
              <div className="flex items-start gap-3 min-w-0 flex-1">
                <div className={clsx('w-1.5 self-stretch rounded-full flex-shrink-0', rs.dot)} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-base font-bold text-foreground truncate">{repo.full_name}</h2>
                    <span className={clsx(
                      'text-[9px] px-2 py-0.5 rounded-full font-bold border uppercase tracking-wider',
                      rs.bg, rs.text, rs.border,
                    )}>
                      {rl}
                    </span>
                    {healthScore != null && (
                      <span className={clsx('text-[9px] px-2 py-0.5 rounded-full border font-mono',
                        healthScore >= 80 ? 'border-green-500/30 bg-green-500/10 text-green-400'
                        : healthScore >= 60 ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400'
                        : 'border-red-500/30 bg-red-500/10 text-red-400',
                      )}>
                        Health {Math.round(healthScore)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground mt-1 flex-wrap">
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
                    {repo.clone_url && (
                      <>
                        <span className="opacity-30">·</span>
                        <a href={repo.clone_url} target="_blank" rel="noreferrer"
                          className="flex items-center gap-1 text-blue-400 hover:text-blue-300">
                          <ExternalLink className="w-2.5 h-2.5" /> open
                        </a>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <button onClick={onClose} aria-label="Close"
                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors flex-shrink-0">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* ── Tab bar ──────────────────────────────────────────── */}
            <div className="flex items-center gap-1 px-6 py-2 border-b flex-shrink-0" style={BORDER}>
              {tabs.map(t => {
                const active = tab === t.id;
                return (
                  <button key={t.id} onClick={() => setTab(t.id)}
                    className={clsx(
                      'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors',
                      active
                        ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                        : 'text-muted-foreground hover:text-foreground hover:bg-white/5 border border-transparent',
                    )}>
                    <t.icon className="w-3.5 h-3.5" />
                    {t.label}
                  </button>
                );
              })}
              <span className="ml-auto text-[10px] text-muted-foreground/50">
                Press <kbd className="px-1 py-0.5 rounded border text-[9px]" style={BORDER}>Esc</kbd> to close
              </span>
            </div>

            {/* ── Body: 2-column grid ──────────────────────────────── */}
            <div className="flex-1 overflow-y-auto">
              <div className="grid grid-cols-12 gap-0">
                {/* Left column — sticky context */}
                <aside className="col-span-12 lg:col-span-4 xl:col-span-3 border-r" style={{ ...BORDER, background: 'hsl(230 15% 7%)' }}>
                  <div className="p-5 space-y-5 lg:sticky lg:top-0">
                    {/* Gauges */}
                    <div className="flex items-center justify-around gap-3 p-4 rounded-xl" style={SUBTLE}>
                      {healthScore != null
                        ? <ScoreGauge score={healthScore} label="Health Score" sub="0-100, higher is better" />
                        : <ScoreGauge score={0} label="Health Score" sub="No data" />}
                      {riskScore != null
                        ? <ScoreGauge score={riskScore} label="Risk Score" sub="0-100, higher is riskier" />
                        : <ScoreGauge score={0} label="Risk Score" sub="No data" />}
                    </div>

                    {/* Repository facts */}
                    <div>
                      <SectionLabel>Repository</SectionLabel>
                      <StatRow label="Full name"   value={repo.full_name} />
                      <StatRow label="Provider"    value={repo.provider} />
                      <StatRow label="Visibility"  value={repo.is_private ? 'Private' : 'Public'} />
                      <StatRow label="Branch"      value={repo.default_branch} />
                      {repo.language && <StatRow label="Language" value={repo.language} />}
                      {risk?.owner && <StatRow label="Owner" value={risk.owner} />}
                      <StatRow
                        label="Dockerfile"
                        value={repo.has_dockerfile ? 'Detected' : 'Not found'}
                        color={repo.has_dockerfile ? 'text-blue-400' : 'text-muted-foreground'}
                        hint={repo.has_dockerfile
                          ? 'Dockerfile or docker/Dockerfile* found during detection'
                          : 'No Dockerfile in the repository root or docker/ folders'}
                      />
                      <StatRow
                        label="CI/CD config"
                        value={repo.has_cicd ? 'Detected' : 'Not found'}
                        color={repo.has_cicd ? 'text-green-400' : 'text-muted-foreground'}
                        hint={repo.has_cicd
                          ? 'GitHub Actions, GitLab CI, Jenkinsfile, Azure Pipelines, or similar'
                          : 'No CI/CD configuration found'}
                      />
                    </div>

                    {/* Quick KPIs */}
                    {risk && (
                      <div>
                        <SectionLabel>Headline</SectionLabel>
                        <StatRow
                          label="Open findings"
                          value={risk.open_findings}
                          color={risk.open_findings > 0 ? 'text-orange-400' : 'text-green-400'}
                        />
                        <StatRow
                          label="Risk score"
                          value={`${Math.round(risk.risk_score)}/100`}
                          color={risk.risk_score > 60 ? 'text-red-400' : risk.risk_score > 30 ? 'text-yellow-400' : 'text-green-400'}
                          hint="Weighted sum of critical/high/secrets/container/compliance findings, capped at 100"
                        />
                        <StatRow
                          label="Exposure"
                          value={`${risk.exposure_risk.toFixed(1)}/100`}
                          color={risk.exposure_risk > 60 ? 'text-red-400' : risk.exposure_risk > 30 ? 'text-yellow-400' : 'text-green-400'}
                        />
                        <StatRow
                          label="Trend"
                          value={risk.trend}
                          color={risk.trend === 'improving' ? 'text-green-400' : risk.trend === 'worsening' ? 'text-red-400' : 'text-muted-foreground'}
                        />
                      </div>
                    )}

                    {/* Last scan */}
                    {(repo.last_scan_at || risk?.last_scan_at) && (
                      <div>
                        <SectionLabel>Last Scan</SectionLabel>
                        <StatRow label="Scanned at"
                          value={new Date(repo.last_scan_at ?? risk?.last_scan_at ?? '').toLocaleString()} />
                        {scoreData?.scan_id && (
                          <StatRow label="Scan ID" value={scoreData.scan_id.slice(0, 8) + '…'} />
                        )}
                        {scoreData?.last_scan_at && (
                          <StatRow label="Result time" value={new Date(scoreData.last_scan_at).toLocaleString()} />
                        )}
                      </div>
                    )}
                  </div>
                </aside>

                {/* Right column — content per tab */}
                <main className="col-span-12 lg:col-span-8 xl:col-span-9 p-6 space-y-6">
                  {tab === 'overview' && (
                    <>
                      {/* AI Summary */}
                      <section>
                        <SectionLabel hint="Generated from the latest scan findings">
                          AI Security Summary
                        </SectionLabel>
                        <div className="rounded-xl p-4" style={SUBTLE}>
                          {scoreLoading && !scoreData ? (
                            <div className="space-y-1.5">
                              <Skeleton className="h-3 w-full" />
                              <Skeleton className="h-3 w-5/6" />
                              <Skeleton className="h-3 w-4/5" />
                            </div>
                          ) : scoreData?.ai_summary ? (
                            <>
                              <div className="flex items-start gap-2">
                                <Sparkles className="w-3.5 h-3.5 text-blue-400 mt-0.5 flex-shrink-0" />
                                <p className="text-xs text-foreground/90 leading-relaxed">
                                  {scoreData.ai_summary}
                                </p>
                              </div>
                              {/* Source pill */}
                              <div className="mt-3 flex items-center gap-2">
                                <SourcePill source={scoreData.ai_source ?? inferSummarySource(scoreData)} />
                                {scoreData?.ai_suggestions && scoreData.ai_suggestions.length > 0 && (
                                  <span className="text-[10px] text-muted-foreground/60">
                                    {scoreData.ai_suggestions.length} suggestion{scoreData.ai_suggestions.length === 1 ? '' : 's'}
                                  </span>
                                )}
                              </div>
                              {scoreData?.ai_suggestions && scoreData.ai_suggestions.length > 0 && (
                                <ul className="mt-3 space-y-1.5">
                                  {scoreData.ai_suggestions.map((s, i) => (
                                    <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                                      <span className="text-blue-400 mt-0.5 flex-shrink-0">•</span>
                                      <span>{s}</span>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </>
                          ) : (
                            <p className="text-xs text-muted-foreground italic">
                              No AI summary available. Run a scan to generate one.
                            </p>
                          )}
                        </div>
                      </section>

                      {/* Per-scanner health radar */}
                      <section>
                        <SectionLabel hint="Real per-scanner scores from the latest scan">
                          Scanner Health
                        </SectionLabel>
                        <HealthRadar breakdown={scoreData?.breakdown ?? null} />
                      </section>
                    </>
                  )}

                  {tab === 'findings' && (
                    <section>
                      <SectionLabel hint="Open findings grouped by severity">
                        Security Findings
                      </SectionLabel>
                      {risk ? (
                        <div className="rounded-xl p-4 space-y-2" style={SUBTLE}>
                          <FindingBar label="Critical" count={risk.critical_count}  max={maxFindings} color="text-red-400" />
                          <FindingBar label="High"     count={risk.high_count}      max={maxFindings} color="text-orange-400" />
                          <FindingBar
                            label="Med/Low"
                            count={Math.max(0, risk.open_findings - risk.critical_count - risk.high_count)}
                            max={maxFindings}
                            color="text-yellow-400"
                          />
                          <div className="grid grid-cols-3 gap-2 mt-4">
                            <div className="p-3 rounded-lg text-center" style={{ background: 'hsl(230 15% 11%)' }}>
                              <Key className="w-4 h-4 text-yellow-400 mx-auto mb-1" />
                              <p className="text-base font-bold text-yellow-400">{risk.secret_count}</p>
                              <p className="text-[10px] text-muted-foreground">Secrets</p>
                            </div>
                            <div className="p-3 rounded-lg text-center" style={{ background: 'hsl(230 15% 11%)' }}>
                              <Container className="w-4 h-4 text-blue-400 mx-auto mb-1" />
                              <p className="text-base font-bold text-blue-400">{risk.container_count}</p>
                              <p className="text-[10px] text-muted-foreground">Container</p>
                            </div>
                            <div className="p-3 rounded-lg text-center" style={{ background: 'hsl(230 15% 11%)' }}>
                              <AlertTriangle className="w-4 h-4 text-purple-400 mx-auto mb-1" />
                              <p className="text-base font-bold text-purple-400">{risk.compliance_violations}</p>
                              <p className="text-[10px] text-muted-foreground">Violations</p>
                            </div>
                          </div>
                          <div className="mt-4">
                            <StatRow label="Total open findings" value={risk.open_findings}
                              color={risk.open_findings > 0 ? 'text-orange-400' : 'text-green-400'} />
                            {risk.previous_risk_score != null && (
                              <StatRow label="Previous risk score" value={`${Math.round(risk.previous_risk_score)}/100`} />
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="rounded-xl p-8 text-center" style={SUBTLE}>
                          <Shield className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-30" />
                          <p className="text-sm font-medium text-muted-foreground">No security data yet</p>
                          <p className="text-xs text-muted-foreground/60 mt-1">
                            Run a scan to generate security findings.
                          </p>
                        </div>
                      )}
                    </section>
                  )}

                  {tab === 'scanners' && (
                    <section>
                      <SectionLabel hint="Why this repository has the score it has">
                        Scanner Contribution
                      </SectionLabel>
                      <FactorsTable factors={risk?.factors} riskScore={risk?.risk_score ?? 0} />

                      <div className="mt-6">
                        <SectionLabel hint="Real per-scanner scores from the latest scan">
                          Per-Scanner Health
                        </SectionLabel>
                        <HealthRadar breakdown={scoreData?.breakdown ?? null} />
                      </div>
                    </section>
                  )}

                  {tab === 'history' && (
                    <section>
                      <SectionLabel hint="All scans for this repository, most recent first">
                        Scan History
                      </SectionLabel>
                      {histLoading ? (
                        <Skeleton className="h-32 w-full rounded-xl" />
                      ) : chartData.length > 1 ? (
                        <div className="rounded-xl p-4" style={SUBTLE}>
                          <ResponsiveContainer width="100%" height={180}>
                            <AreaChart data={chartData}>
                              <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 16%)" />
                              <XAxis dataKey="date" tick={{ fill: 'hsl(215 16% 55%)', fontSize: 10 }} />
                              <YAxis domain={[0, 100]} tick={{ fill: 'hsl(215 16% 55%)', fontSize: 10 }} />
                              <Tooltip
                                contentStyle={{ background: 'hsl(230 15% 10%)', border: '1px solid hsl(230 15% 18%)', borderRadius: 8, fontSize: 11 }}
                                formatter={(v: any, name: string) => [v, name === 'score' ? 'Score' : name === 'critical' ? 'Critical' : 'High']}
                              />
                              <Area type="monotone" dataKey="score"    stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={1.5} />
                              <Area type="monotone" dataKey="critical" stroke="#ef4444" fill="#ef4444" fillOpacity={0.06} strokeWidth={1} />
                              <Area type="monotone" dataKey="high"     stroke="#f97316" fill="#f97316" fillOpacity={0.04} strokeWidth={1} />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      ) : (
                        <div className="rounded-xl p-8 text-center" style={SUBTLE}>
                          <Activity className="w-6 h-6 text-muted-foreground mx-auto mb-2 opacity-40" />
                          <p className="text-sm text-muted-foreground">No scan history yet</p>
                          <p className="text-[10px] text-muted-foreground/50 mt-1">Run a scan to see history</p>
                        </div>
                      )}

                      {/* Recent scan entries */}
                      {history.length > 0 && (
                        <div className="mt-4 rounded-xl overflow-hidden" style={SUBTLE}>
                          <div className="grid grid-cols-12 gap-2 px-4 py-2 text-[9px] font-bold uppercase tracking-wider text-muted-foreground/60 border-b" style={BORDER}>
                            <div className="col-span-3">Date</div>
                            <div className="col-span-1 text-right">Status</div>
                            <div className="col-span-2 text-right">Score</div>
                            <div className="col-span-2 text-right">Critical</div>
                            <div className="col-span-2 text-right">High</div>
                            <div className="col-span-2 text-right">Secrets</div>
                          </div>
                          {history.slice(0, 10).map((h, i) => (
                            <div key={i} className="grid grid-cols-12 gap-2 px-4 py-2 text-[11px] items-center border-b last:border-0" style={BORDER}>
                              <div className="col-span-3 flex items-center gap-1.5 text-muted-foreground">
                                <Clock className="w-3 h-3" />
                                <span className="font-mono">{new Date(h.date).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                              </div>
                              <div className="col-span-1 text-right">
                                <span className={clsx('text-[9px] px-1.5 py-0.5 rounded font-mono',
                                  h.status === 'completed' ? 'text-green-400 bg-green-500/10'
                                  : h.status === 'failed' ? 'text-red-400 bg-red-500/10'
                                  : 'text-blue-400 bg-blue-500/10',
                                )}>
                                  {h.status ?? 'completed'}
                                </span>
                              </div>
                              <div className="col-span-2 text-right font-mono">
                                <span className={clsx('font-semibold',
                                  h.score >= 80 ? 'text-green-400' : h.score >= 60 ? 'text-yellow-400' : 'text-red-400',
                                )}>
                                  {Math.round(h.score)}
                                </span>
                              </div>
                              <div className="col-span-2 text-right font-mono text-red-400">{h.critical}C</div>
                              <div className="col-span-2 text-right font-mono text-orange-400">{h.high}H</div>
                              <div className="col-span-2 text-right font-mono text-yellow-400">{h.secrets}S</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  )}
                </main>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ── AI source pill ───────────────────────────────────────────────────────────
function SourcePill({ source }: { source: 'llm' | 'fallback' | 'unknown' }) {
  if (source === 'llm') {
    return (
      <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded border border-blue-500/30 bg-blue-500/10 text-blue-400 font-medium">
        <Sparkles className="w-2.5 h-2.5" /> Generated by LLM
      </span>
    );
  }
  if (source === 'fallback') {
    return (
      <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded border border-yellow-500/30 bg-yellow-500/10 text-yellow-400 font-medium"
        title="This summary was generated locally from finding counts (no LLM call).">
        <Wrench className="w-2.5 h-2.5" /> Generated locally
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded border border-white/10 bg-white/5 text-muted-foreground font-medium"
      title="Source unknown — likely local fallback.">
      <Info className="w-2.5 h-2.5" /> Source unknown
    </span>
  );
}

function inferSummarySource(score: RepoScore | any): 'llm' | 'fallback' | 'unknown' {
  // Heuristic: backend may surface source as `ai_source` or `ai_model`.
  if (score?.ai_source === 'llm' || score?.ai_model) return 'llm';
  if (score?.ai_source === 'fallback') return 'fallback';
  const summary = String(score?.ai_summary ?? '');
  // Fallback summaries in scan_engine start with "No security issues found" or
  // "Scan of <repo> completed with N findings".
  if (/^No security issues found/i.test(summary) || /^Scan of /i.test(summary)) return 'fallback';
  return 'unknown';
}
