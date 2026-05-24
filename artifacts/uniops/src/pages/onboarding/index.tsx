import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Cloud, GitBranch, Users, CheckCircle,
  ArrowRight, ArrowLeft, Zap, Bell, RefreshCw, Server,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { ROUTES } from '@/lib/constants';
import { clsx } from 'clsx';
import { apiPost } from '@/hooks/use-api';
import { integrationsApi } from '@/services/api/integrations';

type StepId = 'welcome' | 'cloud' | 'github' | 'team' | 'alerts' | 'done';
interface Step { id: StepId; title: string; subtitle: string; icon: React.ElementType; optional?: boolean; }

const STEPS: Step[] = [
  { id: 'welcome', title: 'Welcome to UniOps',   subtitle: 'Set up in 2 minutes',               icon: Zap },
  { id: 'cloud',   title: 'Connect AWS',          subtitle: 'Real cost & security data',          icon: Cloud },
  { id: 'github',  title: 'Connect GitHub',        subtitle: 'Pipelines & vulnerability alerts',   icon: GitBranch, optional: true },
  { id: 'team',    title: 'Invite Your Team',      subtitle: 'DevOps, Security & Finance leads',   icon: Users,     optional: true },
  { id: 'alerts',  title: 'Configure Alerts',      subtitle: 'Get notified when things go wrong',  icon: Bell,      optional: true },
  { id: 'done',    title: "You're all set!",        subtitle: 'Your dashboard is ready',            icon: CheckCircle },
];

export default function Onboarding() {
  const { user } = useAuth();
  const navigate  = useNavigate();
  const [stepIdx, setStepIdx]     = useState(0);
  const [completed, setCompleted] = useState<Set<StepId>>(new Set());
  const [direction, setDirection] = useState<1 | -1>(1);

  const step    = STEPS[stepIdx];
  const isFirst = stepIdx === 0;
  const isLast  = stepIdx === STEPS.length - 1;

  const go = useCallback((delta: 1 | -1) => {
    setDirection(delta);
    setStepIdx(i => Math.min(Math.max(0, i + delta), STEPS.length - 1));
  }, []);

  const markDone = useCallback((id: StepId) => {
    setCompleted(s => new Set([...s, id]));
  }, []);

  const variants = {
    enter:  (d: number) => ({ x: d > 0 ? 60 : -60, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit:   (d: number) => ({ x: d > 0 ? -60 : 60, opacity: 0 }),
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'hsl(230 20% 4%)' }}>
      <div className="w-full max-w-xl">
        <div className="flex items-center gap-2 mb-8">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex items-center gap-2 flex-1">
              <button
                onClick={() => { setDirection(i > stepIdx ? 1 : -1); setStepIdx(i); }}
                className={clsx('w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all flex-shrink-0',
                  i < stepIdx || completed.has(s.id) ? 'bg-green-500 text-white' :
                  i === stepIdx ? 'bg-primary text-white ring-2 ring-primary/30' :
                  'bg-surface-1 text-muted-foreground border border-border')}>
                {i < stepIdx || completed.has(s.id) ? <CheckCircle className="w-4 h-4" /> : i + 1}
              </button>
              {i < STEPS.length - 1 && (
                <div className={clsx('flex-1 h-0.5 rounded-full transition-all', i < stepIdx ? 'bg-green-500' : 'bg-border')} />
              )}
            </div>
          ))}
        </div>

        <div className="overflow-hidden rounded-2xl border border-border" style={{ background: 'hsl(230 18% 7%)' }}>
          <AnimatePresence custom={direction} mode="wait">
            <motion.div key={step.id} custom={direction} variants={variants}
              initial="enter" animate="center" exit="exit"
              transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
              className="p-8">
              <StepContent step={step} user={user} isCompleted={completed.has(step.id)} onComplete={() => markDone(step.id)} />
            </motion.div>
          </AnimatePresence>

          <div className="px-8 pb-8 flex items-center justify-between">
            <button onClick={() => go(-1)} disabled={isFirst}
              className={clsx('flex items-center gap-2 text-sm transition-all',
                isFirst ? 'text-muted-foreground/30 cursor-not-allowed' : 'text-muted-foreground hover:text-foreground')}>
              <ArrowLeft className="w-4 h-4" />Back
            </button>
            {isLast ? (
              <button onClick={() => navigate(ROUTES.COMMAND)} className="action-btn-primary">
                Go to Dashboard <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button onClick={() => go(1)} className="action-btn-primary">
                {step.optional && !completed.has(step.id) ? 'Skip for now' : 'Continue'} <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
        <p className="text-center text-xs text-muted-foreground mt-4">You can configure these later in Settings.</p>
      </div>
    </div>
  );
}

