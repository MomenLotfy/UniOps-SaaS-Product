import { useState } from 'react';
import { Eye, EyeOff, Lock, CheckCircle, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';

interface PasswordChangeFormProps {
  onSave: (currentPassword: string, newPassword: string) => Promise<void>;
}

export function PasswordChangeForm({ onSave }: PasswordChangeFormProps) {
  const [form, setForm] = useState({ current: '', new: '', confirm: '' });
  const [show, setShow] = useState({ current: false, new: false, confirm: false });
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const inputCls = 'w-full px-3 py-2.5 pr-10 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;
  const labelCls = 'block text-xs font-medium mb-1.5 text-muted-foreground';

  const passwordsMatch = form.new === form.confirm;
  const isStrong = form.new.length >= 8 && /[A-Z]/.test(form.new) && /\d/.test(form.new);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!passwordsMatch) { setErrorMsg('New passwords do not match'); return; }
    if (!isStrong) { setErrorMsg('Password must be at least 8 characters with uppercase and number'); return; }
    setIsLoading(true);
    setStatus('idle');
    setErrorMsg('');
    try {
      await onSave(form.current, form.new);
      setStatus('success');
      setForm({ current: '', new: '', confirm: '' });
      setTimeout(() => setStatus('idle'), 3000);
    } catch (err) {
      setStatus('error');
      setErrorMsg(err instanceof Error ? err.message : 'Failed to update password');
    } finally {
      setIsLoading(false);
    }
  };

  const PasswordField = ({ id, label, value, showKey }: { id: keyof typeof form; label: string; value: string; showKey: keyof typeof show }) => (
    <div>
      <label className={labelCls}>{label}</label>
      <div className="relative">
        <input
          type={show[showKey] ? 'text' : 'password'}
          value={value}
          required
          onChange={(e) => setForm((p) => ({ ...p, [id]: e.target.value }))}
          className={clsx(inputCls, id === 'confirm' && !passwordsMatch && value && 'ring-2 ring-red-500/50')}
          style={inputStyle}
          placeholder="••••••••"
        />
        <button type="button" onClick={() => setShow((p) => ({ ...p, [showKey]: !p[showKey] }))}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
          {show[showKey] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-md">
      <div className="flex items-center gap-3 mb-4 p-3 rounded-lg" style={{ background: 'hsl(220 90% 60% / 0.08)', border: '1px solid hsl(220 90% 60% / 0.15)' }}>
        <Lock className="w-4 h-4 text-blue-400 flex-shrink-0" />
        <p className="text-xs text-muted-foreground">Choose a strong password with at least 8 characters, an uppercase letter, and a number.</p>
      </div>

      {status === 'success' && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400"
          style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
          <CheckCircle className="w-4 h-4 flex-shrink-0" /> Password updated successfully
        </div>
      )}
      {(status === 'error' || errorMsg) && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
          style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> {errorMsg || 'Failed to update password'}
        </div>
      )}

      <PasswordField id="current" label="Current password" value={form.current} showKey="current" />
      <PasswordField id="new" label="New password" value={form.new} showKey="new" />
      <PasswordField id="confirm" label="Confirm new password" value={form.confirm} showKey="confirm" />

      <button type="submit" disabled={isLoading}
        className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-semibold text-sm disabled:opacity-60 disabled:cursor-not-allowed"
        style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
        {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Lock className="w-4 h-4" />}
        {isLoading ? 'Updating...' : 'Update password'}
      </button>
    </form>
  );
}
