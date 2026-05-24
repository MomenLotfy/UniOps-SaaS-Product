import { useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Lock, CheckCircle } from 'lucide-react';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { authApi } from '@/services/api/auth';
import { ROUTES } from '@/lib/constants';
import { validatePassword } from '@/lib/validators';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';
  const [form, setForm] = useState({ password: '', confirm: '' });
  const [showPwd, setShowPwd] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validatePassword(form.password);
    if (err) { setError(err); return; }
    if (form.password !== form.confirm) { setError('Passwords do not match'); return; }
    setError('');
    setIsLoading(true);
    try {
      await authApi.resetPassword(token, form.password);
      setDone(true);
    } catch {
      setError('Invalid or expired reset link. Please request a new one.');
    } finally {
      setIsLoading(false);
    }
  };

  if (done) {
    return (
      <AuthLayout title="Password updated!" subtitle="">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto" style={{ background: 'hsl(160 84% 39% / 0.15)' }}>
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
          <p className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>Your password has been updated successfully.</p>
          <button onClick={() => navigate(ROUTES.LOGIN)}
            className="w-full py-2.5 rounded-lg font-semibold text-sm"
            style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
            Sign in with new password
          </button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Set new password" subtitle="Choose a strong password for your account">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>{error}</div>}
        {['password', 'confirm'].map((field) => (
          <div key={field}>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>
              {field === 'password' ? 'New password' : 'Confirm new password'}
            </label>
            <div className="relative">
              <input type={showPwd ? 'text' : 'password'} required
                value={form[field as keyof typeof form]}
                onChange={(e) => setForm((p) => ({ ...p, [field]: e.target.value }))}
                placeholder="••••••••"
                className="w-full px-3 py-2.5 pr-10 rounded-lg text-sm text-white border outline-none focus:ring-2 focus:ring-blue-500/50"
                style={inputStyle} />
              {field === 'password' && (
                <button type="button" onClick={() => setShowPwd((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: 'hsl(215 16% 47%)' }}>
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              )}
            </div>
          </div>
        ))}
        <button type="submit" disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm disabled:opacity-60"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Lock className="w-4 h-4" />}
          {isLoading ? 'Updating...' : 'Update password'}
        </button>
      </form>
    </AuthLayout>
  );
}
