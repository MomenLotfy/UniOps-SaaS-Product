// ─────────────────────────────────────────────────────────────────────────────
// GitOpsTab — ArgoCD-style application management (Epic 5)
// App cards with health/sync status, Sync / Rollback / History actions
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  GitBranch, RefreshCw, CheckCircle2, AlertTriangle, XCircle,
  Clock, Loader2, Plus, ExternalLink, RotateCcw, ChevronRight,
  Server, FolderGit2, Zap, Activity, ArrowLeft, History,
  GitCommit, User, Calendar, Tag,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost, apiDelete } from '@/hooks/use-api';

// ── Types ────────────────────────────────────────────────────────────────────

type HealthStatus = 'Healthy' | 'Degraded' | 'Progressing' | 'Missing' | 'Suspended' | 'Unknown';
type SyncStatus   = 'Synced'  | 'OutOfSync' | 'Unknown';
type SourceType   = 'git' | 'helm' | 'kustomize';

interface GitOpsApp {
  id: string; name: string; project: string; namespace: string;
  cluster_id?: string; source_type: SourceType;
  repo_url?: string; target_revision: string; path?: string; helm_chart?: string;
  health_status: HealthStatus; sync_status: SyncStatus; sync_message?: string;
  last_synced_at?: string; current_revision?: string;
  argocd_app_name?: string; argocd_server?: string;
  resource_summary: Record<string, number>;
  created_at: string;
}

interface HistoryEntry {
  id: string; app_id: string; revision: string; short_sha?: string;
  author?: string; message?: string; deployed_at: string; deployed_by?: string;
  status: string; source_type: string;
}

interface GitOpsStats {
  total: number; healthy: number; degraded: number; progressing: number;
  synced: number; out_of_sync: number; argocd_connected: boolean;
}

// ── Style maps ────────────────────────────────────────────────────────────────

const HEALTH_COLOR: Record<string, string> = {
  Healthy:     'text-green-400',
  Degraded:    'text-red-400',
  Progressing: 'text-blue-400',
  Missing:     'text-gray-500',
  Suspended:   'text-yellow-400',
  Unknown:     'text-gray-500',
};
const HEALTH_BG: Record<string, string> = {
  Healthy:     'bg-green-500/10 border-green-500/20',
  Degraded:    'bg-red-500/10 border-red-500/20',
  Progressing: 'bg-blue-500/10 border-blue-500/20',
  Missing:     'bg-gray-500/10 border-gray-500/20',
  Suspended:   'bg-yellow-500/10 border-yellow-500/20',
  Unknown:     'bg-gray-500/10 border-gray-500/20',
};
const SYNC_COLOR: Record<string, string> = {
  Synced:    'text-green-400',
  OutOfSync: 'text-yellow-400',
  Unknown:   'text-gray-500',
};
const SYNC_BG: Record<string, string> = {
  Synced:    'bg-green-500/10 text-green-400',
  OutOfSync: 'bg-yellow-500/10 text-yellow-400',
  Unknown:   'bg-gray-500/10 text-gray-500',
};
const HIST_STATUS_COLOR: Record<string, string> = {
  Succeeded: 'text-green-400',
  Failed:    'text-red-400',
  Running:   'text-blue-400',
};
const SOURCE_TYPE_ICON: Record<SourceType, React.ElementType> = {
  git:       FolderGit2,
  helm:      Tag,
  kustomize: Server,
};

function HealthDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    Healthy: 'bg-green-500', Degraded: 'bg-red-500',
    Progressing: 'bg-blue-500 animate-pulse', Suspended: 'bg-yellow-500',
    Missing: 'bg-gray-600', Unknown: 'bg-gray-700',
  };
  return <span className={clsx('inline-block w-2 h-2 rounded-full flex-shrink-0', colors[status] ?? 'bg-gray-700')} />;
}

function timeAgo(ts?: string): string {
  if (!ts) return '—';
  try {
    const diff = Date.now() - new Date(ts).getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  } catch { return '—'; }
}

