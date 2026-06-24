import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { clsx } from 'clsx';
import {
  ZoomIn, ZoomOut, Maximize2, RefreshCw, X,
  ExternalLink, Filter, Activity,
} from 'lucide-react';
import { useApi } from '@/hooks/use-api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface GraphNode {
  id: string;
  name: string;
  type: string;
  source: string;
  risk_level: string;
  environment: string;
  owner?: string | null;
  open_findings: number;
  is_critical: boolean;
  url?: string | null;
  // simulation state (mutated in place)
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number; // pinned x
  fy?: number; // pinned y
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const RISK_COLOR: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#3b82f6',
  none:     '#22c55e',
};

const RISK_GLOW: Record<string, string> = {
  critical: 'rgba(239,68,68,0.4)',
  high:     'rgba(249,115,22,0.4)',
  medium:   'rgba(234,179,8,0.3)',
  low:      'rgba(59,130,246,0.3)',
  none:     'rgba(34,197,94,0.3)',
};

const SOURCE_HUE: Record<string, string> = {
  github:     '#a855f7',
  gitlab:     '#e2684e',
  aws:        '#f97316',
  kubernetes: '#6366f1',
  docker:     '#38bdf8',
};

const TYPE_EMOJI: Record<string, string> = {
  github_repo:    '⌥',
  gitlab_repo:    '⌦',
  aws_ec2:        '☁',
  aws_s3:         '🪣',
  aws_iam_user:   '👤',
  aws_iam_role:   '🔑',
  aws_rds:        '🗄',
  docker_image:   '🐳',
  k8s_cluster:    '⚙',
  k8s_namespace:  '📁',
  k8s_pod:        '📦',
};

const REL_COLORS: Record<string, string> = {
  contains:   '#6366f1',
  runs_on:    '#22c55e',
  hosted_in:  '#f97316',
  depends_on: '#a855f7',
  scanned_by: '#3b82f6',
  belongs_to: '#ec4899',
};

// ─── Force simulation ─────────────────────────────────────────────────────────

const REPULSION    = 3500;
const SPRING_LEN   = 120;
const SPRING_K     = 0.04;
const GRAVITY      = 0.008;
const DAMPING      = 0.82;
const NODE_RADIUS  = 22;

function nodeRadius(node: GraphNode): number {
  if (node.is_critical)     return 30;
  if (node.open_findings > 5) return 27;
  return NODE_RADIUS;
}

function tick(
  nodes: GraphNode[],
  edges: GraphEdge[],
  nodeMap: Map<string, GraphNode>,
  cx: number,
  cy: number,
) {
  const n = nodes.length;

  // Repulsion — O(n²) but fine for ≤200 nodes
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const a = nodes[i], b = nodes[j];
      const dx = b.x - a.x || 0.01;
      const dy = b.y - a.y || 0.01;
      const dist2 = dx * dx + dy * dy;
      const dist  = Math.sqrt(dist2);
      const force = REPULSION / dist2;
      const fx = (force * dx) / dist;
      const fy = (force * dy) / dist;
      a.vx -= fx; a.vy -= fy;
      b.vx += fx; b.vy += fy;
    }
  }

  // Spring attraction along edges
  for (const edge of edges) {
    const a = nodeMap.get(edge.source);
    const b = nodeMap.get(edge.target);
    if (!a || !b) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const stretch = dist - SPRING_LEN;
    const fx = SPRING_K * stretch * (dx / dist);
    const fy = SPRING_K * stretch * (dy / dist);
    a.vx += fx; a.vy += fy;
    b.vx -= fx; b.vy -= fy;
  }

  // Gravity toward center
  for (const node of nodes) {
    node.vx += (cx - node.x) * GRAVITY;
    node.vy += (cy - node.y) * GRAVITY;
  }

  // Integrate + damp
  for (const node of nodes) {
    if (node.fx !== undefined) { node.x = node.fx; node.vx = 0; }
    else { node.vx *= DAMPING; node.x += node.vx; }
    if (node.fy !== undefined) { node.y = node.fy; node.vy = 0; }
    else { node.vy *= DAMPING; node.y += node.vy; }
  }
}

// ─── Legend entry ─────────────────────────────────────────────────────────────

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}

// ─── Node detail panel ────────────────────────────────────────────────────────

