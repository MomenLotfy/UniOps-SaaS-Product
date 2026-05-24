import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, ArrowLeft, CheckCircle } from 'lucide-react';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { authApi } from '@/services/api/auth';
import { ROUTES } from '@/lib/constants';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    try {
      await authApi.requestPasswordReset(email);
      setSent(true);
    } catch {
      setError('Failed to send reset email. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (sent) {
    return (
      <AuthLayout title="Check your email" subtitle="">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto" style={{ background: 'hsl(160 84% 39% / 0.15)' }}>
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
          <p className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>
            We sent a password reset link to <span className="text-white font-medium">{email}</span>.
            Check your inbox and follow the link to reset your password.
          </p>
          <p className="text-xs" style={{ color: 'hsl(215 16% 37%)' }}>Didn't receive it? Check your spam folder or try again.</p>
          <button onClick={() => setSent(false)} className="text-sm text-blue-400 hover:text-blue-300">Try a different email</button>
          <div className="pt-2">
            <Link to={ROUTES.LOGIN} className="flex items-center justify-center gap-2 text-sm" style={{ color: 'hsl(215 16% 57%)' }}>
              <ArrowLeft className="w-4 h-4" /> Back to sign in
            </Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Reset your password" subtitle="Enter your email and we'll send you a reset link">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>{error}</div>
        )}
        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Email address</label>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="w-full px-3 py-2.5 rounded-lg text-sm text-white border outline-none focus:ring-2 focus:ring-blue-500/50"
            style={inputStyle} />
        </div>
        <button type="submit" disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm disabled:opacity-60"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Mail className="w-4 h-4" />}
          {isLoading ? 'Sending...' : 'Send reset link'}
        </button>
        <Link to={ROUTES.LOGIN} className="flex items-center justify-center gap-2 text-sm pt-2" style={{ color: 'hsl(215 16% 57%)' }}>
          <ArrowLeft className="w-4 h-4" /> Back to sign in
        </Link>
      </form>
    </AuthLayout>
  );
}
