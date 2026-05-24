import { Zap, Users, Plug, Activity, ArrowUpRight, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { PLAN_LABELS, PLAN_LIMITS } from '@/lib/constants';
import type { Company } from '@/types/company';

interface SubscriptionPlanProps {
  company: Company;
  onUpgrade?: () => void;
}

const PLAN_COLORS: Record<string, { badge: string; bg: string }> = {
  starter: { badge: 'text-slate-400', bg: 'bg-slate-500/10' },
  professional: { badge: 'text-blue-400', bg: 'bg-blue-500/10' },
  enterprise: { badge: 'text-purple-400', bg: 'bg-purple-500/10' },
};

export function SubscriptionPlan({ company, onUpgrade }: SubscriptionPlanProps) {
  const planKey = company.plan as keyof typeof PLAN_LIMITS;
  const limits = PLAN_LIMITS[planKey];
  const planColor = PLAN_COLORS[company.plan] ?? PLAN_COLORS.starter;

  const usage = {
    members: { used: company.memberCount, limit: company.maxMembers },
    integrations: { used: 7, limit: limits.integrations },
    apiCalls: { used: 42_850, limit: limits.apiCalls },
  };

  const usageItems = [
    { icon: Users, label: 'Team members', used: usage.members.used, limit: usage.members.limit, format: (n: number) => n.toString() },
    { icon: Plug, label: 'Integrations', used: usage.integrations.used, limit: usage.integrations.limit, format: (n: number) => n.toString() },
    { icon: Activity, label: 'API calls/month', used: usage.apiCalls.used, limit: usage.apiCalls.limit, format: (n: number) => n.toLocaleString() },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between p-5 rounded-xl border"
        style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
        <div className="flex items-center gap-4">
          <div className={clsx('w-12 h-12 rounded-xl flex items-center justify-center', planColor.bg)}>
            <Zap className={clsx('w-6 h-6', planColor.badge)} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-foreground">{PLAN_LABELS[company.plan]} Plan</h3>
              <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', planColor.badge, planColor.bg)}>Current</span>
            </div>
            <p className="text-sm text-muted-foreground capitalize">Billing {company.billingCycle} · Renews next month</p>
            <div className="flex items-center gap-1.5 mt-1.5">
              <CheckCircle className="w-3.5 h-3.5 text-green-400" />
              <span className="text-xs text-green-400">Active subscription</span>
            </div>
          </div>
        </div>
        {company.plan !== 'enterprise' && (
          <button onClick={onUpgrade}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{ background: 'hsl(220 90% 60% / 0.15)', color: 'hsl(220 90% 70%)' }}>
            Upgrade <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Usage</h4>
        <div className="space-y-3">
          {usageItems.map((item) => {
            const pct = Math.min((item.used / item.limit) * 100, 100);
            const isWarning = pct >= 80;
            const isCritical = pct >= 95;
            return (
              <div key={item.label} className="p-3 rounded-xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <item.icon className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm text-foreground">{item.label}</span>
                  </div>
                  <span className={clsx('text-xs font-medium', isCritical ? 'text-red-400' : isWarning ? 'text-yellow-400' : 'text-muted-foreground')}>
                    {item.format(item.used)} / {limits.members === 999 ? '∞' : item.format(item.limit)}
                  </span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden bg-muted/30">
                  <div
                    className={clsx('h-full rounded-full transition-all', isCritical ? 'bg-red-500' : isWarning ? 'bg-yellow-400' : 'bg-blue-500')}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
