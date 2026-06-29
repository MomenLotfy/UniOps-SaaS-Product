import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  AreaChart, Area,
} from 'recharts';
import type { MergedRepo, ScanHistoryEntry } from './types';
import { RISK_STYLES } from './types';

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card-base p-4">
      <p className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wide">{title}</p>
      {children}
    </div>
  );
}

const PIE_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#22c55e',
  unscanned:'#475569',
};

const TOOLTIP_STYLE = {
  background:   'hsl(230 15% 10%)',
  border:       '1px solid hsl(230 15% 18%)',
  borderRadius: 8,
  fontSize:     11,
};

interface RepoChartsProps {
  repos:   MergedRepo[];
  history: ScanHistoryEntry[];
  loading: boolean;
}

function RepoCharts({ repos, history, loading }: RepoChartsProps) {
  // Risk distribution pie
  const riskDist = useMemo(() => {
    const counts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0, unscanned: 0 };
    for (const r of repos) {
      const lvl = r.risk?.risk_level;
      if (lvl && lvl in counts) counts[lvl]++;
      else counts.unscanned++;
    }
    return Object.entries(counts)
      .filter(([, v]) => v > 0)
      .map(([name, value]) => ({ name, value }));
  }, [repos]);

  // Top risky repos (by risk_score descending)
  const topRisk = useMemo(() =>
    [...repos]
      .filter(r => r.risk?.risk_score != null)
      .sort((a, b) => (b.risk!.risk_score) - (a.risk!.risk_score))
      .slice(0, 6)
      .map(r => ({
        name:  r.name.length > 16 ? r.name.slice(0, 14) + '…' : r.name,
        score: Math.round(r.risk!.risk_score),
        level: r.risk!.risk_level,
      })),
    [repos],
  );

  // Health distribution (by score buckets)
  const healthDist = useMemo(() => {
    const buckets = { 'A (80–100)': 0, 'B (60–79)': 0, 'C (40–59)': 0, 'D (<40)': 0, 'Unknown': 0 };
    for (const r of repos) {
      const s = r.risk?.security_score ?? r.last_scan_score;
      if      (s == null)  buckets['Unknown']++;
      else if (s >= 80)    buckets['A (80–100)']++;
      else if (s >= 60)    buckets['B (60–79)']++;
      else if (s >= 40)    buckets['C (40–59)']++;
      else                 buckets['D (<40)']++;
    }
    return Object.entries(buckets).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }));
  }, [repos]);

  // Scan activity timeline (aggregate from history)
  const scanActivity = useMemo(() =>
    history
      .slice(0, 30)
      .map(h => ({
        date:  new Date(h.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        score: h.score,
        crit:  h.critical,
        high:  h.high,
      }))
      .reverse(),
    [history],
  );

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="card-base h-48 animate-pulse" />
        ))}
      </div>
    );
  }

  if (repos.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      {/* Risk Distribution Pie */}
      {riskDist.length > 0 && (
        <SectionCard title="Risk Distribution">
          <div className="flex items-center gap-3">
            <ResponsiveContainer width={100} height={100}>
              <PieChart>
                <Pie data={riskDist} dataKey="value" cx="50%" cy="50%"
                  innerRadius={28} outerRadius={46} paddingAngle={2} strokeWidth={0}>
                  {riskDist.map(entry => (
                    <Cell key={entry.name} fill={PIE_COLORS[entry.name] ?? '#475569'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-1.5 flex-1">
              {riskDist.map(({ name, value }) => (
                <div key={name} className="flex items-center justify-between text-[10px]">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: PIE_COLORS[name] ?? '#475569' }} />
                    <span className="text-muted-foreground capitalize">{name}</span>
                  </div>
                  <span className="font-bold text-foreground">{value}</span>
                </div>
              ))}
            </div>
          </div>
        </SectionCard>
      )}

      {/* Health Score Distribution */}
      {healthDist.length > 0 && (
        <SectionCard title="Health Distribution">
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={healthDist} margin={{ left: -20, right: 4, top: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 16%)" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: 'hsl(215 16% 45%)', fontSize: 8 }} />
              <YAxis tick={{ fill: 'hsl(215 16% 45%)', fontSize: 9 }} allowDecimals={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [v, 'Repos']} />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {healthDist.map(({ name }, i) => (
                  <Cell key={i}
                    fill={
                      name.startsWith('A') ? '#22c55e'
                      : name.startsWith('B') ? '#eab308'
                      : name.startsWith('C') ? '#f97316'
                      : name.startsWith('D') ? '#ef4444'
                      : '#475569'
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      )}

      {/* Top Risk Repos */}
      {topRisk.length > 0 && (
        <SectionCard title="Top Risk Repositories">
          <div className="space-y-2">
            {topRisk.map(({ name, score, level }) => {
              const color = RISK_STYLES[level as keyof typeof RISK_STYLES]?.bar ?? 'bg-gray-500';
              const pct   = score;
              return (
                <div key={name}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-[10px] text-muted-foreground truncate max-w-[120px]">{name}</span>
                    <span className="text-[10px] font-bold text-foreground font-mono">{score}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/6 overflow-hidden">
                    <div className={clsx('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </SectionCard>
      )}

      {/* Scan Activity Timeline */}
      {scanActivity.length > 1 && (
        <SectionCard title="Scan Activity">
          <ResponsiveContainer width="100%" height={100}>
            <AreaChart data={scanActivity} margin={{ left: -20, right: 4, top: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 16%)" />
              <XAxis dataKey="date" tick={{ fill: 'hsl(215 16% 45%)', fontSize: 8 }}
                interval={Math.floor(scanActivity.length / 4)} />
              <YAxis domain={[0, 100]} tick={{ fill: 'hsl(215 16% 45%)', fontSize: 9 }} />
              <Tooltip contentStyle={TOOLTIP_STYLE}
                formatter={(v: any, n: string) => [v, n === 'score' ? 'Score' : n]} />
              <Area type="monotone" dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={1.5} />
              <Area type="monotone" dataKey="crit"  stroke="#ef4444" fill="#ef4444" fillOpacity={0.06} strokeWidth={1} />
            </AreaChart>
          </ResponsiveContainer>
        </SectionCard>
      )}

      {/* Scan coverage summary */}
      {repos.length > 0 && (
        <SectionCard title="Scan Coverage">
          <div className="space-y-2">
            {[
              { label: 'Total Repositories', value: repos.length, color: 'text-foreground' },
              { label: 'Risk Scored',   value: repos.filter(r => !!r.risk).length,            color: 'text-blue-400'   },
              { label: 'Has Dockerfile',value: repos.filter(r => r.has_dockerfile).length,    color: 'text-cyan-400'   },
              { label: 'Has CI/CD',     value: repos.filter(r => r.has_cicd).length,          color: 'text-green-400'  },
              { label: 'Critical Risk', value: repos.filter(r => r.risk?.risk_level === 'critical').length, color: 'text-red-400' },
            ].map(({ label, value, color }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">{label}</span>
                <span className={clsx('text-sm font-bold tabular-nums', color)}>{value}</span>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}

export default memo(RepoCharts);
