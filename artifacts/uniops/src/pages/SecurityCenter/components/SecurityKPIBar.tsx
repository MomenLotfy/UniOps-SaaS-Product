import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts';
import {
  TrendingUp, TrendingDown, Minus,
  GitBranch, Cloud, Layers, Server,
  Bug, AlertTriangle, Wrench, BookOpen,
  CheckSquare, Shield, Clock, Eye,
} from 'lucide-react';
import { useApi } from '@/hooks/use-api';
import type { SecuritySection } from '../index';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/8', className)} />;
}

const COLOR_MAP = {
  red:    { text: 'text-red-400',    bg: 'bg-red-500/15',    border: 'border-red-500/25',    icon: 'text-red-400',    spark: '#ef4444' },
  orange: { text: 'text-orange-400', bg: 'bg-orange-500/15', border: 'border-orange-500/25', icon: 'text-orange-400', spark: '#f97316' },
  yellow: { text: 'text-yellow-400', bg: 'bg-yellow-500/15', border: 'border-yellow-500/25', icon: 'text-yellow-400', spark: '#eab308' },
  green:  { text: 'text-green-400',  bg: 'bg-green-500/15',  border: 'border-green-500/25',  icon: 'text-green-400',  spark: '#22c55e' },
  blue:   { text: 'text-blue-400',   bg: 'bg-blue-500/15',   border: 'border-blue-500/25',   icon: 'text-blue-400',   spark: '#3b82f6' },
  purple: { text: 'text-purple-400', bg: 'bg-purple-500/15', border: 'border-purple-500/25', icon: 'text-purple-400', spark: '#a855f7' },
  muted:  { text: 'text-muted-foreground', bg: 'bg-white/5', border: 'border-white/10',      icon: 'text-muted-foreground', spark: '#64748b' },
} as const;

type ColorKey = keyof typeof COLOR_MAP;

interface KPICardProps {
  label: string;
  value: string | number | undefined;
  loading: boolean;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  color: ColorKey;
  icon: React.ElementType;
  sparkData?: { v: number }[];
  onClick?: () => void;
  trendIsGood?: boolean;
}

