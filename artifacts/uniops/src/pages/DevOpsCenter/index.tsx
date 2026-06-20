// ─────────────────────────────────────────────────────────────────────────────
// DevOps Center — Epic 6 redesign
// 4-section top nav: Cluster Control Plane | Platform Observability |
//                    Delivery & GitOps     | Self-Service Catalog
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  RefreshCw, Server, GitBranch, Activity,
  BookOpen, Wifi, WifiOff,
} from 'lucide-react';
import { clsx } from 'clsx';
import { usePermissions } from '@/hooks/use-permissions';
import { useWebSocket } from '@/contexts/WebSocketContext';

import { StatCard, Toast } from './components';
import { ClusterControlPlane } from './ClusterControlPlane';
import { PlatformObservability } from './PlatformObservability';
import { DeliveryGitOps } from './DeliveryGitOps';
import { CatalogTab } from './CatalogTab';

import { useDevOpsIntegrations, usePods, usePipelines } from './hooks';
import type { DevOpsSection } from './types';

// ── Section config ─────────────────────────────────────────────────────────────
const SECTIONS: {
  id: DevOpsSection;
  label: string;
  sublabel: string;
  icon: React.ElementType;
  accent: string;
  accentBg: string;
}[] = [
  {
    id: 'control-plane',
    label: 'Cluster Control Plane',
    sublabel: 'Clusters · Pods · Workloads · Network · Jobs · Config · Autoscaling',
    icon: Server,
    accent: 'text-blue-400',
    accentBg: 'bg-blue-500/10 border-blue-500/25',
  },
  {
    id: 'observability',
    label: 'Platform Observability',
    sublabel: 'Metrics · Logs · Alerts',
    icon: Activity,
    accent: 'text-emerald-400',
    accentBg: 'bg-emerald-500/10 border-emerald-500/25',
  },
  {
    id: 'delivery',
    label: 'Delivery & GitOps',
    sublabel: 'GitOps · CI/CD Pipelines · Deploy History',
    icon: GitBranch,
    accent: 'text-purple-400',
    accentBg: 'bg-purple-500/10 border-purple-500/25',
  },
  {
    id: 'catalog',
    label: 'Self-Service Catalog',
    sublabel: 'Service Registry · Create Wizard',
    icon: BookOpen,
    accent: 'text-amber-400',
    accentBg: 'bg-amber-500/10 border-amber-500/25',
  },
];