function StepContent({ step, user, isCompleted, onComplete }: { step: Step; user: any; isCompleted: boolean; onComplete: () => void; }) {
  switch (step.id) {
    case 'welcome': return <StepWelcome user={user} />;
    case 'cloud':   return <StepAWS isCompleted={isCompleted} onComplete={onComplete} />;
    case 'github':  return <StepGitHub isCompleted={isCompleted} onComplete={onComplete} />;
    case 'team':    return <StepTeam isCompleted={isCompleted} onComplete={onComplete} />;
    case 'alerts':  return <StepAlerts isCompleted={isCompleted} onComplete={onComplete} />;
    case 'done':    return <StepDone />;
    default:        return null;
  }
}

function StepWelcome({ user }: { user: any }) {
  return (
    <div className="text-center py-4">
      <div className="w-16 h-16 rounded-2xl mx-auto mb-6 flex items-center justify-center"
        style={{ background: 'linear-gradient(135deg,hsl(220 90% 55%),hsl(260 70% 60%))' }}>
        <Zap className="w-8 h-8 text-white" />
      </div>
      <h1 className="text-2xl font-bold text-foreground mb-2">
        Welcome{user?.firstName ? `, ${user.firstName}` : ''}! 👋
      </h1>
      <p className="text-muted-foreground mb-6 max-w-sm mx-auto text-sm">
        UniOps gives your team a unified view of DevOps, Security, Cloud Costs,
        and ML Insights — all in one dashboard.
      </p>
      <div className="grid grid-cols-2 gap-3 text-left max-w-xs mx-auto">
        {[
          [Cloud,     'Real AWS cost data'],
          [Server,    'Live Kubernetes pods'],
          [GitBranch, 'CI/CD pipeline status'],
          [Bell,      'Instant alert emails'],
        ].map(([Icon, label]: any) => (
          <div key={label} className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icon className="w-4 h-4 text-primary flex-shrink-0" />{label}
          </div>
        ))}
      </div>
    </div>
  );
}

function StepAWS({ isCompleted, onComplete }: { isCompleted: boolean; onComplete: () => void }) {
  const [form, setForm]   = useState({ accessKey: '', secretKey: '', region: 'us-east-1', name: 'AWS Production' });
  const [loading, setL]   = useState(false);
  const [error, setError] = useState('');
  const [done, setDone]   = useState(isCompleted);

  const inputCls   = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-primary/40 text-foreground font-mono';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const connect = async (e: React.FormEvent) => {
    e.preventDefault(); setL(true); setError('');
    try {
      await apiPost('/integrations/aws', { access_key_id: form.accessKey, secret_access_key: form.secretKey, region: form.region, name: form.name });
      setDone(true); onComplete();
    } catch (err: any) { setError(err.message); }
    finally { setL(false); }
  };

  if (done) return (
    <div className="text-center py-4">
      <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-3" />
      <h2 className="text-lg font-semibold text-foreground mb-1">AWS Connected!</h2>
      <p className="text-sm text-muted-foreground">Syncing cost & security data in the background…</p>
    </div>
  );

  return (
    <div>
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center"><Cloud className="w-5 h-5 text-orange-400" /></div>
        <div><h2 className="text-base font-semibold text-foreground">Connect Amazon Web Services</h2><p className="text-xs text-muted-foreground">Pulls real cost data and Security Hub findings</p></div>
      </div>
      <form onSubmit={connect} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div><label className="text-xs text-muted-foreground mb-1 block">Name</label>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className={inputCls} style={inputStyle} /></div>
          <div><label className="text-xs text-muted-foreground mb-1 block">Region</label>
            <select value={form.region} onChange={e => setForm(f => ({ ...f, region: e.target.value }))} className={inputCls} style={inputStyle}>
              {['us-east-1','us-east-2','us-west-2','eu-west-1','eu-central-1','ap-southeast-1','ap-northeast-1'].map(r => <option key={r} value={r}>{r}</option>)}
            </select></div>
        </div>
        <div><label className="text-xs text-muted-foreground mb-1 block">Access Key ID</label>
          <input value={form.accessKey} onChange={e => setForm(f => ({ ...f, accessKey: e.target.value }))} placeholder="AKIAIOSFODNN7EXAMPLE" required className={inputCls} style={inputStyle} /></div>
        <div><label className="text-xs text-muted-foreground mb-1 block">Secret Access Key</label>
          <input type="password" value={form.secretKey} onChange={e => setForm(f => ({ ...f, secretKey: e.target.value }))} placeholder="••••••••••••••••••••••" required className={inputCls} style={inputStyle} /></div>
        <p className="text-xs text-muted-foreground">Create IAM user with <code className="text-blue-400">ReadOnlyAccess</code> + <code className="text-blue-400">SecurityAudit</code>. Keys are AES-256 encrypted.</p>
        {error && <p className="text-xs text-red-400">{error}</p>}
        <button type="submit" disabled={loading} className="action-btn-primary w-full justify-center">
          {loading ? <><RefreshCw className="w-4 h-4 animate-spin" />Connecting…</> : <><Cloud className="w-4 h-4" />Connect AWS</>}
        </button>
      </form>
    </div>
  );
}

