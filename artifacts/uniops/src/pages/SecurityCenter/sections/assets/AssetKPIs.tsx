import { memo } from 'react';
import { clsx } from 'clsx';
import { motion } from 'framer-motion';
import {
  Server, ShieldAlert, Globe, HelpCircle,
  TrendingUp, Clock, Percent, BarChart3, Activity,
} from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

interface KpiDef {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  iconBg: string;
  valueColor?: string;
  alarm?: boolean;
}

interface AssetKPIsProps {
  stats: any;
  loading: boolean;
}

function AssetKPIs({ stats, loading }: AssetKPIsProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-3">
        {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
      </div>
    );
  }

  const s = (stats ?? {}) as any;

  const total             = s.total            ?? 0;
  const critical          = s.by_risk?.critical ?? s.critical          ?? 0;
  const high              = s.by_risk?.high     ?? s.high              ?? 0;
  const internetExposed   = s.internet_exposed  ?? s.exposed           ?? '—';
  const unmanaged         = s.unmanaged         ?? '—';
  const recentlyDisc      = s.recently_discovered ?? s.recent_count    ?? '—';
  const coveragePct       = s.coverage_pct      ?? s.scanned_pct       ?? s.scan_coverage ?? null;
  const avgRiskScore      = s.avg_risk_score    ?? s.average_risk_score ?? s.mean_risk     ?? null;

  const kpis: KpiDef[] = [
    {
      label: 'Total Assets',
      value: total.toLocaleString(),
      sub: `across ${Object.keys(s.by_source ?? {}).length || '—'} sources`,
      icon: <Server className="w-4 h-4 text-blue-400" />,
      iconBg: 'bg-blue-500/10',
    },
    {
      label: 'Critical Assets',
      value: critical,
      sub: total > 0 ? `${((critical / total) * 100).toFixed(1)}% of total` : undefined,
      icon: <ShieldAlert className="w-4 h-4 text-red-400" />,
      iconBg: 'bg-red-500/10',
      valueColor: critical > 0 ? 'text-red-400' : undefined,
      alarm: critical > 0,
    },
    {
      label: 'Internet Exposed',
      value: internetExposed,
      sub: 'publicly reachable',
      icon: <Globe className="w-4 h-4 text-orange-400" />,
      iconBg: 'bg-orange-500/10',
      valueColor: typeof internetExposed === 'number' && internetExposed > 0 ? 'text-orange-400' : undefined,
    },
    {
      label: 'Unmanaged Assets',
      value: unmanaged,
      sub: 'no owner assigned',
      icon: <HelpCircle className="w-4 h-4 text-yellow-400" />,
      iconBg: 'bg-yellow-500/10',
      valueColor: typeof unmanaged === 'number' && unmanaged > 0 ? 'text-yellow-400' : undefined,
    },
    {
      label: 'High Risk Assets',
      value: high,
      sub: total > 0 ? `${((high / total) * 100).toFixed(1)}% of total` : undefined,
      icon: <TrendingUp className="w-4 h-4 text-orange-400" />,
      iconBg: 'bg-orange-500/10',
      valueColor: high > 0 ? 'text-orange-400' : undefined,
    },
    {
      label: 'Recently Discovered',
      value: recentlyDisc,
      sub: 'last 24 hours',
      icon: <Clock className="w-4 h-4 text-purple-400" />,
      iconBg: 'bg-purple-500/10',
    },
    {
      label: 'Asset Coverage',
      value: coveragePct != null ? `${Math.round(coveragePct)}%` : '—',
      sub: 'scanned assets',
      icon: <Percent className="w-4 h-4 text-green-400" />,
      iconBg: 'bg-green-500/10',
      valueColor: coveragePct != null && coveragePct < 80 ? 'text-yellow-400' : 'text-green-400',
    },
    {
      label: 'Avg Risk Score',
      value: avgRiskScore != null ? Math.round(avgRiskScore) : '—',
      sub: 'out of 100',
      icon: <BarChart3 className="w-4 h-4 text-cyan-400" />,
      iconBg: 'bg-cyan-500/10',
      valueColor:
        avgRiskScore != null
          ? avgRiskScore >= 80 ? 'text-red-400'
          : avgRiskScore >= 60 ? 'text-orange-400'
          : avgRiskScore >= 40 ? 'text-yellow-400'
          : 'text-green-400'
          : undefined,
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-3">
      {kpis.map((k, i) => (
        <motion.div key={k.label}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04 }}
          className={clsx(
            'card-base p-4 border',
            k.alarm ? 'border-red-500/20 bg-red-500/4' : 'border-transparent',
          )}
        >
          <div className="flex items-start justify-between mb-2">
            <div className={clsx('w-7 h-7 rounded-lg flex items-center justify-center', k.iconBg)}>
              {k.icon}
            </div>
            {k.alarm && <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />}
          </div>
          <p className={clsx('text-xl font-bold leading-none', k.valueColor ?? 'text-foreground')}>
            {k.value}
          </p>
          <p className="text-[10px] font-medium text-foreground mt-1 leading-tight">{k.label}</p>
          {k.sub && <p className="text-[9px] text-muted-foreground/70 mt-0.5">{k.sub}</p>}
        </motion.div>
      ))}
    </div>
  );
}

export default memo(AssetKPIs);
