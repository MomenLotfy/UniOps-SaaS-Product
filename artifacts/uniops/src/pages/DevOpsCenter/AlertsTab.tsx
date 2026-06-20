// ─────────────────────────────────────────────────────────────────────────────
// AlertsTab — DevOps Alert Center (Epic 4)
// Acknowledge / Mute / Escalate / Resolve per alert
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bell, BellOff, AlertTriangle, CheckCircle2, XCircle,
  Info, ChevronDown, Clock, Loader2, Plus, Filter,
  ArrowUpCircle, Volume2, VolumeX, ShieldAlert,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost, apiDelete } from '@/hooks/use-api';

// ── Types ────────────────────────────────────────────────────────────────────

type AlertSeverity = 'critical' | 'warning' | 'info';
type AlertStatus   = 'firing' | 'acknowledged' | 'muted' | 'resolved';

interface DevOpsAlertItem {
  id:          string;
  name:        string;
  severity:    AlertSeverity;
  type:        string;
  resource?:   string;
  namespace?:  string;
  cluster_id?: string;
  message:     string;
  status:      AlertStatus;
  muted_until?:string;
  resolved_at?:string;
  fired_at?:   string;
  labels:      Record<string, string>;
  annotations: Record<string, string>;
  created_at:  string;
}

interface AlertStats {
  total: number; firing: number; acknowledged: number;
  muted: number; resolved: number;
  critical: number; warning: number; info: number;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const SEV_COLOR: Record<AlertSeverity, string> = {
  critical: 'text-red-400 border-red-500/30 bg-red-500/5',
  warning:  'text-yellow-400 border-yellow-500/30 bg-yellow-500/5',
  info:     'text-blue-400 border-blue-500/30 bg-blue-500/5',
};

const SEV_BADGE: Record<AlertSeverity, string> = {
  critical: 'bg-red-500/10 text-red-400 border-red-500/20',
  warning:  'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  info:     'bg-blue-500/10 text-blue-400 border-blue-500/20',
};

const STATUS_BADGE: Record<AlertStatus, string> = {
  firing:       'bg-red-500/10 text-red-400',
  acknowledged: 'bg-blue-500/10 text-blue-400',
  muted:        'bg-gray-500/10 text-gray-400',
  resolved:     'bg-green-500/10 text-green-400',
};

function SevIcon({ s }: { s: AlertSeverity }) {
  if (s === 'critical') return <ShieldAlert className="w-4 h-4 text-red-400" />;
  if (s === 'warning')  return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
  return <Info className="w-4 h-4 text-blue-400" />;
}

function timeAgo(ts?: string): string {
  if (!ts) return '—';
  try {
    const diff = Date.now() - new Date(ts).getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60)     return `${s}s ago`;
    if (s < 3600)   return `${Math.floor(s/60)}m ago`;
    if (s < 86400)  return `${Math.floor(s/3600)}h ago`;
    return `${Math.floor(s/86400)}d ago`;
  } catch { return '—'; }
}

// ── Stat pill ─────────────────────────────────────────────────────────────────

function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex flex-col items-center px-4 py-3 rounded-xl border min-w-[70px]"
      style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
      <span className={clsx('text-xl font-bold tabular-nums', color)}>{value}</span>
      <span className="text-xs text-gray-500 mt-0.5">{label}</span>
    </div>
  );
}

// ── Mute dialog ───────────────────────────────────────────────────────────────

