import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import {
  CheckCircle, AlertTriangle, XCircle, HelpCircle, WifiOff,
  Bug, Settings, Globe, Key, Lock, Terminal, Database,
  Activity,
} from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function countByHealth(items: any[]) {
  const map: Record<string, number> = { healthy: 0, warning: 0, critical: 0, unknown: 0, offline: 0 };
  for (const item of items) {
    const s = (item.status ?? 'unknown').toLowerCase();
    if (['active','running','healthy','connected'].includes(s))   map.healthy++;
    else if (['degraded','warning','maintenance'].includes(s))    map.warning++;
    else if (['error','failed','critical','unhealthy'].includes(s)) map.critical++;
    else if (['offline','stopped','terminated'].includes(s))      map.offline++;
    else                                                           map.unknown++;
  }
  return map;
}

interface HealthStat {
  label: string; count: number;
  icon: React.ReactNode; color: string; bg: string;
}

interface SecurityStat {
  label: string; value: number | string;
  icon: React.ReactNode; color: string;
}

interface InfraHealthProps {
  clusters:  any[];
  assets:    any[];
  vulnStats: any;
  loading:   boolean;
}

function InfraHealth({ clusters, assets, vulnStats, loading }: InfraHealthProps) {
  const vs = (vulnStats ?? {}) as any;

  const clusterHealth = useMemo(() => countByHealth(clusters), [clusters]);
  const assetHealth   = useMemo(() => countByHealth(assets),   [assets]);

  const combined = {
    healthy:  clusterHealth.healthy  + assetHealth.healthy,
    warning:  clusterHealth.warning  + assetHealth.warning,
    critical: clusterHealth.critical + assetHealth.critical,
    unknown:  clusterHealth.unknown  + assetHealth.unknown,
    offline:  clusterHealth.offline  + assetHealth.offline,
  };

  const total = Object.values(combined).reduce((s, v) => s + v, 0);

  const healthItems: HealthStat[] = [
    { label: 'Healthy',  count: combined.healthy,  icon: <CheckCircle className="w-4 h-4 text-green-400"  />, color: 'text-green-400',  bg: 'bg-green-500/10  border-green-500/20'  },
    { label: 'Warning',  count: combined.warning,  icon: <AlertTriangle className="w-4 h-4 text-yellow-400" />, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20' },
    { label: 'Critical', count: combined.critical, icon: <XCircle className="w-4 h-4 text-red-400"     />, color: 'text-red-400',    bg: 'bg-red-500/10    border-red-500/20'    },
    { label: 'Unknown',  count: combined.unknown,  icon: <HelpCircle className="w-4 h-4 text-slate-400" />, color: 'text-slate-400',  bg: 'bg-white/5       border-white/10'       },
    { label: 'Offline',  count: combined.offline,  icon: <WifiOff    className="w-4 h-4 text-orange-400"/>, color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/20' },
  ];

  const critFindings  = vs.critical ?? vs.by_severity?.critical ?? 0;
  const highFindings  = vs.high     ?? vs.by_severity?.high     ?? 0;

  // Derive security summary from asset types
  const publicAssets  = assets.filter((a: any) => a.is_public || (a.tags ?? {}).public === 'true' || a.public_ip).length;
  const secrets       = assets.filter((a: any) => matchSecrets(a)).length;
  const exposedPorts  = assets.filter((a: any) => a.open_ports?.length > 0 || a.exposed_ports?.length > 0).length;
  const unencrypted   = assets.filter((a: any) => a.encrypted === false || a.encryption_enabled === false).length;
  const weakIam       = assets.filter((a: any) => matchType(a, 'iam', 'role', 'policy', 'user') && a.risk_level === 'high').length;
  const misconfigs    = assets.filter((a: any) => (a.finding_count ?? 0) > 0 || a.misconfigured === true).length;

  const securityItems: SecurityStat[] = [
    { label: 'Critical Findings',    value: critFindings, icon: <Bug      className="w-4 h-4 text-red-400"    />, color: 'text-red-400'    },
    { label: 'High Findings',        value: highFindings, icon: <Bug      className="w-4 h-4 text-orange-400" />, color: 'text-orange-400' },
    { label: 'Misconfigurations',    value: misconfigs || '—', icon: <Settings className="w-4 h-4 text-yellow-400" />, color: 'text-yellow-400' },
    { label: 'Public Resources',     value: publicAssets|| '—', icon: <Globe    className="w-4 h-4 text-blue-400"   />, color: 'text-blue-400'   },
    { label: 'Weak IAM Policies',    value: weakIam    || '—', icon: <Key      className="w-4 h-4 text-purple-400" />, color: 'text-purple-400' },
    { label: 'Secrets Exposed',      value: secrets    || '—', icon: <Terminal className="w-4 h-4 text-pink-400"   />, color: 'text-pink-400'   },
    { label: 'Exposed Ports',        value: exposedPorts|| '—', icon: <Lock    className="w-4 h-4 text-orange-400" />, color: 'text-orange-400' },
    { label: 'Unencrypted Storage',  value: unencrypted || '—', icon: <Database className="w-4 h-4 text-red-400"    />, color: 'text-red-400'    },
  ];

  if (loading) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      {/* Infrastructure Health */}
      <div className="space-y-3">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Activity className="w-4 h-4 text-green-400" />
          Infrastructure Health
        </p>
        {total === 0 ? (
          <div className="card-base py-8 text-center">
            <HelpCircle className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-30" />
            <p className="text-sm font-medium text-foreground">No health data available</p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Progress bar breakdown */}
            <div className="card-base p-4 space-y-3">
              <div className="flex h-3 rounded-full overflow-hidden gap-px">
                {healthItems.filter(h => h.count > 0).map(h => (
                  <div key={h.label} className="h-full transition-all"
                    style={{
                      width: `${(h.count / total) * 100}%`,
                      background:
                        h.label === 'Healthy'  ? '#22c55e'
                        : h.label === 'Warning' ? '#eab308'
                        : h.label === 'Critical'? '#ef4444'
                        : h.label === 'Offline' ? '#f97316'
                        : '#475569',
                    }} />
                ))}
              </div>
              <div className="grid grid-cols-2 gap-2">
                {healthItems.map(h => (
                  <div key={h.label} className={clsx('flex items-center justify-between p-2.5 rounded-lg border', h.bg)}>
                    <div className="flex items-center gap-2">
                      {h.icon}
                      <span className="text-xs text-muted-foreground">{h.label}</span>
                    </div>
                    <div className="text-right">
                      <span className={clsx('text-sm font-bold', h.color)}>{h.count}</span>
                      {total > 0 && (
                        <span className="text-[9px] text-muted-foreground/60 ml-1">
                          {((h.count / total) * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Security Summary */}
      <div className="space-y-3">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Bug className="w-4 h-4 text-red-400" />
          Security Summary
        </p>
        <div className="grid grid-cols-2 gap-2">
          {securityItems.map(item => (
            <div key={item.label} className="card-base p-3 flex items-center gap-2">
              {item.icon}
              <div className="min-w-0">
                <p className={clsx('text-sm font-bold', item.color)}>{item.value}</p>
                <p className="text-[10px] text-muted-foreground leading-tight">{item.label}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function matchType(asset: any, ...keys: string[]) {
  const t = (asset.asset_type ?? asset.type ?? '').toLowerCase();
  return keys.some(k => t.includes(k));
}

function matchSecrets(asset: any) {
  const t = (asset.asset_type ?? asset.type ?? asset.name ?? '').toLowerCase();
  return ['secret', 'credential', 'key', 'token', 'ssm', 'vault', 'kms'].some(k => t.includes(k));
}

export default memo(InfraHealth);