function KPICard({
  label, value, loading, trend, trendLabel,
  color, icon: Icon, sparkData, onClick, trendIsGood,
}: KPICardProps) {
  const c = COLOR_MAP[color];

  const trendColor =
    trend === 'neutral' ? 'text-muted-foreground'
    : trend === 'up' && trendIsGood  ? 'text-green-400'
    : trend === 'up' && !trendIsGood ? 'text-red-400'
    : trend === 'down' && trendIsGood  ? 'text-green-400'
    : 'text-red-400';

  const TrendIcon =
    trend === 'up' ? TrendingUp
    : trend === 'down' ? TrendingDown
    : Minus;

  return (
    <button
      onClick={onClick}
      className={clsx(
        'relative flex flex-col justify-between p-3 rounded-xl border transition-all duration-150 text-left group min-w-0',
        'hover:scale-[1.01] hover:shadow-lg',
        c.border,
        c.bg,
      )}
      style={{ minHeight: 88 }}
    >
      {/* Top row: icon + label */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <Icon className={clsx('w-3.5 h-3.5 flex-shrink-0', c.icon)} />
          <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide truncate">
            {label}
          </span>
        </div>
        {sparkData && sparkData.length > 1 && (
          <div className="w-14 h-6 flex-shrink-0 opacity-60 group-hover:opacity-100 transition-opacity">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sparkData}>
                <Line
                  type="monotone"
                  dataKey="v"
                  stroke={c.spark}
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
                <Tooltip
                  contentStyle={{ display: 'none' }}
                  wrapperStyle={{ display: 'none' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Value */}
      <div className="flex items-end gap-2">
        {loading ? (
          <Skeleton className="h-6 w-12" />
        ) : (
          <span className={clsx('text-xl font-bold leading-none tabular-nums', c.text)}>
            {value ?? '—'}
          </span>
        )}
        {!loading && trend && trendLabel && (
          <span className={clsx('flex items-center gap-0.5 text-[10px] font-medium mb-0.5', trendColor)}>
            <TrendIcon className="w-3 h-3" />
            {trendLabel}
          </span>
        )}
      </div>
    </button>
  );
}

interface SecurityKPIBarProps {
  onNavigate: (section: SecuritySection) => void;
}

function SecurityKPIBar({ onNavigate }: SecurityKPIBarProps) {
  const { data: postureRaw, loading: postureLoading } = useApi<any>('/security-posture/summary');
  const { data: vulnRaw,    loading: vulnLoading }    = useApi<any>('/vulnerabilities/stats');
  const { data: policyRaw,  loading: policyLoading }  = useApi<any>('/security-policies/stats');
  const { data: threatRaw,  loading: threatLoading }  = useApi<any>('/threats/stats');
  const { data: reposRaw,   loading: reposLoading }   = useApi<any>('/security/repos');
  const { data: clustersRaw, loading: clustersLoading } = useApi<any>('/clusters');
  const { data: assetsRaw,  loading: assetsLoading }  = useApi<any>('/assets');
  const { data: exRaw,      loading: exLoading }      = useApi<any>('/security-exceptions/stats');

  const ps    = postureRaw?.data ?? postureRaw;
  const vs    = vulnRaw?.data    ?? vulnRaw;
  const pol   = policyRaw?.data  ?? policyRaw;
  const ts    = threatRaw?.data  ?? threatRaw;
  const repos = Array.isArray(reposRaw) ? reposRaw : (reposRaw?.data ?? reposRaw?.items ?? []);
  const clusters = useMemo(() => {
    const raw = clustersRaw?.data ?? clustersRaw;
    return Array.isArray(raw) ? raw : (raw?.items ?? []);
  }, [clustersRaw]);
  const assets = useMemo(() => {
    const raw = assetsRaw?.data ?? assetsRaw;
    return Array.isArray(raw) ? raw : (raw?.items ?? []);
  }, [assetsRaw]);

  const history: { v: number }[] = useMemo(() =>
    (ps?.history ?? []).slice(-12).map((h: any) => ({ v: Math.round(h.overall ?? 0) })),
    [ps],
  );

  const kpis: KPICardProps[] = [
    {
      label: 'Repositories',
      value: reposLoading ? undefined : repos.length,
      loading: reposLoading,
      color: 'blue',
      icon: GitBranch,
      trend: 'neutral',
      onClick: () => onNavigate('repositories'),
    },
    {
      label: 'Cloud Accounts',
      value: undefined,
      loading: true,
      color: 'muted',
      icon: Cloud,
      trend: 'neutral',
    },
    {
      label: 'Clusters',
      value: clustersLoading ? undefined : clusters.length,
      loading: clustersLoading,
      color: 'purple',
      icon: Layers,
      trend: 'neutral',
      onClick: () => onNavigate('kubernetes'),
    },
    {
      label: 'Assets',
      value: assetsLoading ? undefined : assets.length,
      loading: assetsLoading,
      color: 'blue',
      icon: Server,
      trend: 'neutral',
      onClick: () => onNavigate('assets'),
    },
    {
      label: 'Critical Vulns',
      value: vulnLoading ? undefined : (vs?.critical ?? vs?.by_severity?.critical ?? '—'),
      loading: vulnLoading,
      color: 'red',
      icon: Bug,
      trend: 'neutral',
      onClick: () => onNavigate('vulnerabilities'),
    },
    {
      label: 'High Vulns',
      value: vulnLoading ? undefined : (vs?.high ?? vs?.by_severity?.high ?? '—'),
      loading: vulnLoading,
      color: 'orange',
      icon: Bug,
      trend: 'neutral',
      onClick: () => onNavigate('vulnerabilities'),
    },
    {
      label: 'Open Remediations',
      value: postureLoading ? undefined : (ps?.open_remediations ?? ps?.breakdown?.threats?.open ?? '—'),
      loading: postureLoading,
      color: 'orange',
      icon: Wrench,
      trend: 'neutral',
      onClick: () => onNavigate('remediation'),
    },
    {
      label: 'Failed Policies',
      value: policyLoading ? undefined : (pol?.violations_count ?? '—'),
      loading: policyLoading,
      color: 'red',
      icon: BookOpen,
      trend: 'neutral',
      onClick: () => onNavigate('policies'),
    },
    {
      label: 'Compliance Score',
      value: postureLoading ? undefined : (ps?.compliance_score != null ? `${Math.round(ps.compliance_score)}%` : '—'),
      loading: postureLoading,
      color: ps?.compliance_score >= 80 ? 'green' : ps?.compliance_score >= 60 ? 'yellow' : 'red',
      icon: CheckSquare,
      sparkData: history,
      trend: 'neutral',
      onClick: () => onNavigate('compliance'),
    },
    {
      label: 'Risk Score',
      value: postureLoading ? undefined : (ps?.current_score != null ? Math.round(ps.current_score) : '—'),
      loading: postureLoading,
      color: ps?.current_score >= 80 ? 'green' : ps?.current_score >= 60 ? 'yellow' : 'red',
      icon: Shield,
      sparkData: history,
      trend: ps?.trend === 'improving' ? 'up' : ps?.trend === 'degrading' ? 'down' : 'neutral',
      trendLabel: ps?.trend ?? undefined,
      trendIsGood: ps?.trend === 'improving',
      onClick: () => onNavigate('posture'),
    },
    {
      label: 'MTTR',
      value: threatLoading ? undefined : (ts?.mttr_hours != null ? `${ts.mttr_hours}h` : '—'),
      loading: threatLoading,
      color: 'muted',
      icon: Clock,
      trend: 'neutral',
      onClick: () => onNavigate('threats'),
    },
    {
      label: 'MTTD',
      value: threatLoading ? undefined : (ts?.mttd_hours != null ? `${ts.mttd_hours}h` : '—'),
      loading: threatLoading,
      color: 'muted',
      icon: Eye,
      trend: 'neutral',
      onClick: () => onNavigate('threats'),
    },
  ];

  return (
    <div
      className="flex-shrink-0 px-4 py-3 border-b overflow-x-auto"
      style={{ borderColor: 'hsl(230 15% 14%)' }}
    >
      <div
        className="grid gap-2"
        style={{
          gridTemplateColumns: 'repeat(12, minmax(90px, 1fr))',
          minWidth: 'max-content',
          width: '100%',
        }}
      >
        {kpis.map((kpi, i) => (
          <KPICard key={i} {...kpi} />
        ))}
      </div>
    </div>
  );
}

export default memo(SecurityKPIBar);
