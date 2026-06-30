import { useState, useCallback } from 'react';
import { clsx } from 'clsx';
import {
  X, ExternalLink, Link2, Shield, Globe, Cpu, Clock,
  AlertTriangle, Bug, CheckCircle, Copy, Server,
  User, Tag, Network, Scan, Layers, Container,
  GitBranch, FileCode, RefreshCw, Download, MoreHorizontal,
} from 'lucide-react';
import { useApi, apiPost } from '@/hooks/use-api';

// ── helpers ────────────────────────────────────────────────────────────────────
function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d    = new Date(iso);
  const diff = Date.now() - d.getTime();
  if (diff < 60_000)     return 'just now';
  if (diff < 3_600_000)  return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
}

function copyText(text: string) {
  navigator.clipboard.writeText(text).catch(() => {});
}

const RISK_BADGE: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/30',
  high:     'bg-orange-500/15 text-orange-400 border-orange-500/30',
  medium:   'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  low:      'bg-blue-500/15 text-blue-400 border-blue-500/30',
  none:     'bg-green-500/15 text-green-400 border-green-500/30',
};

const GRADE_COLORS: Record<string, string> = {
  A: 'text-green-400',  B: 'text-teal-400',   C: 'text-yellow-400',
  D: 'text-orange-400', E: 'text-red-400',     F: 'text-red-500',
};

const TYPE_LABEL: Record<string, string> = {
  github_repo: 'GitHub Repo', gitlab_repo: 'GitLab Repo',
  aws_ec2: 'EC2 Instance', aws_s3: 'S3 Bucket',
  aws_iam_user: 'IAM User', aws_iam_role: 'IAM Role',
  aws_rds: 'RDS Database', docker_image: 'Docker Image',
  k8s_cluster: 'K8s Cluster', k8s_namespace: 'Namespace', k8s_pod: 'Pod',
};

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function Row({ label, value, copyable }: { label: string; value?: string | number | null; copyable?: boolean }) {
  if (!value && value !== 0) return null;
  const str = String(value);
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-white/4 last:border-0">
      <span className="text-[10px] text-muted-foreground flex-shrink-0 w-28">{label}</span>
      <div className="flex items-center gap-1 min-w-0">
        <span className="text-[10px] text-foreground text-right break-all">{str}</span>
        {copyable && (
          <button onClick={() => copyText(str)}
            className="flex-shrink-0 p-0.5 text-muted-foreground/50 hover:text-muted-foreground transition-colors">
            <Copy className="w-2.5 h-2.5" />
          </button>
        )}
      </div>
    </div>
  );
}

function SevCount({ label, count, color }: { label: string; count?: number; color: string }) {
  if (count == null || count === 0) return null;
  return (
    <div className={clsx('flex items-center justify-between p-2 rounded-lg border', color)}>
      <span className="text-[10px]">{label}</span>
      <span className="text-sm font-bold">{count}</span>
    </div>
  );
}

type Tab = 'basic' | 'security' | 'network' | 'scan';

// ── Component ──────────────────────────────────────────────────────────────────
interface AssetDrawerProps {
  asset: any;
  onClose: () => void;
  canSync?: boolean;
}

