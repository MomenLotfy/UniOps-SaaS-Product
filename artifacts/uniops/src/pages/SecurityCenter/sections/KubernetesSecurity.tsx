import {
  useState, useCallback, useEffect, useRef, useMemo, memo,
} from 'react';
import {
  Server, RefreshCw, Play, Shield, AlertTriangle,
  ChevronDown, ChevronUp, ChevronRight, X,
  CheckCircle, Clock, Filter, Layers, Box, Cpu,
  Lock, Globe, Network, Eye, EyeOff, Activity, BarChart3,
  Database, HardDrive, Zap, GitBranch, Terminal, Download,
  Search, Package, Workflow, CircleDot, AlertCircle,
  MemoryStick, Boxes, Link2, FileCode, Settings, Plus,
  ArrowRight, Info, TriangleAlert,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost, apiPatch } from '@/hooks/use-api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Cluster {
  id: string;
  name: string;
  status: string;
  provider: string;
  environment?: string;
  region?: string;
  k8s_version?: string;
  api_server_url?: string;
  node_count?: number;
  pod_count?: number;
  findings_count?: number;
  risk_score?: number | null;
  last_scan?: string;
  last_sync?: string;
  distribution?: string;
}

interface NamespaceData {
  name: string;
  status: string;
  pod_count?: number;
  deployment_count?: number;
  cpu_usage?: string;
  memory_usage?: string;
  restart_count?: number;
  network_policies?: number;
  security_score?: number;
  created_at?: string;
}

interface NodeData {
  name: string;
  status: string;
  roles?: string[];
  cpu_capacity?: string;
  memory_capacity?: string;
  cpu_usage?: string;
  memory_usage?: string;
  pod_count?: number;
  version?: string;
}

interface KEvent {
  id?: string;
  timestamp: string;
  namespace: string;
  kind: string;
  reason: string;
  object: string;
  message?: string;
  type?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SEV_COLOR: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-blue-400',
  info:     'text-slate-400',
};
const SEV_BG: Record<string, string> = {
  critical: 'bg-red-500/15 border-red-500/30',
  high:     'bg-orange-500/15 border-orange-500/30',
  medium:   'bg-yellow-500/15 border-yellow-500/30',
  low:      'bg-blue-500/15 border-blue-500/30',
  info:     'bg-slate-500/15 border-slate-500/30',
};
const SEV_DOT: Record<string, string> = {
  critical: 'bg-red-500',
  high:     'bg-orange-500',
  medium:   'bg-yellow-500',
  low:      'bg-blue-500',
  info:     'bg-slate-500',
};
const CAT_LABEL: Record<string, string> = {
  privileged_containers: 'Privileged Containers',
  rbac:                  'RBAC Misconfigurations',
  exposed_services:      'Exposed Services',
  network_policy:        'Network Policies',
  secrets:               'Secrets Exposure',
  cis_benchmark:         'CIS Benchmark',
  runtime:               'Runtime Security',
};
const STATUS_COLOR: Record<string, string> = {
  connected:    'text-green-400',
  running:      'text-green-400',
  Active:       'text-green-400',
  Ready:        'text-green-400',
  disconnected: 'text-red-400',
  error:        'text-red-400',
  Failed:       'text-red-400',
  NotReady:     'text-red-400',
  pending:      'text-yellow-400',
  Pending:      'text-yellow-400',
  Terminating:  'text-orange-400',
};
const STATUS_DOT: Record<string, string> = {
  connected:    'bg-green-400',
  running:      'bg-green-400',
  Active:       'bg-green-400',
  Ready:        'bg-green-400',
  disconnected: 'bg-red-400',
  error:        'bg-red-400',
  Failed:       'bg-red-400',
  pending:      'bg-yellow-400',
  Pending:      'bg-yellow-400',
};

function fmtDate(iso: string | null | undefined, short = false): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (short) return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Sk({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// ─── Risk Ring ────────────────────────────────────────────────────────────────

function RiskRing({ score, size = 56 }: { score: number | null; size?: number }) {
  if (score === null || score === undefined) return (
    <div className="w-12 h-12 rounded-full border-2 border-white/10 flex items-center justify-center flex-shrink-0">
      <span className="text-[9px] text-muted-foreground">N/A</span>
    </div>
  );
  const pct = Math.min(100, score);
  const color = pct >= 70 ? '#ef4444' : pct >= 40 ? '#f97316' : pct >= 20 ? '#eab308' : '#22c55e';
  const r = 18; const circ = 2 * Math.PI * r;
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg viewBox="0 0 48 48" className="-rotate-90" style={{ width: size, height: size }}>
        <circle cx="24" cy="24" r={r} fill="none" stroke="hsl(230 15% 15%)" strokeWidth="4" />
        <circle cx="24" cy="24" r={r} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={`${circ * (pct / 100)} ${circ}`} />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[10px] font-bold" style={{ color }}>{Math.round(score)}</span>
      </div>
    </div>
  );
}

// ─── Summary Cards ────────────────────────────────────────────────────────────

function SummaryCard({ label, value, sub, icon: Icon, color = 'text-blue-400', loading }: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; color?: string; loading?: boolean;
}) {
  return (
    <div className="card-base px-4 py-3 flex items-start gap-3 min-w-0">
      <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5',
        color.includes('green') ? 'bg-green-500/10' :
        color.includes('red') ? 'bg-red-500/10' :
        color.includes('yellow') ? 'bg-yellow-500/10' :
        color.includes('purple') ? 'bg-purple-500/10' :
        'bg-blue-500/10',
      )}>
        <Icon className={clsx('w-4 h-4', color)} />
      </div>
      <div className="min-w-0 flex-1">
        {loading ? (
          <>
            <Sk className="h-5 w-14 mb-1" />
            <Sk className="h-3 w-20" />
          </>
        ) : (
          <>
            <div className="text-lg font-bold text-foreground tabular-nums leading-tight">{value}</div>
            <div className="text-[11px] text-muted-foreground leading-tight">{label}</div>
            {sub && <div className="text-[10px] text-muted-foreground/60 mt-0.5">{sub}</div>}
          </>
        )}
      </div>
    </div>
  );
}

// ─── Cluster Topology (SVG) ───────────────────────────────────────────────────

interface TopoNode {
  id: string; label: string; kind: 'cluster' | 'node' | 'namespace' | 'pod' | 'service';
  x: number; y: number; status?: string; count?: number;
}
interface TopoEdge { from: string; to: string; }

