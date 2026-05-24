import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, UserPlus, AlertCircle, CheckCircle } from 'lucide-react';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { useAuth } from '@/contexts/AuthContext';
import { ROUTES } from '@/lib/constants';
import { validatePassword } from '@/lib/validators';
import { clsx } from 'clsx';

export default function Register() {
  const { register, isAuthenticated, isLoading, error, clearError } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', password: '', confirmPassword: '' });
  const [showPwd, setShowPwd] = useState(false);
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [justRegistered, setJustRegistered] = useState(false);

  useEffect(() => {
    if (isAuthenticated && justRegistered) navigate('/onboarding', { replace: true });
    else if (isAuthenticated && !justRegistered) navigate(ROUTES.COMMAND, { replace: true });
  }, [isAuthenticated, justRegistered, navigate]);
  useEffect(() => () => clearError(), [clearError]);

  const pwdStrength = (() => {
    const p = form.password;
    let score = 0;
    if (p.length >= 8) score++;
    if (/[A-Z]/.test(p)) score++;
    if (/[0-9]/.test(p)) score++;
    if (/[@$!%*?&]/.test(p)) score++;
    return score;
  })();

  const strengthLabel = ['', 'Weak', 'Fair', 'Good', 'Strong'][pwdStrength];
  const strengthColor = ['', '#ef4444', '#f59e0b', '#3b82f6', '#10b981'][pwdStrength];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validatePassword(form.password);
    if (err) { setPwdError(err); return; }
    if (form.password !== form.confirmPassword) { setPwdError('Passwords do not match'); return; }
    setPwdError(null);
    setJustRegistered(true);
    await register({ firstName: form.firstName, lastName: form.lastName, email: form.email, password: form.password, confirmPassword: form.confirmPassword });
  };

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm text-white border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  return (
    <AuthLayout title="Create your account" subtitle="Start your 14-day free trial — no credit card required">
      <form onSubmit={handleSubmit} className="space-y-4">
        {(error || pwdError) && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error || pwdError}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          {[{ key: 'firstName', label: 'First name', placeholder: 'Alex' }, { key: 'lastName', label: 'Last name', placeholder: 'Johnson' }].map((f) => (
            <div key={f.key}>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>{f.label}</label>
              <input required value={form[f.key as keyof typeof form]} onChange={(e) => setForm((p) => ({ ...p, [f.key]: e.target.value }))}
                placeholder={f.placeholder} className={inputCls} style={inputStyle} />
            </div>
          ))}
        </div>

        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Work email</label>
          <input type="email" required value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
            placeholder="you@company.com" className={inputCls} style={inputStyle} />
        </div>

        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Password</label>
          <div className="relative">
            <input type={showPwd ? 'text' : 'password'} required value={form.password}
              onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
              placeholder="Min 8 chars, uppercase, number, symbol"
              className={clsx(inputCls, 'pr-10')} style={inputStyle} />
            <button type="button" onClick={() => setShowPwd((p) => !p)}
              className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: 'hsl(215 16% 47%)' }}>
              {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {form.password && (
            <div className="mt-2">
              <div className="flex gap-1 mb-1">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-1 flex-1 rounded-full transition-all"
                    style={{ background: i <= pwdStrength ? strengthColor : 'hsl(230 15% 14%)' }} />
                ))}
              </div>
              <span className="text-xs" style={{ color: strengthColor }}>{strengthLabel}</span>
            </div>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Confirm password</label>
          <input type="password" required value={form.confirmPassword}
            onChange={(e) => setForm((p) => ({ ...p, confirmPassword: e.target.value }))}
            placeholder="Repeat password" className={inputCls} style={inputStyle} />
        </div>

        <button type="submit" disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm transition-all disabled:opacity-60"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <UserPlus className="w-4 h-4" />}
          {isLoading ? 'Creating account...' : 'Create account'}
        </button>

        <p className="text-center text-xs" style={{ color: 'hsl(215 16% 47%)' }}>
          Already have an account?{' '}
          <Link to={ROUTES.LOGIN} className="text-blue-400 hover:text-blue-300 font-medium">Sign in</Link>
        </p>
        <p className="text-center text-xs" style={{ color: 'hsl(215 16% 37%)' }}>
          By creating an account you agree to our Terms of Service and Privacy Policy.
        </p>
      </form>
    </AuthLayout>
  );
}
