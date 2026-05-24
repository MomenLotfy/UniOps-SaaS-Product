import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { CheckCircle, XCircle, Mail } from 'lucide-react';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { authApi } from '@/services/api/auth';
import { ROUTES } from '@/lib/constants';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');
  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying');

  useEffect(() => {
    if (!token) { setStatus('error'); return; }
    authApi.verifyEmail(token)
      .then(() => setStatus('success'))
      .catch(() => setStatus('error'));
  }, [token]);

  return (
    <AuthLayout title="Email Verification" subtitle="">
      <div className="text-center space-y-4">
        {status === 'verifying' && (
          <>
            <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto" style={{ background: 'hsl(220 90% 60% / 0.15)' }}>
              <div className="w-8 h-8 rounded-full border-2 border-blue-500/20 border-t-blue-500 animate-spin" />
            </div>
            <p className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>Verifying your email address...</p>
          </>
        )}
        {status === 'success' && (
          <>
            <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto" style={{ background: 'hsl(160 84% 39% / 0.15)' }}>
              <CheckCircle className="w-8 h-8 text-green-400" />
            </div>
            <p className="font-semibold text-white">Email verified!</p>
            <p className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>Your email has been verified. You can now access all features.</p>
            <button onClick={() => navigate(ROUTES.COMMAND)}
              className="w-full py-2.5 rounded-lg font-semibold text-sm" style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
              Go to dashboard
            </button>
          </>
        )}
        {status === 'error' && (
          <>
            <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto" style={{ background: 'hsl(0 72% 51% / 0.15)' }}>
              <XCircle className="w-8 h-8 text-red-400" />
            </div>
            <p className="font-semibold text-white">Verification failed</p>
            <p className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>The link is invalid or expired. Request a new verification email.</p>
            <button onClick={() => navigate(ROUTES.LOGIN)}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm"
              style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
              <Mail className="w-4 h-4" /> Back to sign in
            </button>
          </>
        )}
      </div>
    </AuthLayout>
  );
}
