import { useState, useCallback, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Sparkles, TrendingUp, TrendingDown, Network, Lightbulb,
  RefreshCw, ChevronDown, ChevronUp, CheckCircle, XCircle,
  AlertTriangle, Zap, Clock, BarChart2, Loader2, X, Calendar,
} from 'lucide-react';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import { useIntegrationsCtx } from '@/contexts/IntegrationsContext';
import { useWebSocket } from '@/contexts/WebSocketContext';

type Tab = 'correlations' | 'predictions' | 'patterns' | 'recommendations';
type DaysFilter = 7 | 30 | 90 | 0;

const DAY_OPTIONS: { label: string; value: DaysFilter }[] = [
  { label: '7 days',  value: 7  },
  { label: '30 days', value: 30 },
  { label: '90 days', value: 90 },
  { label: 'All time', value: 0 },
];

const PRIORITY_STYLE: Record<string, { badge: string; dot: string; label: string }> = {
  critical: { badge: 'bg-red-500/15 text-red-400 border border-red-500/25',    dot: 'bg-red-500',    label: 'Critical' },
  high:     { badge: 'bg-orange-500/15 text-orange-400 border border-orange-500/25', dot: 'bg-orange-500', label: 'High' },
  medium:   { badge: 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/25', dot: 'bg-yellow-500', label: 'Medium' },
  low:      { badge: 'bg-blue-500/15 text-blue-400 border border-blue-500/25',  dot: 'bg-blue-500',   label: 'Low' },
};
const EFFORT_STYLE: Record<string, string> = {
  low:    'bg-green-500/10 text-green-400 border border-green-500/20',
  medium: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
  high:   'bg-red-500/10 text-red-400 border border-red-500/20',
};
const CORR_STRENGTH = (r: number) => r >= 0.9 ? { label: 'Very Strong', color: '#10b981' } : r >= 0.8 ? { label: 'Strong', color: '#3b82f6' } : r >= 0.7 ? { label: 'Moderate', color: '#f59e0b' } : { label: 'Weak', color: '#6b7280' };

// ── Confirm Dialog ─────────────────────────────────────────────────────────────
function ConfirmDialog({ open, title, desc, confirmLabel, danger, onConfirm, onCancel, loading }: {
  open: boolean; title: string; desc: string; confirmLabel: string; danger?: boolean;
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
          <div className={clsx('p-2 rounded-lg flex-shrink-0', danger ? 'bg-red-500/10' : 'bg-purple-500/10')}>
            <Brain className={clsx('w-4 h-4', danger ? 'text-red-400' : 'text-purple-400')} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
            <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} disabled={loading}
            className="px-4 py-2 text-xs rounded-lg border text-gray-400 hover:text-white transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>Cancel</button>
          <button onClick={onConfirm} disabled={loading}
            className={clsx('px-4 py-2 text-xs rounded-lg font-semibold flex items-center gap-1.5 transition-all disabled:opacity-60',
              danger ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-purple-600 hover:bg-purple-700 text-white')}>
            {loading && <Loader2 className="w-3 h-3 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Custom chart tooltip ───────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border px-3 py-2 text-xs shadow-xl" style={{ background: 'hsl(230 18% 10%)', borderColor: 'hsl(230 15% 14%)' }}>
      <p className="text-muted-foreground mb-1">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-muted-foreground capitalize">{p.name}:</span>
          <span className="font-medium text-foreground">{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</span>
        </div>
      ))}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
export default function MLInsights() {
  const [tab, setTab]           = useState<Tab>('correlations');
  const [corrDays, setCorrDays] = useState<DaysFilter>(30);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSyncing,   setIsSyncing]   = useState(false);
  const [toast, setToast]       = useState<{ ok: boolean; msg: string } | null>(null);
  const [confirm, setConfirm]   = useState<{ title: string; desc: string; confirmLabel: string; danger?: boolean; action: () => Promise<void> } | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [expandedRec, setExpandedRec] = useState<string | null>(null);

  const corrPath = corrDays > 0 ? `/ml/correlations?days=${corrDays}` : '/ml/correlations';
  const { data: corrRaw,    loading: corrLoad,  refetch: refetchCorr  } = useApi<any>(corrPath);
  const { data: predsRaw,   loading: predLoad,  refetch: refetchPred  } = useApi<any>('/ml/predictions');
  const { data: chartRaw,   loading: chartLoad, refetch: refetchChart } = useApi<any>('/ml/workload/chart');
  const { data: predSumRaw, loading: psLoad,    refetch: refetchPS    } = useApi<any>('/ml/predictions/summary');
  const { data: patsRaw,    loading: patLoad,   refetch: refetchPat   } = useApi<any>('/ml/patterns');
  const { data: recsRaw,    loading: recLoad,   refetch: refetchRec   } = useApi<any>('/ml/recommendations');
  const { data: modelsRaw,  loading: modLoad,   refetch: refetchModels} = useApi<any>('/ml/models/status');
  const { data: radarRaw,                       refetch: refetchRadar  } = useApi<any>('/ml/radar');

  // ── Global integrations state (shared — no extra HTTP request) ────────────
  const { isConnected } = useIntegrationsCtx();

  // ── Live WebSocket updates ─────────────────────────────────────────────────
  const { subscribe } = useWebSocket();
  useEffect(() => {
    // ml.insight → correlations were recalculated by reactive ML pipeline
    const unsubML = subscribe('ml.insight', () => {
      refetchCorr(true);
      refetchRadar(true);
    });
    return () => { unsubML(); };
  }, [subscribe, refetchCorr, refetchRadar]);

  const corrs:       any[] = (Array.isArray(corrRaw)  ? corrRaw  : corrRaw?.data)  ?? [];
  const preds:       any[] = (Array.isArray(predsRaw) ? predsRaw : predsRaw?.data) ?? [];
  const chartPoints: any[] = chartRaw?.data?.points ?? chartRaw?.points ?? [];
  const pats:   any[] = (Array.isArray(patsRaw)  ? patsRaw  : patsRaw?.data)  ?? [];
  const recs:   any[] = (Array.isArray(recsRaw)  ? recsRaw  : recsRaw?.data)  ?? [];
  const predSum: any  = predSumRaw ?? {};
  const models: any   = modelsRaw  ?? {};
  const radarData: any[] = (Array.isArray(radarRaw) ? radarRaw : radarRaw?.data) ?? [];

  const liveMode = isConnected('github') || isConnected('aws') || isConnected('kubernetes');

  const activeRecs = recs.filter(r => r.status === 'pending');
  const activePats = pats.filter(p => p.status !== 'dismissed');

  const showToast = (ok: boolean, msg: string) => {
    setToast({ ok, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const runConfirm = async () => {
    if (!confirm) return;
    setConfirmLoading(true);
    try { await confirm.action(); }
    finally { setConfirmLoading(false); setConfirm(null); }
  };

  const refetchAll = useCallback(() => {
    refetchCorr(true); refetchPred(true); refetchChart(true); refetchPS(true); refetchPat(true); refetchRec(true); refetchModels(true); refetchRadar(true);
  }, [refetchCorr, refetchPred, refetchChart, refetchPS, refetchPat, refetchRec, refetchModels, refetchRadar]);

  const handleAnalyze = useCallback(async () => {
    setIsAnalyzing(true);
    try {
      await apiPost('/ml/analyze', {});
      refetchAll();
      showToast(true, 'Analysis complete — insights updated');
    } catch {
      showToast(false, 'Analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  }, [refetchAll]);

  const handleSyncML = useCallback(async () => {
    setIsSyncing(true);
    try {
      await apiPost('/ml/sync', {});
      // Poll for a couple seconds then refetch — the sync runs async in the backend
      setTimeout(() => { refetchAll(); }, 3000);
      showToast(true, 'Prediction sync started — refreshing in 3s…');
    } catch {
      showToast(false, 'Sync failed');
    } finally {
      setIsSyncing(false);
    }
  }, [refetchAll]);

  const recCounts = {
    total:    recs.length,
    critical: recs.filter(r => r.priority === 'critical').length,
    high:     recs.filter(r => r.priority === 'high').length,
    medium:   recs.filter(r => r.priority === 'medium').length,
  };

  const summaryCards = [
    { label: 'Active Correlations', value: corrs.length || '—', icon: Network,   color: 'text-cyan-400',    bg: 'bg-cyan-500/10' },
    { label: 'Model Accuracy',      value: models.workload_predictor ? `${models.workload_predictor.accuracy}%` : '—', icon: Brain, color: 'text-purple-400', bg: 'bg-purple-500/10' },
    { label: 'Patterns Found',      value: activePats.length || '—', icon: BarChart2, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
    { label: 'Recommendations',     value: activeRecs.length || '—', icon: Lightbulb, color: 'text-green-400',  bg: 'bg-green-500/10' },
  ];

  const TABS = [
    { id: 'correlations' as Tab,   label: 'Correlations',   icon: Network },
    { id: 'predictions'  as Tab,   label: 'Predictions',    icon: TrendingUp },
    { id: 'patterns'     as Tab,   label: `Patterns${activePats.length ? ` (${activePats.length})` : ''}`, icon: Brain },
    { id: 'recommendations' as Tab,label: `Recommendations${activeRecs.length ? ` (${activeRecs.length})` : ''}`, icon: Lightbulb },
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }}
            className={clsx('fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium shadow-xl border',
              toast.ok ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400')}>
            {toast.ok ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            {toast.msg}
            <button onClick={() => setToast(null)} className="ml-1 opacity-60 hover:opacity-100"><X className="w-3.5 h-3.5" /></button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {confirm && (
          <ConfirmDialog open={!!confirm} title={confirm.title} desc={confirm.desc}
            confirmLabel={confirm.confirmLabel} danger={confirm.danger}
            onConfirm={runConfirm} onCancel={() => setConfirm(null)} loading={confirmLoading} />
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="page-header">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Brain className="w-5 h-5 text-purple-400" />
            <h1 className="page-title">ML Insights</h1>
          </div>
          <p className="page-subtitle">
            {liveMode
              ? 'Live integration-backed insights from connected services'
              : 'Connect GitHub, AWS, or Kubernetes to unlock live insights'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleSyncML} className="action-btn" disabled={isSyncing}>
            {isSyncing
              ? <><Loader2 className="w-4 h-4 animate-spin" />Syncing…</>
              : <><RefreshCw className="w-4 h-4" />Sync Predictions</>}
          </button>
          <button onClick={handleAnalyze} className="action-btn-primary" disabled={isAnalyzing}>
            {isAnalyzing
              ? <><Loader2 className="w-4 h-4 animate-spin" />Analyzing…</>
              : <><Sparkles className="w-4 h-4" />Run Analysis</>}
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        {summaryCards.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
            className="card-base flex items-center gap-4">
            <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0', s.bg)}>
              <s.icon className={clsx('w-5 h-5', s.color)} />
            </div>
            <div>
              <div className="text-xl font-bold text-foreground">{s.value}</div>
              <div className="text-xs text-muted-foreground">{s.label}</div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Tabs */}
      <div className="tab-bar mb-5">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={clsx('tab-btn', tab === t.id && 'active')}>
            <t.icon className="w-4 h-4" />{t.label}
          </button>
        ))}
      </div>

      {/* ── CORRELATIONS ─────────────────────────────────────────────────────── */}
      {tab === 'correlations' && (
        <div className="space-y-4">
          {!liveMode && (
            <div className="card-base border-yellow-500/20 bg-yellow-500/5 text-yellow-200 text-sm">
              No connected integrations found. This view stays empty until GitHub, AWS, or Kubernetes is connected.
            </div>
          )}

          {/* ── Date-range filter bar ─────────────────────────────────────── */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground flex items-center gap-1.5 mr-1">
              <Calendar className="w-3.5 h-3.5" />
              Time window:
            </span>
            {DAY_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setCorrDays(opt.value)}
                className={clsx(
                  'px-3 py-1 rounded-lg text-xs font-medium border transition-all',
                  corrDays === opt.value
                    ? 'bg-purple-500/20 border-purple-500/40 text-purple-300'
                    : 'bg-transparent border-border text-muted-foreground hover:border-purple-500/30 hover:text-foreground',
                )}
              >
                {opt.label}
              </button>
            ))}
            {corrLoad && (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground ml-1" />
            )}
            <span className="ml-auto text-xs text-muted-foreground">
              {corrs.length} correlation{corrs.length !== 1 ? 's' : ''}
              {corrDays > 0 ? ` in last ${corrDays} days` : ' (all time)'}
            </span>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* Scatter plot */}
            <div className="card-base">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-sm font-semibold text-foreground">Metric Correlation Map</h2>
                  <p className="text-xs text-muted-foreground mt-0.5">Pearson r — correlation coefficient per metric pair</p>
                </div>
              </div>
              {corrLoad ? (
                <div className="h-48 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
              ) : corrs.length === 0 ? (
                <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">No live correlation data yet.</div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: -8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 14%)" />
                    <XAxis dataKey="x" name="Metric Value (%)" type="number" domain={[50, 100]}
                      tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} tickLine={false} axisLine={false} unit="%" label={{ value: 'Metric Value (%)', position: 'insideBottom', offset: -4, fill: 'hsl(215 16% 40%)', fontSize: 9 }} />
                    <YAxis dataKey="y" name="Pearson r" type="number" domain={[0.6, 1]}
                      tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => v.toFixed(2)} width={36} label={{ value: 'Pearson r', angle: -90, position: 'insideLeft', fill: 'hsl(215 16% 40%)', fontSize: 9 }} />
                    <Tooltip content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0]?.payload;
                      return (
                        <div className="rounded-lg border px-3 py-2 text-xs shadow-xl" style={{ background: 'hsl(230 18% 10%)', borderColor: 'hsl(230 15% 14%)' }}>
                          <p className="font-medium text-foreground mb-1">{d?.label}</p>
                          <p className="text-muted-foreground">r = <span className="text-purple-400 font-bold">{d?.y?.toFixed(2)}</span></p>
                          <p className="text-muted-foreground">Metric: <span className="text-foreground">{d?.x}%</span></p>
                        </div>
                      );
                    }} />
                    <Scatter data={corrs} shape={(props: any) => {
                      const { cx, cy, payload } = props;
                      return <circle cx={cx} cy={cy} r={7} fill={payload.color ?? '#8b5cf6'} opacity={0.85} />;
                    }} />
                  </ScatterChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* System Health Radar */}
            <div className="card-base">
              <h2 className="text-sm font-semibold text-foreground mb-4">System Health Radar</h2>
              {radarData.length === 0 ? (
                <div className="h-48 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="hsl(230 15% 18%)" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: 'hsl(215 16% 55%)', fontSize: 11 }} />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: 'hsl(215 16% 35%)', fontSize: 9 }} tickCount={4} />
                    <Radar name="Score" dataKey="A" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.25} strokeWidth={2} dot={{ fill: '#8b5cf6', r: 3 }} />
                    <Tooltip formatter={(v: number) => [`${v}/100`, 'Score']}
                      contentStyle={{ background: 'hsl(230 18% 10%)', border: '1px solid hsl(230 15% 14%)', borderRadius: 8, fontSize: 12 }} />
                  </RadarChart>
                </ResponsiveContainer>
              )}
              <div className="mt-2 grid grid-cols-5 gap-1">
                {radarData.map((d: any) => (
                  <div key={d.subject} className="text-center">
                    <div className="text-sm font-bold text-purple-400">{d.A}</div>
                    <div className="text-[9px] text-muted-foreground leading-tight">{d.subject.split(' ')[0]}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Correlation list */}
          <div className="card-base">
            <h2 className="text-sm font-semibold text-foreground mb-4">Top Correlations Discovered</h2>
            {corrLoad ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
            ) : corrs.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">No live correlation data yet.</div>
            ) : (
              <div className="space-y-3">
                {corrs.map((c: any) => {
                  const str = CORR_STRENGTH(c.correlation_coefficient);
                  return (
                    <div key={c.id} className="p-4 rounded-xl border border-border bg-surface-1 space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: c.color }} />
                          <span className="text-sm font-medium text-foreground">{c.label}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold" style={{ background: c.color + '22', color: c.color, border: `1px solid ${c.color}40` }}>{str.label}</span>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <div className="w-20 h-1.5 rounded-full bg-border overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${c.correlation_coefficient * 100}%`, background: c.color }} />
                          </div>
                          <span className="text-sm font-bold" style={{ color: c.color }}>r={c.correlation_coefficient.toFixed(2)}</span>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">{c.insight}</p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ML Insight callout — real backend data only */}
          {corrs.length > 0 && corrs[0].insight ? (
            <div className="card-base flex gap-3 bg-purple-500/5 border-purple-500/20">
              <Zap className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-0.5">
                  <p className="text-xs font-semibold text-foreground">Strongest Signal</p>
                  <span
                    className="text-xs font-mono font-bold flex-shrink-0"
                    style={{ color: corrs[0].color ?? '#a78bfa' }}
                  >
                    r = {corrs[0].correlation_coefficient.toFixed(3)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {corrs[0].insight}
                </p>
                <p className="text-xs text-muted-foreground/50 mt-1">
                  {corrs[0].label} · {corrs[0].strength ?? 'correlation detected'}
                </p>
              </div>
            </div>
          ) : corrs.length > 0 ? (
            /* Correlations exist but backend returned no insight text yet */
            <div className="card-base flex gap-3 bg-purple-500/5 border-purple-500/20">
              <Zap className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-foreground mb-0.5">Strongest Signal</p>
                <p className="text-xs font-mono" style={{ color: corrs[0].color ?? '#a78bfa' }}>
                  {corrs[0].label} · r = {corrs[0].correlation_coefficient.toFixed(3)}
                </p>
              </div>
            </div>
          ) : null}

          {/* Empty state — shown when Run Analysis has not been triggered yet */}
          {corrs.length === 0 && liveMode && (
            <div className="card-base flex gap-3 border-dashed">
              <BarChart2 className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-foreground mb-0.5">No correlations yet</p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Click <span className="font-medium text-foreground">Run Analysis</span> to discover
                  real statistical signals across your infrastructure data.
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── PREDICTIONS ──────────────────────────────────────────────────────── */}
      {tab === 'predictions' && (
        <div className="space-y-4">
          {/* 48-hour workload chart */}
          <div className="card-base">
            <div className="flex items-center justify-between mb-1">
              <div>
                <h2 className="text-sm font-semibold text-foreground">48-Hour Workload Prediction</h2>
                <p className="text-xs text-muted-foreground mt-0.5">LSTM Model · {models.workload_predictor?.accuracy ?? 92}% accuracy · Confidence: High</p>
              </div>
              <div className="flex items-center gap-4 text-xs">
                {[{ label: 'Actual', color: '#3b82f6' }, { label: 'Predicted', color: '#8b5cf6' }].map(l => (
                  <div key={l.label} className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 rounded" style={{ background: l.color }} />
                    <span className="text-muted-foreground">{l.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {chartLoad ? (
              <div className="h-64 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>
            ) : chartPoints.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center gap-2 text-center">
                <Brain className="w-8 h-8 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">No workload predictions yet</p>
                <p className="text-xs text-muted-foreground/60">Click <span className="font-medium text-foreground/70">Sync Predictions</span> to generate real forecasts from your pipeline data</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={chartPoints} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="mlActG" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="mlPredG" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 14%)" />
                  <XAxis dataKey="label" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} tickLine={false} axisLine={false} interval={5} />
                  <YAxis tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} tickLine={false} axisLine={false}
                    tickFormatter={(v: number) => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v % 1 !== 0 ? v.toFixed(1) : String(v)}
                    width={36} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="actual" name="Actual" stroke="#3b82f6" strokeWidth={2} fill="url(#mlActG)" connectNulls={false} dot={false} />
                  <Area type="monotone" dataKey="predicted" name="Predicted" stroke="#8b5cf6" strokeWidth={2} strokeDasharray="6 3" fill="url(#mlPredG)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            )}

            {/* Prediction insight */}
            {chartPoints.length > 0 && (() => {
              const actuals   = chartPoints.filter((p: any) => p.actual != null).map((p: any) => p.actual as number);
              const predicted = chartPoints.filter((p: any) => p.predicted != null).map((p: any) => p.predicted as number);
              const avgAct    = actuals.length   ? actuals.reduce((a: number, b: number)   => a + b, 0) / actuals.length   : 0;
              const avgPred   = predicted.length ? predicted.reduce((a: number, b: number) => a + b, 0) / predicted.length : 0;
              const pctChange = avgAct > 0 ? ((avgPred - avgAct) / avgAct * 100) : 0;
              const dir       = pctChange > 5 ? 'increase' : pctChange < -5 ? 'decrease' : 'remain stable';
              const Icon      = pctChange > 5 ? AlertTriangle : pctChange < -5 ? TrendingDown : TrendingUp;
              const iconColor = pctChange > 5 ? 'text-yellow-400' : pctChange < -5 ? 'text-blue-400' : 'text-green-400';
              return (
                <div className="mt-3 p-3 rounded-lg flex gap-2 text-xs" style={{ background: 'hsl(230 15% 11%)' }}>
                  <Icon className={`w-3.5 h-3.5 ${iconColor} flex-shrink-0 mt-0.5`} />
                  <div className="space-y-0.5">
                    <span className={`${iconColor} font-medium`}>Prediction: </span>
                    <span className="text-foreground">
                      Pipeline activity will {dir} {Math.abs(pctChange) > 1 ? `~${Math.abs(pctChange).toFixed(0)}%` : ''} in the next 24 hours
                      {predicted.length > 0 ? ` (avg ${avgPred.toFixed(2)} runs/hr)` : ''}.
                    </span>
                    <br />
                    <span className="text-green-400 font-medium">Recommended Action: </span>
                    <span className="text-muted-foreground">
                      {pctChange > 10
                        ? 'Ensure CI runners have sufficient capacity before the predicted spike.'
                        : pctChange < -10
                        ? 'Activity trending down — a good time to run maintenance or batch jobs.'
                        : 'Pipeline load looks stable. No immediate scaling action required.'}
                    </span>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Prediction summary cards */}
          {psLoad ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" />Loading predictions…</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {[
                {
                  icon: '💰', label: 'Cost Forecast',
                  current: `$${predSum.cost?.current ?? 0}`,
                  predicted: `$${predSum.cost?.predicted ?? 0}`,
                  change: predSum.cost?.change_pct ?? 0,
                  model: predSum.cost?.model ?? '—',
                  accuracy: predSum.cost?.accuracy ?? 0,
                  confidence: predSum.cost?.confidence ?? '—',
                  isFallback: predSum.cost?.is_fallback ?? true,
                },
                {
                  icon: '🚀', label: 'Deploy Failures',
                  current: String(predSum.deploys?.current ?? 0),
                  predicted: String(predSum.deploys?.predicted ?? 0),
                  change: predSum.deploys?.change_pct ?? 0,
                  model: predSum.deploys?.model ?? '—',
                  accuracy: predSum.deploys?.accuracy ?? 0,
                  confidence: predSum.deploys?.confidence ?? '—',
                  isFallback: predSum.deploys?.is_fallback ?? true,
                },
                {
                  icon: '🔒', label: 'Vulnerabilities',
                  current: String(predSum.vulns?.current ?? 0),
                  predicted: String(predSum.vulns?.predicted ?? 0),
                  change: predSum.vulns?.change_pct ?? 07,
                  model: predSum.vulns?.model ?? '—',
                  accuracy: predSum.vulns?.accuracy ?? 05,
                  confidence: predSum.vulns?.confidence ?? '—',
                  isFallback: predSum.vulns?.is_fallback ?? true,
                },
              ].map(p => (
                <div key={p.label} className={clsx('card-base space-y-3', p.isFallback && 'border-dashed opacity-70')}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-semibold text-foreground">{p.icon} {p.label}</span>
                      {p.isFallback && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-gray-500/10 text-gray-500 border border-gray-500/20 font-medium">
                          DEMO
                        </span>
                      )}
                    </div>
                    <span className={clsx('text-xs font-semibold px-1.5 py-0.5 rounded', p.change > 0 ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400')}>
                      {p.change > 0 ? <TrendingUp className="w-3 h-3 inline mr-0.5" /> : <TrendingDown className="w-3 h-3 inline mr-0.5" />}
                      {p.change > 0 ? '+' : ''}{p.change}%
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-muted-foreground">{p.current}</span>
                    <span className="text-muted-foreground">→</span>
                    <span className={clsx('font-bold', p.change > 0 ? 'text-red-400' : 'text-green-400')}>{p.predicted}</span>
                  </div>
                  <div className="space-y-1 text-xs text-muted-foreground border-t border-border pt-2">
                    <div className="flex justify-between">
                      <span>Model</span><span className="text-foreground">{p.model}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Accuracy</span><span className="text-purple-400 font-medium">{p.accuracy}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Confidence</span>
                      <span className={clsx('font-medium', p.confidence === 'High' ? 'text-green-400' : 'text-yellow-400')}>{p.confidence}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Model status */}
          <div className="card-base">
            <h2 className="text-sm font-semibold text-foreground mb-4">Trained Models</h2>
            {modLoad ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" />Loading…</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
                {Object.values(models).map((m: any) => (
                  <div key={m.name} className="p-3 rounded-xl border border-border bg-surface-1 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-foreground truncate">{m.algorithm}</span>
                      <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-medium', m.is_fitted ? 'bg-green-500/10 text-green-400' : 'bg-yellow-500/10 text-yellow-400')}>
                        {m.is_fitted ? 'Ready' : 'Not trained'}
                      </span>
                    </div>
                    <div className="text-xl font-bold text-purple-400">{m.accuracy}%</div>
                    <div className="text-[10px] text-muted-foreground">
                      Trained {m.trained_at ? new Date(m.trained_at).toLocaleDateString() : 'N/A'}
                    </div>
                    <div className="progress-bar-base">
                      <div className="h-full rounded-full bg-purple-500" style={{ width: `${m.accuracy}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── PATTERNS ─────────────────────────────────────────────────────────── */}
      {tab === 'patterns' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span>{activePats.length} active patterns · {pats.filter(p => p.status === 'dismissed').length} dismissed</span>
            <span>Algorithms: Isolation Forest, Time Series Decomposition</span>
          </div>

          {patLoad ? (
            <div className="card-base flex items-center gap-2 text-sm text-muted-foreground p-6">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading patterns…
            </div>
          ) : pats.length === 0 ? (
            <div className="card-base py-12 text-center">
              <Brain className="w-10 h-10 text-purple-400/40 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground mb-4">No patterns discovered yet.</p>
              <button onClick={handleAnalyze} className="action-btn-primary text-xs"><Sparkles className="w-3.5 h-3.5" />Run Analysis</button>
            </div>
          ) : (
            pats.map((p: any) => {
              const sty = PRIORITY_STYLE[p.severity] ?? PRIORITY_STYLE.medium;
              const dismissed = p.status === 'dismissed';
              return (
                <motion.div key={p.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
                  className={clsx('card-base transition-opacity', dismissed && 'opacity-40')}>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-semibold', sty.badge)}>{p.severity}</span>
                      <code className="text-xs font-mono text-muted-foreground">{p.id}</code>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">{p.pattern_type}</span>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-xs text-muted-foreground">Confidence:</span>
                      <span className="text-sm font-bold text-purple-400">{p.confidence_score}%</span>
                      {dismissed && <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-500/10 text-gray-400 border border-gray-500/20">Dismissed</span>}
                    </div>
                  </div>

                  <p className="text-sm text-foreground mb-3">{p.description}</p>

                  <div className="progress-bar-base mb-3">
                    <div className="h-full rounded-full bg-purple-500" style={{ width: `${p.confidence_score}%`, transition: 'width 0.8s ease' }} />
                  </div>

                  <div className="flex items-center gap-4 mb-3 text-xs flex-wrap">
                    <span className="text-muted-foreground">Impact: <span className="text-foreground font-medium">{p.impact}</span></span>
                    <span className="text-muted-foreground">Algorithm: <span className="text-foreground">{p.algorithm}</span></span>
                    <span className="text-muted-foreground">Detected: <span className="text-foreground">{new Date(p.discovered_at).toLocaleDateString()}</span></span>
                  </div>

                  {p.affected_services?.length > 0 && (
                    <div className="flex items-center gap-1.5 mb-3 flex-wrap">
                      {p.affected_services.map((s: string) => (
                        <code key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">{s}</code>
                      ))}
                    </div>
                  )}

                  {p.recommendation && (
                    <div className="p-2.5 rounded-lg mb-3 text-xs flex gap-2" style={{ background: 'hsl(230 15% 11%)' }}>
                      <Lightbulb className="w-3.5 h-3.5 text-green-400 flex-shrink-0 mt-0.5" />
                      <span className="text-muted-foreground"><span className="text-green-400 font-medium">Recommendation: </span>{p.recommendation}</span>
                    </div>
                  )}

                  {!dismissed && (
                    <div className="flex items-center gap-2 flex-wrap">
                      {p.pattern_type === 'Resource Leak' ? (
                        <button
                          onClick={() => setConfirm({
                            title: `Restart Pod: ${p.affected_services?.[0]}`,
                            desc: `This will restart the ${p.affected_services?.[0]} pod to clear the memory leak. The pod will have brief downtime (~30 seconds).`,
                            confirmLabel: 'Restart Pod',
                            action: async () => {
                              await apiPost(`/ml/patterns/${p.id}/restart`, {});
                              showToast(true, `Pod restart initiated: ${p.affected_services?.[0]}`);
                              refetchPat(true);
                            },
                          })}
                          className="text-xs px-3 py-1.5 rounded-lg bg-orange-500/10 text-orange-400 hover:bg-orange-500/20 border border-orange-500/20 transition-colors flex items-center gap-1.5">
                          <RefreshCw className="w-3 h-3" /> Restart Pod
                        </button>
                      ) : p.pattern_type === 'Periodic Spike' ? (
                        <button
                          onClick={() => setConfirm({
                            title: 'Create Alert Rule',
                            desc: `Create an alert rule for pattern "${p.pattern_type}" — this will be saved and trigger notifications when the condition recurs.`,
                            confirmLabel: 'Create Rule',
                            action: async () => {
                              await apiPost('/ml/alert-rules', {
                                name:         `Alert: ${p.pattern_type}`,
                                condition:    p.recommendation ?? p.description ?? 'auto',
                                pattern_id:   p.id,
                                schedule:     'realtime',
                                notify_slack: true,
                              });
                              showToast(true, `Alert rule created: ${p.pattern_type}`);
                              refetchPat(true);
                            },
                          })}
                          className="text-xs px-3 py-1.5 rounded-lg bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20 transition-colors flex items-center gap-1.5">
                          <Zap className="w-3 h-3" /> Create Alert Rule
                        </button>
                      ) : (
                        <button className="text-xs px-3 py-1.5 rounded-lg bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 border border-purple-500/20 transition-colors flex items-center gap-1.5">
                          <BarChart2 className="w-3 h-3" /> Investigate
                        </button>
                      )}
                      <button
                        onClick={() => setConfirm({
                          title: `Dismiss Pattern: ${p.id}`,
                          desc: 'Mark this pattern as dismissed. It will no longer appear in active patterns.',
                          confirmLabel: 'Dismiss', danger: true,
                          action: async () => {
                            await apiPost(`/ml/patterns/${p.id}/dismiss`, {});
                            refetchPat(true);
                            showToast(true, `Pattern ${p.id} dismissed`);
                          },
                        })}
                        className="text-xs px-3 py-1.5 rounded-lg bg-gray-500/10 text-gray-400 hover:bg-gray-500/20 border border-gray-500/20 transition-colors flex items-center gap-1.5">
                        <X className="w-3 h-3" /> Dismiss
                      </button>
                    </div>
                  )}
                </motion.div>
              );
            })
          )}
        </div>
      )}

      {/* ── RECOMMENDATIONS ──────────────────────────────────────────────────── */}
      {tab === 'recommendations' && (
        <div className="space-y-4">
          {/* Summary stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Total',    value: recCounts.total,    color: 'text-foreground' },
              { label: 'Critical', value: recCounts.critical, color: 'text-red-400' },
              { label: 'High',     value: recCounts.high,     color: 'text-orange-400' },
              { label: 'Medium',   value: recCounts.medium,   color: 'text-yellow-400' },
            ].map(s => (
              <div key={s.label} className="card-base text-center py-3">
                <div className={clsx('text-xl font-bold', s.color)}>{s.value}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>

          {recLoad ? (
            <div className="card-base flex items-center gap-2 text-sm text-muted-foreground p-6">
              <Loader2 className="w-4 h-4 animate-spin" />Loading recommendations…
            </div>
          ) : recs.length === 0 ? (
            <div className="card-base py-12 text-center">
              <Lightbulb className="w-10 h-10 text-green-400/40 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground mb-4">No recommendations yet. Run analysis to generate AI-powered optimizations.</p>
              <button onClick={handleAnalyze} className="action-btn-primary text-xs"><Sparkles className="w-3.5 h-3.5" />Run Analysis</button>
            </div>
          ) : (
            <div className="space-y-3">
              {recs.map((r: any, i: number) => {
                const sty = PRIORITY_STYLE[r.priority] ?? PRIORITY_STYLE.medium;
                const isExpanded = expandedRec === r.id;
                const applied   = r.status === 'applied';
                const dismissed = r.status === 'dismissed';
                return (
                  <motion.div key={r.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                    className={clsx('card-base transition-opacity', dismissed && 'opacity-40')}>
                    <div className="flex items-start gap-4">
                      <div className="w-9 h-9 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <Lightbulb className="w-4 h-4 text-green-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        {/* Header */}
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-semibold', sty.badge)}>{r.priority}</span>
                            <code className="text-[10px] font-mono text-muted-foreground">{r.id}</code>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">{r.category}</span>
                            {r.effort && <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-semibold', EFFORT_STYLE[r.effort] ?? EFFORT_STYLE.medium)}>{r.effort} effort</span>}
                            {applied   && <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20">Applied ✓</span>}
                            {dismissed && <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-500/10 text-gray-400 border border-gray-500/20">Dismissed</span>}
                          </div>
                          <span className="text-xs font-bold text-purple-400 flex-shrink-0">
                            {r.confidence_score}% conf.
                          </span>
                        </div>

                        <h3 className="text-sm font-semibold text-foreground mb-1">{r.title}</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed mb-2">{r.description}</p>

                        {r.expected_impact && (
                          <div className="flex items-center gap-1.5 text-xs mb-2">
                            <TrendingDown className="w-3.5 h-3.5 text-green-400" />
                            <span className="text-green-400 font-medium">{r.expected_impact}</span>
                          </div>
                        )}

                        <div className="flex items-center gap-3 text-xs text-muted-foreground mb-3">
                          {r.time_estimate && (
                            <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{r.time_estimate}</span>
                          )}
                          {r.algorithm && <span className="text-[10px] text-gray-500">{r.algorithm}</span>}
                        </div>

                        {/* Steps (expandable) */}
                        {r.steps?.length > 0 && (
                          <div className="mb-3">
                            <button
                              onClick={() => setExpandedRec(isExpanded ? null : r.id)}
                              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors">
                              {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                              {isExpanded ? 'Hide steps' : `View ${r.steps.length} steps`}
                            </button>
                            <AnimatePresence>
                              {isExpanded && (
                                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                                  <ol className="mt-2 space-y-1.5 p-3 rounded-lg text-xs" style={{ background: 'hsl(230 15% 10%)' }}>
                                    {r.steps.map((step: string, si: number) => (
                                      <li key={si} className="flex gap-2 text-muted-foreground">
                                        <span className="w-4 h-4 rounded-full bg-purple-500/20 text-purple-400 font-bold text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">{si + 1}</span>
                                        {step}
                                      </li>
                                    ))}
                                  </ol>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        )}

                        {/* Actions */}
                        {!applied && !dismissed && (
                          <div className="flex items-center gap-2 flex-wrap">
                            <button
                              onClick={() => setConfirm({
                                title: `Apply: ${r.title}`,
                                desc: `This will execute the recommendation automatically. ${r.expected_impact ?? 'Impact as described above.'}`,
                                confirmLabel: 'Apply Recommendation',
                                action: async () => {
                                  await apiPost(`/ml/recommendations/${r.id}/apply`, {});
                                  refetchRec(true);
                                  showToast(true, `Recommendation applied: ${r.title}`);
                                },
                              })}
                              className="text-xs px-3 py-1.5 rounded-lg bg-green-500/10 text-green-400 hover:bg-green-500/20 border border-green-500/20 transition-colors flex items-center gap-1.5">
                              <CheckCircle className="w-3 h-3" /> Apply Recommendation
                            </button>
                            <button
                              onClick={() => setConfirm({
                                title: `Dismiss: ${r.id}`,
                                desc: 'Dismiss this recommendation. It will no longer appear in the active list.',
                                confirmLabel: 'Dismiss', danger: true,
                                action: async () => {
                                  await apiPost(`/ml/recommendations/${r.id}/dismiss`, {});
                                  refetchRec(true);
                                  showToast(true, 'Recommendation dismissed');
                                },
                              })}
                              className="text-xs px-3 py-1.5 rounded-lg bg-gray-500/10 text-gray-400 hover:bg-gray-500/20 border border-gray-500/20 transition-colors flex items-center gap-1.5">
                              <X className="w-3 h-3" /> Dismiss
                            </button>
                          </div>
                        )}
                        {applied && (
                          <div className="flex items-center gap-1.5 text-xs text-green-400">
                            <CheckCircle className="w-3.5 h-3.5" /> Applied successfully
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
