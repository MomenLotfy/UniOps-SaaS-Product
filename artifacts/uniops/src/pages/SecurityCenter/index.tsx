import { useState, useCallback, lazy, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, AlertTriangle, Bug, CheckSquare, GitBranch,
  Server, TrendingUp, FileText, ClipboardList, BookOpen,
  ChevronRight, X, Layers, Package, Users, Clock, Bot,
  Wrench, Eye, BarChart3, Cloud, Gavel,
} from 'lucide-react';
import { clsx } from 'clsx';
import { usePermissions } from '@/hooks/use-permissions';
import { canReadSecurity } from '@/lib/permissions';
import SecurityTopBar from './components/SecurityTopBar';
import SecurityKPIBar from './components/SecurityKPIBar';

// ── Lazy-load every section for performance ───────────────────────────────
const Overview            = lazy(() => import('./sections/Overview'));
const Threats             = lazy(() => import('./sections/Threats'));
const Vulnerabilities     = lazy(() => import('./sections/Vulnerabilities'));
const Compliance          = lazy(() => import('./sections/Compliance'));
const Repositories        = lazy(() => import('./sections/Repositories'));
const Assets              = lazy(() => import('./sections/Assets'));
const SecurityPosture     = lazy(() => import('./sections/SecurityPosture'));
const Policies            = lazy(() => import('./sections/Policies'));
const Exceptions          = lazy(() => import('./sections/Exceptions'));
const Reports             = lazy(() => import('./sections/Reports'));
const KubernetesSecurity  = lazy(() => import('./sections/KubernetesSecurity'));
const SBOMSection         = lazy(() => import('./sections/SBOM'));
const Ownership           = lazy(() => import('./sections/Ownership'));
const SLATracker          = lazy(() => import('./sections/SLATracker'));
const Intelligence        = lazy(() => import('./sections/Intelligence'));
const Remediation         = lazy(() => import('./sections/Remediation'));
const Decisions           = lazy(() => import('./sections/Decisions'));
const Rules               = lazy(() => import('./sections/Rules'));
const SecurityCopilot     = lazy(() => import('./SecurityCopilot'));
const InfrastructureOverview = lazy(() => import('./sections/InfrastructureOverview'));
const GovernanceOverview  = lazy(() => import('./sections/GovernanceOverview'));

export type SecuritySection =
  | 'repositories' | 'overview' | 'infrastructure' | 'assets' | 'kubernetes'
  | 'threats' | 'vulnerabilities' | 'posture' | 'remediation' | 'intelligence'
  | 'compliance' | 'policies' | 'exceptions' | 'governance' | 'ownership'
  | 'sla' | 'reports' | 'sbom' | 'copilot' | 'decisions' | 'rules';

interface NavItem {
  id: SecuritySection;
  label: string;
  icon: React.ElementType;
  description: string;
  badge?: string;
  badgeColor?: string;
  group: string;
}

