import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { CheckCircle, Activity, ArrowRight } from 'lucide-react';
import { ROUTES } from '@/lib/constants';

const PLANS = [
  {
    id: 'starter', name: 'Starter', price: 29, desc: 'For small teams getting started',
    features: ['Up to 5 members', '3 integrations', '10k API calls/mo', '7-day data retention', 'Email support', 'Basic dashboards'],
  },
  {
    id: 'professional', name: 'Professional', price: 99, desc: 'For growing engineering teams', popular: true,
    features: ['Up to 25 members', '15 integrations', '100k API calls/mo', '90-day data retention', 'Priority support', 'SSO (SAML)', 'Advanced analytics', 'ML Insights', 'Audit logs'],
  },
  {
    id: 'enterprise', name: 'Enterprise', price: null, desc: 'For large organizations with custom needs',
    features: ['Unlimited members', 'Unlimited integrations', 'Unlimited API calls', 'Custom data retention', 'Dedicated support', 'Custom SSO', 'SLA guarantee', 'On-premise option', 'Custom contracts'],
  },
];

export default function Pricing() {
  return (
    <div style={{ background: 'hsl(230 20% 4%)', color: 'hsl(213 31% 91%)', minHeight: '100vh', padding: '5rem 2rem' }}>
      <nav className="flex items-center justify-between max-w-6xl mx-auto mb-16">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, hsl(220 90% 55%), hsl(260 70% 60%))' }}>
            <Activity className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold">UniOps</span>
        </Link>
        <Link to={ROUTES.COMMAND} className="text-sm px-4 py-1.5 rounded-lg border" style={{ borderColor: 'hsl(230 15% 14%)', color: 'hsl(215 16% 77%)' }}>
          Sign in
        </Link>
      </nav>

      <div className="text-center max-w-2xl mx-auto mb-12">
        <h1 className="text-4xl font-bold mb-4">Simple, transparent pricing</h1>
        <p style={{ color: 'hsl(215 16% 57%)' }}>No hidden fees. Cancel anytime. All plans include a 14-day free trial.</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 max-w-5xl mx-auto">
        {PLANS.map((plan, i) => (
          <motion.div key={plan.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
            className="p-6 rounded-2xl border relative"
            style={{
              background: plan.popular ? 'hsl(220 90% 60% / 0.08)' : 'hsl(230 18% 7%)',
              borderColor: plan.popular ? 'hsl(220 90% 60%)' : 'hsl(230 15% 12%)',
            }}>
            {plan.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-semibold"
                style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>Most Popular</div>
            )}
            <div className="mb-6">
              <div className="text-lg font-bold">{plan.name}</div>
              <div className="text-sm mb-4" style={{ color: 'hsl(215 16% 57%)' }}>{plan.desc}</div>
              <div className="flex items-baseline gap-1">
                {plan.price ? (
                  <><span className="text-4xl font-bold">${plan.price}</span><span style={{ color: 'hsl(215 16% 57%)' }}>/mo</span></>
                ) : (
                  <span className="text-4xl font-bold">Custom</span>
                )}
              </div>
            </div>
            <div className="space-y-2.5 mb-8">
              {plan.features.map((f) => (
                <div key={f} className="flex items-center gap-2 text-sm">
                  <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                  {f}
                </div>
              ))}
            </div>
            <Link to={plan.id === 'enterprise' ? ROUTES.CONTACT : ROUTES.COMPANY_SIGNUP}
              className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg font-semibold text-sm"
              style={{ background: plan.popular ? 'hsl(220 90% 60%)' : 'transparent', color: plan.popular ? 'white' : 'hsl(220 90% 70%)', border: plan.popular ? 'none' : '1px solid hsl(220 90% 60% / 0.4)' }}>
              {plan.id === 'enterprise' ? 'Contact sales' : 'Start free trial'} <ArrowRight className="w-4 h-4" />
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
