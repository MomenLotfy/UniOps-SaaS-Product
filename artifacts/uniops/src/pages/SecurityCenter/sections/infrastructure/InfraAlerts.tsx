import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import {
  AlertTriangle, WifiOff, KeyRound, XCircle,
  Clock, CheckCircle, Bell,
} from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function fmtRelative(d?: string) {
  if (!d) return '—';
  const diff = Date.now() - new Date(d).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

type AlertSeverity = 'critical' | 'high' | 'medium' | 'low';

const SEV_STYLE: Record<AlertSeverity, string> = {
  critical: 'bg-red-500/12 border-red-500/25 text-red-400',
  high:     'bg-orange-500/12 border-orange-500/25 text-orange-400',
  medium:   'bg-yellow-500/12 border-yellow-500/25 text-yellow-400',
  low:      'bg-blue-500/12 border-blue-500/25 text-blue-400',
};

function SevBadge({ sev }: { sev: string }) {
  const s = (sev ?? 'low').toLowerCase() as AlertSeverity;
  return (
    <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full font-bold uppercase border', SEV_STYLE[s] ?? SEV_STYLE.low)}>
      {sev}
    </span>
  );
}

interface AlertRow {
  id: string; icon: React.ReactNode; category: string;
  title: string; detail: string; severity: string; time?: string;
}

interface InfraAlertsProps {
  clusters: any[];
  syncStatus: any;
  alerts: any[];
  loading: boolean;
}

function InfraAlerts({ clusters, syncStatus, alerts, loading }: InfraAlertsProps) {
  const rows = useMemo<AlertRow[]>(() => {
    const list: AlertRow[] = [];

    // Connection failures from cluster status
    for (const c of clusters) {
      const s = (c.status ?? '').toLowerCase();
      if (['error', 'failed', 'disconnected'].includes(s)) {
        list.push({
          id: `cluster-err-${c.id}`,
          icon: <WifiOff className="w-3.5 h-3.5 text-red-400" />,
          category: 'Connection Failure',
          title: `Cluster disconnected: ${c.name}`,
          detail: c.error_message ?? 'Cluster not reachable',
          severity: 'critical',
          time: c.last_health_check ?? c.updated_at,
        });
      }
      if (['degraded', 'warning'].includes(s)) {
        list.push({
          id: `cluster-warn-${c.id}`,
          icon: <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />,
          category: 'Degraded Cluster',
          title: `Cluster degraded: ${c.name}`,
          detail: c.error_message ?? 'Performance degradation detected',
          severity: 'high',
          time: c.last_health_check ?? c.updated_at,
        });
      }
    }

    // Expired credentials from sync status
    if (syncStatus?.expired_credentials?.length) {
      for (const cred of syncStatus.expired_credentials) {
        list.push({
          id: `cred-${cred.source ?? cred}`,
          icon: <KeyRound className="w-3.5 h-3.5 text-orange-400" />,
          category: 'Expired Credentials',
          title: `Credentials expired: ${cred.source ?? cred}`,
          detail: 'Integration credentials need renewal',
          severity: 'high',
          time: cred.expired_at,
        });
      }
    }

    // Alerts from /alerts endpoint
    for (const a of alerts) {
      if (!['critical', 'high'].includes((a.severity ?? '').toLowerCase())) continue;
      list.push({
        id: a.id ?? `alert-${list.length}`,
        icon: <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />,
        category: a.category ?? 'Infrastructure Alert',
        title: a.title ?? a.message ?? 'Alert',
        detail: a.description ?? a.detail ?? '',
        severity: a.severity?.toLowerCase() ?? 'high',
        time: a.created_at ?? a.triggered_at,
      });
    }

    return list.sort((a, b) => {
      const order = { critical: 0, high: 1, medium: 2, low: 3 };
      return (order[a.severity as AlertSeverity] ?? 3) - (order[b.severity as AlertSeverity] ?? 3);
    });
  }, [clusters, syncStatus, alerts]);

  // Infra alert type counts
  const connectionFails  = rows.filter(r => r.category === 'Connection Failure').length;
  const expiredCreds     = rows.filter(r => r.category === 'Expired Credentials').length;
  const offlineResources = clusters.filter((c: any) => ['offline','stopped','terminated'].includes((c.status ?? '').toLowerCase())).length;
  const criticalAlerts   = rows.filter(r => r.severity === 'critical').length;

  const summaryItems = [
    { label: 'Connection Failures',  value: connectionFails,  icon: <WifiOff        className="w-4 h-4 text-red-400"    />, color: 'text-red-400'    },
    { label: 'Expired Credentials',  value: expiredCreds,     icon: <KeyRound       className="w-4 h-4 text-orange-400" />, color: 'text-orange-400' },
    { label: 'Offline Resources',    value: offlineResources, icon: <XCircle        className="w-4 h-4 text-orange-400" />, color: 'text-orange-400' },
    { label: 'Critical Alerts',      value: criticalAlerts,   icon: <AlertTriangle  className="w-4 h-4 text-red-400"    />, color: 'text-red-400'    },
  ];

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-40 rounded" />
        <div className="grid grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
        <Skeleton className="h-40 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm font-semibold text-foreground flex items-center gap-2">
        <Bell className="w-4 h-4 text-orange-400" />
        Infrastructure Alerts
      </p>

      {/* Summary pills */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {summaryItems.map(item => (
          <div key={item.label} className="card-base p-3 flex items-center gap-2">
            {item.icon}
            <div>
              <p className={clsx('text-lg font-bold', item.color)}>{item.value}</p>
              <p className="text-[10px] text-muted-foreground">{item.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Alert list */}
      <div className="card-base overflow-hidden">
        <div className="p-3 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Recent Events · {rows.length} item{rows.length !== 1 ? 's' : ''}
          </p>
        </div>
        {rows.length === 0 ? (
          <div className="py-10 text-center">
            <CheckCircle className="w-8 h-8 text-green-400 mx-auto mb-2 opacity-60" />
            <p className="text-sm font-medium text-foreground">No infrastructure alerts</p>
            <p className="text-xs text-muted-foreground/70 mt-1">All systems operating normally</p>
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: 'hsl(230 15% 11%)' }}>
            {rows.map(row => (
              <div key={row.id} className="px-4 py-3 hover:bg-white/3 transition-colors flex items-start gap-3">
                <div className="mt-0.5 flex-shrink-0">{row.icon}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium text-foreground">{row.title}</span>
                    <SevBadge sev={row.severity} />
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground border border-white/10">
                      {row.category}
                    </span>
                  </div>
                  {row.detail && (
                    <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{row.detail}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 text-[9px] text-muted-foreground/60 flex-shrink-0">
                  <Clock className="w-3 h-3" />
                  {fmtRelative(row.time)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(InfraAlerts);
