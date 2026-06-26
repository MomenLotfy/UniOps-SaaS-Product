import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, AlertTriangle, Bug, CheckSquare, GitBranch,
  Server, TrendingUp, FileText, ClipboardList, BookOpen,
  ChevronRight, Menu, X, Layers, Package, Users, Clock, Ticket,
} from 'lucide-react';
import { clsx } from 'clsx';
import { usePermissions } from '@/hooks/use-permissions';
import { canReadSecurity } from '@/lib/permissions';

import Overview             from './sections/Overview';
import Threats              from './sections/Threats';
import Vulnerabilities      from './sections/Vulnerabilities';
import Compliance           from './sections/Compliance';
import Repositories         from './sections/Repositories';
import Assets               from './sections/Assets';
import SecurityPosture      from './sections/SecurityPosture';
import Policies             from './sections/Policies';
import Exceptions           from './sections/Exceptions';
import Reports              from './sections/Reports';
import KubernetesSecurity   from './sections/KubernetesSecurity';
import SBOMSection          from './sections/SBOM';
import Ownership            from './sections/Ownership';
import SLATracker           from './sections/SLATracker';

export type SecuritySection =
  | 'overview' | 'threats' | 'vulnerabilities' | 'compliance'
  | 'repositories' | 'assets' | 'kubernetes' | 'posture'
  | 'policies' | 'exceptions' | 'reports' | 'sbom'
  | 'ownership' | 'sla';

interface NavItem {
  id: SecuritySection;
  label: string;
  icon: React.ElementType;
  description: string;
  badge?: string;
  group?: string;
}

const NAV_ITEMS: NavItem[] = [
  // ── Core
  { id: 'overview',        label: 'Overview',            icon: Shield,        description: 'Security dashboard',           group: 'Core' },
  { id: 'threats',         label: 'Threats',             icon: AlertTriangle, description: 'Active security threats',       group: 'Core' },
  { id: 'vulnerabilities', label: 'Vulnerabilities',     icon: Bug,           description: 'CVEs and findings',             group: 'Core' },
  { id: 'compliance',      label: 'Compliance',          icon: CheckSquare,   description: 'Framework compliance',          group: 'Core' },
  // ── Infrastructure
  { id: 'repositories',    label: 'Repositories',        icon: GitBranch,     description: 'Repo scanning & risk',          group: 'Infrastructure' },
  { id: 'assets',          label: 'Assets',              icon: Server,        description: 'Asset inventory',               group: 'Infrastructure' },
  { id: 'kubernetes',      label: 'Kubernetes',          icon: Layers,        description: 'K8s cluster scanning',          group: 'Infrastructure', badge: 'NEW' },
  // ── Governance
  { id: 'posture',         label: 'Security Posture',    icon: TrendingUp,    description: 'Posture score & trends',        group: 'Governance' },
  { id: 'ownership',       label: 'Ownership',           icon: Users,         description: 'Owner / team / department',     group: 'Governance', badge: 'NEW' },
  { id: 'sla',             label: 'SLA Tracker',         icon: Clock,         description: 'Remediation SLA deadlines',     group: 'Governance', badge: 'NEW' },
  { id: 'policies',        label: 'Policies',            icon: BookOpen,      description: 'Security policies',             group: 'Governance' },
  { id: 'exceptions',      label: 'Exceptions',          icon: ClipboardList, description: 'Exception requests',            group: 'Governance' },
  // ── Reports
  { id: 'reports',         label: 'Reports',             icon: FileText,      description: 'Audit & reports',               group: 'Reports' },
  { id: 'sbom',            label: 'SBOM',                icon: Package,       description: 'Software Bill of Materials',    group: 'Reports' },
];

const SECTION_COMPONENTS: Record<SecuritySection, React.ComponentType> = {
  overview:        Overview,
  threats:         Threats,
  vulnerabilities: Vulnerabilities,
  compliance:      Compliance,
  repositories:    Repositories,
  assets:          Assets,
  kubernetes:      KubernetesSecurity,
  posture:         SecurityPosture,
  ownership:       Ownership,
  sla:             SLATracker,
  policies:        Policies,
  exceptions:      Exceptions,
  reports:         Reports,
  sbom:            SBOMSection,
};