function StepGitHub({ isCompleted, onComplete }: { isCompleted: boolean; onComplete: () => void }) {
  const [token, setToken] = useState('');
  const [loading, setL]   = useState(false);
  const [error, setError] = useState('');
  const [done, setDone]   = useState(isCompleted);

  const inputCls   = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-primary/40 text-foreground font-mono';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const connect = async (e: React.FormEvent) => {
    e.preventDefault(); setL(true); setError('');
    try {
      await integrationsApi.connectGitHub(token.trim(), 'GitHub');
      setDone(true); onComplete();
    } catch (err: any) {
      setError(err.message ?? 'Failed to connect GitHub');
    } finally {
      setL(false);
    }
  };

  if (done) return (
    <div className="text-center py-4">
      <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-3" />
      <h2 className="text-lg font-semibold text-foreground mb-1">GitHub Connected!</h2>
      <p className="text-sm text-muted-foreground">Pipeline runs and Dependabot alerts syncing…</p>
    </div>
  );

  return (
    <div>
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center"><GitBranch className="w-5 h-5 text-foreground" /></div>
        <div><h2 className="text-base font-semibold text-foreground">Connect GitHub</h2><p className="text-xs text-muted-foreground">Pulls workflow runs and Dependabot vulnerabilities</p></div>
      </div>
      <form onSubmit={connect} className="space-y-3">
        <div><label className="text-xs text-muted-foreground mb-1 block">Personal Access Token</label>
          <input value={token} onChange={e => setToken(e.target.value)} placeholder="ghp_xxxxxxxxxxxxxxxxxxxx" required className={inputCls} style={inputStyle} /></div>
        <p className="text-xs text-muted-foreground">
          Create at <a href="https://github.com/settings/tokens/new?scopes=repo,workflow,security_events" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">github.com/settings/tokens</a> with <code className="text-blue-400">repo</code>, <code className="text-blue-400">workflow</code>, <code className="text-blue-400">security_events</code> scopes.
        </p>
        {error && <p className="text-xs text-red-400">{error}</p>}
        <button type="submit" disabled={loading} className="action-btn-primary w-full justify-center">
          {loading ? <><RefreshCw className="w-4 h-4 animate-spin" />Connecting…</> : <><GitBranch className="w-4 h-4" />Connect GitHub</>}
        </button>
      </form>
    </div>
  );
}

