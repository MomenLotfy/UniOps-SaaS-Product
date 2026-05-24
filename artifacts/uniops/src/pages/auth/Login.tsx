import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, LogIn, AlertCircle } from 'lucide-react';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { useAuth } from '@/contexts/AuthContext';
import { ROUTES } from '@/lib/constants';
import { clsx } from 'clsx';

export default function Login() {
  const { login, isAuthenticated, isLoading, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? ROUTES.COMMAND;

  const [form, setForm] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  useEffect(() => { if (isAuthenticated) navigate(from, { replace: true }); }, [isAuthenticated, navigate, from]);
  useEffect(() => { return () => clearError(); }, [clearError]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login({ email: form.email, password: form.password, rememberMe });
  };

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm text-white border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your UniOps account">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Email</label>
          <input
            type="email"
            required
            autoComplete="email"
            placeholder="you@company.com"
            value={form.email}
            onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
            className={inputCls}
            style={inputStyle}
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium" style={{ color: 'hsl(215 16% 57%)' }}>Password</label>
            <Link to={ROUTES.FORGOT_PASSWORD} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">Forgot password?</Link>
          </div>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              required
              autoComplete="current-password"
              placeholder="••••••••"
              value={form.password}
              onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
              className={clsx(inputCls, 'pr-10')}
              style={inputStyle}
            />
            <button type="button" onClick={() => setShowPassword((p) => !p)}
              className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
              style={{ color: 'hsl(215 16% 47%)' }}>
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input id="remember" type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)}
            className="w-4 h-4 rounded accent-blue-500" />
          <label htmlFor="remember" className="text-xs" style={{ color: 'hsl(215 16% 57%)' }}>Remember me for 30 days</label>
        </div>

        <button type="submit" disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <LogIn className="w-4 h-4" />}
          {isLoading ? 'Signing in...' : 'Sign in'}
        </button>

        <div className="pt-2 text-center text-xs" style={{ color: 'hsl(215 16% 47%)' }}>
          Don't have an account?{' '}
          <Link to={ROUTES.REGISTER} className="text-blue-400 hover:text-blue-300 font-medium">Create one</Link>
        </div>

        <div className="pt-1 text-center text-xs" style={{ color: 'hsl(215 16% 47%)' }}>
          Registering your company?{' '}
          <Link to={ROUTES.COMPANY_SIGNUP} className="text-blue-400 hover:text-blue-300 font-medium">Company signup</Link>
        </div>

        {/* Demo hint */}
        <div className="mt-4 p-3 rounded-lg text-xs" style={{ background: 'hsl(220 90% 60% / 0.08)', border: '1px solid hsl(220 90% 60% / 0.2)', color: 'hsl(220 90% 75%)' }}>
          <strong>Demo:</strong> admin@demo.com / demo123!
        </div>
      </form>
    </AuthLayout>
  );
}
