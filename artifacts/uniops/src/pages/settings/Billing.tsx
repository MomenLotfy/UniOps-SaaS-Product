import { useState } from 'react';
import { motion } from 'framer-motion';
import { CreditCard, Download, TrendingUp, Users, Zap, CheckCircle, ExternalLink, AlertTriangle } from 'lucide-react';
import { useCompany } from '@/contexts/CompanyContext';
import { formatCurrency } from '@/lib/formatters';
import { useApi, apiPost } from '@/hooks/use-api';
import { clsx } from 'clsx';

const PLANS = [
  {
    id: 'starter',
    name: 'Starter',
    price: 49,
    seats: 10,
    integrations: 5,
    features: ['10 team members', '5 integrations', '100k API calls/mo', 'DevOps + Security + Cost', 'Email support'],
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
  },
  {
    id: 'professional',
    name: 'Professional',
    price: 149,
    seats: 25,
    integrations: 15,
    features: ['25 team members', '15 integrations', '500k API calls/mo', 'All dashboards + ML Insights', 'SSO + Priority support'],
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
    popular: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: null,
    seats: -1,
    integrations: -1,
    features: ['Unlimited members', 'Unlimited integrations', 'Unlimited API calls', 'Custom SLA + SLO', '24/7 dedicated support'],
    color: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/20',
  },
];

