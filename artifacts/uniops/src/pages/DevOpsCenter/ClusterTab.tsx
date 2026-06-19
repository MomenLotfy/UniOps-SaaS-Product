// ─────────────────────────────────────────────────────────────────────────────
// ClusterTab — Multi-Cluster Management (Epic 2)
// Add / Remove / Test clusters; drill-down into nodes, namespaces, workloads
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Server, Plus, Trash2, RefreshCw, CheckCircle2, XCircle,
  AlertTriangle, Clock, ChevronRight, ArrowLeft, Cpu, MemoryStick,
  Globe, GitBranch, Layers, Network, Box, X, Loader2, Info,
  ShieldCheck,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost, apiDelete } from '@/hooks/use-api';
import type {
  Cluster, ClusterProvider, ClusterEnv, ClusterCreatePayload,
  ClusterNode, ClusterNamespace, ClusterDeployment,
  ClusterService, ClusterIngress,
} from './types';

// ── Constants ────────────────────────────────────────────────────────────────

const PROVIDERS: { id: ClusterProvider; label: string; badge: string }[] = [
  { id: 'eks',    label: 'AWS EKS',          badge: 'AWS'   },
  { id: 'aks',    label: 'Azure AKS',        badge: 'Azure' },
  { id: 'gke',    label: 'Google GKE',       badge: 'GCP'   },
  { id: 'oke',    label: 'Oracle OKE',       badge: 'OCI'   },
  { id: 'on-prem',label: 'On-Prem / Vanilla',badge: 'K8s'   },
];

const ENVS: ClusterEnv[] = ['production', 'staging', 'dev', 'sandbox'];

type DetailTab = 'nodes' | 'namespaces' | 'deployments' | 'services' | 'ingresses';

// ── Helpers ──────────────────────────────────────────────────────────────────

function providerLabel(p: string) {
  return PROVIDERS.find(x => x.id === p)?.label ?? p;
}

function statusColor(s: string) {
  switch (s) {
    case 'connected':    return 'text-green-400  border-green-500/20  bg-green-500/5';
    case 'disconnected': return 'text-gray-400   border-gray-500/20   bg-gray-500/5';
    case 'error':        return 'text-red-400    border-red-500/20    bg-red-500/5';
    default:             return 'text-yellow-400 border-yellow-500/20 bg-yellow-500/5';
  }
}

function statusIcon(s: string) {
  switch (s) {
    case 'connected':    return <CheckCircle2 className="w-3.5 h-3.5" />;
    case 'error':        return <XCircle className="w-3.5 h-3.5" />;
    case 'pending':      return <Clock className="w-3.5 h-3.5 animate-pulse" />;
    default:             return <AlertTriangle className="w-3.5 h-3.5" />;
  }
}

function envBadge(e: string) {
  const colors: Record<string, string> = {
    production: 'bg-red-500/10 text-red-400',
    staging:    'bg-yellow-500/10 text-yellow-400',
    dev:        'bg-blue-500/10 text-blue-400',
    sandbox:    'bg-purple-500/10 text-purple-400',
  };
  return colors[e] ?? 'bg-gray-500/10 text-gray-400';
}

function UsageBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
      <div
        className={clsx('h-full rounded-full transition-all', color)}
        style={{ width: `${Math.min(value, 100)}%` }}
      />
    </div>
  );
}

// ── Add Cluster Dialog ────────────────────────────────────────────────────────

interface AddClusterDialogProps {
  onClose: () => void;
  onCreated: () => void;
}

