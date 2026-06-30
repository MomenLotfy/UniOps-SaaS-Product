import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import { BarChart3 } from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const TOOLTIP = {
  background: 'hsl(230 15% 10%)',
  border: '1px solid hsl(230 15% 18%)',
  borderRadius: 8,
  fontSize: 11,
};
const TICK  = { fill: 'hsl(215 16% 45%)', fontSize: 10 };
const GRID  = 'hsl(230 15% 16%)';

const RISK_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#3b82f6',
  none:     '#22c55e',
  unknown:  '#475569',
};

const SOURCE_COLORS: Record<string, string> = {
  github:     '#8b5cf6',
  gitlab:     '#f97316',
  aws:        '#f97316',
  azure:      '#3b82f6',
  gcp:        '#22c55e',
  kubernetes: '#06b6d4',
  docker:     '#2563eb',
  unknown:    '#475569',
};

const ENV_COLORS: Record<string, string> = {
  production:  '#ef4444',
  staging:     '#f97316',
  development: '#3b82f6',
  test:        '#8b5cf6',
  unknown:     '#475569',
};

const TYPE_COLORS = [
  '#3b82f6','#8b5cf6','#22c55e','#f97316','#06b6d4',
  '#eab308','#ec4899','#14b8a6','#a855f7','#64748b',
];

function groupBy(items: any[], key: string): Array<{ name: string; value: number }> {
  const map = new Map<string, number>();
  for (const item of items) {
    const k = (item[key] ?? 'unknown').toLowerCase();
    map.set(k, (map.get(k) ?? 0) + 1);
  }
  return Array.from(map.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);
}

function PieLegend({ data, colors }: { data: Array<{ name: string; value: number }>; colors: (n: string, i: number) => string }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div className="space-y-1.5 flex-1">
      {data.slice(0, 6).map((d, i) => (
        <div key={d.name} className="flex items-center justify-between text-[10px]">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: colors(d.name, i) }} />
            <span className="text-muted-foreground capitalize truncate">{d.name}</span>
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
            <span className="font-bold text-foreground">{d.value}</span>
            {total > 0 && (
              <span className="text-muted-foreground/50">{((d.value / total) * 100).toFixed(0)}%</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

interface ChartCardProps { title: string; children: React.ReactNode }
function ChartCard({ title, children }: ChartCardProps) {
  return (
    <div className="card-base p-4">
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-3">{title}</p>
      {children}
    </div>
  );
}

interface AssetChartsProps {
  assets: any[];
  stats: any;
  loading: boolean;
}

function AssetCharts({ assets, stats, loading }: AssetChartsProps) {
  const byRisk = useMemo(() => {
    const s = (stats ?? {}) as any;
    if (s.by_risk && Object.keys(s.by_risk).length > 0) {
      return Object.entries(s.by_risk)
        .map(([name, value]) => ({ name, value: value as number }))
        .filter(d => d.value > 0)
        .sort((a, b) => b.value - a.value);
    }
    return groupBy(assets, 'risk_level');
  }, [assets, stats]);

  const bySource = useMemo(() => {
    const s = (stats ?? {}) as any;
    if (s.by_source && Object.keys(s.by_source).length > 0) {
      return Object.entries(s.by_source)
        .map(([name, value]) => ({ name, value: value as number }))
        .filter(d => d.value > 0)
        .sort((a, b) => b.value - a.value);
    }
    return groupBy(assets, 'source');
  }, [assets, stats]);

  const byEnv  = useMemo(() => groupBy(assets, 'environment'), [assets]);
  const byType = useMemo(() => groupBy(assets, 'type'),        [assets]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-[140px] rounded-xl" />)}
      </div>
    );
  }

  if (assets.length === 0 && !stats) {
    return (
      <div className="card-base py-8 text-center">
        <BarChart3 className="w-7 h-7 text-muted-foreground mx-auto mb-2 opacity-30" />
        <p className="text-xs text-muted-foreground">No data for charts</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
      {/* Assets by Risk */}
      {byRisk.length > 0 && (
        <ChartCard title="Assets by Risk">
          <div className="flex items-center gap-3">
            <ResponsiveContainer width={86} height={86}>
              <PieChart>
                <Pie data={byRisk} dataKey="value" cx="50%" cy="50%"
                  innerRadius={24} outerRadius={40} paddingAngle={2} strokeWidth={0}>
                  {byRisk.map((e, i) => <Cell key={i} fill={RISK_COLORS[e.name] ?? '#475569'} />)}
                </Pie>
                <Tooltip contentStyle={TOOLTIP} />
              </PieChart>
            </ResponsiveContainer>
            <PieLegend data={byRisk} colors={(n) => RISK_COLORS[n] ?? '#475569'} />
          </div>
        </ChartCard>
      )}

      {/* Assets by Cloud */}
      {bySource.length > 0 && (
        <ChartCard title="Assets by Cloud">
          <div className="flex items-center gap-3">
            <ResponsiveContainer width={86} height={86}>
              <PieChart>
                <Pie data={bySource} dataKey="value" cx="50%" cy="50%"
                  innerRadius={24} outerRadius={40} paddingAngle={2} strokeWidth={0}>
                  {bySource.map((e, i) => <Cell key={i} fill={SOURCE_COLORS[e.name] ?? TYPE_COLORS[i % TYPE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={TOOLTIP} />
              </PieChart>
            </ResponsiveContainer>
            <PieLegend data={bySource} colors={(n, i) => SOURCE_COLORS[n] ?? TYPE_COLORS[i % TYPE_COLORS.length]} />
          </div>
        </ChartCard>
      )}

      {/* Assets by Environment */}
      {byEnv.length > 0 && (
        <ChartCard title="Assets by Environment">
          <div className="flex items-center gap-3">
            <ResponsiveContainer width={86} height={86}>
              <PieChart>
                <Pie data={byEnv} dataKey="value" cx="50%" cy="50%"
                  innerRadius={24} outerRadius={40} paddingAngle={2} strokeWidth={0}>
                  {byEnv.map((e, i) => <Cell key={i} fill={ENV_COLORS[e.name] ?? TYPE_COLORS[i % TYPE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={TOOLTIP} />
              </PieChart>
            </ResponsiveContainer>
            <PieLegend data={byEnv} colors={(n, i) => ENV_COLORS[n] ?? TYPE_COLORS[i % TYPE_COLORS.length]} />
          </div>
        </ChartCard>
      )}

      {/* Assets by Type */}
      {byType.length > 0 && (
        <ChartCard title="Assets by Type">
          <ResponsiveContainer width="100%" height={86}>
            <BarChart data={byType.slice(0, 5)} layout="vertical" margin={{ left: 60, right: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
              <XAxis type="number" tick={TICK} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ ...TICK, fontSize: 9 }} width={65} />
              <Tooltip contentStyle={TOOLTIP} formatter={(v: any) => [v, 'Assets']} />
              <Bar dataKey="value" radius={[0, 3, 3, 0]} maxBarSize={10}>
                {byType.slice(0, 5).map((_, i) => (
                  <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}
    </div>
  );
}

export default memo(AssetCharts);
