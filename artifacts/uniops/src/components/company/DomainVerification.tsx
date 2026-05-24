import { useState } from 'react';
import { Globe, Copy, CheckCircle, XCircle, RefreshCw, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';

interface DomainVerificationProps {
  domain: string;
  isVerified: boolean;
  onVerify: () => Promise<void>;
}

const DNS_RECORD = {
  type: 'TXT',
  name: '_uniops-verify',
  value: 'uniops-verify=abcd1234efgh5678ijkl',
  ttl: '300',
};

export function DomainVerification({ domain, isVerified, onVerify }: DomainVerificationProps) {
  const [isChecking, setIsChecking] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [lastCheck, setLastCheck] = useState<'success' | 'failed' | null>(null);

  const handleCopy = (key: string, value: string) => {
    navigator.clipboard.writeText(value);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleVerify = async () => {
    setIsChecking(true);
    try {
      await onVerify();
      setLastCheck('success');
    } catch {
      setLastCheck('failed');
    } finally {
      setIsChecking(false);
    }
  };

  return (
    <div className="space-y-4 max-w-xl">
      <div className={clsx('flex items-center gap-4 p-4 rounded-xl border', isVerified ? 'border-green-500/20 bg-green-500/5' : 'border-yellow-500/20 bg-yellow-500/5')}>
        <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', isVerified ? 'bg-green-500/20' : 'bg-yellow-500/20')}>
          <Globe className={clsx('w-5 h-5', isVerified ? 'text-green-400' : 'text-yellow-400')} />
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold text-foreground">{domain}</p>
          <p className={clsx('text-xs font-medium', isVerified ? 'text-green-400' : 'text-yellow-400')}>
            {isVerified ? '✓ Verified' : '⚠ Pending verification'}
          </p>
        </div>
        {isVerified && <CheckCircle className="w-5 h-5 text-green-400" />}
      </div>

      {!isVerified && (
        <>
          <div className="p-4 rounded-xl border space-y-3" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
            <p className="text-sm font-medium text-foreground">Add this DNS record to verify ownership</p>
            <div className="space-y-2">
              {(Object.entries(DNS_RECORD) as [string, string][]).map(([key, value]) => (
                <div key={key} className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-10 flex-shrink-0 capitalize font-medium">{key}</span>
                  <code className="flex-1 px-2 py-1.5 rounded text-xs font-mono text-blue-300 overflow-x-auto"
                    style={{ background: 'hsl(230 18% 11%)', border: '1px solid hsl(230 15% 14%)' }}>
                    {value}
                  </code>
                  <button onClick={() => handleCopy(key, value)}
                    className={clsx('p-1.5 rounded transition-colors flex-shrink-0', copied === key ? 'text-green-400' : 'text-muted-foreground hover:text-foreground')}>
                    {copied === key ? <CheckCircle className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {lastCheck === 'failed' && (
            <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
              style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
              <XCircle className="w-4 h-4 flex-shrink-0" />
              Verification failed — DNS record not found yet. DNS changes can take up to 48 hours.
            </div>
          )}

          <div className="flex items-center gap-3">
            <button onClick={handleVerify} disabled={isChecking}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold disabled:opacity-60 transition-all"
              style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
              {isChecking ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              {isChecking ? 'Checking...' : 'Verify domain'}
            </button>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <AlertCircle className="w-3.5 h-3.5" />
              DNS propagation may take up to 48 hours
            </div>
          </div>
        </>
      )}
    </div>
  );
}