export default function AssetDrawer({ asset, onClose, canSync }: AssetDrawerProps) {
  const [tab,       setTab]       = useState<Tab>('basic');
  const [scanning,  setScanning]  = useState(false);
  const [scanMsg,   setScanMsg]   = useState<string | null>(null);

  const { data: rawDetail, loading: detailLoading } = useApi<any>(`/assets/${asset.id}`);
  const detail      = (rawDetail as any)?.data ?? rawDetail ?? asset;
  const meta        = detail?.meta        ?? {};
  const rel         = detail?.relationships;
  const security    = detail?.security    ?? {};
  const network     = detail?.network     ?? {};
  const scan        = detail?.scan_info   ?? {};

  const handleRunScan = useCallback(async () => {
    setScanning(true);
    setScanMsg(null);
    try {
      await apiPost(`/assets/${asset.id}/scan`, {});
      setScanMsg('Scan started');
    } catch {
      setScanMsg('Scan failed');
    } finally {
      setScanning(false);
    }
  }, [asset.id]);

  const tabs: Array<{ id: Tab; label: string; icon: React.ReactNode }> = [
    { id: 'basic',    label: 'Details',  icon: <Server    className="w-3 h-3" /> },
    { id: 'security', label: 'Security', icon: <Shield    className="w-3 h-3" /> },
    { id: 'network',  label: 'Network',  icon: <Network   className="w-3 h-3" /> },
    { id: 'scan',     label: 'Scanning', icon: <Cpu       className="w-3 h-3" /> },
  ];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative w-full max-w-[480px] bg-[hsl(230_15%_9%)] border-l border-white/8 flex flex-col shadow-2xl overflow-hidden">

        {/* ── Header ────────────────────────────────────────────────────── */}
        <div className="sticky top-0 z-10 bg-[hsl(230_15%_9%)] border-b border-white/8 px-5 pt-4 pb-0">
          <div className="flex items-start gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0 mt-0.5">
              <Server className="w-4 h-4 text-blue-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-foreground truncate">{asset.name}</p>
              <p className="text-[10px] text-muted-foreground">{TYPE_LABEL[asset.type] ?? asset.type ?? '—'}</p>
            </div>
            <button onClick={onClose} className="p-1 rounded text-muted-foreground hover:text-foreground flex-shrink-0">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Status badges */}
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <span className={clsx('text-[10px] px-2 py-0.5 rounded-full font-bold border uppercase', RISK_BADGE[asset.risk_level ?? 'none'])}>
              {asset.risk_level ?? 'none'} risk
            </span>
            {asset.is_critical && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/30 font-bold uppercase">
                Critical Asset
              </span>
            )}
            {asset.is_internet_exposed && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/30">
                Internet Exposed
              </span>
            )}
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-muted-foreground capitalize border border-white/8">
              {asset.status ?? 'active'}
            </span>
          </div>

          {/* Tabs */}
          <div className="flex gap-0">
            {tabs.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-2 text-[10px] font-medium border-b-2 transition-colors',
                  tab === t.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-muted-foreground hover:text-foreground',
                )}>
                {t.icon} {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── Actions bar ─────────────────────────────────────────────── */}
        <div className="flex items-center gap-1.5 px-5 py-2.5 border-b border-white/5 flex-wrap">
          {asset.url && (
            <a href={asset.url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 px-2 py-1 text-[10px] rounded bg-white/5 text-blue-400 hover:bg-white/8 transition-colors border border-white/8">
              <ExternalLink className="w-3 h-3" /> Open
            </a>
          )}
          {canSync && (
            <button onClick={handleRunScan} disabled={scanning}
              className="flex items-center gap-1 px-2 py-1 text-[10px] rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 transition-colors border border-blue-500/20 disabled:opacity-40">
              <RefreshCw className={clsx('w-3 h-3', scanning && 'animate-spin')} />
              {scanning ? 'Scanning…' : 'Run Scan'}
            </button>
          )}
          <button className="flex items-center gap-1 px-2 py-1 text-[10px] rounded bg-white/5 text-muted-foreground hover:text-foreground transition-colors border border-white/8">
            <Download className="w-3 h-3" /> Export
          </button>
          <button className="flex items-center gap-1 px-2 py-1 text-[10px] rounded bg-white/5 text-muted-foreground hover:text-foreground transition-colors border border-white/8">
            <Bug className="w-3 h-3" /> Findings
          </button>
          <button className="flex items-center gap-1 px-2 py-1 text-[10px] rounded bg-white/5 text-muted-foreground hover:text-foreground transition-colors border border-white/8">
            <MoreHorizontal className="w-3 h-3" />
          </button>
          {scanMsg && (
            <span className={clsx('text-[10px]', scanMsg.includes('fail') ? 'text-red-400' : 'text-green-400')}>
              {scanMsg}
            </span>
          )}
        </div>

        {/* ── Content ────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">

          {detailLoading && (
            <div className="space-y-2">
              {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-5 w-full" />)}
            </div>
          )}

          {/* BASIC TAB */}
          {!detailLoading && tab === 'basic' && (
            <div className="space-y-4">
              {/* Core fields */}
              <div className="card-base p-3">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">Basic Information</p>
                <Row label="Asset ID"    value={asset.id}         copyable />
                <Row label="Name"        value={asset.name} />
                <Row label="Type"        value={TYPE_LABEL[asset.type] ?? asset.type} />
                <Row label="Source"      value={asset.source} />
                <Row label="Environment" value={asset.environment} />
                <Row label="Region"      value={asset.region} />
                <Row label="Account ID"  value={asset.account_id} copyable />
                <Row label="Owner"       value={asset.owner} />
                <Row label="Team"        value={asset.team} />
                <Row label="Last Synced" value={fmtDate(asset.last_synced_at)} />
                <Row label="Created"     value={fmtDate(detail?.created_at)} />
              </div>

              {/* Infra fields */}
              {(asset.cluster || asset.namespace || asset.node || asset.pod || asset.container || asset.image || asset.repository || asset.deployment) && (
                <div className="card-base p-3">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">Infrastructure</p>
                  <Row label="Cluster"    value={asset.cluster} />
                  <Row label="Namespace"  value={asset.namespace} />
                  <Row label="Node"       value={asset.node} />
                  <Row label="Pod"        value={asset.pod} />
                  <Row label="Container"  value={asset.container} />
                  <Row label="Image"      value={asset.image} />
                  <Row label="Repository" value={asset.repository} />
                  <Row label="Deployment" value={asset.deployment} />
                </div>
              )}

              {/* Tags */}
              {asset.tags && Object.keys(asset.tags).length > 0 && (
                <div className="card-base p-3">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1">
                    <Tag className="w-3 h-3" /> Tags
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(asset.tags)
                      .filter(([, v]) => v !== null && v !== false && v !== '')
                      .map(([k, v]) => (
                        <span key={k} className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-muted-foreground border border-white/8">
                          {k}: {String(v)}
                        </span>
                      ))}
                  </div>
                </div>
              )}

              {/* Description */}
              {(asset.description || detail?.description) && (
                <div className="card-base p-3">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Description</p>
                  <p className="text-xs text-foreground/80 leading-relaxed">{asset.description ?? detail?.description}</p>
                </div>
              )}

              {/* Relationships */}
              {rel && (
                <div className="card-base p-3">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1.5">
                    <Link2 className="w-3 h-3" /> Relationships
                  </p>
                  {[...(rel.outgoing ?? []), ...(rel.incoming ?? [])].length === 0 ? (
                    <p className="text-[10px] text-muted-foreground">No relationships found</p>
                  ) : (
                    <div className="space-y-1.5">
                      {(rel.outgoing ?? []).map((r: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-[10px]">
                          <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 capitalize">{r.relationship_type}</span>
                          <span className="text-foreground truncate">{r.target?.name ?? r.target_asset_id}</span>
                        </div>
                      ))}
                      {(rel.incoming ?? []).map((r: any, i: number) => (
                        <div key={i} className="flex items-center gap-2 text-[10px]">
                          <span className="px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 capitalize">← {r.relationship_type}</span>
                          <span className="text-foreground truncate">{r.source?.name ?? r.source_asset_id}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Raw metadata */}
              {meta && Object.keys(meta).length > 0 && (
                <div className="card-base p-3">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">Metadata</p>
                  <div className="space-y-0">
                    {Object.entries(meta)
                      .filter(([, v]) => v !== null && v !== '' && v !== false)
                      .map(([k, v]) => (
                        <Row key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* SECURITY TAB */}
          {!detailLoading && tab === 'security' && (
            <div className="space-y-4">
              {/* Score + Grade */}
              <div className="grid grid-cols-2 gap-3">
                <div className="card-base p-3 text-center">
                  <p className="text-[10px] text-muted-foreground mb-1">Risk Score</p>
                  <p className={clsx('text-3xl font-bold',
                    (asset.risk_score ?? 0) >= 80 ? 'text-red-400'
                    : (asset.risk_score ?? 0) >= 60 ? 'text-orange-400'
                    : (asset.risk_score ?? 0) >= 40 ? 'text-yellow-400'
                    : 'text-green-400'
                  )}>{asset.risk_score ?? security.risk_score ?? '—'}</p>
                </div>
                <div className="card-base p-3 text-center">
                  <p className="text-[10px] text-muted-foreground mb-1">Security Grade</p>
                  <p className={clsx('text-3xl font-bold', GRADE_COLORS[asset.security_grade ?? security.grade ?? 'C'] ?? 'text-muted-foreground')}>
                    {asset.security_grade ?? security.grade ?? '—'}
                  </p>
                </div>
              </div>

              {/* Compliance */}
              {(asset.compliance_score ?? security.compliance_score) != null && (
                <div className="card-base p-3">
                  <p className="text-[10px] text-muted-foreground mb-1">Compliance Score</p>
                  <div className="flex items-center gap-3">
                    <div className="h-2 flex-1 rounded-full bg-white/6 overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${asset.compliance_score ?? security.compliance_score}%` }} />
                    </div>
                    <span className="text-sm font-bold text-blue-400">
                      {asset.compliance_score ?? security.compliance_score}%
                    </span>
                  </div>
                </div>
              )}

              {/* Findings breakdown */}
              <div className="card-base p-3 space-y-2">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Findings</p>
                <SevCount label="Critical" count={asset.critical_findings ?? security.critical} color="bg-red-500/10 border-red-500/20 text-red-400" />
                <SevCount label="High"     count={asset.high_findings     ?? security.high}     color="bg-orange-500/10 border-orange-500/20 text-orange-400" />
                <SevCount label="Medium"   count={asset.medium_findings   ?? security.medium}   color="bg-yellow-500/10 border-yellow-500/20 text-yellow-400" />
                <SevCount label="Low"      count={asset.low_findings      ?? security.low}      color="bg-blue-500/10 border-blue-500/20 text-blue-400" />
                {(asset.open_findings ?? 0) > 0 && (
                  <div className="pt-1.5 border-t border-white/6 flex justify-between text-[10px]">
                    <span className="text-muted-foreground">Total Open</span>
                    <span className="font-bold text-foreground">{asset.open_findings}</span>
                  </div>
                )}
                {(asset.critical_findings == null && asset.high_findings == null && asset.medium_findings == null && asset.low_findings == null) && (
                  <p className="text-[10px] text-muted-foreground">No finding breakdown available</p>
                )}
              </div>

              {/* Threats + Remediations */}
              <div className="grid grid-cols-2 gap-3">
                <div className="card-base p-3 text-center">
                  <p className="text-[10px] text-muted-foreground mb-1">Active Threats</p>
                  <p className={clsx('text-2xl font-bold', (asset.active_threats ?? security.active_threats ?? 0) > 0 ? 'text-red-400' : 'text-green-400')}>
                    {asset.active_threats ?? security.active_threats ?? 0}
                  </p>
                </div>
                <div className="card-base p-3 text-center">
                  <p className="text-[10px] text-muted-foreground mb-1">Open Remediations</p>
                  <p className={clsx('text-2xl font-bold', (asset.open_remediations ?? security.open_remediations ?? 0) > 0 ? 'text-yellow-400' : 'text-green-400')}>
                    {asset.open_remediations ?? security.open_remediations ?? 0}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* NETWORK TAB */}
          {!detailLoading && tab === 'network' && (
            <div className="space-y-4">
              <div className="card-base p-3">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">Network Information</p>
                <Row label="Public IP"   value={asset.public_ip    ?? network.public_ip}    copyable />
                <Row label="Private IP"  value={asset.private_ip   ?? network.private_ip}   copyable />
                <Row label="DNS"         value={asset.dns          ?? network.dns}           copyable />
                <Row label="VPC / VNet"  value={asset.vpc_id       ?? network.vpc_id} />
                <Row label="Subnet"      value={asset.subnet_id    ?? network.subnet_id} />
                <Row label="MAC Address" value={asset.mac_address  ?? network.mac_address} />
              </div>

              {/* Internet exposure */}
              <div className="card-base p-3">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">Exposure</p>
                <div className="flex items-center gap-2 mb-2">
                  {(asset.is_internet_exposed ?? network.is_internet_exposed) ? (
                    <span className="flex items-center gap-1.5 text-[10px] text-orange-400">
                      <Globe className="w-3 h-3" /> Internet Exposed
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-[10px] text-green-400">
                      <CheckCircle className="w-3 h-3" /> Not Exposed
                    </span>
                  )}
                </div>
                <Row label="Exposure Type" value={asset.exposure_type ?? network.exposure_type} />
                <Row label="Exposed Since" value={fmtDate(asset.exposed_since ?? network.exposed_since)} />
              </div>

              {/* Open Ports */}
              {(asset.open_ports ?? network.open_ports)?.length > 0 && (
                <div className="card-base p-3">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                    Open Ports ({(asset.open_ports ?? network.open_ports).length})
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {(asset.open_ports ?? network.open_ports).map((port: any, i: number) => (
                      <span key={i}
                        className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 border border-white/8 text-muted-foreground font-mono">
                        {typeof port === 'object' ? `${port.port}/${port.protocol ?? 'tcp'}` : port}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* SCAN TAB */}
          {!detailLoading && tab === 'scan' && (
            <div className="space-y-4">
              <div className="card-base p-3">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">Scanning Status</p>
                <Row label="Last Scan"     value={fmtDate(asset.last_scanned_at ?? scan.last_scan_at)} />
                <Row label="Scanner"       value={asset.scanner ?? scan.scanner} />
                <Row label="Scan Duration" value={scan.duration_ms ? `${(scan.duration_ms / 1000).toFixed(1)}s` : null} />
                <Row label="Scan Status"   value={asset.scan_status ?? scan.status} />
              </div>

              {/* Scan type statuses */}
              <div className="card-base p-3 space-y-2">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Scan Coverage</p>
                {[
                  { label: 'SBOM',            field: 'sbom_status'       },
                  { label: 'Secret Scan',      field: 'secret_scan'       },
                  { label: 'Dependency Scan',  field: 'dependency_scan'   },
                  { label: 'Container Scan',   field: 'container_scan'    },
                  { label: 'IaC Scan',         field: 'iac_scan'          },
                  { label: 'Vulnerability Scan', field: 'vuln_scan'       },
                ].map(({ label, field }) => {
                  const val = asset[field] ?? scan[field] ?? scan[field.replace('_scan', '')] ?? null;
                  return (
                    <div key={field} className="flex items-center justify-between text-[10px]">
                      <span className="text-muted-foreground">{label}</span>
                      {val == null ? (
                        <span className="text-muted-foreground/40">—</span>
                      ) : val === true || val === 'completed' || val === 'done' ? (
                        <span className="flex items-center gap-1 text-green-400"><CheckCircle className="w-3 h-3" /> Done</span>
                      ) : val === false || val === 'failed' ? (
                        <span className="flex items-center gap-1 text-red-400"><AlertTriangle className="w-3 h-3" /> Failed</span>
                      ) : val === 'running' || val === 'in_progress' ? (
                        <span className="flex items-center gap-1 text-blue-400"><RefreshCw className="w-3 h-3 animate-spin" /> Running</span>
                      ) : (
                        <span className="text-muted-foreground capitalize">{String(val)}</span>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* SBOM ID if available */}
              {(asset.sbom_id ?? scan.sbom_id) && (
                <div className="card-base p-3">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">SBOM</p>
                  <Row label="SBOM ID" value={asset.sbom_id ?? scan.sbom_id} copyable />
                  <Row label="Generated" value={fmtDate(asset.sbom_generated_at ?? scan.sbom_generated_at)} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
