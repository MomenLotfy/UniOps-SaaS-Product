import { useState } from 'react';
import { TrendingUp, RefreshCw, Loader2, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, Legend,
} from 'recharts';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function ScoreGauge({ score, label }: { score: number; label: string }) {
  const color = score >= 80 ? '#22c55e' : score >= 60 ? '#eab308' : '#ef4444';
  return (
    <div className="card-base p-4 flex flex-col items-center">
      <div className="relative w-16 h-16 mb-2">
        <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="hsl(230 15% 16%)" strokeWidth="3" />
          <circle cx="18" cy="18" r="15.9" fill="none" stroke={color} strokeWidth="3"
            strokeDasharray={`${score} 100`} strokeLinecap="round" />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold" style={{ color }}>
          {score.toFixed(0)}
        </span>
      </div>
      <p className="text-[10px] text-muted-foreground text-center">{label}</p>
    </div>
  );
}

// Stable palette for up to 10 repos
const REPO_COLORS = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7',
  '#06b6d4', '#f97316', '#ec4899', '#84cc16', '#14b8a6',
];

const RISK_LEVEL_SCORE: Record<string, number> = {
  critical: 4, high: 3, medium: 2, low: 1,
};
const RISK_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e',
};

function RiskLevelTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border p-2 text-xs shadow-xl"
      style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 18%)' }}>
      <p className="text-muted-foreground mb-1">
        {new Date(label).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
      </p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color }} />
          <span className="text-muted-foreground truncate max-w-[100px]">{p.name}:</span>
          <span className="font-medium text-foreground">{Number(p.value).toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
}

