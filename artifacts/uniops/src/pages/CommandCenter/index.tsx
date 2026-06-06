import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Activity, Shield, DollarSign, Brain, Server,
  CheckCircle, Clock, RefreshCw, GitBranch,
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';

interface Stats {
  services_running?: number;
  active_threats?: number;
  monthly_spend?: number;
  ml_patterns?: number;
  pods?: { running?: number; pending?: number; failed?: number };
}

const HEALTH_COLORS = ['#10b981', '#f59e0b', '#ef4444'];

export default function CommandCenter() {
  const [now, setNow] = useState(new Date());

  const { data: threatStats, loading: tLoading, refetch: refetchT } = useApi<any>('/threats/stats');
  const { data: costSummary, loading: cLoading, refetch: refetchC }  = useApi<any>('/costs/summary');
  const { data: podStats,    loading: pLoading, refetch: refetchP }  = useApi<any>('/kubernetes/pods/stats');
  const { data: mlStats,     loading: mLoading, refetch: refetchM }  = useApi<any>('/ml/stats');
  const { data: alerts,      refetch: refetchA }                     = useApi<any>('/alerts?page_size=5');

  const isRefreshing = tLoading || cLoading || pLoading || mLoading;

  const handleRefresh = useCallback(() => {
    refetchT(true); refetchC(true); refetchP(true); refetchM(true); refetchA(true);
    setNow(new Date());
  }, [refetchT, refetchC, refetchP, refetchM, refetchA]);

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  const runningPods  = podStats?.running  ?? 0;
  const pendingPods  = podStats?.pending  ?? 0;
  const failedPods   = podStats?.failed   ?? 0;
  const totalPods    = podStats?.total    ?? 0;

  const healthData = [
    { name: 'Running', value: runningPods, color: '#10b981' },
    { name: 'Pending', value: pendingPods, color: '#f59e0b' },
    { name: 'Failed',  value: failedPods,  color: '#ef4444' },
  ].filter(d => d.value > 0);

  const summaryCards = [
    {
      title: 'Pods Running',
      value: totalPods ? `${runningPods}/${totalPods}` : '—',
      sub: failedPods > 0 ? `${failedPods} failed` : 'All healthy',
      icon: Server,
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
    },
    {
      title: 'Active Threats',
      value: threatStats?.active ?? '—',
      sub: `${threatStats?.critical ?? 0} critical`,
      icon: Shield,
      color: 'text-red-400',
      bg: 'bg-red-500/10',
    },
    {
      title: 'Monthly Spend',
      value: costSummary?.mtd != null ? `$${(costSummary.mtd / 1000).toFixed(1)}k` : '—',
      sub: costSummary?.trend_pct != null ? `${costSummary.trend_pct > 0 ? '+' : ''}${costSummary.trend_pct.toFixed(0)}% vs last month` : '',
      icon: DollarSign,
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
    },
    {
      title: 'ML Patterns',
      value: mlStats?.patterns_found ?? '—',
      sub: mlStats?.accuracy != null ? `${mlStats.accuracy}% accuracy` : '',
      icon: Brain,
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
    },
  ];

  const recentEvents = (Array.isArray(alerts) ? alerts : alerts?.data) ?? [];

  const eventColors: Record<string, string> = {
    critical: 'text-red-400', high: 'text-red-400',
    warning: 'text-yellow-400', medium: 'text-yellow-400',
    info: 'text-blue-400', low: 'text-blue-400', success: 'text-green-400',
  };
  const eventBg: Record<string, string> = {
    critical: 'bg-red-500/10', high: 'bg-red-500/10',
    warning: 'bg-yellow-500/10', medium: 'bg-yellow-500/10',
    info: 'bg-blue-500/10', low: 'bg-blue-500/10', success: 'bg-green-500/10',
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Command Center</h1>
          <p className="page-subtitle">Unified operational intelligence — {now.toLocaleTimeString('en-US', { hour12: true })}</p>
        </div>
        <button onClick={handleRefresh} className="action-btn" disabled={isRefreshing}>
          <RefreshCw className={clsx('w-4 h-4', isRefreshing && 'animate-spin')} />
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {summaryCards.map((card, i) => (
          <motion.div key={card.title} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }} className="card-base flex items-start gap-4">
            <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0', card.bg)}>
              <card.icon className={clsx('w-5 h-5', card.color)} />
            </div>
            <div>
              <div className="stat-value">{card.value}</div>
              <div className="stat-label">{card.title}</div>
              <div className="text-xs mt-0.5 text-muted-foreground">{card.sub}</div>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4">
        <div className="xl:col-span-2 card-base">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-foreground">Pod Health Distribution</h2>
          </div>
          {healthData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={healthData} cx="50%" cy="50%" outerRadius={80} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine={false}>
                  {healthData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: 'hsl(230 18% 10%)', border: '1px solid hsl(230 15% 14%)', borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
              {pLoading ? 'Loading pod data...' : 'No pod data — connect a Kubernetes cluster'}
            </div>
          )}
        </div>

        <div className="card-base flex flex-col">
          <h2 className="text-sm font-semibold text-foreground mb-4">Pod Status</h2>
          <div className="space-y-3">
            {[
              { label: 'Running', value: runningPods, color: '#10b981' },
              { label: 'Pending', value: pendingPods, color: '#f59e0b' },
              { label: 'Failed',  value: failedPods,  color: '#ef4444' },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ background: item.color }} />
                  <span className="text-muted-foreground">{item.label}</span>
                </div>
                <span className="font-medium text-foreground">{item.value}</span>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-4 border-t border-border space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Total threats</span>
              <span className="font-medium">{threatStats?.total ?? '—'}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Critical</span>
              <span className="font-medium text-red-400">{threatStats?.critical ?? '—'}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Monthly forecast</span>
              <span className="font-medium">{costSummary?.forecast != null ? `$${(costSummary.forecast / 1000).toFixed(1)}k` : '—'}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="card-base">
        <h2 className="text-sm font-semibold text-foreground mb-4">Recent Alerts</h2>
        {recentEvents.length > 0 ? (
          <div className="space-y-2">
            {recentEvents.map((event: any, i: number) => (
              <div key={event.id ?? i} className="flex items-start gap-3 p-3 rounded-lg bg-surface-1 border border-border/50">
                <div className={clsx('w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5', eventBg[event.severity ?? 'info'])}>
                  <Activity className={clsx('w-3.5 h-3.5', eventColors[event.severity ?? 'info'])} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-foreground leading-tight">{event.message ?? event.title}</p>
                  <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    {event.created_at ? new Date(event.created_at).toLocaleTimeString() : ''}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {tLoading ? 'Loading alerts...' : 'No recent alerts'}
          </p>
        )}
      </div>
    </motion.div>
  );
}
