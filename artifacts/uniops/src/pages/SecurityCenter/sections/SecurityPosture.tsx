import { useState } from 'react';
import {
  TrendingUp, TrendingDown, Minus, Loader2, RefreshCw,
  ShieldCheck, GitBranch, Cloud, Server, AlertTriangle,
  CheckCircle2, XCircle, BarChart3,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import {
  AreaChart, Area, LineChart, Line,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';

// ─── helpers ────────────────────────────────────────────────────────────────
function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function fmt(v: number | null | undefined, digits = 1) {
  if (v == null) return '—';
  return v.toFixed(digits);
}

function scoreColor(score: number | null | undefined, invert = false): string {
  if (score == null) return 'text-muted-foreground';
  const s = invert ? 100 - score : score;
  if (s >= 75) return 'text-green-400';
  if (s >= 50) return 'text-yellow-400';
  return 'text-red-400';
}

function scoreBg(score: number | null | undefined, invert = false): string {
  if (score == null) return 'border-white/10';
  const s = invert ? 100 - score : score;
  if (s >= 75) return 'border-green-500/30';
  if (s >= 50) return 'border-yellow-500/30';
  return 'border-red-500/30';
}

function scoreFill(score: number | null | undefined, invert = false): string {
  if (score == null) return '#6b7280';
  const s = invert ? 100 - score : score;
  if (s >= 75) return '#22c55e';
  if (s >= 50) return '#eab308';
  return '#ef4444';
}

function DeltaBadge({ delta, invert = false }: { delta: number | null | undefined; invert?: boolean }) {
  if (delta == null) return null;
  const effective = invert ? -delta : delta;
  if (Math.abs(delta) < 0.5) {
    return (
      <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
        <Minus className="w-2.5 h-2.5" /> stable
      </span>
    );
  }
  if (effective > 0) {
    return (
      <span className="flex items-center gap-0.5 text-[10px] text-green-400">
        <TrendingUp className="w-2.5 h-2.5" /> +{Math.abs(delta).toFixed(1)}
      </span>
    );
  }
  return (
    <span className="flex items-center gap-0.5 text-[10px] text-red-400">
      <TrendingDown className="w-2.5 h-2.5" /> {delta.toFixed(1)}
    </span>
  );
}

// Circular gauge
function CircleGauge({ score, size = 80, invert = false }: { score: number | null; size?: number; invert?: boolean }) {
  const fill  = scoreFill(score, invert);
  const pct   = score != null ? (invert ? 100 - score : score) : 0;
  const r     = 15.9;
  const circ  = 2 * Math.PI * r;
  const dash  = (pct / 100) * circ;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
        <circle cx="18" cy="18" r={r} fill="none" stroke="hsl(230 15% 16%)" strokeWidth="3" />
        {score != null && (
          <circle cx="18" cy="18" r={r} fill="none" stroke={fill} strokeWidth="3"
            strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round" />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-bold leading-none" style={{ fontSize: size * 0.2, color: fill }}>
          {score != null ? score.toFixed(0) : '—'}
        </span>
      </div>
    </div>
  );
}

// ─── Score Card ──────────────────────────────────────────────────────────────
interface ScoreCardProps {
  label:    string;
  sublabel: string;
  icon:     React.ReactNode;
  score:    number | null;
  delta?:   number | null;
  invert?:  boolean; // true = lower score is WORSE (risk score)
  extra?:   React.ReactNode;
  noData?:  boolean;
}
function ScoreCard({ label, sublabel, icon, score, delta, invert = false, extra, noData }: ScoreCardProps) {
  return (
    <div className={clsx('card-base p-4 flex flex-col gap-3 border', scoreBg(score, invert))}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="text-muted-foreground">{icon}</span>
            <p className="text-[11px] font-semibold text-foreground">{label}</p>
          </div>
          <p className="text-[10px] text-muted-foreground">{sublabel}</p>
        </div>
        {noData && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground">no data</span>
        )}
      </div>
      <div className="flex items-end justify-between gap-2">
        <CircleGauge score={score} invert={invert} />
        <div className="flex-1 flex flex-col items-end gap-1">
          <span className={clsx('text-2xl font-bold', scoreColor(score, invert))}>
            {score != null ? score.toFixed(0) : '—'}
          </span>
          <DeltaBadge delta={delta} invert={invert} />
          {extra}
        </div>
      </div>
    </div>
  );
}

// ─── Chart tooltip ────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border p-2 text-xs shadow-xl space-y-1"
      style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 18%)' }}>
      <p className="text-muted-foreground font-medium">
        {label ? new Date(label).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : ''}
      </p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-semibold text-foreground">{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</span>
        </div>
      ))}
    </div>
  );
}

