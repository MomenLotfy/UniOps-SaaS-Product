import {
  useState, useEffect, useCallback, useRef, useMemo, memo,
} from 'react';
import {
  Shield, RefreshCw, Activity, AlertTriangle, Search, Filter,
  X, ChevronRight, ChevronDown, ChevronUp, ExternalLink, Download,
  Globe, Database, Zap, Target, Clock, CheckCircle, AlertCircle,
  Info, Eye, Server, Network, Hash, Mail, FileCode, Key,
  BarChart3, Layers, Users, Bug, Crosshair, Radio, Settings,
  TrendingUp, ArrowUpRight, Link2, ShieldCheck, ShieldOff,
  TriangleAlert, Package, Box, GitBranch, Cpu, FileText,
  Play, Loader2,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import type {
  IntelligenceSummary, IntelligenceFeed, IntelligenceRecord,
  IOC, ThreatActor, MalwareFamily, AttackTechnique, RecordPage, IOCPage,
} from '@/services/api/intelligence';

// ─── Constants ────────────────────────────────────────────────────────────────

const SEV: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border border-red-500/30',
  high:     'bg-orange-500/15 text-orange-400 border border-orange-500/30',
  medium:   'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
  low:      'bg-blue-500/15 text-blue-400 border border-blue-500/30',
  info:     'bg-slate-500/15 text-slate-400 border border-slate-500/30',
  unknown:  'bg-slate-500/10 text-slate-500 border border-slate-500/20',
};

const SEV_DOT: Record<string, string> = {
  critical: 'bg-red-500',
  high:     'bg-orange-500',
  medium:   'bg-yellow-500',
  low:      'bg-blue-500',
  info:     'bg-slate-400',
  unknown:  'bg-slate-600',
};

const CONF: Record<string, string> = {
  high:     'text-green-400',
  medium:   'text-yellow-400',
  low:      'text-slate-400',
  uncertain:'text-slate-500',
};

const IOC_ICON: Record<string, React.ElementType> = {
  ip:          Network,
  domain:      Globe,
  url:         Link2,
  hash:        Hash,
  email:       Mail,
  filename:    FileCode,
  registry:    Key,
  process:     Cpu,
  mutex:       Box,
  certificate: Shield,
};

const TABS = [
  { id: 'overview',   label: 'Overview',        icon: BarChart3 },
  { id: 'feeds',      label: 'Feeds',           icon: Radio },
  { id: 'records',    label: 'Intelligence',     icon: Database },
  { id: 'iocs',       label: 'IOCs',            icon: Target },
  { id: 'actors',     label: 'Threat Actors',   icon: Users },
  { id: 'malware',    label: 'Malware',         icon: Bug },
  { id: 'techniques', label: 'ATT&CK',          icon: Crosshair },
] as const;

type Tab = typeof TABS[number]['id'];

// ─── Small helpers ────────────────────────────────────────────────────────────

const SevBadge = memo(({ sev }: { sev: string }) => (
  <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide', SEV[sev] ?? SEV.unknown)}>
    {sev || 'unknown'}
  </span>
));

const ConfBadge = memo(({ conf }: { conf: string }) => (
  <span className={clsx('text-xs font-medium', CONF[conf] ?? 'text-slate-500')}>
    {conf}
  </span>
));

const KevBadge = memo(() => (
  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-red-500/20 text-red-400 border border-red-500/40">
    KEV
  </span>
));

const StatusDot = memo(({ status }: { status: string }) => {
  const color =
    status === 'healthy'  ? 'bg-green-500 shadow-green-500/50' :
    status === 'degraded' ? 'bg-yellow-500 shadow-yellow-500/50' :
    status === 'active'   ? 'bg-green-500 shadow-green-500/50' :
    'bg-red-500 shadow-red-500/50';
  return <span className={clsx('inline-block w-2 h-2 rounded-full shadow', color)} />;
});

function fmt(iso: string | null | undefined): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return iso; }
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); }
  catch { return iso; }
}

function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return '—';
  return `${Math.round(ms)}ms`;
}

function epssColor(score: number): string {
  if (score >= 0.9) return 'text-red-400';
  if (score >= 0.7) return 'text-orange-400';
  if (score >= 0.4) return 'text-yellow-400';
  return 'text-slate-400';
}

// ─── Empty State ──────────────────────────────────────────────────────────────

const EmptyState = memo(({ title, subtitle, icon: Icon, action }: {
  title: string; subtitle: string; icon?: React.ElementType; action?: React.ReactNode;
}) => (
  <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
    <div className="w-14 h-14 rounded-2xl bg-surface-2 border border-white/5 flex items-center justify-center">
      {Icon ? <Icon size={24} className="text-muted-foreground" /> : <Shield size={24} className="text-muted-foreground" />}
    </div>
    <div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="text-xs text-muted-foreground mt-1 max-w-xs">{subtitle}</p>
    </div>
    {action}
  </div>
));

// ─── Summary Cards ────────────────────────────────────────────────────────────

