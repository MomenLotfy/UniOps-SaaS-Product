import {
  useState, useCallback, useEffect, useRef, useMemo, memo,
} from 'react';
import {
  AlertTriangle, Shield, ShieldCheck, ShieldOff, RefreshCw,
  ChevronLeft, ChevronRight, Loader2, CheckCircle, Search,
  Filter, X, ExternalLink, Clock, Activity, Zap, Target,
  GitBranch, Box, Server, Database, ChevronDown, ChevronUp,
  AlertCircle, Eye, EyeOff, TriangleAlert, Info, Plus,
  FileText, Download, UserCircle, ArrowRight, Crosshair,
  Network, Globe, Package, BarChart3, Layers,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Threat {
  id: string;
  title: string;
  description?: string;
  severity: string;
  status: string;
  category?: string;
  source?: string;
  resource?: string;
  namespace?: string;
  ip?: string;
  mitre_tactic?: string;
  mitre_technique?: string;
  raw_data?: Record<string, any>;
  detected_at?: string;
  resolved_at?: string;
  created_at?: string;
  updated_at?: string;
}

interface ThreatStats {
  total?: number;
  critical?: number;
  high?: number;
  medium?: number;
  low?: number;
  open?: number;
  resolved?: number;
  // extended (may come from backend)
  assets_affected?: number;
  repos_affected?: number;
  clusters_affected?: number;
  containers_affected?: number;
  exploited_in_wild?: number;
  avg_risk_score?: number;
  highest_epss?: number;
  open_remediations?: number;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SEV_BADGE: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/30',
  high:     'bg-orange-500/15 text-orange-400 border-orange-500/30',
  medium:   'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  low:      'bg-blue-500/15 text-blue-400 border-blue-500/30',
  info:     'bg-slate-500/15 text-slate-400 border-slate-500/30',
};
const SEV_DOT: Record<string, string> = {
  critical: 'bg-red-500',
  high:     'bg-orange-500',
  medium:   'bg-yellow-500',
  low:      'bg-blue-500',
  info:     'bg-slate-500',
};
const SEV_ICON_COLOR: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-blue-400',
};
const STATUS_BADGE: Record<string, string> = {
  open:          'bg-red-500/10 text-red-400 border-red-500/20',
  active:        'bg-red-500/10 text-red-400 border-red-500/20',
  investigating: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  resolved:      'bg-green-500/10 text-green-400 border-green-500/20',
  suppressed:    'bg-slate-500/10 text-slate-400 border-slate-500/20',
  mitigated:     'bg-green-500/10 text-green-400 border-green-500/20',
  false_positive:'bg-slate-500/10 text-slate-400 border-slate-500/20',
};
const CAT_ICON: Record<string, React.ElementType> = {
  malware:           Package,
  phishing:          Globe,
  brute_force:       Zap,
  data_exfiltration: Database,
  privilege_escalation: Layers,
  lateral_movement:  Network,
  ransomware:        AlertTriangle,
  insider_threat:    UserCircle,
  ddos:              Activity,
  supply_chain:      GitBranch,
};
const MITRE_TACTICS = [
  'Initial Access', 'Execution', 'Persistence', 'Privilege Escalation',
  'Defense Evasion', 'Credential Access', 'Discovery', 'Lateral Movement',
  'Collection', 'Command and Control', 'Exfiltration', 'Impact',
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—';
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60)   return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function fmtDateShort(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function epssFromRaw(raw?: Record<string, any>): string {
  const v = raw?.epss_score ?? raw?.epss ?? raw?.epss_percentile;
  if (v == null) return '—';
  const n = parseFloat(v);
  if (isNaN(n)) return String(v);
  return `${(n * (n <= 1 ? 100 : 1)).toFixed(2)}%`;
}

function cvssFromRaw(raw?: Record<string, any>): string {
  const v = raw?.cvss_v3_score ?? raw?.cvss_score ?? raw?.cvss ?? raw?.Score;
  if (v == null) return '—';
  return Number(v).toFixed(1);
}

function kevFromRaw(raw?: Record<string, any>): boolean {
  return !!(raw?.kev || raw?.in_kev || raw?.cisa_kev || raw?.exploited_in_wild);
}

function threatActorFromRaw(raw?: Record<string, any>): string {
  return raw?.threat_actor ?? raw?.actor ?? raw?.attribution ?? '';
}

function affectedCount(raw?: Record<string, any>, key: string = 'affected_assets'): number {
  const v = raw?.[key];
  if (Array.isArray(v)) return v.length;
  if (typeof v === 'number') return v;
  return 0;
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Sk({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// ─── Summary Card ─────────────────────────────────────────────────────────────

function SummaryCard({
  label, value, icon: Icon, color = 'text-blue-400', sub, onClick, loading,
}: {
  label: string; value: string | number; icon: React.ElementType;
  color?: string; sub?: string; onClick?: () => void; loading?: boolean;
}) {
  const bg = color.includes('red') ? 'bg-red-500/8' :
             color.includes('orange') ? 'bg-orange-500/8' :
             color.includes('yellow') ? 'bg-yellow-500/8' :
             color.includes('green') ? 'bg-green-500/8' :
             color.includes('purple') ? 'bg-purple-500/8' :
             'bg-blue-500/8';
  return (
    <div onClick={onClick}
      className={clsx(
        'card-base px-3 py-3 flex items-start gap-2.5 min-w-0 transition-all',
        onClick && 'cursor-pointer hover:border-white/20',
      )}>
      <div className={clsx('w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5', bg)}>
        <Icon className={clsx('w-3.5 h-3.5', color)} />
      </div>
      <div className="min-w-0 flex-1">
        {loading ? (
          <><Sk className="h-5 w-10 mb-1" /><Sk className="h-3 w-16" /></>
        ) : (
          <>
            <div className="text-base font-bold text-foreground tabular-nums leading-tight">{value}</div>
            <div className="text-[10px] text-muted-foreground leading-tight">{label}</div>
            {sub && <div className="text-[9px] text-muted-foreground/50 mt-0.5">{sub}</div>}
          </>
        )}
      </div>
    </div>
  );
}

// ─── KEV Badge ────────────────────────────────────────────────────────────────

function KevBadge() {
  return (
    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-600/20 text-red-400 border border-red-500/30 whitespace-nowrap">
      ⚡ KEV
    </span>
  );
}

// ─── MITRE Badge ──────────────────────────────────────────────────────────────

function MitreBadge({ tactic, technique }: { tactic?: string; technique?: string }) {
  if (!tactic && !technique) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="min-w-0">
      {technique && (
        <span className="font-mono text-[10px] text-indigo-400 block truncate">{technique}</span>
      )}
      {tactic && (
        <span className="text-[10px] text-muted-foreground truncate block">{tactic}</span>
      )}
    </div>
  );
}

// ─── Attack Timeline ──────────────────────────────────────────────────────────

function AttackTimeline({ threat }: { threat: Threat }) {
  const events: { label: string; ts?: string; done: boolean; color: string }[] = [
    { label: 'Threat Discovered',    ts: threat.detected_at ?? threat.created_at, done: true,  color: 'bg-red-500' },
    { label: 'Alert Generated',      ts: threat.created_at,                         done: true,  color: 'bg-orange-500' },
    { label: 'Investigation Started',ts: undefined,                                  done: ['investigating','resolved','suppressed','mitigated'].includes(threat.status), color: 'bg-yellow-500' },
    { label: 'Remediation Started',  ts: undefined,                                  done: ['resolved','suppressed','mitigated'].includes(threat.status), color: 'bg-blue-500' },
    { label: 'Resolved / Closed',    ts: threat.resolved_at,                         done: ['resolved','suppressed','mitigated'].includes(threat.status), color: 'bg-green-500' },
  ];
  return (
    <div className="space-y-0">
      {events.map((ev, i) => (
        <div key={i} className="flex items-start gap-3 relative">
          {/* Connector line */}
          {i < events.length - 1 && (
            <div className={clsx(
              'absolute left-[11px] top-6 w-0.5 h-full',
              ev.done ? 'bg-white/15' : 'bg-white/5',
            )} />
          )}
          <div className={clsx('w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 border',
            ev.done
              ? `${ev.color} border-transparent`
              : 'bg-white/5 border-border',
          )}>
            {ev.done && <CheckCircle className="w-3 h-3 text-white" />}
          </div>
          <div className="pb-4 min-w-0">
            <p className={clsx('text-xs font-medium', ev.done ? 'text-foreground' : 'text-muted-foreground/40')}>
              {ev.label}
            </p>
            {ev.ts && (
              <p className="text-[10px] text-muted-foreground">{fmtDateShort(ev.ts)}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── MITRE Panel ─────────────────────────────────────────────────────────────

function MitrePanel({ threat }: { threat: Threat }) {
  if (!threat.mitre_tactic && !threat.mitre_technique) {
    return (
      <div className="py-6 text-center">
        <Target className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
        <p className="text-xs text-muted-foreground">No MITRE ATT&CK mapping available for this threat.</p>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {threat.mitre_tactic && (
        <div className="p-3 rounded-xl border border-border bg-white/2">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest">Tactic</span>
          </div>
          <p className="text-sm font-semibold text-foreground">{threat.mitre_tactic}</p>
          <p className="text-[10px] text-muted-foreground mt-1">
            {MITRE_TACTICS.includes(threat.mitre_tactic)
              ? 'Mapped to MITRE ATT&CK Enterprise framework'
              : threat.mitre_tactic}
          </p>
        </div>
      )}
      {threat.mitre_technique && (
        <div className="p-3 rounded-xl border border-border bg-white/2">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest">Technique / Sub-technique</span>
          </div>
          <p className="text-sm font-semibold text-foreground font-mono">{threat.mitre_technique}</p>
        </div>
      )}
      <div className="p-3 rounded-xl border border-border bg-indigo-500/5">
        <p className="text-[11px] text-muted-foreground mb-2">ATT&CK Navigator</p>
        <a href={`https://attack.mitre.org/techniques/${threat.mitre_technique?.replace('.', '/') ?? ''}`}
          target="_blank" rel="noreferrer"
          className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
          View on MITRE ATT&CK <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}

// ─── Threat Detail Panel ──────────────────────────────────────────────────────

const PANEL_TABS = ['Overview', 'MITRE', 'Timeline', 'Raw Data'] as const;
type PanelTab = typeof PANEL_TABS[number];

function ThreatDetailPanel({
  threat, onClose, onResolve, onSuppress, canAct, acting,
}: {
  threat: Threat;
  onClose: () => void;
  onResolve: (id: string) => void;
  onSuppress: (id: string) => void;
  canAct: boolean;
  acting: string | null;
}) {
  const [tab, setTab] = useState<PanelTab>('Overview');

  // Fetch full threat detail
  const { data: raw } = useApi<any>(`/threats/${threat.id}`);
  const detail: Threat = raw?.data ?? raw ?? threat;

  const isOpen = !['resolved', 'suppressed', 'mitigated'].includes(detail.status);
  const epss    = epssFromRaw(detail.raw_data);
  const cvss    = cvssFromRaw(detail.raw_data);
  const isKev   = kevFromRaw(detail.raw_data);
  const actor   = threatActorFromRaw(detail.raw_data);
  const CatIcon = CAT_ICON[detail.category ?? ''] ?? AlertTriangle;

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex">
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto w-full max-w-xl bg-[hsl(230_15%_9%)] border-l border-border flex flex-col shadow-2xl">

        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-border flex-shrink-0">
          <div className="flex items-start gap-3 min-w-0 flex-1">
            <div className={clsx('w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5',
              detail.severity === 'critical' ? 'bg-red-500/10' :
              detail.severity === 'high' ? 'bg-orange-500/10' :
              detail.severity === 'medium' ? 'bg-yellow-500/10' :
              'bg-blue-500/10',
            )}>
              <AlertTriangle className={clsx('w-4 h-4', SEV_ICON_COLOR[detail.severity] ?? 'text-slate-400')} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className={clsx('px-2 py-0.5 text-[10px] font-semibold rounded-md border capitalize', SEV_BADGE[detail.severity] ?? SEV_BADGE.low)}>
                  {detail.severity}
                </span>
                <span className={clsx('px-2 py-0.5 text-[10px] font-medium rounded-md border capitalize', STATUS_BADGE[detail.status] ?? 'border-border text-muted-foreground')}>
                  {detail.status}
                </span>
                {isKev && <KevBadge />}
              </div>
              <h2 className="text-sm font-semibold text-foreground leading-snug">{detail.title}</h2>
              <p className="text-[10px] text-muted-foreground mt-0.5 font-mono">{detail.id}</p>
            </div>
          </div>
          <button onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors flex-shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Quick metrics */}
        <div className="grid grid-cols-3 gap-px bg-border border-b border-border flex-shrink-0">
          {[
            { label: 'EPSS',  value: epss,       color: epss !== '—' && parseFloat(epss) > 50 ? 'text-orange-400' : 'text-foreground' },
            { label: 'CVSS',  value: cvss,        color: cvss !== '—' && parseFloat(cvss) >= 9 ? 'text-red-400' : cvss !== '—' && parseFloat(cvss) >= 7 ? 'text-orange-400' : 'text-foreground' },
            { label: 'Source', value: detail.source ?? '—', color: 'text-foreground' },
          ].map(m => (
            <div key={m.label} className="px-4 py-2.5 bg-[hsl(230_15%_9%)] text-center">
              <div className={clsx('text-sm font-bold tabular-nums', m.color)}>{m.value}</div>
              <div className="text-[10px] text-muted-foreground">{m.label}</div>
            </div>
          ))}
        </div>

        {/* Tab bar */}
        <div className="flex items-center px-4 border-b border-border flex-shrink-0 overflow-x-auto">
          {PANEL_TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx(
                'px-3 py-2.5 text-xs whitespace-nowrap border-b-2 transition-colors -mb-px',
                tab === t ? 'border-indigo-500 text-foreground font-medium' : 'border-transparent text-muted-foreground hover:text-foreground',
              )}>
              {t}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* ── OVERVIEW ── */}
          {tab === 'Overview' && (
            <>
              {detail.description && (
                <div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Technical Description</p>
                  <p className="text-xs text-foreground/80 leading-relaxed">{detail.description}</p>
                </div>
              )}

              {/* Metadata grid */}
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Threat Details</p>
                <div className="space-y-2">
                  {[
                    { label: 'Category',       value: detail.category    ?? '—' },
                    { label: 'Source',         value: detail.source      ?? '—' },
                    { label: 'Resource',       value: detail.resource    ?? '—', mono: true },
                    { label: 'Namespace',      value: detail.namespace   ?? '—', mono: true },
                    { label: 'IP',             value: detail.ip          ?? '—', mono: true },
                    { label: 'MITRE Tactic',   value: detail.mitre_tactic ?? '—' },
                    { label: 'MITRE Technique',value: detail.mitre_technique ?? '—', mono: true },
                    { label: 'Threat Actor',   value: actor || '—' },
                    { label: 'Exploit Avail.', value: isKev ? 'Yes (KEV)' : (detail.raw_data?.exploit_available ? 'Yes' : '—') },
                    { label: 'Detected',       value: fmtDateShort(detail.detected_at ?? detail.created_at) },
                    { label: 'Last Updated',   value: fmtDateShort(detail.updated_at) },
                    { label: 'Resolved At',    value: fmtDateShort(detail.resolved_at) },
                  ].filter(r => r.value !== '—' || true).map(row => (
                    <div key={row.label} className="flex items-baseline gap-2">
                      <span className="text-[10px] text-muted-foreground w-32 flex-shrink-0">{row.label}</span>
                      <span className={clsx('text-[11px] text-foreground min-w-0 break-all', row.mono && 'font-mono')}>
                        {row.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Affected Resources from raw_data */}
              {(detail.raw_data?.affected_assets || detail.raw_data?.affected_repos || detail.raw_data?.affected_containers) && (
                <div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Affected Assets</p>
                  <div className="space-y-1">
                    {Array.isArray(detail.raw_data?.affected_assets) && detail.raw_data.affected_assets.map((a: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/3 text-xs">
                        <Server className="w-3 h-3 text-blue-400 flex-shrink-0" />
                        <span className="text-foreground font-mono">{typeof a === 'string' ? a : a.name ?? JSON.stringify(a)}</span>
                      </div>
                    ))}
                    {Array.isArray(detail.raw_data?.affected_repos) && detail.raw_data.affected_repos.map((r: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/3 text-xs">
                        <GitBranch className="w-3 h-3 text-purple-400 flex-shrink-0" />
                        <span className="text-foreground font-mono">{typeof r === 'string' ? r : r.name ?? JSON.stringify(r)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Related CVEs from raw_data */}
              {detail.raw_data?.cve_ids && Array.isArray(detail.raw_data.cve_ids) && detail.raw_data.cve_ids.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Related CVEs</p>
                  <div className="flex flex-wrap gap-1.5">
                    {detail.raw_data.cve_ids.map((cve: string) => (
                      <a key={cve} href={`https://nvd.nist.gov/vuln/detail/${cve}`} target="_blank" rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-[10px] font-mono text-blue-400 hover:text-blue-300 transition-colors">
                        {cve} <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* Remediation from raw_data */}
              {detail.raw_data?.remediation && (
                <div>
                  <p className="text-[10px] font-semibold text-green-400 uppercase tracking-widest mb-2">Recommended Remediation</p>
                  <div className="p-3 rounded-xl border border-green-500/20 bg-green-500/5">
                    <p className="text-xs text-foreground/80 leading-relaxed">{detail.raw_data.remediation}</p>
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── MITRE ── */}
          {tab === 'MITRE' && <MitrePanel threat={detail} />}

          {/* ── TIMELINE ── */}
          {tab === 'Timeline' && <AttackTimeline threat={detail} />}

          {/* ── RAW DATA ── */}
          {tab === 'Raw Data' && (
            <div>
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Raw Finding Data</p>
              {detail.raw_data && Object.keys(detail.raw_data).length > 0 ? (
                <pre className="text-[10px] font-mono text-foreground/70 bg-white/3 border border-border rounded-xl p-3 overflow-x-auto whitespace-pre-wrap break-all">
                  {JSON.stringify(detail.raw_data, null, 2)}
                </pre>
              ) : (
                <p className="text-xs text-muted-foreground">No raw data attached to this threat.</p>
              )}
            </div>
          )}
        </div>

        {/* Actions footer */}
        {canAct && isOpen && (
          <div className="flex items-center gap-2 px-5 py-3 border-t border-border flex-shrink-0 bg-[hsl(230_15%_8%)]">
            <button onClick={() => onResolve(threat.id)} disabled={!!acting}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-green-600/20 text-green-400 border border-green-500/30 hover:bg-green-600/30 transition-colors disabled:opacity-40 font-medium">
              {acting === threat.id + 'resolve' ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldCheck className="w-3 h-3" />}
              Resolve
            </button>
            <button onClick={() => onSuppress(threat.id)} disabled={!!acting}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-white/5 text-muted-foreground border border-border hover:text-foreground transition-colors disabled:opacity-40">
              {acting === threat.id + 'suppress' ? <Loader2 className="w-3 h-3 animate-spin" /> : <EyeOff className="w-3 h-3" />}
              Suppress
            </button>
            <button
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-white/5 text-muted-foreground border border-border hover:text-foreground transition-colors">
              <FileText className="w-3 h-3" /> Export
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Table Row ────────────────────────────────────────────────────────────────

const ThreatRow = memo(function ThreatRow({
  threat, selected, onClick, onResolve, onSuppress, canAct, acting,
}: {
  threat: Threat; selected: boolean;
  onClick: () => void; onResolve: () => void; onSuppress: () => void;
  canAct: boolean; acting: string | null;
}) {
  const isKev  = kevFromRaw(threat.raw_data);
  const epss   = epssFromRaw(threat.raw_data);
  const cvss   = cvssFromRaw(threat.raw_data);
  const isOpen = !['resolved', 'suppressed', 'mitigated'].includes(threat.status);
  const CatIcon = CAT_ICON[threat.category ?? ''] ?? AlertTriangle;

  return (
    <tr onClick={onClick}
      className={clsx(
        'border-b border-border/40 cursor-pointer transition-colors',
        selected ? 'bg-indigo-500/8 border-indigo-500/20' : 'hover:bg-white/2',
      )}>
      {/* Severity */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <div className="flex items-center gap-1.5">
          <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', SEV_DOT[threat.severity] ?? 'bg-slate-500')} />
          <span className={clsx('text-[10px] font-semibold capitalize', SEV_ICON_COLOR[threat.severity] ?? 'text-slate-400')}>
            {threat.severity}
          </span>
        </div>
      </td>

      {/* Threat / Title */}
      <td className="px-3 py-2.5 max-w-[220px]">
        <div className="flex items-start gap-1.5">
          <CatIcon className="w-3 h-3 text-muted-foreground flex-shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-xs font-medium text-foreground truncate">{threat.title}</p>
            <div className="flex items-center gap-1 mt-0.5 flex-wrap">
              {threat.category && (
                <span className="text-[9px] text-muted-foreground capitalize">{threat.category.replace(/_/g, ' ')}</span>
              )}
              {isKev && <KevBadge />}
            </div>
          </div>
        </div>
      </td>

      {/* EPSS */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <span className={clsx('text-[11px] tabular-nums',
          epss !== '—' && parseFloat(epss) > 50 ? 'text-red-400 font-medium' :
          epss !== '—' && parseFloat(epss) > 20 ? 'text-orange-400' :
          'text-muted-foreground',
        )}>
          {epss}
        </span>
      </td>

      {/* CVSS */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <span className={clsx('text-[11px] font-mono tabular-nums',
          cvss !== '—' && parseFloat(cvss) >= 9 ? 'text-red-400 font-bold' :
          cvss !== '—' && parseFloat(cvss) >= 7 ? 'text-orange-400' :
          'text-muted-foreground',
        )}>
          {cvss}
        </span>
      </td>

      {/* MITRE */}
      <td className="px-3 py-2.5 max-w-[130px]">
        <MitreBadge tactic={threat.mitre_tactic} technique={threat.mitre_technique} />
      </td>

      {/* Source */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <span className="text-[10px] text-muted-foreground">{threat.source ?? '—'}</span>
      </td>

      {/* Resource */}
      <td className="px-3 py-2.5 max-w-[120px]">
        <span className="text-[10px] font-mono text-muted-foreground truncate block">{threat.resource ?? threat.namespace ?? '—'}</span>
      </td>

      {/* Status */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border capitalize', STATUS_BADGE[threat.status] ?? 'border-border text-muted-foreground')}>
          {threat.status}
        </span>
      </td>

      {/* Detected */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <span className="text-[10px] text-muted-foreground">{timeAgo(threat.detected_at ?? threat.created_at)}</span>
      </td>

      {/* Actions */}
      <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
        {canAct && isOpen ? (
          <div className="flex items-center gap-1">
            <button onClick={onResolve} disabled={!!acting} title="Resolve"
              className="p-1 rounded text-green-400 hover:bg-green-500/10 transition-colors disabled:opacity-40">
              {acting === threat.id + 'resolve' ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldCheck className="w-3 h-3" />}
            </button>
            <button onClick={onSuppress} disabled={!!acting} title="Suppress"
              className="p-1 rounded text-slate-400 hover:bg-white/5 transition-colors disabled:opacity-40">
              {acting === threat.id + 'suppress' ? <Loader2 className="w-3 h-3 animate-spin" /> : <EyeOff className="w-3 h-3" />}
            </button>
          </div>
        ) : (
          <Eye className="w-3 h-3 text-muted-foreground/30" />
        )}
      </td>
    </tr>
  );
});

// ─── Filter Bar ───────────────────────────────────────────────────────────────

function FilterPill({
  label, active, onClick, color,
}: { label: string; active: boolean; onClick: () => void; color?: string }) {
  return (
    <button onClick={onClick}
      className={clsx(
        'px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-colors whitespace-nowrap',
        active
          ? color ?? 'bg-indigo-600 text-white'
          : 'text-muted-foreground hover:text-foreground',
      )}>
      {label}
    </button>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Threats() {
  const { role } = usePermissions();
  const canAct = canWriteSecurity(role);

  // Filters
  const [severity,  setSeverity]  = useState('');
  const [status,    setStatus]    = useState('open');
  const [category,  setCategory]  = useState('');
  const [search,    setSearch]    = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [page, setPage]           = useState(1);
  const [selectedThreat, setSelectedThreat] = useState<Threat | null>(null);
  const [acting, setActing]       = useState<string | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>();

  // Debounced search
  useEffect(() => {
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { setSearch(searchInput); setPage(1); }, 350);
    return () => clearTimeout(searchTimer.current);
  }, [searchInput]);

  // Auto-refresh every 60 seconds
  const { data: rawThreats, loading, refetch } = useApi<any>(
    buildQs('/threats', { page, page_size: 25, severity, status, category })
  );
  const { data: statsRaw, refetch: refetchStats } = useApi<any>('/threats/stats');

  useEffect(() => {
    const id = setInterval(() => { refetch(); refetchStats(); }, 60_000);
    return () => clearInterval(id);
  }, [refetch, refetchStats]);

  const result   = rawThreats?.data ?? rawThreats;
  const threats: Threat[] = useMemo(() => result?.data ?? [], [result]);
  const total    = result?.total ?? 0;
  const pages    = result?.pages ?? 1;
  const stats: ThreatStats = statsRaw?.data ?? statsRaw ?? {};

  // Client-side search filter (for fast UX; server handles real filtering)
  const filtered = useMemo(() => {
    if (!search) return threats;
    const q = search.toLowerCase();
    return threats.filter(t =>
      t.title?.toLowerCase().includes(q) ||
      t.category?.toLowerCase().includes(q) ||
      t.mitre_tactic?.toLowerCase().includes(q) ||
      t.mitre_technique?.toLowerCase().includes(q) ||
      t.source?.toLowerCase().includes(q) ||
      t.resource?.toLowerCase().includes(q) ||
      t.ip?.toLowerCase().includes(q) ||
      t.id?.toLowerCase().includes(q)
    );
  }, [threats, search]);

  // Stats derived values
  const criticalCount = stats?.critical ?? 0;
  const openCount     = stats?.open ?? 0;
  const kevCount      = stats?.exploited_in_wild ?? 0;
  const assetsAffected = stats?.assets_affected ?? 0;
  const reposAffected  = stats?.repos_affected ?? 0;
  const clustersAff    = stats?.clusters_affected ?? 0;
  const containersAff  = stats?.containers_affected ?? 0;
  const avgRisk        = stats?.avg_risk_score;
  const highestEpss    = stats?.highest_epss;
  const openRem        = stats?.open_remediations ?? 0;

  const handleRefresh = useCallback(() => { refetch(); refetchStats(); }, [refetch, refetchStats]);

  const handleResolve = useCallback(async (id: string) => {
    setActing(id + 'resolve');
    try {
      await apiPost(`/threats/${id}/resolve`, { note: 'Resolved via UniOps Security Center' });
      refetch(); refetchStats();
      if (selectedThreat?.id === id) setSelectedThreat(null);
    } catch {}
    finally { setActing(null); }
  }, [refetch, refetchStats, selectedThreat]);

  const handleSuppress = useCallback(async (id: string) => {
    setActing(id + 'suppress');
    try {
      await apiPost(`/threats/${id}/suppress`, { reason: 'TOLERATED' });
      refetch(); refetchStats();
      if (selectedThreat?.id === id) setSelectedThreat(null);
    } catch {}
    finally { setActing(null); }
  }, [refetch, refetchStats, selectedThreat]);

  const clearFilter = useCallback((type: 'severity' | 'status' | 'category' | 'search') => {
    if (type === 'severity') setSeverity('');
    if (type === 'status')   setStatus('open');
    if (type === 'category') setCategory('');
    if (type === 'search')   { setSearch(''); setSearchInput(''); }
    setPage(1);
  }, []);

  const statsLoading = !statsRaw;

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-bold text-foreground flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-red-500/10 flex items-center justify-center">
              <Crosshair className="w-4 h-4 text-red-400" />
            </div>
            Threat Intelligence
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {total} threats · tenant-isolated · auto-refresh 60s
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <input
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="Search threats, CVE, MITRE, resource…"
              className="w-56 pl-8 pr-3 py-1.5 text-xs bg-white/5 border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-indigo-500/50"
            />
            {searchInput && (
              <button onClick={() => clearFilter('search')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
          <button onClick={handleRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
        <SummaryCard label="Active Threats"       value={openCount}       icon={AlertTriangle}  color="text-red-400"    loading={statsLoading} onClick={() => { setStatus('open'); setPage(1); }} />
        <SummaryCard label="Critical Threats"     value={criticalCount}   icon={AlertCircle}    color="text-red-400"    loading={statsLoading} onClick={() => { setSeverity('critical'); setPage(1); }} />
        <SummaryCard label="Exploited in Wild"    value={kevCount}        icon={Zap}            color="text-orange-400" loading={statsLoading} sub="CISA KEV" />
        <SummaryCard label="Assets Affected"      value={assetsAffected}  icon={Server}         color="text-blue-400"   loading={statsLoading} />
        <SummaryCard label="Repos Affected"       value={reposAffected}   icon={GitBranch}      color="text-purple-400" loading={statsLoading} />
        <SummaryCard label="Clusters Affected"    value={clustersAff}     icon={Layers}         color="text-cyan-400"   loading={statsLoading} />
        <SummaryCard label="Containers Affected"  value={containersAff}   icon={Box}            color="text-indigo-400" loading={statsLoading} />
        <SummaryCard label="Avg Risk Score"       value={avgRisk != null ? avgRisk.toFixed(1) : '—'} icon={BarChart3} color="text-yellow-400" loading={statsLoading} />
        <SummaryCard label="Highest EPSS"         value={highestEpss != null ? `${(highestEpss * (highestEpss <= 1 ? 100 : 1)).toFixed(1)}%` : '—'} icon={Target} color="text-orange-400" loading={statsLoading} />
        <SummaryCard label="Open Remediations"    value={openRem}         icon={Activity}       color="text-green-400"  loading={statsLoading} />
      </div>

      {/* ── Severity quick filters + filter toggle ── */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <div className="flex items-center gap-0.5 mr-1">
          {(['', 'critical', 'high', 'medium', 'low'] as const).map(s => (
            <FilterPill
              key={s}
              label={s || 'All'}
              active={severity === s}
              onClick={() => { setSeverity(s); setPage(1); }}
              color={
                s === 'critical' ? 'bg-red-600/30 text-red-400 border border-red-500/20' :
                s === 'high'     ? 'bg-orange-600/30 text-orange-400 border border-orange-500/20' :
                s === 'medium'   ? 'bg-yellow-600/30 text-yellow-400 border border-yellow-500/20' :
                s === 'low'      ? 'bg-blue-600/30 text-blue-400 border border-blue-500/20' :
                'bg-white/8 text-foreground'
              }
            />
          ))}
        </div>
        <div className="w-px h-4 bg-border mx-1" />
        {(['open', 'investigating', 'resolved', 'suppressed'] as const).map(s => (
          <FilterPill
            key={s}
            label={s}
            active={status === s}
            onClick={() => { setStatus(status === s ? '' : s); setPage(1); }}
          />
        ))}
        <div className="w-px h-4 bg-border mx-1" />
        <button onClick={() => setShowFilters(f => !f)}
          className={clsx(
            'flex items-center gap-1 px-2.5 py-1 rounded-md text-xs border transition-colors',
            showFilters ? 'border-indigo-500/40 text-indigo-400 bg-indigo-500/8' : 'border-border text-muted-foreground hover:text-foreground',
          )}>
          <Filter className="w-3 h-3" /> Filters
        </button>

        {/* Active filter chips */}
        {severity && (
          <span className={clsx('flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border cursor-pointer', SEV_BADGE[severity] ?? SEV_BADGE.low)}
            onClick={() => clearFilter('severity')}>
            {severity} <X className="w-2.5 h-2.5" />
          </span>
        )}
        {category && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border border-border text-muted-foreground cursor-pointer"
            onClick={() => clearFilter('category')}>
            {category.replace(/_/g, ' ')} <X className="w-2.5 h-2.5" />
          </span>
        )}

        <span className="ml-auto text-xs text-muted-foreground">{filtered.length} threats</span>
      </div>

      {/* ── Extended filters ── */}
      {showFilters && (
        <div className="card-base p-3 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">Category</label>
            <select value={category} onChange={e => { setCategory(e.target.value); setPage(1); }}
              className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
              <option value="">All Categories</option>
              {Object.keys(CAT_ICON).map(c => (
                <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">Status</label>
            <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
              className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
              <option value="">All Statuses</option>
              {['open', 'investigating', 'resolved', 'suppressed', 'mitigated'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">Severity</label>
            <select value={severity} onChange={e => { setSeverity(e.target.value); setPage(1); }}
              className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
              <option value="">All Severities</option>
              {['critical', 'high', 'medium', 'low'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">MITRE Tactic</label>
            <select className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
              <option value="">All Tactics</option>
              {MITRE_TACTICS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
      )}

      {/* ── Main table ── */}
      <div className="card-base overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead className="sticky top-0 z-10">
              <tr className="border-b border-border bg-[hsl(230_15%_9%)]">
                {[
                  'Severity', 'Threat / Category', 'EPSS', 'CVSS',
                  'MITRE', 'Source', 'Resource', 'Status', 'Detected', '',
                ].map(h => (
                  <th key={h} className="text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wide px-3 py-2.5 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i} className="border-b border-border/40">
                    {[...Array(10)].map((_, j) => (
                      <td key={j} className="px-3 py-3"><Sk className="h-3.5 rounded" /></td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-4">
                    <div className="flex flex-col items-center gap-3 py-12 text-center">
                      <div className="w-14 h-14 rounded-2xl bg-green-500/8 border border-green-500/20 flex items-center justify-center">
                        <Shield className="w-7 h-7 text-green-400 opacity-60" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-foreground mb-1">No active threats detected</p>
                        <p className="text-xs text-muted-foreground max-w-sm">
                          {severity || category || search
                            ? 'No threats match the current filters. Try adjusting or clearing filters.'
                            : 'Your environment has no threats matching the current view. Keep monitoring — threats will appear here as they are detected by your configured security integrations.'}
                        </p>
                      </div>
                      {(severity || category || status || search) && (
                        <button onClick={() => { setSeverity(''); setCategory(''); setStatus('open'); setSearch(''); setSearchInput(''); setPage(1); }}
                          className="text-xs text-indigo-400 hover:text-indigo-300 underline transition-colors">
                          Clear all filters
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                filtered.map(t => (
                  <ThreatRow
                    key={t.id}
                    threat={t}
                    selected={selectedThreat?.id === t.id}
                    onClick={() => setSelectedThreat(selectedThreat?.id === t.id ? null : t)}
                    onResolve={() => handleResolve(t.id)}
                    onSuppress={() => handleSuppress(t.id)}
                    canAct={canAct}
                    acting={acting}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <span className="text-xs text-muted-foreground">
              {Math.min((page - 1) * 25 + 1, total)}–{Math.min(page * 25, total)} of {total} threats
            </span>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30">
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs text-foreground px-2">{page} / {pages}</span>
              <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30">
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Threat detail panel ── */}
      {selectedThreat && (
        <ThreatDetailPanel
          threat={selectedThreat}
          onClose={() => setSelectedThreat(null)}
          onResolve={handleResolve}
          onSuppress={handleSuppress}
          canAct={canAct}
          acting={acting}
        />
      )}
    </div>
  );
}

// ─── Utility ──────────────────────────────────────────────────────────────────

function buildQs(path: string, params: Record<string, any>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== '' && v != null) qs.set(k, String(v));
  }
  return `${path}?${qs}`;
}
