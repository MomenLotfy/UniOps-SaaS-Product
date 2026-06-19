import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Cloud, GitBranch, Server, MessageSquare, Activity,
  CheckCircle, XCircle, AlertCircle, RefreshCw, X, Eye, EyeOff, Loader2,
  Key, ExternalLink, ShieldCheck, ArrowRight, Copy, Database, Clock,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { formatRelative } from '@/lib/formatters';
import { clsx } from 'clsx';
import { apiPost, apiPatch } from '@/hooks/use-api';
import { integrationsApi } from '@/services/api/integrations';
import { useNotifications } from '@/contexts/NotificationContext';
import { useIntegrationsCtx } from '@/contexts/IntegrationsContext';

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

const statusIcon: Record<string, any> = {
  connected:           CheckCircle,
  disconnected:        XCircle,
  error:               AlertCircle,
  invalid_token:       AlertCircle,
  credentials_invalid: AlertCircle,
  sync_failed:         AlertCircle,
  pending:             Clock,
  testing:             Loader2,
};
const statusColor: Record<string, string> = {
  connected:           'text-green-400',
  disconnected:        'text-muted-foreground',
  error:               'text-red-400',
  invalid_token:       'text-red-400',
  credentials_invalid: 'text-red-400',
  sync_failed:         'text-yellow-400',
  pending:             'text-yellow-400',
  testing:             'text-yellow-400',
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

// ── GitHub PAT Setup Wizard ───────────────────────────────────────────────────
const GH_TOKEN_URL =
  'https://github.com/settings/tokens/new' +
  '?description=UniOps+Control+Tower' +
  '&scopes=repo,workflow,read%3Aorg';

const REQUIRED_SCOPES = [
  { name: 'repo',       description: 'Clone and read private repositories for scanning' },
  { name: 'workflow',   description: 'Trigger and monitor GitHub Actions CI/CD pipelines' },
  { name: 'read:org',   description: 'List organization repositories and team membership' },
];

type WizardStep = 'intro' | 'enter' | 'validating' | 'success';

function GitHubPATWizard({
  integration,
  onClose,
  onConnected,
}: {
  integration: any;
  onClose: () => void;
  onConnected: () => void;
}) {
  const navigate  = useNavigate();
  const [step, setStep]                         = useState<WizardStep>('intro');
  const [token, setToken]                       = useState('');
  const [showToken, setShowToken]               = useState(false);
  const [copied, setCopied]                     = useState(false);
  const [error, setError]                       = useState<string | null>(null);
  const [connectedInfo, setConnectedInfo]       = useState<{ username: string; repos: number } | null>(null);

  const trimmed   = token.trim();
  const formatOk  = trimmed.startsWith('ghp_') || trimmed.startsWith('github_pat_') || trimmed.length >= 40;

  const modalBg   = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 16%)' } as React.CSSProperties;
  const divider   = { borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;
  const inputStyle= { background: 'hsl(230 15% 7%)', borderColor: 'hsl(230 15% 18%)', color: 'white' } as React.CSSProperties;

  const handleConnect = useCallback(async () => {
    if (!trimmed) return;
    setStep('validating');
    setError(null);
    try {
      const result = await integrationsApi.connectGitHub(trimmed, integration?.name ?? 'GitHub');
      const username  = (result?.config as any)?.username ?? '';
      const repos     = (result?.config as any)?.repo_count ?? 0;

      const syncId = result?.id;
      if (syncId) {
        await apiPost(`/integrations/${syncId}/sync`, {}).catch(() => {});
      }
      await apiPost('/security/repos/sync', {}).catch(() => {});

      setConnectedInfo({ username, repos });
      setStep('success');
      onConnected();
    } catch (e: any) {
      setError(e?.message ?? 'Connection failed — check your token and try again.');
      setStep('enter');
    }
  }, [trimmed, integration, onConnected]);

  const copyUrl = () => {
    navigator.clipboard.writeText(GH_TOKEN_URL).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const stepDots: WizardStep[] = ['intro', 'enter', 'success'];
  const dotIdx = step === 'validating' ? 1 : stepDots.indexOf(step);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={step !== 'validating' ? onClose : undefined} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        className="relative w-full max-w-lg rounded-2xl border shadow-2xl overflow-hidden"
        style={modalBg}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b" style={divider}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'hsl(230 15% 13%)' }}>
              <GitBranch className="w-4 h-4 text-white" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Connect GitHub</h2>
              <p className="text-xs text-gray-500">Personal Access Token setup</p>
            </div>
          </div>
          {step !== 'validating' && (
            <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/5 transition-colors">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Step dots */}
        <div className="flex items-center justify-center gap-2 pt-4 pb-1">
          {['Create token', 'Enter token', 'Connected'].map((label, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className={clsx(
                'flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold transition-all duration-300',
                i < dotIdx
                  ? 'bg-green-500 text-white'
                  : i === dotIdx
                    ? 'bg-blue-500 text-white'
                    : 'bg-white/10 text-gray-500'
              )}>
                {i < dotIdx ? <CheckCircle className="w-3 h-3" /> : i + 1}
              </div>
              <span className={clsx('text-xs hidden sm:block', i === dotIdx ? 'text-white' : 'text-gray-600')}>{label}</span>
              {i < 2 && <div className="w-6 h-px bg-white/10 hidden sm:block" />}
            </div>
          ))}
        </div>

        {/* Body — animated step transitions */}
        <AnimatePresence mode="wait">

          {/* ── Step 1: intro ── */}
          {step === 'intro' && (
            <motion.div key="intro"
              initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
              className="p-5 space-y-4"
            >
              <p className="text-xs text-gray-400 leading-relaxed">
                UniOps needs a GitHub <strong className="text-white">Personal Access Token</strong> to clone
                your repositories for security scanning, read CI/CD pipeline status, and monitor your organization.
              </p>

              {/* Scopes */}
              <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'hsl(230 15% 16%)' }}>
                <div className="px-4 py-2 border-b" style={{ borderColor: 'hsl(230 15% 14%)', background: 'hsl(230 15% 11%)' }}>
                  <span className="text-xs font-semibold text-gray-300">Required token scopes</span>
                </div>
                <div className="divide-y divide-white/5">
                  {REQUIRED_SCOPES.map(scope => (
                    <div key={scope.name} className="flex items-start gap-3 px-4 py-2.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-blue-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <code className="text-xs font-mono text-blue-300">{scope.name}</code>
                        <p className="text-xs text-gray-500 mt-0.5">{scope.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg p-3 text-xs text-yellow-300/80 flex items-start gap-2"
                style={{ background: 'hsl(48 96% 53% / 0.07)', border: '1px solid hsl(48 96% 53% / 0.15)' }}>
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-yellow-400" />
                <span>We recommend a <strong>Classic token</strong> (not fine-grained) for full organization access. Your token is encrypted with AES-256-GCM before storage.</span>
              </div>

              <div className="flex gap-2 pt-1">
                <a
                  href={GH_TOKEN_URL} target="_blank" rel="noreferrer"
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white transition-all"
                  style={{ background: 'hsl(220 90% 55%)' }}
                  onClick={() => setTimeout(() => setStep('enter'), 800)}
                >
                  <ExternalLink className="w-4 h-4" />
                  Open GitHub Token Page
                </a>
                <button
                  onClick={() => setStep('enter')}
                  className="px-4 py-2.5 rounded-lg text-sm text-gray-400 border border-border hover:text-white transition-colors"
                >
                  I have a token
                </button>
              </div>
            </motion.div>
          )}

          {/* ── Step 2: enter token ── */}
          {step === 'enter' && (
            <motion.div key="enter"
              initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
              className="p-5 space-y-4"
            >
              {/* Scope reminder strip */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {REQUIRED_SCOPES.map(s => (
                  <span key={s.name} className="px-2 py-0.5 rounded-md text-xs font-mono border"
                    style={{ color: 'hsl(217 91% 70%)', borderColor: 'hsl(217 91% 50% / 0.25)', background: 'hsl(217 91% 50% / 0.08)' }}>
                    {s.name}
                  </span>
                ))}
                <span className="text-xs text-gray-600 ml-1">scopes required</span>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-2">
                  Paste your Personal Access Token
                </label>
                <div className="relative">
                  <input
                    type={showToken ? 'text' : 'password'}
                    value={token}
                    onChange={e => { setToken(e.target.value); setError(null); }}
                    onKeyDown={e => e.key === 'Enter' && formatOk && handleConnect()}
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    autoFocus
                    autoComplete="off"
                    spellCheck={false}
                    className="w-full px-3 py-2.5 pr-10 rounded-lg text-sm border outline-none focus:ring-2 font-mono transition-all"
                    style={{
                      ...inputStyle,
                      borderColor: formatOk && trimmed ? 'hsl(142 72% 40%)' : error ? 'hsl(0 72% 51% / 0.6)' : 'hsl(230 15% 18%)',
                      boxShadow: formatOk && trimmed ? '0 0 0 2px hsl(142 72% 40% / 0.12)' : undefined,
                    }}
                  />
                  <button type="button" onClick={() => setShowToken(p => !p)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors">
                    {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {/* Format indicator */}
                <div className="mt-1.5 flex items-center justify-between">
                  <span className={clsx('text-xs', formatOk && trimmed ? 'text-green-400' : 'text-gray-600')}>
                    {formatOk && trimmed ? '✓ Token format looks valid' : 'Starts with ghp_ or github_pat_'}
                  </span>
                  <button onClick={copyUrl} className="text-xs text-gray-600 hover:text-blue-400 flex items-center gap-1 transition-colors">
                    <Copy className="w-3 h-3" />
                    {copied ? 'Copied!' : 'Copy GitHub URL'}
                  </button>
                </div>
              </div>

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg text-xs text-red-300"
                  style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.25)' }}>
                  <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-red-400" />
                  <div>
                    <div className="font-medium text-red-400 mb-0.5">Connection failed</div>
                    {error}
                    {error.toLowerCase().includes('scope') || error.toLowerCase().includes('forbidden') ? (
                      <a href={GH_TOKEN_URL} target="_blank" rel="noreferrer"
                        className="block mt-1.5 text-blue-400 hover:underline">
                        Re-create token with correct scopes →
                      </a>
                    ) : null}
                  </div>
                </div>
              )}

              <div className="flex gap-2 pt-1">
                <button onClick={() => setStep('intro')}
                  className="px-4 py-2.5 rounded-lg text-sm text-gray-400 border border-border hover:text-white transition-colors">
                  Back
                </button>
                <button
                  onClick={handleConnect}
                  disabled={!formatOk || !trimmed}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-40 transition-all"
                  style={{ background: 'hsl(220 90% 55%)' }}
                >
                  <Key className="w-4 h-4" />
                  Validate &amp; Connect
                </button>
              </div>
            </motion.div>
          )}

          {/* ── Step 2b: validating ── */}
          {step === 'validating' && (
            <motion.div key="validating"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="p-8 flex flex-col items-center justify-center gap-4"
            >
              <div className="relative">
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
                  style={{ background: 'hsl(220 90% 55% / 0.15)', border: '1px solid hsl(220 90% 55% / 0.25)' }}>
                  <Loader2 className="w-7 h-7 text-blue-400 animate-spin" />
                </div>
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-white">Validating token…</p>
                <p className="text-xs text-gray-500 mt-1">Calling GitHub API &amp; encrypting credentials</p>
              </div>
              <div className="flex flex-col gap-1.5 w-full max-w-xs">
                {['Connecting to GitHub API', 'Verifying token scopes', 'Encrypting credentials', 'Syncing repositories'].map((label, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Loader2 className="w-3 h-3 text-blue-400/60 animate-spin flex-shrink-0"
                      style={{ animationDelay: `${i * 200}ms` }} />
                    <span className="text-xs text-gray-500">{label}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* ── Step 3: success ── */}
          {step === 'success' && connectedInfo && (
            <motion.div key="success"
              initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
              className="p-6 space-y-5"
            >
              <div className="flex flex-col items-center gap-3 py-2">
                <motion.div
                  initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                  className="w-14 h-14 rounded-2xl flex items-center justify-center"
                  style={{ background: 'hsl(142 72% 40% / 0.15)', border: '1px solid hsl(142 72% 40% / 0.3)' }}>
                  <CheckCircle className="w-7 h-7 text-green-400" />
                </motion.div>
                <div className="text-center">
                  <p className="text-base font-bold text-white">GitHub Connected!</p>
                  <p className="text-xs text-gray-500 mt-0.5">Your repositories are ready for security scanning</p>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl p-3 text-center border"
                  style={{ background: 'hsl(230 15% 11%)', borderColor: 'hsl(230 15% 16%)' }}>
                  <div className="text-xl font-bold text-white">
                    {connectedInfo.username ? `@${connectedInfo.username}` : '—'}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">GitHub account</div>
                </div>
                <div className="rounded-xl p-3 text-center border"
                  style={{ background: 'hsl(230 15% 11%)', borderColor: 'hsl(230 15% 16%)' }}>
                  <div className="text-xl font-bold text-white">{connectedInfo.repos || '—'}</div>
                  <div className="text-xs text-gray-500 mt-0.5">Repositories synced</div>
                </div>
              </div>

              {/* Active scopes */}
              <div className="rounded-xl border p-3" style={{ borderColor: 'hsl(142 72% 40% / 0.2)', background: 'hsl(142 72% 40% / 0.05)' }}>
                <p className="text-xs text-green-400 font-medium mb-2">Active permissions</p>
                <div className="flex flex-wrap gap-1.5">
                  {REQUIRED_SCOPES.map(s => (
                    <span key={s.name} className="flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-mono text-green-300"
                      style={{ background: 'hsl(142 72% 40% / 0.12)', border: '1px solid hsl(142 72% 40% / 0.2)' }}>
                      <CheckCircle className="w-2.5 h-2.5" />{s.name}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex gap-2">
                <button onClick={onClose}
                  className="px-4 py-2.5 rounded-lg text-sm text-gray-400 border border-border hover:text-white transition-colors">
                  Done
                </button>
                <button
                  onClick={() => { onClose(); navigate('/security'); }}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white transition-all"
                  style={{ background: 'hsl(142 72% 40%)' }}
                >
                  <Database className="w-4 h-4" />
                  Go to Security Center
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          )}

        </AnimatePresence>
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
  const { addNotification } = useNotifications();

  // Use the global IntegrationsContext so this page shares state with
  // DevOps Center, Security Center, etc. — no duplicate fetches.
  const { integrations: rawIntegrations, isLoading: loading, refetch: ctxRefetch } = useIntegrationsCtx();
  const integrations: any[] = rawIntegrations;

  // After a connection/disconnection, refresh global context immediately
  // AND again after 3 s to pick up the background connection-test result.
  const refetch = useCallback(async () => {
    await ctxRefetch();
    setTimeout(ctxRefetch, 3000);
  }, [ctxRefetch]);

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

  const handleSync = async (id: string, name: string) => {
    setSyncing(id);
    try {
      await apiPost(`/integrations/${id}/sync`, {});
      addNotification({
        title: 'Sync started',
        message: `${name} is syncing in the background. Data will update shortly.`,
        type: 'success',
      });
      setTimeout(refetch, 3000);
    } catch (e: any) {
      addNotification({
        title: 'Sync failed',
        message: e?.message ?? `Could not start sync for ${name}.`,
        type: 'error',
      });
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
          <button onClick={() => refetch()} className="action-btn" disabled={loading}>
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
            const status: string = intg.status ?? 'disconnected';
            const StatusIcon = statusIcon[status] ?? XCircle;
            const metaLine = renderMeta(intg);
            const isConnected = status === 'connected';
            const isPending   = status === 'pending';
            const isError     = ['error', 'credentials_invalid', 'invalid_token', 'sync_failed'].includes(status);

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
                      <StatusIcon className={clsx('w-3.5 h-3.5 flex-shrink-0',
                        isPending ? 'animate-pulse' : '',
                        statusColor[status] ?? 'text-muted-foreground')} />
                      <span className={clsx('text-xs font-medium capitalize', statusColor[status] ?? 'text-muted-foreground')}>
                        {isPending ? 'Testing…' : status.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mb-1">{meta.description}</p>
                    {isConnected && metaLine && (
                      <p className="text-xs text-blue-400/80 mb-1 font-mono">{metaLine}</p>
                    )}
                    {(intg.lastSync || intg.last_sync) && (
                      <p className="text-xs text-muted-foreground">Last sync: {formatRelative(intg.lastSync ?? intg.last_sync)}</p>
                    )}
                    {isError && (intg.error || intg.error_message) && (
                      <p className="text-xs text-red-400/80 font-mono break-words mt-0.5">{intg.error ?? intg.error_message}</p>
                    )}
                    <div className="flex items-center gap-2 mt-3">
                      {isConnected && (
                        <>
                          <button onClick={() => handleTest(intg.id)} disabled={testing === intg.id}
                            className="text-xs px-2.5 py-1.5 rounded-md border border-border hover:bg-accent transition-colors text-muted-foreground">
                            {testing === intg.id ? 'Testing...' : 'Test'}
                          </button>
                          <button onClick={() => handleSync(intg.id, intg.name)} disabled={syncing === intg.id}
                            className="text-xs px-2.5 py-1.5 rounded-md border border-border hover:bg-accent transition-colors text-muted-foreground flex items-center gap-1">
                            <RefreshCw className={clsx('w-3 h-3', syncing === intg.id && 'animate-spin')} />
                            {syncing === intg.id ? 'Syncing...' : 'Sync Now'}
                          </button>
                        </>
                      )}
                      {isError && (
                        <button onClick={() => handleTest(intg.id)} disabled={testing === intg.id}
                          className="text-xs px-2.5 py-1.5 rounded-md border border-orange-500/20 bg-orange-500/10 text-orange-400 hover:bg-orange-500/20 transition-colors">
                          {testing === intg.id ? 'Retrying...' : 'Retry Connection'}
                        </button>
                      )}
                      <button
                        onClick={() => isConnected ? handleDisconnect(intg.id) : handleConnectClick(intg)}
                        className={clsx('text-xs px-3 py-1.5 rounded-md transition-colors ml-auto',
                          isConnected
                            ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20'
                            : 'bg-green-500/10 text-green-400 hover:bg-green-500/20 border border-green-500/20'
                        )}>
                        {isConnected ? 'Disconnect' : isError ? 'Reconnect' : 'Connect'}
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
        {connectModal && providerOf(connectModal) === 'github' && (
          <GitHubPATWizard
            integration={connectModal}
            onClose={() => setConnectModal(null)}
            onConnected={refetch}
          />
        )}
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
        {connectModal && TOKEN_PROVIDERS[providerOf(connectModal)] && providerOf(connectModal) !== 'github' && (
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
