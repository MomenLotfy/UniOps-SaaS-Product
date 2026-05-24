import { useState } from 'react';
import { X, ExternalLink, Copy, CheckCircle, AlertCircle, Loader } from 'lucide-react';
import { clsx } from 'clsx';

interface AWSCloudFormationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnect: (config: { roleArn: string; externalId: string; region: string }) => Promise<void>;
}

const CF_TEMPLATE_URL = 'https://console.aws.amazon.com/cloudformation/home#/stacks/create/template?templateURL=https://uniops-cf-templates.s3.amazonaws.com/uniops-role.yaml';
const EXTERNAL_ID = 'uniops-ext-' + Math.random().toString(36).slice(2, 10);
const AWS_REGIONS = ['us-east-1', 'us-west-2', 'eu-west-1', 'eu-central-1', 'ap-southeast-1', 'ap-northeast-1', 'me-south-1'];

export function AWSCloudFormationModal({ isOpen, onClose, onConnect }: AWSCloudFormationModalProps) {
  const [step, setStep] = useState(1);
  const [roleArn, setRoleArn] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(EXTERNAL_ID);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleConnect = async () => {
    if (!roleArn.startsWith('arn:aws:iam::')) {
      setError('Invalid IAM Role ARN format');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      await onConnect({ roleArn, externalId: EXTERNAL_ID, region });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setIsLoading(false);
    }
  };

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg rounded-2xl border shadow-2xl"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' }}>
        <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <div className="flex items-center gap-3">
            <span className="text-2xl">🟠</span>
            <div>
              <h2 className="text-sm font-semibold text-foreground">Connect AWS</h2>
              <p className="text-xs text-muted-foreground">Via IAM Role (CloudFormation)</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div className="flex items-center gap-2">
            {[1, 2, 3].map((s) => (
              <div key={s} className="flex items-center gap-2">
                <div className={clsx('w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold',
                  s === step ? 'bg-blue-500 text-white' : s < step ? 'bg-green-500 text-white' : 'bg-muted text-muted-foreground')}>
                  {s < step ? '✓' : s}
                </div>
                {s < 3 && <div className={clsx('h-0.5 w-8', s < step ? 'bg-green-500' : 'bg-muted')} />}
              </div>
            ))}
            <span className="ml-2 text-xs text-muted-foreground">{['Launch Stack', 'Note External ID', 'Enter Role ARN'][step - 1]}</span>
          </div>

          {step === 1 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">Launch the CloudFormation stack in your AWS account to create an IAM role with read-only access.</p>
              <a href={CF_TEMPLATE_URL} target="_blank" rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg font-semibold text-sm"
                style={{ background: 'hsl(25 100% 55%)', color: 'white' }}>
                Launch CloudFormation Stack <ExternalLink className="w-4 h-4" />
              </a>
              <button onClick={() => setStep(2)} className="w-full py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground border transition-colors"
                style={{ borderColor: 'hsl(230 15% 14%)' }}>
                Already launched → Continue
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">When prompted by CloudFormation, enter this External ID in the stack parameters:</p>
              <div className="flex items-center gap-2 p-3 rounded-lg" style={{ background: 'hsl(230 18% 11%)', border: '1px solid hsl(230 15% 14%)' }}>
                <code className="flex-1 text-sm font-mono text-blue-300">{EXTERNAL_ID}</code>
                <button onClick={handleCopy} className={clsx('p-1.5 rounded transition-colors', copied ? 'text-green-400' : 'text-muted-foreground hover:text-foreground')}>
                  {copied ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setStep(1)} className="flex-1 py-2.5 rounded-lg text-sm text-muted-foreground hover:text-foreground border transition-colors"
                  style={{ borderColor: 'hsl(230 15% 14%)' }}>Back</button>
                <button onClick={() => setStep(3)} className="flex-1 py-2.5 rounded-lg text-sm font-semibold text-white"
                  style={{ background: 'hsl(220 90% 60%)' }}>Continue</button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
                  style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
                </div>
              )}
              <div>
                <label className="block text-xs font-medium mb-1.5 text-muted-foreground">IAM Role ARN</label>
                <input type="text" placeholder="arn:aws:iam::123456789012:role/UniOpsRole" value={roleArn}
                  onChange={(e) => setRoleArn(e.target.value)} className={inputCls} style={inputStyle} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Primary Region</label>
                <select value={region} onChange={(e) => setRegion(e.target.value)} className={inputCls} style={inputStyle}>
                  {AWS_REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setStep(2)} className="flex-1 py-2.5 rounded-lg text-sm text-muted-foreground hover:text-foreground border transition-colors"
                  style={{ borderColor: 'hsl(230 15% 14%)' }}>Back</button>
                <button onClick={handleConnect} disabled={isLoading || !roleArn}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-60"
                  style={{ background: 'hsl(220 90% 60%)' }}>
                  {isLoading ? <Loader className="w-4 h-4 animate-spin" /> : null}
                  {isLoading ? 'Connecting...' : 'Connect AWS'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
