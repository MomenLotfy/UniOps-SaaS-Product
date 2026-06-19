import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Server, Shield, DollarSign, Brain,
  Settings, Activity, ChevronLeft, ChevronRight,
  Users, FileText, Zap, Building2, CreditCard,
  Key, Bell, Palette, LogOut, User, ShieldCheck,
} from 'lucide-react';
import { useStore } from '@/store';
import { useAuth } from '@/contexts/AuthContext';
import { usePermissions } from '@/hooks/use-permissions';
import { ROUTES } from '@/lib/constants';
import { initials } from '@/lib/formatters';
import { clsx } from 'clsx';
import { useState } from 'react';

interface NavSection {
  label?: string;
  items: {
    path: string;
    icon: React.ElementType;
    label: string;
    shortcut?: string;
    adminOnly?: boolean;
    roles?: string[];   // if set, only these roles can see the item
  }[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    label: 'Dashboards',
    items: [
      { path: ROUTES.COMMAND,  icon: LayoutDashboard, label: 'Command Center', shortcut: '⌘1' },
      { path: ROUTES.DEVOPS,   icon: Server,          label: 'DevOps',         shortcut: '⌘2', roles: ['super_admin','admin','devops'] },
      { path: ROUTES.SECURITY, icon: Shield,          label: 'SecOps',         shortcut: '⌘3', roles: ['super_admin','admin','security'] },
      { path: ROUTES.COST,     icon: DollarSign,      label: 'FinOps',         shortcut: '⌘4', roles: ['super_admin','admin','finops'] },
      { path: ROUTES.INSIGHTS, icon: Brain,           label: 'ML Insights',    shortcut: '⌘5', roles: ['super_admin','admin'] },
    ],
  },
  {
    label: 'Administration',
    items: [
      { path: ROUTES.COMPANY_DASHBOARD, icon: Building2,  label: 'Company Overview' },
      { path: ROUTES.ADMIN_USERS,       icon: Users,      label: 'User Management',   adminOnly: true },
      { path: ROUTES.ADMIN_ROLES,       icon: ShieldCheck,label: 'Roles',             adminOnly: true },
      { path: ROUTES.ADMIN_TEAMS,       icon: Users,      label: 'Teams',             adminOnly: true },
      { path: ROUTES.ADMIN_AUDIT,       icon: FileText,   label: 'Audit Logs',        roles: ['super_admin','admin','security'] },
      { path: ROUTES.ADMIN_POLICIES,    icon: Shield,     label: 'Security Policies', roles: ['super_admin','admin','security'] },
      { path: ROUTES.COMPANY_MEMBERS,   icon: Building2,  label: 'Team Members' },
      { path: ROUTES.COMPANY_USAGE,     icon: Zap,        label: 'Usage & Limits' },
    ],
  },
  {
    label: 'Settings',
    items: [
      { path: ROUTES.SETTINGS_PROFILE,       icon: User,        label: 'Profile' },
      { path: ROUTES.SETTINGS_ACCOUNT,       icon: Settings,    label: 'Account' },
      { path: ROUTES.SETTINGS_SECURITY,      icon: ShieldCheck, label: 'Security' },
      { path: ROUTES.SETTINGS_INTEGRATIONS,  icon: Zap,         label: 'Integrations',  roles: ['super_admin','admin','devops'] },
      { path: ROUTES.SETTINGS_API_KEYS,      icon: Key,         label: 'API Keys' },
      { path: ROUTES.SETTINGS_WEBHOOKS,      icon: Activity,    label: 'Webhooks',      roles: ['super_admin','admin'] },
      { path: ROUTES.SETTINGS_BILLING,       icon: CreditCard,  label: 'Billing',       roles: ['super_admin','admin','finops'] },
      { path: ROUTES.SETTINGS_NOTIFICATIONS, icon: Bell,        label: 'Notifications' },
      { path: ROUTES.SETTINGS_APPEARANCE,    icon: Palette,     label: 'Appearance' },
      { path: ROUTES.SETTINGS_TEAM,          icon: Users,       label: 'Team',          adminOnly: true },
    ],
  },
];

const NavItem = ({ path, icon: Icon, label, shortcut, isActive, collapsed }: {
  path: string; icon: React.ElementType; label: string; shortcut?: string; isActive: boolean; collapsed: boolean;
}) => (
  <NavLink
    to={path}
    title={collapsed ? label : undefined}
    className={clsx(
      'flex items-center rounded-lg transition-all duration-150 group relative overflow-hidden',
      collapsed ? 'justify-center p-2.5' : 'px-3 py-2',
      isActive ? 'text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-accent',
    )}
  >
    {isActive && (
      <motion.div layoutId="sidebar-active" className="absolute inset-0 rounded-lg"
        style={{ background: 'hsl(220 90% 60% / 0.15)' }} transition={{ duration: 0.2 }} />
    )}
    {isActive && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-r-full" style={{ background: 'hsl(var(--primary))' }} />}
    <Icon className={clsx('w-4 h-4 flex-shrink-0 relative z-10', isActive ? 'text-primary' : '')} />
    <AnimatePresence>
      {!collapsed && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}
          className="flex-1 flex items-center justify-between ml-2.5 min-w-0 relative z-10">
          <span className="text-xs font-medium truncate">{label}</span>
          {shortcut && <span className="text-xs ml-1 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground">{shortcut}</span>}
        </motion.div>
      )}
    </AnimatePresence>
  </NavLink>
);