const StatCard = memo(({ label, value, icon: Icon, color, sub }: {
  label: string; value: string | number; icon: React.ElementType;
  color: string; sub?: string;
}) => (
  <div className="bg-surface-2 border border-white/5 rounded-xl p-4 flex items-start gap-3 hover:border-white/10 transition-colors">
    <div className={clsx('p-2 rounded-lg shrink-0', color)}>
      <Icon size={16} className="opacity-80" />
    </div>
    <div className="min-w-0">
      <p className="text-[11px] text-muted-foreground truncate">{label}</p>
      <p className="text-xl font-bold text-foreground leading-none mt-0.5">{value}</p>
      {sub && <p className="text-[10px] text-muted-foreground mt-1">{sub}</p>}
    </div>
  </div>
));

// ─── Detail Drawer ────────────────────────────────────────────────────────────

const DetailDrawer = memo(({ record, onClose }: {
  record: IntelligenceRecord; onClose: () => void;
}) => {
  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl flex flex-col bg-surface-1 border-l border-white/10 shadow-2xl">
      {/* Header */}
      <div className="flex items-start gap-3 p-5 border-b border-white/8">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <SevBadge sev={record.severity} />
            {record.is_kev && <KevBadge />}
            <span className="text-[10px] text-muted-foreground uppercase tracking-wide border border-white/10 px-1.5 py-0.5 rounded">
              {record.type}
            </span>
          </div>
          <h2 className="text-base font-semibold text-foreground mt-2 leading-snug">{record.title}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{record.id}</p>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-md hover:bg-white/8 text-muted-foreground hover:text-foreground transition-colors shrink-0">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {/* Scores row */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-surface-2 rounded-lg p-3 text-center border border-white/5">
            <p className="text-[10px] text-muted-foreground">CVSS</p>
            <p className={clsx('text-2xl font-bold mt-0.5', record.cvss_score != null && record.cvss_score >= 9 ? 'text-red-400' : record.cvss_score != null && record.cvss_score >= 7 ? 'text-orange-400' : 'text-foreground')}>
              {record.cvss_score != null ? record.cvss_score.toFixed(1) : '—'}
            </p>
          </div>
          <div className="bg-surface-2 rounded-lg p-3 text-center border border-white/5">
            <p className="text-[10px] text-muted-foreground">EPSS</p>
            <p className={clsx('text-2xl font-bold mt-0.5', epssColor(record.epss_score))}>
              {record.epss_score > 0 ? `${(record.epss_score * 100).toFixed(1)}%` : '—'}
            </p>
          </div>
          <div className="bg-surface-2 rounded-lg p-3 text-center border border-white/5">
            <p className="text-[10px] text-muted-foreground">Confidence</p>
            <p className={clsx('text-lg font-bold mt-0.5 capitalize', CONF[record.confidence] ?? 'text-slate-400')}>
              {record.confidence}
            </p>
          </div>
        </div>

        {/* Description */}
        {record.description && (
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Description</h3>
            <p className="text-sm text-foreground/80 leading-relaxed">{record.description}</p>
          </section>
        )}

        {/* MITRE / Threat Actor */}
        {(record.mitre_technique || record.threat_actor || record.malware) && (
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Threat Context</h3>
            <div className="space-y-2">
              {record.mitre_technique && (
                <div className="flex items-center justify-between py-1.5 border-b border-white/5">
                  <span className="text-xs text-muted-foreground">MITRE Technique</span>
                  <span className="text-xs font-mono text-blue-400">{record.mitre_technique}</span>
                </div>
              )}
              {record.threat_actor && (
                <div className="flex items-center justify-between py-1.5 border-b border-white/5">
                  <span className="text-xs text-muted-foreground">Threat Actor</span>
                  <span className="text-xs text-orange-400 font-medium">{record.threat_actor}</span>
                </div>
              )}
              {record.malware && (
                <div className="flex items-center justify-between py-1.5 border-b border-white/5">
                  <span className="text-xs text-muted-foreground">Malware</span>
                  <span className="text-xs text-red-400 font-medium">{record.malware}</span>
                </div>
              )}
            </div>
          </section>
        )}

        {/* CWE / CAPEC */}
        {(record.cwe_ids.length > 0 || record.capec_ids.length > 0) && (
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Classifications</h3>
            <div className="space-y-2">
              {record.cwe_ids.length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground mb-1">CWE</p>
                  <div className="flex flex-wrap gap-1">
                    {record.cwe_ids.map(c => (
                      <span key={c} className="text-[10px] bg-purple-500/10 text-purple-400 border border-purple-500/20 px-1.5 py-0.5 rounded font-mono">{c}</span>
                    ))}
                  </div>
                </div>
              )}
              {record.capec_ids.length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground mb-1">CAPEC</p>
                  <div className="flex flex-wrap gap-1">
                    {record.capec_ids.map(c => (
                      <span key={c} className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded font-mono">{c}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Affected Products */}
        {record.affected_products.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Affected Products</h3>
            <div className="flex flex-wrap gap-1">
              {record.affected_products.map((p, i) => (
                <span key={i} className="text-[10px] bg-surface-2 text-foreground/70 border border-white/8 px-1.5 py-0.5 rounded">{p}</span>
              ))}
            </div>
          </section>
        )}

        {/* Sources */}
        {record.sources.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Intelligence Sources</h3>
            <div className="flex flex-wrap gap-1">
              {record.sources.map(s => (
                <span key={s} className="text-[10px] bg-green-500/10 text-green-400 border border-green-500/20 px-1.5 py-0.5 rounded font-medium">{s}</span>
              ))}
            </div>
          </section>
        )}

        {/* Timeline */}
        <section>
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Timeline</h3>
          <div className="space-y-0">
            {[
              { label: 'Published', date: record.published_at },
              { label: 'Last Updated', date: record.updated_at },
            ].filter(e => e.date).map((e, i) => (
              <div key={i} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
                <div className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                <span className="text-xs text-muted-foreground flex-1">{e.label}</span>
                <span className="text-xs text-foreground">{fmtTime(e.date)}</span>
              </div>
            ))}
          </div>
        </section>

        {/* References */}
        {record.references.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">References</h3>
            <div className="space-y-1">
              {record.references.slice(0, 8).map((ref, i) => (
                <a key={i} href={ref} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 truncate group transition-colors">
                  <ExternalLink size={10} className="shrink-0 opacity-60 group-hover:opacity-100" />
                  <span className="truncate">{ref}</span>
                </a>
              ))}
              {record.references.length > 8 && (
                <p className="text-xs text-muted-foreground">+{record.references.length - 8} more</p>
              )}
            </div>
          </section>
        )}
      </div>

      {/* Footer actions */}
      <div className="p-4 border-t border-white/8 flex items-center gap-2">
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors">
          <FileText size={12} /> Export JSON
        </button>
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 hover:bg-white/10 text-foreground border border-white/10 rounded-md transition-colors">
          <Download size={12} /> Export CSV
        </button>
        {record.id.startsWith('CVE-') && (
          <a href={`https://nvd.nist.gov/vuln/detail/${record.id}`} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 hover:bg-white/10 text-foreground border border-white/10 rounded-md transition-colors ml-auto">
            <ExternalLink size={12} /> NVD
          </a>
        )}
      </div>
    </div>
  );
});

// ─── Overview Tab ─────────────────────────────────────────────────────────────

const OverviewTab = memo(({ summary, feeds, onRefresh, refreshing }: {
  summary: IntelligenceSummary | null;
  feeds: IntelligenceFeed[];
  onRefresh: () => void;
  refreshing: boolean;
}) => {
  const cards = summary ? [
    { label: 'Total Records',          value: summary.total_records.toLocaleString(),      icon: Database,    color: 'bg-blue-500/10 text-blue-400' },
    { label: 'Critical Advisories',    value: summary.critical_advisories.toLocaleString(), icon: AlertTriangle, color: 'bg-red-500/10 text-red-400' },
    { label: 'New CVEs Today',         value: summary.new_cves_today.toLocaleString(),      icon: TrendingUp,  color: 'bg-orange-500/10 text-orange-400' },
    { label: 'KEV CVEs',               value: summary.kev_cves.toLocaleString(),            icon: Target,      color: 'bg-red-500/10 text-red-400' },
    { label: 'High EPSS (≥70%)',       value: summary.high_epss.toLocaleString(),           icon: Zap,         color: 'bg-yellow-500/10 text-yellow-400' },
    { label: 'Active Campaigns',       value: summary.active_campaigns.toLocaleString(),    icon: Radio,       color: 'bg-purple-500/10 text-purple-400' },
    { label: 'Threat Actors',          value: summary.known_threat_actors.toLocaleString(), icon: Users,       color: 'bg-orange-500/10 text-orange-400' },
    { label: 'Malware Families',       value: summary.malware_families.toLocaleString(),    icon: Bug,         color: 'bg-red-500/10 text-red-400' },
    { label: 'IOCs',                   value: summary.ioc_count.toLocaleString(),           icon: Target,      color: 'bg-blue-500/10 text-blue-400' },
    { label: 'High Confidence',        value: summary.high_confidence.toLocaleString(),     icon: ShieldCheck, color: 'bg-green-500/10 text-green-400' },
    { label: 'Active Providers',       value: `${summary.active_providers} / ${summary.healthy_providers} healthy`, icon: Activity, color: 'bg-green-500/10 text-green-400' },
    { label: 'Last Feed Update',       value: summary.last_feed_update ? fmt(summary.last_feed_update) : 'Never', icon: Clock, color: 'bg-slate-500/10 text-slate-400',
      sub: summary.last_feed_update ? fmtTime(summary.last_feed_update) : undefined },
  ] : [];

  const noProviders = summary && summary.active_providers === 0;

  return (
    <div className="space-y-6">
      {noProviders ? (
        <EmptyState
          title="No intelligence providers connected."
          subtitle="Connect intelligence sources like NVD, CISA KEV, or VirusTotal to start aggregating threat data."
          icon={Shield}
          action={
            <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors">
              <Settings size={14} /> Configure Providers
            </button>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
            {!summary
              ? Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="bg-surface-2 border border-white/5 rounded-xl p-4 h-20 animate-pulse" />
              ))
              : cards.map(c => <StatCard key={c.label} {...c} />)
            }
          </div>

          {/* Feed health quick view */}
          {feeds.length > 0 && (
            <div className="bg-surface-2 border border-white/5 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-foreground mb-4">Feed Health Overview</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                {feeds.map(f => (
                  <div key={f.provider_id} className="flex items-center gap-2 p-2.5 bg-surface-1 rounded-lg border border-white/5">
                    <StatusDot status={f.status} />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{f.name}</p>
                      <p className="text-[10px] text-muted-foreground">{f.records.toLocaleString()} records</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
});

// ─── Feeds Tab ────────────────────────────────────────────────────────────────

const FeedsTab = memo(({ feeds, onSync, syncing }: {
  feeds: IntelligenceFeed[];
  onSync: (id: string) => void;
  syncing: string | null;
}) => {
  if (feeds.length === 0) {
    return (
      <EmptyState
        title="No intelligence providers connected."
        subtitle="Configure providers to start ingesting threat intelligence from NVD, CISA KEV, VirusTotal, and more."
        icon={Radio}
        action={
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors">
            <Settings size={14} /> Configure Providers
          </button>
        }
      />
    );
  }

  return (
    <div className="bg-surface-2 border border-white/5 rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/8 bg-surface-1/50">
            {['Provider', 'Status', 'Last Sync', 'Records', 'Errors', 'Latency', 'Health', ''].map(h => (
              <th key={h} className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-4 py-3">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {feeds.map(f => (
            <tr key={f.provider_id} className="border-b border-white/5 hover:bg-white/3 transition-colors">
              <td className="px-4 py-3">
                <div>
                  <p className="text-xs font-semibold text-foreground">{f.name}</p>
                  <p className="text-[10px] text-muted-foreground font-mono">{f.provider_id}</p>
                </div>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-1.5">
                  <StatusDot status={f.status} />
                  <span className="text-xs capitalize">{f.status}</span>
                </div>
              </td>
              <td className="px-4 py-3">
                <span className="text-xs text-muted-foreground">{f.last_sync ? fmtTime(f.last_sync) : '—'}</span>
              </td>
              <td className="px-4 py-3">
                <span className="text-xs font-mono text-foreground">{f.records.toLocaleString()}</span>
              </td>
              <td className="px-4 py-3">
                <span className={clsx('text-xs font-mono', f.errors > 0 ? 'text-red-400' : 'text-muted-foreground')}>
                  {f.errors}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="text-xs font-mono text-muted-foreground">{fmtMs(f.latency_ms)}</span>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-1.5">
                  <div className={clsx('w-12 h-1.5 rounded-full overflow-hidden bg-surface-1')}>
                    <div className={clsx('h-full rounded-full transition-all', f.status === 'healthy' ? 'bg-green-500 w-full' : f.status === 'degraded' ? 'bg-yellow-500 w-3/4' : 'bg-red-500 w-1/4')} />
                  </div>
                </div>
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => onSync(f.provider_id)}
                  disabled={syncing === f.provider_id}
                  className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium bg-surface-1 hover:bg-white/10 border border-white/10 text-foreground rounded-md transition-colors disabled:opacity-50"
                >
                  {syncing === f.provider_id
                    ? <Loader2 size={10} className="animate-spin" />
                    : <Play size={10} />
                  }
                  Sync
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});

// ─── Records Tab ──────────────────────────────────────────────────────────────

const RecordsTab = memo(({ onSelectRecord }: { onSelectRecord: (r: IntelligenceRecord) => void }) => {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [severity, setSeverity] = useState('');
  const [kevOnly, setKevOnly] = useState(false);
  const [highEpss, setHighEpss] = useState(false);
  const [page, setPage] = useState(1);
  const [sortCol, setSortCol] = useState<string>('severity');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  const params = useMemo(() => {
    const p: Record<string, any> = { page, page_size: 50 };
    if (severity) p.severity = severity;
    if (debouncedSearch) p.search = debouncedSearch;
    if (kevOnly) p.kev_only = true;
    if (highEpss) p.high_epss = true;
    return p;
  }, [page, severity, debouncedSearch, kevOnly, highEpss]);

  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();
  const { data, loading, error, refetch } = useApi<RecordPage>(`/intelligence/records?${qs}`);

  const records = data?.data ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  const sorted = useMemo(() => {
    const arr = [...records];
    arr.sort((a, b) => {
      let av: any = (a as any)[sortCol] ?? '';
      let bv: any = (b as any)[sortCol] ?? '';
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'asc' ? av - bv : bv - av;
      return sortDir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return arr;
  }, [records, sortCol, sortDir]);

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortDir('desc'); }
  };

  const SortIcon = ({ col }: { col: string }) => sortCol === col
    ? (sortDir === 'desc' ? <ChevronDown size={10} /> : <ChevronUp size={10} />)
    : null;

  const SEVS = ['critical', 'high', 'medium', 'low', 'info'];

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap sticky top-0 z-10 bg-surface-1/95 backdrop-blur-sm py-2">
        <div className="relative flex-1 min-w-48">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search CVE, actor, malware, technique…"
            className="w-full bg-surface-2 border border-white/10 rounded-lg pl-8 pr-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/50 transition-colors"
          />
          {search && (
            <button onClick={() => { setSearch(''); setPage(1); }} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
              <X size={12} />
            </button>
          )}
        </div>
        <select
          value={severity}
          onChange={e => { setSeverity(e.target.value); setPage(1); }}
          className="bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:border-blue-500/50"
        >
          <option value="">All Severities</option>
          {SEVS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
        </select>
        <button
          onClick={() => { setKevOnly(v => !v); setPage(1); }}
          className={clsx('px-3 py-2 text-xs font-medium rounded-lg border transition-colors', kevOnly ? 'bg-red-500/20 text-red-400 border-red-500/40' : 'bg-surface-2 text-muted-foreground border-white/10 hover:text-foreground')}
        >
          KEV Only
        </button>
        <button
          onClick={() => { setHighEpss(v => !v); setPage(1); }}
          className={clsx('px-3 py-2 text-xs font-medium rounded-lg border transition-colors', highEpss ? 'bg-orange-500/20 text-orange-400 border-orange-500/40' : 'bg-surface-2 text-muted-foreground border-white/10 hover:text-foreground')}
        >
          High EPSS
        </button>
        <button onClick={() => refetch()} className="p-2 rounded-lg bg-surface-2 border border-white/10 text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
        </button>
        <span className="text-xs text-muted-foreground">{total.toLocaleString()} records</span>
      </div>

      {/* Table */}
      {loading && records.length === 0 ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-12 bg-surface-2 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <EmptyState title="Failed to load records" subtitle={error} icon={AlertCircle} />
      ) : records.length === 0 ? (
        <EmptyState title="No intelligence records" subtitle="No intelligence matches your current filters. Adjust filters or wait for providers to sync." icon={Database} />
      ) : (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-surface-1/30">
                {[
                  { key: 'title',          label: 'Title' },
                  { key: 'type',           label: 'Type' },
                  { key: 'severity',       label: 'Severity' },
                  { key: 'cvss_score',     label: 'CVSS' },
                  { key: 'epss_score',     label: 'EPSS' },
                  { key: 'is_kev',         label: 'KEV' },
                  { key: 'threat_actor',   label: 'Actor' },
                  { key: 'mitre_technique',label: 'MITRE' },
                  { key: 'confidence',     label: 'Confidence' },
                  { key: 'published_at',   label: 'Published' },
                  { key: '',               label: '' },
                ].map(col => (
                  <th
                    key={col.key}
                    onClick={() => col.key && toggleSort(col.key)}
                    className={clsx(
                      'text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 py-3',
                      col.key && 'cursor-pointer hover:text-foreground select-none'
                    )}
                  >
                    <span className="flex items-center gap-1">{col.label}<SortIcon col={col.key} /></span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map(r => (
                <tr
                  key={r.id}
                  onClick={() => onSelectRecord(r)}
                  className="border-b border-white/4 hover:bg-white/4 cursor-pointer transition-colors group"
                >
                  <td className="px-3 py-2.5 max-w-xs">
                    <div className="truncate font-medium text-foreground/90 group-hover:text-foreground">{r.title}</div>
                    <div className="text-[10px] text-muted-foreground font-mono">{r.id}</div>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="text-[10px] uppercase tracking-wide border border-white/10 px-1.5 py-0.5 rounded text-muted-foreground">
                      {r.type}
                    </span>
                  </td>
                  <td className="px-3 py-2.5"><SevBadge sev={r.severity} /></td>
                  <td className="px-3 py-2.5">
                    <span className={clsx('font-mono', r.cvss_score != null && r.cvss_score >= 9 ? 'text-red-400' : r.cvss_score != null && r.cvss_score >= 7 ? 'text-orange-400' : 'text-muted-foreground')}>
                      {r.cvss_score != null ? r.cvss_score.toFixed(1) : '—'}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={clsx('font-mono', epssColor(r.epss_score))}>
                      {r.epss_score > 0 ? `${(r.epss_score * 100).toFixed(1)}%` : '—'}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    {r.is_kev && <KevBadge />}
                  </td>
                  <td className="px-3 py-2.5 max-w-[100px]">
                    {r.threat_actor ? (
                      <span className="text-orange-400 truncate block">{r.threat_actor}</span>
                    ) : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="px-3 py-2.5 max-w-[100px]">
                    {r.mitre_technique ? (
                      <span className="text-blue-400 font-mono truncate block">{r.mitre_technique}</span>
                    ) : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="px-3 py-2.5"><ConfBadge conf={r.confidence} /></td>
                  <td className="px-3 py-2.5 text-muted-foreground">{fmt(r.published_at)}</td>
                  <td className="px-3 py-2.5">
                    <ChevronRight size={14} className="text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Page {page} of {pages} · {total.toLocaleString()} total
          </span>
          <div className="flex items-center gap-1">
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
              className="px-3 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-md hover:bg-white/8 disabled:opacity-40 transition-colors"
            >Previous</button>
            <button
              disabled={page >= pages}
              onClick={() => setPage(p => p + 1)}
              className="px-3 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-md hover:bg-white/8 disabled:opacity-40 transition-colors"
            >Next</button>
          </div>
        </div>
      )}
    </div>
  );
});

// ─── IOCs Tab ─────────────────────────────────────────────────────────────────

const IOCsTab = memo(() => {
  const [iocType, setIocType] = useState('');
  const [page, setPage] = useState(1);

  const params = useMemo(() => {
    const p: Record<string, any> = { page, page_size: 50 };
    if (iocType) p.ioc_type = iocType;
    return p;
  }, [page, iocType]);

  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();
  const { data, loading, error } = useApi<IOCPage>(`/intelligence/iocs?${qs}`);

  const iocs = data?.data ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  const IOC_TYPES = ['ip', 'domain', 'url', 'hash', 'email', 'filename', 'registry', 'process', 'mutex', 'certificate'];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1 p-1 bg-surface-2 rounded-lg border border-white/5 overflow-x-auto">
          <button
            onClick={() => { setIocType(''); setPage(1); }}
            className={clsx('px-2.5 py-1 text-[10px] font-medium rounded-md transition-all whitespace-nowrap', !iocType ? 'bg-surface-1 text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}
          >
            All Types
          </button>
          {IOC_TYPES.map(t => {
            const Icon = IOC_ICON[t] ?? Target;
            return (
              <button
                key={t}
                onClick={() => { setIocType(t); setPage(1); }}
                className={clsx('flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-md transition-all whitespace-nowrap capitalize', iocType === t ? 'bg-surface-1 text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}
              >
                <Icon size={9} />{t}
              </button>
            );
          })}
        </div>
        <span className="text-xs text-muted-foreground ml-auto">{total.toLocaleString()} indicators</span>
      </div>

      {loading && iocs.length === 0 ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-12 bg-surface-2 rounded-lg animate-pulse" />)}</div>
      ) : error ? (
        <EmptyState title="Failed to load IOCs" subtitle={error} icon={AlertCircle} />
      ) : iocs.length === 0 ? (
        <EmptyState
          title="No indicators of compromise"
          subtitle="IOCs will appear here once intelligence providers are connected and synchronized."
          icon={Target}
        />
      ) : (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-surface-1/30">
                {['Type', 'Value', 'Confidence', 'First Seen', 'Last Seen', 'Source', 'Internal'].map(h => (
                  <th key={h} className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {iocs.map(ioc => {
                const Icon = IOC_ICON[ioc.type.toLowerCase()] ?? Target;
                return (
                  <tr key={ioc.id} className="border-b border-white/4 hover:bg-white/3 transition-colors">
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <Icon size={12} className="text-blue-400 shrink-0" />
                        <span className="uppercase text-[10px] font-medium text-muted-foreground">{ioc.type}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 max-w-xs">
                      <span className="font-mono text-foreground/80 truncate block">{ioc.value}</span>
                    </td>
                    <td className="px-3 py-2.5"><ConfBadge conf={ioc.confidence} /></td>
                    <td className="px-3 py-2.5 text-muted-foreground">{fmt(ioc.first_seen)}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{fmt(ioc.last_seen)}</td>
                    <td className="px-3 py-2.5">
                      <span className="text-[10px] bg-green-500/10 text-green-400 border border-green-500/20 px-1.5 py-0.5 rounded">
                        {Array.isArray(ioc.source) ? ioc.source.join(', ') : ioc.source}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      {ioc.observed_internally ? (
                        <span className="flex items-center gap-1 text-red-400"><AlertTriangle size={10} />Yes</span>
                      ) : (
                        <span className="text-muted-foreground">No</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <div className="flex justify-end gap-1">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-md hover:bg-white/8 disabled:opacity-40">Previous</button>
          <button disabled={page >= pages} onClick={() => setPage(p => p + 1)} className="px-3 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-md hover:bg-white/8 disabled:opacity-40">Next</button>
        </div>
      )}
    </div>
  );
});

// ─── Threat Actors Tab ────────────────────────────────────────────────────────

const ThreatActorsTab = memo(() => {
  const { data: actors, loading, error } = useApi<ThreatActor[]>('/intelligence/threat-actors');
  const [expanded, setExpanded] = useState<string | null>(null);

  if (loading) return <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 bg-surface-2 rounded-lg animate-pulse" />)}</div>;
  if (error) return <EmptyState title="Failed to load threat actors" subtitle={error} icon={AlertCircle} />;
  if (!actors || actors.length === 0) {
    return <EmptyState title="No threat actor profiles" subtitle="Threat actor intelligence will appear here once providers are connected and synced." icon={Users} />;
  }

  return (
    <div className="space-y-2">
      {actors.map(actor => (
        <div key={actor.name} className="bg-surface-2 border border-white/5 rounded-xl overflow-hidden">
          <button
            onClick={() => setExpanded(expanded === actor.name ? null : actor.name)}
            className="w-full flex items-center gap-3 p-4 hover:bg-white/3 transition-colors text-left"
          >
            <div className="w-8 h-8 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center shrink-0">
              <Users size={14} className="text-orange-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-foreground">{actor.name}</p>
              <div className="flex items-center gap-2 mt-0.5">
                {actor.country && <span className="text-[10px] text-muted-foreground">{actor.country}</span>}
                {actor.motivation && <span className="text-[10px] text-purple-400">{actor.motivation}</span>}
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <div className="text-right">
                <p className="text-xs font-mono text-foreground">{actor.associated_cves.length}</p>
                <p className="text-[9px] text-muted-foreground">CVEs</p>
              </div>
              <div className="text-right">
                <p className="text-xs font-mono text-foreground">{actor.known_campaigns.length}</p>
                <p className="text-[9px] text-muted-foreground">Campaigns</p>
              </div>
              {expanded === actor.name ? <ChevronUp size={14} className="text-muted-foreground" /> : <ChevronRight size={14} className="text-muted-foreground" />}
            </div>
          </button>

          {expanded === actor.name && (
            <div className="border-t border-white/8 p-4 grid grid-cols-2 md:grid-cols-3 gap-4">
              {actor.known_campaigns.length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground font-semibold uppercase mb-1">Campaigns</p>
                  {actor.known_campaigns.map(c => <p key={c} className="text-xs text-foreground/80">{c}</p>)}
                </div>
              )}
              {actor.known_malware.length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground font-semibold uppercase mb-1">Malware</p>
                  {actor.known_malware.map(m => <p key={m} className="text-xs text-red-400">{m}</p>)}
                </div>
              )}
              {actor.mitre_techniques.length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground font-semibold uppercase mb-1">MITRE</p>
                  {actor.mitre_techniques.map(t => <p key={t} className="text-xs text-blue-400 font-mono">{t}</p>)}
                </div>
              )}
              {actor.target_industries.length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground font-semibold uppercase mb-1">Target Industries</p>
                  <div className="flex flex-wrap gap-1">
                    {actor.target_industries.map(i => <span key={i} className="text-[10px] bg-surface-1 border border-white/8 px-1.5 py-0.5 rounded text-foreground/70">{i}</span>)}
                  </div>
                </div>
              )}
              {actor.associated_cves.length > 0 && (
                <div>
                  <p className="text-[10px] text-muted-foreground font-semibold uppercase mb-1">Associated CVEs</p>
                  <div className="flex flex-wrap gap-1">
                    {actor.associated_cves.slice(0, 5).map(c => <span key={c} className="text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 px-1.5 py-0.5 rounded font-mono">{c}</span>)}
                    {actor.associated_cves.length > 5 && <span className="text-[10px] text-muted-foreground">+{actor.associated_cves.length - 5} more</span>}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
});

// ─── Malware Tab ──────────────────────────────────────────────────────────────

const MalwareTab = memo(() => {
  const { data: families, loading, error } = useApi<MalwareFamily[]>('/intelligence/malware');

  if (loading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-32 bg-surface-2 rounded-xl animate-pulse" />)}</div>;
  if (error) return <EmptyState title="Failed to load malware families" subtitle={error} icon={AlertCircle} />;
  if (!families || families.length === 0) {
    return <EmptyState title="No malware family data" subtitle="Malware intelligence will appear here once providers are connected and synced." icon={Bug} />;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {families.map(f => (
        <div key={f.family} className="bg-surface-2 border border-white/5 rounded-xl p-4 hover:border-white/10 transition-colors">
          <div className="flex items-start justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                <Bug size={13} className="text-red-400" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">{f.family}</p>
                {f.category && <p className="text-[10px] text-muted-foreground capitalize">{f.category}</p>}
              </div>
            </div>
            <SevBadge sev={f.severity} />
          </div>
          <div className="space-y-1.5 text-xs">
            {f.associated_threat_actor && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Threat Actor</span>
                <span className="text-orange-400">{f.associated_threat_actor}</span>
              </div>
            )}
            {f.delivery_method && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Delivery</span>
                <span className="text-foreground/70">{f.delivery_method}</span>
              </div>
            )}
            {f.persistence && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Persistence</span>
                <span className="text-foreground/70">{f.persistence}</span>
              </div>
            )}
            {f.mitre_mapping && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">MITRE</span>
                <span className="text-blue-400 font-mono">{f.mitre_mapping}</span>
              </div>
            )}
            {f.related_cves.length > 0 && (
              <div className="pt-1.5 border-t border-white/5">
                <p className="text-[10px] text-muted-foreground mb-1">Related CVEs</p>
                <div className="flex flex-wrap gap-1">
                  {f.related_cves.slice(0, 4).map(c => (
                    <span key={c} className="text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 px-1 py-0.5 rounded font-mono">{c}</span>
                  ))}
                  {f.related_cves.length > 4 && <span className="text-[10px] text-muted-foreground">+{f.related_cves.length - 4}</span>}
                </div>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
});

// ─── Techniques Tab ───────────────────────────────────────────────────────────

const TechniquesTab = memo(() => {
  const { data: techniques, loading, error } = useApi<AttackTechnique[]>('/intelligence/techniques');

  if (loading) return <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-12 bg-surface-2 rounded-lg animate-pulse" />)}</div>;
  if (error) return <EmptyState title="Failed to load techniques" subtitle={error} icon={AlertCircle} />;
  if (!techniques || techniques.length === 0) {
    return <EmptyState title="No MITRE ATT&CK data" subtitle="Attack technique mappings will appear here as intelligence is ingested from connected providers." icon={Crosshair} />;
  }

  const grouped = useMemo(() => {
    const g: Record<string, AttackTechnique[]> = {};
    for (const t of techniques) {
      const tactic = t.tactic || 'Unknown';
      if (!g[tactic]) g[tactic] = [];
      g[tactic].push(t);
    }
    return g;
  }, [techniques]);

  return (
    <div className="space-y-4">
      <div className="text-xs text-muted-foreground">
        {techniques.length} techniques across {Object.keys(grouped).length} tactics
      </div>
      {Object.entries(grouped).map(([tactic, techs]) => (
        <div key={tactic} className="bg-surface-2 border border-white/5 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-white/8 bg-surface-1/30">
            <Layers size={13} className="text-blue-400" />
            <span className="text-xs font-semibold text-foreground">{tactic}</span>
            <span className="text-[10px] text-muted-foreground ml-auto">{techs.length} techniques</span>
          </div>
          <div className="divide-y divide-white/4">
            {techs.map(t => (
              <div key={t.technique} className="flex items-center gap-4 px-4 py-3 hover:bg-white/3 transition-colors">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-blue-400 font-semibold">{t.technique}</span>
                    {t.sub_technique && <span className="text-[10px] text-muted-foreground font-mono">{t.sub_technique}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-4 shrink-0 text-right">
                  <div>
                    <p className="text-xs font-mono text-foreground">{t.observed_events}</p>
                    <p className="text-[9px] text-muted-foreground">events</p>
                  </div>
                  <div>
                    <p className="text-xs font-mono text-foreground">{t.related_intel_ids.length}</p>
                    <p className="text-[9px] text-muted-foreground">intel records</p>
                  </div>
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded capitalize border',
                    t.coverage === 'full' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                    t.coverage === 'partial' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                    'bg-slate-500/10 text-slate-400 border-slate-500/20'
                  )}>
                    {t.coverage}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
});

// ─── Main Component ───────────────────────────────────────────────────────────

const IntelligenceSection = () => {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [selectedRecord, setSelectedRecord] = useState<IntelligenceRecord | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [summaryTick, setSummaryTick] = useState(0);
  const [feedsTick, setFeedsTick] = useState(0);

  const { data: summary, loading: summaryLoading, refetch: refetchSummary } =
    useApi<IntelligenceSummary>('/intelligence/summary', [summaryTick]);
  const { data: feeds, loading: feedsLoading, refetch: refetchFeeds } =
    useApi<IntelligenceFeed[]>('/intelligence/feeds', [feedsTick]);

  const feedsList = feeds ?? [];

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      refetchSummary();
      refetchFeeds();
    }, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [refetchSummary, refetchFeeds]);

  const handleSync = useCallback(async (providerId: string) => {
    setSyncing(providerId);
    try {
      await apiClient.post(`/intelligence/feeds/${providerId}/sync`, {});
      await new Promise(r => setTimeout(r, 1000));
      refetchFeeds();
      refetchSummary();
    } catch (e) {
      console.error('Sync failed', e);
    } finally {
      setSyncing(null);
    }
  }, [refetchFeeds, refetchSummary]);

  const handleRefresh = useCallback(() => {
    refetchSummary();
    refetchFeeds();
  }, [refetchSummary, refetchFeeds]);

  return (
    <div className="relative flex flex-col h-full">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Shield size={16} className="text-blue-400" />
            Threat Intelligence Platform
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Aggregated intelligence from {feedsList.length} configured providers
            {summary?.last_feed_update && <> · Updated {fmtTime(summary.last_feed_update)}</>}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 hover:bg-white/10 border border-white/10 text-foreground rounded-lg transition-colors"
          >
            <RefreshCw size={12} className={(summaryLoading || feedsLoading) ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 p-1 bg-surface-2 rounded-xl border border-white/5 w-fit mb-5 overflow-x-auto shrink-0">
        {TABS.map(t => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-lg transition-all whitespace-nowrap',
                activeTab === t.id
                  ? 'bg-surface-1 text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
              )}
            >
              <Icon size={11} />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="flex-1 min-h-0">
        {activeTab === 'overview' && (
          <OverviewTab
            summary={summary}
            feeds={feedsList}
            onRefresh={handleRefresh}
            refreshing={summaryLoading || feedsLoading}
          />
        )}
        {activeTab === 'feeds' && (
          <FeedsTab feeds={feedsList} onSync={handleSync} syncing={syncing} />
        )}
        {activeTab === 'records' && (
          <RecordsTab onSelectRecord={setSelectedRecord} />
        )}
        {activeTab === 'iocs' && <IOCsTab />}
        {activeTab === 'actors' && <ThreatActorsTab />}
        {activeTab === 'malware' && <MalwareTab />}
        {activeTab === 'techniques' && <TechniquesTab />}
      </div>

      {/* Detail Drawer */}
      {selectedRecord && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            onClick={() => setSelectedRecord(null)}
          />
          <DetailDrawer record={selectedRecord} onClose={() => setSelectedRecord(null)} />
        </>
      )}
    </div>
  );
};

export default IntelligenceSection;
