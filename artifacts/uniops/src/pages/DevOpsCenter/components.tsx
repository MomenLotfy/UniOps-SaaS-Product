// ─────────────────────────────────────────────────────────────────────────────
// DevOpsCenter — reusable sub-components
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle, X, Loader2, Activity, RotateCcw, Trash2,
  Terminal, FileText, ChevronDown, ChevronRight, CheckCircle,
  XCircle, Clock, ExternalLink, Copy, Check, Zap,
  MoreVertical, Server, GitBranch, Minus, Plus, Maximize2,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import { usePodLogs } from './hooks';
import type { PodRow, PipelineRow, PodStatus, PipelineStatus, LogLine } from './types';

// ── Colour helpers ────────────────────────────────────────────────────────────
export const POD_STATUS_DOT: Record<string, string> = {
  Running:          'bg-green-500',
  Pending:          'bg-yellow-500',
  Failed:           'bg-red-500',
  CrashLoopBackOff: 'bg-red-500',
  OOMKilled:        'bg-red-400',
  Terminating:      'bg-orange-400',
  Completed:        'bg-blue-400',
  Error:            'bg-red-500',
  Unknown:          'bg-gray-500',
};
export const POD_STATUS_TEXT: Record<string, string> = {
  Running:          'text-green-400',
  Pending:          'text-yellow-400',
  Failed:           'text-red-400',
  CrashLoopBackOff: 'text-red-400',
  OOMKilled:        'text-red-400',
  Terminating:      'text-orange-400',
  Completed:        'text-blue-400',
  Error:            'text-red-400',
};
export const PIPE_STATUS_COLOR: Record<string, string> = {
  success:     'text-green-400',
  failed:      'text-red-400',
  error:       'text-red-400',
  running:     'text-blue-400',
  in_progress: 'text-blue-400',
  pending:     'text-yellow-400',
  queued:      'text-yellow-400',
  cancelled:   'text-gray-400',
  canceled:    'text-gray-400',
  skipped:     'text-gray-500',
  timed_out:   'text-orange-400',
};
export const PIPE_STATUS_DOT: Record<string, string> = {
  success:     'bg-green-500',
  failed:      'bg-red-500',
  error:       'bg-red-500',
  running:     'bg-blue-400',
  in_progress: 'bg-blue-400',
  pending:     'bg-yellow-400',
  queued:      'bg-yellow-400',
  cancelled:   'bg-gray-500',
  canceled:    'bg-gray-500',
  skipped:     'bg-gray-600',
  timed_out:   'bg-orange-400',
};
export const RERUNNABLE = new Set(['failed','cancelled','canceled','error','timed_out','skipped']);
export const ACTIVE     = new Set(['running','queued','pending','in_progress','waiting']);

// ── ConfirmDialog ─────────────────────────────────────────────────────────────
interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  danger?: boolean;
  loading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}
export function ConfirmDialog({
  open, title, description, confirmLabel, danger = false,
  loading, onConfirm, onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="relative z-10 w-full max-w-md mx-4 rounded-xl border p-6 shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}
      >
        <div className="flex items-start gap-3 mb-5">
          <div className={clsx('p-2 rounded-lg flex-shrink-0', danger ? 'bg-red-500/10' : 'bg-yellow-500/10')}>
            <AlertTriangle className={clsx('w-5 h-5', danger ? 'text-red-400' : 'text-yellow-400')} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
            <p className="text-xs text-gray-400 leading-relaxed">{description}</p>
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} disabled={loading}
            className="px-4 py-2 text-xs rounded-lg border text-gray-400 hover:text-white transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>
            Cancel
          </button>
          <button onClick={onConfirm} disabled={loading}
            className={clsx(
              'px-4 py-2 text-xs rounded-lg font-semibold flex items-center gap-2 transition-all',
              danger ? 'bg-red-500 hover:bg-red-600 text-white' : 'bg-orange-500 hover:bg-orange-600 text-white',
              loading && 'opacity-60 cursor-not-allowed',
            )}>
            {loading && <Loader2 className="w-3 h-3 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
export function RowSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-14 rounded-lg animate-pulse"
          style={{ background: 'hsl(230 15% 12%)', opacity: 1 - i * 0.15 }} />
      ))}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
