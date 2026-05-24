import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { authApi } from '@/services/api/auth';
import { ROUTES } from '@/lib/constants';

export default function TwoFactorAuth() {
  const navigate = useNavigate();
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  const handleChange = (i: number, val: string) => {
    if (!/^\d?$/.test(val)) return;
    const next = [...code];
    next[i] = val;
    setCode(next);
    if (val && i < 5) refs.current[i + 1]?.focus();
  };

  const handleKeyDown = (i: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !code[i] && i > 0) refs.current[i - 1]?.focus();
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    setCode(text.split('').concat(Array(6).fill('')).slice(0, 6));
    refs.current[Math.min(text.length, 5)]?.focus();
    e.preventDefault();
  };

  useEffect(() => { refs.current[0]?.focus(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const fullCode = code.join('');
    if (fullCode.length < 6) { setError('Enter the 6-digit code'); return; }
    setIsLoading(true);
    setError('');
    try {
      await authApi.verifyTwoFactor(fullCode);
      navigate(ROUTES.COMMAND, { replace: true });
    } catch {
      setError('Invalid code. Please try again.');
      setCode(['', '', '', '', '', '']);
      refs.current[0]?.focus();
    } finally {
      setIsLoading(false);
    }
  };

  const boxStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  return (
    <AuthLayout title="Two-factor authentication" subtitle="Enter the 6-digit code from your authenticator app">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="flex justify-center">
          <div className="w-14 h-14 rounded-xl flex items-center justify-center" style={{ background: 'hsl(220 90% 60% / 0.15)' }}>
            <ShieldCheck className="w-7 h-7 text-blue-400" />
          </div>
        </div>

        {error && <div className="p-3 rounded-lg text-sm text-red-400 text-center" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>{error}</div>}

        <div className="flex gap-2 justify-center" onPaste={handlePaste}>
          {code.map((digit, i) => (
            <input key={i} ref={(el) => { refs.current[i] = el; }}
              type="text" inputMode="numeric" maxLength={1} value={digit}
              onChange={(e) => handleChange(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              className="w-11 h-12 text-center text-lg font-bold rounded-lg border outline-none focus:ring-2 focus:ring-blue-500/50 text-white transition-all"
              style={boxStyle} />
          ))}
        </div>

        <button type="submit" disabled={isLoading || code.join('').length < 6}
          className="w-full py-2.5 rounded-lg font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          {isLoading && <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" />}
          {isLoading ? 'Verifying...' : 'Verify code'}
        </button>

        <p className="text-center text-xs" style={{ color: 'hsl(215 16% 47%)' }}>
          Lost access to your authenticator?{' '}
          <button type="button" className="text-blue-400 hover:text-blue-300">Use a backup code</button>
        </p>
      </form>
    </AuthLayout>
  );
}
