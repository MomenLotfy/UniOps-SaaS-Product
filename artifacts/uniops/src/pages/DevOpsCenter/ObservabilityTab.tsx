// ─────────────────────────────────────────────────────────────────────────────
// ObservabilityTab — Metrics + Logs (Epic 3)
// Pulls from K8s Metrics API; graceful empty state when not connected.
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Legend,
} from 'recharts';
import {
  Activity, FileText, Search, RefreshCw, Loader2,
  AlertTriangle, Info, ChevronDown, Circle,
  Cpu, MemoryStick, Wifi, WifiOff,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';

// ── Types ────────────────────────────────────────────────────────────────────

type ObsTab    = 'metrics' | 'logs';
type TimeRange = '15m' | '1h' | '6h' | '24h' | '7d' | '30d';
type LogLevel  = 'ALL' | 'INFO' | 'WARN' | 'ERROR';

interface TimePoint { timestamp: string; value: number }
interface PodMetric {
  name: string; namespace: string; status: string;
  cpu_pct: number; memory_pct: number;
  cpu_timeseries: TimePoint[]; memory_timeseries: TimePoint[];
}
interface LogLine { timestamp?: string; level: string; message: string; raw: string }

// ── Constants ────────────────────────────────────────────────────────────────

const RANGES: TimeRange[] = ['15m', '1h', '6h', '24h', '7d', '30d'];

const LEVEL_COLORS: Record<string, string> = {
  ERROR: 'text-red-400',
  WARN:  'text-yellow-400',
  INFO:  'text-blue-400',
};
const LEVEL_BG: Record<string, string> = {
  ERROR: 'bg-red-500/10',
  WARN:  'bg-yellow-500/10',
  INFO:  'bg-transparent',
};

// ── Chart helpers ─────────────────────────────────────────────────────────────

const chartStyle = {
  background:  'transparent',
  fontSize:    11,
  color:       '#6b7280',
};

function formatTs(ts: string, range: TimeRange): string {
  try {
    const d = new Date(ts);
    if (range === '7d' || range === '30d')
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch { return ts; }
}

interface MetricAreaProps {
  data: TimePoint[];
  color: string;
  label: string;
  range: TimeRange;
  unit?: string;
}
function MetricArea({ data, color, label, range, unit = '%' }: MetricAreaProps) {
  const chartData = data.map(d => ({ ...d, ts: formatTs(d.timestamp, range) }));
  const current = data[data.length - 1]?.value ?? 0;
  return (
    <div className="rounded-xl border p-4" style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-gray-400">{label}</span>
        <span className={clsx('text-lg font-bold tabular-nums', color)}>{current.toFixed(1)}{unit}</span>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color.replace('text-', '#').replace('-400', '')} stopOpacity={0.25} />
              <stop offset="95%" stopColor={color.replace('text-', '#').replace('-400', '')} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 13%)" vertical={false} />
          <XAxis dataKey="ts" tick={{ fill: '#4b5563', fontSize: 10 }} tickLine={false} axisLine={false}
            interval="preserveStartEnd" />
          <YAxis domain={[0, 100]} tick={{ fill: '#4b5563', fontSize: 10 }} tickLine={false} axisLine={false}
            tickFormatter={v => `${v}%`} />
          <Tooltip
            contentStyle={{ background: 'hsl(230 18% 12%)', border: '1px solid hsl(230 15% 20%)', borderRadius: 8, fontSize: 11 }}
            labelStyle={{ color: '#9ca3af' }}
            itemStyle={{ color: '#e5e7eb' }}
            formatter={(v: number) => [`${v.toFixed(1)}${unit}`, label]}
          />
          <Area
            type="monotone" dataKey="value" stroke={resolveColor(color)}
            fill={`url(#grad-${label})`} strokeWidth={1.5} dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function resolveColor(tailwindColor: string): string {
  const map: Record<string, string> = {
    'text-blue-400':   '#60a5fa',
    'text-green-400':  '#4ade80',
    'text-purple-400': '#c084fc',
    'text-yellow-400': '#facc15',
    'text-red-400':    '#f87171',
    'text-cyan-400':   '#22d3ee',
  };
  return map[tailwindColor] ?? '#60a5fa';
}

// ── Namespace bar chart ────────────────────────────────────────────────────────

function NamespaceChart({ data }: { data: any[] }) {
  if (!data.length) return null;
  return (
    <div className="rounded-xl border p-4" style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
      <p className="text-xs font-medium text-gray-400 mb-3">CPU & Memory by Namespace</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 2, right: 2, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 13%)" vertical={false} />
          <XAxis dataKey="namespace" tick={{ fill: '#4b5563', fontSize: 10 }} tickLine={false} axisLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: '#4b5563', fontSize: 10 }} tickLine={false} axisLine={false}
            tickFormatter={v => `${v}%`} />
          <Tooltip
            contentStyle={{ background: 'hsl(230 18% 12%)', border: '1px solid hsl(230 15% 20%)', borderRadius: 8, fontSize: 11 }}
            labelStyle={{ color: '#9ca3af' }}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: '#6b7280' }} />
          <Bar dataKey="cpu_pct"    name="CPU %"    fill="#60a5fa" radius={[3,3,0,0]} maxBarSize={30} />
          <Bar dataKey="memory_pct" name="Memory %" fill="#c084fc" radius={[3,3,0,0]} maxBarSize={30} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Pod metrics table ─────────────────────────────────────────────────────────