interface EmptyStateProps {
  icon: React.ElementType;
  title: string;
  description: string;
  action?: { label: string; href?: string; onClick?: () => void };
}
export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
        style={{ background: 'hsl(230 15% 14%)' }}>
        <Icon className="w-7 h-7 text-gray-600" />
      </div>
      <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
      <p className="text-xs text-gray-500 max-w-xs leading-relaxed mb-4">{description}</p>
      {action && (
        action.href ? (
          <a href={action.href}
            className="px-4 py-2 text-xs rounded-lg font-semibold transition-all"
            style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
            {action.label}
          </a>
        ) : (
          <button onClick={action.onClick}
            className="px-4 py-2 text-xs rounded-lg font-semibold transition-all"
            style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
            {action.label}
          </button>
        )
      )}
    </div>
  );
}

// ── Toast ─────────────────────────────────────────────────────────────────────
interface ToastProps { ok: boolean; msg: string }
export function Toast({ ok, msg }: ToastProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -12, x: 12 }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      exit={{ opacity: 0, y: -12, x: 12 }}
      className={clsx(
        'fixed top-4 right-4 z-[60] flex items-center gap-2 px-4 py-2.5',
        'rounded-lg text-sm font-medium shadow-2xl border',
        ok
          ? 'bg-green-500/10 border-green-500/20 text-green-400'
          : 'bg-red-500/10 border-red-500/20 text-red-400',
      )}
    >
      {ok ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
      {msg}
    </motion.div>
  );
}

// ── StatCard ──────────────────────────────────────────────────────────────────
interface StatCardProps {
  label: string;
  value: string | number;
  sub: string;
  color: string;
  danger?: boolean;
  delay?: number;
}
export function StatCard({ label, value, sub, color, danger, delay = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      className="rounded-xl border p-4"
      style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}
    >
      <div className={clsx(
        'text-2xl font-bold mb-1 tabular-nums',
        danger && Number(value) > 0 ? 'text-red-400' : color,
      )}>
        {value}
      </div>
      <div className="text-sm font-medium text-white">{label}</div>
      <div className="text-xs text-gray-500 mt-0.5">{sub}</div>
    </motion.div>
  );
}

