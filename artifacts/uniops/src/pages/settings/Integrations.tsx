import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Cloud, GitBranch, Server, MessageSquare, Activity,
  CheckCircle, XCircle, AlertCircle, RefreshCw, X, Eye, EyeOff, Loader2,
} from 'lucide-react';
import { formatRelative } from '@/lib/formatters';
import { clsx } from 'clsx';
import { useApi, apiPost, apiPatch } from '@/hooks/use-api';
import { integrationsApi } from '@/services/api/integrations'; // ✅ Added: use the corrected integration API methods

const PROVIDER_META: Record<string, { icon: any; color: string; description: string; category: string }> = {
  aws:        { icon: Cloud,         color: 'text-orange-400', description: 'Monitor EC2, S3, RDS, and 200+ AWS services', category: 'Cloud' },
  gcp:        { icon: Cloud,         color: 'text-blue-400',   description: 'GKE, Cloud Run, BigQuery and more', category: 'Cloud' },
  azure:      { icon: Cloud,         color: 'text-cyan-400',   description: 'AKS, Azure Monitor and Azure services', category: 'Cloud' },
  github:     { icon: GitBranch,     color: 'text-white',      description: 'Repositories, Actions CI/CD pipelines', category: 'Version Control' },
  gitlab:     { icon: GitBranch,     color: 'text-orange-500', description: 'GitLab CI/CD and repository monitoring', category: 'Version Control' },
  kubernetes: { icon: Server,        color: 'text-blue-400',   description: 'Cluster monitoring, pods and deployments', category: 'Orchestration' },
  slack:      { icon: MessageSquare, color: 'text-green-400',  description: 'Send alerts and reports to Slack channels', category: 'Communication' },
  teams:      { icon: MessageSquare, color: 'text-purple-400', description: 'Send notifications to Teams channels', category: 'Communication' },
  datadog:    { icon: Activity,      color: 'text-purple-400', description: 'Import metrics and dashboards', category: 'Monitoring' },
};

const TOKEN_PROVIDERS: Record<string, { label: string; placeholder: string; helpUrl: string; helpText: string; extraField?: string }> = {
  github: {
    label: 'GitHub Personal Access Token',
    placeholder: 'ghp_xxxxxxxxxxxxxxxxxxxx',
    helpUrl: 'https://github.com/settings/tokens/new',
    helpText: 'Create a token with repo, workflow, read:org scopes.',
  },
  gitlab: {
    label: 'GitLab Personal Access Token',
    placeholder: 'glpat-xxxxxxxxxxxxxxxxxxxx',
    helpUrl: 'https://gitlab.com/-/user_settings/personal_access_tokens',
    helpText: 'Create a token with api, read_repository scopes.',
    extraField: 'gitlab_url',
  },
};

const statusIcon = {
  connected: CheckCircle,
  disconnected: XCircle,
  error: AlertCircle,
  invalid_token: AlertCircle,
  testing: Loader2,
};
const statusColor = {
  connected: 'text-green-400',
  disconnected: 'text-muted-foreground',
  error: 'text-red-400',
  invalid_token: 'text-red-400',
  testing: 'text-yellow-400',
};

