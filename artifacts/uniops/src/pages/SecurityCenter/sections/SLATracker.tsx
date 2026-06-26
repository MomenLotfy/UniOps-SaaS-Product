import { useState } from 'react';
import { Clock, AlertTriangle, CheckCircle2, Loader2, RefreshCw, Filter, Bug, Shield, Timer } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const SEV_COLOR: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-green-400',
};
const SEV_BG: Record<string, string> = {
  critical: 'bg-red-400/10 border-red-400/20',
  high:     'bg-orange-400/10 border-orange-400/20',
  medium:   'bg-yellow-400/10 border-yellow-400/20',
  low:      'bg-green-400/10 border-green-400/20',
};

const SLA_WINDOWS = [
  { severity: 'critical', label: 'Critical',  hours: 24,       color: 'text-red-400',    bg: 'bg-red-400/10 border-red-400/20' },
  { severity: 'high',     label: 'High',      hours: 7 * 24,   color: 'text-orange-400', bg: 'bg-orange-400/10 border-orange-400/20' },
  { severity: 'medium',   label: 'Medium',    hours: 30 * 24,  color: 'text-yellow-400', bg: 'bg-yellow-400/10 border-yellow-400/20' },
  { severity: 'low',      label: 'Low',       hours: 90 * 24,  color: 'text-green-400',  bg: 'bg-green-400/10 border-green-400/20' },
];

function fmtHours(h: number | null | undefined): string {
  if (h == null) return '—';
  const ah = Math.abs(h);
  if (ah < 1)    return `${Math.round(ah * 60)}m`;
  if (ah < 48)   return `${ah.toFixed(0)}h`;
  return `${(ah / 24).toFixed(0)}d`;
}

interface SLAFinding {
  id: string;
  entity_type: string;
  entity_id:   string;
  severity:    string;
  title:       string;
  status:      string;
  is_overdue:  boolean;
  is_breached: boolean;
  detected_at: string;
  sla_due_at:  string;
  sla_hours:   number;
  overdue_hours?:    number | null;
  remaining_hours?:  number | null;
  owner?:      string | null;
  team?:       string | null;
  department?: string | null;
}

interface SLASummary {
  total_open:   number;
  overdue:      number;
  due_soon_24h: number;
  by_severity:  Record<string, { total: number; overdue: number; sla_hours: number }>;
}

