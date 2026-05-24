import { useState } from 'react';
import { Eye, EyeOff, UserPlus, AlertCircle, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';
import type { RegisterData } from '@/types/user';

interface RegisterFormProps {
  onSubmit: (data: RegisterData) => Promise<void>;
  isLoading: boolean;
  error?: string | null;
}

function PasswordStrength({ password }: { password: string }) {
  const checks = [
    { label: 'At least 8 characters', ok: password.length >= 8 },
    { label: 'Uppercase letter', ok: /[A-Z]/.test(password) },
    { label: 'Lowercase letter', ok: /[a-z]/.test(password) },
    { label: 'Number', ok: /\d/.test(password) },
    { label: 'Special character', ok: /[!@#$%^&*]/.test(password) },
  ];
  const score = checks.filter((c) => c.ok).length;
  const label = ['', 'Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'][score];
  const color = ['', 'bg-red-500', 'bg-orange-500', 'bg-yellow-500', 'bg-green-400', 'bg-emerald-400'][score];

  if (!password) return null;

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className={clsx('h-1 flex-1 rounded-full transition-all', i <= score ? color : 'bg-muted')} />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <div className="grid grid-cols-2 gap-1">
        {checks.map((c) => (
          <div key={c.label} className={clsx('flex items-center gap-1 text-xs', c.ok ? 'text-green-400' : 'text-muted-foreground')}>
            <CheckCircle className="w-3 h-3 flex-shrink-0" />
            {c.label}
          </div>
        ))}
      </div>
    </div>
  );
}

export function RegisterForm({ onSubmit, isLoading, error }: RegisterFormProps) {
  const [form, setForm] = useState<RegisterData>({ firstName: '', lastName: '', email: '', password: '', confirmPassword: '' });
  const [showPass, setShowPass] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;
  const labelCls = 'block text-xs font-medium mb-1.5 text-muted-foreground';

  const passwordMismatch = form.confirmPassword.length > 0 && form.password !== form.confirmPassword;

  return (
    <form onSubmit={async (e) => { e.preventDefault(); await onSubmit(form); }} className="space-y-4">
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
          style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

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
        <input type="email" required autoComplete="email" placeholder="you@company.com" value={form.email}
          onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
          className={inputCls} style={inputStyle} />
      </div>

      <div>
        <label className={labelCls}>Password</label>
        <div className="relative">
          <input type={showPass ? 'text' : 'password'} required minLength={8} placeholder="••••••••" value={form.password}
            onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
            className={clsx(inputCls, 'pr-10')} style={inputStyle} />
          <button type="button" onClick={() => setShowPass((p) => !p)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
            {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        <PasswordStrength password={form.password} />
      </div>

      <div>
        <label className={labelCls}>Confirm password</label>
        <div className="relative">
          <input type={showConfirm ? 'text' : 'password'} required placeholder="••••••••" value={form.confirmPassword}
            onChange={(e) => setForm((p) => ({ ...p, confirmPassword: e.target.value }))}
            className={clsx(inputCls, 'pr-10', passwordMismatch && 'ring-2 ring-red-500/50')} style={inputStyle} />
          <button type="button" onClick={() => setShowConfirm((p) => !p)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
            {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {passwordMismatch && <p className="mt-1 text-xs text-red-400">Passwords do not match</p>}
      </div>

      <button type="submit" disabled={isLoading || passwordMismatch}
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm transition-all disabled:opacity-60 disabled:cursor-not-allowed"
        style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
        {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <UserPlus className="w-4 h-4" />}
        {isLoading ? 'Creating account...' : 'Create account'}
      </button>
    </form>
  );
}
