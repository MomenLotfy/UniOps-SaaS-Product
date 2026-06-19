import { useEffect, useCallback, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, XCircle, CheckCircle, AlertTriangle, X, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { clsx } from 'clsx';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { useNotifications } from '@/contexts/NotificationContext';

interface ScanToast {
  id: string;
  type: 'completed' | 'failed';
  repoName: string;
  repoId?: string;
  score?: number;
  criticalCount?: number;
  highCount?: number;
  secretCount?: number;
  error?: string;
  createdAt: number;
}

function scoreColor(score: number): string {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-yellow-400';
  return 'text-red-400';
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#ef4444';
  const r = 16;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" className="flex-shrink-0">
      <circle cx="20" cy="20" r={r} fill="none" stroke="hsl(230 15% 18%)" strokeWidth="4" />
      <circle
        cx="20" cy="20" r={r} fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        transform="rotate(-90 20 20)"
        style={{ transition: 'stroke-dasharray 0.6s ease' }}
      />
      <text x="20" y="24" textAnchor="middle" fontSize="10" fontWeight="bold" fill={color}>
        {Math.round(score)}
      </text>
    </svg>
  );
}

function ScanToastCard({ toast, onDismiss }: { toast: ScanToast; onDismiss: (id: string) => void }) {
  const navigate = useNavigate();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [progress, setProgress] = useState(100);
  const DURATION = 10000;

  useEffect(() => {
    const start = Date.now();
    const tick = setInterval(() => {
      const elapsed = Date.now() - start;
      setProgress(Math.max(0, 100 - (elapsed / DURATION) * 100));
    }, 50);
    timerRef.current = setTimeout(() => onDismiss(toast.id), DURATION);
    return () => { clearInterval(tick); if (timerRef.current) clearTimeout(timerRef.current); };
  }, [toast.id, onDismiss]);

  const isCompleted = toast.type === 'completed';
  const hasIssues   = (toast.criticalCount ?? 0) > 0 || (toast.highCount ?? 0) > 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 60, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 60, scale: 0.9 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className="w-80 rounded-xl border shadow-2xl overflow-hidden"
      style={{ background: 'hsl(230 18% 9%)', borderColor: isCompleted ? 'hsl(220 90% 60% / 0.3)' : 'hsl(0 72% 51% / 0.3)' }}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          {isCompleted && toast.score != null
            ? <ScoreRing score={toast.score} />
            : (
              <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
                isCompleted ? 'bg-green-500/10' : 'bg-red-500/10')}>
                {isCompleted
                  ? <Shield className="w-5 h-5 text-green-400" />
                  : <XCircle className="w-5 h-5 text-red-400" />}
              </div>
            )
          }

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2 mb-0.5">
              <p className="text-xs font-semibold text-white">
                {isCompleted ? 'Scan Complete' : 'Scan Failed'}
              </p>
              <button onClick={() => onDismiss(toast.id)}
                className="text-gray-600 hover:text-gray-400 transition-colors flex-shrink-0">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <p className="text-xs text-gray-400 truncate font-mono">{toast.repoName}</p>

            {isCompleted && toast.score != null && (
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                {(toast.criticalCount ?? 0) > 0 && (
                  <span className="flex items-center gap-0.5 text-xs text-red-400 font-semibold">
                    <AlertTriangle className="w-3 h-3" />{toast.criticalCount} critical
                  </span>
                )}
                {(toast.highCount ?? 0) > 0 && (
                  <span className="text-xs text-orange-400">{toast.highCount} high</span>
                )}
                {(toast.secretCount ?? 0) > 0 && (
                  <span className="text-xs text-red-400 font-bold">⚠ {toast.secretCount} secrets</span>
                )}
                {!hasIssues && (
                  <span className="flex items-center gap-1 text-xs text-green-400">
                    <CheckCircle className="w-3 h-3" /> No critical issues
                  </span>
                )}
              </div>
            )}

            {!isCompleted && toast.error && (
              <p className="text-xs text-red-400/80 mt-1 line-clamp-2">{toast.error}</p>
            )}

            {isCompleted && (
              <button
                onClick={() => { navigate('/security'); onDismiss(toast.id); }}
                className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 mt-2 transition-colors"
              >
                <ExternalLink className="w-3 h-3" />View results
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="h-0.5 w-full" style={{ background: 'hsl(230 15% 14%)' }}>
        <div
          className={clsx('h-full transition-none', isCompleted ? 'bg-blue-500' : 'bg-red-500')}
          style={{ width: `${progress}%` }}
        />
      </div>
    </motion.div>
  );
}

export function ScanNotificationListener() {
  const { subscribe } = useWebSocket();
  const { addNotification } = useNotifications();
  const [toasts, setToasts] = useState<ScanToast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const addToast = useCallback((toast: Omit<ScanToast, 'id' | 'createdAt'>) => {
    const id = crypto.randomUUID();
    setToasts(prev => [{ ...toast, id, createdAt: Date.now() }, ...prev].slice(0, 4));
    return id;
  }, []);

  useEffect(() => {
    const unsubCompleted = subscribe('scan.completed', (data: any) => {
      const score = data?.security_score ?? null;
      const repo  = data?.repo_name ?? 'Unknown repo';
      const crit  = data?.critical_count ?? 0;
      const high  = data?.high_count ?? 0;
      const secs  = data?.secret_count ?? 0;

      addToast({
        type:          'completed',
        repoName:      repo,
        repoId:        data?.repo_id,
        score:         score,
        criticalCount: crit,
        highCount:     high,
        secretCount:   secs,
      });

      addNotification({
        title:   `Scan complete — ${repo}`,
        message: score != null
          ? `Security score: ${Math.round(score)}/100${crit > 0 ? ` · ${crit} critical` : ''}${secs > 0 ? ` · ${secs} secrets` : ''}`
          : 'Scan finished. View results in Security Center.',
        type:  crit > 0 || secs > 0 ? 'warning' : 'success',
        link:  '/security',
      });
    });

    const unsubFailed = subscribe('scan.failed', (data: any) => {
      const repo = data?.repo_name ?? 'Unknown repo';

      addToast({
        type:     'failed',
        repoName: repo,
        repoId:   data?.repo_id,
        error:    data?.error,
      });

      addNotification({
        title:   `Scan failed — ${repo}`,
        message: data?.error ?? 'The security scan encountered an error. Check the Security Center for details.',
        type:    'error',
        link:    '/security',
      });
    });

    return () => { unsubCompleted(); unsubFailed(); };
  }, [subscribe, addNotification, addToast]);

  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map(t => (
          <div key={t.id} className="pointer-events-auto">
            <ScanToastCard toast={t} onDismiss={dismiss} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}
