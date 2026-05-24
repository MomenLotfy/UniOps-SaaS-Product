import { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, AlertCircle, ExternalLink } from 'lucide-react';
import { integrationsApi } from '@/services/api/integrations';

export default function AzureIntegration() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ tenantId: '', clientId: '', clientSecret: '', subscriptionId: '' });
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
      await integrationsApi.connectAzure(form);
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
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl" style={{ background: 'hsl(230 15% 12%)', border: '1px solid hsl(230 15% 16%)' }}>🟦</div>
        <div>
          <h1 className="text-xl font-bold text-foreground">Microsoft Azure Integration</h1>
          <p className="text-sm text-muted-foreground">Connect Azure for cost management and resource monitoring</p>
        </div>
      </div>
      <div className="card-base p-4 space-y-1" style={{ background: 'hsl(220 90% 60% / 0.08)', borderColor: 'hsl(220 90% 60% / 0.2)' }}>
        <p className="text-sm font-medium text-foreground">Setup guide</p>
        <p className="text-xs text-muted-foreground">Create an App Registration in Azure AD, then assign the <code className="text-blue-400">Reader</code> role on your subscription.</p>
        <a href="https://docs.microsoft.com/en-us/azure/active-directory/develop/app-registrations-training-guide-for-app-registrations-legacy-users" target="_blank" rel="noreferrer"
          className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 mt-1">
          Azure documentation <ExternalLink className="w-3 h-3" />
        </a>
      </div>
      <form onSubmit={handleSubmit} className="card-base space-y-4">
        {status === 'success' && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400" style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
            <CheckCircle className="w-4 h-4 flex-shrink-0" /> Azure connected successfully!
          </div>
        )}
        {status === 'error' && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
            <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
          </div>
        )}
        {[
          { key: 'tenantId', label: 'Tenant (Directory) ID', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' },
          { key: 'clientId', label: 'Application (Client) ID', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' },
          { key: 'clientSecret', label: 'Client Secret', placeholder: '•••••••••••••••••••••••••••••', type: 'password' },
          { key: 'subscriptionId', label: 'Subscription ID', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' },
        ].map((field) => (
          <div key={field.key}>
            <label className={labelCls}>{field.label}</label>
            <input type={field.type ?? 'text'} required placeholder={field.placeholder}
              value={form[field.key as keyof typeof form]}
              onChange={(e) => setForm((p) => ({ ...p, [field.key]: e.target.value }))}
              className={inputCls} style={inputStyle} />
          </div>
        ))}
        <button type="submit" disabled={isLoading || Object.values(form).some((v) => !v)}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm text-white disabled:opacity-60"
          style={{ background: 'hsl(220 90% 60%)' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : null}
          {isLoading ? 'Connecting...' : 'Connect Azure'}
        </button>
      </form>
    </motion.div>
  );
}
