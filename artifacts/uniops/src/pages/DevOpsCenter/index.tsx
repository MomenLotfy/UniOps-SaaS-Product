// ─────────────────────────────────────────────────────────────────────────────
// DevOps Center — main page
// Single export default, zero duplicates, full TypeScript
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  RefreshCw, Server, GitBranch, History,
  Plug, CheckCircle, Layers, Network,
  Clock, Settings2, Zap, Shield, Wifi, WifiOff,
} from 'lucide-react';
import { clsx } from 'clsx';
import { usePermissions } from '@/hooks/use-permissions';
import { useApi } from '@/hooks/use-api';
import { useWebSocket } from '@/contexts/WebSocketContext';

import {
  useDevOpsIntegrations,
  usePods,
  usePipelines,
  usePodActions,
  usePipelineActions,
} from './hooks';

import {
  ConfirmDialog, EmptyState, RowSkeleton, StatCard,
  Toast, EventsDrawer, JobsDrawer, LogViewerDialog,
  PodTableRow, PipelineTableRow,
  ExecTerminalDialog, ScaleDialog,
  ClusterSection,
} from './components';

import type { PodRow, PipelineRow, DevOpsTab } from './types';

// ── Tab config ────────────────────────────────────────────────────────────────
const TABS: { id: DevOpsTab; label: string; icon: React.ElementType }[] = [
  { id: 'kubernetes',   label: 'Pods',          icon: Server    },
  { id: 'workloads',    label: 'Workloads',      icon: Layers    },
  { id: 'network',      label: 'Network',        icon: Network   },
  { id: 'jobs',         label: 'Jobs',           icon: Clock     },
  { id: 'config',       label: 'Config',         icon: Settings2 },
  { id: 'hpa',          label: 'Autoscaling',    icon: Zap       },
  { id: 'pipelines',    label: 'CI/CD',          icon: GitBranch },
  { id: 'history',      label: 'History',        icon: History   },
];