export default function SecurityPosture() {
  const [days, setDays]             = useState(30);
  const [riskDays, setRiskDays]     = useState(30);
  const [snapshotting, setSnapshotting] = useState(false);

  const { data: summaryRaw,   loading: summaryLoading,  refetch: refetchSummary  } = useApi<any>('/security-posture/summary');
  const { data: historyRaw,   loading: historyLoading,  refetch: refetchHistory  } = useApi<any>(`/security-posture/history?days=${days}`);
  const { data: riskHistRaw,  loading: riskHistLoading, refetch: refetchRiskHist } = useApi<any>(`/repos/risk/history?days=${riskDays}`);

  const summary    = summaryRaw?.data ?? summaryRaw;
  const history    = historyRaw?.data ?? (Array.isArray(historyRaw) ? historyRaw : []);
  const riskHistRaw2 = riskHistRaw?.data ?? riskHistRaw;

  // riskHistRaw2 shape: { repos: [{repo_id, repo_name}], timeline: [{date, scores: {repo_id: risk_score}}] }
  const riskRepos:    Array<{ repo_id: string; repo_name: string }> = riskHistRaw2?.repos ?? [];
  const riskTimeline: Array<{ date: string; [key: string]: any }>   = riskHistRaw2?.timeline ?? [];

  const radarData = summary ? [
    { subject: 'Threats',    A: summary.threat_score ?? 0 },
    { subject: 'Vulns',      A: summary.vulnerability_score ?? 0 },
    { subject: 'Compliance', A: summary.compliance_score ?? 0 },
    { subject: 'Assets',     A: summary.asset_score ?? 0 },
    { subject: 'Policies',   A: summary.policy_score ?? 0 },
  ] : [];

  const handleSnapshot = async () => {
    setSnapshotting(true);
    try {
      await apiClient.post('/security-posture/snapshot');
      await Promise.all([refetchSummary(), refetchHistory(), refetchRiskHist()]);
    } finally { setSnapshotting(false); }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Security Posture</h1>
          <p className="text-xs text-muted-foreground">Computed score across all security dimensions</p>
        </div>
        <button onClick={handleSnapshot} disabled={snapshotting}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-60">
          {snapshotting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TrendingUp className="w-3.5 h-3.5" />}
          {snapshotting ? 'Computing…' : 'Snapshot Now'}
        </button>
      </div>

      {/* Overall score */}
      {summaryLoading ? (
        <Skeleton className="h-28 rounded-xl" />
      ) : summary ? (
        <div className="card-base p-5 flex items-center gap-6 flex-wrap">
          <div className="flex flex-col items-center">
            <div className={clsx('w-20 h-20 rounded-full border-4 flex items-center justify-center',
              (summary.current_score ?? 0) >= 80 ? 'border-green-500/50'
              : (summary.current_score ?? 0) >= 60 ? 'border-yellow-500/50'
              : 'border-red-500/50')}>
              <span className={clsx('text-2xl font-bold',
                (summary.current_score ?? 0) >= 80 ? 'text-green-400'
                : (summary.current_score ?? 0) >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                {(summary.current_score ?? 0).toFixed(0)}
              </span>
            </div>
            <p className={clsx('text-xs mt-1 capitalize font-medium',
              summary.trend === 'improving' ? 'text-green-400'
              : summary.trend === 'degrading' ? 'text-red-400' : 'text-muted-foreground')}>
              {summary.trend ?? 'stable'}
            </p>
          </div>
          <div className="flex-1 grid grid-cols-2 lg:grid-cols-5 gap-3">
            {[
              { label: 'Open Threats',       value: summary.open_threats ?? 0,       color: 'text-red-400' },
              { label: 'Open Vulns',          value: summary.open_vulns ?? 0,         color: 'text-orange-400' },
              { label: 'Critical Assets',     value: summary.critical_assets ?? 0,    color: 'text-yellow-400' },
              { label: 'Active Policies',     value: summary.active_policies ?? 0,    color: 'text-blue-400' },
              { label: 'Pending Exceptions',  value: summary.pending_exceptions ?? 0, color: 'text-purple-400' },
            ].map(({ label, value, color }) => (
              <div key={label} className="text-center">
                <p className={clsx('text-lg font-bold', color)}>{value}</p>
                <p className="text-[10px] text-muted-foreground">{label}</p>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="card-base py-8 text-center">
          <p className="text-sm text-muted-foreground">No posture data. Click "Snapshot Now" to compute.</p>
        </div>
      )}

      {/* Score breakdown gauges */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <ScoreGauge score={summary.threat_score ?? 0}         label="Threat Score" />
          <ScoreGauge score={summary.vulnerability_score ?? 0}  label="Vuln Score" />
          <ScoreGauge score={summary.compliance_score ?? 0}     label="Compliance" />
          <ScoreGauge score={summary.asset_score ?? 0}          label="Asset Score" />
          <ScoreGauge score={summary.policy_score ?? 0}         label="Policy Score" />
        </div>
      )}

      {/* Radar + Score Trend */}
      {radarData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card-base p-4">
            <p className="text-xs font-semibold text-muted-foreground mb-2">Dimension Breakdown</p>
            <ResponsiveContainer width="100%" height={180}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
                <PolarGrid stroke="hsl(230 15% 20%)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} />
                <Radar dataKey="A" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={1.5} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div className="card-base p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-muted-foreground">Score Trend</p>
              <div className="flex gap-1">
                {[7, 30, 90].map(d => (
                  <button key={d} onClick={() => setDays(d)}
                    className={clsx('px-2 py-0.5 text-[10px] rounded transition-colors',
                      days === d ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
                    {d}d
                  </button>
                ))}
              </div>
            </div>
            {historyLoading ? <Skeleton className="h-32" /> : history.length < 2 ? (
              <div className="h-32 flex items-center justify-center text-xs text-muted-foreground">
                Not enough data. Click "Snapshot Now" to build history.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={140}>
                <AreaChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 16%)" />
                  <XAxis dataKey="date" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 9 }}
                    tickFormatter={v => new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'hsl(215 16% 47%)', fontSize: 9 }} />
                  <Tooltip contentStyle={{ background: 'hsl(230 15% 10%)', border: '1px solid hsl(230 15% 18%)', borderRadius: 8, fontSize: 11 }}
                    formatter={(v: any, name: string) => [`${Number(v).toFixed(1)}`, name]} />
                  <Area type="monotone" dataKey="overall"    stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={2} name="Overall" />
                  <Area type="monotone" dataKey="threat"     stroke="#ef4444" fill="none" strokeWidth={1} strokeDasharray="4 2" name="Threat" />
                  <Area type="monotone" dataKey="compliance" stroke="#22c55e" fill="none" strokeWidth={1} strokeDasharray="4 2" name="Compliance" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}

      {/* ── Repository Risk History ─────────────────────────────────────────── */}
      <div className="card-base p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-xs font-semibold text-foreground">Repository Risk History</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Risk score per repo over time — higher score = more risky
            </p>
          </div>
          <div className="flex gap-1">
            {[7, 30, 90].map(d => (
              <button key={d} onClick={() => setRiskDays(d)}
                className={clsx('px-2 py-0.5 text-[10px] rounded transition-colors',
                  riskDays === d ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
                {d}d
              </button>
            ))}
          </div>
        </div>

        {riskHistLoading ? (
          <Skeleton className="h-48" />
        ) : riskTimeline.length < 2 ? (
          <div className="h-48 flex flex-col items-center justify-center gap-2 text-center">
            <AlertTriangle className="w-6 h-6 text-muted-foreground opacity-50" />
            <p className="text-xs text-muted-foreground">
              No risk history yet. Risk scores are recorded automatically after each repository scan.
            </p>
          </div>
        ) : (
          <>
            {/* Legend */}
            <div className="flex flex-wrap gap-3 mb-2">
              {riskRepos.slice(0, 10).map((r, i) => (
                <div key={r.repo_id} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <span className="w-2.5 h-0.5 rounded-full flex-shrink-0" style={{ background: REPO_COLORS[i % REPO_COLORS.length] }} />
                  <span className="truncate max-w-[120px]">{r.repo_name.split('/').pop()}</span>
                </div>
              ))}
            </div>

            {/* Risk score trend lines */}
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={riskTimeline} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 16%)" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: 'hsl(215 16% 47%)', fontSize: 9 }}
                  tickFormatter={v => new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: 'hsl(215 16% 47%)', fontSize: 9 }}
                  label={{ value: 'Risk', angle: -90, position: 'insideLeft', fill: 'hsl(215 16% 47%)', fontSize: 9, dx: -2 }}
                />
                {/* Risk zone bands */}
                <Tooltip content={<RiskLevelTooltip />} />
                {riskRepos.slice(0, 10).map((r, i) => (
                  <Line
                    key={r.repo_id}
                    type="monotone"
                    dataKey={r.repo_id}
                    name={r.repo_name.split('/').pop()}
                    stroke={REPO_COLORS[i % REPO_COLORS.length]}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 0 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>

            {/* Risk zone legend */}
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              {[
                { label: 'Critical ≥75', color: '#ef4444' },
                { label: 'High ≥50',     color: '#f97316' },
                { label: 'Medium ≥25',   color: '#eab308' },
                { label: 'Low <25',      color: '#22c55e' },
              ].map(({ label, color }) => (
                <div key={label} className="flex items-center gap-1.5 text-[9px] text-muted-foreground">
                  <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: color, opacity: 0.6 }} />
                  {label}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Per-repo current risk table */}
      {riskRepos.length > 0 && !riskHistLoading && (
        <div className="card-base p-4">
          <p className="text-xs font-semibold text-muted-foreground mb-3">Current Risk by Repository</p>
          <div className="space-y-2">
            {riskRepos.map((r, i) => {
              // Get latest risk score from timeline
              const latest = riskTimeline.length > 0
                ? riskTimeline[riskTimeline.length - 1]?.[r.repo_id]
                : null;
              const first  = riskTimeline.length > 0
                ? riskTimeline[0]?.[r.repo_id]
                : null;
              const delta  = latest != null && first != null ? latest - first : null;
              const level  = latest == null ? 'low'
                : latest >= 75 ? 'critical'
                : latest >= 50 ? 'high'
                : latest >= 25 ? 'medium' : 'low';

              return (
                <div key={r.repo_id} className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: REPO_COLORS[i % REPO_COLORS.length] }} />
                  <span className="text-xs text-foreground flex-1 truncate">{r.repo_name}</span>
                  {latest != null && (
                    <>
                      {/* Mini bar */}
                      <div className="w-20 h-1.5 rounded-full bg-white/10 overflow-hidden flex-shrink-0">
                        <div className="h-full rounded-full" style={{
                          width: `${Math.min(100, latest)}%`,
                          background: RISK_COLOR[level],
                        }} />
                      </div>
                      <span className="text-xs font-bold flex-shrink-0" style={{ color: RISK_COLOR[level] }}>
                        {latest.toFixed(0)}
                      </span>
                      {delta != null && Math.abs(delta) >= 1 && (
                        <span className={clsx('text-[10px] flex-shrink-0', delta > 0 ? 'text-red-400' : 'text-green-400')}>
                          {delta > 0 ? `+${delta.toFixed(0)}` : delta.toFixed(0)}
                        </span>
                      )}
                    </>
                  )}
                  {latest == null && (
                    <span className="text-[10px] text-muted-foreground">no data</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
