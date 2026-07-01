import {
  useState, useEffect, useCallback, useRef, useMemo, memo,
} from 'react';
import {
  CheckSquare, RefreshCw, AlertTriangle, CheckCircle, X,
  ChevronRight, ChevronDown, ChevronUp, Shield, Search,
  Download, FileText, Clock, Settings,
  BarChart3, Database, Server, GitBranch, Layers, Package,
  AlertCircle, ClipboardList, History, ShieldOff,
  ShieldCheck, Crosshair, FileCheck, Globe, Zap,
  TrendingDown, TrendingUp,
  BookOpen, Play, Network, MapPin, Link2, Activity,
  Workflow, Terminal, Eye, Lock,
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

interface PolicyFinding {
  id: string;
  type: 'threat' | 'vulnerability';
  title: string;
  severity: string;
  status: string;
  source?: string;
  resource?: string;
  cve_id?: string;
  cvss?: number;
  remediation: { available: boolean; action: string; fixed_version?: string };
}

interface PolicyNode {
  id: string;
  name: string;
  category: string;
  severity: string;
  enforcement: string;
  violations: number;
  findings: PolicyFinding[];
  finding_count: number;
}

interface MappingControl {
  id: string;
  control_id: string;
  title: string;
  category: string;
  severity: string;
  status: string;
  has_evidence: boolean;
  policies: PolicyNode[];
  policy_count: number;
}

interface PolicyMappingFramework {
  framework: string;
  framework_id: string;
  score: number;
  status: string;
  controls: MappingControl[];
}

interface TimelineEvent {
  type: string;
  label: string;
  description: string;
  timestamp: string;
  actor: string | null;
  severity: string;
  icon: string;
  resource?: string;
  status?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'overview',       label: 'Overview',        icon: BarChart3 },
  { id: 'frameworks',     label: 'Frameworks',       icon: BookOpen },
  { id: 'controls',       label: 'Controls',         icon: CheckSquare },
  { id: 'evidence',       label: 'Evidence',         icon: FileCheck },
  { id: 'policy_mapping', label: 'Policy Mapping',   icon: Network },
  { id: 'resources',      label: 'Non-Compliant',    icon: ShieldOff },
  { id: 'assessments',    label: 'Assessments',      icon: History },
  { id: 'exceptions',     label: 'Exceptions',       icon: AlertCircle },
  { id: 'timeline',       label: 'Timeline',         icon: Activity },
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

const DRAWER_SECTIONS = [
  { key: 'overview',    label: 'Overview' },
  { key: 'policies',    label: 'Policies' },
  { key: 'assets',      label: 'Assets' },
  { key: 'repos',       label: 'Repos' },
  { key: 'k8s',         label: 'Kubernetes' },
  { key: 'cloud',       label: 'Cloud' },
  { key: 'findings',    label: 'Findings' },
  { key: 'evidence',    label: 'Evidence' },
  { key: 'remediations',label: 'Remediations' },
  { key: 'exceptions',  label: 'Exceptions' },
  { key: 'audit',       label: 'Audit Log' },
  { key: 'timeline',    label: 'Timeline' },
];

const DrawerSection = ({ title, children, empty }: { title: string; children?: React.ReactNode; empty?: string }) => (
  <div>
    <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">{title}</h3>
    {children ?? <p className="text-xs text-muted-foreground">{empty}</p>}
  </div>
);

const DrawerRow = ({ label, value }: { label: string; value: React.ReactNode }) => (
  <div className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
    <span className="text-xs text-muted-foreground">{label}</span>
    <span className="text-xs text-foreground text-right max-w-[60%]">{value}</span>
  </div>
);

const DrawerCard = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <div className={clsx('p-3 bg-surface-2 rounded-lg mb-2 border border-white/5', className)}>{children}</div>
);