function NodePanel({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  const riskColor = RISK_COLOR[node.risk_level] ?? RISK_COLOR.none;
  return (
    <div className="absolute top-3 right-3 w-64 z-20 rounded-xl border border-border bg-[hsl(230_15%_10%)] shadow-2xl overflow-hidden">
      <div className="flex items-start gap-2.5 p-3 border-b border-border">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
          style={{ background: `${riskColor}22` }}>
          {TYPE_EMOJI[node.type] ?? '📄'}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-foreground truncate">{node.name}</p>
          <p className="text-[10px] text-muted-foreground capitalize">{node.type?.replace(/_/g, ' ')}</p>
        </div>
        <button onClick={onClose} className="p-0.5 text-muted-foreground hover:text-foreground">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="p-3 space-y-2">
        {[
          { label: 'Source',       value: node.source },
          { label: 'Environment',  value: node.environment },
          { label: 'Risk Level',   value: node.risk_level },
          { label: 'Owner',        value: node.owner ?? '—' },
          { label: 'Open Findings',value: node.open_findings },
        ].map(r => (
          <div key={r.label} className="flex justify-between items-center">
            <span className="text-[10px] text-muted-foreground">{r.label}</span>
            <span className={clsx(
              'text-[10px] font-medium',
              r.label === 'Risk Level' ? '' : 'text-foreground',
            )} style={r.label === 'Risk Level' ? { color: riskColor } : undefined}>
              {String(r.value)}
            </span>
          </div>
        ))}
      </div>

      {node.url && (
        <div className="px-3 pb-3">
          <a href={node.url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300">
            <ExternalLink className="w-3 h-3" /> Open in console
          </a>
        </div>
      )}
    </div>
  );
}

// ─── Graph filters ────────────────────────────────────────────────────────────

interface GraphFilters {
  source: string;
  risk_level: string;
  type: string;
  limit: number;
}

// ─── Main graph component ─────────────────────────────────────────────────────

export default function AssetGraph() {
  const svgRef   = useRef<SVGSVGElement>(null);
  const rafRef   = useRef<number>(0);
  const dragging = useRef<{ node: GraphNode; ox: number; oy: number } | null>(null);
  const panning  = useRef<{ startX: number; startY: number; startTx: number; startTy: number } | null>(null);

  const [filters, setFilters] = useState<GraphFilters>({ source: '', risk_level: '', type: '', limit: 150 });
  const [showFilters, setShowFilters] = useState(false);
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [tick2, setTick2] = useState(0); // render counter
  const [simNodes, setSimNodes] = useState<GraphNode[]>([]);
  const [simEdges, setSimEdges] = useState<GraphEdge[]>([]);
  const [stabilized, setStabilized] = useState(false);

  const qs = new URLSearchParams({ limit: String(filters.limit) });
  if (filters.source)     qs.set('source', filters.source);
  if (filters.risk_level) qs.set('risk_level', filters.risk_level);
  if (filters.type)       qs.set('type', filters.type);

  const { data: raw, loading, refetch } = useApi<any>(`/assets/graph?${qs}`);
  const graphData = raw?.data ?? raw;

  const nodeMap = useMemo(() => {
    const m = new Map<string, GraphNode>();
    simNodes.forEach(n => m.set(n.id, n));
    return m;
  }, [simNodes]);

  // Initialise simulation when data arrives
  useEffect(() => {
    if (!graphData?.nodes) return;
    const svg = svgRef.current;
    const W = svg?.clientWidth ?? 800;
    const H = svg?.clientHeight ?? 600;

    const nodes: GraphNode[] = graphData.nodes.map((n: any, i: number) => ({
      ...n,
      x: W / 2 + (Math.random() - 0.5) * 200,
      y: H / 2 + (Math.random() - 0.5) * 200,
      vx: 0,
      vy: 0,
    }));
    const edges: GraphEdge[] = graphData.edges ?? [];

    setSimNodes(nodes);
    setSimEdges(edges);
    setStabilized(false);
  }, [graphData]);

  // Simulation loop
  useEffect(() => {
    if (simNodes.length === 0) return;
    const svg = svgRef.current;
    const W = svg?.clientWidth ?? 800;
    const H = svg?.clientHeight ?? 600;
    const cx = W / 2, cy = H / 2;

    let frameCount = 0;
    const MAX_FRAMES = 300;

    const loop = () => {
      const map = new Map<string, GraphNode>();
      simNodes.forEach(n => map.set(n.id, n));
      tick(simNodes, simEdges, map, cx, cy);
      frameCount++;
      setTick2(t => t + 1);
      if (frameCount < MAX_FRAMES) {
        rafRef.current = requestAnimationFrame(loop);
      } else {
        setStabilized(true);
      }
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [simNodes, simEdges]);

  // Zoom
  const zoom = useCallback((delta: number) => {
    setTransform(t => ({
      ...t,
      scale: Math.min(3, Math.max(0.2, t.scale * (delta > 0 ? 1.15 : 0.87))),
    }));
  }, []);

  const resetView = useCallback(() => setTransform({ x: 0, y: 0, scale: 1 }), []);

  // Wheel zoom
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => { e.preventDefault(); zoom(-e.deltaY); };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
  }, [zoom]);

  // Pan + drag helpers
  const screenToSvg = useCallback((sx: number, sy: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: sx, y: sy };
    const rect = svg.getBoundingClientRect();
    return {
      x: (sx - rect.left - transform.x) / transform.scale,
      y: (sy - rect.top  - transform.y) / transform.scale,
    };
  }, [transform]);

  const onNodeMouseDown = useCallback((e: React.MouseEvent, node: GraphNode) => {
    e.stopPropagation();
    const pt = screenToSvg(e.clientX, e.clientY);
    dragging.current = { node, ox: pt.x - node.x, oy: pt.y - node.y };
    node.fx = node.x;
    node.fy = node.y;
  }, [screenToSvg]);

  const onSvgMouseDown = useCallback((e: React.MouseEvent) => {
    if (dragging.current) return;
    panning.current = {
      startX: e.clientX, startY: e.clientY,
      startTx: transform.x, startTy: transform.y,
    };
  }, [transform]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragging.current) {
      const pt = screenToSvg(e.clientX, e.clientY);
      dragging.current.node.fx = pt.x - dragging.current.ox;
      dragging.current.node.fy = pt.y - dragging.current.oy;
      // keep sim running while dragging
      setStabilized(false);
      setTick2(t => t + 1);
    } else if (panning.current) {
      const dx = e.clientX - panning.current.startX;
      const dy = e.clientY - panning.current.startY;
      setTransform(t => ({ ...t, x: panning.current!.startTx + dx, y: panning.current!.startTy + dy }));
    }
  }, [screenToSvg]);

  const onMouseUp = useCallback((e: React.MouseEvent) => {
    if (dragging.current) {
      const d = dragging.current;
      // Release pin unless user ctrl-clicked to keep it pinned
      if (!e.ctrlKey) {
        delete d.node.fx;
        delete d.node.fy;
      }
      dragging.current = null;
      setStabilized(false);
    }
    panning.current = null;
  }, []);

  const onNodeClick = useCallback((e: React.MouseEvent, node: GraphNode) => {
    e.stopPropagation();
    setSelected(s => s?.id === node.id ? null : node);
  }, []);

  const isEmpty = !loading && simNodes.length === 0;

  return (
    <div className="flex flex-col h-full" style={{ minHeight: '600px' }}>
      {/* ── Toolbar ── */}
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <div>
          <h1 className="text-lg font-bold text-foreground">Asset Relationship Graph</h1>
          <p className="text-xs text-muted-foreground">
            {simNodes.length} nodes · {simEdges.length} edges
            {!stabilized && simNodes.length > 0 && (
              <span className="ml-2 text-blue-400 flex items-center gap-1 inline-flex">
                <Activity className="w-3 h-3 animate-pulse" /> simulating…
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button onClick={() => setShowFilters(f => !f)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors',
              showFilters ? 'border-blue-500/40 text-blue-400 bg-blue-500/10' : 'border-border text-muted-foreground hover:text-foreground',
            )}>
            <Filter className="w-3.5 h-3.5" /> Filter
          </button>
          <button onClick={resetView}
            className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
            <Maximize2 className="w-4 h-4" />
          </button>
          <button onClick={() => zoom(1)}
            className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
            <ZoomIn className="w-4 h-4" />
          </button>
          <button onClick={() => zoom(-1)}
            className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
            <ZoomOut className="w-4 h-4" />
          </button>
          <button onClick={() => { refetch(); setSelected(null); }}
            className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* ── Filter panel ── */}
      {showFilters && (
        <div className="card-base p-3 mb-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Source', key: 'source', opts: ['', 'github', 'gitlab', 'aws', 'kubernetes', 'docker'] },
            { label: 'Risk',   key: 'risk_level', opts: ['', 'critical', 'high', 'medium', 'low', 'none'] },
            {
              label: 'Type', key: 'type',
              opts: ['', 'github_repo', 'gitlab_repo', 'aws_ec2', 'aws_s3', 'aws_iam_user', 'aws_iam_role', 'aws_rds', 'docker_image', 'k8s_cluster', 'k8s_namespace', 'k8s_pod'],
            },
            {
              label: 'Max Nodes', key: 'limit',
              opts: [50, 100, 150, 200, 300, 500] as any,
            },
          ].map(f => (
            <div key={f.key}>
              <label className="text-[10px] text-muted-foreground block mb-1">{f.label}</label>
              <select
                value={String((filters as any)[f.key])}
                onChange={e => setFilters(flt => ({ ...flt, [f.key]: f.key === 'limit' ? Number(e.target.value) : e.target.value }))}
                className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none"
              >
                {f.opts.map((o: any) => (
                  <option key={o} value={o}>{o === '' ? `All ${f.label}s` : String(o)}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      )}

      {/* ── Canvas ── */}
      <div className="relative flex-1 rounded-xl border border-border overflow-hidden bg-[hsl(230_15%_7%)]"
        style={{ minHeight: '520px' }}>

        {/* Loading */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <div className="flex flex-col items-center gap-3">
              <div className="w-10 h-10 rounded-full border-2 border-blue-500/40 border-t-blue-500 animate-spin" />
              <p className="text-xs text-muted-foreground">Loading graph…</p>
            </div>
          </div>
        )}

        {/* Empty state */}
        {isEmpty && !loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="text-4xl mb-3">🕸️</div>
              <p className="text-sm font-medium text-foreground mb-1">No assets to graph</p>
              <p className="text-xs text-muted-foreground">Connect integrations and sync assets first.</p>
            </div>
          </div>
        )}

        {/* Hint */}
        {!loading && simNodes.length > 0 && (
          <div className="absolute bottom-3 left-3 z-10 text-[10px] text-muted-foreground pointer-events-none select-none">
            Scroll to zoom · drag to pan · drag node to move · click node for details
          </div>
        )}

        {/* SVG */}
        <svg
          ref={svgRef}
          className="w-full h-full cursor-grab active:cursor-grabbing select-none"
          style={{ minHeight: '520px' }}
          onMouseDown={onSvgMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
          onClick={() => setSelected(null)}
        >
          <defs>
            {/* Arrow marker per relationship type */}
            {Object.entries(REL_COLORS).map(([type, color]) => (
              <marker key={type} id={`arrow-${type}`} viewBox="0 0 10 10"
                refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill={color} opacity="0.7" />
              </marker>
            ))}
            <marker id="arrow-default" viewBox="0 0 10 10"
              refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#6b7280" opacity="0.7" />
            </marker>
            {/* Radial glow filters */}
            {Object.entries(RISK_COLOR).map(([risk, color]) => (
              <filter key={risk} id={`glow-${risk}`} x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="4" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            ))}
          </defs>

          <g transform={`translate(${transform.x},${transform.y}) scale(${transform.scale})`}>
            {/* Edges */}
            {simEdges.map(edge => {
              const src = nodeMap.get(edge.source);
              const tgt = nodeMap.get(edge.target);
              if (!src || !tgt) return null;
              const color = REL_COLORS[edge.type] ?? '#6b7280';
              const markerId = REL_COLORS[edge.type] ? `arrow-${edge.type}` : 'arrow-default';

              // Shorten line so arrow doesn't overlap node circle
              const dx = tgt.x - src.x;
              const dy = tgt.y - src.y;
              const dist = Math.sqrt(dx * dx + dy * dy) || 1;
              const tR = nodeRadius(tgt) + 4;
              const ex = tgt.x - (dx / dist) * tR;
              const ey = tgt.y - (dy / dist) * tR;

              // Mid-point for label
              const mx = (src.x + ex) / 2;
              const my = (src.y + ey) / 2;

              return (
                <g key={edge.id}>
                  <line
                    x1={src.x} y1={src.y} x2={ex} y2={ey}
                    stroke={color}
                    strokeWidth={1.5}
                    strokeOpacity={0.5}
                    markerEnd={`url(#${markerId})`}
                  />
                  {/* Relationship label — only at sufficient zoom */}
                  {transform.scale > 0.6 && dist > 60 && (
                    <text x={mx} y={my - 5} textAnchor="middle"
                      fontSize={9} fill={color} fillOpacity={0.8} pointerEvents="none">
                      {edge.type}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Nodes */}
            {simNodes.map(node => {
              const r     = nodeRadius(node);
              const color = RISK_COLOR[node.risk_level] ?? RISK_COLOR.none;
              const srcColor = SOURCE_HUE[node.source] ?? '#6b7280';
              const isSelected = selected?.id === node.id;
              const emoji = TYPE_EMOJI[node.type] ?? '📄';

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x},${node.y})`}
                  style={{ cursor: 'pointer' }}
                  onMouseDown={e => onNodeMouseDown(e, node)}
                  onClick={e => onNodeClick(e, node)}
                >
                  {/* Selection ring */}
                  {isSelected && (
                    <circle r={r + 6} fill="none" stroke={color} strokeWidth={2} strokeDasharray="4 2" strokeOpacity={0.9} />
                  )}

                  {/* Critical pulse ring */}
                  {node.is_critical && (
                    <circle r={r + 4} fill="none" stroke={color} strokeWidth={1} strokeOpacity={0.4}>
                      <animate attributeName="r" values={`${r + 2};${r + 9};${r + 2}`} dur="2.5s" repeatCount="indefinite" />
                      <animate attributeName="stroke-opacity" values="0.5;0;0.5" dur="2.5s" repeatCount="indefinite" />
                    </circle>
                  )}

                  {/* Glow */}
                  <circle
                    r={r}
                    fill={`${color}15`}
                    filter={`url(#glow-${node.risk_level})`}
                    style={{ pointerEvents: 'none' }}
                  />

                  {/* Main circle — source-tinted fill */}
                  <circle
                    r={r}
                    fill={`${srcColor}22`}
                    stroke={color}
                    strokeWidth={isSelected ? 2.5 : 1.5}
                    strokeOpacity={isSelected ? 1 : 0.8}
                  />

                  {/* Type emoji icon */}
                  <text
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={r * 0.8}
                    style={{ pointerEvents: 'none', userSelect: 'none' }}
                  >
                    {emoji}
                  </text>

                  {/* Open findings badge */}
                  {node.open_findings > 0 && (
                    <g transform={`translate(${r - 6}, ${-r + 6})`}>
                      <circle r={8} fill="#ef4444" />
                      <text textAnchor="middle" dominantBaseline="central"
                        fontSize={7} fill="white" fontWeight="bold">
                        {node.open_findings > 99 ? '99+' : node.open_findings}
                      </text>
                    </g>
                  )}

                  {/* Name label */}
                  {transform.scale > 0.5 && (
                    <text
                      y={r + 12}
                      textAnchor="middle"
                      fontSize={10}
                      fill="hsl(230 15% 70%)"
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {node.name.length > 18 ? node.name.slice(0, 16) + '…' : node.name}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* Node detail panel */}
        {selected && <NodePanel node={selected} onClose={() => setSelected(null)} />}

        {/* Legend */}
        {simNodes.length > 0 && (
          <div className="absolute top-3 left-3 z-10 rounded-lg border border-border bg-[hsl(230_15%_10%)/90] backdrop-blur-sm p-2.5 space-y-2.5">
            <div>
              <p className="text-[10px] font-medium text-muted-foreground mb-1.5">Risk Level</p>
              <div className="space-y-1">
                {Object.entries(RISK_COLOR).map(([k, c]) => (
                  <LegendDot key={k} color={c} label={k.charAt(0).toUpperCase() + k.slice(1)} />
                ))}
              </div>
            </div>
            <div className="border-t border-border/50 pt-2">
              <p className="text-[10px] font-medium text-muted-foreground mb-1.5">Relationships</p>
              <div className="space-y-1">
                {Object.entries(REL_COLORS).map(([k, c]) => (
                  <LegendDot key={k} color={c} label={k} />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