const GROUPS = ['Core', 'Infrastructure', 'Governance', 'Reports'];

export default function SecurityCenter() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sidebarOpen, setSidebarOpen]   = useState(false);
  const { role } = usePermissions();

  const sectionParam = searchParams.get('section') as SecuritySection | null;
  const activeSection: SecuritySection =
    sectionParam && NAV_ITEMS.some(n => n.id === sectionParam)
      ? sectionParam
      : 'overview';

  const navigate = (section: SecuritySection) => {
    setSearchParams({ section });
    setSidebarOpen(false);
    window.scrollTo(0, 0);
  };

  const ActiveComponent = SECTION_COMPONENTS[activeSection];

  if (!canReadSecurity(role)) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center">
          <Shield className="w-12 h-12 text-red-400 mx-auto mb-3 opacity-50" />
          <h2 className="text-base font-semibold text-foreground mb-1">Access Restricted</h2>
          <p className="text-sm text-muted-foreground">Your role does not have access to the Security Center.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-screen" style={{ background: 'hsl(230 15% 6%)' }}>
      {/* ── Mobile overlay ───────────────────────────────────────────── */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-30 bg-black/60 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* ── Sidebar ──────────────────────────────────────────────────── */}
      <aside className={clsx(
        'fixed lg:static inset-y-0 left-0 z-40 lg:z-auto',
        'w-56 flex-shrink-0 flex flex-col border-r transition-transform duration-200',
        'bg-surface-1',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
      )} style={{ borderColor: 'hsl(230 15% 14%)' }}>

        {/* Header */}
        <div className="px-4 py-4 border-b flex items-center justify-between" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-red-500/15 flex items-center justify-center">
              <Shield className="w-4 h-4 text-red-400" />
            </div>
            <div>
              <p className="text-xs font-semibold text-foreground">Security Center</p>
              <p className="text-[10px] text-muted-foreground">DevSecOps Platform</p>
            </div>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Nav — grouped */}
        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-3">
          {GROUPS.map(group => {
            const items = NAV_ITEMS.filter(n => n.group === group);
            return (
              <div key={group}>
                <p className="px-3 py-1 text-[9px] font-bold text-muted-foreground/50 uppercase tracking-widest">
                  {group}
                </p>
                {items.map(item => {
                  const Icon   = item.icon;
                  const active = activeSection === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => navigate(item.id)}
                      className={clsx(
                        'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-all mb-0.5',
                        active
                          ? 'bg-blue-600/20 text-blue-400 border border-blue-500/20'
                          : 'text-muted-foreground hover:text-foreground hover:bg-white/5 border border-transparent',
                      )}
                    >
                      <Icon className={clsx('w-4 h-4 flex-shrink-0', active ? 'text-blue-400' : 'text-muted-foreground')} />
                      <span className="text-xs font-medium flex-1">{item.label}</span>
                      {item.badge && !active && (
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                          {item.badge}
                        </span>
                      )}
                      {active && <ChevronRight className="w-3 h-3 ml-auto text-blue-400" />}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* Role badge */}
        <div className="px-4 py-3 border-t" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <div className="px-2 py-1.5 rounded-md bg-white/5 border border-white/10 text-center">
            <p className="text-[10px] text-muted-foreground">Logged in as</p>
            <p className="text-xs font-medium text-foreground capitalize">{role.replace(/_/g, ' ')}</p>
          </div>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <button onClick={() => setSidebarOpen(true)} className="text-muted-foreground hover:text-foreground">
            <Menu className="w-5 h-5" />
          </button>
          <span className="text-sm font-medium text-foreground">
            {NAV_ITEMS.find(n => n.id === activeSection)?.label ?? 'Security Center'}
          </span>
        </div>

        <main className="flex-1 overflow-auto p-4 lg:p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeSection}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.15 }}
            >
              <ActiveComponent />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