// ── AWS Connect Modal ─────────────────────────────────────────────────────────
function AWSConnectModal({
  integration,
  onClose,
  onConnected,
}: { integration: any; onClose: () => void; onConnected: () => void }) {
  const [form, setForm] = useState({
    name: integration?.name || 'AWS Production',
    region: 'us-east-1',
    accessKeyId: '',
    secretAccessKey: '',
  });
  const [showSecret, setShowSecret] = useState(false);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);

  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 18%)', color: 'white' } as React.CSSProperties;
  const inputCls   = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/40 font-mono';

  const handleConnect = async () => {
    if (!form.accessKeyId.trim() || !form.secretAccessKey.trim()) {
      setError('Access Key ID and Secret Access Key are required');
      return;
    }
    setLoading(true); setError(null);
    try {
      await apiPost('/integrations/aws', {
        access_key_id:     form.accessKeyId.trim(),
        secret_access_key: form.secretAccessKey.trim(),
        region:            form.region,
        name:              form.name.trim() || undefined,
      });
      onConnected();
      onClose();
    } catch (e: any) {
      setError(e?.message ?? 'Connection failed. Check your credentials and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }}
        className="relative w-full max-w-lg rounded-2xl border shadow-2xl"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 16%)' }}>
        <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <div>
            <h2 className="text-sm font-semibold text-white">Connect AWS Account</h2>
            <p className="text-xs text-gray-400 mt-0.5">Credentials are encrypted with AES-256-GCM before storage</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/5"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Name</label>
              <input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="AWS Production"
                className={inputCls}
                style={inputStyle}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Region</label>
              <select
                value={form.region}
                onChange={e => setForm(f => ({ ...f, region: e.target.value }))}
                className={inputCls}
                style={inputStyle}
              >
                {['us-east-1','us-east-2','us-west-1','us-west-2','eu-west-1','eu-west-2','eu-central-1','ap-southeast-1','ap-northeast-1'].map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">AWS Access Key ID</label>
            <input
              value={form.accessKeyId}
              onChange={e => setForm(f => ({ ...f, accessKeyId: e.target.value }))}
              placeholder="AKIAIOSFODNN7EXAMPLE"
              autoComplete="off"
              spellCheck={false}
              className={inputCls}
              style={inputStyle}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">AWS Secret Access Key</label>
            <div className="relative">
              <input
                type={showSecret ? 'text' : 'password'}
                value={form.secretAccessKey}
                onChange={e => setForm(f => ({ ...f, secretAccessKey: e.target.value }))}
                onKeyDown={e => e.key === 'Enter' && handleConnect()}
                placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                autoComplete="new-password"
                className={clsx(inputCls, 'pr-10')}
                style={inputStyle}
              />
              <button type="button" onClick={() => setShowSecret(p => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Create an IAM user with <code className="text-blue-400">ReadOnlyAccess</code> + <code className="text-blue-400">SecurityAudit</code>.{' '}
              <a href="https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">AWS docs →</a>
            </p>
          </div>
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg text-xs text-red-400"
              style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />{error}
            </div>
          )}
          <div className="flex gap-2 pt-1">
            <button onClick={onClose}
              className="flex-1 py-2.5 rounded-lg text-sm text-gray-400 border transition-colors hover:text-white"
              style={{ borderColor: 'hsl(230 15% 18%)' }}>Cancel</button>
            <button onClick={handleConnect} disabled={loading || !form.accessKeyId.trim() || !form.secretAccessKey.trim()}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-50 transition-all"
              style={{ background: 'hsl(220 90% 55%)' }}>
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {loading ? 'Connecting…' : 'Connect AWS'}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// ── Kubernetes Connect Modal ──────────────────────────────────────────────────
function KubernetesConnectModal({
  integration, onClose, onConnected,
}: { integration: any; onClose: () => void; onConnected: () => void }) {
  const [kubeconfig, setKubeconfig] = useState('');
  const [context, setContext]       = useState('');
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);

  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 18%)', color: 'white' } as React.CSSProperties;

  const handleConnect = async () => {
    if (!kubeconfig.trim()) { setError('Kubeconfig is required'); return; }
    setLoading(true); setError(null);
    try {
      await apiPost('/integrations/kubernetes', {
        kubeconfig:   kubeconfig.trim(),
        context:      context.trim() || undefined,
        clusterName:  integration?.name || undefined,
      });
      onConnected();
      onClose();
    } catch (e: any) {
      setError(e?.message ?? 'Connection failed. Verify your kubeconfig.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }}
        className="relative w-full max-w-lg rounded-2xl border shadow-2xl"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 16%)' }}>
        <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <div>
            <h2 className="text-sm font-semibold text-white">Connect Kubernetes Cluster</h2>
            <p className="text-xs text-gray-400 mt-0.5">Kubeconfig is encrypted with AES-256-GCM before storage</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/5"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Kubeconfig (YAML)</label>
            <textarea
              value={kubeconfig}
              onChange={e => setKubeconfig(e.target.value)}
              placeholder={'apiVersion: v1\nclusters:\n- cluster:\n    server: https://...\n  name: my-cluster\n...'}
              rows={8}
              className="w-full px-3 py-2.5 rounded-lg text-xs border outline-none focus:ring-2 focus:ring-blue-500/40 font-mono resize-none"
              style={inputStyle}
              autoFocus
            />
            <p className="text-xs text-gray-500 mt-1">Run <code className="text-blue-400">kubectl config view --raw</code> to get your kubeconfig.</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Context (optional)</label>
            <input
              type="text"
              value={context}
              onChange={e => setContext(e.target.value)}
              placeholder="my-cluster-context (leave blank for default)"
              className="w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/40"
              style={inputStyle}
            />
          </div>
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg text-xs text-red-400"
              style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />{error}
            </div>
          )}
          <div className="flex gap-2 pt-1">
            <button onClick={onClose}
              className="flex-1 py-2.5 rounded-lg text-sm text-gray-400 border transition-colors hover:text-white"
              style={{ borderColor: 'hsl(230 15% 18%)' }}>Cancel</button>
            <button onClick={handleConnect} disabled={loading || !kubeconfig.trim()}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-50 transition-all"
              style={{ background: 'hsl(220 90% 55%)' }}>
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {loading ? 'Connecting…' : 'Connect Cluster'}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// ── Token Connect Modal ───────────────────────────────────────────────────────
function TokenConnectModal({
  integration,
  onClose,
  onConnected,
}: {
  integration: any;
  onClose: () => void;
  onConnected: () => void;
}) {
  const provider = integration.provider ?? integration.type;
  const meta = TOKEN_PROVIDERS[provider];
  const [token, setToken]         = useState('');
  const [extraValue, setExtraValue] = useState('https://gitlab.com');
  const [showToken, setShowToken] = useState(false);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);

  const handleConnect = async () => {
    if (!token.trim()) { setError('Token is required'); return; }
    setLoading(true);
    setError(null);

    try {
      let connectedIntegration: any | undefined;

      if (provider === 'github') {
        connectedIntegration = await integrationsApi.connectGitHub(token.trim(), integration?.name);
      } else if (provider === 'gitlab') {
        connectedIntegration = await integrationsApi.connectGitLab(token.trim(), integration?.name);
      } else {
        // Fallback: PATCH status for other providers
        await apiPatch(`/integrations/${integration.id}`, {
          credentials: { token: token.trim() },
          status: 'connected',
          is_active: true,
        });
        connectedIntegration = integration;
      }

      const syncId = connectedIntegration?.id ?? integration.id;
      if (syncId) {
        try { await apiPost(`/integrations/${syncId}/sync`, {}); } catch (_) {}
      }
      try { await apiPost('/security/repos/sync', {}); } catch (_) {}

      await onConnected();
      onClose();
    } catch (e: any) {
      setError(e?.message ?? 'Connection failed. Check your token and try again.');
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 18%)', color: 'white' } as React.CSSProperties;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        className="relative w-full max-w-md rounded-2xl border shadow-2xl"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 16%)' }}
      >
        <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <div>
            <h2 className="text-sm font-semibold text-white capitalize">Connect {integration.name ?? provider}</h2>
            <p className="text-xs text-gray-400 mt-0.5">Token is encrypted with AES-256-GCM before storage</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/5">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {meta?.extraField && (
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">GitLab Instance URL</label>
              <input
                type="url"
                value={extraValue}
                onChange={e => setExtraValue(e.target.value)}
                placeholder="https://gitlab.com"
                className="w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/40"
                style={inputStyle}
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">{meta?.label ?? 'Personal Access Token'}</label>
            <div className="relative">
              <input
                type={showToken ? 'text' : 'password'}
                value={token}
                onChange={e => setToken(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleConnect()}
                placeholder={meta?.placeholder ?? ''}
                className="w-full px-3 py-2.5 pr-10 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/40 font-mono"
                style={inputStyle}
                autoFocus
              />
              <button
                type="button"
                onClick={() => setShowToken(p => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
              >
                {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {meta && (
              <p className="text-xs text-gray-500 mt-1.5">
                {meta.helpText}{' '}
                <a href={meta.helpUrl} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">Create token →</a>
              </p>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg text-xs text-red-400"
              style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />{error}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button onClick={onClose}
              className="flex-1 py-2.5 rounded-lg text-sm text-gray-400 border transition-colors hover:text-white"
              style={{ borderColor: 'hsl(230 15% 18%)' }}>
              Cancel
            </button>
            <button
              onClick={handleConnect}
              disabled={loading || !token.trim()}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-50 transition-all"
              style={{ background: 'hsl(220 90% 55%)' }}
            >
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {loading ? 'Connecting…' : 'Connect'}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Integrations() {
  const [filter, setFilter] = useState('All');
  const [testing, setTesting] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [connectModal, setConnectModal] = useState<any | null>(null);

  const { data, loading, refetch } = useApi<any>('/integrations?page_size=50');
  // useApi already unwraps body.data — result is the array directly
  const integrations: any[] = (Array.isArray(data) ? data : data?.data) ?? [];

  const providerOf = (i: any) => i.provider ?? i.type ?? '';

  const ALL_PROVIDERS = Object.keys(PROVIDER_META);
  const dbTypes = new Set(integrations.map((i: any) => providerOf(i)));
  const placeholders = ALL_PROVIDERS
    .filter(p => dbTypes.has(p) === false)
    .map(p => ({ id: `placeholder-${p}`, type: p, name: p.charAt(0).toUpperCase() + p.slice(1), status: 'disconnected' }));
  const allIntegrations = [...integrations, ...placeholders];

  const categories = ['All', ...Array.from(new Set(
    allIntegrations.map((i: any) => PROVIDER_META[providerOf(i)]?.category ?? 'Other')
  ))];

  const filtered = filter === 'All' ? allIntegrations : allIntegrations.filter((i: any) => PROVIDER_META[providerOf(i)]?.category === filter);

  const connected = allIntegrations.filter((i: any) => i.status === 'connected').length;

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      await apiPost(`/integrations/${id}/test`, {});
      refetch();
    } finally {
      setTesting(null);
    }
  };

  const handleSync = async (id: string) => {
    setSyncing(id);
    try {
      await apiPost(`/integrations/${id}/sync`, {});
      refetch();
    } finally {
      setSyncing(null);
    }
  };

  const handleDisconnect = async (id: string) => {
    await apiPatch(`/integrations/${id}`, { status: 'disconnected', is_active: false });
    refetch();
  };

  const handleConnectClick = (intg: any) => {
    setConnectModal(intg);
  };

  // Render a short metadata line for connected integrations
  const renderMeta = (intg: any) => {
    const p = providerOf(intg);
    const cfg = intg.config || {};
    if (p === 'github' && cfg.username) {
      return `@${cfg.username}${cfg.repo_count != null ? ` · ${cfg.repo_count} repos` : ''}`;
    }
    if (p === 'gitlab' && cfg.gitlab_url) {
      return cfg.gitlab_url.replace('https://', '');
    }
    if (p === 'kubernetes' && (cfg.node_count != null || cfg.cluster_name)) {
      return [cfg.cluster_name, cfg.node_count != null ? `${cfg.node_count} nodes` : null].filter(Boolean).join(' · ');
    }
    if (p === 'aws' && (cfg.region || cfg.key_prefix)) {
      return [cfg.region, cfg.key_prefix ? `key: ${cfg.key_prefix}` : null].filter(Boolean).join(' · ');
    }
    return intg.description || null;
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Integrations</h1>
          <p className="page-subtitle">{connected} of {integrations.length} integrations connected</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={refetch} className="action-btn" disabled={loading}>
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />Refresh
          </button>
        </div>
      </div>

      <div className="tab-bar mb-5">
        {categories.map(c => (
          <button key={c} onClick={() => setFilter(c)} className={clsx('tab-btn', filter === c && 'active')}>{c}</button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="card-base h-32 animate-pulse bg-surface-2" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card-base py-12 text-center">
          <p className="text-sm text-muted-foreground">No integrations found. Add your first integration to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {filtered.map((intg: any) => {
            const p = providerOf(intg);
            const meta = PROVIDER_META[p] ?? { icon: Activity, color: 'text-muted-foreground', description: p, category: 'Other' };
            const Icon = meta.icon;
            const status: 'connected' | 'disconnected' | 'error' | 'invalid_token' | 'testing' = intg.status ?? 'disconnected';
            const StatusIcon = statusIcon[status] ?? XCircle;
            const metaLine = renderMeta(intg);

            return (
              <motion.div key={intg.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="card-base">
                <div className="flex items-start gap-4">
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ background: 'hsl(230 15% 12%)' }}>
                    <Icon className={clsx('w-5 h-5', meta.color)} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <h3 className="text-sm font-semibold text-foreground capitalize">{intg.name}</h3>
                      <StatusIcon className={clsx('w-3.5 h-3.5 flex-shrink-0', statusColor[status])} />
                    </div>
                    <p className="text-xs text-muted-foreground mb-1">{meta.description}</p>
                    {status === 'connected' && metaLine && (
                      <p className="text-xs text-blue-400/80 mb-1 font-mono">{metaLine}</p>
                    )}
                    {intg.lastSync && (
                      <p className="text-xs text-muted-foreground">Last sync: {formatRelative(intg.lastSync)}</p>
                    )}
                    {!intg.lastSync && intg.last_sync && (
                      <p className="text-xs text-muted-foreground">Last sync: {formatRelative(intg.last_sync)}</p>
                    )}
                    {status !== 'connected' && intg.error && (
                      <p className="text-xs text-red-400/80 font-mono break-words">{intg.error}</p>
                    )}
                    <div className="flex items-center gap-2 mt-3">
                      {status === 'connected' && (
                        <>
                          <button onClick={() => handleTest(intg.id)} disabled={testing === intg.id}
                            className="text-xs px-2.5 py-1.5 rounded-md border border-border hover:bg-accent transition-colors text-muted-foreground">
                            {testing === intg.id ? 'Testing...' : 'Test'}
                          </button>
                          <button onClick={() => handleSync(intg.id)} disabled={syncing === intg.id}
                            className="text-xs px-2.5 py-1.5 rounded-md border border-border hover:bg-accent transition-colors text-muted-foreground">
                            <RefreshCw className={clsx('w-3 h-3 inline mr-1', syncing === intg.id && 'animate-spin')} />
                            {syncing === intg.id ? 'Syncing...' : 'Sync Now'}
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => status === 'connected' ? handleDisconnect(intg.id) : handleConnectClick(intg)}
                        className={clsx('text-xs px-3 py-1.5 rounded-md transition-colors ml-auto',
                          status === 'connected'
                            ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20'
                            : 'bg-green-500/10 text-green-400 hover:bg-green-500/20 border border-green-500/20'
                        )}>
                        {status === 'connected' ? 'Disconnect' : 'Connect'}
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Connect modals */}
      <AnimatePresence>
        {connectModal && providerOf(connectModal) === 'kubernetes' && (
          <KubernetesConnectModal
            integration={connectModal}
            onClose={() => setConnectModal(null)}
            onConnected={refetch}
          />
        )}
        {connectModal && providerOf(connectModal) === 'aws' && (
          <AWSConnectModal
            integration={connectModal}
            onClose={() => setConnectModal(null)}
            onConnected={refetch}
          />
        )}
        {connectModal && TOKEN_PROVIDERS[providerOf(connectModal)] && (
          <TokenConnectModal
            integration={connectModal}
            onClose={() => setConnectModal(null)}
            onConnected={refetch}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}