// ── New nav order per design spec ─────────────────────────────────────────
const NAV_ITEMS: NavItem[] = [
  // ── Core
  { id: 'repositories',    label: 'Repositories',     icon: GitBranch,   description: 'Repo scanning & risk',          group: 'Core' },
  { id: 'overview',        label: 'Overview',          icon: BarChart3,   description: 'Security dashboard',            group: 'Core' },
  // ── Infrastructure
  { id: 'infrastructure',  label: 'Infrastructure',    icon: Cloud,       description: 'Cloud infra overview',          group: 'Infrastructure' },
  { id: 'assets',          label: 'Assets',            icon: Server,      description: 'Asset inventory',               group: 'Infrastructure' },
  { id: 'kubernetes',      label: 'Kubernetes',        icon: Layers,      description: 'K8s cluster scanning',          group: 'Infrastructure', badge: 'NEW', badgeColor: 'indigo' },
  // ── Detection
  { id: 'threats',         label: 'Threats',           icon: AlertTriangle, description: 'Active threats',              group: 'Detection' },
  { id: 'vulnerabilities', label: 'Vulnerabilities',   icon: Bug,         description: 'CVEs and findings',             group: 'Detection' },
  // ── Posture
  { id: 'posture',         label: 'Security Posture',  icon: TrendingUp,  description: 'Posture score & trends',        group: 'Posture' },
  // ── Governance
  { id: 'remediation',     label: 'Remediation',       icon: Wrench,      description: 'Auto-remediation engine',       group: 'Governance', badge: 'NEW', badgeColor: 'indigo' },
  { id: 'intelligence',    label: 'Intelligence',      icon: Eye,         description: 'Security intel foundation',     group: 'Governance', badge: 'NEW', badgeColor: 'indigo' },
  { id: 'compliance',      label: 'Compliance',        icon: CheckSquare, description: 'Framework compliance',          group: 'Governance' },
  { id: 'policies',        label: 'Policies',          icon: BookOpen,    description: 'Security policies',             group: 'Governance' },
  { id: 'exceptions',      label: 'Exceptions',        icon: ClipboardList, description: 'Exception requests',          group: 'Governance' },
  { id: 'governance',      label: 'Governance',        icon: Gavel,       description: 'Policy & exception summary',    group: 'Governance' },
  { id: 'ownership',       label: 'Ownership',         icon: Users,       description: 'Owner / team / department',     group: 'Governance', badge: 'NEW', badgeColor: 'indigo' },
  { id: 'sla',             label: 'SLA Tracker',       icon: Clock,       description: 'Remediation SLA deadlines',     group: 'Governance', badge: 'NEW', badgeColor: 'indigo' },
  // ── Reports
  { id: 'reports',         label: 'Reports',           icon: FileText,    description: 'Audit & reports',               group: 'Reports' },
  { id: 'sbom',            label: 'SBOM',              icon: Package,     description: 'Software Bill of Materials',    group: 'Reports' },
  // ── AI
  { id: 'copilot',         label: 'Security Copilot',  icon: Bot,         description: 'AI Security Assistant',         group: 'AI', badge: 'AI', badgeColor: 'blue' },
];

const GROUPS = ['Core', 'Infrastructure', 'Detection', 'Posture', 'Governance', 'Reports', 'AI'];

const SECTION_COMPONENTS: Record<SecuritySection, React.ComponentType> = {
  repositories:   Repositories,
  overview:       Overview,
  infrastructure: InfrastructureOverview,
  assets:         Assets,
  kubernetes:     KubernetesSecurity,
  threats:        Threats,
  vulnerabilities: Vulnerabilities,
  posture:        SecurityPosture,
  remediation:    Remediation,
  intelligence:   Intelligence,
  compliance:     Compliance,
  policies:       Policies,
  exceptions:     Exceptions,
  governance:     GovernanceOverview,
  ownership:      Ownership,
  sla:            SLATracker,
  reports:        Reports,
  sbom:           SBOMSection,
  copilot:        SecurityCopilot,
  decisions:      Decisions,
  rules:          Rules,
};

const BADGE_COLORS: Record<string, string> = {
  blue:   'bg-blue-500/20 text-blue-400 border-blue-500/30',
  indigo: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  green:  'bg-green-500/20 text-green-400 border-green-500/30',
};

function SectionFallback() {
  return (
    <div className="space-y-4 p-1">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="animate-pulse rounded-xl bg-white/5 h-24 w-full" />
      ))}
    </div>
  );
}

const BG_DEEP  = 'hsl(230 15% 5%)';
const BG_SIDE  = 'hsl(230 15% 7%)';
const BORDER   = 'hsl(230 15% 13%)';