function PodRow({ pod }: { pod: PodMetric }) {
  const cpuColor  = pod.cpu_pct >= 80 ? 'text-red-400' : pod.cpu_pct >= 60 ? 'text-yellow-400' : 'text-green-400';
  const memColor  = pod.memory_pct >= 80 ? 'text-red-400' : pod.memory_pct >= 60 ? 'text-yellow-400' : 'text-purple-400';
  return (
    <tr className="border-b transition-colors hover:bg-white/2" style={{ borderColor: 'hsl(230 15% 13%)' }}>
      <td className="px-4 py-2.5 text-xs font-mono text-white">{pod.name}</td>
      <td className="px-4 py-2.5 text-xs text-gray-400">{pod.namespace}</td>
      <td className="px-4 py-2.5">
        <span className={clsx('text-xs', pod.status === 'Running' ? 'text-green-400' : 'text-yellow-400')}>{pod.status}</span>
      </td>
      <td className="px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className={clsx('text-xs font-mono font-bold w-10', cpuColor)}>{pod.cpu_pct.toFixed(0)}%</span>
          <div className="w-20 h-1.5 rounded-full bg-white/5 overflow-hidden">
            <div className={clsx('h-full rounded-full', pod.cpu_pct >= 80 ? 'bg-red-500' : pod.cpu_pct >= 60 ? 'bg-yellow-500' : 'bg-green-500')}
              style={{ width: `${Math.min(pod.cpu_pct, 100)}%` }} />
          </div>
        </div>
      </td>
      <td className="px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className={clsx('text-xs font-mono font-bold w-10', memColor)}>{pod.memory_pct.toFixed(0)}%</span>
          <div className="w-20 h-1.5 rounded-full bg-white/5 overflow-hidden">
            <div className={clsx('h-full rounded-full', pod.memory_pct >= 80 ? 'bg-red-500' : pod.memory_pct >= 60 ? 'bg-yellow-500' : 'bg-purple-500')}
              style={{ width: `${Math.min(pod.memory_pct, 100)}%` }} />
          </div>
        </div>
      </td>
    </tr>
  );
}

// ── Metrics sub-tab ───────────────────────────────────────────────────────────