export default function SLATracker() {
  const [filter, setFilter]         = useState<'all' | 'overdue' | 'due_soon'>('all');
  const [severityFilter, setSev]    = useState('');
  const [entityFilter, setEntity]   = useState('');
  const [syncing, setSyncing]       = useState(false);

  const { data: sumRaw, loading: sumLoading, refetch: refetchSum } = useApi<any>('/sla/summary');
  const summary: SLASummary | null = sumRaw?.data ?? sumRaw ?? null;

  const params = new URLSearchParams({ limit: '200' });
  if (filter === 'overdue')   params.set('overdue_only', 'true');
  if (severityFilter)         params.set('severity', severityFilter);
  if (entityFilter)           params.set('entity_type', entityFilter);

  const { data: findRaw, loading: findLoading, refetch: refetchFind } = useApi<any>(`/sla/findings?${params}`);
  const findings: SLAFinding[] = Array.isArray(findRaw?.data ?? findRaw) ? (findRaw?.data ?? findRaw) : [];

  const displayed = filter === 'due_soon'
    ? findings.filter(f => !f.is_overdue && f.remaining_hours != null && f.remaining_hours <= 24)
    : findings;

  const handleSync = async () => {
    setSyncing(true);
    try {
      await apiClient.post('/sla/sync');
      await Promise.all([refetchSum(), refetchFind()]);
    } finally { setSyncing(false); }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">SLA Tracker</h1>
          <p className="text-xs text-muted-foreground">
            Track remediation deadlines — Critical 24h · High 7d · Medium 30d · Low 90d
          </p>
        </div>
        <button onClick={handleSync} disabled={syncing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-60">
          {syncing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          {syncing ? 'Syncing…' : 'Sync SLAs'}
        </button>
      </div>

      {/* SLA window reference */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {SLA_WINDOWS.map(({ severity, label, hours, color, bg }) => {
          const sevData = summary?.by_severity?.[severity];
          return (
            <div key={severity} className={clsx('card-base p-4 border', bg)}>
              <div className="flex items-center justify-between mb-2">
                <span className={clsx('text-[11px] font-semibold', color)}>{label}</span>
                <span className={clsx('text-[10px] px-1.5 py-0.5 rounded-full border font-medium', bg, color)}>
                  {hours < 48 ? `${hours}h` : `${hours / 24}d`}
                </span>
              </div>
              {sumLoading ? (
                <Skeleton className="h-8" />
              ) : (
                <div className="flex items-end gap-3">
                  <div>
                    <p className={clsx('text-2xl font-bold', color)}>{sevData?.overdue ?? 0}</p>
                    <p className="text-[10px] text-muted-foreground">overdue</p>
                  </div>
                  <div className="text-right flex-1">
                    <p className="text-sm font-semibold text-foreground">{sevData?.total ?? 0}</p>
                    <p className="text-[10px] text-muted-foreground">total open</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary bar */}
      {summary && (
        <div className="card-base p-4 flex flex-wrap gap-6 items-center">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <div>
              <p className="text-xl font-bold text-red-400">{summary.overdue}</p>
              <p className="text-[10px] text-muted-foreground">Overdue findings</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Timer className="w-4 h-4 text-orange-400" />
            <div>
              <p className="text-xl font-bold text-orange-400">{summary.due_soon_24h}</p>
              <p className="text-[10px] text-muted-foreground">Due in 24h</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-blue-400" />
            <div>
              <p className="text-xl font-bold text-blue-400">{summary.total_open}</p>
              <p className="text-[10px] text-muted-foreground">Total tracked</p>
            </div>
          </div>
          {/* Progress bar: on-time vs overdue */}
          <div className="flex-1 min-w-32">
            <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
              <span>On-time {summary.total_open - summary.overdue}</span>
              <span>Overdue {summary.overdue}</span>
            </div>
            <div className="h-2 rounded-full bg-white/10 overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-green-500 to-red-500" style={{
                background: `linear-gradient(to right, #22c55e ${Math.round(((summary.total_open - summary.overdue) / Math.max(summary.total_open, 1)) * 100)}%, #ef4444 0%)`,
              }} />
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {/* Status filter */}
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {([['all', 'All'], ['overdue', 'Overdue'], ['due_soon', 'Due Soon']] as const).map(([v, label]) => (
            <button key={v} onClick={() => setFilter(v)}
              className={clsx('px-3 py-1.5 text-[11px] font-medium transition-colors',
                filter === v ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              {label}
            </button>
          ))}
        </div>
        {/* Severity filter */}
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {[['', 'All Sev'], ['critical', 'Critical'], ['high', 'High'], ['medium', 'Medium']].map(([v, label]) => (
            <button key={v} onClick={() => setSev(v)}
              className={clsx('px-3 py-1.5 text-[11px] font-medium transition-colors',
                severityFilter === v ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              {label}
            </button>
          ))}
        </div>
        {/* Entity filter */}
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {[['', 'All Types'], ['threat', 'Threats'], ['vulnerability', 'Vulns']].map(([v, label]) => (
            <button key={v} onClick={() => setEntity(v)}
              className={clsx('px-3 py-1.5 text-[11px] font-medium transition-colors',
                entityFilter === v ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Findings table */}
      {findLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
        </div>
      ) : displayed.length === 0 ? (
        <div className="card-base py-14 text-center">
          <CheckCircle2 className="w-8 h-8 text-green-400 opacity-40 mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">
            {filter === 'overdue' ? 'No overdue findings — great work!' : 'No findings match the current filter.'}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Click "Sync SLAs" to pull the latest data.</p>
        </div>
      ) : (
        <div className="card-base overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                {['Finding', 'Severity', 'Type', 'Detected', 'SLA Due', 'Status', 'Owner / Team'].map(h => (
                  <th key={h} className="px-3 py-2.5 text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: 'hsl(230 15% 12%)' }}>
              {displayed.map(f => {
                const dueSoon = !f.is_overdue && f.remaining_hours != null && f.remaining_hours <= 24;
                return (
                  <tr key={f.id}
                    className={clsx('transition-colors',
                      f.is_overdue ? 'bg-red-500/5 hover:bg-red-500/8' :
                      dueSoon      ? 'bg-orange-500/5 hover:bg-orange-500/8' :
                      'hover:bg-white/[0.02]')}>
                    {/* Title */}
                    <td className="px-3 py-2.5 max-w-[200px]">
                      <p className="truncate text-foreground font-medium">{f.title}</p>
                    </td>
                    {/* Severity */}
                    <td className="px-3 py-2.5">
                      <span className={clsx('capitalize text-[11px] font-semibold border px-1.5 py-0.5 rounded',
                        SEV_COLOR[f.severity], SEV_BG[f.severity])}>
                        {f.severity}
                      </span>
                    </td>
                    {/* Entity type */}
                    <td className="px-3 py-2.5">
                      <span className="capitalize text-[11px] text-muted-foreground">{f.entity_type}</span>
                    </td>
                    {/* Detected */}
                    <td className="px-3 py-2.5 text-muted-foreground">
                      {new Date(f.detected_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </td>
                    {/* SLA due + time remaining/overdue */}
                    <td className="px-3 py-2.5">
                      <div>
                        <p className="text-foreground">
                          {new Date(f.sla_due_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                        </p>
                        {f.is_overdue ? (
                          <p className="text-[10px] text-red-400 font-medium">
                            {fmtHours(f.overdue_hours)} overdue
                          </p>
                        ) : (
                          <p className={clsx('text-[10px] font-medium', dueSoon ? 'text-orange-400' : 'text-muted-foreground')}>
                            {fmtHours(f.remaining_hours)} left
                          </p>
                        )}
                      </div>
                    </td>
                    {/* Status badge */}
                    <td className="px-3 py-2.5">
                      {f.is_overdue ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-400/15 text-red-400 border border-red-400/20">
                          <AlertTriangle className="w-2.5 h-2.5" /> Overdue
                        </span>
                      ) : dueSoon ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-orange-400/15 text-orange-400 border border-orange-400/20">
                          <Timer className="w-2.5 h-2.5" /> Due soon
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-400/15 text-green-400 border border-green-400/20">
                          <CheckCircle2 className="w-2.5 h-2.5" /> On track
                        </span>
                      )}
                    </td>
                    {/* Owner / Team */}
                    <td className="px-3 py-2.5">
                      {f.owner || f.team ? (
                        <div>
                          {f.owner && <p className="text-foreground">{f.owner}</p>}
                          {f.team  && <p className="text-[10px] text-muted-foreground">{f.team}</p>}
                        </div>
                      ) : (
                        <span className="text-muted-foreground/40 italic text-[11px]">unassigned</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
