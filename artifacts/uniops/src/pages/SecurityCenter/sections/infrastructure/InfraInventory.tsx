import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import {
  Cpu, Box, Layers, Container, Image, HardDrive,
  Database, Network, Shield, ArchiveX, BarChart3, Server,
} from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function fmtDate(d?: string) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
}

function matchType(asset: any, ...keywords: string[]) {
  const t = (asset.asset_type ?? asset.type ?? '').toLowerCase();
  return keywords.some(k => t.includes(k));
}

const STATUS_COLOR: Record<string, string> = {
  active:      'text-green-400 bg-green-500/10 border-green-500/20',
  running:     'text-green-400 bg-green-500/10 border-green-500/20',
  healthy:     'text-green-400 bg-green-500/10 border-green-500/20',
  connected:   'text-green-400 bg-green-500/10 border-green-500/20',
  warning:     'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  degraded:    'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  stopped:     'text-slate-400 bg-slate-500/10 border-slate-500/20',
  terminated:  'text-slate-400 bg-slate-500/10 border-slate-500/20',
  error:       'text-red-400 bg-red-500/10 border-red-500/20',
  failed:      'text-red-400 bg-red-500/10 border-red-500/20',
  offline:     'text-red-400 bg-red-500/10 border-red-500/20',
};

function StatusBadge({ status }: { status?: string }) {
  const s = (status ?? 'unknown').toLowerCase();
  const style = STATUS_COLOR[s] ?? 'text-muted-foreground bg-white/5 border-white/10';
  return (
    <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full font-medium border uppercase', style)}>
      {status ?? 'Unknown'}
    </span>
  );
}

function RiskBar({ score }: { score?: number }) {
  if (score == null) return <span className="text-muted-foreground text-xs">—</span>;
  const color = score >= 80 ? 'bg-red-500' : score >= 60 ? 'bg-orange-500' : score >= 40 ? 'bg-yellow-500' : 'bg-green-500';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-white/6 overflow-hidden">
        <div className={clsx('h-full rounded-full', color)} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-mono text-foreground">{Math.round(score)}</span>
    </div>
  );
}

interface InfraInventoryProps {
  clusters: any[];
  assets: any[];
  loading: boolean;
}

