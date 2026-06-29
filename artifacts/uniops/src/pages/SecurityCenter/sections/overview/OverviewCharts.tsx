import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar,
  LineChart, Line, Legend,
} from 'recharts';
import { TrendingUp, Activity, GitBranch, Shield } from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const TOOLTIP_STYLE = {
  background:   'hsl(230 15% 10%)',
  border:       '1px solid hsl(230 15% 18%)',
  borderRadius: 8,
  fontSize:     11,
};

const TICK_STYLE = { fill: 'hsl(215 16% 45%)', fontSize: 10 };
const GRID_COLOR = 'hsl(230 15% 16%)';

function ChartCard({ title, children, col2 = false }: {
  title: string;
  children: React.ReactNode;
  col2?: boolean;
}) {
  return (
    <div className={clsx('card-base p-4', col2 && 'col-span-2')}>
      <p className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wide">{title}</p>
      {children}
    </div>
  );
}

const RISK_PIE_COLORS: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e', unscanned: '#475569',
};
const GRADE_COLORS: Record<string, string> = {
  'A (≥90)': '#22c55e', 'B (80–89)': '#3b82f6', 'C (70–79)': '#eab308',
  'D (60–69)': '#f97316', 'F (<60)': '#ef4444', 'Unknown': '#475569',
};

interface OverviewChartsProps {
  postureHistory: Array<{ date: string; overall: number; threat: number; vulnerability: number; compliance: number }>;
  repos: any[];
  riskList: any[];
  scanHistory: any[];
  assets: any[];
  loading: boolean;
}

