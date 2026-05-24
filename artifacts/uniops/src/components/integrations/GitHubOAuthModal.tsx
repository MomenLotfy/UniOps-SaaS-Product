import { useState } from 'react';
import { X, Github, CheckCircle, AlertCircle, ExternalLink } from 'lucide-react';
import { clsx } from 'clsx';

interface GitHubOAuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnect: (code: string) => Promise<void>;
}

const GITHUB_SCOPES = ['repo', 'workflow', 'read:org', 'read:user'];
const OAUTH_URL = `https://github.com/login/oauth/authorize?client_id=GITHUB_CLIENT_ID&scope=${GITHUB_SCOPES.join(',')}&state=uniops_oauth`;

export function GitHubOAuthModal({ isOpen, onClose, onConnect }: GitHubOAuthModalProps) {
  const [step, setStep] = useState<'intro' | 'waiting' | 'manual'>('intro');
  const [manualCode, setManualCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleOAuth = () => {
    window.open(OAUTH_URL, 'github_oauth', 'width=600,height=700,scrollbars=yes');
    setStep('waiting');
  };

  const handleManualConnect = async () => {
    if (!manualCode.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      await onConnect(manualCode);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-2xl border shadow-2xl"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' }}>
        <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-white/5">
              <Github className="w-5 h-5 text-foreground" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">Connect GitHub</h2>
              <p className="text-xs text-muted-foreground">OAuth 2.0 Authorization</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {step === 'intro' && (
            <>
              <p className="text-sm text-muted-foreground">UniOps will request the following permissions from GitHub:</p>
              <div className="space-y-2">
                {[
                  { scope: 'repo', desc: 'Read repository metadata and status' },
                  { scope: 'workflow', desc: 'View GitHub Actions workflow runs' },
                  { scope: 'read:org', desc: 'Read organization membership' },
                  { scope: 'read:user', desc: 'Read basic user profile' },
                ].map((item) => (
                  <div key={item.scope} className="flex items-center gap-3 p-2.5 rounded-lg"
                    style={{ background: 'hsl(230 18% 11%)', border: '1px solid hsl(230 15% 14%)' }}>
                    <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                    <div>
                      <code className="text-xs font-mono text-blue-300">{item.scope}</code>
                      <p className="text-xs text-muted-foreground">{item.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={handleOAuth}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm text-white"
                style={{ background: 'hsl(230 10% 15%)', border: '1px solid hsl(230 15% 25%)' }}>
                <Github className="w-4 h-4" /> Authorize with GitHub <ExternalLink className="w-3.5 h-3.5 opacity-50" />
              </button>
            </>
          )}

          {step === 'waiting' && (
            <div className="space-y-4">
              <div className="text-center py-4">
                <div className="w-12 h-12 rounded-full border-2 border-blue-500/20 border-t-blue-500 animate-spin mx-auto mb-3" />
                <p className="text-sm text-foreground font-medium">Waiting for authorization...</p>
                <p className="text-xs text-muted-foreground mt-1">Complete the GitHub OAuth flow in the popup window</p>
              </div>
              <button onClick={() => setStep('manual')} className="w-full text-xs text-blue-400 hover:text-blue-300 text-center transition-colors">
                Popup not working? Enter code manually →
              </button>
            </div>
          )}

          {step === 'manual' && (
            <div className="space-y-4">
              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
                  style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
                </div>
              )}
              <div>
                <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Authorization code from GitHub</label>
                <input type="text" placeholder="Paste the code from the callback URL" value={manualCode}
                  onChange={(e) => setManualCode(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/50"
                  style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' }} />
              </div>
              <div className="flex gap-2">
                <button onClick={() => setStep('intro')} className="flex-1 py-2.5 rounded-lg text-sm text-muted-foreground border transition-colors"
                  style={{ borderColor: 'hsl(230 15% 14%)' }}>Back</button>
                <button onClick={handleManualConnect} disabled={isLoading || !manualCode.trim()}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-60"
                  style={{ background: 'hsl(220 90% 60%)' }}>
                  {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : null}
                  Connect GitHub
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