function InfraInventory({ clusters, assets, loading }: InfraInventoryProps) {
  const nodes      = useMemo(() => clusters.reduce((s: number, c: any) => s + (c.node_count ?? 0), 0), [clusters]);
  const pods       = useMemo(() => clusters.reduce((s: number, c: any) => s + (c.pod_count ?? 0), 0), [clusters]);
  const containers = useMemo(() => assets.filter((a: any) => matchType(a, 'container')).length || pods, [assets, pods]);
  const images     = useMemo(() => assets.filter((a: any) => matchType(a, 'image')).length, [assets]);
  const vms        = useMemo(() => assets.filter((a: any) => matchType(a, 'vm', 'virtual_machine', 'instance', 'ec2')).length, [assets]);
  const dbs        = useMemo(() => assets.filter((a: any) => matchType(a, 'database', 'rds', 'db', 'sql', 'mongo', 'redis', 'dynamo')).length, [assets]);
  const networks   = useMemo(() => assets.filter((a: any) => matchType(a, 'vpc', 'vnet', 'network', 'subnet')).length, [assets]);
  const sgCount    = useMemo(() => assets.filter((a: any) => matchType(a, 'security_group', 'sg', 'firewall', 'nsg')).length, [assets]);
  const buckets    = useMemo(() => assets.filter((a: any) => matchType(a, 'bucket', 's3', 'blob', 'storage')).length, [assets]);
  const lbs        = useMemo(() => assets.filter((a: any) => matchType(a, 'load_balancer', 'alb', 'nlb', 'elb', 'lb')).length, [assets]);

  const inventoryItems = [
    { icon: <Layers className="w-4 h-4 text-cyan-400"   />, label: 'Clusters',        value: clusters.length, color: 'bg-cyan-500/10'   },
    { icon: <Cpu    className="w-4 h-4 text-blue-400"   />, label: 'Nodes',           value: nodes,           color: 'bg-blue-500/10'   },
    { icon: <Box    className="w-4 h-4 text-purple-400" />, label: 'Pods',            value: pods,            color: 'bg-purple-500/10' },
    { icon: <Container className="w-4 h-4 text-teal-400"  />, label: 'Containers',   value: containers,      color: 'bg-teal-500/10'   },
    { icon: <Image  className="w-4 h-4 text-green-400"  />, label: 'Images',          value: images || '—',   color: 'bg-green-500/10'  },
    { icon: <Server className="w-4 h-4 text-orange-400" />, label: 'Virtual Machines',value: vms   || '—',   color: 'bg-orange-500/10' },
    { icon: <Database className="w-4 h-4 text-yellow-400"/>, label: 'Databases',      value: dbs   || '—',   color: 'bg-yellow-500/10' },
    { icon: <Network  className="w-4 h-4 text-sky-400"  />, label: 'Networks',        value: networks|| '—', color: 'bg-sky-500/10'    },
    { icon: <Shield   className="w-4 h-4 text-red-400"  />, label: 'Security Groups', value: sgCount || '—', color: 'bg-red-500/10'    },
    { icon: <ArchiveX className="w-4 h-4 text-violet-400"/>, label: 'Buckets',        value: buckets || '—', color: 'bg-violet-500/10' },
    { icon: <BarChart3 className="w-4 h-4 text-rose-400"/>, label: 'Load Balancers',  value: lbs    || '—', color: 'bg-rose-500/10'   },
  ];

  // Cloud accounts table: group assets by account + provider
  const accounts = useMemo(() => {
    const map = new Map<string, any>();
    for (const a of assets) {
      const provider = (a.cloud_provider ?? a.provider ?? 'unknown').toLowerCase();
      const acctId   = a.account_id ?? a.subscription_id ?? a.project_id ?? provider;
      const key      = `${provider}:${acctId}`;
      if (!map.has(key)) {
        map.set(key, {
          name:        a.account_name ?? a.subscription_name ?? a.project_name ?? acctId,
          provider,
          accountId:   acctId,
          region:      a.region ?? '—',
          environment: a.environment ?? '—',
          assetCount:  0,
          riskScore:   undefined as number | undefined,
          status:      a.status ?? 'active',
          lastSync:    a.updated_at,
        });
      }
      const entry = map.get(key)!;
      entry.assetCount++;
      if (a.updated_at && (!entry.lastSync || a.updated_at > entry.lastSync))
        entry.lastSync = a.updated_at;
    }
    return Array.from(map.values()).sort((a, b) => b.assetCount - a.assetCount).slice(0, 20);
  }, [assets]);

  return (
    <div className="space-y-4">
      {/* Inventory grid */}
      <div className="space-y-3">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-purple-400" />
          Infrastructure Inventory
        </p>
        {loading ? (
          <div className="grid grid-cols-3 sm:grid-cols-4 xl:grid-cols-6 gap-2">
            {[...Array(11)].map((_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
          </div>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 xl:grid-cols-6 gap-2">
            {inventoryItems.map(item => (
              <div key={item.label} className={clsx('card-base p-3 flex flex-col gap-1.5')}>
                <div className={clsx('w-7 h-7 rounded-lg flex items-center justify-center', item.color)}>
                  {item.icon}
                </div>
                <p className="text-base font-bold text-foreground leading-tight">{item.value}</p>
                <p className="text-[9px] text-muted-foreground leading-tight">{item.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Cloud accounts table */}
      <div className="space-y-3">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Server className="w-4 h-4 text-blue-400" />
          Cloud Accounts
        </p>
        <div className="card-base overflow-hidden">
          {loading ? (
            <div className="p-4 space-y-2">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 w-full rounded-lg" />)}
            </div>
          ) : accounts.length === 0 ? (
            <div className="py-10 text-center">
              <Server className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-30" />
              <p className="text-sm font-medium text-foreground">No cloud accounts detected</p>
              <p className="text-xs text-muted-foreground/70 mt-1">Connect providers to see account inventory</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-left" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                    {['Account Name', 'Provider', 'Account ID', 'Region', 'Environment', 'Assets', 'Risk Score', 'Status', 'Last Sync'].map(h => (
                      <th key={h} className="px-3 py-2.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: 'hsl(230 15% 11%)' }}>
                  {accounts.map((acc: any, i: number) => (
                    <tr key={i} className="hover:bg-white/3 transition-colors">
                      <td className="px-3 py-2.5 font-medium text-foreground whitespace-nowrap max-w-[140px] truncate" title={acc.name}>{acc.name}</td>
                      <td className="px-3 py-2.5 text-muted-foreground uppercase font-mono text-[10px]">{acc.provider}</td>
                      <td className="px-3 py-2.5 text-muted-foreground font-mono text-[10px] whitespace-nowrap max-w-[100px] truncate" title={acc.accountId}>{String(acc.accountId).slice(0, 18)}</td>
                      <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">{acc.region}</td>
                      <td className="px-3 py-2.5 text-muted-foreground capitalize whitespace-nowrap">{acc.environment}</td>
                      <td className="px-3 py-2.5 font-bold text-foreground">{acc.assetCount}</td>
                      <td className="px-3 py-2.5"><RiskBar score={acc.riskScore} /></td>
                      <td className="px-3 py-2.5 whitespace-nowrap"><StatusBadge status={acc.status} /></td>
                      <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">{fmtDate(acc.lastSync)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default memo(InfraInventory);
