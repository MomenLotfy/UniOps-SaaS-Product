import { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, AlertCircle, ExternalLink } from 'lucide-react';
import { clsx } from 'clsx';
import { integrationsApi } from '@/services/api/integrations';

export default function GitLabIntegration() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ baseUrl: 'https://gitlab.com', personalToken: '', groupId: '' });
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [error, setError] = useState('');

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;
  const labelCls = 'block text-xs font-medium mb-1.5 text-muted-foreground';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setStatus('idle');
    try {
      await integrationsApi.connectGitLab(form.personalToken);
      setStatus('success');
      setTimeout(() => navigate(-1), 2000);
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="max-w-xl space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="action-btn"><ArrowLeft className="w-4 h-4" /> Back</button>
      </div>

      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl" style={{ background: 'hsl(230 15% 12%)', border: '1px solid hsl(230 15% 16%)' }}>🟠</div>
        <div>
          <h1 className="text-xl font-bold text-foreground">GitLab Integration</h1>
          <p className="text-sm text-muted-foreground">Connect your GitLab instance to monitor CI/CD pipelines</p>
        </div>
      </div>

      <div className="card-base space-y-2">
        {[{ icon: CheckCircle, text: 'Monitor pipeline runs and job status' }, { icon: CheckCircle, text: 'View MR approvals and deployment events' }, { icon: CheckCircle, text: 'Receive real-time build failure alerts' }].map((item) => (
          <div key={item.text} className="flex items-center gap-2.5 text-sm text-muted-foreground">
            <item.icon className="w-4 h-4 text-green-400 flex-shrink-0" />{item.text}
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="card-base space-y-4">
        {status === 'success' && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400" style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
            <CheckCircle className="w-4 h-4 flex-shrink-0" /> GitLab connected successfully!
          </div>
        )}
        {status === 'error' && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
            <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
          </div>
        )}
        <div>
          <label className={labelCls}>GitLab URL</label>
          <input type="url" required value={form.baseUrl} onChange={(e) => setForm((p) => ({ ...p, baseUrl: e.target.value }))} className={inputCls} style={inputStyle} />
          <p className="text-xs text-muted-foreground mt-1">For self-hosted GitLab, enter your instance URL</p>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className={clsx(labelCls, 'mb-0')}>Personal Access Token</label>
            <a href="https://gitlab.com/-/profile/personal_access_tokens" target="_blank" rel="noreferrer" className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              Create token <ExternalLink className="w-3 h-3" />
            </a>
          </div>
          <input type="password" required placeholder="glpat-xxxxxxxxxxxxxxxxxxxx" value={form.personalToken}
            onChange={(e) => setForm((p) => ({ ...p, personalToken: e.target.value }))} className={inputCls} style={inputStyle} />
          <p className="text-xs text-muted-foreground mt-1">Required scopes: <code className="text-blue-400">read_api</code>, <code className="text-blue-400">read_repository</code></p>
        </div>
        <div>
          <label className={labelCls}>Group ID (optional)</label>
          <input type="text" placeholder="12345678" value={form.groupId} onChange={(e) => setForm((p) => ({ ...p, groupId: e.target.value }))} className={inputCls} style={inputStyle} />
        </div>
        <button type="submit" disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm text-white disabled:opacity-60"
          style={{ background: 'hsl(220 90% 60%)' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : null}
          {isLoading ? 'Connecting...' : 'Connect GitLab'}
        </button>
      </form>
    </motion.div>
  );
}