export default function Billing() {
  const { company, usage, refetch: refetchCompany, isLoading } = useCompany() as any;
  const { data: subData, refetch: refetchSub } = useApi<any>('/billing/subscription');
  const { data: invoices, loading: invLoading } = useApi<any>('/billing/invoices?page_size=6');

  const [checkingOut, setCheckingOut] = useState<string | null>(null);
  const [openingPortal, setOpeningPortal] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [error, setError] = useState('');

  // ✅ إصلاح الشاشة السوداء: عرض مؤشر تحميل
  if (isLoading || !company) {
    return (
      <div className="flex items-center justify-center min-h-[400px] gap-3">
        <div className="w-8 h-8 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
        <span className="text-gray-400">جاري تحميل بيانات الفوترة...</span>
      </div>
    );
  }

  const invoiceList = invoices ?? [];
  const currentPlan = company?.plan ?? 'free';
  const subscription = subData;

  const handleCheckout = async (planId: string) => {
    setCheckingOut(planId);
    setError('');
    try {
      const result = await apiPost<any>('/billing/checkout', {
        plan: planId,
        success_url: `${window.location.origin}/settings/billing?success=1`,
        cancel_url:  `${window.location.origin}/settings/billing?canceled=1`,
      });
      if (result?.checkout_url) {
        window.location.href = result.checkout_url;
      }
    } catch (err: any) {
      setError(err.message ?? 'Checkout failed. Make sure STRIPE_SECRET_KEY is configured.');
    } finally {
      setCheckingOut(null);
    }
  };

  const handlePortal = async () => {
    setOpeningPortal(true);
    setError('');
    try {
      const result = await apiPost<any>('/billing/portal', {
        return_url: window.location.href,
      });
      if (result?.portal_url) {
        window.location.href = result.portal_url;
      }
    } catch (err: any) {
      setError(err.message ?? 'Could not open billing portal');
    } finally {
      setOpeningPortal(false);
    }
  };

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel your subscription? It will remain active until the end of the billing period.')) return;
    setCanceling(true);
    try {
      await apiPost('/billing/cancel?at_period_end=true', {});
      refetchSub();
      refetchCompany?.();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCanceling(false);
    }
  };

  // Check URL params for success/cancel
  const urlParams = new URLSearchParams(window.location.search);
  const checkoutSuccess  = urlParams.get('success') === '1';
  const checkoutCanceled = urlParams.get('canceled') === '1';

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      <div className="page-header">
        <div><h1 className="page-title">Billing & Subscription</h1><p className="page-subtitle">Manage your plan, payment, and invoices</p></div>
        {subscription?.stripe_customer_id && (
          <button onClick={handlePortal} disabled={openingPortal} className="action-btn">
            <ExternalLink className="w-4 h-4" />
            {openingPortal ? 'Opening...' : 'Manage Billing'}
          </button>
        )}
      </div>

      {/* Notifications */}
      {checkoutSuccess && (
        <div className="flex items-center gap-2 p-4 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
          <CheckCircle className="w-5 h-5 flex-shrink-0" />
          Subscription activated successfully! Your plan has been upgraded.
        </div>
      )}
      {checkoutCanceled && (
        <div className="flex items-center gap-2 p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-sm">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          Checkout was canceled. Your plan was not changed.
        </div>
      )}
      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>
      )}

      {/* Current plan card */}
      {company && (
        <div className="card-base">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                <Zap className="w-6 h-6 text-primary" />
              </div>
              <div>
                <div className="text-lg font-bold text-foreground capitalize">{currentPlan} Plan</div>
                <div className="text-sm text-muted-foreground">
                  {subscription?.status === 'active' ? (
                    subscription.cancel_at_period_end
                      ? `Cancels ${subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : 'end of period'}`
                      : `Renews ${subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : ''}`
                  ) : currentPlan === 'free' ? 'Free tier — no payment required' : 'No active subscription'}
                </div>
              </div>
            </div>
            <div className="text-right">
              {currentPlan !== 'free' && (
                <div className="text-2xl font-bold text-foreground">
                  {formatCurrency(PLANS.find(p => p.id === currentPlan)?.price ?? 0)}<span className="text-sm text-muted-foreground">/mo</span>
                </div>
              )}
              {subscription?.stripe_subscription_id && !subscription.cancel_at_period_end && (
                <button onClick={handleCancel} disabled={canceling}
                  className="text-xs text-red-400 hover:text-red-300 mt-1">
                  {canceling ? 'Canceling...' : 'Cancel subscription'}
                </button>
              )}
            </div>
          </div>

          {/* Usage meters */}
          {usage && (
            <div className="grid grid-cols-3 gap-4 mt-5 pt-4 border-t border-border">
              {[
                { label: 'Team Members', icon: Users,       used: usage?.users?.used ?? 0,        limit: usage?.users?.limit ?? 1 },
                { label: 'Integrations', icon: Zap,         used: usage?.integrations?.used ?? 0, limit: usage?.integrations?.limit ?? 1 },
                { label: 'API Calls',    icon: TrendingUp,  used: usage?.apiCalls?.used ?? 0,     limit: usage?.apiCalls?.limit ?? 1 },
              ].map(u => {
                const pct = Math.min((u.used / u.limit) * 100, 100);
                return (
                  <div key={u.label}>
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="text-muted-foreground">{u.label}</span>
                      <span className="text-foreground font-medium">{u.used.toLocaleString()} / {u.limit === -1 ? '∞' : u.limit.toLocaleString()}</span>
                    </div>
                    {u.limit !== -1 && (
                      <div className="progress-bar-base">
                        <div className="h-full rounded-full transition-all"
                          style={{ width: `${pct}%`, background: pct > 90 ? '#ef4444' : pct > 70 ? '#f59e0b' : '#10b981' }} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Pricing plans */}
      <div>
        <h2 className="text-sm font-semibold text-foreground mb-3">
          {currentPlan === 'free' ? 'Choose a Plan' : 'Upgrade or Change Plan'}
        </h2>
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          {PLANS.map(plan => {
            const isCurrentPlan = currentPlan === plan.id;
            return (
              <motion.div key={plan.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className={clsx('card-base relative', plan.popular && 'border-purple-500/30')}>
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="text-xs px-3 py-1 rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/30 font-medium">
                      Most Popular
                    </span>
                  </div>
                )}
                <div className="flex items-center gap-2 mb-3">
                  <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', plan.bg)}>
                    <Zap className={clsx('w-4 h-4', plan.color)} />
                  </div>
                  <div className="font-semibold text-foreground">{plan.name}</div>
                </div>
                <div className="mb-4">
                  {plan.price !== null ? (
                    <div className="text-2xl font-bold text-foreground">
                      {formatCurrency(plan.price)}<span className="text-sm text-muted-foreground font-normal">/mo</span>
                    </div>
                  ) : (
                    <div className="text-2xl font-bold text-foreground">Custom</div>
                  )}
                </div>
                <ul className="space-y-2 mb-5">
                  {plan.features.map(f => (
                    <li key={f} className="flex items-center gap-2 text-xs text-muted-foreground">
                      <CheckCircle className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />{f}
                    </li>
                  ))}
                </ul>
                {isCurrentPlan ? (
                  <div className="w-full py-2 text-center text-xs rounded-lg bg-surface-1 text-muted-foreground border border-border">
                    Current Plan
                  </div>
                ) : plan.id === 'enterprise' ? (
                  <a href="mailto:sales@uniops.io"
                    className="block w-full py-2 text-center text-xs rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20 hover:bg-orange-500/20 transition-colors">
                    Contact Sales →
                  </a>
                ) : (
                  <button onClick={() => handleCheckout(plan.id)} disabled={checkingOut === plan.id}
                    className={clsx('w-full py-2 text-xs rounded-lg transition-colors',
                      plan.popular
                        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30 hover:bg-purple-500/30'
                        : 'bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20'
                    )}>
                    {checkingOut === plan.id ? 'Redirecting...' : `Upgrade to ${plan.name} →`}
                  </button>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Invoices */}
      <div className="card-base">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-foreground">Billing History</h2>
          {subscription?.stripe_customer_id && (
            <button onClick={handlePortal} disabled={openingPortal} className="action-btn text-xs">
              <Download className="w-3.5 h-3.5" />View all invoices
            </button>
          )}
        </div>
        {invLoading ? (
          <p className="text-sm text-muted-foreground">Loading invoices...</p>
        ) : invoiceList.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No invoices yet. Invoices appear here after your first payment.
          </p>
        ) : (
          <table className="data-table">
            <thead><tr><th>Invoice</th><th>Period</th><th>Amount</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {invoiceList.map((inv: any) => (
                <tr key={inv.id}>
                  <td><code className="text-xs font-mono text-blue-400">{inv.number}</code></td>
                  <td><span className="text-xs text-muted-foreground">{inv.period}</span></td>
                  <td><span className="text-sm font-medium text-foreground">{formatCurrency((inv.amount ?? 0) / 100)}</span></td>
                  <td><span className="text-xs font-medium text-green-400">{inv.status}</span></td>
                  <td>
                    {inv.pdf_url && (
                      <a href={inv.pdf_url} target="_blank" rel="noopener noreferrer"
                        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                        <Download className="w-3 h-3" />PDF
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </motion.div>
  );
}