function OverviewCharts({ postureHistory, repos, riskList, scanHistory, assets, loading }: OverviewChartsProps) {
  const riskMap = useMemo(
    () => new Map(riskList.map((r: any) => [r.repo_id, r])),
    [riskList],
  );

  // Security trend from posture history
  const trendData = useMemo(() =>
    [...postureHistory].reverse().slice(0, 30).map(h => ({
      date: new Date(h.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      score: Math.round(h.overall ?? 0),
      threat: Math.round(h.threat ?? 0),
      vuln: Math.round(h.vulnerability ?? 0),
      compliance: Math.round(h.compliance ?? 0),
    })),
    [postureHistory],
  );

  // Risk distribution from repo risk
  const riskDist = useMemo(() => {
    const counts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0, unscanned: 0 };
    for (const r of repos) {
      const risk = riskMap.get(r.id);
      const lvl  = risk?.risk_level;
      if (lvl && lvl in counts) counts[lvl]++;
      else counts.unscanned++;
    }
    return Object.entries(counts).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }));
  }, [repos, riskMap]);

  // Repo health distribution
  const healthDist = useMemo(() => {
    const buckets: Record<string, number> = {
      'A (≥90)': 0, 'B (80–89)': 0, 'C (70–79)': 0, 'D (60–69)': 0, 'F (<60)': 0, 'Unknown': 0,
    };
    for (const r of repos) {
      const score = riskMap.get(r.id)?.security_score ?? r.last_scan_score;
      if      (score == null) buckets['Unknown']++;
      else if (score >= 90)   buckets['A (≥90)']++;
      else if (score >= 80)   buckets['B (80–89)']++;
      else if (score >= 70)   buckets['C (70–79)']++;
      else if (score >= 60)   buckets['D (60–69)']++;
      else                    buckets['F (<60)']++;
    }
    return Object.entries(buckets).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }));
  }, [repos, riskMap]);

  // Top risk repos
  const topRisk = useMemo(() =>
    riskList
      .filter((r: any) => r.risk_score != null)
      .sort((a: any, b: any) => b.risk_score - a.risk_score)
      .slice(0, 8)
      .map((r: any) => {
        const repo = repos.find((rp: any) => rp.id === r.repo_id);
        return {
          name:  (repo?.name ?? r.repo_id?.slice(0, 12) ?? 'Unknown').slice(0, 18),
          score: Math.round(r.risk_score),
          level: r.risk_level,
        };
      }),
    [riskList, repos],
  );

  // Scan activity from history
  const scanActivity = useMemo(() =>
    [...scanHistory].reverse().slice(0, 20).map(h => ({
      date:  new Date(h.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      score: h.score ?? 0,
      crit:  h.critical ?? 0,
      high:  h.high ?? 0,
    })),
    [scanHistory],
  );

  // Scan coverage
  const coverageData = useMemo(() => {
    const scanned   = repos.filter(r => r.last_scan_at).length;
    const unscanned = repos.length - scanned;
    return [
      { name: 'Scanned',   value: scanned,   fill: '#22c55e' },
      { name: 'Unscanned', value: unscanned,  fill: '#475569' },
    ].filter(d => d.value > 0);
  }, [repos]);

  // Assets by cloud
  const assetsByCloud = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const a of assets) {
      const cloud = a.cloud_provider ?? a.provider ?? a.platform ?? 'Unknown';
      counts[cloud] = (counts[cloud] ?? 0) + 1;
    }
    return Object.entries(counts).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, 6);
  }, [assets]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Security Score Trend — wide */}
      {trendData.length > 1 && (
        <ChartCard title="Overall Security Trend" col2={false}>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
              <XAxis dataKey="date" tick={TICK_STYLE} interval={Math.floor(trendData.length / 6)} />
              <YAxis domain={[0, 100]} tick={TICK_STYLE} />
              <Tooltip contentStyle={TOOLTIP_STYLE}
                formatter={(v: any, n: string) => [
                  `${Number(v).toFixed(1)}`,
                  n === 'score' ? 'Security Score' : n === 'threat' ? 'Threat Score' : n === 'vuln' ? 'Vuln Score' : 'Compliance',
                ]} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Area type="monotone" dataKey="score" name="score" stroke="#3b82f6" fill="url(#scoreGrad)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="threat" name="threat" stroke="#ef4444" strokeWidth={1} dot={false} strokeDasharray="4 2" />
              <Line type="monotone" dataKey="compliance" name="compliance" stroke="#22c55e" strokeWidth={1} dot={false} strokeDasharray="4 2" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {/* Charts grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {/* Risk Distribution */}
        {riskDist.length > 0 && (
          <ChartCard title="Repository Risk Distribution">
            <div className="flex items-center gap-4">
              <ResponsiveContainer width={110} height={110}>
                <PieChart>
                  <Pie data={riskDist} dataKey="value" cx="50%" cy="50%"
                    innerRadius={30} outerRadius={50} paddingAngle={2} strokeWidth={0}>
                    {riskDist.map(entry => (
                      <Cell key={entry.name} fill={RISK_PIE_COLORS[entry.name] ?? '#475569'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 flex-1">
                {riskDist.map(({ name, value }) => (
                  <div key={name} className="flex items-center justify-between text-[10px]">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: RISK_PIE_COLORS[name] ?? '#475569' }} />
                      <span className="text-muted-foreground capitalize">{name}</span>
                    </div>
                    <span className="font-bold text-foreground">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </ChartCard>
        )}

        {/* Repo Health Distribution */}
        {healthDist.length > 0 && (
          <ChartCard title="Repository Health Distribution">
            <ResponsiveContainer width="100%" height={110}>
              <BarChart data={healthDist} margin={{ left: -20, right: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
                <XAxis dataKey="name" tick={{ ...TICK_STYLE, fontSize: 8 }} />
                <YAxis tick={TICK_STYLE} allowDecimals={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [v, 'Repos']} />
                <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                  {healthDist.map(({ name }, i) => (
                    <Cell key={i} fill={GRADE_COLORS[name] ?? '#475569'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {/* Scan Coverage Donut */}
        {repos.length > 0 && coverageData.length > 0 && (
          <ChartCard title="Scan Coverage">
            <div className="flex items-center gap-4">
              <ResponsiveContainer width={110} height={110}>
                <PieChart>
                  <Pie data={coverageData} dataKey="value" cx="50%" cy="50%"
                    innerRadius={30} outerRadius={50} paddingAngle={2} strokeWidth={0}>
                    {coverageData.map(d => <Cell key={d.name} fill={d.fill} />)}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 flex-1">
                {coverageData.map(d => (
                  <div key={d.name}>
                    <div className="flex justify-between text-[10px] mb-0.5">
                      <span className="text-muted-foreground">{d.name}</span>
                      <span className="font-bold text-foreground">{d.value}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/6 overflow-hidden">
                      <div className="h-full rounded-full" style={{
                        width: `${(d.value / repos.length) * 100}%`,
                        background: d.fill,
                      }} />
                    </div>
                  </div>
                ))}
                <p className="text-[9px] text-muted-foreground">
                  {repos.filter(r => r.last_scan_at).length}/{repos.length} repos scanned
                </p>
              </div>
            </div>
          </ChartCard>
        )}

        {/* Vulnerability trend from posture history */}
        {trendData.length > 1 && (
          <ChartCard title="Vulnerability Trend">
            <ResponsiveContainer width="100%" height={110}>
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="vulnGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f97316" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#f97316" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                <XAxis dataKey="date" tick={{ ...TICK_STYLE, fontSize: 8 }} interval={Math.floor(trendData.length / 4)} />
                <YAxis domain={[0, 100]} tick={TICK_STYLE} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [`${v}`, 'Vuln Score']} />
                <Area type="monotone" dataKey="vuln" stroke="#f97316" fill="url(#vulnGrad)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {/* Compliance trend */}
        {trendData.length > 1 && (
          <ChartCard title="Compliance Trend">
            <ResponsiveContainer width="100%" height={110}>
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="compGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                <XAxis dataKey="date" tick={{ ...TICK_STYLE, fontSize: 8 }} interval={Math.floor(trendData.length / 4)} />
                <YAxis domain={[0, 100]} tick={TICK_STYLE} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [`${v}`, 'Compliance']} />
                <Area type="monotone" dataKey="compliance" stroke="#22c55e" fill="url(#compGrad)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {/* Scan Activity */}
        {scanActivity.length > 1 && (
          <ChartCard title="Recent Scan Activity">
            <ResponsiveContainer width="100%" height={110}>
              <AreaChart data={scanActivity}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                <XAxis dataKey="date" tick={{ ...TICK_STYLE, fontSize: 8 }} interval={Math.floor(scanActivity.length / 4)} />
                <YAxis tick={TICK_STYLE} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Area type="monotone" dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.08} strokeWidth={1.5} dot={false} />
                <Area type="monotone" dataKey="crit"  stroke="#ef4444" fill="#ef4444" fillOpacity={0.06} strokeWidth={1}   dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {/* Top Risk Repos */}
        {topRisk.length > 0 && (
          <ChartCard title="Top Risk Repositories">
            <div className="space-y-1.5">
              {topRisk.map(({ name, score, level }) => {
                const barColor =
                  level === 'critical' ? 'bg-red-500'
                  : level === 'high'   ? 'bg-orange-500'
                  : level === 'medium' ? 'bg-yellow-500'
                  : 'bg-green-500';
                return (
                  <div key={name}>
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[10px] text-muted-foreground truncate max-w-[140px]">{name}</span>
                      <span className="text-[10px] font-bold font-mono text-foreground ml-2">{score}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/6 overflow-hidden">
                      <div className={clsx('h-full rounded-full', barColor)} style={{ width: `${score}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </ChartCard>
        )}

        {/* Assets by Cloud */}
        {assetsByCloud.length > 0 && (
          <ChartCard title="Assets by Cloud Provider">
            <ResponsiveContainer width="100%" height={110}>
              <BarChart data={assetsByCloud} layout="vertical" margin={{ left: 40, right: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} horizontal={false} />
                <XAxis type="number" tick={TICK_STYLE} allowDecimals={false} />
                <YAxis type="category" dataKey="name" tick={{ ...TICK_STYLE, fontSize: 9 }} width={60} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [v, 'Assets']} />
                <Bar dataKey="value" fill="#3b82f6" fillOpacity={0.8} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}
      </div>

      {/* No data state */}
      {trendData.length === 0 && riskDist.length === 0 && repos.length === 0 && (
        <div className="card-base py-10 text-center">
          <Activity className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-30" />
          <p className="text-sm font-medium text-foreground">No chart data yet</p>
          <p className="text-xs text-muted-foreground/70 mt-1">Run security scans to populate trend charts</p>
        </div>
      )}
    </div>
  );
}

export default memo(OverviewCharts);
