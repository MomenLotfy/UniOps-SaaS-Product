import { memo } from 'react';
import { clsx } from 'clsx';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area,
} from 'recharts';
import { DollarSign, TrendingUp } from 'lucide-react';

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

function fmtCurrency(v?: number) {
  if (v == null) return '—';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000)     return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(2)}`;
}

interface InfraCostProps {
  costSummary:   any | null;
  costBreakdown: any | null;
  loading: boolean;
}

function InfraCost({ costSummary, costBreakdown, loading }: InfraCostProps) {
  const cs = costSummary   ?? {};
  const cb = costBreakdown ?? {};

  const hasCostData = cs.total_cost != null || cs.current_month != null || cs.mtd != null;

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-36 rounded" />
        <div className="grid grid-cols-3 gap-3">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      </div>
    );
  }

  if (!hasCostData) return null; // Don't render if backend has no billing data

  const currentSpend = cs.total_cost ?? cs.current_month ?? cs.mtd ?? 0;
  const forecast     = cs.forecast   ?? cs.projected     ?? null;
  const byService    = Array.isArray(cb.by_service)  ? cb.by_service.slice(0, 6)  : [];
  const byAccount    = Array.isArray(cb.by_account)  ? cb.by_account.slice(0, 6)  : [];
  const trend        = Array.isArray(cs.monthly_trend) ? cs.monthly_trend : [];

  const trendChange = cs.trend_pct ?? cs.change_pct ?? null;

  return (
    <div className="space-y-4">
      <p className="text-sm font-semibold text-foreground flex items-center gap-2">
        <DollarSign className="w-4 h-4 text-green-400" />
        Cloud Cost Overview
      </p>

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="card-base p-4 border border-green-500/20 bg-green-500/5">
          <p className="text-xs text-muted-foreground mb-1">Current Spend</p>
          <p className="text-2xl font-bold text-green-400">{fmtCurrency(currentSpend)}</p>
          {trendChange != null && (
            <div className="flex items-center gap-1 mt-1">
              <TrendingUp className={clsx('w-3 h-3', trendChange > 0 ? 'text-red-400' : 'text-green-400')} />
              <span className={clsx('text-[10px] font-medium', trendChange > 0 ? 'text-red-400' : 'text-green-400')}>
                {trendChange > 0 ? '+' : ''}{trendChange.toFixed(1)}% vs last month
              </span>
            </div>
          )}
        </div>
        {forecast != null && (
          <div className="card-base p-4">
            <p className="text-xs text-muted-foreground mb-1">Month Forecast</p>
            <p className="text-2xl font-bold text-blue-400">{fmtCurrency(forecast)}</p>
            <p className="text-[10px] text-muted-foreground mt-1">Projected end-of-month</p>
          </div>
        )}
        {cs.savings != null && (
          <div className="card-base p-4">
            <p className="text-xs text-muted-foreground mb-1">Potential Savings</p>
            <p className="text-2xl font-bold text-yellow-400">{fmtCurrency(cs.savings)}</p>
            <p className="text-[10px] text-muted-foreground mt-1">Identified optimisations</p>
          </div>
        )}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {trend.length > 1 && (
          <div className="card-base p-4">
            <p className="text-xs text-muted-foreground mb-3 uppercase tracking-wide">Monthly Trend</p>
            <ResponsiveContainer width="100%" height={100}>
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="month" tick={{ ...TICK, fontSize: 9 }} />
                <YAxis tick={TICK} tickFormatter={fmtCurrency} width={48} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [fmtCurrency(v), 'Cost']} />
                <Area type="monotone" dataKey="cost" stroke="#22c55e" fill="url(#costGrad)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {byService.length > 0 && (
          <div className="card-base p-4">
            <p className="text-xs text-muted-foreground mb-3 uppercase tracking-wide">Top Services</p>
            <ResponsiveContainer width="100%" height={100}>
              <BarChart data={byService} layout="vertical" margin={{ left: 50, right: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
                <XAxis type="number" tick={TICK} tickFormatter={fmtCurrency} />
                <YAxis type="category" dataKey="service" tick={{ ...TICK, fontSize: 9 }} width={55} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [fmtCurrency(v), 'Cost']} />
                <Bar dataKey="cost" fill="#3b82f6" fillOpacity={0.8} radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {byAccount.length > 0 && (
          <div className="card-base p-4">
            <p className="text-xs text-muted-foreground mb-3 uppercase tracking-wide">Top Accounts</p>
            <ResponsiveContainer width="100%" height={100}>
              <BarChart data={byAccount} layout="vertical" margin={{ left: 50, right: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
                <XAxis type="number" tick={TICK} tickFormatter={fmtCurrency} />
                <YAxis type="category" dataKey="account" tick={{ ...TICK, fontSize: 9 }} width={55} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [fmtCurrency(v), 'Cost']} />
                <Bar dataKey="cost" fill="#f97316" fillOpacity={0.8} radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(InfraCost);
