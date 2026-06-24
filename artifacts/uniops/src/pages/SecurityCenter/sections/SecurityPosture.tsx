import { useState } from 'react';
import { TrendingUp, RefreshCw, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar } from 'recharts';

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

export default function SecurityPosture() {
  const [days, setDays] = useState(30);
  const [snapshotting, setSnapshotting] = useState(false);

  const { data: summaryRaw, loading: summaryLoading, refetch: refetchSummary } = useApi<any>('/security-posture/summary');
  const { data: historyRaw, loading: historyLoading, refetch: refetchHistory } = useApi<any>(`/security-posture/history?days=${days}`);

  const summary = summaryRaw?.data ?? summaryRaw;
  const history = historyRaw?.data ?? (Array.isArray(historyRaw) ? historyRaw : []);

  const radarData = summary ? [
    { subject: 'Threats',   A: summary.threat_score ?? 0 },
    { subject: 'Vulns',     A: summary.vulnerability_score ?? 0 },
    { subject: 'Compliance',A: summary.compliance_score ?? 0 },
    { subject: 'Assets',    A: summary.asset_score ?? 0 },
    { subject: 'Policies',  A: summary.policy_score ?? 0 },
  ] : [];

  const handleSnapshot = async () => {
    setSnapshotting(true);
    try {
      await apiClient.post('/security-posture/snapshot');
      await Promise.all([refetchSummary(), refetchHistory()]);
    } finally { setSnapshotting(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Security Posture</h1>
          <p className="text-xs text-muted-foreground">Computed score across all security dimensions</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSnapshot} disabled={snapshotting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-60">
            {snapshotting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TrendingUp className="w-3.5 h-3.5" />}
            {snapshotting ? 'Computing…' : 'Snapshot Now'}
          </button>
        </div>
      </div>

      {/* Overall score */}
      {summaryLoading ? (
        <Skeleton className="h-28 rounded-xl" />
      ) : summary ? (
        <div className="card-base p-5 flex items-center gap-6 flex-wrap">
          <div className="flex flex-col items-center">
            <div className={clsx('w-20 h-20 rounded-full border-4 flex items-center justify-center',
              (summary.current_score ?? 0) >= 80 ? 'border-green-500/50' : (summary.current_score ?? 0) >= 60 ? 'border-yellow-500/50' : 'border-red-500/50')}>
              <span className={clsx('text-2xl font-bold',
                (summary.current_score ?? 0) >= 80 ? 'text-green-400' : (summary.current_score ?? 0) >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                {(summary.current_score ?? 0).toFixed(0)}
              </span>
            </div>
            <p className={clsx('text-xs mt-1 capitalize font-medium',
              summary.trend === 'improving' ? 'text-green-400' : summary.trend === 'degrading' ? 'text-red-400' : 'text-muted-foreground')}>
              {summary.trend ?? 'stable'}
            </p>
          </div>
          <div className="flex-1 grid grid-cols-2 lg:grid-cols-5 gap-3">
            {[
              { label: 'Open Threats',   value: summary.open_threats ?? 0,      color: 'text-red-400' },
              { label: 'Open Vulns',     value: summary.open_vulns ?? 0,        color: 'text-orange-400' },
              { label: 'Critical Assets',value: summary.critical_assets ?? 0,   color: 'text-yellow-400' },
              { label: 'Active Policies',value: summary.active_policies ?? 0,   color: 'text-blue-400' },
              { label: 'Pending Exceptions',value: summary.pending_exceptions ?? 0, color: 'text-purple-400' },
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
          <ScoreGauge score={summary.threat_score ?? 0} label="Threat Score" />
          <ScoreGauge score={summary.vulnerability_score ?? 0} label="Vuln Score" />
          <ScoreGauge score={summary.compliance_score ?? 0} label="Compliance" />
          <ScoreGauge score={summary.asset_score ?? 0} label="Asset Score" />
          <ScoreGauge score={summary.policy_score ?? 0} label="Policy Score" />
        </div>
      )}

      {/* Radar */}
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

          {/* Trend period selector + chart */}
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
                  <Area type="monotone" dataKey="overall" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={2} name="Overall" />
                  <Area type="monotone" dataKey="threat" stroke="#ef4444" fill="none" strokeWidth={1} strokeDasharray="4 2" name="Threat" />
                  <Area type="monotone" dataKey="compliance" stroke="#22c55e" fill="none" strokeWidth={1} strokeDasharray="4 2" name="Compliance" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
