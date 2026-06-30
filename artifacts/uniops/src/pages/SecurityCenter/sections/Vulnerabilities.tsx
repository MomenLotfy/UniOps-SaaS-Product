import {
  useState, useCallback, useEffect, useRef, useMemo, memo,
} from 'react';
import {
  Bug, Shield, RefreshCw, ChevronLeft, ChevronRight, Search,
  Filter, X, ExternalLink, CheckCircle, Clock, AlertTriangle,
  Package, GitBranch, Box, Server, Layers, Eye, FileText,
  ChevronDown, ChevronUp, AlertCircle, Zap, Database,
  TriangleAlert, ArrowRight, Info, BarChart3, Link2,
  ShieldCheck, EyeOff, Download, Copy,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPatch } from '@/hooks/use-api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Vuln {
  id: string;
  cve_id?: string;
  title: string;
  description?: string;
  severity: string;
  cvss_score?: number;
  status: string;
  package_name?: string;
  package_version?: string;
  fixed_version?: string;
  target?: string;
  image?: string;
  repo_id?: string;
  scan_id?: string;
  references?: string[];
  detected_by?: string[];
  first_seen_at?: string;
  last_seen_at?: string;
  created_at?: string;
  updated_at?: string;
}

interface VulnStats {
  total?: number;
  critical?: number;
  high?: number;
  medium?: number;
  low?: number;
  open?: number;
  patched?: number;
  wont_fix?: number;
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
const SEV_TEXT: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-blue-400',
};
const STATUS_BADGE: Record<string, string> = {
  open:          'bg-red-500/10 text-red-400 border-red-500/20',
  patched:       'bg-green-500/10 text-green-400 border-green-500/20',
  fixed:         'bg-green-500/10 text-green-400 border-green-500/20',
  wont_fix:      'bg-slate-500/10 text-slate-400 border-slate-500/20',
  accepted:      'bg-slate-500/10 text-slate-400 border-slate-500/20',
  accepted_risk: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
  false_positive:'bg-slate-500/10 text-slate-400 border-slate-500/20',
  in_progress:   'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
};
const SCANNER_BADGE: Record<string, string> = {
  trivy:   'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  grype:   'bg-purple-500/10 text-purple-400 border-purple-500/20',
  osv:     'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  deps:    'bg-purple-500/10 text-purple-400 border-purple-500/20',
  sast:    'bg-blue-500/10 text-blue-400 border-blue-500/20',
  secrets: 'bg-red-500/10 text-red-400 border-red-500/20',
  container: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
};

function cvssColor(score?: number): string {
  if (!score) return 'text-muted-foreground';
  if (score >= 9)   return 'text-red-400';
  if (score >= 7)   return 'text-orange-400';
  if (score >= 4)   return 'text-yellow-400';
  return 'text-blue-400';
}

function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60)    return `${s}s ago`;
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function fmtDate(iso?: string): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

