import { memo } from 'react';
import { clsx } from 'clsx';
import { Bug, Shield, Clock } from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const SEV_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  critical: { bg: 'bg-red-500/15',    text: 'text-red-400',    border: 'border-red-500/20'    },
  high:     { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/20' },
  medium:   { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/20' },
  low:      { bg: 'bg-blue-500/15',   text: 'text-blue-400',   border: 'border-blue-500/20'   },
};

const STATUS_STYLES: Record<string, string> = {
  open:          'text-red-400',
  active:        'text-red-400',
  investigating: 'text-yellow-400',
  mitigated:     'text-green-400',
  resolved:      'text-green-400',
  suppressed:    'text-gray-400',
};

function SevBadge({ severity }: { severity: string }) {
  const s = SEV_STYLES[severity?.toLowerCase()] ?? SEV_STYLES.low;
  return (
    <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full font-bold uppercase border', s.bg, s.text, s.border)}>
      {severity}
    </span>
  );
}

function fmt(dateStr?: string) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
}

interface OverviewFindingsProps {
  vulns: any[];
  loading: boolean;
}

function OverviewFindings({ vulns, loading }: OverviewFindingsProps) {
  const items = Array.isArray(vulns) ? vulns : [];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Bug className="w-4 h-4 text-red-400" />
          Top Critical Findings
        </p>
        <span className="text-[10px] text-muted-foreground">
          {loading ? '…' : `${items.length} critical finding${items.length !== 1 ? 's' : ''}`}
        </span>
      </div>

      <div className="card-base overflow-hidden">
        {loading ? (
          <div className="p-4 space-y-2">
            {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full rounded-lg" />)}
          </div>
        ) : items.length === 0 ? (
          <div className="py-10 text-center">
            <Shield className="w-8 h-8 text-green-400 mx-auto mb-2 opacity-60" />
            <p className="text-sm font-medium text-foreground">No critical findings</p>
            <p className="text-xs text-muted-foreground/70 mt-1">No open critical vulnerabilities detected</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                  {['Severity', 'Title / CVE', 'Repository', 'Asset', 'CVSS', 'Status', 'Source', 'Detected'].map(h => (
                    <th key={h} className="px-3 py-2.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'hsl(230 15% 11%)' }}>
                {items.map((v: any, i: number) => {
                  const sev = (v.severity ?? 'low').toLowerCase();
                  const status = (v.status ?? 'open').toLowerCase();
                  const cve   = v.cve_id ?? v.cve ?? v.vuln_id ?? '—';
                  const title = v.title ?? v.name ?? cve;
                  const repo  = v.repo_name ?? v.repository ?? v.source_repo ?? '—';
                  const asset = v.asset_id ?? v.asset ?? v.affected_component ?? '—';
                  const cvss  = v.cvss_score ?? v.cvss ?? '—';
                  const src   = v.scanner ?? v.source ?? v.detected_by ?? '—';
                  const det   = v.first_seen ?? v.detected_at ?? v.created_at;

                  return (
                    <tr key={v.id ?? i} className="hover:bg-white/3 transition-colors">
                      <td className="px-3 py-2.5 whitespace-nowrap"><SevBadge severity={sev} /></td>
                      <td className="px-3 py-2.5 max-w-[200px]">
                        <p className="font-medium text-foreground truncate" title={title}>{title}</p>
                        {cve !== title && cve !== '—' && (
                          <p className="text-[9px] text-muted-foreground font-mono">{cve}</p>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap max-w-[120px] truncate" title={repo}>{repo}</td>
                      <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap max-w-[100px] truncate" title={String(asset)}>{String(asset).slice(0, 20) || '—'}</td>
                      <td className="px-3 py-2.5 font-mono whitespace-nowrap">
                        {cvss !== '—' ? (
                          <span className={clsx('font-bold',
                            Number(cvss) >= 9 ? 'text-red-400'
                            : Number(cvss) >= 7 ? 'text-orange-400'
                            : 'text-yellow-400'
                          )}>
                            {Number(cvss).toFixed(1)}
                          </span>
                        ) : <span className="text-muted-foreground">—</span>}
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <span className={clsx('text-xs font-medium capitalize', STATUS_STYLES[status] ?? 'text-muted-foreground')}>
                          {status}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 capitalize font-mono">
                          {String(src).slice(0, 12)}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <div className="flex items-center gap-1 text-muted-foreground">
                          <Clock className="w-3 h-3 flex-shrink-0" />
                          <span>{fmt(det)}</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(OverviewFindings);