function AddClusterDialog({ onClose, onCreated }: AddClusterDialogProps) {
  const [form, setForm] = useState<ClusterCreatePayload>({
    name: '', provider: 'eks', region: '', environment: 'production',
  });
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState<string | null>(null);

  const set = (k: keyof ClusterCreatePayload, v: string) =>
    setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setError('Name is required'); return; }
    setSaving(true); setError(null);
    try {
      await apiPost('/clusters', form);
      onCreated();
      onClose();
    } catch (err: any) {
      setError(err?.message ?? 'Failed to add cluster');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)' }}>
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.94 }}
        className="w-full max-w-lg rounded-2xl border shadow-2xl overflow-hidden"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 18%)' }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'hsl(230 15% 15%)' }}>
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-blue-400" />
            <span className="font-semibold text-white text-sm">Add Cluster</span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Cluster name *</label>
            <input
              value={form.name}
              onChange={e => set('name', e.target.value)}
              placeholder="prod-us-east-1"
              className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none focus:border-blue-500/50 transition-colors"
              style={{ background: 'hsl(230 15% 13%)', borderColor: 'hsl(230 15% 20%)' }}
            />
          </div>

          {/* Provider */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Provider *</label>
            <div className="grid grid-cols-5 gap-1.5">
              {PROVIDERS.map(p => (
                <button
                  key={p.id} type="button"
                  onClick={() => set('provider', p.id)}
                  className={clsx(
                    'py-2 rounded-lg text-xs font-medium border transition-all',
                    form.provider === p.id
                      ? 'border-blue-500/50 text-blue-400 bg-blue-500/10'
                      : 'border-white/5 text-gray-400 hover:border-white/15',
                  )}
                >
                  {p.badge}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-600 mt-1">{providerLabel(form.provider)}</p>
          </div>

          {/* Region + Environment */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Region</label>
              <input
                value={form.region}
                onChange={e => set('region', e.target.value)}
                placeholder="us-east-1"
                className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none focus:border-blue-500/50 transition-colors"
                style={{ background: 'hsl(230 15% 13%)', borderColor: 'hsl(230 15% 20%)' }}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Environment</label>
              <select
                value={form.environment}
                onChange={e => set('environment', e.target.value as ClusterEnv)}
                className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none focus:border-blue-500/50 transition-colors"
                style={{ background: 'hsl(230 15% 13%)', borderColor: 'hsl(230 15% 20%)' }}
              >
                {ENVS.map(e => <option key={e} value={e}>{e}</option>)}
              </select>
            </div>
          </div>

          {/* API Server */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">API Server URL</label>
            <input
              value={form.api_server_url ?? ''}
              onChange={e => set('api_server_url', e.target.value)}
              placeholder="https://k8s.example.com:6443"
              className="w-full px-3 py-2 rounded-lg text-sm text-white border outline-none focus:border-blue-500/50 transition-colors"
              style={{ background: 'hsl(230 15% 13%)', borderColor: 'hsl(230 15% 20%)' }}
            />
          </div>

          {/* Kubeconfig */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Kubeconfig (paste YAML)</label>
            <textarea
              value={form.kubeconfig ?? ''}
              onChange={e => set('kubeconfig', e.target.value)}
              rows={5}
              placeholder="apiVersion: v1&#10;kind: Config&#10;clusters:&#10;  - cluster:&#10;      server: https://..."
              className="w-full px-3 py-2 rounded-lg text-xs text-gray-300 font-mono border outline-none focus:border-blue-500/50 transition-colors resize-none"
              style={{ background: 'hsl(230 15% 11%)', borderColor: 'hsl(230 15% 18%)' }}
            />
            <p className="text-xs text-gray-600 mt-1 flex items-center gap-1">
              <Info className="w-3 h-3" /> Stored securely. Leave blank to use the primary K8s integration.
            </p>
          </div>

          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">{error}</p>
          )}

          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm text-gray-400 border hover:text-white transition-colors"
              style={{ borderColor: 'hsl(230 15% 20%)' }}>
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
              {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {saving ? 'Adding...' : 'Add Cluster'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

// ── Cluster Card ──────────────────────────────────────────────────────────────

interface ClusterCardProps {
  cluster: Cluster;
  onDelete: (id: string) => void;
  onTest:   (id: string) => void;
  onOpen:   (cluster: Cluster) => void;
  testing:  boolean;
}

function ClusterCard({ cluster: c, onDelete, onTest, onOpen, testing }: ClusterCardProps) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="group rounded-xl border p-4 hover:border-blue-500/30 transition-all cursor-pointer relative"
      style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 16%)' }}
      onClick={() => onOpen(c)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Server className="w-4 h-4 text-blue-400 flex-shrink-0" />
            <span className="text-sm font-semibold text-white truncate">{c.name}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-500">{providerLabel(c.provider)}</span>
            {c.region && <><span className="text-gray-700">·</span><span className="text-xs text-gray-500">{c.region}</span></>}
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
          <span className={clsx('px-2 py-0.5 text-xs rounded', envBadge(c.environment))}>{c.environment}</span>
          <span className={clsx('flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border', statusColor(c.status))}>
            {statusIcon(c.status)}{c.status}
          </span>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="rounded-lg px-3 py-2" style={{ background: 'hsl(230 15% 12%)' }}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500 flex items-center gap-1"><Cpu className="w-3 h-3" />CPU</span>
            <span className={clsx('text-xs font-mono font-bold',
              c.cpu_usage_pct >= 80 ? 'text-red-400' : c.cpu_usage_pct >= 60 ? 'text-yellow-400' : 'text-green-400')}>
              {c.cpu_usage_pct.toFixed(0)}%
            </span>
          </div>
          <UsageBar value={c.cpu_usage_pct}
            color={c.cpu_usage_pct >= 80 ? 'bg-red-500' : c.cpu_usage_pct >= 60 ? 'bg-yellow-500' : 'bg-green-500'} />
        </div>
        <div className="rounded-lg px-3 py-2" style={{ background: 'hsl(230 15% 12%)' }}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500 flex items-center gap-1"><MemoryStick className="w-3 h-3" />Memory</span>
            <span className={clsx('text-xs font-mono font-bold',
              c.memory_usage_pct >= 80 ? 'text-red-400' : c.memory_usage_pct >= 60 ? 'text-yellow-400' : 'text-purple-400')}>
              {c.memory_usage_pct.toFixed(0)}%
            </span>
          </div>
          <UsageBar value={c.memory_usage_pct}
            color={c.memory_usage_pct >= 80 ? 'bg-red-500' : c.memory_usage_pct >= 60 ? 'bg-yellow-500' : 'bg-purple-500'} />
        </div>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-3 mb-3 text-xs text-gray-400">
        <span className="flex items-center gap-1"><Server className="w-3 h-3" />{c.node_count} nodes</span>
        <span className="flex items-center gap-1"><Box className="w-3 h-3" />{c.pod_count} pods</span>
        {c.k8s_version && <span className="flex items-center gap-1"><ShieldCheck className="w-3 h-3" />v{c.k8s_version}</span>}
      </div>

      {c.error_message && (
        <p className="text-xs text-red-400/80 mb-2 line-clamp-1 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 flex-shrink-0" />{c.error_message}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
        <button
          onClick={() => onTest(c.id)}
          disabled={testing}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 hover:text-white border hover:border-white/20 transition-colors disabled:opacity-50"
          style={{ borderColor: 'hsl(230 15% 20%)' }}>
          {testing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          Test
        </button>
        <div className="flex-1" />
        <button
          onClick={() => onDelete(c.id)}
          className="p-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-colors">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => onOpen(c)}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-blue-400 hover:text-blue-300 border border-blue-500/20 hover:border-blue-500/40 transition-colors">
          Details <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </motion.div>
  );
}

// ── Cluster Detail View ───────────────────────────────────────────────────────

interface ClusterDetailProps {
  cluster: Cluster;
  onBack: () => void;
}

const DETAIL_TABS: { id: DetailTab; label: string; icon: React.ElementType }[] = [
  { id: 'nodes',       label: 'Nodes',       icon: Server   },
  { id: 'namespaces',  label: 'Namespaces',  icon: Layers   },
  { id: 'deployments', label: 'Deployments', icon: GitBranch },
  { id: 'services',    label: 'Services',    icon: Network  },
  { id: 'ingresses',   label: 'Ingresses',   icon: Globe    },
];

function ClusterDetail({ cluster, onBack }: ClusterDetailProps) {
  const [tab, setTab] = useState<DetailTab>('nodes');

  const { data: nodesData,   loading: nodesLoad }   = useApi<any>(tab === 'nodes'       ? `/clusters/${cluster.id}/nodes`       : null);
  const { data: nsData,      loading: nsLoad }      = useApi<any>(tab === 'namespaces'  ? `/clusters/${cluster.id}/namespaces`  : null);
  const { data: depsData,    loading: depsLoad }    = useApi<any>(tab === 'deployments' ? `/clusters/${cluster.id}/deployments` : null);
  const { data: svcsData,    loading: svcsLoad }    = useApi<any>(tab === 'services'    ? `/clusters/${cluster.id}/services`    : null);
  const { data: ingsData,    loading: ingsLoad }    = useApi<any>(tab === 'ingresses'   ? `/clusters/${cluster.id}/ingresses`   : null);

  const nodes:       ClusterNode[]       = nodesData?.data ?? nodesData ?? [];
  const namespaces:  ClusterNamespace[]  = nsData?.data    ?? nsData    ?? [];
  const deployments: ClusterDeployment[] = depsData?.data  ?? depsData  ?? [];
  const services:    ClusterService[]    = svcsData?.data  ?? svcsData  ?? [];
  const ingresses:   ClusterIngress[]    = ingsData?.data  ?? ingsData  ?? [];

  const loading = nodesLoad || nsLoad || depsLoad || svcsLoad || ingsLoad;

  const tableRow = (...cells: (string | React.ReactNode)[]) => (
    <tr className="border-b transition-colors hover:bg-white/2" style={{ borderColor: 'hsl(230 15% 13%)' }}>
      {cells.map((c, i) => (
        <td key={i} className="px-4 py-2.5 text-xs text-gray-300">{c}</td>
      ))}
    </tr>
  );

  const thCls = "px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider";

  return (
    <div>
      {/* Back header */}
      <div className="flex items-center gap-3 mb-5">
        <button onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors">
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </button>
        <div className="h-4 w-px bg-white/10" />
        <Server className="w-4 h-4 text-blue-400" />
        <span className="text-sm font-semibold text-white">{cluster.name}</span>
        <span className={clsx('flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border', statusColor(cluster.status))}>
          {statusIcon(cluster.status)}{cluster.status}
        </span>
        <span className="text-xs text-gray-500 ml-auto">{cluster.k8s_version ? `v${cluster.k8s_version}` : ''} · {providerLabel(cluster.provider)}</span>
      </div>

      {/* Detail tabs */}
      <div className="flex gap-1 mb-4 p-1 rounded-lg" style={{ background: 'hsl(230 15% 10%)' }}>
        {DETAIL_TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={clsx('flex items-center gap-1.5 flex-1 py-1.5 rounded-md text-xs font-medium transition-all',
              tab === t.id ? 'text-white shadow-sm' : 'text-gray-500 hover:text-gray-300')}
            style={tab === t.id ? { background: 'hsl(230 15% 16%)' } : {}}>
            <t.icon className="w-3 h-3 mx-auto sm:mx-0" />
            <span className="hidden sm:inline">{t.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'hsl(230 15% 15%)' }}>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 text-gray-500 animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              {/* ── Nodes ── */}
              {tab === 'nodes' && (
                <>
                  <thead style={{ background: 'hsl(230 15% 11%)' }}>
                    <tr>{['Name','Status','Roles','CPU','Memory','OS','Kubelet','Age'].map(h => <th key={h} className={thCls}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {nodes.length === 0
                      ? <tr><td colSpan={8} className="px-4 py-8 text-center text-xs text-gray-500">No nodes found</td></tr>
                      : nodes.map(n => tableRow(
                          <span className="font-mono text-white">{n.name}</span>,
                          <span className={clsx('flex items-center gap-1', n.status === 'Ready' ? 'text-green-400' : 'text-red-400')}>
                            {n.status === 'Ready' ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}{n.status}
                          </span>,
                          n.roles.join(', '),
                          `${n.cpu_allocatable ?? '—'} / ${n.cpu_capacity ?? '—'}`,
                          `${n.memory_allocatable ?? '—'} / ${n.memory_capacity ?? '—'}`,
                          n.os_image ?? '—',
                          n.kubelet_version ?? '—',
                          n.age ?? '—',
                        ))
                    }
                  </tbody>
                </>
              )}

              {/* ── Namespaces ── */}
              {tab === 'namespaces' && (
                <>
                  <thead style={{ background: 'hsl(230 15% 11%)' }}>
                    <tr>{['Name','Status','Age','Labels'].map(h => <th key={h} className={thCls}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {namespaces.length === 0
                      ? <tr><td colSpan={4} className="px-4 py-8 text-center text-xs text-gray-500">No namespaces found</td></tr>
                      : namespaces.map(ns => tableRow(
                          <span className="font-mono text-white">{ns.name}</span>,
                          <span className={ns.status === 'Active' ? 'text-green-400' : 'text-yellow-400'}>{ns.status}</span>,
                          ns.age ?? '—',
                          Object.entries(ns.labels).slice(0,2).map(([k,v]) => (
                            <span key={k} className="inline-flex mr-1 px-1.5 py-0.5 text-xs rounded bg-white/5 text-gray-400">{k}={v}</span>
                          )),
                        ))
                    }
                  </tbody>
                </>
              )}

              {/* ── Deployments ── */}
              {tab === 'deployments' && (
                <>
                  <thead style={{ background: 'hsl(230 15% 11%)' }}>
                    <tr>{['Name','Namespace','Replicas','Status','Image','Age'].map(h => <th key={h} className={thCls}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {deployments.length === 0
                      ? <tr><td colSpan={6} className="px-4 py-8 text-center text-xs text-gray-500">No deployments found</td></tr>
                      : deployments.map(d => tableRow(
                          <span className="font-mono text-white">{d.name}</span>,
                          <span className="text-gray-400">{d.namespace}</span>,
                          `${d.ready_replicas}/${d.replicas}`,
                          <span className={clsx('flex items-center gap-1',
                            d.status === 'Healthy' ? 'text-green-400' : d.status === 'Progressing' ? 'text-yellow-400' : 'text-red-400')}>
                            {d.status === 'Healthy' ? <CheckCircle2 className="w-3 h-3" />
                              : d.status === 'Progressing' ? <Clock className="w-3 h-3" />
                              : <XCircle className="w-3 h-3" />}
                            {d.status}
                          </span>,
                          <span className="font-mono text-xs text-gray-500 max-w-xs truncate block">{d.image ?? '—'}</span>,
                          d.age ?? '—',
                        ))
                    }
                  </tbody>
                </>
              )}

              {/* ── Services ── */}
              {tab === 'services' && (
                <>
                  <thead style={{ background: 'hsl(230 15% 11%)' }}>
                    <tr>{['Name','Namespace','Type','Cluster IP','External IP','Ports','Age'].map(h => <th key={h} className={thCls}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {services.length === 0
                      ? <tr><td colSpan={7} className="px-4 py-8 text-center text-xs text-gray-500">No services found</td></tr>
                      : services.map(s => tableRow(
                          <span className="font-mono text-white">{s.name}</span>,
                          <span className="text-gray-400">{s.namespace}</span>,
                          <span className="px-1.5 py-0.5 rounded text-xs bg-blue-500/10 text-blue-400">{s.type}</span>,
                          <span className="font-mono text-xs text-gray-400">{s.cluster_ip ?? '—'}</span>,
                          s.external_ip
                            ? <span className="font-mono text-xs text-green-400">{s.external_ip}</span>
                            : <span className="text-gray-600">—</span>,
                          <span className="font-mono text-xs text-gray-400">{s.ports.join(', ')}</span>,
                          s.age ?? '—',
                        ))
                    }
                  </tbody>
                </>
              )}

              {/* ── Ingresses ── */}
              {tab === 'ingresses' && (
                <>
                  <thead style={{ background: 'hsl(230 15% 11%)' }}>
                    <tr>{['Name','Namespace','Class','Hosts','Paths','TLS','Age'].map(h => <th key={h} className={thCls}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {ingresses.length === 0
                      ? <tr><td colSpan={7} className="px-4 py-8 text-center text-xs text-gray-500">No ingresses found</td></tr>
                      : ingresses.map(ing => tableRow(
                          <span className="font-mono text-white">{ing.name}</span>,
                          <span className="text-gray-400">{ing.namespace}</span>,
                          ing.class_ ?? '—',
                          ing.hosts.join(', ') || '—',
                          ing.paths.join(', ') || '/',
                          ing.tls
                            ? <span className="flex items-center gap-1 text-green-400"><ShieldCheck className="w-3 h-3" />TLS</span>
                            : <span className="text-gray-600">None</span>,
                          ing.age ?? '—',
                        ))
                    }
                  </tbody>
                </>
              )}
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main ClusterTab ───────────────────────────────────────────────────────────

interface ClusterTabProps {
  showToast: (ok: boolean, msg: string) => void;
}

export function ClusterTab({ showToast }: ClusterTabProps) {
  const { data, loading, refetch } = useApi<any>('/clusters');
  const clusters: Cluster[] = data?.data ?? data ?? [];

  const [showAdd,   setShowAdd]   = useState(false);
  const [detail,    setDetail]    = useState<Cluster | null>(null);
  const [testing,   setTesting]   = useState<Record<string, boolean>>({});
  const [deleting,  setDeleting]  = useState<Record<string, boolean>>({});

  const handleTest = useCallback(async (id: string) => {
    setTesting(p => ({ ...p, [id]: true }));
    try {
      const res: any = await apiPost(`/clusters/${id}/test`, {});
      const d = res?.data ?? res;
      showToast(d.status === 'connected', d.message ?? (d.status === 'connected' ? 'Connected!' : 'Connection failed'));
      refetch(true);
    } catch (e: any) {
      showToast(false, e.message ?? 'Test failed');
    } finally {
      setTesting(p => ({ ...p, [id]: false }));
    }
  }, [showToast, refetch]);

  const handleDelete = useCallback(async (id: string) => {
    if (!window.confirm('Remove this cluster? This cannot be undone.')) return;
    setDeleting(p => ({ ...p, [id]: true }));
    try {
      await apiDelete(`/clusters/${id}`);
      showToast(true, 'Cluster removed');
      refetch(true);
    } catch (e: any) {
      showToast(false, e.message ?? 'Delete failed');
    } finally {
      setDeleting(p => ({ ...p, [id]: false }));
    }
  }, [showToast, refetch]);

  if (detail) {
    return (
      <ClusterDetail
        cluster={detail}
        onBack={() => setDetail(null)}
      />
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-xs text-gray-500">{clusters.length} cluster{clusters.length !== 1 ? 's' : ''} registered</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors">
          <Plus className="w-3.5 h-3.5" /> Add Cluster
        </button>
      </div>

      {/* Empty state */}
      {!loading && clusters.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Server className="w-12 h-12 text-gray-700 mb-3" />
          <p className="text-sm font-medium text-gray-400 mb-1">No clusters registered</p>
          <p className="text-xs text-gray-600 mb-4">Add your first cluster to manage it from here</p>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors">
            <Plus className="w-3.5 h-3.5" /> Add Cluster
          </button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1,2,3].map(i => (
            <div key={i} className="rounded-xl border p-4 animate-pulse" style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' }}>
              <div className="h-4 w-32 rounded bg-white/5 mb-2" />
              <div className="h-3 w-20 rounded bg-white/5 mb-3" />
              <div className="h-8 rounded bg-white/5" />
            </div>
          ))}
        </div>
      )}

      {/* Cluster grid */}
      {!loading && clusters.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          <AnimatePresence mode="popLayout">
            {clusters.map(c => (
              <ClusterCard
                key={c.id}
                cluster={c}
                onDelete={handleDelete}
                onTest={handleTest}
                onOpen={setDetail}
                testing={testing[c.id] ?? false}
              />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Add dialog */}
      <AnimatePresence>
        {showAdd && (
          <AddClusterDialog
            onClose={() => setShowAdd(false)}
            onCreated={() => refetch(true)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
