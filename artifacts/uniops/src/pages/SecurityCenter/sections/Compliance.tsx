import {
  useState, useEffect, useCallback, useRef, useMemo, memo,
} from 'react';
import {
  CheckSquare, RefreshCw, AlertTriangle, CheckCircle, X,
  ChevronRight, ChevronDown, ChevronUp, Shield, Search, Filter,
  Download, ExternalLink, FileText, Clock, Settings, Info,
  BarChart3, Database, Server, GitBranch, Layers, Package,
  AlertCircle, Eye, Users, ClipboardList, History, ShieldOff,
  ShieldCheck, Crosshair, FileCheck, Building, Globe, Zap,
  TrendingDown, TrendingUp, TriangleAlert, ArrowUpRight,
  BookOpen, Loader2, Play,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ComplianceSummary {
  overall_score: number;
  enabled_frameworks: number;
  compliant_frameworks: number;
  non_compliant_frameworks: number;
  total_controls: number;
  passing_controls: number;
  failing_controls: number;
  missing_evidence: number;
  critical_findings: number;
  open_vulnerabilities: number;
  open_threats: number;
  total_assets: number;
  non_compliant_assets: number;
  last_assessment: string | null;
  open_remediations: number;
}

interface Framework {
  id: string;
  framework: string;
  version: string | null;
  score: number;
  passed: number;
  failed: number;
  not_applicable: number;
  total: number;
  status: string;
  last_assessment: string | null;
  mapped_policies: any[];
  controls_count: number;
}

interface Control {
  id: string;
  control_id: string;
  title: string;
  framework: string;
  category: string;
  severity: string;
  status: string;
  evidence_count: number;
  has_evidence: boolean;
  owner: string | null;
  last_evaluated: string | null;
  next_evaluation: string | null;
  description: string | null;
  mapped_policies: any[];
  mapped_assets: any[];
  mapped_repos: any[];
  mapped_k8s: any[];
  related_findings: any[];
  related_threats?: any[];
  related_vulnerabilities?: any[];
  exceptions: any[];
  score?: number;
}

interface ControlPage {
  data: Control[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface Resource {
  id: string;
  resource: string;
  resource_type: string;
  reason: string;
  severity: string;
  source: string;
  namespace: string | null;
  related_controls: string[];
  suggested_remediation: string;
  detected_at: string | null;
  status: string;
}

interface Assessment {
  id: string;
  assessment_date: string | null;
  framework: string;
  score: number;
  passed: number;
  failed: number;
  evidence_count: number;
  duration_seconds: number | null;
  status: string;
}

interface ComplianceException {
  id: string;
  title: string;
  reason: string | null;
  expiration: string | null;
  owner: string | null;
  approved_by: string | null;
  status: string;
  exception_type: string | null;
  finding_type: string | null;
  framework: string | null;
  control_id: string | null;
  created_at: string | null;
}

interface EvidenceItem {
  id: string;
  control_id: string | null;
  framework: string;
  source: string;
  collection_time: string | null;
  collected_by: string;
  status: string;
  verification: string;
  evidence_type: string;
  description: string | null;
  download_url: string | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'overview',    label: 'Overview',       icon: BarChart3 },
  { id: 'frameworks',  label: 'Frameworks',      icon: BookOpen },
  { id: 'controls',   label: 'Controls',        icon: CheckSquare },
  { id: 'evidence',   label: 'Evidence',        icon: FileCheck },
  { id: 'resources',  label: 'Non-Compliant',   icon: ShieldOff },
  { id: 'assessments',label: 'Assessments',     icon: History },
  { id: 'exceptions', label: 'Exceptions',      icon: AlertCircle },
] as const;
type Tab = typeof TABS[number]['id'];

const STATUS_STYLE: Record<string, string> = {
  compliant:       'bg-green-500/15 text-green-400 border border-green-500/30',
  pass:            'bg-green-500/15 text-green-400 border border-green-500/30',
  passing:         'bg-green-500/15 text-green-400 border border-green-500/30',
  non_compliant:   'bg-red-500/15 text-red-400 border border-red-500/30',
  fail:            'bg-red-500/15 text-red-400 border border-red-500/30',
  failing:         'bg-red-500/15 text-red-400 border border-red-500/30',
  in_progress:     'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
  not_applicable:  'bg-slate-500/15 text-slate-400 border border-slate-500/20',
  na:              'bg-slate-500/15 text-slate-400 border border-slate-500/20',
  unknown:         'bg-slate-500/10 text-slate-500 border border-slate-500/15',
  pending:         'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
  approved:        'bg-green-500/15 text-green-400 border border-green-500/30',
  rejected:        'bg-red-500/15 text-red-400 border border-red-500/30',
  active:          'bg-blue-500/15 text-blue-400 border border-blue-500/30',
  expired:         'bg-slate-500/15 text-slate-400 border border-slate-500/20',
};

const SEV_STYLE: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border border-red-500/30',
  high:     'bg-orange-500/15 text-orange-400 border border-orange-500/30',
  medium:   'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
  low:      'bg-blue-500/15 text-blue-400 border border-blue-500/30',
  info:     'bg-slate-500/15 text-slate-400 border border-slate-500/20',
};

const FRAMEWORK_ICON: Record<string, string> = {
  'SOC 2':                  '🔐',
  'ISO 27001':              '📋',
  'NIST CSF':               '🛡️',
  'NIST 800-53':            '🏛️',
  'CIS Kubernetes':         '☸️',
  'CIS Docker':             '🐳',
  'PCI DSS':                '💳',
  'HIPAA':                  '🏥',
  'GDPR':                   '🇪🇺',
  'FedRAMP':                '🦅',
  'AWS Well-Architected':   '☁️',
  'Azure Security Benchmark':'🔷',
};

const RESOURCE_TYPE_ICON: Record<string, React.ElementType> = {
  repository: GitBranch,
  cluster:    Layers,
  namespace:  Package,
  pod:        Server,
  vm:         Server,
  cloud:      Globe,
  container:  Database,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

const StatusBadge = memo(({ status }: { status: string }) => (
  <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide', STATUS_STYLE[status] ?? STATUS_STYLE.unknown)}>
    {status.replace(/_/g, ' ')}
  </span>
));

const SevBadge = memo(({ sev }: { sev: string }) => (
  <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide', SEV_STYLE[sev] ?? 'bg-slate-500/10 text-slate-500 border border-slate-500/15')}>
    {sev}
  </span>
));

const ScoreBar = memo(({ score, size = 'md' }: { score: number; size?: 'sm' | 'md' | 'lg' }) => {
  const color = score >= 80 ? '#22c55e' : score >= 60 ? '#eab308' : '#ef4444';
  const h = size === 'sm' ? 'h-1' : size === 'lg' ? 'h-2.5' : 'h-1.5';
  return (
    <div className={clsx('w-full bg-white/5 rounded-full overflow-hidden', h)}>
      <div className={clsx('h-full rounded-full transition-all duration-500')}
        style={{ width: `${Math.min(100, score)}%`, background: color }} />
    </div>
  );
});

const ScoreCircle = memo(({ score }: { score: number }) => {
  const color = score >= 80 ? 'text-green-400' : score >= 60 ? 'text-yellow-400' : 'text-red-400';
  const stroke = score >= 80 ? '#22c55e' : score >= 60 ? '#eab308' : '#ef4444';
  const r = 28; const circ = 2 * Math.PI * r;
  const dash = circ * (score / 100);
  return (
    <div className="relative w-20 h-20 flex items-center justify-center">
      <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 72 72">
        <circle cx="36" cy="36" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
        <circle cx="36" cy="36" r={r} fill="none" stroke={stroke} strokeWidth="6"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" className="transition-all duration-700" />
      </svg>
      <span className={clsx('text-xl font-bold relative z-10', color)}>{Math.round(score)}</span>
    </div>
  );
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
function fmtDur(secs: number | null | undefined): string {
  if (secs == null) return '—';
  if (secs < 60) return `${Math.round(secs)}s`;
  return `${Math.round(secs / 60)}m`;
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

// ─── Stat Card ────────────────────────────────────────────────────────────────

const StatCard = memo(({ label, value, icon: Icon, color, sub, trend }: {
  label: string; value: string | number; icon: React.ElementType;
  color: string; sub?: string; trend?: 'up' | 'down' | 'neutral';
}) => (
  <div className="bg-surface-2 border border-white/5 rounded-xl p-4 flex items-start gap-3 hover:border-white/10 transition-colors">
    <div className={clsx('p-2 rounded-lg shrink-0', color)}>
      <Icon size={15} className="opacity-80" />
    </div>
    <div className="min-w-0 flex-1">
      <p className="text-[10px] text-muted-foreground truncate leading-tight">{label}</p>
      <p className="text-xl font-bold text-foreground leading-none mt-0.5">{value}</p>
      {sub && <p className="text-[10px] text-muted-foreground mt-0.5">{sub}</p>}
    </div>
    {trend === 'up' && <TrendingUp size={13} className="text-green-400 shrink-0 mt-1" />}
    {trend === 'down' && <TrendingDown size={13} className="text-red-400 shrink-0 mt-1" />}
  </div>
));

// ─── Control Detail Drawer ────────────────────────────────────────────────────

const ControlDrawer = memo(({ control, onClose }: { control: Control; onClose: () => void }) => {
  const { data: detail, loading } = useApi<Control>(
    `/compliance/controls/${encodeURIComponent(control.id)}?framework=${encodeURIComponent(control.framework)}`
  );
  const ctrl = detail ?? control;

  const SECTIONS = [
    { key: 'overview',      label: 'Overview' },
    { key: 'policies',      label: 'Mapped Policies' },
    { key: 'findings',      label: 'Related Findings' },
    { key: 'evidence',      label: 'Evidence' },
    { key: 'exceptions',    label: 'Exceptions' },
  ];
  const [section, setSection] = useState('overview');

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl flex flex-col bg-surface-1 border-l border-white/10 shadow-2xl">
      {/* Header */}
      <div className="flex items-start gap-3 p-5 border-b border-white/8 shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs text-blue-400 font-semibold">{ctrl.control_id}</span>
            <StatusBadge status={ctrl.status} />
            <SevBadge sev={ctrl.severity} />
            {ctrl.has_evidence && (
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-green-500/10 text-green-400 border border-green-500/20">Evidence</span>
            )}
          </div>
          <h2 className="text-sm font-semibold text-foreground mt-1.5 leading-snug">{ctrl.title}</h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">{ctrl.framework} · {ctrl.category}</p>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-md hover:bg-white/8 text-muted-foreground hover:text-foreground transition-colors shrink-0">
          <X size={16} />
        </button>
      </div>

      {/* Sub-nav */}
      <div className="flex items-center gap-0.5 px-5 py-2 border-b border-white/5 overflow-x-auto shrink-0">
        {SECTIONS.map(s => (
          <button key={s.key} onClick={() => setSection(s.key)}
            className={clsx('px-3 py-1.5 text-[11px] font-medium rounded-md transition-all whitespace-nowrap',
              section === s.key ? 'bg-surface-2 text-foreground' : 'text-muted-foreground hover:text-foreground')}
          >{s.label}</button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {loading && <div className="h-32 bg-surface-2 rounded-xl animate-pulse" />}

        {section === 'overview' && (
          <>
            {ctrl.description && (
              <div>
                <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Description</h3>
                <p className="text-xs text-foreground/80 leading-relaxed">{ctrl.description}</p>
              </div>
            )}
            <div>
              <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Details</h3>
              <div className="space-y-0 divide-y divide-white/5">
                {[
                  { label: 'Framework', value: ctrl.framework },
                  { label: 'Category', value: ctrl.category },
                  { label: 'Owner', value: ctrl.owner || '—' },
                  { label: 'Last Evaluated', value: fmtTime(ctrl.last_evaluated) },
                  { label: 'Next Evaluation', value: fmtTime(ctrl.next_evaluation) },
                  { label: 'Evidence Count', value: ctrl.evidence_count },
                ].map(row => (
                  <div key={row.label} className="flex items-center justify-between py-2">
                    <span className="text-xs text-muted-foreground">{row.label}</span>
                    <span className="text-xs text-foreground">{String(row.value)}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {section === 'policies' && (
          <div>
            <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">Mapped Policies</h3>
            {ctrl.mapped_policies.length === 0 ? (
              <p className="text-xs text-muted-foreground">No policies mapped to this control.</p>
            ) : ctrl.mapped_policies.map((p: any, i: number) => (
              <div key={p.id ?? i} className="flex items-center justify-between p-3 bg-surface-2 rounded-lg mb-2 border border-white/5">
                <div>
                  <p className="text-xs font-medium text-foreground">{p.name}</p>
                  <p className="text-[10px] text-muted-foreground">{p.category}</p>
                </div>
                <div className="flex items-center gap-2">
                  <SevBadge sev={p.severity} />
                  <StatusBadge status={p.status} />
                </div>
              </div>
            ))}
          </div>
        )}

        {section === 'findings' && (
          <div className="space-y-4">
            {ctrl.related_threats && ctrl.related_threats.length > 0 && (
              <div>
                <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Related Threats</h3>
                {ctrl.related_threats.map((t: any) => (
                  <div key={t.id} className="flex items-center justify-between p-3 bg-surface-2 rounded-lg mb-2 border border-white/5">
                    <p className="text-xs text-foreground truncate flex-1">{t.title}</p>
                    <SevBadge sev={t.severity} />
                  </div>
                ))}
              </div>
            )}
            {ctrl.related_vulnerabilities && ctrl.related_vulnerabilities.length > 0 && (
              <div>
                <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Related Vulnerabilities</h3>
                {ctrl.related_vulnerabilities.map((v: any) => (
                  <div key={v.id} className="flex items-center justify-between p-3 bg-surface-2 rounded-lg mb-2 border border-white/5">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-foreground truncate">{v.title}</p>
                      {v.cve_id && <p className="text-[10px] font-mono text-blue-400">{v.cve_id}</p>}
                    </div>
                    <div className="flex items-center gap-2">
                      {v.cvss_score != null && <span className="text-[10px] font-mono text-orange-400">{v.cvss_score?.toFixed(1)}</span>}
                      <SevBadge sev={v.severity} />
                    </div>
                  </div>
                ))}
              </div>
            )}
            {(!ctrl.related_threats?.length && !ctrl.related_vulnerabilities?.length) && (
              <p className="text-xs text-muted-foreground">No related findings.</p>
            )}
          </div>
        )}

        {section === 'evidence' && (
          <div>
            <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">Evidence</h3>
            {ctrl.evidence_count === 0 ? (
              <p className="text-xs text-muted-foreground">No evidence collected for this control.</p>
            ) : (
              <p className="text-xs text-muted-foreground">{ctrl.evidence_count} evidence items. View in Evidence tab.</p>
            )}
          </div>
        )}

        {section === 'exceptions' && (
          <div>
            <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">Exceptions</h3>
            {ctrl.exceptions.length === 0 ? (
              <p className="text-xs text-muted-foreground">No exceptions for this control.</p>
            ) : ctrl.exceptions.map((e: any, i: number) => (
              <div key={i} className="p-3 bg-surface-2 rounded-lg mb-2 border border-white/5">
                <p className="text-xs text-foreground">{e.title || e.reason || 'Exception'}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-white/8 flex items-center gap-2 shrink-0">
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 border border-white/10 hover:bg-white/10 text-foreground rounded-md transition-colors">
          <Download size={12} /> Export
        </button>
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 border border-white/10 hover:bg-white/10 text-foreground rounded-md transition-colors">
          <FileText size={12} /> Audit Log
        </button>
      </div>
    </div>
  );
});

// ─── Overview Tab ─────────────────────────────────────────────────────────────

const OverviewTab = memo(({ summary, frameworks, onSetTab }: {
  summary: ComplianceSummary | null;
  frameworks: Framework[];
  onSetTab: (tab: Tab) => void;
}) => {
  const noFrameworks = !summary || summary.enabled_frameworks === 0;

  if (noFrameworks) {
    return (
      <EmptyState
        title="No compliance frameworks configured."
        subtitle="Enable frameworks like SOC 2, ISO 27001, or CIS Kubernetes to start evaluating your compliance posture."
        icon={CheckSquare}
        action={
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors">
            <Settings size={14} /> Configure Frameworks
          </button>
        }
      />
    );
  }

  const s = summary!;
  const cards = [
    { label: 'Overall Score',           value: `${s.overall_score}%`,              icon: ShieldCheck,   color: s.overall_score >= 80 ? 'bg-green-500/10 text-green-400' : s.overall_score >= 60 ? 'bg-yellow-500/10 text-yellow-400' : 'bg-red-500/10 text-red-400' },
    { label: 'Enabled Frameworks',      value: s.enabled_frameworks,                icon: BookOpen,      color: 'bg-blue-500/10 text-blue-400' },
    { label: 'Passing Controls',        value: s.passing_controls,                  icon: CheckCircle,   color: 'bg-green-500/10 text-green-400' },
    { label: 'Failing Controls',        value: s.failing_controls,                  icon: AlertTriangle, color: 'bg-red-500/10 text-red-400' },
    { label: 'Missing Evidence',        value: s.missing_evidence,                  icon: FileCheck,     color: 'bg-yellow-500/10 text-yellow-400' },
    { label: 'Critical Findings',       value: s.critical_findings,                 icon: Crosshair,     color: 'bg-red-500/10 text-red-400' },
    { label: 'Open Vulnerabilities',    value: s.open_vulnerabilities,              icon: Zap,           color: 'bg-orange-500/10 text-orange-400' },
    { label: 'Open Threats',            value: s.open_threats,                      icon: AlertCircle,   color: 'bg-orange-500/10 text-orange-400' },
    { label: 'Non-Compliant Frameworks',value: s.non_compliant_frameworks,           icon: ShieldOff,     color: 'bg-red-500/10 text-red-400' },
    { label: 'Total Assets',            value: s.total_assets,                      icon: Server,        color: 'bg-slate-500/10 text-slate-400' },
    { label: 'Open Remediations',       value: s.open_remediations,                 icon: ClipboardList, color: 'bg-purple-500/10 text-purple-400' },
    { label: 'Last Assessment',         value: s.last_assessment ? fmt(s.last_assessment) : 'Never', icon: Clock, color: 'bg-slate-500/10 text-slate-400', sub: s.last_assessment ? fmtTime(s.last_assessment) : undefined },
  ] as any[];

  return (
    <div className="space-y-6">
      {/* Score + KPIs */}
      <div className="flex items-start gap-5">
        <div className="bg-surface-2 border border-white/5 rounded-xl p-6 flex items-center gap-5 shrink-0">
          <ScoreCircle score={s.overall_score} />
          <div>
            <p className="text-xs text-muted-foreground">Overall Compliance</p>
            <p className={clsx('text-lg font-bold mt-0.5', s.overall_score >= 80 ? 'text-green-400' : s.overall_score >= 60 ? 'text-yellow-400' : 'text-red-400')}>
              {s.overall_score >= 80 ? 'Compliant' : s.overall_score >= 60 ? 'At Risk' : 'Non-Compliant'}
            </p>
            <p className="text-[10px] text-muted-foreground mt-1">Across {s.enabled_frameworks} frameworks</p>
          </div>
        </div>
        <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {cards.slice(1, 9).map(c => <StatCard key={c.label} {...c} />)}
        </div>
      </div>

      {/* Framework Quick View */}
      {frameworks.length > 0 && (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/8">
            <h3 className="text-xs font-semibold text-foreground">Framework Status</h3>
            <button onClick={() => onSetTab('frameworks')} className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors">
              View All <ChevronRight size={10} />
            </button>
          </div>
          <div className="divide-y divide-white/4">
            {frameworks.slice(0, 6).map(fw => (
              <div key={fw.id} className="flex items-center gap-4 px-4 py-3 hover:bg-white/3 transition-colors">
                <span className="text-lg shrink-0">{FRAMEWORK_ICON[fw.framework] || '📋'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-xs font-medium text-foreground truncate">{fw.framework}</p>
                    {fw.version && <span className="text-[9px] text-muted-foreground">v{fw.version}</span>}
                  </div>
                  <ScoreBar score={fw.score} size="sm" />
                </div>
                <div className="text-right shrink-0">
                  <p className={clsx('text-sm font-bold', fw.score >= 80 ? 'text-green-400' : fw.score >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                    {fw.score}%
                  </p>
                  <p className="text-[9px] text-muted-foreground">{fw.passed}P / {fw.failed}F</p>
                </div>
                <StatusBadge status={fw.status} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

// ─── Frameworks Tab ───────────────────────────────────────────────────────────

const FrameworksTab = memo(({ frameworks, loading }: { frameworks: Framework[]; loading: boolean }) => {
  if (loading) return <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 bg-surface-2 rounded-xl animate-pulse" />)}</div>;
  if (frameworks.length === 0) {
    return <EmptyState title="No compliance frameworks configured." subtitle="Configure frameworks to start evaluating compliance posture." icon={BookOpen} action={
      <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"><Settings size={14} /> Configure</button>
    } />;
  }

  return (
    <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-white/8 bg-surface-1/30">
            {['Framework', 'Version', 'Status', 'Compliance %', 'Passing', 'Failed', 'N/A', 'Controls', 'Last Assessment', 'Policies'].map(h => (
              <th key={h} className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-4 py-3">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {frameworks.map(fw => (
            <tr key={fw.id} className="border-b border-white/4 hover:bg-white/3 transition-colors">
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-base">{FRAMEWORK_ICON[fw.framework] || '📋'}</span>
                  <span className="font-semibold text-foreground">{fw.framework}</span>
                </div>
              </td>
              <td className="px-4 py-3 text-muted-foreground">{fw.version || '—'}</td>
              <td className="px-4 py-3"><StatusBadge status={fw.status} /></td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-16">
                    <ScoreBar score={fw.score} size="sm" />
                  </div>
                  <span className={clsx('font-bold text-xs', fw.score >= 80 ? 'text-green-400' : fw.score >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                    {fw.score}%
                  </span>
                </div>
              </td>
              <td className="px-4 py-3 text-green-400 font-mono">{fw.passed}</td>
              <td className="px-4 py-3 text-red-400 font-mono">{fw.failed}</td>
              <td className="px-4 py-3 text-muted-foreground font-mono">{fw.not_applicable}</td>
              <td className="px-4 py-3 text-muted-foreground font-mono">{fw.controls_count}</td>
              <td className="px-4 py-3 text-muted-foreground">{fmt(fw.last_assessment)}</td>
              <td className="px-4 py-3 text-muted-foreground font-mono">{fw.mapped_policies.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});

// ─── Controls Tab ─────────────────────────────────────────────────────────────

const ControlsTab = memo(({ frameworks, onSelectControl }: {
  frameworks: Framework[];
  onSelectControl: (c: Control) => void;
}) => {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [framework, setFramework] = useState('');
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [evidence, setEvidence] = useState('');
  const [page, setPage] = useState(1);
  const [sortCol, setSortCol] = useState('severity');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  const qs = useMemo(() => {
    const p: Record<string, string> = { page: String(page), page_size: '50' };
    if (framework) p.framework = framework;
    if (severity)  p.severity  = severity;
    if (status)    p.status    = status;
    if (evidence)  p.evidence  = evidence;
    if (debouncedSearch) p.search = debouncedSearch;
    return new URLSearchParams(p).toString();
  }, [page, framework, severity, status, evidence, debouncedSearch]);

  const { data, loading, error, refetch } = useApi<ControlPage>(`/compliance/controls?${qs}`);
  const controls = data?.data ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  const sorted = useMemo(() => {
    const arr = [...controls];
    arr.sort((a, b) => {
      const av = (a as any)[sortCol] ?? '';
      const bv = (b as any)[sortCol] ?? '';
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'asc' ? av - bv : bv - av;
      return sortDir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return arr;
  }, [controls, sortCol, sortDir]);

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortDir('desc'); }
  };

  const SortIcon = ({ col }: { col: string }) => sortCol === col
    ? (sortDir === 'desc' ? <ChevronDown size={10} /> : <ChevronUp size={10} />)
    : null;

  const SEVS = ['critical', 'high', 'medium', 'low', 'info'];
  const STATUSES = ['compliant', 'non_compliant', 'in_progress', 'not_applicable'];

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap sticky top-0 z-10 bg-surface-1/95 backdrop-blur-sm py-2">
        <div className="relative flex-1 min-w-44">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search controls…"
            className="w-full bg-surface-2 border border-white/10 rounded-lg pl-8 pr-8 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/50 transition-colors" />
          {search && <button onClick={() => { setSearch(''); setPage(1); }} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"><X size={11} /></button>}
        </div>
        <select value={framework} onChange={e => { setFramework(e.target.value); setPage(1); }}
          className="bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:border-blue-500/50">
          <option value="">All Frameworks</option>
          {frameworks.map(f => <option key={f.id} value={f.framework}>{f.framework}</option>)}
        </select>
        <select value={severity} onChange={e => { setSeverity(e.target.value); setPage(1); }}
          className="bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:border-blue-500/50">
          <option value="">All Severities</option>
          {SEVS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
        </select>
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
          className="bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:border-blue-500/50">
          <option value="">All Statuses</option>
          {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
        </select>
        <button onClick={() => { setEvidence(evidence === 'missing' ? '' : 'missing'); setPage(1); }}
          className={clsx('px-3 py-2 text-xs font-medium rounded-lg border transition-colors', evidence === 'missing' ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40' : 'bg-surface-2 text-muted-foreground border-white/10 hover:text-foreground')}>
          Missing Evidence
        </button>
        <button onClick={() => refetch()} className="p-2 rounded-lg bg-surface-2 border border-white/10 text-muted-foreground hover:text-foreground">
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
        </button>
        <span className="text-xs text-muted-foreground">{total.toLocaleString()} controls</span>
      </div>

      {/* Table */}
      {loading && controls.length === 0 ? (
        <div className="space-y-1.5">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="h-11 bg-surface-2 rounded-lg animate-pulse" />)}</div>
      ) : error ? (
        <EmptyState title="Failed to load controls" subtitle={error} icon={AlertCircle} />
      ) : controls.length === 0 ? (
        <EmptyState title="No controls found" subtitle="Adjust your filters or wait for a compliance assessment to run." icon={CheckSquare} />
      ) : (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-surface-1/30">
                {[
                  { key: 'control_id', label: 'Control ID' },
                  { key: 'title',      label: 'Title' },
                  { key: 'framework',  label: 'Framework' },
                  { key: 'category',   label: 'Category' },
                  { key: 'severity',   label: 'Severity' },
                  { key: 'status',     label: 'Status' },
                  { key: 'has_evidence', label: 'Evidence' },
                  { key: 'owner',      label: 'Owner' },
                  { key: 'last_evaluated', label: 'Evaluated' },
                  { key: '',           label: '' },
                ].map(col => (
                  <th key={col.key}
                    onClick={() => col.key && toggleSort(col.key)}
                    className={clsx('text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 py-3', col.key && 'cursor-pointer hover:text-foreground select-none')}
                  >
                    <span className="flex items-center gap-1">{col.label}<SortIcon col={col.key} /></span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map(ctrl => (
                <tr key={ctrl.id} onClick={() => onSelectControl(ctrl)}
                  className="border-b border-white/4 hover:bg-white/4 cursor-pointer transition-colors group">
                  <td className="px-3 py-2.5">
                    <span className="font-mono text-blue-400 font-semibold">{ctrl.control_id}</span>
                  </td>
                  <td className="px-3 py-2.5 max-w-xs">
                    <span className="text-foreground/90 group-hover:text-foreground truncate block">{ctrl.title}</span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-1">
                      <span>{FRAMEWORK_ICON[ctrl.framework] || '📋'}</span>
                      <span className="text-muted-foreground truncate max-w-[100px]">{ctrl.framework}</span>
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">{ctrl.category}</td>
                  <td className="px-3 py-2.5"><SevBadge sev={ctrl.severity} /></td>
                  <td className="px-3 py-2.5"><StatusBadge status={ctrl.status} /></td>
                  <td className="px-3 py-2.5">
                    {ctrl.has_evidence
                      ? <span className="flex items-center gap-1 text-green-400"><CheckCircle size={11} /> Yes</span>
                      : <span className="text-muted-foreground">—</span>
                    }
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">{ctrl.owner || '—'}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{fmt(ctrl.last_evaluated)}</td>
                  <td className="px-3 py-2.5">
                    <ChevronRight size={14} className="text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">Page {page} of {pages} · {total.toLocaleString()} total</span>
          <div className="flex items-center gap-1">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
              className="px-3 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-md hover:bg-white/8 disabled:opacity-40 transition-colors">Previous</button>
            <button disabled={page >= pages} onClick={() => setPage(p => p + 1)}
              className="px-3 py-1.5 text-xs bg-surface-2 border border-white/10 rounded-md hover:bg-white/8 disabled:opacity-40 transition-colors">Next</button>
          </div>
        </div>
      )}
    </div>
  );
});

// ─── Evidence Tab ─────────────────────────────────────────────────────────────

const EvidenceTab = memo(({ frameworks }: { frameworks: Framework[] }) => {
  const [fw, setFw] = useState('');
  const [page, setPage] = useState(1);
  const qs = useMemo(() => {
    const p: Record<string, string> = { page: String(page), page_size: '50' };
    if (fw) p.framework = fw;
    return new URLSearchParams(p).toString();
  }, [fw, page]);

  const { data, loading, error } = useApi<{ data: EvidenceItem[]; total: number; pages: number }>(`/compliance/evidence?${qs}`);
  const items = data?.data ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  const EV_TYPE_COLOR: Record<string, string> = {
    scan_result: 'text-blue-400',
    log:         'text-green-400',
    screenshot:  'text-purple-400',
    api_response:'text-orange-400',
    document:    'text-yellow-400',
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <select value={fw} onChange={e => { setFw(e.target.value); setPage(1); }}
          className="bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:border-blue-500/50">
          <option value="">All Frameworks</option>
          {frameworks.map(f => <option key={f.id} value={f.framework}>{f.framework}</option>)}
        </select>
        <span className="text-xs text-muted-foreground ml-auto">{total.toLocaleString()} items</span>
      </div>

      {loading && items.length === 0 ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 bg-surface-2 rounded-lg animate-pulse" />)}</div>
      ) : error ? (
        <EmptyState title="Failed to load evidence" subtitle={error} icon={AlertCircle} />
      ) : items.length === 0 ? (
        <EmptyState title="No evidence collected" subtitle="Evidence will appear here once compliance assessments run." icon={FileCheck} />
      ) : (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-surface-1/30">
                {['Framework', 'Control', 'Type', 'Source', 'Collected By', 'Collection Time', 'Status', 'Verification', ''].map(h => (
                  <th key={h} className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(ev => (
                <tr key={ev.id} className="border-b border-white/4 hover:bg-white/3 transition-colors">
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-1">
                      <span>{FRAMEWORK_ICON[ev.framework] || '📋'}</span>
                      <span className="text-muted-foreground">{ev.framework}</span>
                    </span>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-blue-400">{ev.control_id || '—'}</td>
                  <td className="px-3 py-2.5">
                    <span className={clsx('capitalize', EV_TYPE_COLOR[ev.evidence_type] ?? 'text-muted-foreground')}>
                      {ev.evidence_type.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">{ev.source}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{ev.collected_by}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{fmtTime(ev.collection_time)}</td>
                  <td className="px-3 py-2.5"><StatusBadge status={ev.status} /></td>
                  <td className="px-3 py-2.5 text-muted-foreground capitalize">{ev.verification}</td>
                  <td className="px-3 py-2.5">
                    {ev.download_url && (
                      <a href={ev.download_url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors">
                        <Download size={11} />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
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

// ─── Non-Compliant Resources Tab ──────────────────────────────────────────────

const ResourcesTab = memo(() => {
  const [resourceType, setResourceType] = useState('');
  const [page, setPage] = useState(1);
  const qs = useMemo(() => {
    const p: Record<string, string> = { page: String(page), page_size: '50' };
    if (resourceType) p.resource_type = resourceType;
    return new URLSearchParams(p).toString();
  }, [page, resourceType]);

  const { data, loading, error } = useApi<{ data: Resource[]; total: number; pages: number }>(`/compliance/resources?${qs}`);
  const resources = data?.data ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  const TYPES = ['repository', 'cluster', 'namespace', 'pod', 'vm', 'cloud', 'container'];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1 p-1 bg-surface-2 rounded-lg border border-white/5 overflow-x-auto">
          <button onClick={() => { setResourceType(''); setPage(1); }}
            className={clsx('px-2.5 py-1 text-[10px] font-medium rounded-md transition-all', !resourceType ? 'bg-surface-1 text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
            All Types
          </button>
          {TYPES.map(t => {
            const Icon = RESOURCE_TYPE_ICON[t] ?? Server;
            return (
              <button key={t} onClick={() => { setResourceType(t); setPage(1); }}
                className={clsx('flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-md capitalize transition-all whitespace-nowrap', resourceType === t ? 'bg-surface-1 text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
                <Icon size={9} />{t}
              </button>
            );
          })}
        </div>
        <span className="text-xs text-muted-foreground ml-auto">{total.toLocaleString()} resources</span>
      </div>

      {loading && resources.length === 0 ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 bg-surface-2 rounded-lg animate-pulse" />)}</div>
      ) : error ? (
        <EmptyState title="Failed to load resources" subtitle={error} icon={AlertCircle} />
      ) : resources.length === 0 ? (
        <EmptyState title="No non-compliant resources" subtitle="All resources are compliant, or no compliance data is available." icon={ShieldCheck} />
      ) : (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-surface-1/30">
                {['Type', 'Resource', 'Reason', 'Severity', 'Source', 'Detected', 'Suggested Fix'].map(h => (
                  <th key={h} className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {resources.map(r => {
                const Icon = RESOURCE_TYPE_ICON[r.resource_type] ?? Server;
                return (
                  <tr key={r.id} className="border-b border-white/4 hover:bg-white/3 transition-colors">
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5 capitalize">
                        <Icon size={12} className="text-muted-foreground" />
                        <span className="text-muted-foreground">{r.resource_type}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 max-w-xs">
                      <span className="font-mono text-foreground/80 truncate block">{r.resource}</span>
                      {r.namespace && <span className="text-[10px] text-muted-foreground">{r.namespace}</span>}
                    </td>
                    <td className="px-3 py-2.5 max-w-xs">
                      <span className="text-foreground/70 truncate block">{r.reason}</span>
                    </td>
                    <td className="px-3 py-2.5"><SevBadge sev={r.severity} /></td>
                    <td className="px-3 py-2.5 text-muted-foreground">{r.source}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{fmt(r.detected_at)}</td>
                    <td className="px-3 py-2.5 max-w-xs">
                      <span className="text-muted-foreground truncate block text-[10px]">{r.suggested_remediation}</span>
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

// ─── Assessments Tab ──────────────────────────────────────────────────────────

const AssessmentsTab = memo(() => {
  const [page, setPage] = useState(1);
  const qs = `page=${page}&page_size=20`;
  const { data, loading, error } = useApi<{ data: Assessment[]; total: number; pages: number }>(`/compliance/assessments?${qs}`);
  const assessments = data?.data ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{total.toLocaleString()} assessments</span>
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 border border-white/10 hover:bg-white/10 text-foreground rounded-lg transition-colors">
          <Download size={12} /> Export PDF
        </button>
      </div>

      {loading && assessments.length === 0 ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 bg-surface-2 rounded-lg animate-pulse" />)}</div>
      ) : error ? (
        <EmptyState title="Failed to load assessments" subtitle={error} icon={AlertCircle} />
      ) : assessments.length === 0 ? (
        <EmptyState title="No assessment history" subtitle="Assessments will appear here after compliance scans run." icon={History} />
      ) : (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-surface-1/30">
                {['Date', 'Framework', 'Score', 'Passed', 'Failed', 'Evidence', 'Duration', 'Status'].map(h => (
                  <th key={h} className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {assessments.map(a => (
                <tr key={a.id} className="border-b border-white/4 hover:bg-white/3 transition-colors">
                  <td className="px-3 py-2.5 text-muted-foreground">{fmtTime(a.assessment_date)}</td>
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-1">
                      <span>{FRAMEWORK_ICON[a.framework] || '📋'}</span>
                      <span className="text-foreground">{a.framework}</span>
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={clsx('font-bold', a.score >= 80 ? 'text-green-400' : a.score >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                      {a.score}%
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-green-400 font-mono">{a.passed}</td>
                  <td className="px-3 py-2.5 text-red-400 font-mono">{a.failed}</td>
                  <td className="px-3 py-2.5 text-muted-foreground font-mono">{a.evidence_count}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{fmtDur(a.duration_seconds)}</td>
                  <td className="px-3 py-2.5"><StatusBadge status={a.status} /></td>
                </tr>
              ))}
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

// ─── Exceptions Tab ───────────────────────────────────────────────────────────

const ExceptionsTab = memo(() => {
  const [page, setPage] = useState(1);
  const qs = `page=${page}&page_size=50`;
  const { data, loading, error } = useApi<{ data: ComplianceException[]; total: number; pages: number }>(`/compliance/exceptions?${qs}`);
  const exceptions = data?.data ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{total.toLocaleString()} exceptions</span>
      </div>

      {loading && exceptions.length === 0 ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-14 bg-surface-2 rounded-lg animate-pulse" />)}</div>
      ) : error ? (
        <EmptyState title="Failed to load exceptions" subtitle={error} icon={AlertCircle} />
      ) : exceptions.length === 0 ? (
        <EmptyState title="No compliance exceptions" subtitle="Approved exceptions and waivers will appear here." icon={AlertCircle} />
      ) : (
        <div className="bg-surface-2 border border-white/5 rounded-xl overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-surface-1/30">
                {['Exception', 'Type', 'Reason', 'Owner', 'Approved By', 'Expires', 'Status'].map(h => (
                  <th key={h} className="text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {exceptions.map(e => (
                <tr key={e.id} className="border-b border-white/4 hover:bg-white/3 transition-colors">
                  <td className="px-3 py-2.5 max-w-xs">
                    <span className="text-foreground font-medium truncate block">{e.title}</span>
                    {e.finding_type && <span className="text-[10px] text-muted-foreground capitalize">{e.finding_type}</span>}
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground capitalize">{e.exception_type?.replace(/_/g, ' ') || '—'}</td>
                  <td className="px-3 py-2.5 max-w-xs">
                    <span className="text-muted-foreground truncate block text-[10px]">{e.reason || '—'}</span>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-muted-foreground text-[10px]">{e.owner ? e.owner.slice(0, 8) + '…' : '—'}</td>
                  <td className="px-3 py-2.5 font-mono text-muted-foreground text-[10px]">{e.approved_by ? e.approved_by.slice(0, 8) + '…' : '—'}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{fmt(e.expiration)}</td>
                  <td className="px-3 py-2.5"><StatusBadge status={e.status} /></td>
                </tr>
              ))}
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

// ─── Main Component ───────────────────────────────────────────────────────────

export default function ComplianceSection() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [selectedControl, setSelectedControl] = useState<Control | null>(null);

  const { data: summary, loading: sumLoading, refetch: refetchSummary } =
    useApi<ComplianceSummary>('/compliance/summary');
  const { data: frameworksRaw, loading: fwLoading, refetch: refetchFw } =
    useApi<Framework[]>('/compliance/frameworks');

  const frameworks = frameworksRaw ?? [];

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const id = setInterval(() => { refetchSummary(); refetchFw(); }, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [refetchSummary, refetchFw]);

  const handleRefresh = useCallback(() => { refetchSummary(); refetchFw(); }, [refetchSummary, refetchFw]);

  return (
    <div className="relative flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <CheckSquare size={16} className="text-green-400" />
            Compliance Management Center
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {frameworks.length > 0
              ? `${frameworks.length} framework${frameworks.length !== 1 ? 's' : ''} · ${summary ? `${summary.overall_score}% overall` : 'loading…'}`
              : 'No compliance frameworks configured'
            }
            {summary?.last_assessment && ` · Last assessed ${fmtTime(summary.last_assessment)}`}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={handleRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 hover:bg-white/10 border border-white/10 text-foreground rounded-lg transition-colors">
            <RefreshCw size={12} className={(sumLoading || fwLoading) ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 hover:bg-white/10 border border-white/10 text-foreground rounded-lg transition-colors">
            <Download size={12} /> Export CSV
          </button>
        </div>
      </div>

      {/* Tab nav */}
      <div className="flex items-center gap-1 p-1 bg-surface-2 rounded-xl border border-white/5 w-fit mb-5 overflow-x-auto shrink-0">
        {TABS.map(t => {
          const Icon = t.icon;
          return (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={clsx('flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-lg transition-all whitespace-nowrap',
                activeTab === t.id ? 'bg-surface-1 text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              <Icon size={11} />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {activeTab === 'overview'    && <OverviewTab summary={summary} frameworks={frameworks} onSetTab={setActiveTab} />}
        {activeTab === 'frameworks'  && <FrameworksTab frameworks={frameworks} loading={fwLoading} />}
        {activeTab === 'controls'    && <ControlsTab frameworks={frameworks} onSelectControl={setSelectedControl} />}
        {activeTab === 'evidence'    && <EvidenceTab frameworks={frameworks} />}
        {activeTab === 'resources'   && <ResourcesTab />}
        {activeTab === 'assessments' && <AssessmentsTab />}
        {activeTab === 'exceptions'  && <ExceptionsTab />}
      </div>

      {/* Detail drawer */}
      {selectedControl && (
        <>
          <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={() => setSelectedControl(null)} />
          <ControlDrawer control={selectedControl} onClose={() => setSelectedControl(null)} />
        </>
      )}
    </div>
  );
}