// ── Log Viewer Dialog ──────────────────────────────────────────────────────────
interface LogViewerProps { podId: string; podName: string; onClose: () => void }
export function LogViewerDialog({ podId, podName, onClose }: LogViewerProps) {
  const { lines, loading, error } = usePodLogs(podId, true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied]       = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [lines, autoScroll]);

  const handleCopy = () => {
    navigator.clipboard.writeText(lines.map(l => l.text).join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
        className="relative z-10 w-full max-w-4xl h-[70vh] flex flex-col rounded-xl border shadow-2xl overflow-hidden"
        style={{ background: '#0d0d14', borderColor: 'hsl(230 15% 16%)' }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b flex-shrink-0"
          style={{ borderColor: 'hsl(230 15% 16%)', background: 'hsl(230 15% 8%)' }}>
          <FileText className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-semibold text-white flex-1 truncate">
            Logs — {podName}
          </span>
          <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer">
            <input type="checkbox" checked={autoScroll}
              onChange={e => setAutoScroll(e.target.checked)}
              className="w-3 h-3 rounded" />
            Auto-scroll
          </label>
          <button onClick={handleCopy}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors px-2 py-1 rounded hover:bg-white/5">
            {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-white/5 text-gray-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Log body */}
        <div className="flex-1 overflow-y-auto font-mono text-xs p-4 space-y-0.5">
          {loading && (
            <div className="flex items-center gap-2 text-gray-400 py-8 justify-center">
              <Loader2 className="w-4 h-4 animate-spin" /> Fetching logs...
            </div>
          )}
          {error && (
            <div className="text-red-400 py-4 text-center">{error}</div>
          )}
          {!loading && lines.length === 0 && !error && (
            <div className="text-gray-500 py-8 text-center">No log output</div>
          )}
          {lines.map((line: LogLine, i: number) => (
            <div key={i} className="flex gap-3 leading-5 hover:bg-white/5 rounded px-1">
              {line.timestamp && (
                <span className="text-gray-600 flex-shrink-0 select-none">
                  {new Date(line.timestamp).toLocaleTimeString()}
                </span>
              )}
              <span className={clsx(
                'break-all',
                line.text.toLowerCase().includes('error') || line.text.toLowerCase().includes('fatal')
                  ? 'text-red-400'
                  : line.text.toLowerCase().includes('warn')
                    ? 'text-yellow-400'
                    : 'text-gray-300',
              )}>{line.text}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Footer status */}
        <div className="px-4 py-2 border-t flex items-center gap-2 flex-shrink-0"
          style={{ borderColor: 'hsl(230 15% 16%)', background: 'hsl(230 15% 8%)' }}>
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-gray-500">Live streaming · {lines.length} lines</span>
        </div>
      </motion.div>
    </div>
  );
}

// ── Events Drawer ─────────────────────────────────────────────────────────────
interface EventsDrawerProps { pod: PodRow; onClose: () => void }
export function EventsDrawer({ pod, onClose }: EventsDrawerProps) {
  const { data: events, loading } = useApi<any[]>(`/kubernetes/pods/${pod.id}/events`);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="relative z-10 w-full max-w-lg h-full flex flex-col border-l shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}
      >
        <div className="flex items-center justify-between p-4 border-b flex-shrink-0"
          style={{ borderColor: 'hsl(230 15% 16%)' }}>
          <div>
            <p className="text-sm font-semibold text-white">{pod.name}</p>
            <p className="text-xs text-gray-400">{pod.namespace} · K8s Events</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-white/5 text-gray-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading && (
            <div className="flex items-center gap-2 text-gray-400 text-xs py-6 justify-center">
              <Loader2 className="w-4 h-4 animate-spin" /> Fetching events from cluster...
            </div>
          )}
          {!loading && (!events || events.length === 0) && (
            <p className="text-xs text-gray-500 py-6 text-center">No events for this pod.</p>
          )}
          {(events ?? []).map((ev: any, i: number) => (
            <div key={i} className="p-3 rounded-lg border text-xs space-y-1"
              style={{ background: 'hsl(230 15% 11%)', borderColor: 'hsl(230 15% 18%)' }}>
              <div className="flex items-center gap-2">
                <span className={clsx('font-semibold',
                  ev.type === 'Warning' ? 'text-yellow-400' : 'text-blue-400')}>
                  {ev.type}
                </span>
                <span className="text-gray-300 font-medium">{ev.reason}</span>
                {ev.count > 1 && <span className="ml-auto text-gray-500">×{ev.count}</span>}
              </div>
              <p className="text-gray-400 leading-relaxed">{ev.message}</p>
              {ev.last_time && (
                <p className="text-gray-600">{new Date(ev.last_time).toLocaleString()}</p>
              )}
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

// ── Jobs Drawer ───────────────────────────────────────────────────────────────
interface JobsDrawerProps { pipeline: PipelineRow; onClose: () => void }
export function JobsDrawer({ pipeline, onClose }: JobsDrawerProps) {
  const { data: jobs, loading } = useApi<any[]>(`/pipelines/${pipeline.id}/jobs`);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="relative z-10 w-full max-w-lg h-full flex flex-col border-l shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}
      >
        <div className="flex items-center justify-between p-4 border-b flex-shrink-0"
          style={{ borderColor: 'hsl(230 15% 16%)' }}>
          <div className="min-w-0 flex-1 pr-4">
            <p className="text-sm font-semibold text-white truncate">{pipeline.name}</p>
            <p className="text-xs text-gray-400">{pipeline.repository} · {pipeline.branch} · Jobs</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {pipeline.logs_url && (
              <a href={pipeline.logs_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors">
                <ExternalLink className="w-3 h-3" /> Open
              </a>
            )}
            <button onClick={onClose} className="p-1.5 rounded hover:bg-white/5 text-gray-400 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading && (
            <div className="flex items-center gap-2 text-gray-400 text-xs py-6 justify-center">
              <Loader2 className="w-4 h-4 animate-spin" /> Fetching jobs from provider...
            </div>
          )}
          {!loading && (!jobs || jobs.length === 0) && (
            <p className="text-xs text-gray-500 py-6 text-center">No jobs found for this run.</p>
          )}
          {(jobs ?? []).map((job: any, i: number) => {
            const dur = job.duration
              ? `${Math.floor(job.duration / 60)}m ${Math.round(job.duration % 60)}s`
              : null;
            return (
              <div key={job.id ?? i}
                className="flex items-center gap-3 p-3 rounded-lg border text-xs"
                style={{ background: 'hsl(230 15% 11%)', borderColor: 'hsl(230 15% 18%)' }}>
                <span className={clsx('w-2 h-2 rounded-full flex-shrink-0',
                  PIPE_STATUS_DOT[job.status] ?? 'bg-gray-500')} />
                <div className="flex-1 min-w-0">
                  <p className="text-white font-medium truncate">{job.name}</p>
                  {job.stage && <p className="text-gray-500 text-xs">{job.stage}</p>}
                </div>
                <div className="text-right">
                  <p className={clsx('font-medium', PIPE_STATUS_COLOR[job.status] ?? 'text-gray-400')}>
                    {job.status}
                  </p>
                  {dur && <p className="text-gray-500">{dur}</p>}
                </div>
                {job.web_url && (
                  <a href={job.web_url} target="_blank" rel="noopener noreferrer"
                    className="text-gray-600 hover:text-blue-400 transition-colors">
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}

// ── Pod expanded detail ───────────────────────────────────────────────────────
export function PodDetail({ pod }: { pod: PodRow }) {
  const containers = pod.containers ?? [];
  return (
    <div className="px-4 pb-4 pt-2 space-y-4 border-t"
      style={{ borderColor: 'hsl(230 15% 16%)' }}>
      {/* Containers */}
      {containers.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-400 mb-2">Containers</p>
          <div className="space-y-1">
            {containers.map((c: any) => (
              <div key={c.name}
                className="flex items-center gap-3 text-xs p-2 rounded"
                style={{ background: 'hsl(230 15% 13%)' }}>
                <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0',
                  c.ready ? 'bg-green-500' : 'bg-red-500')} />
                <span className="font-medium text-white flex-1 truncate">{c.name}</span>
                <span className="text-gray-500 font-mono truncate max-w-[160px]">{c.image}</span>
                <span className={c.ready ? 'text-green-400' : 'text-red-400'}>
                  {c.ready ? 'Ready' : 'Not Ready'}
                </span>
                {c.restartCount > 0 && (
                  <span className="text-yellow-400">↺ {c.restartCount}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Resource bars */}
      {(pod.cpu_usage_pct != null || pod.memory_usage_pct != null) && (
        <div className="grid grid-cols-2 gap-4">
          {pod.cpu_usage_pct != null && (
            <ResourceBar label="CPU" pct={pod.cpu_usage_pct} />
          )}
          {pod.memory_usage_pct != null && (
            <ResourceBar label="Memory" pct={pod.memory_usage_pct} />
          )}
        </div>
      )}

      {/* Meta */}
      <div className="flex gap-4 text-xs text-gray-500">
        {pod.node && <span>Node: <span className="text-gray-300 font-mono">{pod.node}</span></span>}
        <span>Created: <span className="text-gray-300">{new Date(pod.created_at).toLocaleDateString()}</span></span>
      </div>
    </div>
  );
}

function ResourceBar({ label, pct }: { label: string; pct: number }) {
  const color = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981';
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-400">{label}</span>
        <span className="font-medium text-white">{pct.toFixed(0)}%</span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'hsl(230 15% 18%)' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

// ── Exec Terminal Dialog ──────────────────────────────────────────────────────
interface ExecTerminalProps { pod: PodRow; onClose: () => void }
export function ExecTerminalDialog({ pod, onClose }: ExecTerminalProps) {
  const [input, setInput]       = useState('');
  const [history, setHistory]   = useState<{ cmd: string; out: string }[]>([
    { cmd: '', out: `Connected to ${pod.name}\r\nType a command and press Enter.\r\n` },
  ]);
  const [busy, setBusy]         = useState(false);
  const bottomRef               = useRef<HTMLDivElement>(null);
  const inputRef                = useRef<HTMLInputElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    inputRef.current?.focus();
  }, [history]);

  const runCommand = async () => {
    const cmd = input.trim();
    if (!cmd || busy) return;
    setInput('');
    setBusy(true);
    try {
      const { apiPost: post } = await import('@/hooks/use-api');
      const json: any = await post(`/kubernetes/pods/${pod.id}/exec`, { command: cmd });
      const out = json?.output ?? json?.data?.output ?? '(no output)';
      setHistory(h => [...h, { cmd, out: String(out) }]);
    } catch (e: any) {
      setHistory(h => [...h, { cmd, out: `Error: ${e.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
        className="relative z-10 w-full max-w-3xl h-[60vh] flex flex-col rounded-xl border shadow-2xl overflow-hidden"
        style={{ background: '#0a0a10', borderColor: 'hsl(230 15% 18%)' }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b flex-shrink-0"
          style={{ borderColor: 'hsl(230 15% 16%)', background: 'hsl(230 15% 8%)' }}>
          <Terminal className="w-4 h-4 text-green-400" />
          <span className="text-sm font-semibold text-white flex-1 truncate">
            Exec — {pod.name}
          </span>
          <span className="text-xs text-gray-500 font-mono">{pod.namespace}</span>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-white/5 text-gray-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Output */}
        <div className="flex-1 overflow-y-auto p-4 font-mono text-xs text-green-300 space-y-2"
          onClick={() => inputRef.current?.focus()}>
          {history.map((h, i) => (
            <div key={i}>
              {h.cmd && (
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-green-500 select-none">$</span>
                  <span className="text-white">{h.cmd}</span>
                </div>
              )}
              <pre className="whitespace-pre-wrap text-green-300/80 leading-5">{h.out}</pre>
            </div>
          ))}
          {busy && (
            <div className="flex items-center gap-2 text-green-500">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Running...</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="flex items-center gap-2 px-4 py-3 border-t flex-shrink-0"
          style={{ borderColor: 'hsl(230 15% 16%)', background: 'hsl(230 15% 8%)' }}>
          <span className="text-green-500 font-mono text-sm select-none flex-shrink-0">$</span>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && runCommand()}
            disabled={busy}
            placeholder="enter command..."
            className="flex-1 bg-transparent text-xs font-mono text-white outline-none placeholder-gray-600"
            autoFocus
          />
          <button onClick={runCommand} disabled={busy || !input.trim()}
            className="text-xs px-3 py-1.5 rounded-md font-medium transition-colors disabled:opacity-30"
            style={{ background: 'hsl(220 90% 55%)', color: 'white' }}>
            Run
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Scale Dialog ──────────────────────────────────────────────────────────────
interface ScaleDialogProps {
  pod: PodRow;
  onClose: () => void;
  onScaled: (msg: string) => void;
}
export function ScaleDialog({ pod, onClose, onScaled }: ScaleDialogProps) {
  const [replicas, setReplicas] = useState(1);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  // Derive deployment name from pod name (strip random suffix)
  const deploymentName = pod.name.replace(/-[a-z0-9]{5,10}-[a-z0-9]{5}$/, '')
                                  .replace(/-[a-z0-9]{10}$/, '');

  const handleScale = async () => {
    setLoading(true); setError(null);
    try {
      const { apiPost: post } = await import('@/hooks/use-api');
      const json: any = await post(`/kubernetes/deployments/${deploymentName}/scale`, { replicas, namespace: pod.namespace });
      onScaled((json as any)?.message ?? `Scaled ${deploymentName} to ${replicas} replicas`);
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="relative z-10 w-full max-w-sm mx-4 rounded-xl border p-6 shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 rounded-lg bg-blue-500/10 flex-shrink-0">
            <Maximize2 className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Scale Deployment</h3>
            <p className="text-xs text-gray-400 mt-0.5 font-mono">{deploymentName}</p>
          </div>
        </div>

        <div className="mb-5">
          <label className="text-xs text-gray-400 mb-2 block">Replicas</label>
          <div className="flex items-center gap-3">
            <button onClick={() => setReplicas(r => Math.max(0, r - 1))}
              className="w-9 h-9 rounded-lg border flex items-center justify-center text-gray-300 hover:text-white hover:bg-white/5 transition-colors"
              style={{ borderColor: 'hsl(230 15% 22%)' }}>
              <Minus className="w-4 h-4" />
            </button>
            <input
              type="number" min={0} max={50} value={replicas}
              onChange={e => setReplicas(Math.max(0, Math.min(50, Number(e.target.value))))}
              className="flex-1 text-center text-2xl font-bold text-white bg-transparent outline-none border rounded-lg py-2"
              style={{ borderColor: 'hsl(230 15% 22%)' }}
            />
            <button onClick={() => setReplicas(r => Math.min(50, r + 1))}
              className="w-9 h-9 rounded-lg border flex items-center justify-center text-gray-300 hover:text-white hover:bg-white/5 transition-colors"
              style={{ borderColor: 'hsl(230 15% 22%)' }}>
              <Plus className="w-4 h-4" />
            </button>
          </div>
          {replicas === 0 && (
            <p className="text-xs text-yellow-400 mt-2 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> Setting to 0 will stop all pods
            </p>
          )}
        </div>

        {error && <p className="text-xs text-red-400 mb-3">{error}</p>}

        <div className="flex gap-2">
          <button onClick={onClose} disabled={loading}
            className="flex-1 py-2 text-xs rounded-lg border text-gray-400 hover:text-white transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>
            Cancel
          </button>
          <button onClick={handleScale} disabled={loading}
            className="flex-1 py-2 text-xs rounded-lg font-semibold flex items-center justify-center gap-2 transition-all"
            style={{ background: 'hsl(220 90% 55%)', color: 'white', opacity: loading ? 0.6 : 1 }}>
            {loading && <Loader2 className="w-3 h-3 animate-spin" />}
            Apply Scale
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── PodRow (full table row) ────────────────────────────────────────────────────
interface PodTableRowProps {
  pod: PodRow;
  canAct: boolean;
  onRestart: (pod: PodRow) => void;
  onDelete: (pod: PodRow) => void;
  onViewEvents: (pod: PodRow) => void;
  onViewLogs: (pod: PodRow) => void;
  onExec: (pod: PodRow) => void;
  onScale: (pod: PodRow) => void;
}
export function PodTableRow({
  pod, canAct, onRestart, onDelete, onViewEvents, onViewLogs, onExec, onScale,
}: PodTableRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const isCritical = ['Failed','CrashLoopBackOff','OOMKilled','Error'].includes(pod.status);

  return (
    <div className={clsx(
      'rounded-lg border overflow-hidden transition-all',
      isCritical
        ? 'border-red-500/20 bg-red-500/3'
        : 'border-border',
    )}
      style={!isCritical ? { background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' } : {}}>
      {/* Main row */}
      <div className="flex items-center gap-3 p-3 cursor-pointer select-none"
        onClick={() => setExpanded(v => !v)}>
        {/* Expand chevron */}
        <ChevronDown className={clsx(
          'w-3.5 h-3.5 text-gray-600 transition-transform flex-shrink-0',
          expanded && 'rotate-180',
        )} />

        {/* Status dot */}
        <span className={clsx('w-2 h-2 rounded-full flex-shrink-0',
          POD_STATUS_DOT[pod.status] ?? 'bg-gray-500',
          (pod.status === 'Running') && 'shadow-[0_0_4px_1px] shadow-green-500/40',
        )} />

        {/* Name + namespace */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-white truncate">{pod.name}</span>
            {isCritical && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 font-medium flex-shrink-0">
                {pod.status}
              </span>
            )}
          </div>
          <div className="text-xs text-gray-500">{pod.namespace}{pod.cluster ? ` · ${pod.cluster}` : ''}</div>
        </div>

        {/* Status text (non-critical) */}
        {!isCritical && (
          <div className="hidden sm:block text-center min-w-[88px]">
            <span className={clsx('text-xs font-medium', POD_STATUS_TEXT[pod.status] ?? 'text-gray-400')}>
              {pod.status}
            </span>
            {pod.restart_count > 0 && (
              <div className="text-xs text-yellow-400">↺ {pod.restart_count}</div>
            )}
          </div>
        )}

        {/* CPU / Mem */}
        <div className="hidden md:flex gap-4 text-xs text-gray-400 min-w-[100px] justify-end">
          {pod.cpu_usage_pct != null && (
            <span className={clsx(pod.cpu_usage_pct >= 90 ? 'text-red-400' : pod.cpu_usage_pct >= 70 ? 'text-yellow-400' : '')}>
              CPU {pod.cpu_usage_pct.toFixed(0)}%
            </span>
          )}
          {pod.memory_usage_pct != null && (
            <span className={clsx(pod.memory_usage_pct >= 90 ? 'text-red-400' : pod.memory_usage_pct >= 70 ? 'text-yellow-400' : '')}>
              Mem {pod.memory_usage_pct.toFixed(0)}%
            </span>
          )}
        </div>

        {/* Action menu */}
        <div className="relative flex-shrink-0" onClick={e => e.stopPropagation()}>
          <button onClick={() => setMenuOpen(v => !v)}
            className="p-1.5 rounded-md text-gray-500 hover:text-white hover:bg-white/5 transition-colors">
            <MoreVertical className="w-4 h-4" />
          </button>
          <AnimatePresence>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: -4 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: -4 }}
                  transition={{ duration: 0.1 }}
                  className="absolute right-0 top-8 z-20 w-44 rounded-lg border shadow-2xl py-1 text-xs"
                  style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 20%)' }}
                >
                  <button onClick={() => { setMenuOpen(false); onViewLogs(pod); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-gray-300 hover:text-white hover:bg-white/5 transition-colors">
                    <FileText className="w-3.5 h-3.5 text-blue-400" /> Stream Logs
                  </button>
                  <button onClick={() => { setMenuOpen(false); onViewEvents(pod); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-gray-300 hover:text-white hover:bg-white/5 transition-colors">
                    <Activity className="w-3.5 h-3.5 text-purple-400" /> View Events
                  </button>
                  {canAct && (
                    <>
                      <button onClick={() => { setMenuOpen(false); onExec(pod); }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-gray-300 hover:text-white hover:bg-white/5 transition-colors">
                        <Terminal className="w-3.5 h-3.5 text-green-400" /> Exec Terminal
                      </button>
                      <div className="my-1 border-t" style={{ borderColor: 'hsl(230 15% 18%)' }} />
                      <button onClick={() => { setMenuOpen(false); onScale(pod); }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-gray-300 hover:text-white hover:bg-white/5 transition-colors">
                        <Maximize2 className="w-3.5 h-3.5 text-blue-400" /> Scale
                      </button>
                      <button onClick={() => { setMenuOpen(false); onRestart(pod); }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-gray-300 hover:text-white hover:bg-white/5 transition-colors">
                        <RotateCcw className="w-3.5 h-3.5 text-orange-400" /> Restart Pod
                      </button>
                      <button onClick={() => { setMenuOpen(false); onDelete(pod); }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-red-400 hover:text-red-300 hover:bg-red-500/5 transition-colors">
                        <Trash2 className="w-3.5 h-3.5" /> Force Delete
                      </button>
                    </>
                  )}
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Expanded detail */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            <PodDetail pod={pod} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── PipelineTableRow ──────────────────────────────────────────────────────────
interface PipelineTableRowProps {
  pipeline: PipelineRow;
  canAct: boolean;
  onRerun: (p: PipelineRow, failedOnly: boolean) => void;
  onCancel?: (p: PipelineRow) => void;
  onViewJobs: (p: PipelineRow) => void;
}
export function PipelineTableRow({ pipeline, canAct, onRerun, onCancel, onViewJobs }: PipelineTableRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const canRerun = canAct && RERUNNABLE.has(pipeline.status?.toLowerCase());
  const isActive = ACTIVE.has(pipeline.status?.toLowerCase());

  const stages = pipeline.stages ?? [];

  return (
    <div className="rounded-lg border overflow-hidden"
      style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
      {/* Main row */}
      <div className="flex items-center gap-3 p-3 cursor-pointer select-none"
        onClick={() => setExpanded(v => !v)}>
        <ChevronDown className={clsx(
          'w-3.5 h-3.5 text-gray-600 transition-transform flex-shrink-0',
          expanded && 'rotate-180',
        )} />

        {/* Status indicator */}
        <span className={clsx(
          'w-2 h-2 rounded-full flex-shrink-0',
          PIPE_STATUS_DOT[pipeline.status] ?? 'bg-gray-500',
          isActive && 'animate-pulse',
        )} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-white truncate">{pipeline.name}</span>
            {pipeline.author && (
              <span className="text-xs text-gray-500">by {pipeline.author}</span>
            )}
          </div>
          <div className="text-xs text-gray-500 flex items-center gap-2">
            <GitBranch className="w-3 h-3" />
            <span className="truncate">{pipeline.repository}</span>
            <span className="text-gray-600">·</span>
            <span>{pipeline.branch}</span>
            {pipeline.commit_sha && (
              <span className="font-mono opacity-50">#{pipeline.commit_sha.slice(0, 7)}</span>
            )}
          </div>
          {pipeline.commit_message && (
            <div className="text-xs text-gray-600 truncate mt-0.5">{pipeline.commit_message}</div>
          )}
        </div>

        <div className="text-right min-w-[80px] flex-shrink-0">
          <div className={clsx('text-xs font-medium', PIPE_STATUS_COLOR[pipeline.status] ?? 'text-gray-400')}>
            {isActive ? (
              <span className="flex items-center gap-1 justify-end">
                <Loader2 className="w-3 h-3 animate-spin" /> {pipeline.status}
              </span>
            ) : pipeline.status}
          </div>
          {pipeline.duration != null && (
            <div className="text-xs text-gray-500">
              {Math.floor(pipeline.duration / 60)}m {pipeline.duration % 60}s
            </div>
          )}
        </div>

        {/* Action menu */}
        <div className="relative flex-shrink-0" onClick={e => e.stopPropagation()}>
          <button onClick={() => setMenuOpen(v => !v)}
            className="p-1.5 rounded-md text-gray-500 hover:text-white hover:bg-white/5 transition-colors">
            <MoreVertical className="w-4 h-4" />
          </button>
          <AnimatePresence>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: -4 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: -4 }}
                  transition={{ duration: 0.1 }}
                  className="absolute right-0 top-8 z-20 w-52 rounded-lg border shadow-2xl py-1 text-xs"
                  style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 20%)' }}
                >
                  <button onClick={() => { setMenuOpen(false); onViewJobs(pipeline); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-gray-300 hover:text-white hover:bg-white/5">
                    <Activity className="w-3.5 h-3.5 text-blue-400" /> View Jobs
                  </button>
                  {pipeline.logs_url && (
                    <a href={pipeline.logs_url} target="_blank" rel="noopener noreferrer"
                      onClick={() => setMenuOpen(false)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-gray-300 hover:text-white hover:bg-white/5">
                      <ExternalLink className="w-3.5 h-3.5 text-gray-400" /> Open in GitHub
                    </a>
                  )}
                  {canAct && (
                    <>
                      <div className="my-1 border-t" style={{ borderColor: 'hsl(230 15% 18%)' }} />
                      {isActive ? (
                        onCancel ? (
                          <button onClick={() => { setMenuOpen(false); onCancel(pipeline); }}
                            className="w-full flex items-center gap-2 px-3 py-2 text-red-400 hover:text-red-300 hover:bg-red-500/5 transition-colors">
                            <XCircle className="w-3.5 h-3.5" /> Cancel Pipeline
                          </button>
                        ) : (
                          <div className="px-3 py-2 text-gray-600 flex items-center gap-2">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Running...
                          </div>
                        )
                      ) : (
                        <>
                          <button onClick={() => { setMenuOpen(false); onRerun(pipeline, true); }}
                            disabled={!canRerun}
                            className={clsx('w-full flex items-center gap-2 px-3 py-2 transition-colors',
                              canRerun
                                ? 'text-orange-300 hover:text-orange-200 hover:bg-orange-500/5'
                                : 'text-gray-600 cursor-not-allowed')}>
                            <RotateCcw className="w-3.5 h-3.5" /> Re-run Failed Jobs
                          </button>
                          <button onClick={() => { setMenuOpen(false); onRerun(pipeline, false); }}
                            disabled={!canRerun}
                            className={clsx('w-full flex items-center gap-2 px-3 py-2 transition-colors',
                              canRerun
                                ? 'text-yellow-300 hover:text-yellow-200 hover:bg-yellow-500/5'
                                : 'text-gray-600 cursor-not-allowed')}>
                            <Zap className="w-3.5 h-3.5" /> Re-run All Jobs
                          </button>
                        </>
                      )}
                    </>
                  )}
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Expanded stages */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            {stages.length > 0 ? (
              <div className="px-4 pb-4 pt-2 border-t space-y-2"
                style={{ borderColor: 'hsl(230 15% 16%)' }}>
                <p className="text-xs font-medium text-gray-400 mb-2">Stages</p>
                {stages.map((stage: any) => (
                  <div key={stage.id} className="flex items-center gap-3 text-xs p-2 rounded"
                    style={{ background: 'hsl(230 15% 13%)' }}>
                    <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0',
                      PIPE_STATUS_DOT[stage.status] ?? 'bg-gray-500')} />
                    <span className="font-medium text-white flex-1">{stage.name}</span>
                    <span className={PIPE_STATUS_COLOR[stage.status] ?? 'text-gray-400'}>
                      {stage.status}
                    </span>
                    {stage.duration != null && (
                      <span className="text-gray-500">
                        {Math.floor(stage.duration / 60)}m {stage.duration % 60}s
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-4 pb-4 pt-2 border-t text-xs text-gray-500"
                style={{ borderColor: 'hsl(230 15% 16%)' }}>
                No stage breakdown available — click "View Jobs" for details.
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── ClusterSection — reusable wrapper for cluster resource sections ───────────
interface ClusterSectionProps {
  title: string;
  icon: React.ElementType;
  count: number;
  loading: boolean;
  children: React.ReactNode;
}
export function ClusterSection({ title, icon: Icon, count, loading, children }: ClusterSectionProps) {
  return (
    <div className="rounded-xl border overflow-hidden"
      style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
      <div className="flex items-center justify-between px-5 py-4 border-b"
        style={{ borderColor: 'hsl(230 15% 15%)' }}>
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-semibold text-white">{title}</span>
          {!loading && (
            <span className="text-xs text-gray-500 font-mono">({count})</span>
          )}
        </div>
        {loading && <Loader2 className="w-4 h-4 text-gray-500 animate-spin" />}
      </div>
      <div className="p-4 space-y-2">
        {loading ? (
          <RowSkeleton rows={3} />
        ) : count === 0 ? (
          <p className="text-xs text-gray-500 py-4 text-center">No resources found</p>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