function TopologyGraph({ cluster, nodes, namespaces, pods, services }: {
  cluster: Cluster | null;
  nodes: NodeData[];
  namespaces: NamespaceData[];
  pods: any[];
  services: any[];
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [zoom, setZoom] = useState(1);
  const W = 560; const H = 420;

  const { topoNodes, edges } = useMemo<{ topoNodes: TopoNode[]; edges: TopoEdge[] }>(() => {
    if (!cluster) return { topoNodes: [], edges: [] };
    const tn: TopoNode[] = [];
    const es: TopoEdge[] = [];

    // Cluster center
    tn.push({ id: 'cluster', label: cluster.name, kind: 'cluster', x: W / 2, y: 50, status: cluster.status });

    // Nodes row
    const visNodes = nodes.slice(0, 6);
    visNodes.forEach((n, i) => {
      const x = 60 + (i * (W - 80)) / Math.max(1, visNodes.length - 1 || 1);
      tn.push({ id: `node-${n.name}`, label: n.name.slice(0, 14), kind: 'node', x, y: 140, status: n.status });
      es.push({ from: 'cluster', to: `node-${n.name}` });
    });

    // Namespaces row
    const visNs = namespaces.slice(0, 7);
    visNs.forEach((ns, i) => {
      const x = 40 + (i * (W - 60)) / Math.max(1, visNs.length - 1 || 1);
      tn.push({ id: `ns-${ns.name}`, label: ns.name.slice(0, 12), kind: 'namespace', x, y: 240, status: ns.status, count: ns.pod_count });
      // Connect to nearest node
      if (visNodes.length > 0) {
        const ni = Math.floor((i / Math.max(1, visNs.length)) * visNodes.length);
        const nn = visNodes[Math.min(ni, visNodes.length - 1)];
        es.push({ from: `node-${nn.name}`, to: `ns-${ns.name}` });
      } else {
        es.push({ from: 'cluster', to: `ns-${ns.name}` });
      }
    });

    // Services row (bottom)
    const visSvc = services.slice(0, 5);
    visSvc.forEach((svc, i) => {
      const x = 80 + (i * (W - 120)) / Math.max(1, visSvc.length - 1 || 1);
      tn.push({ id: `svc-${svc.name ?? i}`, label: (svc.name ?? 'svc').slice(0, 12), kind: 'service', x, y: 340, status: 'running' });
      // Connect to its namespace if matched
      const matchNs = visNs.findIndex(ns => ns.name === svc.namespace);
      if (matchNs >= 0) {
        es.push({ from: `ns-${visNs[matchNs].name}`, to: `svc-${svc.name ?? i}` });
      } else if (visNs.length > 0) {
        es.push({ from: `ns-${visNs[0].name}`, to: `svc-${svc.name ?? i}` });
      }
    });

    return { topoNodes: tn, edges: es };
  }, [cluster, nodes, namespaces, pods, services]);

  const kindColor: Record<string, string> = {
    cluster: '#6366f1', node: '#3b82f6', namespace: '#8b5cf6', pod: '#10b981', service: '#f59e0b',
  };
  const kindLabel: Record<string, string> = {
    cluster: 'Cluster', node: 'Node', namespace: 'Namespace', pod: 'Pod', service: 'Service',
  };

  if (!cluster) return (
    <div className="flex items-center justify-center h-full text-muted-foreground text-xs">
      Select a cluster to view topology
    </div>
  );
  if (topoNodes.length === 0) return (
    <div className="flex items-center justify-center h-full text-muted-foreground text-xs">
      No topology data
    </div>
  );

  return (
    <div className="relative w-full h-full overflow-hidden">
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full h-full"
        style={{ transform: `scale(${zoom})`, transformOrigin: 'center center', transition: 'transform 0.15s' }}>
        <defs>
          <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="rgba(255,255,255,0.15)" />
          </marker>
        </defs>
        {/* Edges */}
        {edges.map((e, i) => {
          const from = topoNodes.find(n => n.id === e.from);
          const to = topoNodes.find(n => n.id === e.to);
          if (!from || !to) return null;
          return (
            <line key={i} x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke="rgba(255,255,255,0.08)" strokeWidth="1"
              markerEnd="url(#arrow)" />
          );
        })}
        {/* Nodes */}
        {topoNodes.map(n => {
          const color = kindColor[n.kind] ?? '#64748b';
          const r = n.kind === 'cluster' ? 26 : n.kind === 'node' ? 20 : 16;
          const dotColor = STATUS_DOT[n.status ?? ''] ? '#22c55e' : '#ef4444';
          return (
            <g key={n.id}>
              <circle cx={n.x} cy={n.y} r={r} fill={`${color}20`} stroke={color} strokeWidth="1.5" />
              {n.kind === 'cluster' && <circle cx={n.x} cy={n.y} r={r + 5} fill="none" stroke={color} strokeWidth="0.5" strokeDasharray="3 3" opacity={0.4} />}
              <text x={n.x} y={n.y} textAnchor="middle" dominantBaseline="middle"
                fill={color} fontSize={n.kind === 'cluster' ? 9 : 8} fontWeight="600">
                {n.kind === 'cluster' ? '⎈' : n.kind === 'node' ? '⬡' : n.kind === 'service' ? '⬡' : '●'}
              </text>
              <text x={n.x} y={n.y + r + 10} textAnchor="middle" fill="rgba(255,255,255,0.55)" fontSize={8.5}>
                {n.label}
              </text>
              {n.count !== undefined && (
                <text x={n.x} y={n.y + r + 19} textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize={7.5}>
                  {n.count} pods
                </text>
              )}
              {/* Status dot */}
              <circle cx={n.x + r - 4} cy={n.y - r + 4} r={4} fill={dotColor} stroke="#0f172a" strokeWidth="1.5" />
            </g>
          );
        })}
      </svg>
      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex flex-wrap gap-2">
        {Object.entries(kindLabel).map(([k, label]) => (
          <div key={k} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full" style={{ background: kindColor[k] }} />
            <span className="text-[9px] text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>
      {/* Zoom */}
      <div className="absolute top-2 right-2 flex items-center gap-1">
        <button onClick={() => setZoom(z => Math.min(1.8, z + 0.2))}
          className="w-6 h-6 rounded border border-border bg-surface-1 text-muted-foreground hover:text-foreground text-xs flex items-center justify-center">+</button>
        <button onClick={() => setZoom(1)}
          className="px-1.5 h-6 rounded border border-border bg-surface-1 text-muted-foreground hover:text-foreground text-[10px] flex items-center justify-center">1:1</button>
        <button onClick={() => setZoom(z => Math.max(0.4, z - 0.2))}
          className="w-6 h-6 rounded border border-border bg-surface-1 text-muted-foreground hover:text-foreground text-xs flex items-center justify-center">−</button>
      </div>
    </div>
  );
}

// ─── Namespace Drawer ─────────────────────────────────────────────────────────

const NS_TABS = ['Pods', 'Deployments', 'Services', 'Ingress', 'Events', 'Security'] as const;
type NsTab = typeof NS_TABS[number];

function NamespaceDrawer({
  ns, clusterId, onClose, findings,
}: {
  ns: NamespaceData; clusterId: string; onClose: () => void; findings: any[];
}) {
  const [tab, setTab] = useState<NsTab>('Pods');
  const [search, setSearch] = useState('');

  const podsQs = new URLSearchParams({ namespace: ns.name, page_size: '30' });
  if (clusterId) podsQs.set('cluster', clusterId);
  const { data: podsRaw, loading: podsLoading } = useApi<any>(`/kubernetes/pods?${podsQs}`);
  const pods: any[] = podsRaw?.data ?? [];

  const { data: deploysRaw, loading: deploysLoading } = useApi<any>(
    `/clusters/${clusterId}/deployments?namespace=${ns.name}`
  );
  const deploys: any[] = deploysRaw?.data ?? deploysRaw ?? [];

  const { data: svcsRaw } = useApi<any>(`/clusters/${clusterId}/services?namespace=${ns.name}`);
  const svcs: any[] = svcsRaw?.data ?? svcsRaw ?? [];

  const { data: ingsRaw } = useApi<any>(`/clusters/${clusterId}/ingresses?namespace=${ns.name}`);
  const ings: any[] = ingsRaw?.data ?? ingsRaw ?? [];

  const nsFindingsOpen = findings.filter(
    f => f.namespace === ns.name && f.status === 'open'
  );

  const filteredPods = pods.filter(p =>
    !search || (p.name ?? '').toLowerCase().includes(search.toLowerCase())
  );

  const scoreColor = ns.security_score !== undefined
    ? ns.security_score >= 80 ? 'text-green-400'
      : ns.security_score >= 50 ? 'text-yellow-400'
      : 'text-red-400'
    : 'text-muted-foreground';

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      {/* Panel */}
      <div className="relative ml-auto w-full max-w-2xl bg-[hsl(230_15%_10%)] border-l border-border flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
              <Boxes className="w-4 h-4 text-purple-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">{ns.name}</h2>
              <p className="text-[10px] text-muted-foreground">
                <span className={clsx('font-medium', STATUS_COLOR[ns.status] ?? 'text-muted-foreground')}>● {ns.status}</span>
                {ns.pod_count !== undefined && <> · {ns.pod_count} pods</>}
                {ns.security_score !== undefined && <> · Security <span className={scoreColor}>{ns.security_score}%</span></>}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 px-4 py-2 border-b border-border flex-shrink-0 overflow-x-auto">
          {NS_TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx(
                'px-3 py-1.5 text-xs rounded-md whitespace-nowrap transition-colors',
                tab === t ? 'bg-white/8 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground',
              )}>
              {t}
              {t === 'Security' && nsFindingsOpen.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 text-[9px] rounded-full bg-red-500/20 text-red-400">
                  {nsFindingsOpen.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Search (pods/deploys) */}
        {(tab === 'Pods' || tab === 'Deployments') && (
          <div className="px-4 py-2 border-b border-border flex-shrink-0">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Filter resources…"
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-white/5 border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/50" />
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {/* PODS */}
          {tab === 'Pods' && (
            <>
              {podsLoading ? (
                [...Array(5)].map((_, i) => <Sk key={i} className="h-10 rounded-lg" />)
              ) : filteredPods.length === 0 ? (
                <EmptyState icon={Box} title="No pods" desc={search ? 'No pods match your search.' : 'No pods running in this namespace.'} />
              ) : (
                <div className="space-y-1">
                  {filteredPods.map((p: any, i: number) => (
                    <div key={p.id ?? i} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/3 hover:bg-white/5 transition-colors">
                      <div className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', STATUS_DOT[p.status] ?? 'bg-slate-500')} />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">{p.name}</p>
                        <p className="text-[10px] text-muted-foreground">
                          {p.image && <span className="font-mono truncate">{p.image}</span>}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 text-[10px] text-muted-foreground flex-shrink-0">
                        {p.restart_count > 0 && (
                          <span className="text-orange-400">↻ {p.restart_count}</span>
                        )}
                        <span className={STATUS_COLOR[p.status] ?? 'text-muted-foreground'}>{p.status}</span>
                        <div className="flex items-center gap-1">
                          <button title="View Logs" className="p-1 hover:text-foreground transition-colors">
                            <Terminal className="w-3 h-3" />
                          </button>
                          <button title="YAML" className="p-1 hover:text-foreground transition-colors">
                            <FileCode className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* DEPLOYMENTS */}
          {tab === 'Deployments' && (
            <>
              {deploysLoading ? (
                [...Array(4)].map((_, i) => <Sk key={i} className="h-10 rounded-lg" />)
              ) : deploys.length === 0 ? (
                <EmptyState icon={GitBranch} title="No deployments" desc="No deployments found in this namespace." />
              ) : (
                <div className="space-y-1">
                  {deploys.filter((d: any) => !search || (d.name ?? '').toLowerCase().includes(search.toLowerCase())).map((d: any, i: number) => (
                    <div key={d.name ?? i} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/3 hover:bg-white/5 transition-colors">
                      <GitBranch className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">{d.name}</p>
                        <p className="text-[10px] text-muted-foreground">
                          {d.ready_replicas ?? 0}/{d.replicas ?? 0} ready
                        </p>
                      </div>
                      <span className={clsx('text-[10px] font-medium',
                        (d.ready_replicas ?? 0) === (d.replicas ?? 0) ? 'text-green-400' : 'text-orange-400')}>
                        {(d.ready_replicas ?? 0) === (d.replicas ?? 0) ? 'Healthy' : 'Degraded'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* SERVICES */}
          {tab === 'Services' && (
            svcs.length === 0 ? (
              <EmptyState icon={Network} title="No services" desc="No services found in this namespace." />
            ) : (
              <div className="space-y-1">
                {svcs.map((s: any, i: number) => (
                  <div key={s.name ?? i} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/3">
                    <Network className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{s.name}</p>
                      <p className="text-[10px] text-muted-foreground font-mono">
                        {s.cluster_ip ?? '—'} · {s.type ?? 'ClusterIP'}
                      </p>
                    </div>
                    {s.type === 'LoadBalancer' && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-400 border border-orange-500/20">
                        Exposed
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )
          )}

          {/* INGRESS */}
          {tab === 'Ingress' && (
            ings.length === 0 ? (
              <EmptyState icon={Globe} title="No ingress resources" desc="No ingress routes defined in this namespace." />
            ) : (
              <div className="space-y-1">
                {ings.map((ing: any, i: number) => (
                  <div key={ing.name ?? i} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/3">
                    <Globe className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{ing.name}</p>
                      {ing.hosts && (
                        <p className="text-[10px] text-muted-foreground font-mono">{Array.isArray(ing.hosts) ? ing.hosts.join(', ') : ing.hosts}</p>
                      )}
                    </div>
                    {ing.tls && <span className="text-[10px] text-green-400">TLS</span>}
                  </div>
                ))}
              </div>
            )
          )}

          {/* EVENTS */}
          {tab === 'Events' && (
            <EmptyState icon={Activity} title="Events not available" desc="Connect your cluster to stream live Kubernetes events." />
          )}

          {/* SECURITY */}
          {tab === 'Security' && (
            <>
              {nsFindingsOpen.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-10">
                  <div className="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center">
                    <Shield className="w-6 h-6 text-green-400" />
                  </div>
                  <p className="text-sm font-medium text-foreground">Clean namespace</p>
                  <p className="text-xs text-muted-foreground text-center max-w-xs">
                    No open security findings for this namespace. Run a scan to refresh.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {nsFindingsOpen.map((f: any) => (
                    <div key={f.id} className={clsx('p-3 rounded-lg border', SEV_BG[f.severity])}>
                      <div className="flex items-start gap-2">
                        <span className={clsx('text-[10px] font-medium uppercase px-1.5 py-0.5 rounded border', SEV_BG[f.severity], SEV_COLOR[f.severity])}>
                          {f.severity}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-foreground">{f.title}</p>
                          {f.resource_kind && (
                            <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                              {f.resource_kind}/{f.resource_name}
                            </p>
                          )}
                        </div>
                      </div>
                      {f.remediation && (
                        <p className="text-[10px] text-muted-foreground mt-2 leading-relaxed">{f.remediation}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Empty State ──────────────────────────────────────────────────────────────

function EmptyState({
  icon: Icon, title, desc, action, onAction,
}: {
  icon: React.ElementType; title: string; desc: string; action?: string; onAction?: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <div className="w-12 h-12 rounded-xl bg-white/4 flex items-center justify-center">
        <Icon className="w-6 h-6 text-muted-foreground opacity-50" />
      </div>
      <div>
        <p className="text-sm font-medium text-foreground mb-1">{title}</p>
        <p className="text-xs text-muted-foreground max-w-xs">{desc}</p>
      </div>
      {action && onAction && (
        <button onClick={onAction}
          className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
          <Plus className="w-3.5 h-3.5" /> {action}
        </button>
      )}
    </div>
  );
}

// ─── No Cluster Connected ─────────────────────────────────────────────────────

function NoClusterState() {
  return (
    <div className="flex flex-col items-center gap-6 py-20 text-center max-w-md mx-auto">
      <div className="w-20 h-20 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
        <Server className="w-10 h-10 text-indigo-400 opacity-60" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-foreground mb-2">No Kubernetes cluster connected</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Connect your Kubernetes cluster using a kubeconfig file to start monitoring
          resources, security posture, and live workloads.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <button className="flex items-center gap-2 px-5 py-2.5 text-sm rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white transition-colors font-medium">
          <Plus className="w-4 h-4" /> Connect Cluster
        </button>
        <button className="flex items-center gap-2 px-4 py-2.5 text-sm rounded-xl border border-border text-muted-foreground hover:text-foreground transition-colors">
          <Info className="w-4 h-4" /> Learn more
        </button>
      </div>
      <div className="w-full grid grid-cols-3 gap-3 pt-2">
        {[
          { label: 'EKS', icon: '☁', desc: 'Amazon Elastic Kubernetes' },
          { label: 'GKE', icon: '☁', desc: 'Google Kubernetes Engine' },
          { label: 'AKS', icon: '☁', desc: 'Azure Kubernetes Service' },
        ].map(p => (
          <div key={p.label} className="p-3 rounded-xl border border-border bg-white/2 text-center">
            <div className="text-2xl mb-1">{p.icon}</div>
            <p className="text-xs font-semibold text-foreground">{p.label}</p>
            <p className="text-[10px] text-muted-foreground">{p.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Severity Bar ─────────────────────────────────────────────────────────────

function SevBar({ by_severity }: { by_severity: Record<string, number> }) {
  const total = Object.values(by_severity).reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="flex h-1.5 rounded-full overflow-hidden w-full mt-1">
      {(['critical', 'high', 'medium', 'low', 'info'] as const).map(sev => {
        const pct = ((by_severity[sev] ?? 0) / total) * 100;
        if (!pct) return null;
        return <div key={sev} style={{ width: `${pct}%` }} className={SEV_DOT[sev]} title={`${sev}: ${by_severity[sev]}`} />;
      })}
    </div>
  );
}

// ─── Finding Row ──────────────────────────────────────────────────────────────

const FindingRow = memo(function FindingRow({
  finding, expanded, onToggle, onResolve, onSuppress,
}: {
  finding: any; expanded: boolean;
  onToggle: () => void; onResolve: () => void; onSuppress: () => void;
}) {
  const sev = finding.severity as string;
  return (
    <>
      <tr onClick={onToggle}
        className="border-b border-border/40 hover:bg-white/2 cursor-pointer transition-colors">
        <td className="px-3 py-2.5">
          <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border', SEV_BG[sev], SEV_COLOR[sev])}>
            <span className={clsx('w-1.5 h-1.5 rounded-full', SEV_DOT[sev])} />
            {sev}
          </span>
        </td>
        <td className="px-3 py-2.5 max-w-[240px]">
          <p className="text-xs text-foreground font-medium leading-snug truncate">{finding.title}</p>
          {finding.namespace && <p className="text-[10px] text-muted-foreground">ns: {finding.namespace}</p>}
        </td>
        <td className="px-3 py-2.5 text-[10px] text-muted-foreground whitespace-nowrap">
          {CAT_LABEL[finding.category] ?? finding.category}
        </td>
        <td className="px-3 py-2.5 font-mono text-[10px] text-muted-foreground whitespace-nowrap">
          {finding.resource_kind && `${finding.resource_kind}/${finding.resource_name}`}
        </td>
        <td className="px-3 py-2.5 font-mono text-[10px] text-blue-400/80">
          {finding.cis_control}
        </td>
        <td className="px-3 py-2.5 text-[10px] text-muted-foreground whitespace-nowrap">
          {fmtDate(finding.last_seen_at, true)}
        </td>
        <td className="px-3 py-2.5">
          {expanded ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                    : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border/40 bg-white/1">
          <td colSpan={7} className="px-5 py-3">
            <div className="grid md:grid-cols-2 gap-4 mb-3">
              <div>
                <p className="text-[11px] font-semibold text-muted-foreground mb-1 uppercase tracking-wide">Description</p>
                <p className="text-xs text-foreground leading-relaxed">{finding.description || '—'}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-green-400 mb-1 uppercase tracking-wide">Remediation</p>
                <p className="text-xs text-foreground leading-relaxed">{finding.remediation || '—'}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 pt-2 border-t border-border/40">
              <span className="text-[10px] text-muted-foreground flex-1">
                {finding.scanner && `Scanner: ${finding.scanner}`}
                {finding.framework && ` · ${finding.framework}`}
              </span>
              <button onClick={e => { e.stopPropagation(); onResolve(); }}
                className="flex items-center gap-1 px-2.5 py-1 text-[11px] rounded-md bg-green-500/10 text-green-400 border border-green-500/20 hover:bg-green-500/20 transition-colors">
                <CheckCircle className="w-3 h-3" /> Resolve
              </button>
              <button onClick={e => { e.stopPropagation(); onSuppress(); }}
                className="flex items-center gap-1 px-2.5 py-1 text-[11px] rounded-md bg-white/5 text-muted-foreground border border-border hover:text-foreground transition-colors">
                <EyeOff className="w-3 h-3" /> Suppress
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  );
});

// ─── Scan History ─────────────────────────────────────────────────────────────

function ScanHistory({ clusterId }: { clusterId: string }) {
  const { data: raw } = useApi<any>(`/k8s/clusters/${clusterId}/scan-history?limit=4`);
  const history: any[] = raw?.data ?? raw ?? [];
  if (!history.length) return null;
  return (
    <div className="card-base p-3">
      <p className="text-[11px] font-semibold text-foreground mb-2 flex items-center gap-1.5">
        <Clock className="w-3 h-3 text-muted-foreground" /> Recent Scans
      </p>
      <div className="space-y-1.5">
        {history.map((scan: any) => (
          <div key={scan.id} className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {scan.status === 'completed'
                ? <CheckCircle className="w-3 h-3 text-green-400" />
                : scan.status === 'running'
                  ? <RefreshCw className="w-3 h-3 text-blue-400 animate-spin" />
                  : <AlertTriangle className="w-3 h-3 text-red-400" />}
              <span className="text-[10px] text-muted-foreground">{fmtDate(scan.completed_at ?? scan.started_at, true)}</span>
            </div>
            <div className="flex items-center gap-2 text-[10px]">
              <span className="text-foreground">{scan.findings_count} findings</span>
              {scan.risk_score != null && (
                <span className="font-medium" style={{
                  color: scan.risk_score >= 70 ? '#ef4444' : scan.risk_score >= 40 ? '#f97316' : '#22c55e',
                }}>Risk {Math.round(scan.risk_score)}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

const VIEW_TABS = ['Overview', 'Namespaces', 'Security Findings', 'Nodes'] as const;
type ViewTab = typeof VIEW_TABS[number];

export default function KubernetesSecurity() {
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const [scanningCluster, setScanningCluster] = useState<string | null>(null);
  const [viewTab, setViewTab] = useState<ViewTab>('Overview');
  const [nsSearch, setNsSearch] = useState('');
  const [openNs, setOpenNs] = useState<NamespaceData | null>(null);
  const [severityFilter, setSeverityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('open');
  const [findingsPage, setFindingsPage] = useState(1);
  const [expandedFinding, setExpandedFinding] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const PAGE_SIZE = 20;

  // ── Data fetching ──────────────────────────────────────────────────────────

  const { data: clustersRaw, loading: clustersLoading, refetch: refetchClusters } =
    useApi<any>('/k8s/clusters');
  const clusters: Cluster[] = useMemo(() => clustersRaw?.data ?? clustersRaw ?? [], [clustersRaw]);

  const cluster = useMemo(
    () => clusters.find(c => c.id === selectedCluster) ?? null,
    [clusters, selectedCluster],
  );

  // Pod stats (global or per-cluster)
  const { data: podStats, loading: podStatsLoading, refetch: refetchPodStats } =
    useApi<any>('/kubernetes/pods/stats');

  // Security stats
  const statsQs = selectedCluster ? `?cluster_id=${selectedCluster}` : '';
  const { data: secStatsRaw, refetch: refetchSecStats } =
    useApi<any>(`/k8s/findings/stats${statsQs}`);
  const secStats = secStatsRaw?.data ?? secStatsRaw;

  // Cluster-specific resources (only when a cluster is selected)
  const { data: nodesRaw, loading: nodesLoading } =
    useApi<any>(selectedCluster ? `/clusters/${selectedCluster}/nodes` : null);
  const nodes: NodeData[] = nodesRaw?.data ?? nodesRaw ?? [];

  const { data: namespacesRaw, loading: nsLoading } =
    useApi<any>(selectedCluster ? `/clusters/${selectedCluster}/namespaces` : null);
  const namespaces: NamespaceData[] = namespacesRaw?.data ?? namespacesRaw ?? [];

  const { data: deploymentsRaw } =
    useApi<any>(selectedCluster ? `/clusters/${selectedCluster}/deployments` : null);
  const deployments: any[] = deploymentsRaw?.data ?? deploymentsRaw ?? [];

  const { data: servicesRaw } =
    useApi<any>(selectedCluster ? `/clusters/${selectedCluster}/services` : null);
  const services: any[] = servicesRaw?.data ?? servicesRaw ?? [];

  // Cluster summary (workloads)
  const summaryQs = selectedCluster ? `?cluster=${selectedCluster}` : '';
  const { data: summaryRaw } = useApi<any>(`/kubernetes/pods/cluster/summary${summaryQs}`);
  const summary = summaryRaw?.data ?? summaryRaw;

  // Findings
  const findQs = new URLSearchParams({ page: String(findingsPage), page_size: String(PAGE_SIZE) });
  if (selectedCluster) findQs.set('cluster_id', selectedCluster);
  if (severityFilter)  findQs.set('severity', severityFilter);
  if (categoryFilter)  findQs.set('category', categoryFilter);
  if (statusFilter)    findQs.set('status', statusFilter);
  const { data: findingsRaw, loading: findingsLoading, refetch: refetchFindings } =
    useApi<any>(`/k8s/findings?${findQs}`);
  const findingsPage_data = findingsRaw?.data ?? findingsRaw;
  const findings: any[] = findingsPage_data?.data ?? [];
  const findingsTotal: number = findingsPage_data?.total ?? 0;
  const findingsPages: number = findingsPage_data?.pages ?? 1;

  // Auto-select first cluster
  useEffect(() => {
    if (!selectedCluster && clusters.length > 0) {
      setSelectedCluster(clusters[0].id);
    }
  }, [clusters, selectedCluster]);

  // ── Actions ────────────────────────────────────────────────────────────────

  const handleScan = useCallback(async (clusterId: string) => {
    setScanningCluster(clusterId);
    try {
      await apiPost(`/k8s/clusters/${clusterId}/scan`, {});
      setTimeout(() => { refetchClusters(); refetchSecStats(); refetchFindings(); }, 2500);
    } catch (e) {
      console.error('Scan failed', e);
    } finally {
      setTimeout(() => setScanningCluster(null), 4000);
    }
  }, [refetchClusters, refetchSecStats, refetchFindings]);

  const handleResolve = useCallback(async (id: string) => {
    try { await apiPatch(`/k8s/findings/${id}/resolve`, {}); refetchFindings(); refetchSecStats(); }
    catch (e) { console.error(e); }
  }, [refetchFindings, refetchSecStats]);

  const handleSuppress = useCallback(async (id: string) => {
    try { await apiPatch(`/k8s/findings/${id}/suppress`, {}); refetchFindings(); }
    catch (e) { console.error(e); }
  }, [refetchFindings]);

  const handleRefresh = useCallback(() => {
    refetchClusters(); refetchSecStats(); refetchFindings(); refetchPodStats();
  }, [refetchClusters, refetchSecStats, refetchFindings, refetchPodStats]);

  // ── Derived data ───────────────────────────────────────────────────────────

  const filteredNs = useMemo(
    () => namespaces.filter(ns => !nsSearch || ns.name.toLowerCase().includes(nsSearch.toLowerCase())),
    [namespaces, nsSearch],
  );

  const totalPods = podStats?.total ?? 0;
  const runningPods = podStats?.running ?? 0;
  const pendingPods = podStats?.pending ?? 0;
  const failedPods = podStats?.failed ?? 0;
  const cpuPct = podStats?.cpu_percent ?? podStats?.cpu_usage ?? null;
  const memPct = podStats?.memory_percent ?? podStats?.memory_usage ?? null;

  const criticalFindings = secStats?.by_severity?.critical ?? 0;
  const highFindings = secStats?.by_severity?.high ?? 0;

  // ── No clusters ────────────────────────────────────────────────────────────

  if (!clustersLoading && clusters.length === 0) {
    return (
      <div className="space-y-4">
        <DashHeader clusters={clusters} cluster={cluster} scanningCluster={scanningCluster}
          onScan={handleScan} onRefresh={handleRefresh} showFilters={showFilters}
          setShowFilters={setShowFilters} />
        <NoClusterState />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <DashHeader clusters={clusters} cluster={cluster} scanningCluster={scanningCluster}
        onScan={handleScan} onRefresh={handleRefresh} showFilters={showFilters}
        setShowFilters={setShowFilters} />

      {/* ── Cluster selector strip ── */}
      {clusters.length > 1 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {clusters.map(c => (
            <button key={c.id} onClick={() => setSelectedCluster(c.id)}
              className={clsx(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border whitespace-nowrap transition-all',
                selectedCluster === c.id
                  ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-300'
                  : 'border-border text-muted-foreground hover:text-foreground',
              )}>
              <span className={clsx('w-1.5 h-1.5 rounded-full', STATUS_DOT[c.status] ?? 'bg-slate-500')} />
              {c.name}
              {c.findings_count > 0 && (
                <span className="px-1.5 py-0.5 text-[9px] rounded-full bg-red-500/20 text-red-400">
                  {c.findings_count}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* ── Summary cards row 1 ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <SummaryCard label="Connected Clusters" value={clusters.length} icon={Server} color="text-indigo-400" loading={clustersLoading} />
        <SummaryCard label="Nodes" value={cluster?.node_count ?? nodes.length ?? 0} icon={HardDrive} color="text-blue-400" loading={nodesLoading} />
        <SummaryCard label="Namespaces" value={namespaces.length || cluster?.pod_count !== undefined ? namespaces.length : '—'} icon={Layers} color="text-purple-400" loading={nsLoading} />
        <SummaryCard label="Total Pods" value={(totalPods || cluster?.pod_count) ?? '—'} icon={Box} color="text-cyan-400" loading={podStatsLoading} />
        <SummaryCard label="Running Pods" value={runningPods} icon={CircleDot} color="text-green-400"
          sub={totalPods > 0 ? `${Math.round((runningPods / totalPods) * 100)}% healthy` : undefined} loading={podStatsLoading} />
        <SummaryCard label="Deployments" value={(deployments.length || summary?.deployments?.length) ?? '—'} icon={GitBranch} color="text-blue-400" />
      </div>

      {/* ── Summary cards row 2 ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <SummaryCard label="DaemonSets" value={summary?.daemonsets?.length ?? '—'} icon={Workflow} color="text-violet-400" />
        <SummaryCard label="StatefulSets" value={summary?.statefulsets?.length ?? '—'} icon={Database} color="text-pink-400" />
        <SummaryCard label="Pending Pods" value={pendingPods} icon={Clock} color="text-yellow-400" loading={podStatsLoading} />
        <SummaryCard label="Failed Pods" value={failedPods} icon={AlertCircle} color="text-red-400" loading={podStatsLoading} />
        <SummaryCard label="CPU Usage" value={cpuPct !== null ? `${typeof cpuPct === 'number' ? cpuPct.toFixed(1) : cpuPct}%` : '—'}
          icon={Cpu} color={cpuPct !== null && cpuPct > 80 ? 'text-red-400' : 'text-blue-400'} loading={podStatsLoading} />
        <SummaryCard label="Memory Usage" value={memPct !== null ? `${typeof memPct === 'number' ? memPct.toFixed(1) : memPct}%` : '—'}
          icon={MemoryStick} color={memPct !== null && memPct > 80 ? 'text-red-400' : 'text-blue-400'} loading={podStatsLoading} />
      </div>

      {/* ── Cluster info + Security summary ── */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* Cluster Status */}
        <div className="card-base p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-indigo-400" /> Cluster Status
            </p>
            {cluster && (
              <button onClick={() => handleScan(cluster.id)} disabled={!!scanningCluster || cluster.status === 'disconnected'}
                className="flex items-center gap-1 px-2.5 py-1 text-[11px] rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/20 transition-colors disabled:opacity-40">
                <Play className={clsx('w-3 h-3', scanningCluster === cluster.id && 'animate-spin')} />
                {scanningCluster === cluster.id ? 'Scanning…' : 'Scan'}
              </button>
            )}
          </div>
          {cluster ? (
            <div className="space-y-2">
              {[
                { label: 'Status', value: <span className={clsx('font-medium', STATUS_COLOR[cluster.status] ?? 'text-muted-foreground')}>● {cluster.status}</span> },
                { label: 'Provider', value: cluster.provider },
                { label: 'Version', value: cluster.k8s_version ?? '—' },
                { label: 'Distribution', value: cluster.distribution ?? 'Standard' },
                { label: 'API Server', value: <span className="font-mono text-[10px] truncate">{cluster.api_server_url ?? '—'}</span> },
                { label: 'Last Sync', value: timeAgo(cluster.last_sync) },
              ].map(row => (
                <div key={row.label} className="flex items-center gap-2">
                  <span className="text-[11px] text-muted-foreground w-24 flex-shrink-0">{row.label}</span>
                  <span className="text-[11px] text-foreground truncate">{row.value}</span>
                </div>
              ))}
              {secStats?.by_severity && <SevBar by_severity={secStats.by_severity} />}
            </div>
          ) : clustersLoading ? (
            <div className="space-y-2">{[...Array(6)].map((_, i) => <Sk key={i} className="h-4 rounded" />)}</div>
          ) : (
            <p className="text-xs text-muted-foreground">Select a cluster to see details.</p>
          )}
        </div>

        {/* Security Summary */}
        <div className="card-base p-4">
          <p className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-red-400" /> Security Summary
          </p>
          {secStats ? (
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: 'Critical', value: criticalFindings, cls: 'text-red-400', bg: 'bg-red-500/10' },
                { label: 'High', value: highFindings, cls: 'text-orange-400', bg: 'bg-orange-500/10' },
                { label: 'Medium', value: secStats?.by_severity?.medium ?? 0, cls: 'text-yellow-400', bg: 'bg-yellow-500/10' },
                { label: 'Misconfigs', value: secStats?.by_category?.cis_benchmark ?? 0, cls: 'text-purple-400', bg: 'bg-purple-500/10' },
                { label: 'Exposed Svcs', value: secStats?.by_category?.exposed_services ?? 0, cls: 'text-orange-400', bg: 'bg-orange-500/10' },
                { label: 'Priv. Containers', value: secStats?.by_category?.privileged_containers ?? 0, cls: 'text-red-400', bg: 'bg-red-500/10' },
                { label: 'RBAC Issues', value: secStats?.by_category?.rbac ?? 0, cls: 'text-yellow-400', bg: 'bg-yellow-500/10' },
                { label: 'Net Policy', value: secStats?.by_category?.network_policy ?? 0, cls: 'text-blue-400', bg: 'bg-blue-500/10' },
                { label: 'Secrets Exp.', value: secStats?.by_category?.secrets ?? 0, cls: 'text-pink-400', bg: 'bg-pink-500/10' },
              ].map(item => (
                <div key={item.label} className={clsx('rounded-lg p-2 text-center', item.bg)}>
                  <div className={clsx('text-lg font-bold tabular-nums', item.cls)}>{item.value}</div>
                  <div className="text-[10px] text-muted-foreground leading-tight">{item.label}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              {[...Array(9)].map((_, i) => <Sk key={i} className="h-14 rounded-lg" />)}
            </div>
          )}
          {cluster && (
            <button onClick={() => { setViewTab('Security Findings'); }}
              className="mt-3 w-full flex items-center justify-center gap-1 py-2 text-xs rounded-lg border border-border text-muted-foreground hover:text-foreground hover:border-white/20 transition-colors">
              View all findings <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* ── View Tab navigation ── */}
      <div className="flex items-center gap-1 border-b border-border pb-0">
        {VIEW_TABS.map(t => (
          <button key={t} onClick={() => setViewTab(t)}
            className={clsx(
              'px-4 py-2 text-xs font-medium border-b-2 transition-colors -mb-px whitespace-nowrap',
              viewTab === t
                ? 'border-indigo-500 text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}>
            {t}
            {t === 'Security Findings' && (criticalFindings > 0 || highFindings > 0) && (
              <span className="ml-1.5 px-1.5 py-0.5 text-[9px] rounded-full bg-red-500/20 text-red-400">
                {criticalFindings + highFindings}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ════════════════ OVERVIEW TAB ════════════════ */}
      {viewTab === 'Overview' && (
        <div className="grid lg:grid-cols-[1fr_420px] gap-4">
          {/* Left: Resource usage + Nodes */}
          <div className="space-y-4">
            {/* Resource usage */}
            <div className="card-base p-4">
              <p className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-blue-400" /> Resource Usage
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'CPU', value: cpuPct !== null ? `${typeof cpuPct === 'number' ? cpuPct.toFixed(1) : cpuPct}%` : '—',
                    color: cpuPct > 80 ? '#ef4444' : cpuPct > 60 ? '#f97316' : '#3b82f6', loading: podStatsLoading },
                  { label: 'Memory', value: memPct !== null ? `${typeof memPct === 'number' ? memPct.toFixed(1) : memPct}%` : '—',
                    color: memPct > 80 ? '#ef4444' : memPct > 60 ? '#f97316' : '#8b5cf6', loading: podStatsLoading },
                  { label: 'Running Pods', value: runningPods, color: '#22c55e', loading: podStatsLoading },
                  { label: 'Restart Count', value: podStats?.restart_count ?? '—', color: '#f59e0b', loading: podStatsLoading },
                ].map(m => (
                  <div key={m.label} className="rounded-xl border border-border bg-white/2 p-3 text-center">
                    {m.loading ? (
                      <><Sk className="h-6 w-12 mx-auto mb-1" /><Sk className="h-3 w-16 mx-auto" /></>
                    ) : (
                      <>
                        <div className="text-xl font-bold tabular-nums mb-0.5" style={{ color: m.color }}>{m.value}</div>
                        <div className="text-[10px] text-muted-foreground">{m.label}</div>
                      </>
                    )}
                  </div>
                ))}
              </div>
              {!podStatsLoading && podStats === null && (
                <p className="text-xs text-muted-foreground text-center mt-3 py-2 border border-dashed border-border/50 rounded-lg">
                  Metrics unavailable — metrics-server not detected in cluster
                </p>
              )}
            </div>

            {/* Nodes table */}
            {selectedCluster && (
              <div className="card-base overflow-hidden">
                <div className="px-4 py-3 border-b border-border">
                  <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <HardDrive className="w-3.5 h-3.5 text-blue-400" /> Nodes
                    {nodes.length > 0 && <span className="text-muted-foreground font-normal">({nodes.length})</span>}
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[480px]">
                    <thead>
                      <tr className="border-b border-border bg-white/2">
                        {['Node', 'Status', 'Roles', 'CPU', 'Memory', 'Pods', 'Version'].map(h => (
                          <th key={h} className="text-left text-[11px] font-medium text-muted-foreground px-3 py-2.5 whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {nodesLoading ? (
                        [...Array(3)].map((_, i) => (
                          <tr key={i} className="border-b border-border/40">
                            {[...Array(7)].map((_, j) => <td key={j} className="px-3 py-2.5"><Sk className="h-3.5 rounded" /></td>)}
                          </tr>
                        ))
                      ) : nodes.length === 0 ? (
                        <tr><td colSpan={7} className="px-4 py-8 text-center text-xs text-muted-foreground">
                          No nodes data — ensure cluster is connected
                        </td></tr>
                      ) : (
                        nodes.map(n => (
                          <tr key={n.name} className="border-b border-border/40 hover:bg-white/2 transition-colors">
                            <td className="px-3 py-2.5 text-xs font-medium text-foreground truncate max-w-[140px]">{n.name}</td>
                            <td className="px-3 py-2.5">
                              <span className={clsx('text-[10px] font-medium', STATUS_COLOR[n.status] ?? 'text-muted-foreground')}>● {n.status}</span>
                            </td>
                            <td className="px-3 py-2.5 text-[10px] text-muted-foreground">
                              {Array.isArray(n.roles) ? n.roles.join(', ') : n.roles ?? '—'}
                            </td>
                            <td className="px-3 py-2.5 text-[10px] text-muted-foreground">{n.cpu_usage ?? n.cpu_capacity ?? '—'}</td>
                            <td className="px-3 py-2.5 text-[10px] text-muted-foreground">{n.memory_usage ?? n.memory_capacity ?? '—'}</td>
                            <td className="px-3 py-2.5 text-[10px] text-muted-foreground">{n.pod_count ?? '—'}</td>
                            <td className="px-3 py-2.5 text-[10px] font-mono text-muted-foreground">{n.version ?? '—'}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Right: Topology + Scan History */}
          <div className="space-y-4">
            <div className="card-base p-4 h-[380px] flex flex-col">
              <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5 flex-shrink-0">
                <Link2 className="w-3.5 h-3.5 text-indigo-400" /> Cluster Topology
              </p>
              <div className="flex-1 min-h-0">
                <TopologyGraph cluster={cluster} nodes={nodes} namespaces={namespaces} pods={[]} services={services} />
              </div>
            </div>

            {selectedCluster && <ScanHistory clusterId={selectedCluster} />}

            {/* Category breakdown */}
            {secStats?.by_category && Object.keys(secStats.by_category).length > 0 && (
              <div className="card-base p-4">
                <p className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
                  <BarChart3 className="w-3.5 h-3.5 text-muted-foreground" /> Findings by Category
                </p>
                <div className="space-y-2">
                  {Object.entries(secStats.by_category as Record<string, number>)
                    .sort((a, b) => b[1] - a[1])
                    .map(([cat, count]) => {
                      const max = Math.max(...Object.values(secStats.by_category as Record<string, number>)) || 1;
                      return (
                        <div key={cat} className="flex items-center gap-2">
                          <span className="text-[11px] text-muted-foreground w-36 truncate">{CAT_LABEL[cat] ?? cat}</span>
                          <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                            <div className="h-full rounded-full bg-indigo-500/60 transition-all" style={{ width: `${((count as number) / max) * 100}%` }} />
                          </div>
                          <span className="text-[11px] font-medium text-foreground w-5 text-right">{count as number}</span>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════ NAMESPACES TAB ════════════════ */}
      {viewTab === 'Namespaces' && (
        <div className="space-y-3">
          {/* Namespace search */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input value={nsSearch} onChange={e => setNsSearch(e.target.value)}
                placeholder="Search namespaces…"
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-white/5 border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-indigo-500/50" />
            </div>
            <span className="text-xs text-muted-foreground">{filteredNs.length} namespaces</span>
          </div>

          {!selectedCluster ? (
            <div className="card-base py-12 text-center">
              <p className="text-sm text-muted-foreground">Select a cluster above to view namespaces.</p>
            </div>
          ) : (
            <div className="card-base overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[700px]">
                  <thead>
                    <tr className="border-b border-border bg-white/2 sticky top-0">
                      {['Namespace', 'Status', 'Pods', 'Deployments', 'CPU', 'Memory', 'Restarts', 'Net Policies', 'Actions'].map(h => (
                        <th key={h} className="text-left text-[11px] font-medium text-muted-foreground px-3 py-2.5 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {nsLoading ? (
                      [...Array(8)].map((_, i) => (
                        <tr key={i} className="border-b border-border/40">
                          {[...Array(9)].map((_, j) => <td key={j} className="px-3 py-2.5"><Sk className="h-3.5 rounded" /></td>)}
                        </tr>
                      ))
                    ) : filteredNs.length === 0 ? (
                      <tr><td colSpan={9} className="py-12">
                        <EmptyState icon={Layers} title="No namespaces found"
                          desc={nsSearch ? 'No namespaces match your search.' : 'No namespaces discovered in this cluster.'} />
                      </td></tr>
                    ) : (
                      filteredNs.map(ns => (
                        <tr key={ns.name}
                          className="border-b border-border/40 hover:bg-white/2 cursor-pointer transition-colors"
                          onClick={() => setOpenNs(ns)}>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-2">
                              <Boxes className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
                              <span className="text-xs font-medium text-foreground">{ns.name}</span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className={clsx('text-[10px] font-medium', STATUS_COLOR[ns.status] ?? 'text-muted-foreground')}>
                              ● {ns.status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-[11px] text-muted-foreground tabular-nums">{ns.pod_count ?? '—'}</td>
                          <td className="px-3 py-2.5 text-[11px] text-muted-foreground tabular-nums">{ns.deployment_count ?? '—'}</td>
                          <td className="px-3 py-2.5 text-[11px] text-muted-foreground">{ns.cpu_usage ?? '—'}</td>
                          <td className="px-3 py-2.5 text-[11px] text-muted-foreground">{ns.memory_usage ?? '—'}</td>
                          <td className="px-3 py-2.5">
                            {ns.restart_count !== undefined && ns.restart_count > 0 ? (
                              <span className="text-[11px] text-orange-400">↻ {ns.restart_count}</span>
                            ) : <span className="text-[11px] text-muted-foreground">0</span>}
                          </td>
                          <td className="px-3 py-2.5 text-[11px] text-muted-foreground tabular-nums">{ns.network_policies ?? '—'}</td>
                          <td className="px-3 py-2.5">
                            <button onClick={e => { e.stopPropagation(); setOpenNs(ns); }}
                              className="flex items-center gap-1 px-2 py-1 text-[10px] rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-white/20 transition-colors">
                              Details <ChevronRight className="w-3 h-3" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ════════════════ SECURITY FINDINGS TAB ════════════════ */}
      {viewTab === 'Security Findings' && (
        <div className="space-y-3">
          {/* Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={() => setShowFilters(f => !f)}
              className={clsx('flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors',
                showFilters ? 'border-indigo-500/40 text-indigo-400 bg-indigo-500/10' : 'border-border text-muted-foreground hover:text-foreground')}>
              <Filter className="w-3.5 h-3.5" /> Filters
            </button>
            {severityFilter && (
              <span className={clsx('flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-full border cursor-pointer', SEV_BG[severityFilter], SEV_COLOR[severityFilter])}
                onClick={() => setSeverityFilter('')}>
                {severityFilter} <X className="w-2.5 h-2.5" />
              </span>
            )}
            {categoryFilter && (
              <span className="flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-full border border-border text-muted-foreground cursor-pointer"
                onClick={() => setCategoryFilter('')}>
                {CAT_LABEL[categoryFilter] ?? categoryFilter} <X className="w-2.5 h-2.5" />
              </span>
            )}
            <span className="ml-auto text-xs text-muted-foreground">{findingsTotal} findings</span>
          </div>

          {showFilters && (
            <div className="card-base p-3 grid sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Severity</label>
                <select value={severityFilter} onChange={e => { setSeverityFilter(e.target.value); setFindingsPage(1); }}
                  className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
                  <option value="">All Severities</option>
                  {['critical', 'high', 'medium', 'low', 'info'].map(s => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Category</label>
                <select value={categoryFilter} onChange={e => { setCategoryFilter(e.target.value); setFindingsPage(1); }}
                  className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
                  <option value="">All Categories</option>
                  {Object.entries(CAT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-muted-foreground block mb-1">Status</label>
                <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setFindingsPage(1); }}
                  className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none">
                  <option value="">All Statuses</option>
                  {['open', 'resolved', 'suppressed'].map(s => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <div className="card-base overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px]">
                <thead>
                  <tr className="border-b border-border bg-white/2">
                    {['Severity', 'Finding', 'Category', 'Resource', 'CIS', 'Last Seen', ''].map(h => (
                      <th key={h} className="text-left text-[11px] font-medium text-muted-foreground px-3 py-2.5 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {findingsLoading ? (
                    [...Array(8)].map((_, i) => (
                      <tr key={i} className="border-b border-border/40">
                        {[...Array(7)].map((_, j) => <td key={j} className="px-3 py-3"><Sk className="h-3.5 rounded" /></td>)}
                      </tr>
                    ))
                  ) : findings.length === 0 ? (
                    <tr><td colSpan={7} className="py-2">
                      <EmptyState icon={Shield}
                        title={statusFilter === 'open' ? 'No open findings' : 'No findings found'}
                        desc={clusters.length === 0
                          ? 'Connect Kubernetes clusters first, then trigger a scan.'
                          : statusFilter === 'open'
                            ? 'Your clusters have no open security findings. Run a fresh scan to verify.'
                            : 'No findings match the current filters.'} />
                    </td></tr>
                  ) : (
                    findings.map(f => (
                      <FindingRow
                        key={f.id}
                        finding={f}
                        expanded={expandedFinding === f.id}
                        onToggle={() => setExpandedFinding(expandedFinding === f.id ? null : f.id)}
                        onResolve={() => handleResolve(f.id)}
                        onSuppress={() => handleSuppress(f.id)}
                      />
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {findingsPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                <span className="text-xs text-muted-foreground">
                  {Math.min((findingsPage - 1) * PAGE_SIZE + 1, findingsTotal)}–{Math.min(findingsPage * PAGE_SIZE, findingsTotal)} of {findingsTotal}
                </span>
                <div className="flex items-center gap-1">
                  <button onClick={() => setFindingsPage(p => Math.max(1, p - 1))} disabled={findingsPage === 1}
                    className="px-2 py-1 text-xs rounded text-muted-foreground hover:text-foreground disabled:opacity-30">‹</button>
                  <span className="text-xs text-foreground px-2">{findingsPage} / {findingsPages}</span>
                  <button onClick={() => setFindingsPage(p => Math.min(findingsPages, p + 1))} disabled={findingsPage === findingsPages}
                    className="px-2 py-1 text-xs rounded text-muted-foreground hover:text-foreground disabled:opacity-30">›</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════ NODES TAB ════════════════ */}
      {viewTab === 'Nodes' && (
        !selectedCluster ? (
          <div className="card-base py-12 text-center">
            <p className="text-sm text-muted-foreground">Select a cluster above to view node details.</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {nodesLoading ? (
              [...Array(3)].map((_, i) => <Sk key={i} className="h-28 rounded-xl" />)
            ) : nodes.length === 0 ? (
              <div className="card-base">
                <EmptyState icon={HardDrive} title="No nodes found"
                  desc="No node data returned from cluster. Ensure the cluster is connected and the kubeconfig has node read permissions." />
              </div>
            ) : (
              nodes.map(n => {
                const cpuNum = parseFloat(n.cpu_usage ?? '0');
                const memNum = parseFloat(n.memory_usage ?? '0');
                return (
                  <div key={n.name} className="card-base p-4">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                        <HardDrive className="w-5 h-5 text-blue-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-sm font-semibold text-foreground truncate">{n.name}</h3>
                          <span className={clsx('text-[10px] font-medium', STATUS_COLOR[n.status] ?? 'text-muted-foreground')}>
                            ● {n.status}
                          </span>
                          {Array.isArray(n.roles) && n.roles.map(r => (
                            <span key={r} className="px-1.5 py-0.5 text-[9px] rounded-full bg-white/5 border border-border text-muted-foreground">{r}</span>
                          ))}
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                          <div>
                            <p className="text-[10px] text-muted-foreground mb-1">CPU</p>
                            <p className="text-xs font-medium text-foreground">{n.cpu_usage ?? '—'} / {n.cpu_capacity ?? '—'}</p>
                            {n.cpu_usage && (
                              <div className="mt-1 h-1 rounded-full bg-white/5 overflow-hidden">
                                <div className="h-full rounded-full transition-all"
                                  style={{ width: `${Math.min(100, cpuNum)}%`, background: cpuNum > 80 ? '#ef4444' : '#3b82f6' }} />
                              </div>
                            )}
                          </div>
                          <div>
                            <p className="text-[10px] text-muted-foreground mb-1">Memory</p>
                            <p className="text-xs font-medium text-foreground">{n.memory_usage ?? '—'} / {n.memory_capacity ?? '—'}</p>
                            {n.memory_usage && (
                              <div className="mt-1 h-1 rounded-full bg-white/5 overflow-hidden">
                                <div className="h-full rounded-full transition-all"
                                  style={{ width: `${Math.min(100, memNum)}%`, background: memNum > 80 ? '#ef4444' : '#8b5cf6' }} />
                              </div>
                            )}
                          </div>
                          <div>
                            <p className="text-[10px] text-muted-foreground mb-1">Pods</p>
                            <p className="text-xs font-medium text-foreground">{n.pod_count ?? '—'}</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-muted-foreground mb-1">Version</p>
                            <p className="text-xs font-mono text-foreground">{n.version ?? '—'}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )
      )}

      {/* ── Namespace Drawer ── */}
      {openNs && selectedCluster && (
        <NamespaceDrawer ns={openNs} clusterId={selectedCluster} findings={findings}
          onClose={() => setOpenNs(null)} />
      )}
    </div>
  );
}

// ─── Dashboard Header ─────────────────────────────────────────────────────────

function DashHeader({
  clusters, cluster, scanningCluster, onScan, onRefresh, showFilters, setShowFilters,
}: {
  clusters: Cluster[];
  cluster: Cluster | null;
  scanningCluster: string | null;
  onScan: (id: string) => void;
  onRefresh: () => void;
  showFilters: boolean;
  setShowFilters: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 className="text-lg font-bold text-foreground flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-500/15 flex items-center justify-center">
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          Kubernetes Operations
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          {clusters.length} cluster{clusters.length !== 1 ? 's' : ''} connected
          {cluster && <> · <span className="capitalize">{cluster.status}</span> · {cluster.provider}</>}
        </p>
      </div>
      <div className="flex items-center gap-2">
        {cluster && (
          <button onClick={() => onScan(cluster.id)}
            disabled={!!scanningCluster || cluster.status === 'disconnected'}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-40 font-medium">
            <Play className={clsx('w-3.5 h-3.5', scanningCluster === cluster.id && 'animate-spin')} />
            {scanningCluster === cluster.id ? 'Scanning…' : 'Security Scan'}
          </button>
        )}
        <button onClick={onRefresh}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>
    </div>
  );
}
