import { useState } from 'react';
import { Building2, AlertCircle, ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';

interface CompanySignupData {
  companyName: string;
  companySlug: string;
  domain: string;
  plan: 'starter' | 'professional' | 'enterprise';
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  agreeToTerms: boolean;
}

interface CompanySignupFormProps {
  onSubmit: (data: CompanySignupData) => Promise<void>;
  isLoading: boolean;
  error?: string | null;
}

const PLANS = [
  { id: 'starter' as const, name: 'Starter', price: '$49/mo', features: ['5 members', '3 integrations', '10K API calls'] },
  { id: 'professional' as const, name: 'Professional', price: '$149/mo', features: ['25 members', '15 integrations', '100K API calls'], popular: true },
  { id: 'enterprise' as const, name: 'Enterprise', price: 'Custom', features: ['Unlimited members', 'All integrations', 'Unlimited API calls'] },
];

export function CompanySignupForm({ onSubmit, isLoading, error }: CompanySignupFormProps) {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<CompanySignupData>({
    companyName: '', companySlug: '', domain: '',
    plan: 'professional',
    firstName: '', lastName: '', email: '', password: '',
    agreeToTerms: false,
  });

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;
  const labelCls = 'block text-xs font-medium mb-1.5 text-muted-foreground';

  const slugify = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  return (
    <form onSubmit={async (e) => { e.preventDefault(); if (step < 3) { setStep(s => s + 1); } else { await onSubmit(form); } }} className="space-y-5">
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
          style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      <div className="flex items-center gap-2 mb-2">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div className={clsx('w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold',
              s === step ? 'bg-blue-500 text-white' : s < step ? 'bg-green-500 text-white' : 'bg-muted text-muted-foreground')}>
              {s < step ? '✓' : s}
            </div>
            {s < 3 && <div className={clsx('h-0.5 w-8', s < step ? 'bg-green-500' : 'bg-muted')} />}
          </div>
        ))}
        <span className="ml-2 text-xs text-muted-foreground">
          {['Company Info', 'Choose Plan', 'Admin Account'][step - 1]}
        </span>
      </div>

      {step === 1 && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 p-4 rounded-xl mb-2" style={{ background: 'hsl(220 90% 60% / 0.1)', border: '1px solid hsl(220 90% 60% / 0.2)' }}>
            <Building2 className="w-6 h-6 text-blue-400 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-foreground">Set up your company workspace</p>
              <p className="text-xs text-muted-foreground">This will be your team's UniOps environment</p>
            </div>
          </div>
          <div>
            <label className={labelCls}>Company name</label>
            <input type="text" required placeholder="Acme Corporation" value={form.companyName}
              onChange={(e) => setForm((p) => ({ ...p, companyName: e.target.value, companySlug: slugify(e.target.value) }))}
              className={inputCls} style={inputStyle} />
          </div>
          <div>
            <label className={labelCls}>Workspace slug</label>
            <div className="flex items-center gap-0">
              <span className="px-3 py-2.5 text-sm rounded-l-lg text-muted-foreground" style={{ background: 'hsl(230 15% 12%)', border: '1px solid hsl(230 15% 14%)', borderRight: 'none' }}>
                app.uniops.io/
              </span>
              <input type="text" required placeholder="acme-corp" value={form.companySlug}
                onChange={(e) => setForm((p) => ({ ...p, companySlug: slugify(e.target.value) }))}
                className={clsx(inputCls, 'rounded-l-none')} style={inputStyle} />
            </div>
          </div>
          <div>
            <label className={labelCls}>Company domain</label>
            <input type="text" placeholder="acmecorp.com" value={form.domain}
              onChange={(e) => setForm((p) => ({ ...p, domain: e.target.value }))}
              className={inputCls} style={inputStyle} />
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-3">
          {PLANS.map((plan) => (
            <label key={plan.id} className={clsx('flex items-start gap-3 p-4 rounded-xl cursor-pointer transition-all',
              form.plan === plan.id ? 'ring-2 ring-blue-500' : 'hover:border-border/60')}
              style={{ background: form.plan === plan.id ? 'hsl(220 90% 60% / 0.1)' : 'hsl(230 15% 8%)', border: `1px solid ${form.plan === plan.id ? 'transparent' : 'hsl(230 15% 14%)'}` }}>
              <input type="radio" name="plan" value={plan.id} checked={form.plan === plan.id}
                onChange={() => setForm((p) => ({ ...p, plan: plan.id }))} className="mt-0.5 accent-blue-500" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-foreground">{plan.name}</span>
                  {plan.popular && <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: 'hsl(220 90% 60% / 0.2)', color: 'hsl(220 90% 70%)' }}>Popular</span>}
                </div>
                <div className="text-lg font-bold text-blue-400 mt-0.5">{plan.price}</div>
                <ul className="mt-1.5 space-y-0.5">
                  {plan.features.map((f) => (
                    <li key={f} className="text-xs text-muted-foreground flex items-center gap-1">
                      <span className="text-green-400">✓</span> {f}
                    </li>
                  ))}
                </ul>
              </div>
            </label>
          ))}
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>First name</label>
              <input type="text" required placeholder="John" value={form.firstName}
                onChange={(e) => setForm((p) => ({ ...p, firstName: e.target.value }))}
                className={inputCls} style={inputStyle} />
            </div>
            <div>
              <label className={labelCls}>Last name</label>
              <input type="text" required placeholder="Doe" value={form.lastName}
                onChange={(e) => setForm((p) => ({ ...p, lastName: e.target.value }))}
                className={inputCls} style={inputStyle} />
            </div>
          </div>
          <div>
            <label className={labelCls}>Work email</label>
            <input type="email" required placeholder="admin@company.com" value={form.email}
              onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
              className={inputCls} style={inputStyle} />
          </div>
          <div>
            <label className={labelCls}>Password</label>
            <input type="password" required minLength={8} placeholder="Min 8 characters" value={form.password}
              onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
              className={inputCls} style={inputStyle} />
          </div>
          <div className="flex items-start gap-2">
            <input id="terms" type="checkbox" required checked={form.agreeToTerms}
              onChange={(e) => setForm((p) => ({ ...p, agreeToTerms: e.target.checked }))}
              className="w-4 h-4 mt-0.5 rounded accent-blue-500" />
            <label htmlFor="terms" className="text-xs text-muted-foreground">
              I agree to the{' '}
              <a href="#" className="text-blue-400 hover:underline">Terms of Service</a> and{' '}
              <a href="#" className="text-blue-400 hover:underline">Privacy Policy</a>
            </label>
          </div>
        </div>
      )}

      <button type="submit" disabled={isLoading}
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm transition-all disabled:opacity-60 disabled:cursor-not-allowed"
        style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
        {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <ChevronRight className="w-4 h-4" />}
        {isLoading ? 'Creating workspace...' : step < 3 ? 'Continue' : 'Create workspace'}
      </button>
    </form>
  );
}