function fmtDateShort(iso?: string): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Sk({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// ─── Summary Card ─────────────────────────────────────────────────────────────

function SummaryCard({
  label, value, icon: Icon, color = 'text-blue-400', sub, onClick, loading,
}: {
  label: string; value: string | number;
  icon: React.ElementType; color?: string;
  sub?: string; onClick?: () => void; loading?: boolean;
}) {
  const bg = color.includes('red') ? 'bg-red-500/8' :
             color.includes('orange') ? 'bg-orange-500/8' :
             color.includes('yellow') ? 'bg-yellow-500/8' :
             color.includes('green') ? 'bg-green-500/8' :
             color.includes('purple') ? 'bg-purple-500/8' :
             color.includes('cyan') ? 'bg-cyan-500/8' :
             'bg-blue-500/8';
  return (
    <div onClick={onClick}
      className={clsx(
        'card-base px-3 py-3 flex items-start gap-2.5 min-w-0 transition-colors',
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

// ─── CVE Link ─────────────────────────────────────────────────────────────────

function CveLink({ cveId }: { cveId?: string }) {
  if (!cveId) return <span className="text-muted-foreground text-[10px]">—</span>;
  const isReal = /^CVE-\d{4}-\d+$/i.test(cveId);
  const content = (
    <span className="font-mono text-[11px] text-blue-400 hover:text-blue-300 transition-colors">
      {cveId}
    </span>
  );
  return isReal ? (
    <a href={`https://nvd.nist.gov/vuln/detail/${cveId}`} target="_blank" rel="noreferrer"
      className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
      {content}<ExternalLink className="w-2.5 h-2.5 text-blue-400/50" />
    </a>
  ) : content;
}

// ─── Scanner Badges ───────────────────────────────────────────────────────────

function ScannerBadges({ scanners }: { scanners?: string[] }) {
  if (!scanners || scanners.length === 0) return null;
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {scanners.slice(0, 3).map(s => (
        <span key={s} className={clsx(
          'text-[9px] px-1.5 py-0.5 rounded border font-mono capitalize',
          SCANNER_BADGE[s.toLowerCase()] ?? 'bg-white/5 text-muted-foreground border-white/10',
        )}>{s}</span>
      ))}
    </div>
  );
}

// ─── CVSS Score ───────────────────────────────────────────────────────────────

function CvssScore({ score }: { score?: number }) {
  if (score == null) return <span className="text-muted-foreground text-[10px]">—</span>;
  return (
    <div className="flex items-center gap-1">
      <span className={clsx('text-[11px] font-bold tabular-nums font-mono', cvssColor(score))}>
        {score.toFixed(1)}
      </span>
      <div className="w-10 h-1 rounded-full bg-white/5 overflow-hidden">
        <div className="h-full rounded-full"
          style={{ width: `${(score / 10) * 100}%`, background: score >= 9 ? '#ef4444' : score >= 7 ? '#f97316' : score >= 4 ? '#eab308' : '#3b82f6' }} />
      </div>
    </div>
  );
}

// ─── Fix Badge ────────────────────────────────────────────────────────────────

function FixBadge({ fixedVersion }: { fixedVersion?: string }) {
  if (!fixedVersion) {
    return <span className="text-[10px] text-muted-foreground">No fix</span>;
  }
  return (
    <span className="flex items-center gap-1 text-[10px] text-green-400">
      <CheckCircle className="w-3 h-3" />
      <span className="font-mono">{fixedVersion}</span>
    </span>
  );
}

// ─── Vuln Detail Panel ────────────────────────────────────────────────────────

const PANEL_TABS = ['Overview', 'Package', 'Timeline', 'References'] as const;
type PanelTab = typeof PANEL_TABS[number];

function VulnDetailPanel({
  vuln, onClose, onStatusChange, updating,
}: {
  vuln: Vuln;
  onClose: () => void;
  onStatusChange: (id: string, status: string) => void;
  updating: boolean;
}) {
  const [tab, setTab] = useState<PanelTab>('Overview');

  // Fetch full detail
  const { data: raw } = useApi<any>(`/vulnerabilities/${vuln.id}`);
  const detail: Vuln = (raw?.data ?? raw) ?? vuln;

  const isOpen = !['patched', 'fixed', 'wont_fix', 'accepted', 'accepted_risk', 'false_positive'].includes(detail.status);
  const hasFix = !!detail.fixed_version;

  const refs: string[] = detail.references ?? [];

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
              detail.severity === 'medium' ? 'bg-yellow-500/10' : 'bg-blue-500/10',
            )}>
              <Bug className={clsx('w-4 h-4', SEV_TEXT[detail.severity] ?? 'text-blue-400')} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className={clsx('px-2 py-0.5 text-[10px] font-semibold rounded-md border capitalize', SEV_BADGE[detail.severity] ?? SEV_BADGE.low)}>
                  {detail.severity}
                </span>
                <span className={clsx('px-2 py-0.5 text-[10px] rounded-md border capitalize', STATUS_BADGE[detail.status] ?? 'border-border text-muted-foreground')}>
                  {detail.status}
                </span>
                {hasFix && (
                  <span className="flex items-center gap-0.5 px-2 py-0.5 rounded-md bg-green-500/10 border border-green-500/20 text-[10px] text-green-400">
                    <CheckCircle className="w-2.5 h-2.5" /> Fix Available
                  </span>
                )}
              </div>
              <h2 className="text-sm font-semibold text-foreground leading-snug">{detail.title}</h2>
              {detail.cve_id && (
                <div className="mt-0.5">
                  <CveLink cveId={detail.cve_id} />
                </div>
              )}
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
            { label: 'CVSS',     value: detail.cvss_score != null ? detail.cvss_score.toFixed(1) : '—', color: cvssColor(detail.cvss_score) },
            { label: 'Fix',      value: hasFix ? detail.fixed_version! : 'None',  color: hasFix ? 'text-green-400' : 'text-muted-foreground' },
            { label: 'Detected', value: timeAgo(detail.first_seen_at ?? detail.created_at), color: 'text-foreground' },
          ].map(m => (
            <div key={m.label} className="px-3 py-2.5 bg-[hsl(230_15%_9%)] text-center">
              <div className={clsx('text-sm font-bold tabular-nums truncate', m.color)}>{m.value}</div>
              <div className="text-[10px] text-muted-foreground">{m.label}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex items-center px-4 border-b border-border flex-shrink-0 overflow-x-auto">
          {PANEL_TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx(
                'px-3 py-2.5 text-xs whitespace-nowrap border-b-2 -mb-px transition-colors',
                tab === t ? 'border-indigo-500 text-foreground font-medium' : 'border-transparent text-muted-foreground hover:text-foreground',
              )}>
              {t}
              {t === 'References' && refs.length > 0 && (
                <span className="ml-1 text-[9px] text-muted-foreground/60">({refs.length})</span>
              )}
            </button>
          ))}
        </div>

        {/* Panel content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">

          {/* ── OVERVIEW ── */}
          {tab === 'Overview' && (
            <>
              {detail.description && (
                <div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Description</p>
                  <p className="text-xs text-foreground/80 leading-relaxed">{detail.description}</p>
                </div>
              )}

              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Vulnerability Details</p>
                <div className="space-y-2">
                  {[
                    { label: 'CVE ID',        value: detail.cve_id    ?? '—', mono: true },
                    { label: 'Severity',      value: detail.severity,          },
                    { label: 'CVSS Score',    value: detail.cvss_score != null ? `${detail.cvss_score.toFixed(1)} / 10` : '—' },
                    { label: 'Status',        value: detail.status    ?? '—'   },
                    { label: 'Package',       value: detail.package_name  ?? '—', mono: true },
                    { label: 'Version',       value: detail.package_version ?? '—', mono: true },
                    { label: 'Fixed In',      value: detail.fixed_version ?? 'No fix available', mono: !!detail.fixed_version, color: detail.fixed_version ? 'text-green-400' : undefined },
                    { label: 'Target',        value: detail.target    ?? '—', mono: true },
                    { label: 'Image',         value: detail.image     ?? '—', mono: true },
                    { label: 'First Seen',    value: fmtDate(detail.first_seen_at) },
                    { label: 'Last Seen',     value: fmtDate(detail.last_seen_at)  },
                  ].map(row => (
                    <div key={row.label} className="flex items-baseline gap-2">
                      <span className="text-[10px] text-muted-foreground w-28 flex-shrink-0">{row.label}</span>
                      <span className={clsx('text-[11px] min-w-0 break-all', row.mono ? 'font-mono text-foreground' : 'text-foreground', row.color)}>
                        {row.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Scanners */}
              {detail.detected_by && detail.detected_by.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Detected By</p>
                  <div className="flex flex-wrap gap-1.5">
                    {detail.detected_by.map(s => (
                      <span key={s} className={clsx(
                        'px-2 py-0.5 rounded-md border text-[10px] font-mono capitalize',
                        SCANNER_BADGE[s.toLowerCase()] ?? 'bg-white/5 text-muted-foreground border-white/10',
                      )}>{s}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Business Impact note */}
              <div className="p-3 rounded-xl border border-border bg-white/2">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">Risk Assessment</p>
                <p className="text-xs text-foreground/70 leading-relaxed">
                  Risk prioritization is computed by the backend combining severity, CVSS score, exploit availability, KEV listing, asset criticality, and internet exposure. All scoring is server-side only.
                </p>
              </div>
            </>
          )}

          {/* ── PACKAGE ── */}
          {tab === 'Package' && (
            <>
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Package Information</p>
                <div className="space-y-2">
                  {[
                    { label: 'Package Name',    value: detail.package_name    ?? '—', mono: true },
                    { label: 'Installed',       value: detail.package_version ?? '—', mono: true, color: 'text-red-400' },
                    { label: 'Fix Version',     value: detail.fixed_version   ?? 'No fix available', mono: !!detail.fixed_version, color: detail.fixed_version ? 'text-green-400' : 'text-muted-foreground' },
                    { label: 'Target / Path',   value: detail.target          ?? '—', mono: true },
                    { label: 'Image',           value: detail.image           ?? '—', mono: true },
                  ].map(row => (
                    <div key={row.label} className="flex items-baseline gap-2">
                      <span className="text-[10px] text-muted-foreground w-28 flex-shrink-0">{row.label}</span>
                      <span className={clsx('text-[11px] min-w-0 break-all', row.mono && 'font-mono', row.color ?? 'text-foreground')}>
                        {row.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {detail.fixed_version && (
                <div className="p-3 rounded-xl border border-green-500/20 bg-green-500/5">
                  <p className="text-[10px] font-semibold text-green-400 uppercase tracking-widest mb-1.5">
                    Upgrade Recommendation
                  </p>
                  <p className="text-xs text-foreground/80 leading-relaxed">
                    Upgrade <span className="font-mono text-foreground">{detail.package_name}</span> from{' '}
                    <span className="font-mono text-red-400">{detail.package_version ?? 'current'}</span> to{' '}
                    <span className="font-mono text-green-400">{detail.fixed_version}</span> to resolve this vulnerability.
                  </p>
                  <div className="flex items-center gap-2 mt-2 font-mono text-xs text-muted-foreground">
                    <span className="text-red-400/70 line-through">{detail.package_version}</span>
                    <ArrowRight className="w-3 h-3" />
                    <span className="text-green-400">{detail.fixed_version}</span>
                  </div>
                </div>
              )}

              {/* Dependency visual */}
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Dependency Chain</p>
                <div className="space-y-1">
                  {[
                    { label: detail.target ? 'Application / Target' : 'Asset', value: detail.target ?? detail.image ?? 'Unknown', icon: Server, color: 'text-indigo-400' },
                    { label: 'Package',      value: detail.package_name ?? '—',                    icon: Package,  color: 'text-blue-400' },
                    { label: 'Version',      value: detail.package_version ?? '—',                  icon: Database, color: 'text-yellow-400' },
                    { label: 'Vulnerability',value: detail.cve_id ?? detail.title,                   icon: Bug,      color: 'text-red-400' },
                    { label: 'Fix',          value: detail.fixed_version ?? 'No fix available',      icon: ShieldCheck, color: detail.fixed_version ? 'text-green-400' : 'text-muted-foreground' },
                  ].map((n, i) => {
                    const Icon = n.icon;
                    return (
                      <div key={i}>
                        {i > 0 && <div className="w-0.5 h-3 bg-white/10 ml-3.5" />}
                        <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-white/3 border border-border/50">
                          <Icon className={clsx('w-3.5 h-3.5 flex-shrink-0', n.color)} />
                          <div className="min-w-0 flex-1">
                            <span className="text-[9px] text-muted-foreground">{n.label}</span>
                            <p className="text-[11px] font-mono text-foreground truncate">{n.value}</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}

          {/* ── TIMELINE ── */}
          {tab === 'Timeline' && (
            <div>
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Vulnerability Timeline</p>
              <div className="space-y-0">
                {[
                  { label: 'First Detected',       ts: detail.first_seen_at ?? detail.created_at, done: true,   color: 'bg-red-500' },
                  { label: 'Vulnerability Record',  ts: detail.created_at,                          done: true,   color: 'bg-orange-500' },
                  { label: 'Last Observed',         ts: detail.last_seen_at,                         done: !!detail.last_seen_at, color: 'bg-yellow-500' },
                  { label: 'Remediation Started',   ts: undefined,                                   done: ['in_progress'].includes(detail.status), color: 'bg-blue-500' },
                  { label: 'Patched / Resolved',    ts: undefined,                                   done: ['patched','fixed','resolved','accepted'].includes(detail.status), color: 'bg-green-500' },
                ].map((ev, i, arr) => (
                  <div key={i} className="flex items-start gap-3 relative">
                    {i < arr.length - 1 && (
                      <div className={clsx('absolute left-[9px] top-5 w-0.5 h-full', ev.done ? 'bg-white/15' : 'bg-white/5')} />
                    )}
                    <div className={clsx('w-[18px] h-[18px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 border-2',
                      ev.done ? `${ev.color} border-transparent` : 'bg-transparent border-border',
                    )}>
                      {ev.done && <div className="w-1.5 h-1.5 rounded-full bg-white/80" />}
                    </div>
                    <div className="pb-4 min-w-0">
                      <p className={clsx('text-xs font-medium', ev.done ? 'text-foreground' : 'text-muted-foreground/40')}>
                        {ev.label}
                      </p>
                      {ev.ts && <p className="text-[10px] text-muted-foreground">{fmtDateShort(ev.ts)}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── REFERENCES ── */}
          {tab === 'References' && (
            <div>
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">External References</p>
              {refs.length === 0 && !detail.cve_id ? (
                <p className="text-xs text-muted-foreground">No external references available.</p>
              ) : (
                <div className="space-y-1.5">
                  {/* Auto-generate NVD link for real CVEs */}
                  {detail.cve_id && /^CVE-\d{4}-\d+$/i.test(detail.cve_id) && (
                    <a href={`https://nvd.nist.gov/vuln/detail/${detail.cve_id}`} target="_blank" rel="noreferrer"
                      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/3 border border-border hover:border-white/20 text-xs text-blue-400 hover:text-blue-300 transition-colors group">
                      <Database className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="flex-1 truncate">NVD — {detail.cve_id}</span>
                      <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </a>
                  )}
                  {detail.cve_id && /^CVE-\d{4}-\d+$/i.test(detail.cve_id) && (
                    <a href={`https://www.osv.dev/vulnerability/${detail.cve_id}`} target="_blank" rel="noreferrer"
                      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/3 border border-border hover:border-white/20 text-xs text-blue-400 hover:text-blue-300 transition-colors group">
                      <Shield className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="flex-1 truncate">OSV — {detail.cve_id}</span>
                      <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </a>
                  )}
                  {refs.map((ref, i) => (
                    <a key={i} href={ref} target="_blank" rel="noreferrer"
                      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/3 border border-border hover:border-white/20 text-xs text-blue-400 hover:text-blue-300 transition-colors group">
                      <Link2 className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="flex-1 truncate">{ref}</span>
                      <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Actions footer */}
        <div className="flex items-center gap-2 px-5 py-3 border-t border-border flex-shrink-0 bg-[hsl(230_15%_8%)]">
          {isOpen && (
            <>
              <button onClick={() => onStatusChange(vuln.id, 'patched')} disabled={updating}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-green-600/20 text-green-400 border border-green-500/30 hover:bg-green-600/30 transition-colors disabled:opacity-40 font-medium">
                <ShieldCheck className="w-3 h-3" /> Mark Patched
              </button>
              <button onClick={() => onStatusChange(vuln.id, 'wont_fix')} disabled={updating}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-white/5 text-muted-foreground border border-border hover:text-foreground transition-colors disabled:opacity-40">
                <EyeOff className="w-3 h-3" /> Won't Fix
              </button>
              <button onClick={() => onStatusChange(vuln.id, 'accepted_risk')} disabled={updating}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-white/5 text-muted-foreground border border-border hover:text-foreground transition-colors disabled:opacity-40">
                <CheckCircle className="w-3 h-3" /> Accept Risk
              </button>
            </>
          )}
          {detail.cve_id && (
            <a href={`https://nvd.nist.gov/vuln/detail/${detail.cve_id}`} target="_blank" rel="noreferrer"
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-white/5 text-muted-foreground border border-border hover:text-foreground transition-colors">
              <ExternalLink className="w-3 h-3" /> NVD
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Table Row ────────────────────────────────────────────────────────────────

const VulnRow = memo(function VulnRow({
  vuln, selected, onClick,
}: {
  vuln: Vuln; selected: boolean; onClick: () => void;
}) {
  const hasFix = !!vuln.fixed_version;

  return (
    <tr onClick={onClick}
      className={clsx(
        'border-b border-border/40 cursor-pointer transition-colors',
        selected ? 'bg-indigo-500/8 border-indigo-500/20' : 'hover:bg-white/2',
      )}>
      {/* Severity */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <div className="flex items-center gap-1.5">
          <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', SEV_DOT[vuln.severity] ?? 'bg-slate-500')} />
          <span className={clsx('text-[10px] font-semibold capitalize', SEV_TEXT[vuln.severity] ?? 'text-slate-400')}>
            {vuln.severity}
          </span>
        </div>
      </td>

      {/* CVE */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <CveLink cveId={vuln.cve_id} />
      </td>

      {/* Title */}
      <td className="px-3 py-2.5 max-w-[200px]">
        <p className="text-xs font-medium text-foreground truncate">{vuln.title}</p>
        {vuln.package_name && (
          <p className="text-[10px] font-mono text-muted-foreground truncate">
            {vuln.package_name}{vuln.package_version ? `@${vuln.package_version}` : ''}
          </p>
        )}
      </td>

      {/* CVSS */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <CvssScore score={vuln.cvss_score} />
      </td>

      {/* Fix */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <FixBadge fixedVersion={vuln.fixed_version} />
      </td>

      {/* Target/Image */}
      <td className="px-3 py-2.5 max-w-[130px]">
        <span className="text-[10px] font-mono text-muted-foreground truncate block">
          {vuln.image ?? vuln.target ?? '—'}
        </span>
      </td>

      {/* Scanner */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <ScannerBadges scanners={vuln.detected_by} />
      </td>

      {/* Status */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border capitalize', STATUS_BADGE[vuln.status] ?? 'border-border text-muted-foreground')}>
          {vuln.status.replace(/_/g, ' ')}
        </span>
      </td>

      {/* Detected */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <span className="text-[10px] text-muted-foreground">{timeAgo(vuln.first_seen_at ?? vuln.created_at)}</span>
      </td>

      {/* Actions */}
      <td className="px-3 py-2.5 whitespace-nowrap" onClick={e => e.stopPropagation()}>
        <button onClick={onClick}
          className="flex items-center gap-1 px-2 py-1 text-[10px] rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-white/20 transition-colors">
          <Eye className="w-3 h-3" /> Details
        </button>
      </td>
    </tr>
  );
});

// ─── Grouped View ─────────────────────────────────────────────────────────────

function GroupedRows({
  vulns, selectedId, onSelect, groupBy,
}: {
  vulns: Vuln[]; selectedId: string | null;
  onSelect: (v: Vuln) => void; groupBy: string;
}) {
  const groups = useMemo(() => {
    const map: Record<string, Vuln[]> = {};
    for (const v of vulns) {
      const key = groupBy === 'severity'   ? (v.severity ?? 'unknown') :
                  groupBy === 'package'    ? (v.package_name ?? 'unknown') :
                  groupBy === 'image'      ? (v.image ?? 'unknown') :
                  groupBy === 'status'     ? (v.status ?? 'unknown') :
                  'all';
      (map[key] = map[key] ?? []).push(v);
    }
    return Object.entries(map).sort((a, b) => {
      const order = ['critical', 'high', 'medium', 'low', 'info'];
      const ai = order.indexOf(a[0]); const bi = order.indexOf(b[0]);
      if (ai !== -1 && bi !== -1) return ai - bi;
      return b[1].length - a[1].length;
    });
  }, [vulns, groupBy]);

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  return (
    <>
      {groups.map(([groupKey, items]) => (
        <>
          <tr key={`group-${groupKey}`}
            className="border-b border-border bg-white/2 cursor-pointer"
            onClick={() => setCollapsed(c => ({ ...c, [groupKey]: !c[groupKey] }))}>
            <td colSpan={10} className="px-3 py-2">
              <div className="flex items-center gap-2">
                {collapsed[groupKey]
                  ? <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                  : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
                <span className={clsx('text-xs font-semibold capitalize', SEV_TEXT[groupKey] ?? 'text-foreground')}>
                  {groupKey.replace(/_/g, ' ')}
                </span>
                <span className="text-[10px] text-muted-foreground ml-1">{items.length} vulnerabilities</span>
                {groupBy === 'severity' && (
                  <span className={clsx('w-2 h-2 rounded-full ml-auto', SEV_DOT[groupKey] ?? 'bg-slate-500')} />
                )}
              </div>
            </td>
          </tr>
          {!collapsed[groupKey] && items.map(v => (
            <VulnRow key={v.id} vuln={v} selected={selectedId === v.id} onClick={() => onSelect(v)} />
          ))}
        </>
      ))}
    </>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

const GROUP_OPTIONS = [
  { value: '',         label: 'No grouping' },
  { value: 'severity', label: 'Severity' },
  { value: 'package',  label: 'Package' },
  { value: 'image',    label: 'Image' },
  { value: 'status',   label: 'Status' },
] as const;

export default function Vulnerabilities() {
  const [severity,   setSeverity]   = useState('');
  const [status,     setStatus]     = useState('open');
  const [search,     setSearch]     = useState('');
  const [searchInp,  setSearchInp]  = useState('');
  const [showFilters,setShowFilters] = useState(false);
  const [groupBy,    setGroupBy]    = useState('');
  const [page,       setPage]       = useState(1);
  const [selected,   setSelected]   = useState<Vuln | null>(null);
  const [updating,   setUpdating]   = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>();

  // Debounced search
  useEffect(() => {
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { setSearch(searchInp); setPage(1); }, 350);
    return () => clearTimeout(searchTimer.current);
  }, [searchInp]);

  // Build query
  const qs = buildQs({ page, page_size: 25, severity, status });

  const { data: raw, loading, refetch }         = useApi<any>(`/vulnerabilities?${qs}`);
  const { data: statsRaw, refetch: refetchStats } = useApi<any>('/vulnerabilities/stats');

  // Auto-refresh every 60s
  useEffect(() => {
    const id = setInterval(() => { refetch(); refetchStats(); }, 60_000);
    return () => clearInterval(id);
  }, [refetch, refetchStats]);

  const result = raw?.data ?? raw;
  const allVulns: Vuln[] = result?.data ?? [];
  const total   = result?.total ?? 0;
  const pages   = result?.pages ?? 1;
  const stats: VulnStats = statsRaw?.data ?? statsRaw ?? {};

  // Client-side search
  const vulns = useMemo(() => {
    if (!search) return allVulns;
    const q = search.toLowerCase();
    return allVulns.filter(v =>
      v.cve_id?.toLowerCase().includes(q) ||
      v.title?.toLowerCase().includes(q) ||
      v.package_name?.toLowerCase().includes(q) ||
      v.target?.toLowerCase().includes(q) ||
      v.image?.toLowerCase().includes(q) ||
      v.status?.toLowerCase().includes(q)
    );
  }, [allVulns, search]);

  // Derived stats
  const fixableCount = useMemo(() => allVulns.filter(v => !!v.fixed_version).length, [allVulns]);
  const noFixCount   = useMemo(() => allVulns.filter(v => !v.fixed_version).length, [allVulns]);
  const avgCvss      = useMemo(() => {
    const scored = allVulns.filter(v => v.cvss_score != null);
    if (!scored.length) return null;
    return scored.reduce((a, v) => a + (v.cvss_score ?? 0), 0) / scored.length;
  }, [allVulns]);
  const statsLoading = !statsRaw;

  const handleStatusChange = useCallback(async (id: string, newStatus: string) => {
    setUpdating(true);
    try {
      await apiPatch(`/vulnerabilities/${id}`, { status: newStatus });
      refetch(); refetchStats();
      setSelected(null);
    } catch {}
    finally { setUpdating(false); }
  }, [refetch, refetchStats]);

  const handleRefresh = useCallback(() => { refetch(); refetchStats(); }, [refetch, refetchStats]);

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-bold text-foreground flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-orange-500/10 flex items-center justify-center">
              <Bug className="w-4 h-4 text-orange-400" />
            </div>
            Vulnerability Management
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {total} findings · deduplicated by CVE + package · auto-refresh 60s
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <input
              value={searchInp}
              onChange={e => setSearchInp(e.target.value)}
              placeholder="Search CVE, package, image, target…"
              className="w-56 pl-8 pr-3 py-1.5 text-xs bg-white/5 border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-indigo-500/50"
            />
            {searchInp && (
              <button onClick={() => { setSearch(''); setSearchInp(''); }}
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

      {/* ── Summary Cards row 1: severity ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
        <SummaryCard label="Total"    value={stats.total ?? 0}   icon={Bug}          color="text-foreground" loading={statsLoading}
          onClick={() => { setSeverity(''); setStatus(''); setPage(1); }} />
        <SummaryCard label="Critical" value={stats.critical ?? 0} icon={AlertCircle}  color="text-red-400"    loading={statsLoading}
          onClick={() => { setSeverity('critical'); setPage(1); }} />
        <SummaryCard label="High"     value={stats.high ?? 0}     icon={AlertTriangle} color="text-orange-400" loading={statsLoading}
          onClick={() => { setSeverity('high'); setPage(1); }} />
        <SummaryCard label="Medium"   value={stats.medium ?? 0}   icon={TriangleAlert} color="text-yellow-400" loading={statsLoading}
          onClick={() => { setSeverity('medium'); setPage(1); }} />
        <SummaryCard label="Low"      value={stats.low ?? 0}       icon={Info}         color="text-blue-400"   loading={statsLoading}
          onClick={() => { setSeverity('low'); setPage(1); }} />
        <SummaryCard label="Open"     value={stats.open ?? 0}      icon={AlertCircle}  color="text-red-400"    loading={statsLoading}
          onClick={() => { setStatus('open'); setPage(1); }} />
        <SummaryCard label="Patched"  value={stats.patched ?? 0}   icon={ShieldCheck}  color="text-green-400"  loading={statsLoading}
          onClick={() => { setStatus('patched'); setPage(1); }} />
        <SummaryCard label="Won't Fix" value={stats.wont_fix ?? 0} icon={EyeOff}       color="text-slate-400"  loading={statsLoading}
          onClick={() => { setStatus('wont_fix'); setPage(1); }} />
      </div>

      {/* ── Summary Cards row 2: derived ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <SummaryCard label="Fix Available"  value={fixableCount}
          icon={CheckCircle} color="text-green-400"
          sub="packages with fixed versions"
          onClick={() => {}} />
        <SummaryCard label="No Fix Yet"     value={noFixCount}
          icon={Clock} color="text-orange-400"
          sub="packages without patch"
          onClick={() => {}} />
        <SummaryCard label="Avg CVSS"       value={avgCvss != null ? avgCvss.toFixed(1) : '—'}
          icon={BarChart3} color={avgCvss != null && avgCvss >= 7 ? 'text-orange-400' : 'text-blue-400'} />
        <SummaryCard label="Scanners Active" value={
          [...new Set(allVulns.flatMap(v => v.detected_by ?? []))].length || '—'
        } icon={Zap} color="text-purple-400" sub="trivy / grype / osv" />
      </div>

      {/* ── Filters ── */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {/* Severity pills */}
        <div className="flex items-center gap-0.5">
          {(['', 'critical', 'high', 'medium', 'low'] as const).map(s => (
            <button key={s} onClick={() => { setSeverity(s); setPage(1); }}
              className={clsx(
                'px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-colors whitespace-nowrap',
                severity === s
                  ? s === 'critical' ? 'bg-red-600/30 text-red-400 border border-red-500/30' :
                    s === 'high'     ? 'bg-orange-600/30 text-orange-400 border border-orange-500/30' :
                    s === 'medium'   ? 'bg-yellow-600/30 text-yellow-400 border border-yellow-500/30' :
                    s === 'low'      ? 'bg-blue-600/30 text-blue-400 border border-blue-500/30' :
                    'bg-white/8 text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}>
              {s || 'All'}
            </button>
          ))}
        </div>

        <div className="w-px h-4 bg-border mx-1" />

        {/* Status pills */}
        {(['open', 'patched', 'wont_fix', 'accepted_risk'] as const).map(s => (
          <button key={s} onClick={() => { setStatus(status === s ? '' : s); setPage(1); }}
            className={clsx(
              'px-2.5 py-1 rounded-md text-xs capitalize transition-colors whitespace-nowrap',
              status === s ? 'bg-white/8 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground',
            )}>
            {s.replace(/_/g, ' ')}
          </button>
        ))}

        <div className="w-px h-4 bg-border mx-1" />

        {/* Group by */}
        <select value={groupBy} onChange={e => setGroupBy(e.target.value)}
          className="text-xs px-2 py-1 bg-white/5 border border-border rounded-md text-muted-foreground focus:outline-none focus:text-foreground">
          {GROUP_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>

        <button onClick={() => setShowFilters(f => !f)}
          className={clsx(
            'flex items-center gap-1 px-2.5 py-1 rounded-md text-xs border transition-colors',
            showFilters ? 'border-indigo-500/40 text-indigo-400 bg-indigo-500/8' : 'border-border text-muted-foreground hover:text-foreground',
          )}>
          <Filter className="w-3 h-3" /> Filters
        </button>

        {/* Active chips */}
        {severity && (
          <span className={clsx('flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border cursor-pointer', SEV_BADGE[severity] ?? SEV_BADGE.low)}
            onClick={() => setSeverity('')}>
            {severity} <X className="w-2.5 h-2.5" />
          </span>
        )}
        {status && status !== 'open' && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border border-border text-muted-foreground cursor-pointer"
            onClick={() => setStatus('open')}>
            {status.replace(/_/g, ' ')} <X className="w-2.5 h-2.5" />
          </span>
        )}

        <span className="ml-auto text-xs text-muted-foreground">{vulns.length} shown</span>
      </div>

      {/* ── Extended filters ── */}
      {showFilters && (
        <div className="card-base p-3 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
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
            <label className="text-[10px] text-muted-foreground block mb-1">Status</label>
            <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
              className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
              <option value="">All Statuses</option>
              {['open', 'patched', 'wont_fix', 'accepted_risk', 'false_positive', 'in_progress'].map(s => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">Fix Available</label>
            <select className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
              <option value="">Any</option>
              <option value="yes">Has Fix</option>
              <option value="no">No Fix</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">Group By</label>
            <select value={groupBy} onChange={e => setGroupBy(e.target.value)}
              className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
              {GROUP_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label || 'None'}</option>)}
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
                  'Severity', 'CVE', 'Title / Package', 'CVSS',
                  'Fix Version', 'Target / Image', 'Scanner',
                  'Status', 'Detected', 'Actions',
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
              ) : vulns.length === 0 ? (
                <tr>
                  <td colSpan={10}>
                    <div className="flex flex-col items-center gap-3 py-14 text-center">
                      <div className="w-14 h-14 rounded-2xl bg-green-500/8 border border-green-500/20 flex items-center justify-center">
                        <Shield className="w-7 h-7 text-green-400 opacity-60" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-foreground mb-1">No vulnerabilities detected</p>
                        <p className="text-xs text-muted-foreground max-w-sm">
                          {severity || status || search
                            ? 'No vulnerabilities match the current filters. Try adjusting or clearing your filters.'
                            : 'No vulnerabilities have been detected yet. Connect repositories, images, or clusters to start scanning with Trivy, Grype, or OSV.'}
                        </p>
                      </div>
                      {(severity || status !== 'open' || search) && (
                        <button onClick={() => { setSeverity(''); setStatus('open'); setSearch(''); setSearchInp(''); setPage(1); }}
                          className="text-xs text-indigo-400 hover:text-indigo-300 underline transition-colors">
                          Clear all filters
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : groupBy ? (
                <GroupedRows
                  vulns={vulns}
                  selectedId={selected?.id ?? null}
                  onSelect={setSelected}
                  groupBy={groupBy}
                />
              ) : (
                vulns.map(v => (
                  <VulnRow
                    key={v.id}
                    vuln={v}
                    selected={selected?.id === v.id}
                    onClick={() => setSelected(selected?.id === v.id ? null : v)}
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
              {Math.min((page - 1) * 25 + 1, total)}–{Math.min(page * 25, total)} of {total} vulnerabilities
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

      {/* ── Detail Panel ── */}
      {selected && (
        <VulnDetailPanel
          vuln={selected}
          onClose={() => setSelected(null)}
          onStatusChange={handleStatusChange}
          updating={updating}
        />
      )}
    </div>
  );
}

// ─── Utility ──────────────────────────────────────────────────────────────────

function buildQs(params: Record<string, any>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== '' && v != null) qs.set(k, String(v));
  }
  return qs.toString();
}
