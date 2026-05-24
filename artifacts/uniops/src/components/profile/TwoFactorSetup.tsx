import { useState } from 'react';
import { Shield, Smartphone, CheckCircle, Copy, Eye, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import apiClient from '@/services/api/client';

interface TwoFactorSetupProps {
  isEnabled: boolean;
  onEnable: (code: string) => Promise<void>;
  onDisable: (code: string) => Promise<void>;
}

export function TwoFactorSetup({ isEnabled, onEnable, onDisable }: TwoFactorSetupProps) {
  const [step, setStep]           = useState<'idle' | 'setup' | 'disable'>('idle');
  const [code, setCode]           = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied]       = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [setupData, setSetupData] = useState<{ secret: string; qr_code_url: string } | null>(null);
  const [setupLoading, setSetupLoading] = useState(false);
  const [setupError, setSetupError]     = useState('');

  const handleStartSetup = async () => {
    setSetupLoading(true);
    setSetupError('');
    try {
      const res = await apiClient.post<any>('/auth/2fa/setup', {});
      const data = res.data?.data;
      setSetupData({ secret: data?.secret ?? '', qr_code_url: data?.qr_code_url ?? '' });
      setStep('setup');
    } catch {
      setSetupError('Failed to start 2FA setup. Please try again.');
    } finally {
      setSetupLoading(false);
    }
  };

  const handleCopy = () => {
    if (setupData?.secret) navigator.clipboard.writeText(setupData.secret);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const qrImageUrl = setupData?.qr_code_url
    ? `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(setupData.qr_code_url)}`
    : null;

  const handleConfirm = async () => {
    setIsLoading(true);
    try {
      if (step === 'setup') await onEnable(code);
      else await onDisable(code);
      setStep('idle');
      setCode('');
      setSetupData(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-md space-y-4">
      <div className={clsx('flex items-center gap-4 p-4 rounded-xl', isEnabled ? 'bg-green-500/10 border border-green-500/20' : 'bg-muted/20 border border-border/50')}>
        <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', isEnabled ? 'bg-green-500/20' : 'bg-muted/30')}>
          <Shield className={clsx('w-5 h-5', isEnabled ? 'text-green-400' : 'text-muted-foreground')} />
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold text-foreground">Two-Factor Authentication</p>
          <p className={clsx('text-xs', isEnabled ? 'text-green-400' : 'text-muted-foreground')}>
            {isEnabled ? 'Enabled — your account is protected' : 'Not enabled — account at risk'}
          </p>
        </div>
        {isEnabled && <CheckCircle className="w-5 h-5 text-green-400" />}
      </div>

      {setupError && (
        <p className="text-xs text-red-400 px-1">{setupError}</p>
      )}

      {step === 'idle' && (
        <button
          onClick={isEnabled ? () => setStep('disable') : handleStartSetup}
          disabled={setupLoading}
          className={clsx('w-full py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-60', isEnabled
            ? 'text-red-400 hover:bg-red-500/10 border border-red-500/20'
            : 'text-white')}
          style={!isEnabled ? { background: 'hsl(220 90% 60%)' } : undefined}>
          {setupLoading && <Loader2 className="w-4 h-4 animate-spin" />}
          {isEnabled ? 'Disable 2FA' : setupLoading ? 'Setting up...' : 'Enable 2FA'}
        </button>
      )}

      {step === 'setup' && setupData && (
        <div className="space-y-4 p-4 rounded-xl border" style={{ borderColor: 'hsl(230 15% 14%)', background: 'hsl(230 18% 8%)' }}>
          <div className="flex items-center gap-2">
            <Smartphone className="w-4 h-4 text-blue-400" />
            <p className="text-sm font-medium text-foreground">Scan QR with your authenticator app</p>
          </div>
          {qrImageUrl && (
            <div className="flex justify-center">
              <img src={qrImageUrl} alt="2FA QR Code" className="w-40 h-40 rounded-lg" />
            </div>
          )}
          <div>
            <p className="text-xs text-muted-foreground mb-1.5">Or enter this key manually:</p>
            <div className="flex items-center gap-2">
              <code className={clsx('flex-1 px-3 py-2 rounded-lg text-xs font-mono text-blue-400', showSecret ? '' : 'blur-sm select-none')}
                style={{ background: 'hsl(230 18% 11%)', border: '1px solid hsl(230 15% 14%)' }}>
                {setupData.secret}
              </code>
              <button type="button" onClick={() => setShowSecret((p) => !p)}
                className="p-2 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground transition-colors">
                <Eye className="w-3.5 h-3.5" />
              </button>
              <button type="button" onClick={handleCopy}
                className="p-2 rounded-lg hover:bg-accent transition-colors"
                style={{ color: copied ? 'hsl(142 70% 55%)' : '' }}>
                <Copy className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1.5">Enter the 6-digit code from your app to verify:</p>
            <input type="text" inputMode="numeric" maxLength={6} placeholder="000000" value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              className="w-full px-3 py-2.5 rounded-lg text-sm text-center font-mono tracking-[0.4em] border outline-none focus:ring-2 focus:ring-blue-500/50"
              style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' }} />
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => { setStep('idle'); setCode(''); setSetupData(null); }}
              className="flex-1 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground border transition-colors"
              style={{ borderColor: 'hsl(230 15% 14%)' }}>Cancel</button>
            <button type="button" disabled={code.length !== 6 || isLoading} onClick={handleConfirm}
              className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60"
              style={{ background: 'hsl(220 90% 60%)' }}>
              {isLoading ? 'Verifying...' : 'Enable 2FA'}
            </button>
          </div>
        </div>
      )}

      {step === 'disable' && (
        <div className="space-y-4 p-4 rounded-xl border border-red-500/20" style={{ background: 'hsl(0 72% 51% / 0.05)' }}>
          <p className="text-sm text-red-400 font-medium">Enter your authenticator code to disable 2FA</p>
          <input type="text" inputMode="numeric" maxLength={6} placeholder="000000" value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            className="w-full px-3 py-2.5 rounded-lg text-sm text-center font-mono tracking-[0.4em] border outline-none focus:ring-2 focus:ring-red-500/50"
            style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(0 72% 51% / 0.3)', color: 'white' }} />
          <div className="flex gap-2">
            <button type="button" onClick={() => { setStep('idle'); setCode(''); }}
              className="flex-1 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground border transition-colors"
              style={{ borderColor: 'hsl(230 15% 14%)' }}>Cancel</button>
            <button type="button" disabled={code.length !== 6 || isLoading} onClick={handleConfirm}
              className="flex-1 py-2 rounded-lg text-sm font-semibold text-red-400 hover:bg-red-500/10 border border-red-500/30 disabled:opacity-60 transition-colors">
              {isLoading ? 'Disabling...' : 'Disable 2FA'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