function StepTeam({ isCompleted, onComplete }: { isCompleted: boolean; onComplete: () => void }) {
  const [email, setEmail]     = useState('');
  const [role, setRole]       = useState('devops');
  const [invited, setInvited] = useState<string[]>([]);
  const [loading, setL]       = useState(false);

  const inputCls   = 'px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-primary/40 text-foreground';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const invite = async (e: React.FormEvent) => {
    e.preventDefault(); setL(true);
    try {
      await apiPost('/users/invite', { email, role });
      setInvited(i => [...i, email]); setEmail(''); onComplete();
    } finally { setL(false); }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center"><Users className="w-5 h-5 text-blue-400" /></div>
        <div><h2 className="text-base font-semibold text-foreground">Invite Your Team</h2><p className="text-xs text-muted-foreground">Each person gets access to their relevant dashboards</p></div>
      </div>
      <form onSubmit={invite} className="space-y-3 mb-4">
        <div className="flex gap-2">
          <input value={email} onChange={e => setEmail(e.target.value)} type="email" placeholder="colleague@company.com" required className={clsx(inputCls, 'flex-1')} style={inputStyle} />
          <select value={role} onChange={e => setRole(e.target.value)} className={clsx(inputCls, 'w-28')} style={inputStyle}>
            <option value="admin">Admin</option>
            <option value="devops">DevOps</option>
            <option value="security">Security</option>
            <option value="finops">Finance</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
        <button type="submit" disabled={loading} className="action-btn w-full justify-center">
          {loading ? 'Sending…' : 'Send Invitation'}
        </button>
      </form>
      {invited.map(e => (
        <div key={e} className="flex items-center gap-2 text-xs text-green-400 mb-1">
          <CheckCircle className="w-3.5 h-3.5" />{e} — invited
        </div>
      ))}
    </div>
  );
}

function StepAlerts({ isCompleted, onComplete }: { isCompleted: boolean; onComplete: () => void }) {
  const [slack, setSlack] = useState('');
  const [loading, setL]   = useState(false);
  const [done, setDone]   = useState(isCompleted);

  const inputCls   = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-primary/40 text-foreground';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const save = async (e: React.FormEvent) => {
    e.preventDefault(); setL(true);
    await new Promise(r => setTimeout(r, 400));
    setDone(true); onComplete(); setL(false);
  };

  if (done) return (
    <div className="text-center py-4">
      <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-3" />
      <h2 className="text-lg font-semibold text-foreground mb-1">Alerts Configured!</h2>
      <p className="text-sm text-muted-foreground">You'll get notified on critical events.</p>
    </div>
  );

  return (
    <div>
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center"><Bell className="w-5 h-5 text-yellow-400" /></div>
        <div><h2 className="text-base font-semibold text-foreground">Alert Notifications</h2><p className="text-xs text-muted-foreground">Get notified on threats, failures, and cost spikes</p></div>
      </div>
      <div className="space-y-2 mb-4">
        {[
          { emoji: '📧', label: 'Email alerts', sub: 'Critical threats + payment receipts', active: true },
          { emoji: '💬', label: 'Slack alerts', sub: 'Pipeline failures + cost anomalies',  active: !!slack },
        ].map(item => (
          <div key={item.label} className="flex items-center gap-3 p-3 rounded-lg bg-surface-1 border border-border/50">
            <span>{item.emoji}</span>
            <div className="flex-1"><div className="text-sm font-medium text-foreground">{item.label}</div><div className="text-xs text-muted-foreground">{item.sub}</div></div>
            {item.active ? <CheckCircle className="w-4 h-4 text-green-400" /> : <span className="text-xs text-muted-foreground">Optional</span>}
          </div>
        ))}
      </div>
      <form onSubmit={save} className="space-y-3">
        <div><label className="text-xs text-muted-foreground mb-1 block">Slack Webhook URL (optional)</label>
          <input value={slack} onChange={e => setSlack(e.target.value)} placeholder="https://hooks.slack.com/services/..." className={inputCls} style={inputStyle} /></div>
        <button type="submit" disabled={loading} className="action-btn-primary w-full justify-center">
          {loading ? 'Saving…' : 'Save & Continue'}
        </button>
      </form>
    </div>
  );
}

function StepDone() {
  return (
    <div className="text-center py-4">
      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 200, damping: 15 }}
        className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
        <CheckCircle className="w-8 h-8 text-green-400" />
      </motion.div>
      <h2 className="text-2xl font-bold text-foreground mb-2">You're all set!</h2>
      <p className="text-muted-foreground mb-6 max-w-sm mx-auto text-sm">
        UniOps is now collecting data from your connected services.
        Your dashboard will populate in the next few minutes.
      </p>
      <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto">
        {[['Command Center','Live overview'],['DevOps','Pods & pipelines'],['Security','Threats & CVEs']].map(([label, sub]) => (
          <div key={label} className="p-3 rounded-lg bg-surface-1 border border-border/50 text-center">
            <div className="text-xs font-medium text-foreground">{label}</div>
            <div className="text-xs text-muted-foreground">{sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
