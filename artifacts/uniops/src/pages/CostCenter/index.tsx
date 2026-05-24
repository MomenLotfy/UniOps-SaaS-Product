import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  DollarSign, TrendingUp, TrendingDown, AlertTriangle,
  Lightbulb, RefreshCw, Cloud, Zap, CheckCircle,
  Loader2, ShieldAlert, BarChart2, ChevronUp, ChevronDown,
  Clock,
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import { clsx } from 'clsx';
import { useWebSocket } from '@/contexts/WebSocketContext';
import {
  useCostSummary, useCostBreakdown, useCostForecast,
  useCostAnomalies, useSavings,
  useInvestigateAnomaly, useResolveAnomaly, useDismissAnomaly,
  useApplySaving, useDismissSaving,
  useInvalidateAllCostData, useTriggerCostSync,
} from '@/hooks/useCostData';

// ─── Types ────────────────────────────────────────────────────────────────────
type Tab = 'overview' | 'services' | 'forecast' | 'savings' | 'anomalies';

const COLORS = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#06b6d4','#ec4899','#f97316','#84cc16'];

const SEVERITY: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border border-red-500/25',
  high:     'bg-orange-500/15 text-orange-400 border border-orange-500/25',
  medium:   'bg-yellow-500/15 text-yellow-400 border border-yellow-500/25',
  low:      'bg-blue-500/15 text-blue-400 border border-blue-500/25',
};
const EFFORT: Record<string, string> = {
  low:    'bg-green-500/15 text-green-400 border border-green-500/25',
  medium: 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/25',
  high:   'bg-red-500/15 text-red-400 border border-red-500/25',
};
const STATUS_STYLE: Record<string, string> = {
  open:          'bg-yellow-500/10 text-yellow-400',
  investigating: 'bg-blue-500/10 text-blue-400',
  resolved:      'bg-green-500/10 text-green-400',
  dismissed:     'bg-gray-500/10 text-gray-400',
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function BudgetGauge({ pct }: { pct: number }) {
  const clamped = Math.min(pct, 130);
  const color   = pct > 100 ? '#ef4444' : pct > 80 ? '#f59e0b' : '#10b981';
  const angle   = -135 + (clamped / 130) * 270;
  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="90" viewBox="0 0 140 90">
        <path d="M 15 85 A 55 55 0 0 1 125 85" fill="none" stroke="hsl(230 15% 14%)" strokeWidth="12" strokeLinecap="round" />
        <path d="M 15 85 A 55 55 0 0 1 125 85" fill="none" stroke={color} strokeWidth="12" strokeLinecap="round"
          strokeDasharray={`${Math.min((clamped / 130), 1) * 172} 172`} />
        <g transform={`rotate(${angle}, 70, 85)`}>
          <line x1="70" y1="85" x2="70" y2="40" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="70" cy="85" r="4" fill="white" />
        </g>
      </svg>
      <div className="text-center -mt-2">
        <span className="text-2xl font-bold" style={{ color }}>{pct}%</span>
        <p className="text-xs text-muted-foreground mt-0.5">of budget used</p>
      </div>
    </div>
  );
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border px-3 py-2 text-xs shadow-xl"
      style={{ background: 'hsl(230 18% 10%)', borderColor: 'hsl(230 15% 14%)' }}>
      <p className="text-muted-foreground mb-1">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-muted-foreground capitalize">{p.name}:</span>
          <span className="font-medium text-foreground">${(p.value ?? 0).toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

/** Skeleton pulse for loading state */
function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

/** Card skeleton for metric cards */
function MetricCardSkeleton() {
  return (
    <div className="card-base p-5 space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-8 w-8 rounded-lg" />
      </div>
      <Skeleton className="h-8 w-36" />
      <Skeleton className="h-3 w-24" />
    </div>
  );
}

/** Empty state when AWS not connected at all */
function NotConnectedBanner() {
  return (
    <div className="card-base py-16 text-center space-y-4">
      <Cloud className="w-12 h-12 text-muted-foreground mx-auto opacity-50" />
      <div>
        <p className="text-sm font-semibold text-foreground">No cloud provider connected</p>
        <p className="text-xs text-muted-foreground mt-1">
          Connect AWS in <strong className="text-foreground">Settings → Integrations</strong> to start seeing real cost data.
        </p>
      </div>
      <a href="/settings/integrations"
        className="inline-flex items-center gap-2 px-4 py-2 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors">
        <Cloud className="w-3.5 h-3.5" /> Connect AWS
      </a>
    </div>
  );
}

/** Error state when AWS integration exists but credentials failed */
function IntegrationErrorBanner({ error, onSync, syncing }: {
  error: string | null;
  onSync: () => void;
  syncing: boolean;
}) {
  return (
    <div className="card-base py-12 px-6 space-y-4 border-orange-500/20 bg-orange-500/5">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-foreground mb-1">AWS credentials need attention</p>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {error
              ? error
              : 'The connection test failed. Check your Access Key and Secret Key in Settings → Integrations.'}
          </p>
          {error && error.toLowerCase().includes('permission') && (
            <p className="text-xs text-orange-300 mt-2">
              Make sure your IAM user has <strong>ce:GetCostAndUsage</strong>, <strong>sts:GetCallerIdentity</strong>, or <strong>ec2:DescribeRegions</strong> permissions.
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3 pl-8">
        <a href="/settings/integrations"
          className="inline-flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg bg-orange-600 hover:bg-orange-700 text-white transition-colors font-medium">
          <Cloud className="w-3 h-3" /> Fix Credentials
        </a>
        <button onClick={onSync} disabled={syncing}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg border border-white/10 text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50">
          <RefreshCw className={clsx('w-3 h-3', syncing && 'animate-spin')} />
          {syncing ? 'Retrying…' : 'Retry Connection'}
        </button>
      </div>
    </div>
  );
}

/** Pending state when integration was just saved and is being tested */
function PendingBanner({ onSync, syncing }: { onSync: () => void; syncing: boolean }) {
  return (
    <div className="card-base py-12 px-6 space-y-4 border-blue-500/20 bg-blue-500/5">
      <div className="flex items-start gap-3">
        <Loader2 className="w-5 h-5 text-blue-400 animate-spin flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-foreground mb-1">Testing AWS credentials…</p>
          <p className="text-xs text-muted-foreground">
            Your AWS integration was just saved. Verifying credentials and pulling initial cost data — this usually takes under 30 seconds.
          </p>
        </div>
      </div>
      <div className="pl-8">
        <button onClick={onSync} disabled={syncing}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition-colors disabled:opacity-50">
          <RefreshCw className={clsx('w-3 h-3', syncing && 'animate-spin')} />
          {syncing ? 'Syncing…' : 'Check Now'}
        </button>
      </div>
    </div>
  );
}

/** Confirm dialog for destructive or expensive actions */
function ConfirmDialog({ open, title, description, confirmLabel, onConfirm, onCancel, loading }: {
  open: boolean; title: string; description: string; confirmLabel: string;
  onConfirm: () => void; onCancel: () => void; loading: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
        className="relative z-10 w-full max-w-md rounded-2xl border p-6 shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <div className="flex items-start gap-3 mb-5">
          <div className="p-2 rounded-lg bg-green-500/10 flex-shrink-0 mt-0.5">
            <Lightbulb className="w-4 h-4 text-green-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
            <p className="text-xs text-gray-400 leading-relaxed">{description}</p>
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} disabled={loading}
            className="px-4 py-2 text-xs rounded-lg border text-gray-400 hover:text-white transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>Cancel</button>
          <button onClick={onConfirm} disabled={loading}
            className="px-4 py-2 text-xs rounded-lg font-semibold flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white transition-all disabled:opacity-60">
            {loading && <Loader2 className="w-3 h-3 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Metric Card ───────────────────────────────────────────────────────────────
function MetricCard({ label, value, sub, icon: Icon, iconColor, trend }: {
  label: string; value: string; sub?: string;
  icon: React.ElementType; iconColor: string; trend?: number;
}) {
  return (
    <div className="card-base p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-muted-foreground font-medium">{label}</p>
        <div className={clsx('p-2 rounded-lg', iconColor)}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <p className="text-2xl font-bold tracking-tight text-foreground">{value}</p>
      {(sub || trend !== undefined) && (
        <div className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          {trend !== undefined && trend !== 0 && (
            <>
              {trend > 0
                ? <TrendingUp className="w-3 h-3 text-red-400" />
                : <TrendingDown className="w-3 h-3 text-green-400" />}
              <span className={trend > 0 ? 'text-red-400' : 'text-green-400'}>
                {trend > 0 ? '+' : ''}{trend.toFixed(1)}%
              </span>
              <span>vs last month</span>
            </>
          )}
          {sub && <span>{sub}</span>}
        </div>
      )}
    </div>
  );
}

// ── Last synced indicator ─────────────────────────────────────────────────────
function LastSyncedBadge({ dataUpdatedAt }: { dataUpdatedAt?: number }) {
  if (!dataUpdatedAt) return null;
  const ago = Math.round((Date.now() - dataUpdatedAt) / 1000);
  const label = ago < 60 ? `${ago}s ago` : `${Math.round(ago / 60)}m ago`;
  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground">
      <Clock className="w-3 h-3" />
      <span>Synced {label}</span>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// Main Component
// ══════════════════════════════════════════════════════════════════════════════
export default function CostCenter() {
  const [tab, setTab]         = useState<Tab>('overview');
  const [confirm, setConfirm] = useState<{
    title: string; description: string; confirmLabel: string;
    action: () => void;
  } | null>(null);

  // ── React Query hooks ────────────────────────────────────────────────────
  const summaryQ   = useCostSummary();
  const breakdownQ = useCostBreakdown();
  const forecastQ  = useCostForecast();
  const anomaliesQ = useCostAnomalies();
  const savingsQ   = useSavings();

  const invalidateAll = useInvalidateAllCostData();
  const triggerSync   = useTriggerCostSync();

  // Mutations
  const investigate = useInvestigateAnomaly();
  const resolve     = useResolveAnomaly();
  const dismiss     = useDismissAnomaly();
  const applySaving = useApplySaving();
  const dismissSav  = useDismissSaving();

  // WebSocket live pushes
  const { subscribe } = useWebSocket();
  useState(() => {
    const u1 = subscribe('cost.anomaly_detected', () => {
      anomaliesQ.refetch(); summaryQ.refetch();
    });
    const u2 = subscribe('ml.insight', () => forecastQ.refetch());
    return () => { u1(); u2(); };
  });

  // Normalise data
  const summary   = summaryQ.data;
  const breakdown = breakdownQ.data ?? [];
  const forecast  = forecastQ.data;
  const anomalies = anomaliesQ.data ?? [];
  const savings   = savingsQ.data ?? [];

  // ── Integration state (from backend's new integration_status field) ─────────
  // connected:      integration is "connected" AND credentials verified
  // intgStatus:     "connected" | "error" | "pending" | "disconnected" | null
  // showDashboard:  show the full dashboard (connected OR has data from a prev sync)
  const intgStatus    = summary?.integration_status ?? null;
  const connected     = summary?.connected ?? (intgStatus === 'connected');
  const hasData       = summary?.has_data ?? (summary ? (summary.mtd ?? 0) > 0 : false);
  const showDashboard = connected || (hasData && intgStatus !== null);
  const anyLoading    = summaryQ.isLoading || breakdownQ.isLoading;
  const isRefreshing  = summaryQ.isFetching && !summaryQ.isLoading;

  const fmt = (v: number | undefined) =>
    v !== undefined && v !== null ? `$${v.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '—';

  const fmtSmall = (v: number | undefined) =>
    v !== undefined && v !== null ? `$${v.toFixed(2)}` : '—';

  // Donut chart data
  const total     = breakdown.reduce((a, s) => a + (s.mtd ?? 0), 0);
  const donutData = breakdown
    .sort((a, b) => b.mtd - a.mtd)
    .slice(0, 7)
    .map(s => ({ name: s.service, value: s.mtd }));

  // Budget gauge
  const budgetPct = forecast && forecast.budget > 0
    ? Math.round((forecast.eom_forecast / forecast.budget) * 100)
    : 0;

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: 'overview',  label: 'Overview',       icon: BarChart2 },
    { id: 'services',  label: 'By Service',      icon: Zap },
    { id: 'forecast',  label: 'Forecast',        icon: TrendingUp },
    { id: 'savings',   label: `Savings (${savings.filter(s => s.status === 'pending' || s.status === 'open').length})`, icon: Lightbulb },
    { id: 'anomalies', label: `Anomalies (${anomalies.filter(a => a.status === 'open').length})`, icon: AlertTriangle },
  ];

  return (
    <div className="space-y-5 p-6 max-w-7xl mx-auto">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-blue-400" /> FinOps Cost Center
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">Real-time cloud cost intelligence</p>
        </div>
        <div className="flex items-center gap-2">
          <LastSyncedBadge dataUpdatedAt={summaryQ.dataUpdatedAt} />
          {/* Sync Now — triggers a real AWS data pull on the backend */}
          {intgStatus !== null && (
            <button
              onClick={() => triggerSync.mutate()}
              disabled={triggerSync.isPending || isRefreshing}
              title="Pull latest cost data from AWS"
              className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition-all disabled:opacity-50">
              <RefreshCw className={clsx('w-3.5 h-3.5', triggerSync.isPending && 'animate-spin')} />
              {triggerSync.isPending ? 'Syncing…' : 'Sync Now'}
            </button>
          )}
          <button
            onClick={invalidateAll}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg border transition-all hover:text-foreground text-muted-foreground"
            style={{ borderColor: 'hsl(230 15% 18%)' }}>
            <RefreshCw className={clsx('w-3.5 h-3.5', isRefreshing && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {/* ── Integration state banners (shown only when no data yet) ── */}
      {!anyLoading && !showDashboard && intgStatus === 'error' && (
        <IntegrationErrorBanner
          error={summary?.integration_error ?? null}
          onSync={() => triggerSync.mutate()}
          syncing={triggerSync.isPending}
        />
      )}
      {!anyLoading && !showDashboard && intgStatus === 'pending' && (
        <PendingBanner
          onSync={() => { invalidateAll(); summaryQ.refetch(); }}
          syncing={isRefreshing}
        />
      )}
      {!anyLoading && !showDashboard && (intgStatus === null || intgStatus === 'disconnected') && (
        <NotConnectedBanner />
      )}

      {/* ── Error badge shown above dashboard when integration has error but old data exists ── */}
      {showDashboard && intgStatus === 'error' && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs border border-orange-500/20 bg-orange-500/5 text-orange-300">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span className="flex-1">AWS credentials have an issue — showing last synced data.{' '}
            <a href="/settings/integrations" className="underline underline-offset-2 hover:text-orange-200">Fix credentials</a>
            {summary?.integration_error ? `: ${summary.integration_error}` : '.'}
          </span>
          <button onClick={() => triggerSync.mutate()} disabled={triggerSync.isPending}
            className="ml-2 px-2 py-1 rounded border border-orange-500/30 hover:bg-orange-500/10 transition-colors disabled:opacity-50 whitespace-nowrap">
            {triggerSync.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Retry'}
          </button>
        </div>
      )}

      {/* ── Metric Cards ── */}
      {anyLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <MetricCardSkeleton key={i} />)}
        </div>
      ) : !showDashboard ? null : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Month-to-Date"
            value={fmt(summary?.mtd)}
            icon={DollarSign}
            iconColor="bg-blue-500/10 text-blue-400"
            trend={summary?.trend_pct}
          />
          <MetricCard
            label="Projected Month-End"
            value={fmt(summary?.projected)}
            sub={forecast ? `Budget: ${fmt(forecast.budget)}` : undefined}
            icon={TrendingUp}
            iconColor={forecast?.over_budget ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'}
          />
          <MetricCard
            label="Daily Average"
            value={fmtSmall(summary?.daily_avg)}
            sub="per day this month"
            icon={BarChart2}
            iconColor="bg-purple-500/10 text-purple-400"
          />
          <MetricCard
            label="Year-to-Date"
            value={fmt(summary?.ytd)}
            sub={new Date().getFullYear().toString()}
            icon={Zap}
            iconColor="bg-amber-500/10 text-amber-400"
          />
        </div>
      )}

      {/* ── Tabs (only when there is something to display) ── */}
      {showDashboard && (
        <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'hsl(230 15% 10%)' }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={clsx(
                'flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium transition-all',
                tab === t.id
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-muted-foreground hover:text-foreground',
              )}>
              <t.icon className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{t.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* ══════════════════ OVERVIEW ══════════════════ */}
      {tab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Donut chart */}
          <div className="card-base p-5">
            <h3 className="text-sm font-semibold text-foreground mb-4">Spend by Service (MTD)</h3>
            {breakdownQ.isLoading ? (
              <Skeleton className="h-48 w-full" />
            ) : donutData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-xs text-muted-foreground">No data yet</div>
            ) : (
              <div className="flex items-center gap-6">
                <PieChart width={180} height={180}>
                  <Pie data={donutData} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                    paddingAngle={2} dataKey="value">
                    {donutData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: any) => [`$${Number(v).toLocaleString()}`, '']} />
                </PieChart>
                <div className="flex-1 space-y-1.5 min-w-0">
                  {donutData.map((s, i) => (
                    <div key={s.name} className="flex items-center gap-2 text-xs">
                      <span className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="truncate text-muted-foreground flex-1">{s.name}</span>
                      <span className="font-mono text-foreground">${s.value.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Budget gauge */}
          <div className="card-base p-5 flex flex-col items-center justify-center gap-4">
            <h3 className="text-sm font-semibold text-foreground self-start">Budget Utilization</h3>
            {forecastQ.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              <>
                <BudgetGauge pct={budgetPct} />
                {forecast && (
                  <p className="text-xs text-center text-muted-foreground max-w-xs leading-relaxed">
                    {forecast.insight}
                  </p>
                )}
              </>
            )}
          </div>

          {/* Open anomalies alert */}
          {anomalies.filter(a => a.status === 'open').length > 0 && (
            <div className="lg:col-span-2 flex items-center gap-3 px-4 py-3 rounded-xl border border-orange-500/20 bg-orange-500/5">
              <AlertTriangle className="w-4 h-4 text-orange-400 flex-shrink-0" />
              <p className="text-xs text-orange-300">
                <strong>{anomalies.filter(a => a.status === 'open').length} cost anomalies</strong> detected this month.
                {' '}<button onClick={() => setTab('anomalies')} className="underline">View and investigate →</button>
              </p>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════ BY SERVICE ══════════════════ */}
      {tab === 'services' && (
        <div className="card-base overflow-hidden">
          <div className="p-4 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
            <h3 className="text-sm font-semibold text-foreground">Service Cost Breakdown — MTD</h3>
          </div>
          {breakdownQ.isLoading ? (
            <div className="p-4 space-y-3">
              {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : breakdown.length === 0 ? (
            <div className="p-8 text-center text-xs text-muted-foreground">No cost data available</div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-muted-foreground" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                  {['Service', 'Provider', 'MTD Spend', 'vs Last Period', '% of Total'].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'hsl(230 15% 10%)' }}>
                {breakdown.map((s, i) => (
                  <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3 font-medium text-foreground">{s.service}</td>
                    <td className="px-4 py-3 text-muted-foreground uppercase tracking-wider">{s.provider}</td>
                    <td className="px-4 py-3 font-mono font-semibold text-foreground">
                      ${(s.mtd ?? 0).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      {s.change_pct !== 0 ? (
                        <span className={clsx('flex items-center gap-1 font-mono', s.change_pct > 0 ? 'text-red-400' : 'text-green-400')}>
                          {s.change_pct > 0 ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          {Math.abs(s.change_pct)}%
                        </span>
                      ) : <span className="text-muted-foreground">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                          <div className="h-full rounded-full"
                            style={{ width: `${s.pct_of_total ?? 0}%`, background: COLORS[i % COLORS.length] }} />
                        </div>
                        <span className="font-mono text-muted-foreground w-10 text-right">{s.pct_of_total ?? 0}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t font-semibold" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                  <td colSpan={2} className="px-4 py-2.5 text-muted-foreground">Total</td>
                  <td className="px-4 py-2.5 font-mono text-foreground">${total.toLocaleString()}</td>
                  <td colSpan={2} />
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      )}

      {/* ══════════════════ FORECAST ══════════════════ */}
      {tab === 'forecast' && (
        <div className="space-y-5">
          {/* Summary cards */}
          {forecastQ.isLoading ? (
            <div className="grid grid-cols-3 gap-4">
              {[...Array(3)].map((_, i) => <MetricCardSkeleton key={i} />)}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              <div className="card-base p-4 text-center">
                <p className="text-xs text-muted-foreground">Model Accuracy</p>
                <p className="text-2xl font-bold text-green-400 mt-1">{forecast?.accuracy ?? '—'}%</p>
                <p className="text-xs text-muted-foreground mt-0.5">Random Forest</p>
              </div>
              <div className="card-base p-4 text-center">
                <p className="text-xs text-muted-foreground">EOM Forecast</p>
                <p className="text-2xl font-bold text-foreground mt-1">{fmt(forecast?.eom_forecast)}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{fmt(summary?.daily_avg)}/day avg</p>
              </div>
              <div className={clsx('card-base p-4 text-center', forecast?.over_budget && 'border-red-500/20 bg-red-500/5')}>
                <p className="text-xs text-muted-foreground">Budget Status</p>
                <p className={clsx('text-2xl font-bold mt-1', forecast?.over_budget ? 'text-red-400' : 'text-green-400')}>
                  {forecast?.over_budget ? 'Over' : 'On track'}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">Budget: {fmt(forecast?.budget)}</p>
              </div>
            </div>
          )}

          {/* Area chart */}
          <div className="card-base p-5">
            <h3 className="text-sm font-semibold text-foreground mb-4">Spend Trend &amp; Forecast</h3>
            {forecastQ.isLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : !forecast?.points?.length ? (
              <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">
                No forecast data — connect AWS to generate predictions
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={forecast.points} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gradActual" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradPredicted" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#8b5cf6" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="hsl(230 15% 12%)" strokeDasharray="3 3" />
                  {/* dataKey="date" — matches backend field name */}
                  <XAxis dataKey="date" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} tickLine={false} axisLine={false}
                    interval="preserveStartEnd" />
                  <YAxis tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} tickLine={false} axisLine={false}
                    tickFormatter={(v) => `$${v >= 1000 ? `${(v/1000).toFixed(0)}k` : v}`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="actual"    name="Actual"    stroke="#3b82f6" strokeWidth={2} fill="url(#gradActual)"    connectNulls={false} dot={false} />
                  {/* dataKey="predicted" — matches backend alias */}
                  <Area type="monotone" dataKey="predicted" name="Predicted" stroke="#8b5cf6" strokeWidth={2} fill="url(#gradPredicted)" dot={false} strokeDasharray="5 4" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          {forecast?.insight && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-xs border border-blue-500/15 bg-blue-500/5 text-blue-300">
              <ShieldAlert className="w-4 h-4 flex-shrink-0" /> {forecast.insight}
            </div>
          )}
        </div>
      )}

      {/* ══════════════════ SAVINGS ══════════════════ */}
      {tab === 'savings' && (
        <div className="space-y-3">
          {savingsQ.isLoading ? (
            [...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)
          ) : savings.filter(s => ['pending', 'open'].includes(s.status)).length === 0 ? (
            <div className="card-base py-12 text-center space-y-2">
              <CheckCircle className="w-8 h-8 text-green-400 mx-auto" />
              <p className="text-sm font-medium text-foreground">All savings applied or dismissed</p>
              <p className="text-xs text-muted-foreground">Check back after the next cost sync</p>
            </div>
          ) : (
            savings
              .filter(s => ['pending', 'open'].includes(s.status))
              .map(s => (
                <div key={s.id} className="card-base p-4 flex items-start gap-4">
                  <div className="p-2 rounded-lg bg-green-500/10 flex-shrink-0 mt-0.5">
                    <Lightbulb className="w-4 h-4 text-green-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-sm font-medium text-foreground">{s.title}</p>
                      <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-medium', EFFORT[s.effort])}>
                        {s.effort} effort
                      </span>
                    </div>
                    {s.description && <p className="text-xs text-muted-foreground mb-2">{s.description}</p>}
                    <p className="text-xs text-green-400 font-semibold">
                      Save ${s.potential_savings.toLocaleString()}/mo
                    </p>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <button
                      onClick={() => setConfirm({
                        title: 'Apply Saving',
                        description: `This will apply "${s.title}" via AWS API. Estimated monthly saving: $${s.potential_savings.toLocaleString()}.`,
                        confirmLabel: 'Apply Now',
                        action: () => applySaving.mutateAsync(s.id).then(() => {}),
                      })}
                      disabled={applySaving.isPending}
                      className="px-3 py-1.5 text-xs rounded-lg bg-green-600 hover:bg-green-700 text-white font-medium transition-all disabled:opacity-50">
                      Apply
                    </button>
                    <button
                      onClick={() => dismissSav.mutate(s.id)}
                      disabled={dismissSav.isPending}
                      className="px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
                      style={{ borderColor: 'hsl(230 15% 20%)' }}>
                      Dismiss
                    </button>
                  </div>
                </div>
              ))
          )}
        </div>
      )}

      {/* ══════════════════ ANOMALIES ══════════════════ */}
      {tab === 'anomalies' && (
        <div className="space-y-3">
          {anomaliesQ.isLoading ? (
            [...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)
          ) : anomalies.length === 0 ? (
            <div className="card-base py-12 text-center space-y-2">
              <CheckCircle className="w-8 h-8 text-green-400 mx-auto" />
              <p className="text-sm font-medium text-foreground">No anomalies detected</p>
              <p className="text-xs text-muted-foreground">Cost patterns look normal</p>
            </div>
          ) : (
            anomalies.map(a => (
              <div key={a.id} className="card-base p-4">
                <div className="flex items-start gap-3">
                  <div className={clsx('p-2 rounded-lg flex-shrink-0', SEVERITY[a.severity] ?? SEVERITY.low)}>
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <p className="text-sm font-semibold text-foreground">{a.service}</p>
                      <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-medium', SEVERITY[a.severity] ?? SEVERITY.low)}>
                        {a.severity}
                      </span>
                      <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-medium', STATUS_STYLE[a.status] ?? STATUS_STYLE.open)}>
                        {a.status}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mb-2">{a.description}</p>
                    <div className="flex gap-4 text-xs text-muted-foreground">
                      <span>Expected: <span className="text-foreground">${(a.expected_amount ?? 0).toLocaleString()}</span></span>
                      <span>Actual: <span className="text-red-400">${(a.actual_amount ?? 0).toLocaleString()}</span></span>
                      <span>Deviation: <span className="text-orange-400">+{a.deviation_pct ?? 0}%</span></span>
                    </div>
                    {a.root_cause && (
                      <p className="text-xs text-muted-foreground mt-1.5">
                        <span className="text-foreground font-medium">Root cause:</span> {a.root_cause}
                      </p>
                    )}
                  </div>
                  {/* Actions — only for non-terminal statuses */}
                  {!['resolved', 'dismissed'].includes(a.status) && (
                    <div className="flex gap-2 flex-shrink-0">
                      {a.status === 'open' && (
                        <button
                          onClick={() => investigate.mutate(a.id)}
                          disabled={investigate.isPending}
                          className="px-2.5 py-1.5 text-xs rounded-lg border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition-colors disabled:opacity-50">
                          {investigate.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Investigate'}
                        </button>
                      )}
                      <button
                        onClick={() => resolve.mutate(a.id)}
                        disabled={resolve.isPending}
                        className="px-2.5 py-1.5 text-xs rounded-lg border border-green-500/30 text-green-400 hover:bg-green-500/10 transition-colors disabled:opacity-50">
                        {resolve.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Resolve'}
                      </button>
                      <button
                        onClick={() => dismiss.mutate(a.id)}
                        disabled={dismiss.isPending}
                        className="px-2.5 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
                        style={{ borderColor: 'hsl(230 15% 20%)' }}>
                        Dismiss
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Confirm dialog */}
      <ConfirmDialog
        open={!!confirm}
        title={confirm?.title ?? ''}
        description={confirm?.description ?? ''}
        confirmLabel={confirm?.confirmLabel ?? 'Confirm'}
        onConfirm={() => { confirm?.action(); setConfirm(null); }}
        onCancel={() => setConfirm(null)}
        loading={applySaving.isPending}
      />
    </div>
  );
}
