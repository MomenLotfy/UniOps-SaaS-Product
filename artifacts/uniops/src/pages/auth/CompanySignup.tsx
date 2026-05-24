import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { ROUTES, TOKEN_KEY, REFRESH_TOKEN_KEY, USER_KEY } from '@/lib/constants';
import { validateEmail, validateDomain, validateRequired } from '@/lib/validators';
import { useAuth } from '@/contexts/AuthContext';
import apiClient from '@/services/api/client';

type Step = 1 | 2 | 3;

export default function CompanySignup() {
  const navigate = useNavigate();
  const { updateUser } = useAuth();
  const [step, setStep] = useState<Step>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [form, setForm] = useState({
    companyName: '', domain: '', size: '',
    firstName: '', lastName: '', email: '', password: '',
    plan: 'professional',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm text-white border outline-none focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const validateStep = (s: Step) => {
    const errs: Record<string, string> = {};
    if (s === 1) {
      const n = validateRequired(form.companyName, 'Company name');
      const d = validateDomain(form.domain);
      if (n) errs.companyName = n;
      if (d) errs.domain = d;
      if (!form.size) errs.size = 'Select company size';
    }
    if (s === 2) {
      const fn = validateRequired(form.firstName, 'First name');
      const ln = validateRequired(form.lastName, 'Last name');
      const em = validateEmail(form.email);
      if (fn) errs.firstName = fn;
      if (ln) errs.lastName = ln;
      if (em) errs.email = em;
      if (!form.password || form.password.length < 8) errs.password = 'Min 8 characters';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleNext = () => {
    if (validateStep(step)) setStep((s) => (s + 1) as Step);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateStep(2)) return;
    setIsLoading(true);
    setApiError(null);
    try {
      const res = await apiClient.post<any>('/auth/login', {
        email: form.email,
        password: form.password,
        firstName: form.firstName,
        lastName: form.lastName,
        companyName: form.companyName,
      });
      const body = res.data?.data ?? res.data;
      const token = body?.access_token;
      const user  = body?.user ?? {};
      const fullName = `${form.firstName} ${form.lastName}`.trim();
      const updatedUser = {
        ...user,
        firstName: form.firstName || user.firstName,
        lastName:  form.lastName  || user.lastName,
        displayName: fullName || user.displayName || form.email,
      };
      if (token) localStorage.setItem(TOKEN_KEY, token);
      if (body?.refresh_token) localStorage.setItem(REFRESH_TOKEN_KEY, body.refresh_token);
      localStorage.setItem(USER_KEY, JSON.stringify(updatedUser));
      updateUser(updatedUser as any);
      setStep(3);
    } catch (err: any) {
      setApiError(err?.response?.data?.message ?? err.message ?? 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const sizes = ['1–10', '11–50', '51–200', '201–500', '500+'];
  const plans = [
    { id: 'starter', label: 'Starter', price: '$29/mo', desc: 'Up to 5 members' },
    { id: 'professional', label: 'Professional', price: '$99/mo', desc: 'Up to 25 members', popular: true },
    { id: 'enterprise', label: 'Enterprise', price: 'Custom', desc: 'Unlimited members' },
  ];

  if (step === 3) {
    return (
      <AuthLayout title="You're all set!" subtitle="">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto" style={{ background: 'hsl(160 84% 39% / 0.15)' }}>
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
          <p className="text-white font-semibold">Welcome to UniOps, {form.companyName}!</p>
          <p className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>Your workspace is ready. Let's connect your first integration.</p>
          <button onClick={() => navigate('/onboarding')}
            className="w-full py-2.5 rounded-lg font-semibold text-sm" style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
            Set up your workspace →
          </button>
          <button onClick={() => navigate(ROUTES.COMMAND)}
            className="w-full py-2.5 rounded-lg font-semibold text-sm border" style={{ borderColor: 'hsl(230 15% 14%)', color: 'hsl(215 16% 57%)', background: 'transparent' }}>
            Skip for now
          </button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Set up your company" subtitle={`Step ${step} of 2 — ${step === 1 ? 'Company details' : 'Your account'}`}>
      <div className="flex gap-2 mb-6">
        {[1, 2].map((s) => (
          <div key={s} className="h-1 flex-1 rounded-full transition-all"
            style={{ background: s <= step ? 'hsl(220 90% 60%)' : 'hsl(230 15% 14%)' }} />
        ))}
      </div>

      {apiError && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400 mb-4" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {apiError}
        </div>
      )}

      <form onSubmit={step === 2 ? handleSubmit : (e) => { e.preventDefault(); handleNext(); }} className="space-y-4">
        {step === 1 && (
          <>
            {[{ key: 'companyName', label: 'Company name', placeholder: 'Acme Corporation' },
              { key: 'domain', label: 'Company domain', placeholder: 'acmecorp.com' }].map((f) => (
              <div key={f.key}>
                <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>{f.label}</label>
                <input value={form[f.key as keyof typeof form]} onChange={(e) => setForm((p) => ({ ...p, [f.key]: e.target.value }))}
                  placeholder={f.placeholder} className={inputCls} style={inputStyle} />
                {errors[f.key] && <p className="text-xs text-red-400 mt-1">{errors[f.key]}</p>}
              </div>
            ))}
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Company size</label>
              <div className="grid grid-cols-5 gap-1">
                {sizes.map((s) => (
                  <button key={s} type="button" onClick={() => setForm((p) => ({ ...p, size: s }))}
                    className="py-2 rounded-lg text-xs font-medium transition-all border"
                    style={{ background: form.size === s ? 'hsl(220 90% 60%)' : 'hsl(230 18% 9%)', borderColor: form.size === s ? 'hsl(220 90% 60%)' : 'hsl(230 15% 14%)', color: form.size === s ? 'white' : 'hsl(215 16% 57%)' }}>
                    {s}
                  </button>
                ))}
              </div>
              {errors.size && <p className="text-xs text-red-400 mt-1">{errors.size}</p>}
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div className="grid grid-cols-2 gap-3">
              {[{ k: 'firstName', l: 'First name', pl: 'Alex' }, { k: 'lastName', l: 'Last name', pl: 'Johnson' }].map((f) => (
                <div key={f.k}>
                  <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>{f.l}</label>
                  <input value={form[f.k as keyof typeof form]} onChange={(e) => setForm((p) => ({ ...p, [f.k]: e.target.value }))}
                    placeholder={f.pl} className={inputCls} style={inputStyle} />
                </div>
              ))}
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Work email</label>
              <input type="email" value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
                placeholder={`admin@${form.domain || 'company.com'}`} className={inputCls} style={inputStyle} />
              {errors.email && <p className="text-xs text-red-400 mt-1">{errors.email}</p>}
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Password</label>
              <input type="password" value={form.password} onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
                placeholder="Min 8 characters" className={inputCls} style={inputStyle} />
              {errors.password && <p className="text-xs text-red-400 mt-1">{errors.password}</p>}
            </div>
            <div>
              <label className="block text-xs font-medium mb-2" style={{ color: 'hsl(215 16% 57%)' }}>Choose your plan</label>
              <div className="space-y-2">
                {plans.map((plan) => (
                  <button key={plan.id} type="button" onClick={() => setForm((p) => ({ ...p, plan: plan.id }))}
                    className="w-full flex items-center justify-between p-3 rounded-lg border transition-all"
                    style={{ background: form.plan === plan.id ? 'hsl(220 90% 60% / 0.1)' : 'hsl(230 18% 9%)', borderColor: form.plan === plan.id ? 'hsl(220 90% 60%)' : 'hsl(230 15% 14%)' }}>
                    <div className="text-left">
                      <div className="text-sm font-medium text-white flex items-center gap-2">
                        {plan.label}
                        {(plan as any).popular && <span className="text-xs px-1.5 py-0.5 rounded-full" style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>Popular</span>}
                      </div>
                      <div className="text-xs" style={{ color: 'hsl(215 16% 57%)' }}>{plan.desc}</div>
                    </div>
                    <div className="text-sm font-bold" style={{ color: form.plan === plan.id ? 'hsl(220 90% 70%)' : 'hsl(215 16% 57%)' }}>{plan.price}</div>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        <div className="flex gap-3 pt-2">
          {step > 1 && (
            <button type="button" onClick={() => setStep((s) => (s - 1) as Step)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm border transition-all"
              style={{ border: '1px solid hsl(230 15% 14%)', color: 'hsl(215 16% 57%)', background: 'transparent' }}>
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
          )}
          <button type="submit" disabled={isLoading}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm disabled:opacity-60"
            style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
            {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : null}
            {step === 2 ? (isLoading ? 'Creating workspace...' : 'Create workspace') : <><span>Continue</span> <ArrowRight className="w-4 h-4" /></>}
          </button>
        </div>

        <p className="text-center text-xs" style={{ color: 'hsl(215 16% 47%)' }}>
          Already have an account?{' '}
          <Link to={ROUTES.LOGIN} className="text-blue-400 hover:text-blue-300">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
