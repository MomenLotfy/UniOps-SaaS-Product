import { memo } from 'react';
import { clsx } from 'clsx';
import {
  Clock, CheckCircle, AlertCircle, Loader2, XCircle,
  ShieldAlert, Activity, Sparkles, GitBranch,
} from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function fmtRelative(dateStr?: string) {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)   return 'just now';
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function fmtDate(dateStr?: string) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
}

function eventIcon(scan: any) {
  const crit = scan.critical ?? 0;
  const high = scan.high ?? 0;
  if (crit > 0) return <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />;
  if (high > 0) return <ShieldAlert  className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />;
  return <CheckCircle className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />;
}

function eventLabel(scan: any) {
  const parts: string[] = [];
  if ((scan.critical ?? 0) > 0) parts.push(`${scan.critical} critical`);
  if ((scan.high ?? 0) > 0)     parts.push(`${scan.high} high`);
  if ((scan.medium ?? 0) > 0)   parts.push(`${scan.medium} medium`);
  if ((scan.secrets ?? 0) > 0)  parts.push(`${scan.secrets} secrets`);
  if (parts.length === 0) return 'No findings';
  return parts.join(' · ');
}

/* ── Remediation pill ───────────────────────────────────────────────── */
interface RemPill {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  bg: string;
}

function RemPillCard({ pill }: { pill: RemPill }) {
  return (
    <div className={clsx('card-base p-3 flex items-center gap-2 border', pill.color, pill.bg)}>
      {pill.icon}
      <div>
        <p className="text-sm font-bold text-foreground">{pill.value}</p>
        <p className="text-[10px] text-muted-foreground">{pill.label}</p>
      </div>
    </div>
  );
}

interface OverviewActivityProps {
  scanHistory: any[];
  postureSummary: any | null;
  scoreData: any | null;
  exceptionStats: any | null;
  loading: boolean;
}

function OverviewActivity({
  scanHistory, postureSummary, scoreData, exceptionStats, loading,
}: OverviewActivityProps) {
  const ps  = postureSummary ?? {};
  const exc = exceptionStats ?? {};

  const pending  = ps.pending_remediations  ?? ps.open_remediations  ?? exc.pending  ?? '—';
  const running  = ps.active_remediations   ?? ps.in_progress        ?? exc.active   ?? '—';
  const completed= ps.resolved_remediations ?? ps.resolved           ?? exc.approved ?? '—';
  const failed   = ps.failed_remediations   ?? exc.rejected          ?? '—';
  const approval = ps.pending_exceptions    ?? exc.pending_review    ?? '—';

  const remPills: RemPill[] = [
    { label: 'Pending',          value: pending,   icon: <Clock    className="w-4 h-4 text-yellow-400" />, color: 'border-yellow-500/20', bg: 'bg-yellow-500/5' },
    { label: 'Running',          value: running,   icon: <Loader2  className="w-4 h-4 text-blue-400"   />, color: 'border-blue-500/20',   bg: 'bg-blue-500/5'   },
    { label: 'Completed',        value: completed, icon: <CheckCircle className="w-4 h-4 text-green-400" />, color: 'border-green-500/20', bg: 'bg-green-500/5' },
    { label: 'Failed',           value: failed,    icon: <XCircle  className="w-4 h-4 text-red-400"    />, color: 'border-red-500/20',    bg: 'bg-red-500/5'    },
    { label: 'Approval Required',value: approval,  icon: <ShieldAlert className="w-4 h-4 text-purple-400" />, color: 'border-purple-500/20', bg: 'bg-purple-500/5' },
  ];

  const aiSummary    = scoreData?.ai_summary    ?? null;
  const aiSuggestions: string[] = scoreData?.ai_suggestions ?? [];

  const events = Array.isArray(scanHistory) ? scanHistory.slice(0, 15) : [];

  if (loading) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Activity + Remediation */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

        {/* Recent Activity Timeline */}
        <div className="space-y-3">
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            Recent Security Activity
          </p>
          <div className="card-base p-4">
            {events.length === 0 ? (
              <div className="py-6 text-center">
                <Clock className="w-7 h-7 text-muted-foreground mx-auto mb-2 opacity-30" />
                <p className="text-sm font-medium text-foreground">No scan activity</p>
                <p className="text-xs text-muted-foreground/70 mt-1">Scan history will appear here</p>
              </div>
            ) : (
              <div className="relative">
                {/* vertical line */}
                <div className="absolute left-[6px] top-2 bottom-2 w-px bg-white/8" />
                <div className="space-y-3 pl-5">
                  {events.map((ev: any, i: number) => (
                    <div key={ev.scan_id ?? i} className="relative">
                      <div className="absolute -left-5 top-1">{eventIcon(ev)}</div>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <GitBranch className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                            <span className="text-xs font-medium text-foreground truncate max-w-[120px]">
                              {ev.repo ?? 'All repos'}
                            </span>
                            <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/15 font-mono">
                              Score {Math.round(ev.score ?? 0)}
                            </span>
                          </div>
                          <p className="text-[10px] text-muted-foreground mt-0.5">{eventLabel(ev)}</p>
                        </div>
                        <span className="text-[9px] text-muted-foreground/60 whitespace-nowrap flex-shrink-0">
                          {fmtRelative(ev.date)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Remediation Summary */}
        <div className="space-y-3">
          <p className="text-sm font-semibold text-foreground flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-green-400" />
            Remediation Summary
          </p>
          <div className="grid grid-cols-1 gap-2">
            {remPills.map(p => <RemPillCard key={p.label} pill={p} />)}
          </div>
        </div>
      </div>

      {/* AI Executive Summary — rendered only if backend provides it */}
      {aiSummary && (
        <div className="card-base border border-purple-500/20 bg-purple-500/5 p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <p className="text-sm font-semibold text-foreground">AI Executive Summary</p>
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono border border-purple-500/20">
              AI
            </span>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">{aiSummary}</p>
          {aiSuggestions.length > 0 && (
            <div className="space-y-1.5 pt-1 border-t border-purple-500/15">
              <p className="text-xs font-semibold text-purple-300">Recommendations</p>
              <ul className="space-y-1">
                {aiSuggestions.map((s: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                    <span className="w-4 h-4 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center flex-shrink-0 font-bold text-[9px] mt-0.5">
                      {i + 1}
                    </span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default memo(OverviewActivity);
