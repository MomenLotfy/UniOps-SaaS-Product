import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import { BarChart3 } from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const TOOLTIP_STYLE = {
  background: 'hsl(230 15% 10%)',
  border: '1px solid hsl(230 15% 18%)',
  borderRadius: 8,
  fontSize: 11,
};
const TICK = { fill: 'hsl(215 16% 45%)', fontSize: 10 };
const GRID = 'hsl(230 15% 16%)';

const CLOUD_COLORS: Record<string, string> = {
  aws: '#f97316', azure: '#3b82f6', gcp: '#22c55e',
  kubernetes: '#06b6d4', vmware: '#a855f7', 'on-prem': '#64748b',
  unknown: '#475569',
};

const HEALTH_COLORS: Record<string, string> = {
  healthy: '#22c55e', warning: '#eab308', critical: '#ef4444',
  unknown: '#475569', offline: '#f97316',
};

const ENV_COLORS: Record<string, string> = {
  production: '#ef4444', staging: '#f97316', development: '#3b82f6',
  test: '#8b5cf6', qa: '#06b6d4', 'on-prem': '#64748b',
};

function group<T>(items: T[], key: (item: T) => string): Array<{ name: string; value: number }> {
  const map = new Map<string, number>();
  for (const item of items) {
    const k = key(item) || 'unknown';
    map.set(k, (map.get(k) ?? 0) + 1);
  }
  return Array.from(map.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card-base p-4">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">{title}</p>
      {children}
    </div>
  );
}

interface InfraChartsProps {
  clusters: any[];
  assets: any[];
  loading: boolean;
}

