import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import {
  CheckCircle2, XCircle, AlertTriangle, HelpCircle,
  RefreshCw, Server, Cloud,
} from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function fmtDate(d?: string) {
  if (!d) return 'Never';
  const diff = Date.now() - new Date(d).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)   return 'just now';
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const PROVIDER_META: Record<string, {
  label: string; abbr: string;
  color: string; border: string; bg: string; logo: string;
}> = {
  aws:        { label: 'Amazon Web Services', abbr: 'AWS', color: 'text-orange-400', border: 'border-orange-500/25', bg: 'bg-orange-500/8',  logo: '☁' },
  azure:      { label: 'Microsoft Azure',     abbr: 'AZ',  color: 'text-blue-400',   border: 'border-blue-500/25',   bg: 'bg-blue-500/8',    logo: '⬡' },
  gcp:        { label: 'Google Cloud',        abbr: 'GCP', color: 'text-green-400',  border: 'border-green-500/25',  bg: 'bg-green-500/8',   logo: '◈' },
  kubernetes: { label: 'Kubernetes',          abbr: 'K8s', color: 'text-cyan-400',   border: 'border-cyan-500/25',   bg: 'bg-cyan-500/8',    logo: '⎈' },
  vmware:     { label: 'VMware',              abbr: 'VM',  color: 'text-purple-400', border: 'border-purple-500/25', bg: 'bg-purple-500/8',  logo: '▣' },
  'on-prem':  { label: 'On-Premises',         abbr: 'DC',  color: 'text-slate-400',  border: 'border-slate-500/25',  bg: 'bg-slate-500/8',   logo: '⬜' },
};
const PROVIDER_ORDER = ['aws', 'azure', 'gcp', 'kubernetes', 'vmware', 'on-prem'];

function HealthDot({ status }: { status: 'connected' | 'warning' | 'error' | 'unknown' }) {
  return {
    connected: <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />,
    warning:   <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />,
    error:     <XCircle       className="w-3.5 h-3.5 text-red-400"   />,
    unknown:   <HelpCircle    className="w-3.5 h-3.5 text-slate-400" />,
  }[status];
}

interface ProviderData {
  key: string;
  status: 'connected' | 'warning' | 'error' | 'unknown';
  accounts: number;
  assets: number;
  findings: number;
  lastSync?: string;
  health: 'Healthy' | 'Degraded' | 'Critical' | 'Unknown';
}

interface InfraProvidersProps {
  clusters: any[];
  assets: any[];
  syncStatus: any;
  vulnStats: any;
  loading: boolean;
}