const XAXIS_PROPS = {
  tick: { fill: 'hsl(215 16% 47%)', fontSize: 9 },
  tickFormatter: (v: string) => new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
};
const YAXIS_PROPS = { tick: { fill: 'hsl(215 16% 47%)', fontSize: 9 } };
const GRID_PROPS  = { strokeDasharray: '3 3', stroke: 'hsl(230 15% 16%)' };

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-2 text-center py-8">
      <BarChart3 className="w-7 h-7 text-muted-foreground opacity-30" />
      <p className="text-xs text-muted-foreground max-w-48">{message}</p>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function SecurityPosture() {
  const [days, setDays]         = useState<7 | 30 | 90>(30);
  const [snapshotting, setSnap] = useState(false);

  const { data: raw, loading, error, refetch } = useApi<any>(`/security-posture/dashboard?days=${days}`);
  const dash = raw?.data ?? raw;

  const scores    = dash?.scores    ?? {};
  const trends    = dash?.trends    ?? {};
  const trendKey  = `${days}d` as '7d' | '30d' | '90d';
  const trendData = trends[trendKey] ?? {};

  const riskTrend        = dash?.risk_trend        ?? [];
  const securityTrend    = dash?.security_trend    ?? [];
  const remediationTrend = dash?.remediation_trend ?? [];

  const handleSnapshot = async () => {
    setSnap(true);
    try {
      await apiClient.post('/security-posture/snapshot');
      await refetch();
    } finally { setSnap(false); }
  };

  return (
    <div className="space-y-5">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Security Posture Dashboard</h1>
          <p className="text-xs text-muted-foreground">
            Real-time aggregated security scores across your entire infrastructure
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Time range */}
          <div className="flex rounded-lg border border-white/10 overflow-hidden">
            {([7, 30, 90] as const).map(d => (
              <button key={d} onClick={() => setDays(d)}
                className={clsx('px-3 py-1.5 text-[11px] font-medium transition-colors',
                  days === d ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
                {d}d
              </button>
            ))}
          </div>
          <button onClick={handleSnapshot} disabled={snapshotting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-60">
            {snapshotting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            {snapshotting ? 'Snapshotting…' : 'Snapshot Now'}
          </button>
        </div>
      </div>

      {/* ── Loading skeleton ─────────────────────────────────────────────── */}
      {loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-36" />)}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-52" />)}
          </div>
        </div>
      )}

      {!loading && (
        <>
          {/* ── 5 Score cards ────────────────────────────────────────────── */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">

            {/* Overall Risk */}
            <ScoreCard
              label="Overall Risk"
              sublabel="Avg repo risk score"
              icon={<AlertTriangle className="w-3.5 h-3.5" />}
              score={scores.overall_risk ?? null}
              delta={trendData.risk_score}
              invert={true}
              extra={
                <span className="text-[9px] text-muted-foreground">
                  {scores.open_vulns ?? 0} open vulns
                </span>
              }
            />

            {/* Git Security */}
            <ScoreCard
              label="Git Security"
              sublabel="Avg scan score — GitHub / GitLab"
              icon={<GitBranch className="w-3.5 h-3.5" />}
              score={scores.git_security ?? null}
              noData={scores.git_security == null}
              extra={
                scores.critical_vulns != null && (
                  <span className="text-[9px] text-red-400">
                    {scores.critical_vulns} critical
                  </span>
                )
              }
            />

            {/* AWS Security */}
            <ScoreCard
              label="AWS Security"
              sublabel="Asset risk — cloud assets"
              icon={<Cloud className="w-3.5 h-3.5" />}
              score={scores.aws_security ?? null}
              noData={scores.aws_security == null}
            />

            {/* Kubernetes */}
            <ScoreCard
              label="Kubernetes"
              sublabel="K8s cluster security score"
              icon={<Server className="w-3.5 h-3.5" />}
              score={scores.k8s_security ?? null}
              noData={scores.k8s_security == null}
            />

            {/* Compliance */}
            <ScoreCard
              label="Compliance"
              sublabel="Avg across all frameworks"
              icon={<ShieldCheck className="w-3.5 h-3.5" />}
              score={scores.compliance ?? null}
              delta={trendData.compliance}
              extra={
                scores.resolved_vulns != null && (
                  <span className="text-[9px] text-green-400">
                    {scores.resolved_vulns} resolved
                  </span>
                )
              }
            />
          </div>

          {/* ── Summary bar ──────────────────────────────────────────────── */}
          <div className="card-base p-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              {
                label: 'Overall Security',
                value: scores.overall_security,
                sub: `${days}d delta: ${trendData.overall_security != null ? (trendData.overall_security > 0 ? '+' : '') + trendData.overall_security : '—'}`,
                color: scoreColor(scores.overall_security),
              },
              {
                label: 'Threat Score',
                value: scores.threat,
                sub: 'Higher = safer',
                color: scoreColor(scores.threat),
              },
              {
                label: 'Vuln Score',
                value: scores.vuln_score,
                sub: `${scores.open_vulns ?? 0} open  ·  ${scores.critical_vulns ?? 0} critical`,
                color: scoreColor(scores.vuln_score),
              },
              {
                label: 'Resolved Vulns',
                value: scores.resolved_vulns,
                sub: `of ${(scores.open_vulns ?? 0) + (scores.resolved_vulns ?? 0)} total`,
                color: 'text-green-400',
                raw: true,
              },
            ].map(({ label, value, sub, color, raw }) => (
              <div key={label} className="text-center">
                <p className={clsx('text-2xl font-bold', color)}>
                  {value != null ? (raw ? value : value.toFixed(0)) : '—'}
                </p>
                <p className="text-[11px] font-medium text-foreground mt-0.5">{label}</p>
                <p className="text-[10px] text-muted-foreground">{sub}</p>
              </div>
            ))}
          </div>

          {/* ── 3 Charts ─────────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

            {/* 1. Risk Trend */}
            <div className="card-base p-4">
              <div className="mb-3">
                <p className="text-xs font-semibold text-foreground">Risk Trend</p>
                <p className="text-[10px] text-muted-foreground">
                  Average repository risk score over time (higher = more risk)
                </p>
              </div>
              {riskTrend.length < 2 ? (
                <EmptyChart message="Risk data builds up automatically after each repository scan." />
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={riskTrend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <CartesianGrid {...GRID_PROPS} />
                    <XAxis dataKey="date" {...XAXIS_PROPS} />
                    <YAxis domain={[0, 100]} {...YAXIS_PROPS} />
                    <Tooltip content={<ChartTooltip />} />
                    <defs>
                      <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor="#ef4444" stopOpacity={0.25} />
                        <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <Area
                      type="monotone" dataKey="max_risk" name="Max risk"
                      stroke="#ef4444" fill="none" strokeWidth={1}
                      strokeDasharray="3 2" strokeOpacity={0.5}
                    />
                    <Area
                      type="monotone" dataKey="avg_risk" name="Avg risk"
                      stroke="#ef4444" fill="url(#riskGrad)" strokeWidth={2}
                    />
                    <Area
                      type="monotone" dataKey="min_risk" name="Min risk"
                      stroke="#22c55e" fill="none" strokeWidth={1}
                      strokeDasharray="3 2" strokeOpacity={0.6}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
              {/* Threshold legend */}
              <div className="flex gap-3 mt-2 flex-wrap">
                {[
                  { label: 'Critical ≥75', color: '#ef4444' },
                  { label: 'High ≥50',     color: '#f97316' },
                  { label: 'Medium ≥25',   color: '#eab308' },
                  { label: 'Low <25',      color: '#22c55e' },
                ].map(({ label, color }) => (
                  <div key={label} className="flex items-center gap-1 text-[9px] text-muted-foreground">
                    <span className="w-2 h-0.5 rounded-full" style={{ background: color }} />
                    {label}
                  </div>
                ))}
              </div>
            </div>

            {/* 2. Security Trend */}
            <div className="card-base p-4">
              <div className="mb-3">
                <p className="text-xs font-semibold text-foreground">Security Trend</p>
                <p className="text-[10px] text-muted-foreground">
                  Overall + dimension scores from posture snapshots
                </p>
              </div>
              {securityTrend.length < 2 ? (
                <EmptyChart message='Click "Snapshot Now" to begin recording security posture history.' />
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={securityTrend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <CartesianGrid {...GRID_PROPS} />
                    <XAxis dataKey="date" {...XAXIS_PROPS} />
                    <YAxis domain={[0, 100]} {...YAXIS_PROPS} />
                    <Tooltip content={<ChartTooltip />} />
                    <Line type="monotone" dataKey="overall"    name="Overall"    stroke="#3b82f6" strokeWidth={2.5} dot={false} />
                    <Line type="monotone" dataKey="threat"     name="Threat"     stroke="#22c55e" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                    <Line type="monotone" dataKey="vuln"       name="Vuln"       stroke="#f97316" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                    <Line type="monotone" dataKey="compliance" name="Compliance" stroke="#a855f7" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                  </LineChart>
                </ResponsiveContainer>
              )}
              <div className="flex gap-3 mt-2 flex-wrap">
                {[
                  { label: 'Overall',    color: '#3b82f6' },
                  { label: 'Threat',     color: '#22c55e' },
                  { label: 'Vuln',       color: '#f97316' },
                  { label: 'Compliance', color: '#a855f7' },
                ].map(({ label, color }) => (
                  <div key={label} className="flex items-center gap-1 text-[9px] text-muted-foreground">
                    <span className="w-2 h-0.5 rounded-full" style={{ background: color }} />
                    {label}
                  </div>
                ))}
              </div>
            </div>

            {/* 3. Remediation Trend */}
            <div className="card-base p-4">
              <div className="mb-3">
                <p className="text-xs font-semibold text-foreground">Remediation Trend</p>
                <p className="text-[10px] text-muted-foreground">
                  Open critical/high vs medium/low findings per scan day
                </p>
              </div>
              {remediationTrend.length === 0 ? (
                <EmptyChart message="Remediation data appears after repository scans complete." />
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={remediationTrend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <CartesianGrid {...GRID_PROPS} />
                    <XAxis dataKey="date" {...XAXIS_PROPS} />
                    <YAxis {...YAXIS_PROPS} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="open_crit_high" name="Critical + High" fill="#ef4444" fillOpacity={0.8} radius={[2, 2, 0, 0]} stackId="a" />
                    <Bar dataKey="open_med_low"   name="Medium + Low"   fill="#f97316" fillOpacity={0.6} radius={[2, 2, 0, 0]} stackId="a" />
                  </BarChart>
                </ResponsiveContainer>
              )}
              <div className="flex gap-3 mt-2 flex-wrap">
                {[
                  { label: 'Critical + High', color: '#ef4444' },
                  { label: 'Medium + Low',    color: '#f97316' },
                ].map(({ label, color }) => (
                  <div key={label} className="flex items-center gap-1 text-[9px] text-muted-foreground">
                    <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: color, opacity: 0.8 }} />
                    {label}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Trend delta pills ─────────────────────────────────────────── */}
          {trendData.has_baseline && (
            <div className="card-base p-3 flex flex-wrap gap-3 items-center">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                {days}d Change
              </p>
              {[
                { label: 'Security',   delta: trendData.overall_security, invert: false },
                { label: 'Compliance', delta: trendData.compliance,        invert: false },
                { label: 'Risk Score', delta: trendData.risk_score,        invert: true  },
              ].map(({ label, delta, invert }) => (
                delta != null && (
                  <div key={label} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 text-[11px]">
                    <span className="text-muted-foreground">{label}</span>
                    <DeltaBadge delta={delta} invert={invert} />
                  </div>
                )
              ))}
            </div>
          )}

          {/* ── No-data nudge ─────────────────────────────────────────────── */}
          {!trendData.has_baseline && (
            <div className="card-base p-3 flex items-center gap-3 border border-yellow-500/20">
              <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0" />
              <p className="text-xs text-muted-foreground">
                No baseline snapshot found for {days} days ago.
                Click <strong className="text-foreground">Snapshot Now</strong> regularly to build trend history for delta comparisons.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
