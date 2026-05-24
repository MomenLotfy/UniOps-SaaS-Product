// artifacts/uniops/src/pages/company/Dashboard.tsx
import { motion } from 'framer-motion';
import { Building2, Users, Zap, Activity, TrendingUp, Settings } from 'lucide-react';
import { useCompany } from '@/contexts/CompanyContext';
import { useApi } from '@/hooks/use-api';
import { clsx } from 'clsx';
import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/constants';

export default function CompanyDashboard() {
  const { company, usage, isLoading } = useCompany();
  const { data: stats } = useApi<any>('/companies/stats');

  if (isLoading || !company) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-8 h-8 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
        <span className="ml-3 text-gray-400">جاري تحميل بيانات الشركة...</span>
      </div>
    );
  }

  const statCards = [
    { label: 'Active Members', value: stats?.active_users ?? usage?.users?.used ?? 0, icon: Users, color: 'text-blue-400', bg: 'bg-blue-500/10', link: ROUTES.ADMIN_USERS },
    { label: 'Integrations', value: stats?.active_integrations ?? usage?.integrations?.used ?? 0, icon: Zap, color: 'text-green-400', bg: 'bg-green-500/10', link: ROUTES.SETTINGS_INTEGRATIONS },
    { label: 'Active Threats', value: stats?.active_threats ?? 0, icon: Activity, color: 'text-red-400', bg: 'bg-red-500/10', link: ROUTES.SECURITY },
    { label: 'Running Pipelines', value: stats?.running_pipelines ?? 0, icon: TrendingUp, color: 'text-purple-400', bg: 'bg-purple-500/10', link: ROUTES.DEVOPS },
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Company Overview</h1>
          <p className="page-subtitle">{company?.name ?? 'My Company'} — {company?.plan ?? 'Active'} plan</p>
        </div>
        <Link to={ROUTES.SETTINGS_ACCOUNT} className="action-btn">
          <Settings className="w-4 h-4" />Company Settings
        </Link>
      </div>

      {/* Identity card */}
      <div className="card-base mb-5">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-xl flex items-center justify-center text-2xl font-bold flex-shrink-0"
            style={{ background: 'hsl(220 90% 60% / 0.15)', color: 'hsl(220 90% 70%)' }}>
            {(company?.name ?? 'U').charAt(0).toUpperCase()}
          </div>
          <div className="flex-1">
            <div className="text-lg font-bold text-foreground">{company?.name ?? 'My Company'}</div>
            <div className="text-sm text-muted-foreground">{company?.domain || 'No domain configured'}</div>
            <div className="flex items-center gap-3 mt-1">
              <span className="badge-medium capitalize">{company?.plan ?? 'free'} plan</span>
              <span className={clsx('text-xs font-medium', company?.status === 'active' ? 'text-green-400' : 'text-yellow-400')}>
                {company?.status === 'active' ? '● Active' : '● Inactive'}
              </span>
              {company?.domainVerified && <span className="text-xs text-green-400">✓ Domain verified</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        {statCards.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
            <Link to={s.link} className="card-base flex items-center gap-4 hover:border-border/80 transition-colors block">
              <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0', s.bg)}>
                <s.icon className={clsx('w-5 h-5', s.color)} />
              </div>
              <div>
                <div className="stat-value text-xl">{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Usage */}
      {usage && (
        <div className="card-base">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-foreground">Plan Usage</h2>
            <Link to={ROUTES.SETTINGS_BILLING} className="text-xs text-blue-400 hover:text-blue-300">Manage plan →</Link>
          </div>
          <div className="space-y-4">
            {[
              { label: 'Team Members', used: usage?.users?.used ?? 0, limit: usage?.users?.limit ?? 1 },
              { label: 'Integrations', used: usage?.integrations?.used ?? 0, limit: usage?.integrations?.limit ?? 1 },
              { label: 'API Calls this month', used: usage?.apiCalls?.used ?? 0, limit: usage?.apiCalls?.limit ?? 1 },
            ].map(u => {
              const pct = Math.min((u.used / u.limit) * 100, 100);
              return (
                <div key={u.label}>
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-muted-foreground">{u.label}</span>
                    <span className="text-foreground font-medium">{u.used.toLocaleString()} / {u.limit.toLocaleString()}</span>
                  </div>
                  <div className="progress-bar-base">
                    <div className="h-full rounded-full transition-all"
                      style={{ width: `${pct}%`, background: pct > 90 ? '#ef4444' : pct > 70 ? '#f59e0b' : '#10b981' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );
}