// ─────────────────────────────────────────────────────────────────────────────
export default function DevOpsCenter() {
  const [section, setSection]         = useState<DevOpsSection>('control-plane');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toast, setToast]             = useState<{ ok: boolean; msg: string } | null>(null);

  const { status: wsStatus } = useWebSocket();
  const wsLive = wsStatus === 'connected';

  const { isAdmin, hasRole } = usePermissions();
  const canAct = isAdmin() || hasRole('devops');

  const { githubConnected } = useDevOpsIntegrations();
  const { podStats, refetch: refetchPods } = usePods();
  const { pipelineStats, refetch: refetchPipes } = usePipelines();

  const showToast = useCallback((ok: boolean, msg: string) => {
    setToast({ ok, msg });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    refetchPods(true);
    refetchPipes(true);
    await new Promise(r => setTimeout(r, 800));
    setIsRefreshing(false);
  }, [refetchPods, refetchPipes]);

  // Stat cards — global summary across all sections
  const podStatCards = [
    {
      label: 'Total Pods',
      value: podStats?.total ?? '—',
      sub: `${podStats?.running ?? 0} running`,
      color: 'text-blue-400',
    },
    {
      label: 'Failed Pods',
      value: podStats?.failed ?? '—',
      sub: `${podStats?.high_restart_count ?? 0} high restarts`,
      color: 'text-red-400',
      danger: true,
    },
    {
      label: 'CPU Usage',
      value: podStats?.cpu_usage_pct != null ? `${podStats.cpu_usage_pct.toFixed(0)}%` : '—',
      sub: 'cluster average',
      color: podStats?.cpu_usage_pct != null && podStats.cpu_usage_pct >= 80
        ? 'text-red-400'
        : podStats?.cpu_usage_pct != null && podStats.cpu_usage_pct >= 60
          ? 'text-yellow-400'
          : 'text-green-400',
    },
    {
      label: 'Pipeline Success',
      value: pipelineStats
        ? `${(pipelineStats.success_rate ?? 0).toFixed(0)}%`
        : '—',
      sub: `${pipelineStats?.total ?? 0} total runs`,
      color: pipelineStats && (pipelineStats.success_rate ?? 0) >= 90
        ? 'text-green-400'
        : pipelineStats && (pipelineStats.success_rate ?? 0) >= 70
          ? 'text-yellow-400'
          : 'text-purple-400',
    },
  ];

  const activeSection = SECTIONS.find(s => s.id === section)!;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>

      {/* ── Toast ────────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {toast && <Toast ok={toast.ok} msg={toast.msg} />}
      </AnimatePresence>

      {/* ── Header ───────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">DevOps Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Kubernetes · CI/CD · GitOps · Catalog ·{' '}
            <span className="text-xs text-gray-600">GitHub: </span>
            <span className={clsx('text-xs font-semibold', githubConnected ? 'text-green-400' : 'text-gray-500')}>
              {githubConnected ? 'CONNECTED' : 'NOT CONNECTED'}
            </span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Real-time status badge */}
          <div className={clsx(
            'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors',
            wsLive
              ? 'text-green-400 border-green-500/20 bg-green-500/5'
              : wsStatus === 'connecting'
                ? 'text-yellow-400 border-yellow-500/20 bg-yellow-500/5'
                : 'text-gray-500 border-border bg-transparent',
          )}>
            {wsLive
              ? <><Wifi className="w-3 h-3" />Live</>
              : wsStatus === 'connecting'
                ? <><Wifi className="w-3 h-3 animate-pulse" />Connecting</>
                : <><WifiOff className="w-3 h-3" />Offline</>
            }
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg border text-gray-300 hover:text-white hover:border-white/20 transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)', background: 'hsl(230 15% 11%)' }}
          >
            <RefreshCw className={clsx('w-3.5 h-3.5', isRefreshing && 'animate-spin')} />
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* ── Global stat cards ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {podStatCards.map((s, i) => (
          <StatCard key={s.label} {...s} delay={i * 0.07} />
        ))}
      </div>

      {/* ── Section navigation ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-6">
        {SECTIONS.map(sec => {
          const active = section === sec.id;
          return (
            <button
              key={sec.id}
              onClick={() => setSection(sec.id)}
              className={clsx(
                'text-left p-4 rounded-xl border transition-all group relative overflow-hidden',
                active
                  ? `${sec.accentBg} shadow-sm`
                  : 'border-transparent hover:border-white/10',
              )}
              style={!active ? { background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' } : {}}
            >
              <div className="flex items-start gap-3">
                <div className={clsx(
                  'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all',
                  active ? sec.accentBg : 'bg-white/5',
                )}>
                  <sec.icon className={clsx('w-4 h-4 transition-colors', active ? sec.accent : 'text-gray-500 group-hover:text-gray-300')} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className={clsx(
                    'text-sm font-semibold transition-colors leading-tight',
                    active ? 'text-white' : 'text-gray-400 group-hover:text-white',
                  )}>
                    {sec.label}
                  </p>
                  <p className="text-xs text-gray-600 mt-0.5 leading-tight hidden xl:block">
                    {sec.sublabel}
                  </p>
                </div>
              </div>
              {active && (
                <motion.div
                  layoutId="section-active-indicator"
                  className={clsx('absolute bottom-0 left-0 right-0 h-0.5', sec.accent.replace('text-', 'bg-'))}
                  transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Active section label ─────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 mb-4">
        <activeSection.icon className={clsx('w-4 h-4', activeSection.accent)} />
        <h2 className="text-sm font-semibold text-white">{activeSection.label}</h2>
        <span className="text-xs text-gray-600">/</span>
        <span className="text-xs text-gray-500">{activeSection.sublabel}</span>
      </div>

      {/* ── Section content ──────────────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        <motion.div
          key={section}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
        >
          {section === 'control-plane' && (
            <ClusterControlPlane showToast={showToast} />
          )}
          {section === 'observability' && (
            <PlatformObservability showToast={showToast} />
          )}
          {section === 'delivery' && (
            <DeliveryGitOps showToast={showToast} canAct={canAct} />
          )}
          {section === 'catalog' && (
            <CatalogTab showToast={showToast} />
          )}
        </motion.div>
      </AnimatePresence>

    </motion.div>
  );
}