function InfraCharts({ clusters, assets, loading }: InfraChartsProps) {
  const byCloud = useMemo(() =>
    group(assets, (a: any) => (a.cloud_provider ?? a.provider ?? 'unknown').toLowerCase()),
    [assets],
  );

  const byRegion = useMemo(() =>
    group(assets, (a: any) => a.region ?? 'unknown'),
    [assets],
  );

  const byEnv = useMemo(() =>
    group(assets, (a: any) => (a.environment ?? 'unknown').toLowerCase()),
    [assets],
  );

  const byType = useMemo(() =>
    group(assets, (a: any) => a.asset_type ?? a.type ?? 'other'),
    [assets],
  );

  // Health donut
  const healthData = useMemo(() => {
    const map: Record<string, number> = { healthy: 0, warning: 0, critical: 0, offline: 0, unknown: 0 };
    const all = [...clusters, ...assets];
    for (const item of all) {
      const s = (item.status ?? 'unknown').toLowerCase();
      if (['active','running','healthy','connected'].includes(s))     map.healthy++;
      else if (['degraded','warning','maintenance'].includes(s))      map.warning++;
      else if (['error','failed','critical','unhealthy'].includes(s)) map.critical++;
      else if (['offline','stopped','terminated'].includes(s))        map.offline++;
      else                                                             map.unknown++;
    }
    return Object.entries(map).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }));
  }, [clusters, assets]);

  // Cluster utilisation
  const clusterUtil = useMemo(() =>
    clusters
      .filter((c: any) => c.cpu_usage_pct != null || c.memory_usage_pct != null)
      .slice(0, 8)
      .map((c: any) => ({
        name:    (c.name ?? c.id ?? '?').slice(0, 14),
        cpu:     Math.round(c.cpu_usage_pct    ?? 0),
        memory:  Math.round(c.memory_usage_pct ?? 0),
        nodes:   c.node_count ?? 0,
      })),
    [clusters],
  );

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
      </div>
    );
  }

  const noData = assets.length === 0 && clusters.length === 0;
  if (noData) {
    return (
      <div className="card-base py-10 text-center">
        <BarChart3 className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-30" />
        <p className="text-sm font-medium text-foreground">No chart data available</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Connect infrastructure providers to populate analytics</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      {/* Resources by Cloud */}
      {byCloud.length > 0 && (
        <ChartCard title="Resources by Cloud">
          <div className="flex items-center gap-3">
            <ResponsiveContainer width={100} height={100}>
              <PieChart>
                <Pie data={byCloud} dataKey="value" cx="50%" cy="50%"
                  innerRadius={28} outerRadius={46} paddingAngle={2} strokeWidth={0}>
                  {byCloud.map(e => <Cell key={e.name} fill={CLOUD_COLORS[e.name] ?? '#475569'} />)}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-1.5 flex-1">
              {byCloud.map(e => (
                <div key={e.name} className="flex items-center justify-between text-[10px]">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: CLOUD_COLORS[e.name] ?? '#475569' }} />
                    <span className="text-muted-foreground uppercase">{e.name}</span>
                  </div>
                  <span className="font-bold text-foreground">{e.value}</span>
                </div>
              ))}
            </div>
          </div>
        </ChartCard>
      )}

      {/* Resources by Region */}
      {byRegion.length > 0 && (
        <ChartCard title="Resources by Region">
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={byRegion.slice(0, 6)} layout="vertical" margin={{ left: 55, right: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
              <XAxis type="number" tick={TICK} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ ...TICK, fontSize: 9 }} width={60} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [v, 'Assets']} />
              <Bar dataKey="value" fill="#3b82f6" fillOpacity={0.8} radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {/* Resources by Environment */}
      {byEnv.length > 0 && (
        <ChartCard title="Resources by Environment">
          <div className="flex items-center gap-3">
            <ResponsiveContainer width={100} height={100}>
              <PieChart>
                <Pie data={byEnv} dataKey="value" cx="50%" cy="50%"
                  innerRadius={28} outerRadius={46} paddingAngle={2} strokeWidth={0}>
                  {byEnv.map(e => <Cell key={e.name} fill={ENV_COLORS[e.name] ?? '#475569'} />)}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-1.5 flex-1">
              {byEnv.map(e => (
                <div key={e.name} className="flex items-center justify-between text-[10px]">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: ENV_COLORS[e.name] ?? '#475569' }} />
                    <span className="text-muted-foreground capitalize">{e.name}</span>
                  </div>
                  <span className="font-bold text-foreground">{e.value}</span>
                </div>
              ))}
            </div>
          </div>
        </ChartCard>
      )}

      {/* Infrastructure Health Donut */}
      {healthData.length > 0 && (
        <ChartCard title="Infrastructure Health">
          <div className="flex items-center gap-3">
            <ResponsiveContainer width={100} height={100}>
              <PieChart>
                <Pie data={healthData} dataKey="value" cx="50%" cy="50%"
                  innerRadius={28} outerRadius={46} paddingAngle={2} strokeWidth={0}>
                  {healthData.map(e => <Cell key={e.name} fill={HEALTH_COLORS[e.name] ?? '#475569'} />)}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-1.5 flex-1">
              {healthData.map(e => (
                <div key={e.name} className="flex items-center justify-between text-[10px]">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: HEALTH_COLORS[e.name] ?? '#475569' }} />
                    <span className="text-muted-foreground capitalize">{e.name}</span>
                  </div>
                  <span className="font-bold text-foreground">{e.value}</span>
                </div>
              ))}
            </div>
          </div>
        </ChartCard>
      )}

      {/* Cluster Utilisation */}
      {clusterUtil.length > 0 && (
        <ChartCard title="Cluster CPU / Memory Usage">
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={clusterUtil} margin={{ left: -20, right: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis dataKey="name" tick={{ ...TICK, fontSize: 8 }} />
              <YAxis domain={[0, 100]} tick={TICK} unit="%" />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any, n: string) => [`${v}%`, n === 'cpu' ? 'CPU' : 'Memory']} />
              <Bar dataKey="cpu"    fill="#3b82f6" fillOpacity={0.9} radius={[2, 2, 0, 0]} maxBarSize={10} />
              <Bar dataKey="memory" fill="#8b5cf6" fillOpacity={0.9} radius={[2, 2, 0, 0]} maxBarSize={10} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {/* Assets by Type */}
      {byType.length > 0 && (
        <ChartCard title="Assets by Type">
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={byType.slice(0, 6)} layout="vertical" margin={{ left: 65, right: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
              <XAxis type="number" tick={TICK} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ ...TICK, fontSize: 9 }} width={70} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [v, 'Assets']} />
              <Bar dataKey="value" fill="#22c55e" fillOpacity={0.8} radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}
    </div>
  );
}

export default memo(InfraCharts);
