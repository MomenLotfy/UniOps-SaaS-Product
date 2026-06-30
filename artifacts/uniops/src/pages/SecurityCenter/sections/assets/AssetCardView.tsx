import { memo } from 'react';
import { clsx } from 'clsx';
import {
  Server, GitBranch, Cloud, HardDrive, User, Database,
  Box, Layers, Globe, ExternalLink, Clock, Bug, Shield,
  AlertTriangle, ChevronRight, Network, Star,
} from 'lucide-react';

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000)     return 'just now';
  if (diff < 3_600_000)  return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function Skeleton() {
  return (
    <div className="card-base p-4 animate-pulse space-y-3">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-white/5" />
        <div className="h-4 bg-white/5 rounded flex-1" />
      </div>
      <div className="space-y-2">
        <div className="h-3 bg-white/5 rounded w-3/4" />
        <div className="h-3 bg-white/5 rounded w-1/2" />
      </div>
    </div>
  );
}

const RISK_STYLE: Record<string, { border: string; badge: string; label: string }> = {
  critical: { border: 'border-red-500/30',    badge: 'bg-red-500/15 text-red-400 border-red-500/30',    label: 'CRITICAL' },
  high:     { border: 'border-orange-500/30', badge: 'bg-orange-500/15 text-orange-400 border-orange-500/30', label: 'HIGH'     },
  medium:   { border: 'border-yellow-500/25', badge: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/25', label: 'MEDIUM'   },
  low:      { border: 'border-blue-500/20',   badge: 'bg-blue-500/15 text-blue-400 border-blue-500/20',   label: 'LOW'      },
  none:     { border: 'border-green-500/20',  badge: 'bg-green-500/15 text-green-400 border-green-500/20', label: 'NONE'    },
};

const TYPE_LABEL: Record<string, string> = {
  github_repo: 'GitHub Repo', gitlab_repo: 'GitLab Repo',
  aws_ec2: 'EC2', aws_s3: 'S3 Bucket',
  aws_iam_user: 'IAM User', aws_iam_role: 'IAM Role',
  aws_rds: 'RDS', docker_image: 'Docker Image',
  k8s_cluster: 'K8s Cluster', k8s_namespace: 'Namespace', k8s_pod: 'Pod',
};

const SOURCE_LABEL: Record<string, string> = {
  github: 'GitHub', gitlab: 'GitLab', aws: 'AWS',
  kubernetes: 'K8s', docker: 'Docker',
};

const ENV_COLOR: Record<string, string> = {
  production:  'text-red-400',
  staging:     'text-yellow-400',
  development: 'text-green-400',
  unknown:     'text-muted-foreground',
};

function TypeIcon({ type }: { type: string }) {
  const cls = 'w-4 h-4';
  switch (type) {
    case 'github_repo':
    case 'gitlab_repo':   return <GitBranch className={clsx(cls, 'text-purple-400')} />;
    case 'aws_ec2':       return <Cloud     className={clsx(cls, 'text-orange-400')} />;
    case 'aws_s3':        return <HardDrive className={clsx(cls, 'text-yellow-400')} />;
    case 'aws_iam_user':
    case 'aws_iam_role':  return <User      className={clsx(cls, 'text-blue-400')}   />;
    case 'aws_rds':       return <Database  className={clsx(cls, 'text-cyan-400')}   />;
    case 'docker_image':  return <Box       className={clsx(cls, 'text-sky-400')}    />;
    case 'k8s_cluster':
    case 'k8s_namespace': return <Layers    className={clsx(cls, 'text-indigo-400')} />;
    case 'k8s_pod':       return <Server    className={clsx(cls, 'text-fuchsia-400')}/>;
    default:              return <Globe     className={clsx(cls, 'text-muted-foreground')} />;
  }
}

interface AssetCardViewProps {
  assets: any[];
  loading: boolean;
  onSelect: (a: any) => void;
}

function AssetCard({ asset, onSelect }: { asset: any; onSelect: () => void }) {
  const risk    = (asset.risk_level ?? 'none').toLowerCase();
  const style   = RISK_STYLE[risk] ?? RISK_STYLE.none;
  const totalF  = (asset.open_findings ?? 0)
    || (asset.critical_findings ?? 0) + (asset.high_findings ?? 0)
    + (asset.medium_findings ?? 0) + (asset.low_findings ?? 0);

  return (
    <div
      onClick={onSelect}
      className={clsx(
        'card-base p-4 border cursor-pointer transition-all hover:bg-white/3 hover:border-white/15 group',
        style.border,
      )}
    >
      {/* Header row */}
      <div className="flex items-start gap-2.5 mb-3">
        <div className="w-8 h-8 rounded-lg bg-white/6 flex items-center justify-center flex-shrink-0 mt-0.5 group-hover:bg-white/10 transition-colors">
          <TypeIcon type={asset.type} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-foreground truncate leading-tight">{asset.name}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">{TYPE_LABEL[asset.type] ?? asset.type}</p>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {asset.is_critical && <Star className="w-3 h-3 text-yellow-400 fill-yellow-400" />}
          <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full font-bold border uppercase', style.badge)}>
            {style.label}
          </span>
        </div>
      </div>

      {/* Badges row */}
      <div className="flex flex-wrap items-center gap-1.5 mb-3">
        <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground border border-white/8">
          {SOURCE_LABEL[asset.source] ?? asset.source ?? '—'}
        </span>
        {asset.environment && (
          <span className={clsx('text-[9px] px-1.5 py-0.5 rounded bg-white/5 border border-white/8 capitalize', ENV_COLOR[asset.environment] ?? 'text-muted-foreground')}>
            {asset.environment}
          </span>
        )}
        {asset.region && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground border border-white/8">
            {asset.region}
          </span>
        )}
        {asset.is_internet_exposed && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-500/20 flex items-center gap-0.5">
            <Globe className="w-2 h-2" /> Exposed
          </span>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-1.5 mb-3">
        <div className="text-center py-1.5 rounded-lg bg-white/3 border border-white/6">
          <p className={clsx('text-sm font-bold leading-none',
            (asset.critical_findings ?? 0) > 0 ? 'text-red-400' : 'text-foreground'
          )}>{asset.critical_findings ?? '—'}</p>
          <p className="text-[8px] text-muted-foreground mt-0.5">Critical</p>
        </div>
        <div className="text-center py-1.5 rounded-lg bg-white/3 border border-white/6">
          <p className={clsx('text-sm font-bold leading-none',
            (asset.high_findings ?? 0) > 0 ? 'text-orange-400' : 'text-foreground'
          )}>{asset.high_findings ?? '—'}</p>
          <p className="text-[8px] text-muted-foreground mt-0.5">High</p>
        </div>
        <div className="text-center py-1.5 rounded-lg bg-white/3 border border-white/6">
          <p className={clsx('text-sm font-bold leading-none',
            totalF > 0 ? 'text-yellow-400' : 'text-foreground'
          )}>{totalF || '—'}</p>
          <p className="text-[8px] text-muted-foreground mt-0.5">All</p>
        </div>
      </div>

      {/* Footer row */}
      <div className="flex items-center justify-between pt-2.5 border-t border-white/5">
        <div className="flex items-center gap-1 text-[9px] text-muted-foreground/70">
          <Clock className="w-2.5 h-2.5" />
          {fmtDate(asset.last_scanned_at ?? asset.last_synced_at)}
        </div>
        <div className="flex items-center gap-1">
          {asset.owner && (
            <span className="text-[9px] text-muted-foreground/70 flex items-center gap-0.5">
              <User className="w-2.5 h-2.5" />{asset.owner.split('@')[0].slice(0, 10)}
            </span>
          )}
          <ChevronRight className="w-3 h-3 text-muted-foreground/40 group-hover:text-muted-foreground transition-colors ml-1" />
        </div>
      </div>

      {/* Quick actions — visible on hover */}
      <div className="mt-2.5 pt-2 border-t border-white/5 hidden group-hover:flex items-center gap-1.5">
        {[
          { label: 'Details', icon: <Shield    className="w-2.5 h-2.5" /> },
          { label: 'Findings',icon: <Bug       className="w-2.5 h-2.5" /> },
          { label: 'Network', icon: <Network   className="w-2.5 h-2.5" /> },
          asset.url && { label: 'Open', icon: <ExternalLink className="w-2.5 h-2.5" />, href: asset.url },
        ].filter(Boolean).map((action: any, i: number) => (
          action.href ? (
            <a key={i} href={action.href} target="_blank" rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] bg-white/5 text-blue-400 hover:bg-white/8 border border-white/8 transition-colors">
              {action.icon} {action.label}
            </a>
          ) : (
            <button key={i} onClick={e => { e.stopPropagation(); }}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] bg-white/5 text-muted-foreground hover:text-foreground border border-white/8 transition-colors">
              {action.icon} {action.label}
            </button>
          )
        ))}
      </div>
    </div>
  );
}

function AssetCardView({ assets, loading, onSelect }: AssetCardViewProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {[...Array(6)].map((_, i) => <Skeleton key={i} />)}
      </div>
    );
  }

  if (assets.length === 0) {
    return null; // Empty state handled by parent
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
      {assets.map((a: any) => (
        <AssetCard key={a.id} asset={a} onSelect={() => onSelect(a)} />
      ))}
    </div>
  );
}

export default memo(AssetCardView);