function InfraProviders({ clusters, assets, syncStatus, vulnStats, loading }: InfraProvidersProps) {
  const providers = useMemo<ProviderData[]>(() => {
    // Build provider info from real data
    const data: ProviderData[] = PROVIDER_ORDER.map(key => {
      let clusterItems: any[] = [];
      let assetItems: any[]   = [];

      if (key === 'kubernetes') {
        clusterItems = clusters;
        assetItems   = assets.filter((a: any) =>
          ['pod', 'container', 'namespace', 'deployment', 'service'].some(t =>
            (a.asset_type ?? a.type ?? '').toLowerCase().includes(t)
          )
        );
      } else if (key === 'on-prem') {
        assetItems = assets.filter((a: any) =>
          ['on-prem', 'onprem', 'on_prem', 'datacenter', 'bare-metal'].some(t =>
            (a.cloud_provider ?? a.provider ?? a.environment ?? '').toLowerCase().includes(t)
          )
        );
      } else {
        clusterItems = clusters.filter((c: any) =>
          (c.provider ?? '').toLowerCase() === key
        );
        assetItems = assets.filter((a: any) =>
          (a.cloud_provider ?? a.provider ?? '').toLowerCase() === key
        );
      }

      const total = clusterItems.length + assetItems.length;
      const accounts = new Set([
        ...clusterItems.map((c: any) => c.account_id ?? c.id),
        ...assetItems.map((a: any)   => a.account_id ?? a.subscription_id ?? a.project_id ?? null)
      ].filter(Boolean)).size;

      // Derive status from cluster health
      const hasError    = clusterItems.some((c: any) => ['error','failed','offline'].includes((c.status ?? '').toLowerCase()));
      const hasWarning  = clusterItems.some((c: any) => ['degraded','warning'].includes((c.status ?? '').toLowerCase()));
      const status: 'connected' | 'warning' | 'error' | 'unknown' =
        total === 0 ? 'unknown' : hasError ? 'error' : hasWarning ? 'warning' : 'connected';

      const health =
        status === 'connected' ? 'Healthy'
        : status === 'warning' ? 'Degraded'
        : status === 'error'   ? 'Critical'
        : 'Unknown';

      const lastSync =
        key === 'kubernetes'
          ? clusterItems.reduce((latest: string | undefined, c: any) => {
              const t = c.last_health_check ?? c.updated_at;
              return !latest || (t && t > latest) ? t : latest;
            }, undefined)
          : syncStatus?.last_sync ?? syncStatus?.updated_at;

      return {
        key, status, accounts, assets: total,
        findings: 0, // no per-provider findings in current API
        lastSync, health,
      };
    });
    return data;
  }, [clusters, assets, syncStatus]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
      </div>
    );
  }

  const connectedCount = providers.filter(p => p.status !== 'unknown' || p.assets > 0).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Cloud className="w-4 h-4 text-blue-400" />
          Connected Providers
        </p>
        <span className="text-[10px] text-muted-foreground">{connectedCount} / {providers.length} providers active</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        {providers.map(p => {
          const meta    = PROVIDER_META[p.key];
          const isEmpty = p.assets === 0 && p.accounts === 0;
          return (
            <div key={p.key}
              className={clsx(
                'card-base p-4 border flex flex-col gap-3 transition-all',
                meta.border,
                isEmpty ? 'opacity-45' : meta.bg,
              )}>
              {/* Header */}
              <div className="flex items-start justify-between">
                <div>
                  <span className={clsx('text-lg font-bold font-mono', meta.color)}>{meta.logo} {meta.abbr}</span>
                  <p className="text-[9px] text-muted-foreground/70 mt-0.5 leading-tight">{meta.label}</p>
                </div>
                <HealthDot status={isEmpty ? 'unknown' : p.status} />
              </div>

              {/* Stats */}
              <div className="space-y-1.5">
                {[
                  { label: 'Accounts',  value: p.accounts || '—'   },
                  { label: 'Assets',    value: p.assets   || '—'   },
                  { label: 'Health',    value: p.health             },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between text-[10px]">
                    <span className="text-muted-foreground">{label}</span>
                    <span className={clsx('font-semibold',
                      label === 'Health' && value === 'Healthy'  ? 'text-green-400'
                      : label === 'Health' && value === 'Degraded' ? 'text-yellow-400'
                      : label === 'Health' && value === 'Critical' ? 'text-red-400'
                      : 'text-foreground'
                    )}>{value}</span>
                  </div>
                ))}
              </div>

              {/* Last sync */}
              <div className="pt-1.5 border-t border-white/6 flex items-center gap-1 text-[9px] text-muted-foreground/60">
                <RefreshCw className="w-2.5 h-2.5" />
                <span>{isEmpty ? 'Not connected' : fmtDate(p.lastSync)}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty global state */}
      {connectedCount === 0 && (
        <div className="card-base py-10 text-center border border-dashed border-white/10">
          <Server className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-30" />
          <p className="text-sm font-semibold text-foreground">No infrastructure connected</p>
          <p className="text-xs text-muted-foreground/70 mt-1 mb-4">Connect a cloud provider to start monitoring your infrastructure</p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {['Connect AWS', 'Connect Azure', 'Connect GCP', 'Connect Kubernetes'].map(label => (
              <button key={label}
                className="px-3 py-1.5 text-xs rounded-lg border border-white/15 text-muted-foreground hover:text-foreground hover:border-white/30 transition-colors">
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default memo(InfraProviders);