const TimelineDot = ({ icon, severity }: { icon: string; severity: string }) => {
  const color = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    high:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
    medium:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    info:     'bg-blue-500/20 text-blue-400 border-blue-500/30',
  }[severity] ?? 'bg-slate-500/20 text-slate-400 border-slate-500/30';

  const IconMap: Record<string, React.ElementType> = {
    'play':          Play,
    'file-check':    FileCheck,
    'check-square':  CheckSquare,
    'alert-triangle':AlertTriangle,
    'check-circle':  CheckCircle,
    'shield':        Shield,
    'file-text':     FileText,
  };
  const Icon = IconMap[icon] ?? Activity;

  return (
    <div className={clsx('w-7 h-7 rounded-full border flex items-center justify-center shrink-0', color)}>
      <Icon size={12} />
    </div>
  );
};

const ControlDrawer = memo(({ control, onClose }: { control: Control; onClose: () => void }) => {
  const { data: detail, loading } = useApi<Control>(
    `/compliance/controls/${encodeURIComponent(control.id)}?framework=${encodeURIComponent(control.framework)}`
  );
  const ctrl = detail ?? control;
  const [section, setSection] = useState('overview');

  // Synthesise timeline from what we know about the control
  const timelineEvents: Array<{ label: string; desc: string; time: string | null; icon: string; severity: string }> = [];
  if (ctrl.last_evaluated) {
    timelineEvents.push({ label: 'Control Evaluated', desc: `Status: ${ctrl.status}`, time: ctrl.last_evaluated, icon: 'check-square', severity: 'info' });
  }
  if (!ctrl.has_evidence) {
    timelineEvents.push({ label: 'Evidence Missing', desc: 'No evidence collected yet', time: ctrl.last_evaluated, icon: 'alert-triangle', severity: 'medium' });
  } else {
    timelineEvents.push({ label: 'Evidence Collected', desc: `${ctrl.evidence_count} item(s)`, time: ctrl.last_evaluated, icon: 'file-check', severity: 'info' });
  }
  if (ctrl.related_threats && ctrl.related_threats.length > 0) {
    ctrl.related_threats.forEach((t: any) => {
      timelineEvents.push({ label: 'Violation Detected', desc: t.title, time: t.detected_at ?? ctrl.last_evaluated, icon: 'alert-triangle', severity: t.severity });
    });
  }
  if (ctrl.exceptions && ctrl.exceptions.length > 0) {
    ctrl.exceptions.forEach((e: any) => {
      timelineEvents.push({ label: 'Exception Created', desc: e.title || e.reason || 'Compliance exception', time: e.created_at, icon: 'shield', severity: 'medium' });
    });
  }

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
      <div className="flex items-center gap-0.5 px-3 py-2 border-b border-white/5 overflow-x-auto shrink-0">
        {DRAWER_SECTIONS.map(s => (
          <button key={s.key} onClick={() => setSection(s.key)}
            className={clsx('px-2.5 py-1.5 text-[10px] font-medium rounded-md transition-all whitespace-nowrap',
              section === s.key ? 'bg-surface-2 text-foreground' : 'text-muted-foreground hover:text-foreground')}
          >{s.label}</button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {loading && <div className="h-32 bg-surface-2 rounded-xl animate-pulse" />}

        {/* ── Overview ── */}
        {section === 'overview' && (
          <>
            {ctrl.description && (
              <DrawerSection title="Description">
                <p className="text-xs text-foreground/80 leading-relaxed">{ctrl.description}</p>
              </DrawerSection>
            )}
            <DrawerSection title="Details">
              <DrawerRow label="Framework"      value={ctrl.framework} />
              <DrawerRow label="Category"       value={ctrl.category} />
              <DrawerRow label="Owner"          value={ctrl.owner || '—'} />
              <DrawerRow label="Last Evaluated" value={fmtTime(ctrl.last_evaluated)} />
              <DrawerRow label="Next Evaluation"value={fmtTime(ctrl.next_evaluation)} />
              <DrawerRow label="Evidence Count" value={ctrl.evidence_count} />
              <DrawerRow label="Score"          value={ctrl.score != null ? `${ctrl.score}%` : '—'} />
            </DrawerSection>
          </>
        )}

        {/* ── Mapped Policies ── */}
        {section === 'policies' && (
          <DrawerSection title="Mapped Policies"
            empty={ctrl.mapped_policies.length === 0 ? 'No policies mapped to this control.' : undefined}>
            {ctrl.mapped_policies.length > 0 && ctrl.mapped_policies.map((p: any, i: number) => (
              <DrawerCard key={p.id ?? i}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">{p.name}</p>
                    <p className="text-[10px] text-muted-foreground capitalize mt-0.5">{p.category} · {p.enforcement || 'enforce'}</p>
                    {p.violations > 0 && <p className="text-[10px] text-red-400 mt-0.5">{p.violations} violation{p.violations !== 1 ? 's' : ''}</p>}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <SevBadge sev={p.severity} />
                    <StatusBadge status={p.status ?? 'active'} />
                  </div>
                </div>
              </DrawerCard>
            ))}
          </DrawerSection>
        )}

        {/* ── Mapped Assets ── */}
        {section === 'assets' && (
          <DrawerSection title="Mapped Assets"
            empty={(ctrl.mapped_assets ?? []).length === 0 ? 'No assets mapped to this control.' : undefined}>
            {(ctrl.mapped_assets ?? []).map((a: any, i: number) => (
              <DrawerCard key={a.id ?? i}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Server size={13} className="text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{a.name || a.hostname || a.ip_address || 'Asset'}</p>
                      <p className="text-[10px] text-muted-foreground capitalize">{a.asset_type || a.type} · {a.cloud_provider || a.region || '—'}</p>
                    </div>
                  </div>
                  <StatusBadge status={a.status ?? 'unknown'} />
                </div>
              </DrawerCard>
            ))}
          </DrawerSection>
        )}

        {/* ── Mapped Repositories ── */}
        {section === 'repos' && (
          <DrawerSection title="Mapped Repositories"
            empty={(ctrl.mapped_repos ?? []).length === 0 ? 'No repositories mapped to this control.' : undefined}>
            {(ctrl.mapped_repos ?? []).map((r: any, i: number) => (
              <DrawerCard key={r.id ?? i}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <GitBranch size={13} className="text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{r.name || r.full_name}</p>
                      <p className="text-[10px] text-muted-foreground">{r.language || '—'} · {r.default_branch || 'main'}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {r.open_issues_count > 0 && <span className="text-[10px] text-orange-400">{r.open_issues_count} issues</span>}
                    <StatusBadge status={r.visibility || 'private'} />
                  </div>
                </div>
              </DrawerCard>
            ))}
          </DrawerSection>
        )}

        {/* ── Mapped Kubernetes ── */}
        {section === 'k8s' && (
          <DrawerSection title="Mapped Kubernetes Resources"
            empty={(ctrl.mapped_k8s ?? []).length === 0 ? 'No Kubernetes resources mapped to this control.' : undefined}>
            {(ctrl.mapped_k8s ?? []).map((k: any, i: number) => (
              <DrawerCard key={k.id ?? i}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Layers size={13} className="text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{k.name}</p>
                      <p className="text-[10px] text-muted-foreground">{k.kind || k.resource_type} · {k.namespace || 'cluster-scoped'}</p>
                    </div>
                  </div>
                  <StatusBadge status={k.status ?? 'unknown'} />
                </div>
              </DrawerCard>
            ))}
          </DrawerSection>
        )}

        {/* ── Mapped Cloud Resources ── */}
        {section === 'cloud' && (
          <DrawerSection title="Mapped Cloud Resources">
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <Globe size={28} className="text-muted-foreground/40" />
              <p className="text-xs text-muted-foreground">Cloud resource mapping requires AWS/Azure/GCP integration.</p>
            </div>
          </DrawerSection>
        )}

        {/* ── Related Findings ── */}
        {section === 'findings' && (
          <div className="space-y-4">
            {ctrl.related_threats && ctrl.related_threats.length > 0 && (
              <DrawerSection title="Related Threats">
                {ctrl.related_threats.map((t: any) => (
                  <DrawerCard key={t.id}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">{t.title}</p>
                        {t.source && <p className="text-[10px] text-muted-foreground capitalize mt-0.5">Source: {t.source}</p>}
                        {t.resource && <p className="text-[10px] text-muted-foreground font-mono mt-0.5 truncate">{t.resource}</p>}
                      </div>
                      <SevBadge sev={t.severity} />
                    </div>
                  </DrawerCard>
                ))}
              </DrawerSection>
            )}
            {ctrl.related_vulnerabilities && ctrl.related_vulnerabilities.length > 0 && (
              <DrawerSection title="Related Vulnerabilities">
                {ctrl.related_vulnerabilities.map((v: any) => (
                  <DrawerCard key={v.id}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium text-foreground truncate">{v.title}</p>
                        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                          {v.cve_id && <span className="text-[10px] font-mono text-blue-400">{v.cve_id}</span>}
                          {v.package_name && <span className="text-[10px] text-muted-foreground">{v.package_name}</span>}
                          {v.fixed_version && <span className="text-[10px] text-green-400">Fix: {v.fixed_version}</span>}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {v.cvss_score != null && <span className="text-[10px] font-mono text-orange-400">CVSS {v.cvss_score?.toFixed(1)}</span>}
                        <SevBadge sev={v.severity} />
                      </div>
                    </div>
                  </DrawerCard>
                ))}
              </DrawerSection>
            )}
            {(!ctrl.related_threats?.length && !ctrl.related_vulnerabilities?.length) && (
              <DrawerSection title="Related Findings" empty="No related findings." />
            )}
          </div>
        )}

        {/* ── Evidence ── */}
        {section === 'evidence' && (
          <DrawerSection title="Evidence"
            empty={ctrl.evidence_count === 0 ? 'No evidence collected for this control.' : undefined}>
            {ctrl.evidence_count > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                  <FileCheck size={14} className="text-green-400" />
                  <div>
                    <p className="text-xs font-medium text-green-400">{ctrl.evidence_count} evidence item{ctrl.evidence_count !== 1 ? 's' : ''} collected</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">Switch to the Evidence tab to view and download all evidence for this control.</p>
                  </div>
                </div>
              </div>
            )}
          </DrawerSection>
        )}

        {/* ── Remediations ── */}
        {section === 'remediations' && (
          <DrawerSection title="Related Remediations">
            {(ctrl.related_vulnerabilities ?? []).filter((v: any) => v.fixed_version).length > 0 ? (
              (ctrl.related_vulnerabilities ?? []).filter((v: any) => v.fixed_version).map((v: any, i: number) => (
                <DrawerCard key={v.id ?? i}>
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-500/15 border border-green-500/30 flex items-center justify-center shrink-0 mt-0.5">
                      <CheckCircle size={11} className="text-green-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-foreground">Upgrade {v.package_name}</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">Fix available: {v.fixed_version}</p>
                      {v.cve_id && <p className="text-[10px] font-mono text-blue-400 mt-0.5">{v.cve_id}</p>}
                    </div>
                    <SevBadge sev={v.severity} />
                  </div>
                </DrawerCard>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-8 gap-2">
                <ClipboardList size={24} className="text-muted-foreground/40" />
                <p className="text-xs text-muted-foreground">No active remediations for this control.</p>
              </div>
            )}
          </DrawerSection>
        )}

        {/* ── Exceptions ── */}
        {section === 'exceptions' && (
          <DrawerSection title="Exceptions"
            empty={ctrl.exceptions.length === 0 ? 'No exceptions for this control.' : undefined}>
            {ctrl.exceptions.length > 0 && ctrl.exceptions.map((e: any, i: number) => (
              <DrawerCard key={i}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-foreground">{e.title || e.reason || 'Exception'}</p>
                    {e.justification && <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{e.justification}</p>}
                    {e.expires_at && <p className="text-[10px] text-orange-400 mt-0.5">Expires: {fmt(e.expires_at)}</p>}
                  </div>
                  <StatusBadge status={e.status ?? 'pending'} />
                </div>
              </DrawerCard>
            ))}
          </DrawerSection>
        )}

        {/* ── Audit Log ── */}
        {section === 'audit' && (
          <DrawerSection title="Audit History">
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <FileText size={24} className="text-muted-foreground/40" />
              <p className="text-xs text-muted-foreground">Audit logs are available in the Timeline tab. Full log export coming soon.</p>
            </div>
          </DrawerSection>
        )}

        {/* ── Timeline ── */}
        {section === 'timeline' && (
          <DrawerSection title="Timeline">
            {timelineEvents.length === 0 ? (
              <p className="text-xs text-muted-foreground">No timeline events.</p>
            ) : (
              <div className="relative pl-4">
                <div className="absolute left-3.5 top-0 bottom-0 w-px bg-white/8" />
                {timelineEvents.map((ev, i) => (
                  <div key={i} className="flex items-start gap-3 mb-5 relative">
                    <TimelineDot icon={ev.icon} severity={ev.severity} />
                    <div className="flex-1 min-w-0 pt-0.5">
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-medium text-foreground">{ev.label}</p>
                        <SevBadge sev={ev.severity} />
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">{ev.desc}</p>
                      <p className="text-[10px] text-muted-foreground/60 mt-0.5 font-mono">{fmtTime(ev.time)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </DrawerSection>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-white/8 flex items-center gap-2 shrink-0">
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 border border-white/10 hover:bg-white/10 text-foreground rounded-md transition-colors">
          <Download size={12} /> Export PDF
        </button>
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 border border-white/10 hover:bg-white/10 text-foreground rounded-md transition-colors">
          <FileText size={12} /> Audit Log
        </button>
        <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface-2 border border-white/10 hover:bg-white/10 text-foreground rounded-md transition-colors">
          <Download size={12} /> Export CSV
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

// ─── Policy Mapping Tab ───────────────────────────────────────────────────────

const PolicyMappingTab = memo(({ frameworks }: { frameworks: Framework[] }) => {
  const [fwFilter, setFwFilter] = useState('');
  const qs = fwFilter ? `framework=${encodeURIComponent(fwFilter)}` : '';
  const { data: tree, loading, error, refetch } = useApi<PolicyMappingFramework[]>(`/compliance/policy-mapping?${qs}`);
  const data = tree ?? [];

  const [expandedFw, setExpandedFw]   = useState<Record<string, boolean>>({});
  const [expandedCtrl, setExpandedCtrl] = useState<Record<string, boolean>>({});
  const [expandedPolicy, setExpandedPolicy] = useState<Record<string, boolean>>({});

  const toggleFw   = (id: string) => setExpandedFw(p   => ({ ...p, [id]: !p[id] }));
  const toggleCtrl = (id: string) => setExpandedCtrl(p => ({ ...p, [id]: !p[id] }));
  const togglePol  = (id: string) => setExpandedPolicy(p => ({ ...p, [id]: !p[id] }));

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap sticky top-0 z-10 bg-surface-1/95 backdrop-blur-sm py-2">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Network size={13} className="text-blue-400" />
          <span className="font-medium text-foreground">Policy Mapping</span>
          <span className="text-muted-foreground">— Framework → Control → Policy → Finding → Remediation</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <select value={fwFilter} onChange={e => setFwFilter(e.target.value)}
            className="bg-surface-2 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-blue-500/50">
            <option value="">All Frameworks</option>
            {frameworks.map(f => <option key={f.id} value={f.framework}>{f.framework}</option>)}
          </select>
          <button onClick={() => refetch()} className="p-2 rounded-lg bg-surface-2 border border-white/10 text-muted-foreground hover:text-foreground transition-colors">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 px-3 py-2 bg-surface-2 border border-white/5 rounded-lg text-[10px] text-muted-foreground">
        {[
          { color: 'bg-blue-500/20 text-blue-400',   label: 'Framework' },
          { color: 'bg-purple-500/20 text-purple-400',label: 'Control' },
          { color: 'bg-indigo-500/20 text-indigo-400',label: 'Policy' },
          { color: 'bg-orange-500/20 text-orange-400',label: 'Finding' },
          { color: 'bg-green-500/20 text-green-400',  label: 'Remediation' },
        ].map(l => (
          <div key={l.label} className="flex items-center gap-1.5">
            <div className={clsx('w-2 h-2 rounded-full', l.color)} />
            <span>{l.label}</span>
          </div>
        ))}
      </div>

      {loading && data.length === 0 ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-16 bg-surface-2 rounded-xl animate-pulse" />)}</div>
      ) : error ? (
        <EmptyState title="Failed to load policy mapping" subtitle={error} icon={Network} />
      ) : data.length === 0 ? (
        <EmptyState title="No policy mapping data" subtitle="Configure compliance frameworks and policies to see the mapping chain." icon={Network} action={
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"><Settings size={14} /> Configure</button>
        } />
      ) : (
        <div className="space-y-2">
          {data.map(fw => (
            <div key={fw.framework_id} className="bg-surface-2 border border-white/5 rounded-xl overflow-hidden">
              {/* Framework row */}
              <button onClick={() => toggleFw(fw.framework_id)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/3 transition-colors text-left">
                <div className="w-5 h-5 rounded bg-blue-500/20 border border-blue-500/30 flex items-center justify-center shrink-0">
                  <BookOpen size={11} className="text-blue-400" />
                </div>
                <span className="text-base shrink-0">{FRAMEWORK_ICON[fw.framework] || '📋'}</span>
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-semibold text-foreground">{fw.framework}</span>
                  <span className="text-[10px] text-muted-foreground ml-2">{fw.controls.length} controls · {fw.score}%</span>
                </div>
                <StatusBadge status={fw.status} />
                {expandedFw[fw.framework_id] ? <ChevronDown size={13} className="text-muted-foreground" /> : <ChevronRight size={13} className="text-muted-foreground" />}
              </button>

              {expandedFw[fw.framework_id] && (
                <div className="border-t border-white/5">
                  {fw.controls.map(ctrl => (
                    <div key={ctrl.id} className="border-b border-white/4 last:border-0">
                      {/* Control row */}
                      <button onClick={() => toggleCtrl(ctrl.id)}
                        className="w-full flex items-center gap-3 pl-10 pr-4 py-2.5 hover:bg-white/2 transition-colors text-left">
                        <div className="w-4 h-4 rounded bg-purple-500/20 border border-purple-500/30 flex items-center justify-center shrink-0">
                          <CheckSquare size={9} className="text-purple-400" />
                        </div>
                        <span className="font-mono text-[10px] text-purple-400 shrink-0">{ctrl.control_id}</span>
                        <span className="text-[11px] text-foreground/80 flex-1 truncate">{ctrl.title}</span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <SevBadge sev={ctrl.severity} />
                          <StatusBadge status={ctrl.status} />
                          {ctrl.has_evidence && <span className="text-[9px] px-1 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20">Evidence</span>}
                          <span className="text-[10px] text-muted-foreground">{ctrl.policy_count}P</span>
                          {expandedCtrl[ctrl.id] ? <ChevronDown size={11} className="text-muted-foreground" /> : <ChevronRight size={11} className="text-muted-foreground" />}
                        </div>
                      </button>

                      {expandedCtrl[ctrl.id] && ctrl.policies.length > 0 && (
                        <div className="pb-1">
                          {ctrl.policies.map(pol => (
                            <div key={pol.id} className="border-b border-white/3 last:border-0">
                              {/* Policy row */}
                              <button onClick={() => togglePol(pol.id)}
                                className="w-full flex items-center gap-3 pl-16 pr-4 py-2 hover:bg-white/2 transition-colors text-left">
                                <div className="w-3.5 h-3.5 rounded bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
                                  <Lock size={8} className="text-indigo-400" />
                                </div>
                                <span className="text-[10px] text-foreground/70 flex-1 truncate">{pol.name}</span>
                                <div className="flex items-center gap-1.5 shrink-0">
                                  <SevBadge sev={pol.severity} />
                                  {pol.violations > 0 && <span className="text-[9px] text-red-400">{pol.violations}V</span>}
                                  <span className="text-[9px] text-muted-foreground">{pol.finding_count}F</span>
                                  {expandedPolicy[pol.id] ? <ChevronDown size={10} className="text-muted-foreground" /> : <ChevronRight size={10} className="text-muted-foreground" />}
                                </div>
                              </button>

                              {expandedPolicy[pol.id] && pol.findings.length > 0 && (
                                <div className="pb-1">
                                  {pol.findings.map(f => (
                                    <div key={f.id} className="pl-20 pr-4 py-1.5 border-b border-white/2 last:border-0">
                                      <div className="flex items-start gap-2">
                                        <div className="w-3 h-3 rounded bg-orange-500/20 border border-orange-500/30 flex items-center justify-center shrink-0 mt-0.5">
                                          <AlertTriangle size={7} className="text-orange-400" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                          <div className="flex items-center gap-2">
                                            <span className="text-[10px] text-foreground/70 truncate flex-1">{f.title}</span>
                                            <SevBadge sev={f.severity} />
                                            <span className={clsx('text-[9px] px-1 py-0.5 rounded uppercase font-mono',
                                              f.type === 'threat' ? 'bg-red-500/10 text-red-400' : 'bg-orange-500/10 text-orange-400')}>
                                              {f.type}
                                            </span>
                                          </div>
                                          {/* Remediation */}
                                          <div className="flex items-center gap-1.5 mt-1 pl-0">
                                            <div className={clsx('w-2.5 h-2.5 rounded-full border flex items-center justify-center shrink-0',
                                              f.remediation.available ? 'bg-green-500/20 border-green-500/30' : 'bg-slate-500/20 border-slate-500/30')}>
                                              <CheckCircle size={6} className={f.remediation.available ? 'text-green-400' : 'text-slate-500'} />
                                            </div>
                                            <span className="text-[9px] text-muted-foreground">{f.remediation.action}</span>
                                          </div>
                                        </div>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                              {expandedPolicy[pol.id] && pol.findings.length === 0 && (
                                <p className="pl-20 pr-4 pb-2 text-[10px] text-muted-foreground">No findings for this policy.</p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      {expandedCtrl[ctrl.id] && ctrl.policies.length === 0 && (
                        <p className="pl-16 pr-4 pb-2.5 text-[10px] text-muted-foreground">No policies mapped to this control.</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

// ─── Timeline Tab ─────────────────────────────────────────────────────────────

const TL_ICON_MAP: Record<string, React.ElementType> = {
  'play':          Play,
  'file-check':    FileCheck,
  'check-square':  CheckSquare,
  'alert-triangle':AlertTriangle,
  'check-circle':  CheckCircle,
  'shield':        Shield,
  'file-text':     FileText,
};

const TL_SEV_COLOR: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  info:     'bg-blue-500/20 text-blue-400 border-blue-500/30',
};

const TL_TYPE_LABEL: Record<string, string> = {
  assessment_started:  'Assessment Started',
  evidence_collected:  'Evidence Collected',
  control_evaluated:   'Control Evaluated',
  violation_detected:  'Violation Detected',
  control_passed:      'Control Passed',
  audit_logged:        'Audit Logged',
};

const TimelineTab = memo(({ frameworks }: { frameworks: Framework[] }) => {
  const [fwFilter, setFwFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const qs = [fwFilter && `framework=${encodeURIComponent(fwFilter)}`, 'limit=100'].filter(Boolean).join('&');
  const { data: rawEvents, loading, error, refetch } = useApi<TimelineEvent[]>(`/compliance/timeline?${qs}`);
  const events = (rawEvents ?? []).filter(e => !typeFilter || e.type === typeFilter);

  const EVENT_TYPES = [
    { value: '', label: 'All Events' },
    { value: 'assessment_started',  label: 'Assessment Started' },
    { value: 'evidence_collected',  label: 'Evidence Collected' },
    { value: 'control_evaluated',   label: 'Control Evaluated' },
    { value: 'violation_detected',  label: 'Violation Detected' },
    { value: 'control_passed',      label: 'Control Passed' },
    { value: 'audit_logged',        label: 'Audit Logged' },
  ];

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap sticky top-0 z-10 bg-surface-1/95 backdrop-blur-sm py-2">
        <Activity size={13} className="text-blue-400" />
        <span className="text-xs font-medium text-foreground">Compliance Timeline</span>
        <span className="text-xs text-muted-foreground ml-1">— {events.length} event{events.length !== 1 ? 's' : ''}</span>
        <div className="ml-auto flex items-center gap-2">
          <select value={fwFilter} onChange={e => setFwFilter(e.target.value)}
            className="bg-surface-2 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-blue-500/50">
            <option value="">All Frameworks</option>
            {frameworks.map(f => <option key={f.id} value={f.framework}>{f.framework}</option>)}
          </select>
          <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
            className="bg-surface-2 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-blue-500/50">
            {EVENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <button onClick={() => refetch()} className="p-2 rounded-lg bg-surface-2 border border-white/10 text-muted-foreground hover:text-foreground transition-colors">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {loading && events.length === 0 ? (
        <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-full bg-surface-2 animate-pulse shrink-0" />
            <div className="flex-1 space-y-1.5 pt-1">
              <div className="h-3 bg-surface-2 rounded animate-pulse w-32" />
              <div className="h-2.5 bg-surface-2 rounded animate-pulse w-64" />
              <div className="h-2 bg-surface-2 rounded animate-pulse w-20" />
            </div>
          </div>
        ))}</div>
      ) : error ? (
        <EmptyState title="Failed to load timeline" subtitle={error} icon={Activity} />
      ) : events.length === 0 ? (
        <EmptyState title="No timeline events" subtitle="Compliance events will appear here as assessments run and findings are detected." icon={Activity} />
      ) : (
        <div className="relative pl-4">
          {/* Vertical line */}
          <div className="absolute left-3.5 top-3.5 bottom-0 w-px bg-white/8" />

          {events.map((ev, i) => {
            const Icon = TL_ICON_MAP[ev.icon] ?? Activity;
            const dotColor = TL_SEV_COLOR[ev.severity] ?? 'bg-slate-500/20 text-slate-400 border-slate-500/30';

            return (
              <div key={i} className="flex items-start gap-3 mb-5 relative">
                {/* Dot */}
                <div className={clsx('w-7 h-7 rounded-full border flex items-center justify-center shrink-0 relative z-10 bg-surface-1', dotColor)}>
                  <Icon size={12} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 bg-surface-2 border border-white/5 rounded-xl p-3 hover:border-white/10 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-semibold text-foreground">
                          {TL_TYPE_LABEL[ev.type] ?? ev.label}
                        </span>
                        <SevBadge sev={ev.severity} />
                        {ev.status && ev.status !== 'success' && <StatusBadge status={ev.status} />}
                      </div>
                      <p className="text-[10px] text-foreground/70 mt-1 leading-relaxed">{ev.description}</p>
                      {ev.resource && (
                        <p className="text-[10px] font-mono text-blue-400/70 mt-0.5 truncate">{ev.resource}</p>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-[10px] text-muted-foreground font-mono whitespace-nowrap">{fmtTime(ev.timestamp)}</p>
                      {ev.actor && <p className="text-[9px] text-muted-foreground/60 mt-0.5 truncate max-w-[80px]">{ev.actor}</p>}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
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
        {activeTab === 'overview'       && <OverviewTab summary={summary} frameworks={frameworks} onSetTab={setActiveTab} />}
        {activeTab === 'frameworks'     && <FrameworksTab frameworks={frameworks} loading={fwLoading} />}
        {activeTab === 'controls'       && <ControlsTab frameworks={frameworks} onSelectControl={setSelectedControl} />}
        {activeTab === 'evidence'       && <EvidenceTab frameworks={frameworks} />}
        {activeTab === 'policy_mapping' && <PolicyMappingTab frameworks={frameworks} />}
        {activeTab === 'resources'      && <ResourcesTab />}
        {activeTab === 'assessments'    && <AssessmentsTab />}
        {activeTab === 'exceptions'     && <ExceptionsTab />}
        {activeTab === 'timeline'       && <TimelineTab frameworks={frameworks} />}
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