// ─────────────────────────────────────────────────────────────────────────────
export default function DevOpsCenter() {
  const [tab, setTab]           = useState<DevOpsTab>('kubernetes');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // WebSocket status
  const { status: wsStatus } = useWebSocket();
  const wsLive = wsStatus === 'connected';

  // Permissions
  const { isAdmin, hasRole } = usePermissions();
  const canAct = isAdmin() || hasRole('devops');

  // Integration status
  const { k8sConnected, gitConnected, isLoading: intLoading } = useDevOpsIntegrations();

  // Data
  const { pods, podStats, loading: podsLoading, error: podsError, refetch: refetchPods } = usePods();
  const { pipelines, pipelineStats, loading: pipesLoading, error: pipesError, refetch: refetchPipes } = usePipelines();

  // ── Cluster-level data (lazy — only fetched when tab active) ───────────────
  const { data: deployData, loading: depsLoading, refetch: refetchDeps }
    = useApi<any>(tab === 'workloads' ? '/kubernetes/pods/workloads/deployments' : null);
  const { data: stsData,    loading: stsLoading }
    = useApi<any>(tab === 'workloads' ? '/kubernetes/pods/workloads/statefulsets' : null);
  const { data: dsData,     loading: dsLoading }
    = useApi<any>(tab === 'workloads' ? '/kubernetes/pods/workloads/daemonsets' : null);
  const { data: svcData,    loading: svcsLoading }
    = useApi<any>(tab === 'network' ? '/kubernetes/pods/network/services' : null);
  const { data: ingData,    loading: ingsLoading }
    = useApi<any>(tab === 'network' ? '/kubernetes/pods/network/ingresses' : null);
  const { data: jobsData,   loading: jobsLoading }
    = useApi<any>(tab === 'jobs' ? '/kubernetes/pods/batch/jobs' : null);
  const { data: cmData,     loading: cmsLoading }
    = useApi<any>(tab === 'config' ? '/kubernetes/pods/config/configmaps' : null);
  const { data: secData,    loading: secsLoading }
    = useApi<any>(tab === 'config' ? '/kubernetes/pods/config/secrets' : null);
  const { data: hpaData,    loading: hpaLoading }
    = useApi<any>(tab === 'hpa' ? '/kubernetes/pods/autoscaling/hpa' : null);

  // Actions
  const podActions  = usePodActions(refetchPods);
  const pipeActions = usePipelineActions(refetchPipes);

  // UI state
  const [confirmPodAction, setConfirmPodAction]     = useState<{ type: 'restart' | 'delete'; pod: PodRow } | null>(null);
  const [confirmRerun, setConfirmRerun]             = useState<{ pipeline: PipelineRow; failedOnly: boolean } | null>(null);
  const [confirmCancel, setConfirmCancel]           = useState<PipelineRow | null>(null);
  const [toast, setToast]                           = useState<{ ok: boolean; msg: string } | null>(null);
  const [eventsPod, setEventsPod]                   = useState<PodRow | null>(null);
  const [logsPod, setLogsPod]                       = useState<PodRow | null>(null);
  const [execPod, setExecPod]                       = useState<PodRow | null>(null);
  const [scalePod, setScalePod]                     = useState<PodRow | null>(null);
  const [jobsPipeline, setJobsPipeline]             = useState<PipelineRow | null>(null);

  const showToast = useCallback((ok: boolean, msg: string) => {
    setToast({ ok, msg });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    refetchPods();
    refetchPipes();
    await new Promise(r => setTimeout(r, 800));
    setIsRefreshing(false);
  }, [refetchPods, refetchPipes]);

  // ── Pod confirm action ──────────────────────────────────────────────────────
  const handlePodConfirm = async () => {
    if (!confirmPodAction) return;
    const { type, pod } = confirmPodAction;
    try {
      const msg = type === 'restart'
        ? await podActions.restart(pod.id)
        : await podActions.forceDelete(pod.id);
      showToast(true, msg);
    } catch (e: any) {
      showToast(false, e.message ?? 'Action failed');
    } finally {
      setConfirmPodAction(null);
    }
  };

  // ── Pipeline confirm re-run ────────────────────────────────────────────────
  const handlePipelineConfirm = async () => {
    if (!confirmRerun) return;
    const { pipeline, failedOnly } = confirmRerun;
    try {
      const msg = await pipeActions.rerun(pipeline.id, failedOnly);
      showToast(true, msg);
    } catch (e: any) {
      showToast(false, e.message ?? 'Re-run failed');
    } finally {
      setConfirmRerun(null);
    }
  };

  // ── Pipeline cancel ────────────────────────────────────────────────────────
  const handleCancelConfirm = async () => {
    if (!confirmCancel) return;
    try {
      const msg = await pipeActions.cancel(confirmCancel.id);
      showToast(true, msg);
    } catch (e: any) {
      showToast(false, e.message ?? 'Cancel failed');
    } finally {
      setConfirmCancel(null);
    }
  };

  // ── Stat cards ─────────────────────────────────────────────────────────────
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
      label: 'Memory Usage',
      value: podStats?.memory_usage_pct != null ? `${podStats.memory_usage_pct.toFixed(0)}%` : '—',
      sub: 'cluster average',
      color: podStats?.memory_usage_pct != null && podStats.memory_usage_pct >= 80
        ? 'text-red-400'
        : podStats?.memory_usage_pct != null && podStats.memory_usage_pct >= 60
          ? 'text-yellow-400'
          : 'text-purple-400',
    },
  ];

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>

      {/* ── Toast ──────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {toast && <Toast ok={toast.ok} msg={toast.msg} />}
      </AnimatePresence>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">DevOps Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">Kubernetes · CI/CD Pipelines · Deployments</p>
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

      {/* ── Stat cards ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {podStatCards.map((s, i) => (
          <StatCard key={s.label} {...s} delay={i * 0.07} />
        ))}
      </div>

      {/* ── Pipeline stats strip ────────────────────────────────────────────── */}
      {pipelineStats && (
        <div className="flex gap-4 px-4 py-3 rounded-xl border mb-5 text-xs"
          style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
          <div className="flex items-center gap-1.5">
            <span className="text-gray-400">Pipelines:</span>
            <span className="text-white font-semibold">{pipelineStats.total}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-gray-300">{pipelineStats.success} success</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            <span className="text-gray-300">{pipelineStats.failed} failed</span>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-gray-400">Success rate:</span>
            <span className={clsx('font-semibold',
              (pipelineStats.success_rate ?? 0) >= 90 ? 'text-green-400'
              : (pipelineStats.success_rate ?? 0) >= 70 ? 'text-yellow-400'
              : 'text-red-400')}>
              {(pipelineStats.success_rate ?? 0).toFixed(0)}%
            </span>
          </div>
        </div>
      )}

      {/* ── Tabs ───────────────────────────────────────────────────────────── */}
      <div className="flex gap-1 mb-5 p-1 rounded-lg"
        style={{ background: 'hsl(230 15% 10%)' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 text-xs rounded-md transition-all font-medium',
              tab === t.id
                ? 'bg-white/8 text-white shadow-sm'
                : 'text-gray-500 hover:text-gray-300',
            )}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Kubernetes Pods tab ─────────────────────────────────────────────── */}
      {tab === 'kubernetes' && (
        <div className="rounded-xl border overflow-hidden"
          style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
          {/* Section header */}
          <div className="flex items-center justify-between px-5 py-4 border-b"
            style={{ borderColor: 'hsl(230 15% 15%)' }}>
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-semibold text-white">Pods</span>
              {pods.length > 0 && (
                <span className="text-xs text-gray-500 font-mono">({pods.length})</span>
              )}
            </div>
            {canAct && k8sConnected && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <CheckCircle className="w-3 h-3 text-green-500" />
                Actions enabled
              </div>
            )}
          </div>

          <div className="p-4">
            {/* Not connected */}
            {!intLoading && !k8sConnected && (
              <EmptyState
                icon={Plug}
                title="Kubernetes not connected"
                description="Connect your Kubernetes cluster to monitor pods, view logs, and execute actions in real time."
                action={{ label: 'Connect Kubernetes Cluster', href: '/settings/integrations' }}
              />
            )}

            {/* Loading */}
            {k8sConnected && podsLoading && <RowSkeleton rows={6} />}

            {/* Error */}
            {k8sConnected && !podsLoading && podsError && (
              <div className="flex flex-col items-center gap-3 py-10 text-center">
                <p className="text-sm text-red-400">{podsError}</p>
                <button onClick={refetchPods}
                  className="text-xs px-3 py-1.5 rounded-lg text-gray-300 hover:text-white border border-border transition-colors">
                  Retry
                </button>
              </div>
            )}

            {/* Empty connected */}
            {k8sConnected && !podsLoading && !podsError && pods.length === 0 && (
              <EmptyState
                icon={Server}
                title="No pods running"
                description="Your cluster is connected but no pods were found. Deploy an application to get started."
              />
            )}

            {/* Pod list */}
            {k8sConnected && !podsLoading && pods.length > 0 && (
              <div className="space-y-2">
                {pods.map((pod: PodRow) => (
                  <PodTableRow
                    key={pod.id}
                    pod={pod}
                    canAct={canAct}
                    onRestart={p => setConfirmPodAction({ type: 'restart', pod: p })}
                    onDelete={p => setConfirmPodAction({ type: 'delete', pod: p })}
                    onViewEvents={p => setEventsPod(p)}
                    onViewLogs={p => setLogsPod(p)}
                    onExec={p => setExecPod(p)}
                    onScale={p => setScalePod(p)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Workloads tab ───────────────────────────────────────────────────── */}
      {tab === 'workloads' && (
        <div className="space-y-4">
          {/* Deployments */}
          <ClusterSection title="Deployments" icon={Layers} count={(deployData?.data ?? []).length} loading={depsLoading}>
            {(deployData?.data ?? []).map((d: any) => (
              <div key={`${d.namespace}/${d.name}`} className="p-3 rounded-lg border text-xs"
                style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white">{d.name}</p>
                    <p className="text-gray-500">{d.namespace}</p>
                  </div>
                  <div className="text-right">
                    <p className={clsx('font-semibold', d.ready_replicas === d.replicas ? 'text-green-400' : 'text-yellow-400')}>
                      {d.ready_replicas}/{d.replicas} ready
                    </p>
                    <p className="text-gray-500">{d.strategy}</p>
                  </div>
                  <div className="text-xs text-gray-600 max-w-[180px] truncate">
                    {d.images?.[0]}
                  </div>
                </div>
                {d.conditions?.some((c: any) => c.type === 'Available' && c.status !== 'True') && (
                  <p className="mt-1.5 text-yellow-400 flex items-center gap-1">
                    ⚠ {d.conditions.find((c: any) => c.type === 'Available')?.message}
                  </p>
                )}
              </div>
            ))}
          </ClusterSection>

          {/* StatefulSets */}
          <ClusterSection title="StatefulSets" icon={Server} count={(stsData?.data ?? []).length} loading={stsLoading}>
            {(stsData?.data ?? []).map((s: any) => (
              <div key={`${s.namespace}/${s.name}`} className="p-3 rounded-lg border text-xs"
                style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-white">{s.name}</p>
                    <p className="text-gray-500">{s.namespace} · svc: {s.service_name}</p>
                  </div>
                  <p className={clsx('font-semibold', s.ready_replicas === s.replicas ? 'text-green-400' : 'text-yellow-400')}>
                    {s.ready_replicas}/{s.replicas} ready
                  </p>
                </div>
              </div>
            ))}
          </ClusterSection>

          {/* DaemonSets */}
          <ClusterSection title="DaemonSets" icon={Shield} count={(dsData?.data ?? []).length} loading={dsLoading}>
            {(dsData?.data ?? []).map((d: any) => (
              <div key={`${d.namespace}/${d.name}`} className="p-3 rounded-lg border text-xs"
                style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-white">{d.name}</p>
                    <p className="text-gray-500">{d.namespace}</p>
                  </div>
                  <p className={clsx('font-semibold', d.number_ready === d.desired_number_scheduled ? 'text-green-400' : 'text-yellow-400')}>
                    {d.number_ready}/{d.desired_number_scheduled} nodes
                  </p>
                </div>
              </div>
            ))}
          </ClusterSection>
        </div>
      )}

      {/* ── Network tab ─────────────────────────────────────────────────────── */}
      {tab === 'network' && (
        <div className="space-y-4">
          <ClusterSection title="Services" icon={Network} count={(svcData?.data ?? []).length} loading={svcsLoading}>
            {(svcData?.data ?? []).map((s: any) => (
              <div key={`${s.namespace}/${s.name}`} className="p-3 rounded-lg border text-xs"
                style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-white">{s.name}</p>
                    <p className="text-gray-500">{s.namespace}</p>
                  </div>
                  <span className={clsx('px-2 py-0.5 rounded text-xs font-medium',
                    s.type === 'LoadBalancer' ? 'bg-blue-500/10 text-blue-400'
                    : s.type === 'NodePort' ? 'bg-yellow-500/10 text-yellow-400'
                    : 'bg-gray-500/10 text-gray-400')}>
                    {s.type}
                  </span>
                  <div className="text-right">
                    <p className="text-gray-300 font-mono">{s.cluster_ip}</p>
                    {s.external_ip && <p className="text-green-400">{s.external_ip}</p>}
                  </div>
                  <div className="text-gray-500">
                    {s.ports?.map((p: any) => `${p.port}/${p.protocol}`).join(', ')}
                  </div>
                </div>
              </div>
            ))}
          </ClusterSection>

          <ClusterSection title="Ingresses" icon={Network} count={(ingData?.data ?? []).length} loading={ingsLoading}>
            {(ingData?.data ?? []).map((ing: any) => (
              <div key={`${ing.namespace}/${ing.name}`} className="p-3 rounded-lg border text-xs"
                style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="text-sm font-medium text-white">{ing.name}</p>
                    <p className="text-gray-500">{ing.namespace} · {ing.class_name ?? 'default'}</p>
                  </div>
                  {ing.tls?.length > 0 && (
                    <span className="px-2 py-0.5 rounded text-xs bg-green-500/10 text-green-400">TLS</span>
                  )}
                </div>
                {ing.rules?.map((r: any, i: number) => (
                  <div key={i} className="mt-1 pl-2 border-l border-blue-500/30">
                    <p className="text-blue-400 font-mono">{r.host}</p>
                    {r.paths?.map((p: any, j: number) => (
                      <p key={j} className="text-gray-500 ml-2">
                        {p.path} → {p.service}:{p.port}
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </ClusterSection>
        </div>
      )}

      {/* ── Jobs tab ────────────────────────────────────────────────────────── */}
      {tab === 'jobs' && (
        <ClusterSection title="Jobs & CronJobs" icon={Clock} count={(jobsData?.data ?? []).length} loading={jobsLoading}>
          {(jobsData?.data ?? []).map((j: any, i: number) => (
            <div key={i} className="p-3 rounded-lg border text-xs"
              style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
              <div className="flex items-center gap-3">
                <span className={clsx('px-2 py-0.5 rounded font-medium flex-shrink-0',
                  j.kind === 'CronJob' ? 'bg-purple-500/10 text-purple-400' : 'bg-blue-500/10 text-blue-400')}>
                  {j.kind}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{j.name}</p>
                  <p className="text-gray-500">{j.namespace}</p>
                </div>
                {j.kind === 'CronJob' ? (
                  <div className="text-right">
                    <p className="text-gray-300 font-mono">{j.schedule}</p>
                    <p className={j.suspended ? 'text-yellow-400' : 'text-gray-500'}>
                      {j.suspended ? 'Suspended' : `${j.active_jobs} active`}
                    </p>
                  </div>
                ) : (
                  <div className="text-right">
                    <p className={clsx('font-semibold', j.failed > 0 ? 'text-red-400' : 'text-green-400')}>
                      {j.succeeded} ✓ {j.failed > 0 ? `${j.failed} ✗` : ''}
                    </p>
                    {j.active > 0 && <p className="text-blue-400">{j.active} running</p>}
                  </div>
                )}
              </div>
            </div>
          ))}
        </ClusterSection>
      )}

      {/* ── Config tab ──────────────────────────────────────────────────────── */}
      {tab === 'config' && (
        <div className="space-y-4">
          <ClusterSection title="ConfigMaps" icon={Settings2} count={(cmData?.data ?? []).length} loading={cmsLoading}>
            {(cmData?.data ?? []).map((cm: any, i: number) => (
              <div key={i} className="p-3 rounded-lg border text-xs flex items-center gap-3"
                style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
                <div className="flex-1">
                  <p className="text-sm font-medium text-white">{cm.name}</p>
                  <p className="text-gray-500">{cm.namespace}</p>
                </div>
                <p className="text-gray-400">{cm.key_count} keys</p>
                <div className="text-gray-600 max-w-[200px] truncate">
                  {cm.keys?.join(', ')}
                </div>
              </div>
            ))}
          </ClusterSection>

          <ClusterSection title="Secrets (metadata only)" icon={Shield} count={(secData?.data ?? []).length} loading={secsLoading}>
            <div className="mb-2 px-3 py-2 rounded-lg text-xs text-yellow-400 flex items-center gap-2"
              style={{ background: 'hsl(45 100% 50% / 0.05)', border: '1px solid hsl(45 100% 50% / 0.15)' }}>
              ⚠ Secret values are never exposed — key names only for audit purposes
            </div>
            {(secData?.data ?? []).map((s: any, i: number) => (
              <div key={i} className="p-3 rounded-lg border text-xs flex items-center gap-3"
                style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
                <div className="flex-1">
                  <p className="text-sm font-medium text-white">{s.name}</p>
                  <p className="text-gray-500">{s.namespace} · {s.type}</p>
                </div>
                <p className="text-gray-400">{s.key_count} keys</p>
                <div className="text-gray-600 max-w-[200px] truncate">{s.keys?.join(', ')}</div>
              </div>
            ))}
          </ClusterSection>
        </div>
      )}

      {/* ── HPA tab ─────────────────────────────────────────────────────────── */}
      {tab === 'hpa' && (
        <ClusterSection title="Horizontal Pod Autoscalers" icon={Zap} count={(hpaData?.data ?? []).length} loading={hpaLoading}>
          {(hpaData?.data ?? []).map((hpa: any, i: number) => {
            const pct = hpa.current_replicas / hpa.max_replicas * 100;
            return (
              <div key={i} className="p-4 rounded-lg border text-xs"
                style={{ background: 'hsl(230 15% 10%)', borderColor: 'hsl(230 15% 16%)' }}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-sm font-medium text-white">{hpa.name}</p>
                    <p className="text-gray-500">{hpa.namespace} → {hpa.target_kind}/{hpa.target_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-white font-semibold">
                      {hpa.current_replicas} / {hpa.max_replicas} replicas
                    </p>
                    <p className="text-gray-500">min: {hpa.min_replicas}</p>
                  </div>
                </div>
                {/* Replica usage bar */}
                <div className="mb-2">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-400">Replica utilization</span>
                    <span className="text-white">{hpa.current_replicas}/{hpa.max_replicas}</span>
                  </div>
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'hsl(230 15% 18%)' }}>
                    <div className="h-full rounded-full transition-all"
                      style={{
                        width: `${pct}%`,
                        background: pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981',
                      }} />
                  </div>
                </div>
                {hpa.current_cpu_pct != null && (
                  <p className={clsx('text-xs', hpa.current_cpu_pct >= 80 ? 'text-red-400' : 'text-gray-400')}>
                    CPU: {hpa.current_cpu_pct}% (target: {hpa.metrics?.[0]?.target_value}%)
                  </p>
                )}
                {hpa.desired_replicas !== hpa.current_replicas && (
                  <p className="text-yellow-400 mt-1">
                    ↕ Scaling to {hpa.desired_replicas} replicas...
                  </p>
                )}
              </div>
            );
          })}
        </ClusterSection>
      )}
      {tab === 'pipelines' && (
        <div className="rounded-xl border overflow-hidden"
          style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
          <div className="flex items-center justify-between px-5 py-4 border-b"
            style={{ borderColor: 'hsl(230 15% 15%)' }}>
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-purple-400" />
              <span className="text-sm font-semibold text-white">Pipelines</span>
              {pipelines.length > 0 && (
                <span className="text-xs text-gray-500 font-mono">({pipelines.length})</span>
              )}
            </div>
            {canAct && gitConnected && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <CheckCircle className="w-3 h-3 text-green-500" />
                Re-run enabled
              </div>
            )}
          </div>

          <div className="p-4">
            {/* Not connected */}
            {!intLoading && !gitConnected && (
              <EmptyState
                icon={GitBranch}
                title="GitHub / GitLab not connected"
                description="Connect your GitHub or GitLab account to monitor pipelines and trigger re-runs directly from UniOps."
                action={{ label: 'Connect GitHub / GitLab', href: '/settings/integrations' }}
              />
            )}

            {/* Loading */}
            {gitConnected && pipesLoading && <RowSkeleton rows={5} />}

            {/* Error */}
            {gitConnected && !pipesLoading && pipesError && (
              <div className="flex flex-col items-center gap-3 py-10 text-center">
                <p className="text-sm text-red-400">{pipesError}</p>
                <button onClick={refetchPipes}
                  className="text-xs px-3 py-1.5 rounded-lg text-gray-300 hover:text-white border border-border transition-colors">
                  Retry
                </button>
              </div>
            )}

            {/* Empty connected */}
            {gitConnected && !pipesLoading && !pipesError && pipelines.length === 0 && (
              <EmptyState
                icon={GitBranch}
                title="No pipelines found"
                description="No pipeline runs detected. Push a commit or trigger a workflow to see results here."
              />
            )}

            {/* Pipeline list */}
            {gitConnected && !pipesLoading && pipelines.length > 0 && (
              <div className="space-y-2">
                {pipelines.map((pl: PipelineRow) => (
                  <PipelineTableRow
                    key={pl.id}
                    pipeline={pl}
                    canAct={canAct}
                    onRerun={(p, failedOnly) => setConfirmRerun({ pipeline: p, failedOnly })}
                    onCancel={p => setConfirmCancel(p)}
                    onViewJobs={p => setJobsPipeline(p)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Deploy History tab ──────────────────────────────────────────────── */}
      {tab === 'history' && (
        <div className="rounded-xl border overflow-hidden"
          style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
          <div className="flex items-center gap-2 px-5 py-4 border-b"
            style={{ borderColor: 'hsl(230 15% 15%)' }}>
            <History className="w-4 h-4 text-gray-400" />
            <span className="text-sm font-semibold text-white">Deploy History</span>
          </div>
          <div className="p-4">
            {pipelines.filter((p: PipelineRow) =>
              ['success', 'failed', 'error'].includes(p.status?.toLowerCase())
            ).length === 0 ? (
              <EmptyState
                icon={History}
                title="No completed deployments"
                description="Completed pipeline runs will appear here for audit and review."
              />
            ) : (
              <div className="space-y-2">
                {pipelines
                  .filter((p: PipelineRow) =>
                    ['success', 'failed', 'error'].includes(p.status?.toLowerCase())
                  )
                  .map((pl: PipelineRow) => (
                    <PipelineTableRow
                      key={pl.id}
                      pipeline={pl}
                      canAct={false}
                      onRerun={() => {}}
                      onViewJobs={p => setJobsPipeline(p)}
                    />
                  ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Dialogs & Drawers ───────────────────────────────────────────────── */}

      {/* Pod restart / delete confirm */}
      <ConfirmDialog
        open={!!confirmPodAction}
        title={
          confirmPodAction?.type === 'restart'
            ? `Restart pod "${confirmPodAction.pod.name}"?`
            : `Force delete pod "${confirmPodAction?.pod.name}"?`
        }
        description={
          confirmPodAction?.type === 'restart'
            ? 'The pod will be gracefully terminated (30s). If owned by a Deployment or StatefulSet, the controller reschedules it immediately.'
            : 'The pod will be deleted immediately (grace_period=0). Deployments will recreate it automatically.'
        }
        confirmLabel={confirmPodAction?.type === 'restart' ? 'Restart' : 'Force Delete'}
        danger={confirmPodAction?.type === 'delete'}
        loading={podActions.loading}
        onConfirm={handlePodConfirm}
        onCancel={() => setConfirmPodAction(null)}
      />

      {/* Pipeline re-run confirm */}
      <ConfirmDialog
        open={!!confirmRerun}
        title={
          confirmRerun?.failedOnly
            ? `Re-run failed jobs in "${confirmRerun.pipeline.name}"?`
            : `Re-run all jobs in "${confirmRerun?.pipeline.name}"?`
        }
        description={
          confirmRerun?.failedOnly
            ? `Only failed jobs will be re-queued on ${confirmRerun.pipeline.repository}. Successful jobs are skipped.`
            : `All jobs will be re-queued from scratch on ${confirmRerun?.pipeline.repository}.`
        }
        confirmLabel={confirmRerun?.failedOnly ? 'Re-run Failed Jobs' : 'Re-run All Jobs'}
        danger={false}
        loading={pipeActions.loading}
        onConfirm={handlePipelineConfirm}
        onCancel={() => setConfirmRerun(null)}
      />

      {/* Pipeline cancel confirm */}
      <ConfirmDialog
        open={!!confirmCancel}
        title={`Cancel pipeline "${confirmCancel?.name}"?`}
        description={`This will send a cancellation request to GitHub. Currently running jobs will be stopped.`}
        confirmLabel="Cancel Pipeline"
        danger={true}
        loading={pipeActions.loading}
        onConfirm={handleCancelConfirm}
        onCancel={() => setConfirmCancel(null)}
      />

      {/* Pod log viewer */}
      <AnimatePresence>
        {logsPod && (
          <LogViewerDialog
            podId={logsPod.id}
            podName={logsPod.name}
            onClose={() => setLogsPod(null)}
          />
        )}
      </AnimatePresence>

      {/* Exec Terminal */}
      <AnimatePresence>
        {execPod && (
          <ExecTerminalDialog
            pod={execPod}
            onClose={() => setExecPod(null)}
          />
        )}
      </AnimatePresence>

      {/* Scale Deployment */}
      <AnimatePresence>
        {scalePod && (
          <ScaleDialog
            pod={scalePod}
            onClose={() => setScalePod(null)}
            onScaled={msg => { showToast(true, msg); refetchPods(); }}
          />
        )}
      </AnimatePresence>

      {/* Pod events drawer */}
      <AnimatePresence>
        {eventsPod && (
          <EventsDrawer pod={eventsPod} onClose={() => setEventsPod(null)} />
        )}
      </AnimatePresence>

      {/* Pipeline jobs drawer */}
      <AnimatePresence>
        {jobsPipeline && (
          <JobsDrawer pipeline={jobsPipeline} onClose={() => setJobsPipeline(null)} />
        )}
      </AnimatePresence>

    </motion.div>
  );
}
