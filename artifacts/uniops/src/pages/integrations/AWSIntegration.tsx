import { useState } from 'react';
import { motion } from 'framer-motion';
import { Cloud, CheckCircle, XCircle, RefreshCw, Shield, DollarSign, AlertTriangle } from 'lucide-react';
import { apiPost } from '@/hooks/use-api';
import { useIntegrationsCtx } from '@/contexts/IntegrationsContext';
import { IntegrationStatus } from '@/components/integrations/IntegrationStatus';
import { clsx } from 'clsx';

export default function AWSIntegration() {
  const [form, setForm] = useState({ accessKeyId: '', secretAccessKey: '', region: 'us-east-1', name: 'AWS Production' });
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  // ── Global context — no extra GET /integrations needed ────────────────────
  const { integrations, refetch } = useIntegrationsCtx();
  const awsIntegrations = integrations.filter((i) => i.provider === 'aws');
  // An integration is "configured" if it exists and wasn't explicitly disconnected.
  // We show connected accounts for all non-disconnected statuses so users can see
  // the integration exists even when credentials are invalid or sync has failed.
  const configured = awsIntegrations.filter((i) => i.status !== 'disconnected');

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/50 text-foreground font-mono';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setConnecting(true);
    setResult(null);
    try {
      await apiPost('/integrations/aws', {
        access_key_id: form.accessKeyId,
        secret_access_key: form.secretAccessKey,
        region: form.region,
        name: form.name,
      });
      setResult({
        success: true,
        message: 'AWS connected! Discovering assets (EC2, S3, IAM, RDS) and pulling Security Hub findings — Security Center will populate in ~60 seconds.',
      });
      setForm(f => ({ ...f, accessKeyId: '', secretAccessKey: '' }));
      setTimeout(() => refetch(), 5000);
    } catch (err: any) {
      setResult({ success: false, message: err.message });
    } finally {
      setConnecting(false);
    }
  };

  const handleSync = async (integrationId: string) => {
    setSyncing(true);
    try {
      await apiPost(`/integrations/${integrationId}/sync`, {});
      setResult({
        success: true,
        message: 'Full sync started — costs, assets (EC2/S3/IAM/RDS), and Security Hub findings are refreshing. Security Center will update in ~60 seconds.',
      });
      setTimeout(() => refetch(), 8000);
    } catch (err: any) {
      setResult({ success: false, message: err.message });
    } finally {
      setSyncing(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Cloud className="w-5 h-5 text-orange-400" />
            <h1 className="page-title">Amazon Web Services</h1>
          </div>
          <p className="page-subtitle">Connect AWS to pull real costs, security findings, and compliance status</p>
        </div>
      </div>

      {/* What you'll get */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-6">
        {[
          { icon: DollarSign, color: 'text-yellow-400', bg: 'bg-yellow-500/10', title: 'Real Cost Data', desc: 'Monthly spend by service, cost anomalies, rightsizing recommendations' },
          { icon: Shield, color: 'text-red-400', bg: 'bg-red-500/10', title: 'Security Findings', desc: 'Threats and vulnerabilities from AWS Security Hub' },
          { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-500/10', title: 'Compliance Status', desc: 'SOC2, PCI-DSS, CIS scores from Security Hub standards' },
        ].map(item => (
          <div key={item.title} className="card-base flex gap-3">
            <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0', item.bg)}>
              <item.icon className={clsx('w-4 h-4', item.color)} />
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground">{item.title}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{item.desc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Configured integrations (all non-disconnected statuses) */}
      {configured.length > 0 && (
        <div className="card-base mb-6">
          <h2 className="text-sm font-semibold text-foreground mb-3">AWS Accounts</h2>
          <div className="space-y-3">
            {configured.map((intg: any) => (
              <div key={intg.id} className="p-3 rounded-lg border"
                style={{ background: 'hsl(230 18% 7%)', borderColor: 'hsl(230 15% 14%)' }}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🟠</span>
                    <div>
                      <div className="text-sm font-medium text-foreground">{intg.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {intg.last_sync
                          ? `Last sync: ${new Date(intg.last_sync).toLocaleString()}`
                          : 'Never synced'}
                      </div>
                    </div>
                  </div>
                  <IntegrationStatus status={intg.status} />
                </div>
                {/* Error message inline */}
                {intg.error_message && (intg.status === 'credentials_invalid' || intg.status === 'error' || intg.status === 'sync_failed') && (
                  <div className={clsx('flex items-start gap-2 mt-2 p-2 rounded text-xs',
                    intg.status === 'sync_failed' ? 'bg-orange-500/8 text-orange-300' : 'bg-red-500/8 text-red-300')}>
                    <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                    <span className="break-all">{intg.error_message}</span>
                  </div>
                )}
                <div className="flex gap-2 mt-2.5">
                  <button onClick={() => handleSync(intg.id)} disabled={syncing}
                    className="text-xs px-3 py-1.5 rounded-md bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20 flex items-center gap-1.5 disabled:opacity-50">
                    <RefreshCw className={clsx('w-3 h-3', syncing && 'animate-spin')} />
                    {syncing ? 'Syncing…' : 'Sync Now'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Connect form */}
      <div className="card-base">
        <h2 className="text-sm font-semibold text-foreground mb-1">Connect AWS Account</h2>
        <p className="text-xs text-muted-foreground mb-4">
          Create an IAM user with <code className="text-blue-400">ReadOnlyAccess</code> + <code className="text-blue-400">SecurityAudit</code> policies.
          {' '}<a href="https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">AWS docs →</a>
        </p>

        <form onSubmit={handleConnect} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">Integration Name</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="AWS Production" className={inputCls} style={inputStyle} required />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">Region</label>
              <select value={form.region} onChange={e => setForm(f => ({ ...f, region: e.target.value }))}
                className={inputCls} style={inputStyle}>
                {['us-east-1','us-east-2','us-west-1','us-west-2','eu-west-1','eu-west-2','eu-central-1','ap-southeast-1','ap-northeast-1'].map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">AWS Access Key ID</label>
            <input value={form.accessKeyId} onChange={e => setForm(f => ({ ...f, accessKeyId: e.target.value }))}
              placeholder="AKIAIOSFODNN7EXAMPLE" className={inputCls} style={inputStyle} required
              autoComplete="off" spellCheck={false} />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">AWS Secret Access Key</label>
            <input type="password" value={form.secretAccessKey} onChange={e => setForm(f => ({ ...f, secretAccessKey: e.target.value }))}
              placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" className={inputCls} style={inputStyle} required
              autoComplete="new-password" />
          </div>

          {result && (
            <div className={clsx('flex items-center gap-2 p-3 rounded-lg text-sm',
              result.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400')}>
              {result.success ? <CheckCircle className="w-4 h-4 flex-shrink-0" /> : <XCircle className="w-4 h-4 flex-shrink-0" />}
              {result.message}
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <p className="text-xs text-muted-foreground">
              Keys are encrypted with AES-256 before storage
            </p>
            <button type="submit" disabled={connecting} className="action-btn-primary">
              {connecting ? <><RefreshCw className="w-4 h-4 animate-spin" />Connecting...</> : <><Cloud className="w-4 h-4" />Connect AWS</>}
            </button>
          </div>
        </form>
      </div>
    </motion.div>
  );
}