function MuteDialog({ onConfirm, onCancel }: { onConfirm: (hours: number) => void; onCancel: () => void }) {
  const [hours, setHours] = useState(4);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.6)' }}>
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
        className="rounded-xl border p-5 w-72 shadow-2xl"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 18%)' }}>
        <p className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <VolumeX className="w-4 h-4 text-gray-400" /> Mute Alert
        </p>
        <p className="text-xs text-gray-400 mb-4">Suppress notifications for:</p>
        <div className="grid grid-cols-4 gap-1.5 mb-4">
          {[1, 2, 4, 8, 24, 48].map(h => (
            <button key={h} onClick={() => setHours(h)}
              className={clsx('py-1.5 rounded-lg text-xs font-medium border transition-all',
                hours === h ? 'border-blue-500/50 text-blue-400 bg-blue-500/10' : 'border-white/5 text-gray-400 hover:border-white/15')}>
              {h}h
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button onClick={onCancel} className="flex-1 py-2 rounded-lg text-xs text-gray-400 border border-white/10 hover:text-white transition-colors">Cancel</button>
          <button onClick={() => onConfirm(hours)} className="flex-1 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors">
            Mute {hours}h
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Create Alert Dialog ───────────────────────────────────────────────────────

const ALERT_TYPES = [
  'CrashLoopBackOff','High CPU','High Memory','Node Down',
  'Pipeline Failed','Deployment Failed','OOMKilled','Disk Pressure',
];

function CreateAlertDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ name:'', severity:'warning', type:'High CPU', resource:'', namespace:'', message:'' });
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState<string|null>(null);
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));
  const inputCls = "w-full px-3 py-2 rounded-lg text-sm text-white border outline-none focus:border-blue-500/50 transition-colors";
  const inputStyle = { background: 'hsl(230 15% 13%)', borderColor: 'hsl(230 15% 20%)' };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name || !form.message) { setError('Name and message are required'); return; }
    setSaving(true); setError(null);
    try {
      await apiPost('/devops-alerts', form);
      onCreated(); onClose();
    } catch (err: any) { setError(err?.message ?? 'Failed'); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.94 }}
        className="w-full max-w-md rounded-2xl border shadow-2xl" style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 18%)' }}>
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'hsl(230 15% 15%)' }}>
          <span className="font-semibold text-white text-sm flex items-center gap-2"><Bell className="w-4 h-4 text-yellow-400" />Create Alert</span>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors text-lg leading-none">×</button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Alert name *</label>
            <input value={form.name} onChange={e => set('name', e.target.value)} placeholder="Pod CrashLoopBackOff" className={inputCls} style={inputStyle} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Severity</label>
              <select value={form.severity} onChange={e => set('severity', e.target.value)} className={inputCls} style={inputStyle}>
                {['critical','warning','info'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Type</label>
              <select value={form.type} onChange={e => set('type', e.target.value)} className={inputCls} style={inputStyle}>
                {ALERT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Resource</label>
              <input value={form.resource} onChange={e => set('resource', e.target.value)} placeholder="pod-name" className={inputCls} style={inputStyle} />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Namespace</label>
              <input value={form.namespace} onChange={e => set('namespace', e.target.value)} placeholder="default" className={inputCls} style={inputStyle} />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Message *</label>
            <textarea value={form.message} onChange={e => set('message', e.target.value)} rows={2} placeholder="Pod has been restarting 5 times in the last 10 minutes…"
              className={clsx(inputCls, 'resize-none text-xs')} style={inputStyle} />
          </div>
          {error && <p className="text-xs text-red-400 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2 rounded-lg text-xs text-gray-400 border border-white/10 hover:text-white transition-colors">Cancel</button>
            <button type="submit" disabled={saving} className="flex-1 py-2 rounded-lg text-xs font-medium bg-yellow-500 hover:bg-yellow-400 text-black transition-colors disabled:opacity-60 flex items-center justify-center gap-1.5">
              {saving && <Loader2 className="w-3 h-3 animate-spin" />}
              {saving ? 'Creating…' : 'Create Alert'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

// ── Alert row ─────────────────────────────────────────────────────────────────

interface AlertRowProps {
  alert: DevOpsAlertItem;
  onAction: (id: string, action: 'acknowledge' | 'mute' | 'escalate' | 'resolve', opts?: any) => void;
  onDelete: (id: string) => void;
  busy: boolean;
}

function AlertRow({ alert: a, onAction, onDelete, busy }: AlertRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [muteDialog, setMuteDialog] = useState(false);

  return (
    <>
      <motion.div layout className={clsx('rounded-xl border p-4 transition-all', SEV_COLOR[a.severity])}
        initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-start gap-3">
          <SevIcon s={a.severity} />
          <div className="flex-1 min-w-0">
            {/* Top row */}
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <span className="text-sm font-semibold text-white">{a.name}</span>
              <span className={clsx('px-1.5 py-0.5 text-xs rounded border', SEV_BADGE[a.severity])}>{a.severity}</span>
              <span className={clsx('px-1.5 py-0.5 text-xs rounded', STATUS_BADGE[a.status])}>{a.status}</span>
              <span className="text-xs text-gray-600 ml-auto">{timeAgo(a.fired_at ?? a.created_at)}</span>
            </div>

            {/* Meta */}
            <div className="flex items-center gap-2 text-xs text-gray-500 mb-1.5">
              <span className="font-mono bg-white/5 px-1.5 py-0.5 rounded">{a.type}</span>
              {a.resource  && <span>· {a.resource}</span>}
              {a.namespace && <span>· {a.namespace}</span>}
            </div>

            {/* Message */}
            <p className="text-xs text-gray-400 line-clamp-2">{a.message}</p>

            {/* Muted until */}
            {a.status === 'muted' && a.muted_until && (
              <p className="text-xs text-gray-600 mt-1 flex items-center gap-1">
                <Clock className="w-3 h-3" />Muted until {new Date(a.muted_until).toLocaleTimeString()}
              </p>
            )}
          </div>

          {/* Expand */}
          <button onClick={() => setExpanded(v => !v)}
            className="text-gray-600 hover:text-gray-300 transition-colors flex-shrink-0 mt-0.5">
            <ChevronDown className={clsx('w-4 h-4 transition-transform', expanded && 'rotate-180')} />
          </button>
        </div>

        {/* Expanded actions */}
        <AnimatePresence>
          {expanded && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
              <div className="flex items-center gap-2 mt-3 pt-3 border-t flex-wrap" style={{ borderColor: 'hsl(230 15% 20%)' }}>
                {a.status === 'firing' && (
                  <>
                    <button onClick={() => onAction(a.id, 'acknowledge')} disabled={busy}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-blue-400 border border-blue-500/20 hover:border-blue-500/40 hover:bg-blue-500/5 transition-all disabled:opacity-50">
                      {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                      Acknowledge
                    </button>
                    <button onClick={() => setMuteDialog(true)} disabled={busy}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gray-400 border border-white/10 hover:border-white/20 transition-all disabled:opacity-50">
                      <VolumeX className="w-3 h-3" />Mute
                    </button>
                    <button onClick={() => onAction(a.id, 'escalate')} disabled={busy}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-red-400 border border-red-500/20 hover:border-red-500/40 hover:bg-red-500/5 transition-all disabled:opacity-50">
                      <ArrowUpCircle className="w-3 h-3" />Escalate
                    </button>
                  </>
                )}
                {(a.status === 'firing' || a.status === 'acknowledged') && (
                  <button onClick={() => onAction(a.id, 'resolve')} disabled={busy}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-green-400 border border-green-500/20 hover:border-green-500/40 hover:bg-green-500/5 transition-all disabled:opacity-50">
                    <CheckCircle2 className="w-3 h-3" />Resolve
                  </button>
                )}
                <button onClick={() => onDelete(a.id)} disabled={busy}
                  className="ml-auto flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs text-gray-600 hover:text-red-400 transition-colors">
                  <XCircle className="w-3 h-3" />Delete
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      <AnimatePresence>
        {muteDialog && (
          <MuteDialog
            onConfirm={(hours) => { setMuteDialog(false); onAction(a.id, 'mute', { mute_hours: hours }); }}
            onCancel={() => setMuteDialog(false)}
          />
        )}
      </AnimatePresence>
    </>
  );
}

// ── Main AlertsTab ────────────────────────────────────────────────────────────

interface AlertsTabProps {
  showToast: (ok: boolean, msg: string) => void;
}

export function AlertsTab({ showToast }: AlertsTabProps) {
  const [statusFilter,   setStatusFilter]   = useState<'all' | AlertStatus>('all');
  const [severityFilter, setSeverityFilter] = useState<'all' | AlertSeverity>('all');
  const [showCreate,     setShowCreate]     = useState(false);
  const [busy,           setBusy]           = useState<Record<string, boolean>>({});

  const qs = new URLSearchParams();
  if (statusFilter   !== 'all') qs.set('status',   statusFilter);
  if (severityFilter !== 'all') qs.set('severity', severityFilter);

  const { data: alertsRaw, loading, refetch } = useApi<any>(`/devops-alerts?${qs}`);
  const { data: statsRaw }                    = useApi<any>('/devops-alerts/stats');

  const alerts: DevOpsAlertItem[] = alertsRaw?.data ?? alertsRaw ?? [];
  const stats:  AlertStats | null  = statsRaw?.data ?? null;

  const handleAction = useCallback(async (id: string, action: string, opts?: any) => {
    setBusy(p => ({ ...p, [id]: true }));
    try {
      const body = opts ?? {};
      await apiPost(`/devops-alerts/${id}/${action}`, body);
      showToast(true, `Alert ${action}d`);
      refetch(true);
    } catch (e: any) {
      showToast(false, e.message ?? `${action} failed`);
    } finally {
      setBusy(p => ({ ...p, [id]: false }));
    }
  }, [showToast, refetch]);

  const handleDelete = useCallback(async (id: string) => {
    if (!window.confirm('Delete this alert?')) return;
    setBusy(p => ({ ...p, [id]: true }));
    try {
      await apiDelete(`/devops-alerts/${id}`);
      showToast(true, 'Alert deleted');
      refetch(true);
    } catch (e: any) {
      showToast(false, e.message ?? 'Delete failed');
    } finally {
      setBusy(p => ({ ...p, [id]: false }));
    }
  }, [showToast, refetch]);

  return (
    <div>
      {/* Stats strip */}
      {stats && (
        <div className="flex gap-2 mb-4 flex-wrap">
          <StatPill label="Total"    value={stats.total}        color="text-white" />
          <StatPill label="Firing"   value={stats.firing}       color="text-red-400" />
          <StatPill label="Acked"    value={stats.acknowledged} color="text-blue-400" />
          <StatPill label="Muted"    value={stats.muted}        color="text-gray-400" />
          <StatPill label="Resolved" value={stats.resolved}     color="text-green-400" />
          <div className="flex-1" />
          <StatPill label="Critical" value={stats.critical}     color="text-red-400" />
          <StatPill label="Warning"  value={stats.warning}      color="text-yellow-400" />
          <StatPill label="Info"     value={stats.info}         color="text-blue-400" />
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {/* Status filter */}
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'hsl(230 15% 10%)' }}>
          {(['all','firing','acknowledged','muted','resolved'] as const).map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={clsx('px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-all',
                statusFilter === s ? 'text-white' : 'text-gray-500 hover:text-gray-300')}
              style={statusFilter === s ? { background: 'hsl(230 15% 16%)' } : {}}>
              {s}
            </button>
          ))}
        </div>

        {/* Severity filter */}
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'hsl(230 15% 10%)' }}>
          {(['all','critical','warning','info'] as const).map(s => (
            <button key={s} onClick={() => setSeverityFilter(s)}
              className={clsx('px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-all',
                severityFilter === s ? 'text-white' : 'text-gray-500 hover:text-gray-300')}
              style={severityFilter === s ? { background: 'hsl(230 15% 16%)' } : {}}>
              {s}
            </button>
          ))}
        </div>

        <div className="flex-1" />
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-yellow-500 hover:bg-yellow-400 text-black transition-colors">
          <Plus className="w-3.5 h-3.5" />New Alert
        </button>
      </div>

      {/* Alert list */}
      {loading && (
        <div className="space-y-3">
          {[1,2,3].map(i => (
            <div key={i} className="rounded-xl border p-4 animate-pulse" style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
              <div className="h-4 w-48 rounded bg-white/5 mb-2" />
              <div className="h-3 w-64 rounded bg-white/5" />
            </div>
          ))}
        </div>
      )}

      {!loading && alerts.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Bell className="w-12 h-12 text-gray-700 mb-3" />
          <p className="text-sm font-medium text-gray-400 mb-1">No alerts</p>
          <p className="text-xs text-gray-600">
            {statusFilter !== 'all' || severityFilter !== 'all'
              ? 'No alerts match the current filters.'
              : 'Your infrastructure is healthy — no alerts firing.'}
          </p>
        </div>
      )}

      <div className="space-y-2">
        <AnimatePresence mode="popLayout">
          {alerts.map(a => (
            <AlertRow
              key={a.id}
              alert={a}
              onAction={handleAction}
              onDelete={handleDelete}
              busy={busy[a.id] ?? false}
            />
          ))}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {showCreate && (
          <CreateAlertDialog onClose={() => setShowCreate(false)} onCreated={() => refetch(true)} />
        )}
      </AnimatePresence>
    </div>
  );
}