function MetricsPane({ k8sConnected }: { k8sConnected: boolean }) {
  const [range, setRange] = useState<TimeRange>('1h');

  const { data: clusterRaw, loading: clusterLoading, refetch: refetchCluster } =
    useApi<any>(`/observability/metrics/cluster?range=${range}`);
  const { data: podsRaw, loading: podsLoading } =
    useApi<any>(`/observability/metrics/pods?range=${range}&top=10`);
  const { data: nsRaw } =
    useApi<any>('/observability/metrics/namespaces');

  const clusterData  = clusterRaw?.data  ?? clusterRaw;
  const podsData     = (podsRaw?.data?.pods ?? podsRaw?.pods ?? []) as PodMetric[];
  const nsData       = nsRaw?.data ?? nsRaw ?? [];

  const cpuSeries    = clusterData?.cpu?.timeseries    ?? [];
  const memorySeries = clusterData?.memory?.timeseries ?? [];

  if (!k8sConnected) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Activity className="w-12 h-12 text-gray-700 mb-3" />
        <p className="text-sm font-medium text-gray-400 mb-1">Kubernetes not connected</p>
        <p className="text-xs text-gray-600 mb-4">Connect your cluster to view real-time metrics</p>
        <a href="/settings/integrations"
          className="px-4 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors">
          Connect Kubernetes
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Time range selector */}
      <div className="flex items-center gap-1 p-1 rounded-lg w-fit" style={{ background: 'hsl(230 15% 10%)' }}>
        {RANGES.map(r => (
          <button key={r} onClick={() => setRange(r)}
            className={clsx('px-3 py-1.5 rounded-md text-xs font-medium transition-all',
              range === r ? 'text-white' : 'text-gray-500 hover:text-gray-300')}
            style={range === r ? { background: 'hsl(230 15% 16%)' } : {}}>
            {r}
          </button>
        ))}
      </div>

      {/* Cluster-level charts */}
      {clusterLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1,2].map(i => <div key={i} className="rounded-xl border p-4 h-48 animate-pulse" style={{ borderColor: 'hsl(230 15% 15%)', background: 'hsl(230 18% 9%)' }} />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <MetricArea data={cpuSeries}    color="text-blue-400"   label="Cluster CPU Usage"    range={range} />
          <MetricArea data={memorySeries} color="text-purple-400" label="Cluster Memory Usage" range={range} />
        </div>
      )}

      {/* Namespace breakdown */}
      {nsData.length > 0 && <NamespaceChart data={nsData} />}

      {/* Pod metrics table */}
      <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'hsl(230 15% 15%)' }}>
        <div className="flex items-center gap-2 px-5 py-3 border-b" style={{ borderColor: 'hsl(230 15% 15%)', background: 'hsl(230 18% 9%)' }}>
          <Cpu className="w-4 h-4 text-blue-400" />
          <span className="text-xs font-semibold text-white">Top Pods by Resource Usage</span>
          {podsLoading && <Loader2 className="w-3.5 h-3.5 text-gray-500 animate-spin ml-auto" />}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead style={{ background: 'hsl(230 15% 11%)' }}>
              <tr>
                {['Pod', 'Namespace', 'Status', 'CPU', 'Memory'].map(h => (
                  <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {podsLoading ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-xs text-gray-500">Loading metrics…</td></tr>
              ) : podsData.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-xs text-gray-500">No pod metrics available</td></tr>
              ) : (
                podsData.map(p => <PodRow key={`${p.namespace}/${p.name}`} pod={p} />)
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── Logs sub-tab ──────────────────────────────────────────────────────────────

function LogsPane({ k8sConnected, pods }: { k8sConnected: boolean; pods: any[] }) {
  const [selectedPod, setSelectedPod] = useState<string>('');
  const [search,      setSearch]      = useState('');
  const [level,       setLevel]       = useState<LogLevel>('ALL');
  const [liveTail,    setLiveTail]    = useState(false);
  const [query,       setQuery]       = useState<{ pod?: string; search?: string; level?: string } | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  const apiUrl = query?.pod
    ? `/observability/logs?pod=${encodeURIComponent(query.pod)}` +
      (query.search ? `&search=${encodeURIComponent(query.search)}` : '') +
      (query.level && query.level !== 'ALL' ? `&level=${query.level}` : '') +
      '&tail=300'
    : null;

  const { data: logsRaw, loading, refetch } = useApi<any>(apiUrl);
  const logsData = logsRaw?.data ?? logsRaw;
  const lines: LogLine[] = logsData?.lines ?? [];

  // Auto-scroll to bottom
  useEffect(() => {
    if (lines.length > 0) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [lines.length]);

  // Live tail
  useEffect(() => {
    if (!liveTail || !apiUrl) return;
    const id = setInterval(() => refetch(true), 3000);
    return () => clearInterval(id);
  }, [liveTail, apiUrl, refetch]);

  const handleApply = useCallback(() => {
    if (!selectedPod) return;
    setQuery({
      pod: selectedPod,
      search: search || undefined,
      level: level !== 'ALL' ? level : undefined,
    });
  }, [selectedPod, search, level]);

  if (!k8sConnected) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <FileText className="w-12 h-12 text-gray-700 mb-3" />
        <p className="text-sm font-medium text-gray-400 mb-1">Kubernetes not connected</p>
        <p className="text-xs text-gray-600 mb-4">Connect your cluster to stream pod logs</p>
        <a href="/settings/integrations"
          className="px-4 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors">
          Connect Kubernetes
        </a>
      </div>
    );
  }

  const inputCls = "px-3 py-2 rounded-lg text-xs text-white border outline-none focus:border-blue-500/50 transition-colors";
  const inputStyle = { background: 'hsl(230 15% 11%)', borderColor: 'hsl(230 15% 18%)' };

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex flex-wrap items-end gap-2 p-4 rounded-xl border" style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
        {/* Pod selector */}
        <div className="flex-1 min-w-48">
          <label className="block text-xs text-gray-500 mb-1.5">Pod</label>
          <div className="relative">
            <select
              value={selectedPod}
              onChange={e => setSelectedPod(e.target.value)}
              className={clsx(inputCls, 'w-full appearance-none pr-8')}
              style={inputStyle}
            >
              <option value="">Select a pod…</option>
              {pods.map((p: any) => {
                const id = `${p.namespace ?? 'default'}/${p.name}`;
                return <option key={id} value={id}>{p.name}</option>;
              })}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-500 pointer-events-none" />
          </div>
        </div>

        {/* Search */}
        <div className="flex-1 min-w-40">
          <label className="block text-xs text-gray-500 mb-1.5">Search</label>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleApply()}
              placeholder="Filter logs…"
              className={clsx(inputCls, 'w-full pl-8')}
              style={inputStyle}
            />
          </div>
        </div>

        {/* Level */}
        <div className="w-28">
          <label className="block text-xs text-gray-500 mb-1.5">Level</label>
          <div className="relative">
            <select
              value={level}
              onChange={e => setLevel(e.target.value as LogLevel)}
              className={clsx(inputCls, 'w-full appearance-none pr-8')}
              style={inputStyle}
            >
              {(['ALL','INFO','WARN','ERROR'] as LogLevel[]).map(l => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-500 pointer-events-none" />
          </div>
        </div>

        {/* Apply */}
        <button onClick={handleApply} disabled={!selectedPod}
          className="px-4 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-40 flex items-center gap-1.5">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
          Load
        </button>

        {/* Live tail toggle */}
        <button
          onClick={() => setLiveTail(v => !v)}
          disabled={!selectedPod}
          className={clsx('flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-all',
            liveTail
              ? 'text-green-400 border-green-500/30 bg-green-500/5'
              : 'text-gray-400 border-white/10 hover:text-white')}
        >
          {liveTail ? <Wifi className="w-3 h-3 animate-pulse" /> : <WifiOff className="w-3 h-3" />}
          {liveTail ? 'Live' : 'Tail'}
        </button>

        {lines.length > 0 && (
          <div className="ml-auto text-xs text-gray-500">
            {logsData?.filtered ?? lines.length} / {logsData?.total ?? lines.length} lines
          </div>
        )}
      </div>

      {/* Log viewer */}
      <div
        className="rounded-xl border overflow-hidden"
        style={{ background: 'hsl(230 18% 7%)', borderColor: 'hsl(230 15% 14%)' }}
      >
        {/* Status bar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b text-xs" style={{ borderColor: 'hsl(230 15% 12%)', background: 'hsl(230 15% 9%)' }}>
          <FileText className="w-3.5 h-3.5 text-gray-500" />
          <span className="text-gray-500">{selectedPod || 'No pod selected'}</span>
          {liveTail && <span className="flex items-center gap-1 text-green-400 ml-auto"><Circle className="w-2 h-2 fill-green-400" />Live</span>}
          {loading && <RefreshCw className="w-3 h-3 text-gray-500 animate-spin ml-auto" />}
        </div>

        {/* Lines */}
        <div className="h-96 overflow-y-auto font-mono text-xs p-3 space-y-0.5">
          {!query?.pod ? (
            <div className="flex items-center justify-center h-full text-gray-600">
              <p>Select a pod and click Load</p>
            </div>
          ) : loading && lines.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-5 h-5 text-gray-500 animate-spin" />
            </div>
          ) : lines.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-600">
              <p>No logs found</p>
            </div>
          ) : (
            lines.map((l, i) => (
              <div key={i}
                className={clsx('flex gap-2 rounded px-2 py-0.5 hover:bg-white/3 transition-colors', LEVEL_BG[l.level])}
              >
                <span className="text-gray-600 select-none w-5 text-right flex-shrink-0">{i + 1}</span>
                {l.timestamp && (
                  <span className="text-gray-600 flex-shrink-0">{l.timestamp.replace('T', ' ').slice(0, 19)}</span>
                )}
                <span className={clsx('flex-shrink-0 w-10 font-bold uppercase', LEVEL_COLORS[l.level] ?? 'text-gray-400')}>
                  {l.level}
                </span>
                <span className="text-gray-300 break-all">{l.message || l.raw}</span>
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}

// ── Main ObservabilityTab ─────────────────────────────────────────────────────

interface ObservabilityTabProps {
  k8sConnected: boolean;
  pods:         any[];
}

export function ObservabilityTab({ k8sConnected, pods }: ObservabilityTabProps) {
  const [tab, setTab] = useState<ObsTab>('metrics');

  const SUB_TABS = [
    { id: 'metrics' as ObsTab, label: 'Metrics', icon: Activity },
    { id: 'logs'    as ObsTab, label: 'Logs',    icon: FileText },
  ];

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
      {/* Sub-tab bar */}
      <div className="flex gap-1 mb-4 p-1 rounded-lg w-fit" style={{ background: 'hsl(230 15% 10%)' }}>
        {SUB_TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={clsx('flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-medium transition-all',
              tab === t.id ? 'text-white' : 'text-gray-500 hover:text-gray-300')}
            style={tab === t.id ? { background: 'hsl(230 15% 16%)' } : {}}>
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'metrics' && <MetricsPane k8sConnected={k8sConnected} />}
      {tab === 'logs'    && <LogsPane k8sConnected={k8sConnected} pods={pods} />}
    </motion.div>
  );
}