// Thin wrapper — uses useLocation so active state is reactive to navigation
const NavItemWrapper = ({ item, collapsed }: { item: { path: string; icon: React.ElementType; label: string; shortcut?: string }; collapsed: boolean }) => {
  const { pathname } = useLocation();
  const isActive = pathname === item.path || pathname.startsWith(item.path + '/');
  return <NavItem path={item.path} icon={item.icon} label={item.label} shortcut={item.shortcut} isActive={isActive} collapsed={collapsed} />;
};

export const Sidebar = () => {
  const { sidebarCollapsed, toggleSidebar } = useStore();
  const { user, logout } = useAuth();
  const { isAdmin, hasRole, role } = usePermissions();
  const navigate = useNavigate();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleLogout = () => {
    logout();
    navigate(ROUTES.LOGIN);
  };

  return (
    <motion.aside
      initial={false}
      animate={{ width: sidebarCollapsed ? 64 : 224 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      className="fixed left-0 top-0 h-full flex flex-col z-50 border-r border-border overflow-hidden"
      style={{ background: 'hsl(230 18% 6% / 0.97)', backdropFilter: 'blur(16px)' }}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-3 border-b border-border flex-shrink-0">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0"
          style={{ background: 'linear-gradient(135deg, hsl(220 90% 55%), hsl(260 70% 60%))' }}>
          <Activity className="w-4 h-4 text-white" />
        </div>
        <AnimatePresence>
          {!sidebarCollapsed && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} className="ml-2.5 min-w-0">
              <div className="font-bold text-sm tracking-tight" style={{ background: 'linear-gradient(135deg, hsl(220 90% 70%), hsl(260 70% 70%))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>UniOps</div>
              <div className="text-xs text-muted-foreground" style={{ fontSize: 10 }}>Control Tower</div>
            </motion.div>
          )}
        </AnimatePresence>
        <button onClick={toggleSidebar}
          className={clsx('flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center transition-colors text-muted-foreground hover:text-foreground hover:bg-accent', sidebarCollapsed ? 'ml-auto' : 'ml-auto')}>
          {sidebarCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2 px-1.5 overflow-y-auto space-y-4 scrollbar-none">
        {NAV_SECTIONS.map((section) => {
          const visibleItems = section.items.filter((item) => {
            if (item.adminOnly && !isAdmin()) return false;
            if (item.roles && !item.roles.includes(role)) return false;
            return true;
          });
          if (visibleItems.length === 0) return null;
          return (
            <div key={section.label ?? 'main'}>
              <AnimatePresence>
                {!sidebarCollapsed && section.label && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="px-3 mb-1" style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', color: 'hsl(215 16% 37%)', textTransform: 'uppercase' }}>
                    {section.label}
                  </motion.div>
                )}
              </AnimatePresence>
              <div className="space-y-0.5">
                {visibleItems.map((item) => (
                  <NavItemWrapper key={item.path} item={item} collapsed={sidebarCollapsed} />
                ))}
              </div>
            </div>
          );
        })}
      </nav>

      {/* User footer */}
      <div className="p-1.5 border-t border-border flex-shrink-0">
        <div className="relative">
          <button onClick={() => setShowUserMenu((p) => !p)}
            className={clsx('w-full flex items-center gap-2.5 rounded-lg p-2 transition-colors hover:bg-accent text-left', sidebarCollapsed && 'justify-center')}>
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
              style={{ background: 'hsl(220 90% 60% / 0.25)', color: 'hsl(220 90% 75%)' }}>
              {user ? initials(user.displayName) : 'U'}
            </div>
            <AnimatePresence>
              {!sidebarCollapsed && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-foreground truncate">{user?.displayName ?? 'User'}</div>
                  <div className="text-xs truncate" style={{ color: 'hsl(215 16% 47%)', fontSize: 10 }}>{user?.email ?? ''}</div>
                </motion.div>
              )}
            </AnimatePresence>
          </button>

          {showUserMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
              <div className="absolute bottom-full mb-2 left-0 w-44 rounded-xl border border-border shadow-xl overflow-hidden z-50"
                style={{ background: 'hsl(230 18% 10%)' }}>
                <button
                  onClick={() => { navigate(ROUTES.SETTINGS_PROFILE); setShowUserMenu(false); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-foreground hover:bg-accent transition-colors text-left"
                >
                  <User className="w-3.5 h-3.5" />Profile
                </button>
                <button
                  onClick={() => { navigate(ROUTES.SETTINGS_SECURITY); setShowUserMenu(false); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-foreground hover:bg-accent transition-colors text-left"
                >
                  <Settings className="w-3.5 h-3.5" />Settings
                </button>
                <div className="border-t border-border" />
                <button onClick={handleLogout} className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors">
                  <LogOut className="w-3.5 h-3.5" />Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </motion.aside>
  );
};