// ── Stat pill ─────────────────────────────────────────────────────────────────

function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex flex-col items-center px-4 py-3 rounded-xl border min-w-[72px]"
      style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
      <span className={clsx('text-xl font-bold tabular-nums', color)}>{value}</span>
      <span className="text-xs text-gray-500 mt-0.5">{label}</span>
    </div>
  );
}

// ── Add App dialog ─────────────────────────────────────────────────────────────

const SOURCE_TYPES: SourceType[] = ['git', 'helm', 'kustomize'];

function AddAppDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    name: '', project: 'default', namespace: 'default',
    source_type: 'git' as SourceType,
    repo_url: '', target_revision: 'HEAD', path: '',
    helm_chart: '', argocd_app_name: '',
  });
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState<string | null>(null);
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const inputCls  = "w-full px-3 py-2 rounded-lg text-sm text-white border outline-none focus:border-blue-500/50 transition-colors";
  const inputStyle = { background: 'hsl(230 15% 13%)', borderColor: 'hsl(230 15% 20%)' };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name) { setError('App name is required'); return; }
    setSaving(true); setError(null);
    try {
      await apiPost('/gitops', { ...form, argocd_app_name: form.argocd_app_name || form.name });
      onCreated(); onClose();
    } catch (err: any) { setError(err?.message ?? 'Failed to register app'); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.94 }}
        className="w-full max-w-lg rounded-2xl border shadow-2xl overflow-hidden"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 18%)' }}>
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'hsl(230 15% 15%)' }}>
          <span className="font-semibold text-white text-sm flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-blue-400" />Register GitOps App
          </span>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors text-xl leading-none">×</button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">App name *</label>
              <input value={form.name} onChange={e => set('name', e.target.value)} placeholder="my-app" className={inputCls} style={inputStyle} />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Project</label>
              <input value={form.project} onChange={e => set('project', e.target.value)} placeholder="default" className={inputCls} style={inputStyle} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Namespace</label>
              <input value={form.namespace} onChange={e => set('namespace', e.target.value)} placeholder="default" className={inputCls} style={inputStyle} />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Source type</label>
              <select value={form.source_type} onChange={e => set('source_type', e.target.value)} className={inputCls} style={inputStyle}>
                {SOURCE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Repository URL</label>
            <input value={form.repo_url} onChange={e => set('repo_url', e.target.value)} placeholder="https://github.com/org/repo" className={inputCls} style={inputStyle} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Target revision</label>
              <input value={form.target_revision} onChange={e => set('target_revision', e.target.value)} placeholder="HEAD" className={inputCls} style={inputStyle} />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">{form.source_type === 'helm' ? 'Chart name' : 'Path'}</label>
              <input
                value={form.source_type === 'helm' ? form.helm_chart : form.path}
                onChange={e => set(form.source_type === 'helm' ? 'helm_chart' : 'path', e.target.value)}
                placeholder={form.source_type === 'helm' ? 'my-chart' : './charts/app'}
                className={inputCls} style={inputStyle}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">ArgoCD app name (if using ArgoCD)</label>
            <input value={form.argocd_app_name} onChange={e => set('argocd_app_name', e.target.value)} placeholder={form.name || 'my-app'} className={inputCls} style={inputStyle} />
          </div>

          {error && <p className="text-xs text-red-400 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">{error}</p>}

          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2 rounded-lg text-xs text-gray-400 border border-white/10 hover:text-white transition-colors">Cancel</button>
            <button type="submit" disabled={saving} className="flex-1 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-60 flex items-center justify-center gap-1.5">
              {saving && <Loader2 className="w-3 h-3 animate-spin" />}
              {saving ? 'Registering…' : 'Register App'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

// ── Rollback dialog ───────────────────────────────────────────────────────────

function RollbackDialog({ app, history, onConfirm, onCancel }:
  { app: GitOpsApp; history: HistoryEntry[]; onConfirm: (rev: string, msg: string) => void; onCancel: () => void }) {
  const [selectedRev, setSelectedRev] = useState(history[1]?.revision ?? '');
  const [message, setMessage]         = useState('');

  const inputCls  = "w-full px-3 py-2 rounded-lg text-sm text-white border outline-none focus:border-blue-500/50 transition-colors";
  const inputStyle = { background: 'hsl(230 15% 13%)', borderColor: 'hsl(230 15% 20%)' };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md rounded-2xl border shadow-2xl"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 18%)' }}>
        <div className="flex items-center gap-2 px-5 py-4 border-b" style={{ borderColor: 'hsl(230 15% 15%)' }}>
          <RotateCcw className="w-4 h-4 text-yellow-400" />
          <span className="font-semibold text-white text-sm">Rollback — {app.name}</span>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-2">Select deployment to roll back to</label>
            {history.slice(1, 8).length === 0 ? (
              <p className="text-xs text-gray-600">No previous deployments found.</p>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {history.slice(1, 8).map(h => (
                  <label key={h.id}
                    className={clsx('flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all',
                      selectedRev === h.revision
                        ? 'border-blue-500/40 bg-blue-500/5'
                        : 'border-white/5 hover:border-white/10')}
                  >
                    <input type="radio" name="rev" value={h.revision} checked={selectedRev === h.revision}
                      onChange={() => setSelectedRev(h.revision)} className="mt-0.5 accent-blue-500" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-blue-400">{h.short_sha ?? h.revision.slice(0, 7)}</span>
                        <span className={clsx('text-xs', HIST_STATUS_COLOR[h.status] ?? 'text-gray-400')}>{h.status}</span>
                        <span className="text-xs text-gray-600 ml-auto">{timeAgo(h.deployed_at)}</span>
                      </div>
                      {h.message && <p className="text-xs text-gray-400 mt-0.5 truncate">{h.message}</p>}
                      {h.author && <p className="text-xs text-gray-600">{h.author}</p>}
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Reason (optional)</label>
            <input value={message} onChange={e => setMessage(e.target.value)} placeholder="Reverting due to…" className={inputCls} style={inputStyle} />
          </div>
          <div className="flex gap-2">
            <button onClick={onCancel} className="flex-1 py-2 rounded-lg text-xs text-gray-400 border border-white/10 hover:text-white transition-colors">Cancel</button>
            <button
              onClick={() => selectedRev && onConfirm(selectedRev, message)}
              disabled={!selectedRev}
              className="flex-1 py-2 rounded-lg text-xs font-medium bg-yellow-500 hover:bg-yellow-400 text-black transition-colors disabled:opacity-40">
              Rollback
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// ── History panel ─────────────────────────────────────────────────────────────

function HistoryPanel({ app, onBack }: { app: GitOpsApp; onBack: () => void }) {
  const { data: raw, loading } = useApi<any>(`/gitops/${app.id}/history?limit=20`);
  const history: HistoryEntry[] = raw?.data ?? raw ?? [];

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
      <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors mb-4">
        <ArrowLeft className="w-3.5 h-3.5" />Back to apps
      </button>
      <div className="flex items-center gap-2 mb-4">
        <History className="w-4 h-4 text-blue-400" />
        <span className="text-sm font-semibold text-white">{app.name}</span>
        <span className="text-xs text-gray-500">— deployment history</span>
      </div>

      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 text-gray-500 animate-spin" /></div>
      ) : history.length === 0 ? (
        <div className="flex flex-col items-center py-12 text-center">
          <GitCommit className="w-10 h-10 text-gray-700 mb-2" />
          <p className="text-xs text-gray-500">No deployment history yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {history.map((h, i) => (
            <motion.div key={h.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              className="flex items-start gap-3 p-4 rounded-xl border"
              style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
              <div className="flex flex-col items-center gap-1 flex-shrink-0">
                <div className={clsx('w-2 h-2 rounded-full mt-1.5', {
                  'bg-green-500': h.status === 'Succeeded',
                  'bg-red-500':   h.status === 'Failed',
                  'bg-blue-500 animate-pulse': h.status === 'Running',
                })} />
                {i < history.length - 1 && <div className="w-px flex-1 min-h-4" style={{ background: 'hsl(230 15% 18%)' }} />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs font-semibold text-blue-400">
                    {h.short_sha ?? h.revision.slice(0, 7)}
                  </span>
                  <span className={clsx('text-xs px-1.5 py-0.5 rounded bg-white/5', HIST_STATUS_COLOR[h.status] ?? 'text-gray-400')}>
                    {h.status}
                  </span>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-white/5 text-gray-500 capitalize">{h.source_type}</span>
                  <span className="text-xs text-gray-600 ml-auto">{timeAgo(h.deployed_at)}</span>
                </div>
                {h.message && <p className="text-xs text-gray-300 mt-1">{h.message}</p>}
                <div className="flex items-center gap-3 mt-1 text-xs text-gray-600">
                  {h.author && <span className="flex items-center gap-1"><User className="w-3 h-3" />{h.author}</span>}
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    {new Date(h.deployed_at).toLocaleString()}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}

// ── App card ──────────────────────────────────────────────────────────────────

interface AppCardProps {
  app: GitOpsApp;
  onSync:    (id: string, hard?: boolean) => void;
  onDelete:  (id: string) => void;
  onHistory: (app: GitOpsApp) => void;
  onRollback:(app: GitOpsApp) => void;
  busy:      boolean;
}

function AppCard({ app, onSync, onDelete, onHistory, onRollback, busy }: AppCardProps) {
  const SrcIcon = SOURCE_TYPE_ICON[app.source_type] ?? FolderGit2;

  return (
    <motion.div layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border overflow-hidden"
      style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
      {/* Header */}
      <div className="flex items-start gap-3 p-4">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: 'hsl(230 15% 14%)' }}>
          <SrcIcon className="w-4 h-4 text-blue-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-white">{app.name}</span>
            <span className="text-xs text-gray-600">/{app.project}</span>
            {/* Health badge */}
            <span className={clsx('flex items-center gap-1 px-1.5 py-0.5 text-xs rounded border', HEALTH_BG[app.health_status])}>
              <HealthDot status={app.health_status} />
              <span className={HEALTH_COLOR[app.health_status]}>{app.health_status}</span>
            </span>
            {/* Sync badge */}
            <span className={clsx('px-1.5 py-0.5 text-xs rounded', SYNC_BG[app.sync_status])}>
              {app.sync_status === 'OutOfSync' ? '↑ Out of Sync' : app.sync_status}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 flex-wrap">
            <span className="flex items-center gap-1"><Server className="w-3 h-3" />{app.namespace}</span>
            {app.repo_url && (
              <span className="flex items-center gap-1 truncate max-w-48">
                <GitBranch className="w-3 h-3 flex-shrink-0" />
                <span className="truncate">{app.repo_url.replace(/^https?:\/\//, '')}</span>
              </span>
            )}
            {app.current_revision && (
              <span className="flex items-center gap-1 font-mono">
                <GitCommit className="w-3 h-3" />{app.current_revision.slice(0, 7)}
              </span>
            )}
            {app.last_synced_at && (
              <span className="flex items-center gap-1 ml-auto">
                <Clock className="w-3 h-3" />synced {timeAgo(app.last_synced_at)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Actions footer */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-t" style={{ borderColor: 'hsl(230 15% 13%)' }}>
        {/* Sync */}
        <button onClick={() => onSync(app.id, false)} disabled={busy}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600/80 hover:bg-blue-600 text-white transition-all disabled:opacity-50">
          {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          Sync
        </button>
        <button onClick={() => onSync(app.id, true)} disabled={busy}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 border border-white/10 hover:text-white hover:border-white/20 transition-all disabled:opacity-50">
          <Zap className="w-3 h-3" />Hard
        </button>
        <button onClick={() => onRollback(app)} disabled={busy}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 border border-white/10 hover:text-yellow-400 hover:border-yellow-500/30 transition-all disabled:opacity-50">
          <RotateCcw className="w-3 h-3" />Rollback
        </button>
        <button onClick={() => onHistory(app)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 border border-white/10 hover:text-blue-400 hover:border-blue-500/30 transition-all">
          <History className="w-3 h-3" />History
        </button>
        <div className="flex-1" />
        {app.argocd_server && (
          <a href={`${app.argocd_server}/applications/${app.argocd_app_name}`} target="_blank" rel="noreferrer"
            className="flex items-center gap-1 text-xs text-gray-600 hover:text-blue-400 transition-colors">
            <ExternalLink className="w-3 h-3" />ArgoCD
          </a>
        )}
        <button onClick={() => { if (window.confirm('Remove this app?')) onDelete(app.id); }}
          className="text-gray-700 hover:text-red-400 transition-colors">
          <XCircle className="w-3.5 h-3.5" />
        </button>
      </div>
    </motion.div>
  );
}

// ── Main GitOpsTab ────────────────────────────────────────────────────────────

interface GitOpsTabProps {
  showToast: (ok: boolean, msg: string) => void;
}

export function GitOpsTab({ showToast }: GitOpsTabProps) {
  const [showAdd,      setShowAdd]      = useState(false);
  const [detailApp,    setDetailApp]    = useState<GitOpsApp | null>(null);    // history panel
  const [rollbackApp,  setRollbackApp]  = useState<GitOpsApp | null>(null);
  const [busy,         setBusy]         = useState<Record<string, boolean>>({});
  const [healthFilter, setHealthFilter] = useState<string>('all');
  const [syncFilter,   setSyncFilter]   = useState<string>('all');

  const qs = new URLSearchParams();
  if (healthFilter !== 'all') qs.set('health_status', healthFilter);
  if (syncFilter   !== 'all') qs.set('sync_status',   syncFilter);

  const { data: appsRaw, loading, refetch } = useApi<any>(`/gitops?${qs}`);
  const { data: statsRaw }                  = useApi<any>('/gitops/stats/summary');

  const apps:  GitOpsApp[]  = appsRaw?.data  ?? appsRaw  ?? [];
  const stats: GitOpsStats | null = statsRaw?.data ?? null;
  const argocdConnected = stats?.argocd_connected ?? false;

  // History for rollback dialog
  const { data: rollbackHistRaw } = useApi<any>(rollbackApp ? `/gitops/${rollbackApp.id}/history?limit=10` : null);
  const rollbackHistory: HistoryEntry[] = rollbackHistRaw?.data ?? rollbackHistRaw ?? [];

  const handleSync = useCallback(async (id: string, hard = false) => {
    setBusy(p => ({ ...p, [id]: true }));
    try {
      await apiPost(`/gitops/${id}/sync`, { hard_sync: hard, dry_run: false });
      showToast(true, hard ? 'Hard sync triggered' : 'Sync triggered');
      refetch(true);
    } catch (e: any) { showToast(false, e.message ?? 'Sync failed'); }
    finally { setBusy(p => ({ ...p, [id]: false })); }
  }, [showToast, refetch]);

  const handleDelete = useCallback(async (id: string) => {
    setBusy(p => ({ ...p, [id]: true }));
    try {
      await apiDelete(`/gitops/${id}`);
      showToast(true, 'App removed');
      refetch(true);
    } catch (e: any) { showToast(false, e.message ?? 'Delete failed'); }
    finally { setBusy(p => ({ ...p, [id]: false })); }
  }, [showToast, refetch]);

  const handleRollback = useCallback(async (rev: string, msg: string) => {
    if (!rollbackApp) return;
    setBusy(p => ({ ...p, [rollbackApp.id]: true }));
    try {
      await apiPost(`/gitops/${rollbackApp.id}/rollback`, { revision: rev, message: msg });
      showToast(true, `Rolled back to ${rev.slice(0, 7)}`);
      setRollbackApp(null);
      refetch(true);
    } catch (e: any) { showToast(false, e.message ?? 'Rollback failed'); }
    finally { setBusy(p => ({ ...p, [rollbackApp!.id]: false })); }
  }, [rollbackApp, showToast, refetch]);

  // ── History detail view ──
  if (detailApp) {
    return <HistoryPanel app={detailApp} onBack={() => setDetailApp(null)} />;
  }

  return (
    <div>
      {/* Stats strip */}
      {stats && (
        <div className="flex gap-2 mb-4 flex-wrap">
          <StatPill label="Total"       value={stats.total}       color="text-white" />
          <StatPill label="Healthy"     value={stats.healthy}     color="text-green-400" />
          <StatPill label="Degraded"    value={stats.degraded}    color="text-red-400" />
          <StatPill label="Progressing" value={stats.progressing} color="text-blue-400" />
          <div className="flex-1" />
          <StatPill label="Synced"      value={stats.synced}      color="text-green-400" />
          <StatPill label="Out of Sync" value={stats.out_of_sync} color="text-yellow-400" />
          {/* ArgoCD status pill */}
          <div className={clsx('flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-medium',
            argocdConnected
              ? 'text-green-400 border-green-500/20 bg-green-500/5'
              : 'text-gray-500 border-white/10')}
            style={{ background: argocdConnected ? undefined : 'hsl(230 18% 9%)' }}>
            <Activity className={clsx('w-3 h-3', argocdConnected && 'animate-pulse')} />
            {argocdConnected ? 'ArgoCD Live' : 'ArgoCD: Not configured'}
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {/* Health filter */}
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'hsl(230 15% 10%)' }}>
          {(['all', 'Healthy', 'Degraded', 'Progressing'] as const).map(s => (
            <button key={s} onClick={() => setHealthFilter(s)}
              className={clsx('px-2.5 py-1 rounded-md text-xs font-medium transition-all',
                healthFilter === s ? 'text-white' : 'text-gray-500 hover:text-gray-300')}
              style={healthFilter === s ? { background: 'hsl(230 15% 16%)' } : {}}>
              {s}
            </button>
          ))}
        </div>
        {/* Sync filter */}
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'hsl(230 15% 10%)' }}>
          {(['all', 'Synced', 'OutOfSync'] as const).map(s => (
            <button key={s} onClick={() => setSyncFilter(s)}
              className={clsx('px-2.5 py-1 rounded-md text-xs font-medium transition-all',
                syncFilter === s ? 'text-white' : 'text-gray-500 hover:text-gray-300')}
              style={syncFilter === s ? { background: 'hsl(230 15% 16%)' } : {}}>
              {s === 'OutOfSync' ? 'Out of Sync' : s}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors">
          <Plus className="w-3.5 h-3.5" />Register App
        </button>
      </div>

      {/* App grid */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="rounded-xl border p-4 animate-pulse h-28"
              style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 15%)' }} />
          ))}
        </div>
      )}

      {!loading && apps.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <GitBranch className="w-12 h-12 text-gray-700 mb-3" />
          <p className="text-sm font-medium text-gray-400 mb-1">No GitOps apps registered</p>
          <p className="text-xs text-gray-600 mb-4">
            Register your first application to manage continuous delivery here.
          </p>
          <button onClick={() => setShowAdd(true)}
            className="px-4 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors">
            Register first app
          </button>
        </div>
      )}

      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {apps.map(app => (
            <AppCard
              key={app.id}
              app={app}
              onSync={handleSync}
              onDelete={handleDelete}
              onHistory={app => setDetailApp(app)}
              onRollback={app => setRollbackApp(app)}
              busy={busy[app.id] ?? false}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Dialogs */}
      <AnimatePresence>
        {showAdd && <AddAppDialog onClose={() => setShowAdd(false)} onCreated={() => refetch(true)} />}
        {rollbackApp && (
          <RollbackDialog
            app={rollbackApp}
            history={rollbackHistory}
            onConfirm={handleRollback}
            onCancel={() => setRollbackApp(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
