import { memo } from 'react';
import { clsx } from 'clsx';
import {
  Server, Box, Cpu, Database, HardDrive, Layers, Cloud,
  AlertTriangle, Shield, Activity, Zap,
} from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

interface InfraItem {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  sub?: string;
  color: string;
}

function InfraCard({ item }: { item: InfraItem }) {
  return (
    <div className="card-base p-3 flex items-center gap-3">
      <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0', item.color)}>
        {item.icon}
      </div>
      <div className="min-w-0">
        <p className="text-base font-bold text-foreground leading-tight">{item.value}</p>
        <p className="text-[10px] text-muted-foreground">{item.label}</p>
        {item.sub && <p className="text-[9px] text-muted-foreground/60 truncate">{item.sub}</p>}
      </div>
    </div>
  );
}

interface ThreatStat {
  label: string;
  value: number | string;
  color: string;
  icon: React.ReactNode;
}

interface OverviewInfraProps {
  repos: any[];
  assets: any[];
  clusters: any[];
  threatStats: any | null;
  loading: boolean;
}

function OverviewInfra({ repos, assets, clusters, threatStats, loading }: OverviewInfraProps) {
  const ts = threatStats ?? {};

  // Derive infra metrics from clusters data
  const totalNodes = clusters.reduce((s: number, c: any) => s + (c.node_count ?? c.nodes ?? 0), 0);
  const totalPods  = clusters.reduce((s: number, c: any) => s + (c.pod_count ?? c.pods ?? 0), 0);
  const totalNS    = clusters.reduce((s: number, c: any) => s + (c.namespace_count ?? c.namespaces ?? 0), 0);

  // Derive from assets
  const containers   = assets.filter((a: any) => (a.asset_type ?? a.type ?? '').toLowerCase().includes('container')).length;
  const images       = assets.filter((a: any) => (a.asset_type ?? a.type ?? '').toLowerCase().includes('image')).length;
  const deployments  = assets.filter((a: any) => (a.asset_type ?? a.type ?? '').toLowerCase().includes('deployment')).length;

  const infraItems: InfraItem[] = [
    { icon: <Box className="w-4 h-4 text-blue-400"    />, label: 'Repositories', value: repos.length,        color: 'bg-blue-500/10'   },
    { icon: <Server className="w-4 h-4 text-purple-400" />, label: 'Assets',        value: assets.length,       color: 'bg-purple-500/10' },
    { icon: <Cpu className="w-4 h-4 text-cyan-400"    />, label: 'Clusters',      value: clusters.length,     color: 'bg-cyan-500/10'   },
    { icon: <HardDrive className="w-4 h-4 text-green-400"  />, label: 'Nodes',         value: totalNodes || '—',   color: 'bg-green-500/10'  },
    { icon: <Layers className="w-4 h-4 text-orange-400" />, label: 'Pods',          value: totalPods  || '—',   color: 'bg-orange-500/10' },
    { icon: <Database className="w-4 h-4 text-teal-400"   />, label: 'Containers',    value: containers || '—',   color: 'bg-teal-500/10'   },
    { icon: <Cloud className="w-4 h-4 text-sky-400"    />, label: 'Images',        value: images     || '—',   color: 'bg-sky-500/10'    },
    { icon: <Zap className="w-4 h-4 text-violet-400"  />, label: 'Deployments',   value: deployments || '—',  color: 'bg-violet-500/10' },
    { icon: <Layers className="w-4 h-4 text-rose-400"    />, label: 'Namespaces',    value: totalNS    || '—',   color: 'bg-rose-500/10'   },
  ];

  const threatItems: ThreatStat[] = [
    { label: 'Active Threats',    value: ts.open      ?? ts.active ?? '—', color: 'text-red-400',    icon: <AlertTriangle className="w-4 h-4 text-red-400"    /> },
    { label: 'Critical',          value: ts.critical  ?? '—',              color: 'text-red-400',    icon: <AlertTriangle className="w-4 h-4 text-red-400"    /> },
    { label: 'High',              value: ts.high      ?? '—',              color: 'text-orange-400', icon: <AlertTriangle className="w-4 h-4 text-orange-400" /> },
    { label: 'Resolved',          value: ts.resolved  ?? ts.closed ?? '—', color: 'text-green-400',  icon: <Shield        className="w-4 h-4 text-green-400"  /> },
    { label: 'MITRE Techniques',  value: ts.mitre_techniques  ?? ts.techniques  ?? '—', color: 'text-purple-400', icon: <Activity  className="w-4 h-4 text-purple-400" /> },
    { label: 'Attack Paths',      value: ts.attack_paths      ?? '—',              color: 'text-orange-400', icon: <Zap       className="w-4 h-4 text-orange-400" /> },
  ];

  if (loading) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Skeleton className="h-52 rounded-xl" />
        <Skeleton className="h-52 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      {/* Infrastructure Summary */}
      <div className="space-y-3">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Server className="w-4 h-4 text-purple-400" />
          Infrastructure Summary
        </p>
        {repos.length === 0 && assets.length === 0 && clusters.length === 0 ? (
          <div className="card-base py-8 text-center">
            <Server className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-30" />
            <p className="text-sm font-medium text-foreground">No infrastructure data</p>
            <p className="text-xs text-muted-foreground/70 mt-1">Connect repositories, assets, and clusters to populate</p>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {infraItems.map(item => (
              <InfraCard key={item.label} item={item} />
            ))}
          </div>
        )}
      </div>

      {/* Threat Summary */}
      <div className="space-y-3">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400" />
          Threat Summary
        </p>
        {ts.open == null && ts.active == null && ts.critical == null ? (
          <div className="card-base py-8 text-center">
            <Shield className="w-8 h-8 text-green-400 mx-auto mb-2 opacity-50" />
            <p className="text-sm font-medium text-foreground">No threat data</p>
            <p className="text-xs text-muted-foreground/70 mt-1">No active threats detected</p>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {threatItems.map(item => (
              <div key={item.label} className="card-base p-3 text-center">
                <div className="flex justify-center mb-1">{item.icon}</div>
                <p className={clsx('text-lg font-bold', item.color)}>{item.value}</p>
                <p className="text-[9px] text-muted-foreground leading-tight">{item.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(OverviewInfra);