export default function SecurityCenter() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sidebarOpen, setSidebarOpen]   = useState(false);
  const [refreshTick, setRefreshTick]   = useState(0);
  const { role } = usePermissions();

  const sectionParam = searchParams.get('section') as SecuritySection | null;
  const activeSection: SecuritySection =
    sectionParam && NAV_ITEMS.some(n => n.id === sectionParam)
      ? sectionParam
      : 'repositories'; // default: Repositories first

  const navigate = useCallback((section: SecuritySection) => {
    setSearchParams({ section });
    setSidebarOpen(false);
    window.scrollTo(0, 0);
  }, [setSearchParams]);

  const handleRefresh = useCallback(() => setRefreshTick(t => t + 1), []);

  const ActiveComponent = SECTION_COMPONENTS[activeSection];
  const activeNavItem   = NAV_ITEMS.find(n => n.id === activeSection);

  if (!canReadSecurity(role)) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-2">
          <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center mx-auto">
            <Shield className="w-7 h-7 text-red-400 opacity-60" />
          </div>
          <h2 className="text-base font-semibold text-foreground">Access Restricted</h2>
          <p className="text-sm text-muted-foreground max-w-xs">
            Your role does not have access to the Security Center.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-screen" style={{ background: BG_DEEP }}>
      {/* ── Top Header ───────────────────────────────────────────────── */}
      <SecurityTopBar
        activeLabel={activeNavItem?.label ?? 'Security Center'}
        onMobileMenuOpen={() => setSidebarOpen(true)}
        onRefresh={handleRefresh}
      />

      {/* ── Global KPI Row ───────────────────────────────────────────── */}
      <SecurityKPIBar onNavigate={navigate} />

      {/* ── Body: Sidebar + Content ──────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Mobile overlay */}
        <AnimatePresence>
          {sidebarOpen && (
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 z-30 bg-black/70 lg:hidden"
              onClick={() => setSidebarOpen(false)}
            />
          )}
        </AnimatePresence>

        {/* ── Sidebar ──────────────────────────────────────────────── */}
        <aside
          className={clsx(
            'fixed lg:static inset-y-0 left-0 z-40 lg:z-auto',
            'w-52 flex-shrink-0 flex flex-col border-r overflow-hidden transition-transform duration-200',
            sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
          )}
          style={{ background: BG_SIDE, borderColor: BORDER }}
        >
          {/* Sidebar header */}
          <div
            className="px-3 py-3 border-b flex items-center justify-between"
            style={{ borderColor: BORDER }}
          >
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-red-500/20 flex items-center justify-center">
                <Shield className="w-3.5 h-3.5 text-red-400" />
              </div>
              <span className="text-xs font-semibold text-foreground">Security Center</span>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Nav — grouped + scrollable */}
          <nav className="flex-1 overflow-y-auto py-2 px-1.5 space-y-0.5">
            {GROUPS.map(group => {
              const items = NAV_ITEMS.filter(n => n.group === group);
              if (!items.length) return null;
              return (
                <div key={group} className="mb-1">
                  <p className="px-2.5 py-1.5 text-[9px] font-bold text-muted-foreground/40 uppercase tracking-widest">
                    {group}
                  </p>
                  {items.map(item => {
                    const Icon   = item.icon;
                    const active = activeSection === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => navigate(item.id)}
                        title={item.description}
                        className={clsx(
                          'w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left transition-all',
                          active
                            ? 'bg-blue-600/20 text-blue-400 shadow-sm'
                            : 'text-muted-foreground hover:text-foreground hover:bg-white/5',
                        )}
                      >
                        <Icon className={clsx('w-3.5 h-3.5 flex-shrink-0', active ? 'text-blue-400' : '')} />
                        <span className="text-[11px] font-medium flex-1 truncate">{item.label}</span>
                        {item.badge && !active && (
                          <span className={clsx(
                            'text-[8px] font-bold px-1.5 py-0.5 rounded-full border',
                            BADGE_COLORS[item.badgeColor ?? 'indigo'],
                          )}>
                            {item.badge}
                          </span>
                        )}
                        {active && <ChevronRight className="w-3 h-3 flex-shrink-0 text-blue-400" />}
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </nav>

          {/* Role indicator */}
          <div className="px-3 py-2.5 border-t" style={{ borderColor: BORDER }}>
            <div
              className="px-2 py-1.5 rounded-lg text-center"
              style={{ background: 'hsl(230 15% 10%)', border: '1px solid hsl(230 15% 16%)' }}
            >
              <p className="text-[9px] text-muted-foreground/60 uppercase tracking-wide">Role</p>
              <p className="text-[11px] font-medium text-foreground capitalize">{role.replace(/_/g, ' ')}</p>
            </div>
          </div>
        </aside>

        {/* ── Main Content ─────────────────────────────────────────── */}
        <main className="flex-1 overflow-auto min-w-0">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeSection}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.12 }}
              className="h-full p-4 lg:p-5"
            >
              <Suspense fallback={<SectionFallback />}>
                <ActiveComponent key={`${activeSection}-${refreshTick}`} />
              </Suspense>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
