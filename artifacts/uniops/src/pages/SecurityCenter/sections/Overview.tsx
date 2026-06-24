import { useApi } from '@/hooks/use-api';
import { AlertTriangle, Bug, Shield, TrendingUp, CheckSquare, Server, Activity, RefreshCw } from 'lucide-react';
import { clsx } from 'clsx';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar } from 'recharts';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function StatCard({ label, value, sub, icon: Icon, color, loading }: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; color: string; loading?: boolean;
}) {
  return (
    <div className="card-base p-4 flex items-center gap-4">
      <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0', color)}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        {loading ? <Skeleton className="h-5 w-16 mb-1" /> : (
          <p className="text-lg font-bold text-foreground">{value}</p>
        )}
        <p className="text-xs text-muted-foreground">{label}</p>
        {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
      </div>
    </div>
  );
}

export default function Overview() {
  const { data: posture, loading: postureLoading, refetch } = useApi<any>('/security-posture/summary');
  const { data: threatStats }  = useApi<any>('/threats/stats');
  const { data: vulnStats }    = useApi<any>('/vulnerabilities/stats');
  const { data: complianceData } = useApi<any>('/compliance');
  const { data: policyStats }  = useApi<any>('/security-policies/stats');

  const ps    = posture?.data ?? posture;
  const ts    = threatStats?.data ?? threatStats;
  const vs    = vulnStats?.data ?? vulnStats;
  const comps = complianceData?.data ?? [];
  const pol   = policyStats?.data ?? policyStats;

  const history = ps?.history ?? [];
  const score   = ps?.current_score ?? 0;
  const trend   = ps?.trend ?? 'stable';

  const radarData = ps ? [
    { subject: 'Threats',        A: ps.threat_score ?? 0 },
    { subject: 'Vulns',          A: ps.vulnerability_score ?? 0 },
    { subject: 'Compliance',     A: ps.compliance_score ?? 0 },
    { subject: 'Assets',         A: ps.asset_score ?? 0 },
    { subject: 'Policies',       A: ps.policy_score ?? 0 },
  ] : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-foreground">Security Overview</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Real-time security posture and key metrics</p>
        </div>
        <button onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
          style={{ borderColor: 'hsl(230 15% 20%)' }}>
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Posture score + radar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card-base p-5 flex flex-col items-center justify-center">
          {postureLoading ? <Skeleton className="h-24 w-24 rounded-full" /> : (
            <>
              <div className={clsx(
                'w-24 h-24 rounded-full border-4 flex items-center justify-center mb-3',
                score >= 80 ? 'border-green-500/50' : score >= 60 ? 'border-yellow-500/50' : 'border-red-500/50'
              )}>
                <span className={clsx('text-2xl font-bold',
                  score >= 80 ? 'text-green-400' : score >= 60 ? 'text-yellow-400' : 'text-red-400'
                )}>{score.toFixed(0)}</span>
              </div>
              <p className="text-sm font-semibold text-foreground">Security Score</p>
              <p className={clsx('text-xs mt-0.5 capitalize',
                trend === 'improving' ? 'text-green-400' : trend === 'degrading' ? 'text-red-400' : 'text-muted-foreground'
              )}>{trend}</p>
            </>
          )}
        </div>

        <div className="card-base p-4 lg:col-span-2">
          <p className="text-xs font-semibold text-muted-foreground mb-2">Score Breakdown</p>
          {postureLoading ? <Skeleton className="h-32 w-full" /> : (
            <ResponsiveContainer width="100%" height={140}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
                <PolarGrid stroke="hsl(230 15% 20%)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} />
                <Radar name="Score" dataKey="A" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={1.5} />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={AlertTriangle} label="Open Threats" value={ts?.open ?? '—'}
          sub={`${ts?.critical ?? 0} critical`} color="bg-red-500/10 text-red-400" loading={!ts} />
        <StatCard icon={Bug} label="Open Vulns" value={vs?.open ?? '—'}
          sub={`${vs?.critical ?? 0} critical`} color="bg-orange-500/10 text-orange-400" loading={!vs} />
        <StatCard icon={CheckSquare} label="Avg Compliance"
          value={comps.length > 0 ? `${(comps.reduce((a: number, c: any) => a + (c.score ?? 0), 0) / comps.length).toFixed(0)}%` : '—'}
          sub={`${comps.length} frameworks`} color="bg-blue-500/10 text-blue-400" />
        <StatCard icon={Shield} label="Active Policies" value={pol?.active ?? '—'}
          sub={`${pol?.total ?? 0} total`} color="bg-purple-500/10 text-purple-400" loading={!pol} />
      </div>

      {/* Score trend */}
      {history.length > 1 && (
        <div className="card-base p-4">
          <p className="text-xs font-semibold text-muted-foreground mb-3">Posture Score Trend</p>
          <ResponsiveContainer width="100%" height={120}>
            <AreaChart data={history}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 16%)" />
              <XAxis dataKey="date" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 9 }}
                tickFormatter={v => new Date(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} />
              <YAxis domain={[0, 100]} tick={{ fill: 'hsl(215 16% 47%)', fontSize: 9 }} />
              <Tooltip contentStyle={{ background: 'hsl(230 15% 10%)', border: '1px solid hsl(230 15% 18%)', borderRadius: 8, fontSize: 11 }}
                formatter={(v: any) => [`${Number(v).toFixed(1)}`, 'Score']} />
              <Area type="monotone" dataKey="overall" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* No data state */}
      {!postureLoading && !ps && (
        <div className="card-base p-8 text-center">
          <Activity className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
          <p className="text-sm font-medium text-foreground mb-1">No posture data yet</p>
          <p className="text-xs text-muted-foreground">Run a security scan or click Refresh to compute your first score.</p>
        </div>
      )}
    </div>
  );
}
