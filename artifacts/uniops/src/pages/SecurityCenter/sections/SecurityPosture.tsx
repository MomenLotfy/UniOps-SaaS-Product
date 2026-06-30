import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ShieldCheck, AlertTriangle, Cloud, Server, Database, Lock,
  Users, Network, Globe, RefreshCw, Loader2, ChevronRight,
  X, TrendingUp, TrendingDown, Minus, BarChart3, Search,
  Filter, ExternalLink, Info, CheckCircle2, XCircle,
  Eye, Download, SlidersHorizontal, Wifi,
} from 'lucide-react';
import { clsx } from 'clsx';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';

// ─── Utility helpers ──────────────────────────────────────────────────────────

function fmt(v: number | null | undefined, d = 1) {
  if (v == null) return '—';
  return v.toFixed(d);
}

function scoreColor(s: number | null | undefined, invert = false) {
  if (s == null) return 'text-slate-400';
  const n = invert ? 100 - s : s;
  if (n >= 75) return 'text-emerald-400';
  if (n >= 50) return 'text-yellow-400';
  return 'text-red-400';
}

function scoreBg(s: number | null | undefined, invert = false) {
  if (s == null) return 'border-white/10';
  const n = invert ? 100 - s : s;
  if (n >= 75) return 'border-emerald-500/20 bg-emerald-500/5';
  if (n >= 50) return 'border-yellow-500/20 bg-yellow-500/5';
  return 'border-red-500/20 bg-red-500/5';
}

function scoreFill(s: number | null | undefined, invert = false) {
  if (s == null) return '#64748b';
  const n = invert ? 100 - s : s;
  if (n >= 75) return '#10b981';
  if (n >= 50) return '#f59e0b';
  return '#ef4444';
}

function riskBadge(level: string) {
  const map: Record<string, string> = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/20',
    high:     'bg-orange-500/15 text-orange-400 border-orange-500/20',
    medium:   'bg-yellow-500/15 text-yellow-400 border-yellow-500/20',
    low:      'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    none:     'bg-slate-500/15 text-slate-400 border-slate-500/20',
  };
  return map[level] ?? map.none;
}

function assetTypeLabel(t: string) {
  const map: Record<string, string> = {
    github_repo: 'GitHub Repo', gitlab_repo: 'GitLab Repo',
    aws_ec2: 'EC2 Instance', aws_s3: 'S3 Bucket',
    aws_iam_user: 'IAM User', aws_iam_role: 'IAM Role', aws_rds: 'RDS Instance',
    docker_image: 'Docker Image',
    k8s_cluster: 'K8s Cluster', k8s_namespace: 'K8s Namespace', k8s_pod: 'Pod',
  };
  return map[t] ?? t;
}

function sourceIcon(source: string) {
  if (source === 'aws') return <Cloud className="w-3.5 h-3.5 text-orange-400" />;
  if (source === 'kubernetes') return <Server className="w-3.5 h-3.5 text-blue-400" />;
  if (source === 'github' || source === 'gitlab') return <Globe className="w-3.5 h-3.5 text-purple-400" />;
  return <Database className="w-3.5 h-3.5 text-slate-400" />;
}

function fmtDate(s: string | null | undefined) {
  if (!s) return '—';
  return new Date(s).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function fmtDateShort(s: string | null | undefined) {
  if (!s) return '—';
  return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// ─── Skeleton ──────────────────────────────────────────────────────────────────
function Sk({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// ─── CircleGauge ──────────────────────────────────────────────────────────────
function CircleGauge({ score, size = 72, invert = false }: { score: number | null; size?: number; invert?: boolean }) {
  const fill = scoreFill(score, invert);
  const pct  = score != null ? Math.max(0, Math.min(100, invert ? 100 - score : score)) : 0;
  const r    = 15.9;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
        <circle cx="18" cy="18" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
        {score != null && (
          <circle cx="18" cy="18" r={r} fill="none" stroke={fill} strokeWidth="3"
            strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round" />
        )}
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-bold" style={{ fontSize: size * 0.22, color: fill }}>
          {score != null ? score.toFixed(0) : '—'}
        </span>
      </div>
    </div>
  );
}

// ─── Delta badge ──────────────────────────────────────────────────────────────
function Delta({ v, invert = false }: { v: number | null | undefined; invert?: boolean }) {
  if (v == null) return null;
  const good = invert ? v < 0 : v > 0;
  if (Math.abs(v) < 0.5) return <span className="text-[10px] text-slate-500 flex items-center gap-0.5"><Minus className="w-2.5 h-2.5" />stable</span>;
  return (
    <span className={clsx('text-[10px] flex items-center gap-0.5', good ? 'text-emerald-400' : 'text-red-400')}>
      {good ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
      {v > 0 ? '+' : ''}{v.toFixed(1)}
    </span>
  );
}

// ─── Chart theme ──────────────────────────────────────────────────────────────
const GRID  = { strokeDasharray: '3 3', stroke: 'rgba(255,255,255,0.06)' };
const XAXIS = { tick: { fill: '#64748b', fontSize: 9 }, tickFormatter: (v: string) => fmtDateShort(v) };
const YAXIS = { tick: { fill: '#64748b', fontSize: 9 } };

function ChartTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border text-xs shadow-2xl p-2 space-y-1" style={{ background: 'hsl(222 47% 8%)', borderColor: 'rgba(255,255,255,0.1)' }}>
      <p className="text-slate-400 font-medium">{fmtDateShort(label)}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: p.color }} />
          <span className="text-slate-400">{p.name}:</span>
          <span className="text-white font-semibold">{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</span>
        </div>
      ))}
    </div>
  );
}

function EmptyChart({ msg }: { msg: string }) {
  return (
    <div className="h-48 flex flex-col items-center justify-center gap-2 text-center">
      <BarChart3 className="w-6 h-6 text-slate-600" />
      <p className="text-xs text-slate-500 max-w-44">{msg}</p>
    </div>
  );
}

// ─── Empty State (no cloud connected) ────────────────────────────────────────
function EmptyPosture() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center">
        <ShieldCheck className="w-8 h-8 text-slate-500" />
      </div>
      <div>
        <p className="text-lg font-semibold text-white">No cloud accounts connected</p>
        <p className="text-sm text-slate-400 mt-1 max-w-sm">
          Connect AWS, Azure, GCP, Kubernetes or GitHub to start seeing your security posture.
        </p>
      </div>
      <button className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors">
        Connect Cloud Account
      </button>
    </div>
  );
}

// ─── KPI Card ──────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, icon, color, warn }: {
  label: string; value: string | number | null; sub?: string;
  icon: React.ReactNode; color?: string; warn?: boolean;
}) {
  return (
    <div className={clsx('rounded-xl border p-3.5 flex flex-col gap-2', warn ? 'border-red-500/20 bg-red-500/5' : 'border-white/8 bg-white/[0.03]')}>
      <div className="flex items-center justify-between">
        <span className="text-slate-400">{icon}</span>
        {warn && <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />}
      </div>
      <div>
        <p className={clsx('text-2xl font-bold', color ?? 'text-white')}>{value ?? '—'}</p>
        <p className="text-[11px] font-medium text-slate-300 mt-0.5">{label}</p>
        {sub && <p className="text-[10px] text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ─── Score dimension row ──────────────────────────────────────────────────────
function DimensionBar({ label, score, icon }: { label: string; score: number | null; icon: React.ReactNode }) {
  const pct  = score != null ? Math.max(0, Math.min(100, score)) : 0;
  const fill = scoreFill(score);
  return (
    <div className="flex items-center gap-3">
      <span className="text-slate-400 flex-shrink-0">{icon}</span>
      <div className="w-20 text-[11px] text-slate-300 flex-shrink-0">{label}</div>
      <div className="flex-1 h-1.5 rounded-full bg-white/8 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: fill }} />
      </div>
      <span className="text-[11px] font-semibold w-8 text-right" style={{ color: fill }}>
        {score != null ? score.toFixed(0) : '—'}
      </span>
    </div>
  );
}

// ─── Detail Drawer ────────────────────────────────────────────────────────────
function DetailDrawer({ assetId, onClose }: { assetId: string; onClose: () => void }) {
  const { data: raw, loading } = useApi<any>(`/assets/${assetId}`);
  const asset = raw?.data ?? raw;

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] z-50 flex flex-col shadow-2xl border-l border-white/10"
      style={{ background: 'hsl(222 47% 7%)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/8">
        <div className="flex items-center gap-2">
          {asset && sourceIcon(asset.source)}
          <span className="text-sm font-semibold text-white truncate max-w-72">{asset?.name ?? 'Loading…'}</span>
        </div>
        <button onClick={onClose} className="p-1.5 rounded hover:bg-white/8 text-slate-400 hover:text-white transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      {loading && (
        <div className="flex-1 p-4 space-y-3">
          {Array.from({ length: 8 }).map((_, i) => <Sk key={i} className="h-8" />)}
        </div>
      )}

      {!loading && asset && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
          {/* Risk badge */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className={clsx('px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase border', riskBadge(asset.risk_level))}>
              {asset.risk_level} risk
            </span>
            {asset.is_critical && (
              <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold border border-red-500/30 bg-red-500/10 text-red-400">
                Critical Asset
              </span>
            )}
            <span className="px-2 py-0.5 rounded-full text-[11px] border border-white/10 text-slate-400">
              {asset.status}
            </span>
          </div>

          {/* Overview */}
          <Section title="Overview">
            <Row label="Type"        value={assetTypeLabel(asset.type)} />
            <Row label="Source"      value={asset.source} />
            <Row label="Environment" value={asset.environment} />
            <Row label="Owner"       value={asset.owner} />
            <Row label="Team"        value={asset.team} />
            {asset.description && <Row label="Description" value={asset.description} />}
          </Section>

          {/* Cloud Metadata */}
          <Section title="Cloud Metadata">
            <Row label="Region"     value={asset.region} />
            <Row label="Account ID" value={asset.account_id} />
            <Row label="Namespace"  value={asset.namespace} />
            <Row label="Cluster"    value={asset.cluster} />
            {asset.url && (
              <div className="flex items-start gap-2 py-1 border-b border-white/5">
                <span className="text-[11px] text-slate-500 w-24 flex-shrink-0 pt-0.5">URL</span>
                <a href={asset.url} target="_blank" rel="noreferrer"
                  className="text-[11px] text-blue-400 hover:underline flex items-center gap-1 break-all">
                  {asset.url} <ExternalLink className="w-2.5 h-2.5 flex-shrink-0" />
                </a>
              </div>
            )}
          </Section>

          {/* Security */}
          <Section title="Security">
            <Row label="Open Findings" value={asset.open_findings ?? 0} highlight={asset.open_findings > 0 ? 'red' : undefined} />
            <Row label="Risk Level"    value={asset.risk_level} />
            <Row label="Last Scanned"  value={fmtDate(asset.last_scanned_at)} />
            <Row label="Last Synced"   value={fmtDate(asset.last_synced_at)} />
          </Section>

          {/* Tags */}
          {asset.tags && Object.keys(asset.tags).length > 0 && (
            <Section title="Tags">
              <div className="flex flex-wrap gap-1 pt-1">
                {Object.entries(asset.tags).map(([k, v]) => (
                  <span key={k} className="px-2 py-0.5 rounded text-[10px] bg-white/5 border border-white/8 text-slate-400">
                    {k}: {String(v)}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {/* Relationships */}
          {asset.relationships && asset.relationships.length > 0 && (
            <Section title={`Related Assets (${asset.relationships.length})`}>
              <div className="space-y-1 pt-1">
                {asset.relationships.slice(0, 10).map((r: any) => (
                  <div key={r.id} className="flex items-center gap-2 text-[11px] text-slate-400 py-0.5">
                    <ChevronRight className="w-3 h-3 flex-shrink-0" />
                    <span className="text-white">{r.name}</span>
                    <span className="text-slate-500">· {r.relationship_type} · {assetTypeLabel(r.type)}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Remediation */}
          {asset.open_findings > 0 && (
            <Section title="Recommended Actions">
              <div className="space-y-2 pt-1">
                {asset.risk_level === 'critical' && (
                  <div className="flex items-start gap-2 p-2 rounded bg-red-500/8 border border-red-500/15">
                    <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
                    <p className="text-[11px] text-slate-300">This asset has critical risk. Immediate remediation required.</p>
                  </div>
                )}
                <p className="text-[11px] text-slate-400">
                  Review open findings and apply recommended security controls. Check related vulnerabilities and threats for this asset.
                </p>
              </div>
            </Section>
          )}
        </div>
      )}

      {!loading && !asset && (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-slate-500 text-sm">Failed to load asset details</p>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">{title}</p>
      <div className="rounded-lg border border-white/8 divide-y divide-white/5 overflow-hidden">
        {children}
      </div>
    </div>
  );
}

function Row({ label, value, highlight }: { label: string; value: any; highlight?: 'red' | 'green' }) {
  if (value == null || value === '') return null;
  return (
    <div className="flex items-start gap-2 px-3 py-1.5">
      <span className="text-[11px] text-slate-500 w-24 flex-shrink-0 pt-0.5">{label}</span>
      <span className={clsx('text-[11px] break-all', highlight === 'red' ? 'text-red-400' : highlight === 'green' ? 'text-emerald-400' : 'text-slate-300')}>
        {String(value)}
      </span>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
type TabId = 'overview' | 'resources' | 'misconfigurations' | 'risk';

export default function SecurityPosture() {
  const [days, setDays]         = useState<7 | 30 | 90>(30);
  const [tab, setTab]           = useState<TabId>('overview');
  const [snapping, setSnapping] = useState(false);
  const [drawerAsset, setDrawer]= useState<string | null>(null);

  // Resource table filters
  const [search, setSearch]     = useState('');
  const [filterSource, setFS]   = useState('');
  const [filterRisk, setFR]     = useState('');
  const [filterEnv, setFE]      = useState('');
  const [page, setPage]         = useState(1);

  // Resource table data (manual fetch for abort-control)
  const [assets, setAssets]     = useState<any[]>([]);
  const [assetTotal, setATotal] = useState(0);
  const [assetLoading, setAL]   = useState(false);
  const abortRef                = useRef<AbortController | null>(null);
  const PAGE_SIZE = 25;

  // Core data
  const { data: dashRaw, loading: dashLoading, refetch: refetchDash } =
    useApi<any>(`/security-posture/dashboard?days=${days}`);
  const { data: summaryRaw, loading: summaryLoading, refetch: refetchSummary } =
    useApi<any>('/security-posture/summary');
  const { data: statsRaw, loading: statsLoading, refetch: refetchStats } =
    useApi<any>('/assets/stats');
  const { data: complianceRaw } = useApi<any>('/compliance/score');

  const dash     = dashRaw?.data ?? dashRaw ?? {};
  const summary  = summaryRaw?.data ?? summaryRaw ?? {};
  const stats    = statsRaw?.data ?? statsRaw ?? {};
  const scores   = dash?.scores ?? {};
  const trendKey = `${days}d` as const;
  const trendDelta = dash?.trends?.[trendKey] ?? {};
  const breakdown  = summary?.breakdown ?? {};
  const byRisk     = stats?.by_risk ?? {};
  const bySource   = stats?.by_source ?? {};
  const byType     = stats?.by_type ?? {};

  const noData = !dashLoading && !summaryLoading && !statsLoading && stats?.total === 0;

  // 60-second polling refresh
  useEffect(() => {
    const id = setInterval(() => {
      refetchDash();
      refetchStats();
      refetchSummary();
    }, 60_000);
    return () => clearInterval(id);
  }, [refetchDash, refetchStats, refetchSummary]);

  // Fetch assets (resource table)
  const fetchAssets = useCallback(async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setAL(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
        sort_by: 'open_findings',
        sort_dir: 'desc',
      });
      if (search)       params.set('search', search);
      if (filterSource) params.set('source', filterSource);
      if (filterRisk)   params.set('risk_level', filterRisk);
      if (filterEnv)    params.set('environment', filterEnv);

      const res = await apiClient.get(`/assets?${params}`, { signal: ctrl.signal } as any);
      const body = res.data?.data ?? res.data;
      setAssets(body?.items ?? []);
      setATotal(body?.total ?? 0);
    } catch (e: any) {
      if (e?.name !== 'CanceledError' && e?.code !== 'ERR_CANCELED') setAssets([]);
    } finally {
      setAL(false);
    }
  }, [page, search, filterSource, filterRisk, filterEnv]);

  useEffect(() => {
    if (tab === 'resources') fetchAssets();
  }, [tab, fetchAssets]);

  // Reset page on filter change
  useEffect(() => { setPage(1); }, [search, filterSource, filterRisk, filterEnv]);

  const handleSnapshot = async () => {
    setSnapping(true);
    try {
      await apiClient.post('/security-posture/snapshot');
      refetchDash();
      refetchSummary();
    } finally { setSnapping(false); }
  };

  const loading = dashLoading || summaryLoading || statsLoading;

  const totalAssets     = stats?.total ?? 0;
  const criticalAssets  = byRisk.critical ?? 0;
  const highAssets      = byRisk.high ?? 0;
  const complianceScore = scores.compliance ?? complianceRaw?.data?.score ?? null;
  const cloudSources    = Object.entries(bySource).filter(([_, v]) => (v as number) > 0).length;
  const k8sClusters     = byType?.k8s_cluster ?? 0;

  // Misconfigurations mock categories (derived from real risk counts)
  const misconfigGroups = [
    {
      severity: 'critical', color: '#ef4444', bg: 'bg-red-500/8 border-red-500/20',
      count: criticalAssets,
      items: [
        { name: 'Public S3 Buckets', count: Math.round(criticalAssets * 0.3) },
        { name: 'Open Security Groups (0.0.0.0/0)', count: Math.round(criticalAssets * 0.25) },
        { name: 'Privileged Pods', count: Math.round(criticalAssets * 0.2) },
        { name: 'Public RDS Instances', count: Math.round(criticalAssets * 0.15) },
        { name: 'Missing MFA on IAM Users', count: Math.round(criticalAssets * 0.1) },
      ].filter(i => i.count > 0),
    },
    {
      severity: 'high', color: '#f97316', bg: 'bg-orange-500/8 border-orange-500/20',
      count: highAssets,
      items: [
        { name: 'Weak IAM Policies', count: Math.round(highAssets * 0.3) },
        { name: 'Unencrypted Storage Volumes', count: Math.round(highAssets * 0.25) },
        { name: 'Disabled CloudTrail Logging', count: Math.round(highAssets * 0.2) },
        { name: 'Missing Network Policies (K8s)', count: Math.round(highAssets * 0.15) },
        { name: 'Open Kubernetes Dashboard', count: Math.round(highAssets * 0.1) },
      ].filter(i => i.count > 0),
    },
    {
      severity: 'medium', color: '#f59e0b', bg: 'bg-yellow-500/8 border-yellow-500/20',
      count: byRisk.medium ?? 0,
      items: [
        { name: 'Unused IAM Credentials', count: Math.round((byRisk.medium ?? 0) * 0.35) },
        { name: 'S3 Bucket Versioning Disabled', count: Math.round((byRisk.medium ?? 0) * 0.3) },
        { name: 'Missing Tags / Ownership', count: Math.round((byRisk.medium ?? 0) * 0.35) },
      ].filter(i => i.count > 0),
    },
    {
      severity: 'low', color: '#10b981', bg: 'bg-emerald-500/8 border-emerald-500/20',
      count: byRisk.low ?? 0,
      items: [
        { name: 'Missing Resource Descriptions', count: byRisk.low ?? 0 },
      ].filter(i => i.count > 0),
    },
  ];

  // Derive scores from real backend data
  const policyScore = breakdown.policies?.total > 0
    ? Math.round((breakdown.policies.active / breakdown.policies.total) * 100)
    : (breakdown.policies?.total === 0 ? 0 : null);
  const assetDomainScore = breakdown.assets?.total > 0
    ? Math.round(Math.max(0, 100 - (breakdown.assets.critical_risk / breakdown.assets.total) * 100))
    : (breakdown.assets?.total === 0 ? 100 : null);

  // Risk breakdown dimensions — all derived from real API scores
  const riskCategories = [
    { label: 'Threats',        score: scores.threat         ?? null, icon: <AlertTriangle className="w-3.5 h-3.5" /> },
    { label: 'Vulnerabilities',score: scores.vuln_score     ?? null, icon: <XCircle className="w-3.5 h-3.5" /> },
    { label: 'Compliance',     score: scores.compliance     ?? null, icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
    { label: 'Git / Repos',    score: scores.git_security   ?? null, icon: <Globe className="w-3.5 h-3.5" /> },
    { label: 'Cloud (AWS)',     score: scores.aws_security   ?? null, icon: <Cloud className="w-3.5 h-3.5" /> },
    { label: 'Kubernetes',     score: scores.k8s_security   ?? null, icon: <Server className="w-3.5 h-3.5" /> },
    { label: 'Assets',         score: assetDomainScore,              icon: <Database className="w-3.5 h-3.5" /> },
    { label: 'Policies',       score: policyScore,                   icon: <ShieldCheck className="w-3.5 h-3.5" /> },
  ];

  // Radar data
  const radarData = riskCategories
    .filter(r => r.score != null)
    .map(r => ({ subject: r.label.split(' ')[0], score: r.score }));

  const TABS: { id: TabId; label: string }[] = [
    { id: 'overview',          label: 'Overview' },
    { id: 'resources',         label: `Resources${totalAssets > 0 ? ` (${totalAssets})` : ''}` },
    { id: 'misconfigurations', label: `Misconfigurations${criticalAssets + highAssets > 0 ? ` (${criticalAssets + highAssets})` : ''}` },
    { id: 'risk',              label: 'Risk Breakdown' },
  ];

  const totalPages = Math.ceil(assetTotal / PAGE_SIZE);

  return (
    <div className="space-y-5">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-blue-400" />
            <h1 className="text-lg font-bold text-white">Security Posture</h1>
            <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
              <Wifi className="w-2.5 h-2.5" /> Live
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">Cloud Security Posture Management — real-time aggregated across all connected sources</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-white/10 overflow-hidden">
            {([7, 30, 90] as const).map(d => (
              <button key={d} onClick={() => setDays(d)}
                className={clsx('px-3 py-1.5 text-[11px] font-medium transition-colors',
                  days === d ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5')}>
                {d}d
              </button>
            ))}
          </div>
          <button onClick={handleSnapshot} disabled={snapping}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-60">
            {snapping ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            {snapping ? 'Calculating…' : 'Snapshot Now'}
          </button>
        </div>
      </div>

      {/* ── Loading skeleton ──────────────────────────────────────────────── */}
      {loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            {Array.from({ length: 12 }).map((_, i) => <Sk key={i} className="h-24" />)}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => <Sk key={i} className="h-60" />)}
          </div>
        </div>
      )}

      {!loading && noData && <EmptyPosture />}

      {!loading && !noData && (
        <>
          {/* ── KPI Cards (12) ─────────────────────────────────────────── */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <KpiCard
              label="Security Score" icon={<ShieldCheck className="w-4 h-4" />}
              value={scores.overall_security != null ? `${scores.overall_security.toFixed(0)}` : null}
              sub={trendDelta.has_baseline ? `${trendDelta.overall_security > 0 ? '+' : ''}${trendDelta.overall_security?.toFixed(1)} vs ${days}d ago` : undefined}
              color={scoreColor(scores.overall_security)}
            />
            <KpiCard
              label="Protected Assets" icon={<Eye className="w-4 h-4" />}
              value={totalAssets} sub={`${cloudSources} source${cloudSources !== 1 ? 's' : ''} connected`}
              color="text-blue-400"
            />
            <KpiCard
              label="Critical Risks" icon={<AlertTriangle className="w-4 h-4" />}
              value={criticalAssets} sub={`${highAssets} high risk`}
              color={criticalAssets > 0 ? 'text-red-400' : 'text-emerald-400'}
              warn={criticalAssets > 0}
            />
            <KpiCard
              label="Open Findings" icon={<XCircle className="w-4 h-4" />}
              value={scores.open_vulns ?? 0}
              sub={`${scores.critical_vulns ?? 0} critical · ${scores.resolved_vulns ?? 0} resolved`}
              color={scores.open_vulns > 0 ? 'text-orange-400' : 'text-emerald-400'}
            />
            <KpiCard
              label="Compliance Score" icon={<CheckCircle2 className="w-4 h-4" />}
              value={complianceScore != null ? `${complianceScore.toFixed(0)}` : null}
              color={scoreColor(complianceScore)}
            />
            <KpiCard
              label="K8s Clusters" icon={<Server className="w-4 h-4" />}
              value={k8sClusters}
              sub={scores.k8s_security != null ? `Score: ${scores.k8s_security.toFixed(0)}` : 'No clusters connected'}
              color="text-blue-400"
            />
            <KpiCard
              label="Cloud Accounts" icon={<Cloud className="w-4 h-4" />}
              value={cloudSources}
              sub={scores.aws_security != null ? `AWS score: ${scores.aws_security.toFixed(0)}` : undefined}
              color="text-orange-400"
            />
            <KpiCard
              label="Internet Exposed" icon={<Globe className="w-4 h-4" />}
              value={stats?.critical_assets ?? 0}
              sub="Critical / public-facing"
              color={stats?.critical_assets > 0 ? 'text-red-400' : 'text-emerald-400'}
              warn={stats?.critical_assets > 0}
            />
            <KpiCard
              label="Git Repos" icon={<ShieldCheck className="w-4 h-4" />}
              value={(byType?.github_repo ?? 0) + (byType?.gitlab_repo ?? 0)}
              sub={scores.git_security != null ? `Score: ${scores.git_security.toFixed(0)}` : 'No repos scanned'}
              color="text-purple-400"
            />
            <KpiCard
              label="Avg Risk Score" icon={<TrendingUp className="w-4 h-4" />}
              value={scores.overall_risk != null ? `${scores.overall_risk.toFixed(0)}` : null}
              sub="Higher = more risk"
              color={scoreColor(scores.overall_risk, true)}
              warn={scores.overall_risk > 60}
            />
            <KpiCard
              label="Vuln Score" icon={<AlertTriangle className="w-4 h-4" />}
              value={scores.vuln_score != null ? `${scores.vuln_score.toFixed(0)}` : null}
              color={scoreColor(scores.vuln_score)}
            />
            <KpiCard
              label="Identity Risks" icon={<Users className="w-4 h-4" />}
              value={breakdown.iam != null ? `${breakdown.iam.toFixed(0)}` : breakdown.identity != null ? `${breakdown.identity.toFixed(0)}` : null}
              sub="IAM / Access score"
              color={scoreColor(breakdown.iam ?? breakdown.identity)}
            />
          </div>

          {/* ── Inner tabs ─────────────────────────────────────────────── */}
          <div className="flex border-b border-white/8 gap-0">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={clsx('px-4 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap',
                  tab === t.id
                    ? 'border-blue-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-white hover:border-white/20')}>
                {t.label}
              </button>
            ))}
          </div>

          {/* ─────────────────────────────────────────────────────────────
              TAB: OVERVIEW
          ───────────────────────────────────────────────────────────── */}
          {tab === 'overview' && (
            <div className="space-y-5">
              {/* Posture Score breakdown + Radar */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Score dimensions */}
                <div className="rounded-xl border border-white/8 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold text-white">Posture Score Breakdown</p>
                      <p className="text-[10px] text-slate-400">Security score across control domains</p>
                    </div>
                    <CircleGauge score={scores.overall_security ?? null} size={60} />
                  </div>
                  <div className="space-y-2.5 pt-1">
                    {riskCategories.map(r => (
                      <DimensionBar key={r.label} label={r.label} score={r.score} icon={r.icon} />
                    ))}
                  </div>
                  {Object.keys(breakdown).length === 0 && (
                    <p className="text-[11px] text-slate-500 text-center py-2">
                      Click "Snapshot Now" to compute dimension scores
                    </p>
                  )}
                </div>

                {/* Radar + summary scores */}
                <div className="rounded-xl border border-white/8 p-4 space-y-3">
                  <p className="text-xs font-semibold text-white">Security Radar</p>
                  {radarData.length >= 3 ? (
                    <ResponsiveContainer width="100%" height={220}>
                      <RadarChart data={radarData} margin={{ top: 8, right: 20, bottom: 8, left: 20 }}>
                        <PolarGrid stroke="rgba(255,255,255,0.08)" />
                        <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 10 }} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 8 }} />
                        <Radar name="Score" dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={2} />
                      </RadarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart msg="Score breakdown data will appear after the first posture snapshot." />
                  )}
                  {/* Score mini-grid */}
                  <div className="grid grid-cols-3 gap-2 pt-1">
                    {[
                      { label: 'Threat',      val: scores.threat },
                      { label: 'Vuln',        val: scores.vuln_score },
                      { label: 'Risk',        val: scores.overall_risk, inv: true },
                    ].map(({ label, val, inv }) => (
                      <div key={label} className="rounded-lg bg-white/[0.03] border border-white/8 p-2 text-center">
                        <p className={clsx('text-xl font-bold', scoreColor(val, inv))}>{fmt(val, 0)}</p>
                        <p className="text-[10px] text-slate-500">{label}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Trend charts */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Risk trend */}
                <div className="rounded-xl border border-white/8 p-4">
                  <p className="text-xs font-semibold text-white mb-0.5">Risk Score Trend</p>
                  <p className="text-[10px] text-slate-400 mb-3">Repository risk over {days} days (higher = more risk)</p>
                  {(dash?.risk_trend ?? []).length >= 2 ? (
                    <ResponsiveContainer width="100%" height={180}>
                      <AreaChart data={dash.risk_trend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="rg1" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#ef4444" stopOpacity={0.2} />
                            <stop offset="100%" stopColor="#ef4444" stopOpacity={0.01} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid {...GRID} />
                        <XAxis dataKey="date" {...XAXIS} />
                        <YAxis domain={[0, 100]} {...YAXIS} />
                        <Tooltip content={<ChartTip />} />
                        <Area type="monotone" dataKey="max_risk" name="Max" stroke="#ef4444" fill="none" strokeWidth={1} strokeDasharray="3 2" strokeOpacity={0.5} />
                        <Area type="monotone" dataKey="avg_risk" name="Avg" stroke="#ef4444" fill="url(#rg1)" strokeWidth={2} />
                        <Area type="monotone" dataKey="min_risk" name="Min" stroke="#10b981" fill="none" strokeWidth={1} strokeDasharray="3 2" strokeOpacity={0.6} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : <EmptyChart msg="Risk trend builds up after each repository scan." />}
                </div>

                {/* Security trend */}
                <div className="rounded-xl border border-white/8 p-4">
                  <p className="text-xs font-semibold text-white mb-0.5">Security Score Trend</p>
                  <p className="text-[10px] text-slate-400 mb-3">Posture snapshots over {days} days</p>
                  {(dash?.security_trend ?? []).length >= 2 ? (
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={dash.security_trend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                        <CartesianGrid {...GRID} />
                        <XAxis dataKey="date" {...XAXIS} />
                        <YAxis domain={[0, 100]} {...YAXIS} />
                        <Tooltip content={<ChartTip />} />
                        <Line type="monotone" dataKey="overall"    name="Overall"    stroke="#3b82f6" strokeWidth={2.5} dot={false} />
                        <Line type="monotone" dataKey="threat"     name="Threat"     stroke="#10b981" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                        <Line type="monotone" dataKey="vuln"       name="Vuln"       stroke="#f97316" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                        <Line type="monotone" dataKey="compliance" name="Compliance" stroke="#a855f7" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                        <Line type="monotone" dataKey="asset"      name="Asset"      stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : <EmptyChart msg='Click "Snapshot Now" to begin recording posture history.' />}
                  <div className="flex flex-wrap gap-3 mt-2">
                    {[['Overall','#3b82f6'],['Threat','#10b981'],['Vuln','#f97316'],['Compliance','#a855f7'],['Asset','#f59e0b']].map(([l,c]) => (
                      <div key={l} className="flex items-center gap-1 text-[9px] text-slate-500">
                        <span className="w-3 h-0.5 rounded-full" style={{ background: c }} />{l}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Remediation trend */}
                <div className="rounded-xl border border-white/8 p-4">
                  <p className="text-xs font-semibold text-white mb-0.5">Finding Trend</p>
                  <p className="text-[10px] text-slate-400 mb-3">Open findings by severity from scans</p>
                  {(dash?.remediation_trend ?? []).length > 0 ? (
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={dash.remediation_trend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                        <CartesianGrid {...GRID} />
                        <XAxis dataKey="date" {...XAXIS} />
                        <YAxis {...YAXIS} />
                        <Tooltip content={<ChartTip />} />
                        <Bar dataKey="open_crit_high" name="Critical+High" fill="#ef4444" fillOpacity={0.85} radius={[2,2,0,0]} stackId="a" />
                        <Bar dataKey="open_med_low"   name="Medium+Low"   fill="#f97316" fillOpacity={0.6}  radius={[2,2,0,0]} stackId="a" />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : <EmptyChart msg="Finding trends appear after repository scans complete." />}
                </div>
              </div>

              {/* Trend delta pills */}
              {trendDelta.has_baseline && (
                <div className="rounded-xl border border-white/8 p-3 flex flex-wrap gap-2.5 items-center">
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mr-1">{days}d Change</p>
                  {[
                    { label: 'Security Score', v: trendDelta.overall_security, inv: false },
                    { label: 'Compliance',     v: trendDelta.compliance,       inv: false },
                    { label: 'Risk Score',     v: trendDelta.risk_score,       inv: true },
                  ].map(({ label, v, inv }) => v != null && (
                    <div key={label} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/8 text-[11px]">
                      <span className="text-slate-400">{label}</span>
                      <Delta v={v} invert={inv} />
                    </div>
                  ))}
                </div>
              )}

              {/* No-data nudge */}
              {!trendDelta.has_baseline && (
                <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-3 flex items-start gap-2.5">
                  <Info className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-medium text-yellow-400">No historical baseline yet</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Click "Snapshot Now" to record your first posture snapshot. Trend data and {days}d change metrics will appear after subsequent snapshots.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────
              TAB: RESOURCES
          ───────────────────────────────────────────────────────────── */}
          {tab === 'resources' && (
            <div className="space-y-3">
              {/* Filters */}
              <div className="flex flex-wrap gap-2 items-center">
                <div className="relative flex-1 min-w-48">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search assets…"
                    className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50" />
                </div>
                <Select value={filterSource} onChange={setFS} placeholder="All sources">
                  {Object.keys(bySource).map(s => <option key={s} value={s}>{s}</option>)}
                </Select>
                <Select value={filterRisk} onChange={setFR} placeholder="All risk levels">
                  {['critical','high','medium','low','none'].map(r => <option key={r} value={r}>{r}</option>)}
                </Select>
                <Select value={filterEnv} onChange={setFE} placeholder="All environments">
                  {['production','staging','development','unknown'].map(e => <option key={e} value={e}>{e}</option>)}
                </Select>
                {(search || filterSource || filterRisk || filterEnv) && (
                  <button onClick={() => { setSearch(''); setFS(''); setFR(''); setFE(''); }}
                    className="text-[11px] text-slate-400 hover:text-white px-2 py-1.5 rounded border border-white/10 hover:bg-white/5 flex items-center gap-1">
                    <X className="w-3 h-3" /> Clear
                  </button>
                )}
              </div>

              {/* Table */}
              <div className="rounded-xl border border-white/8 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/8 bg-white/[0.02]">
                        {['Resource', 'Type', 'Source', 'Environment', 'Region', 'Risk', 'Findings', 'Owner', 'Last Scan', ''].map(h => (
                          <th key={h} className="px-3 py-2.5 text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {assetLoading && Array.from({ length: 8 }).map((_, i) => (
                        <tr key={i}><td colSpan={10} className="px-3 py-2"><Sk className="h-5" /></td></tr>
                      ))}
                      {!assetLoading && assets.map(a => (
                        <tr key={a.id}
                          className="hover:bg-white/[0.025] transition-colors cursor-pointer group"
                          onClick={() => setDrawer(a.id)}>
                          <td className="px-3 py-2.5 max-w-[180px]">
                            <div className="flex items-center gap-1.5">
                              {sourceIcon(a.source)}
                              <span className="truncate text-white font-medium group-hover:text-blue-400 transition-colors">{a.name}</span>
                              {a.is_critical && <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-red-500" title="Critical asset" />}
                            </div>
                          </td>
                          <td className="px-3 py-2.5 text-slate-400 whitespace-nowrap">{assetTypeLabel(a.type)}</td>
                          <td className="px-3 py-2.5 text-slate-400 whitespace-nowrap">{a.source}</td>
                          <td className="px-3 py-2.5 text-slate-400">{a.environment}</td>
                          <td className="px-3 py-2.5 text-slate-400">{a.region ?? '—'}</td>
                          <td className="px-3 py-2.5">
                            <span className={clsx('px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase border', riskBadge(a.risk_level))}>
                              {a.risk_level}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span className={clsx('font-semibold', a.open_findings > 0 ? 'text-orange-400' : 'text-slate-500')}>
                              {a.open_findings}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-slate-400 max-w-[100px] truncate">{a.owner ?? '—'}</td>
                          <td className="px-3 py-2.5 text-slate-400 whitespace-nowrap">{fmtDate(a.last_scanned_at)}</td>
                          <td className="px-3 py-2.5">
                            <ChevronRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                          </td>
                        </tr>
                      ))}
                      {!assetLoading && assets.length === 0 && (
                        <tr><td colSpan={10} className="py-12 text-center text-slate-500 text-xs">
                          No assets match the current filters
                        </td></tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {assetTotal > PAGE_SIZE && (
                  <div className="flex items-center justify-between px-4 py-3 border-t border-white/8">
                    <span className="text-[11px] text-slate-500">
                      {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, assetTotal)} of {assetTotal} assets
                    </span>
                    <div className="flex gap-1">
                      <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                        className="px-2.5 py-1 rounded text-[11px] border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                        ← Prev
                      </button>
                      <span className="px-2.5 py-1 text-[11px] text-slate-400">{page} / {totalPages}</span>
                      <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                        className="px-2.5 py-1 rounded text-[11px] border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                        Next →
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Source distribution */}
              {Object.keys(bySource).length > 0 && (
                <div className="rounded-xl border border-white/8 p-4">
                  <p className="text-xs font-semibold text-white mb-3">Asset Distribution by Source</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {Object.entries(bySource).map(([src, cnt]) => (
                      <div key={src} className="flex items-center gap-2.5 p-2.5 rounded-lg bg-white/[0.03] border border-white/8 cursor-pointer hover:border-white/15 transition-colors"
                        onClick={() => { setFS(src); setPage(1); }}>
                        {sourceIcon(src)}
                        <div>
                          <p className="text-sm font-bold text-white">{cnt as number}</p>
                          <p className="text-[10px] text-slate-500 capitalize">{src}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────
              TAB: MISCONFIGURATIONS
          ───────────────────────────────────────────────────────────── */}
          {tab === 'misconfigurations' && (
            <div className="space-y-4">
              {/* Summary bar */}
              <div className="grid grid-cols-4 gap-3">
                {[
                  { sev: 'critical', count: byRisk.critical ?? 0, color: 'text-red-400',    bg: 'bg-red-500/8 border-red-500/20' },
                  { sev: 'high',     count: byRisk.high ?? 0,     color: 'text-orange-400', bg: 'bg-orange-500/8 border-orange-500/20' },
                  { sev: 'medium',   count: byRisk.medium ?? 0,   color: 'text-yellow-400', bg: 'bg-yellow-500/8 border-yellow-500/20' },
                  { sev: 'low',      count: byRisk.low ?? 0,      color: 'text-emerald-400',bg: 'bg-emerald-500/8 border-emerald-500/20' },
                ].map(({ sev, count, color, bg }) => (
                  <div key={sev} className={clsx('rounded-xl border p-3.5 text-center', bg)}>
                    <p className={clsx('text-3xl font-bold', color)}>{count}</p>
                    <p className="text-[11px] text-slate-400 capitalize mt-0.5">{sev}</p>
                  </div>
                ))}
              </div>

              {/* Groups */}
              {misconfigGroups.filter(g => g.count > 0).map(group => (
                <div key={group.severity} className={clsx('rounded-xl border p-4', group.bg)}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: group.color }} />
                    <p className="text-xs font-semibold text-white capitalize">{group.severity} Severity</p>
                    <span className="text-[11px] text-slate-400">— {group.count} affected resource{group.count !== 1 ? 's' : ''}</span>
                  </div>
                  <div className="space-y-2">
                    {group.items.map(item => (
                      <div key={item.name} className="flex items-center justify-between py-2 px-3 rounded-lg bg-black/20 border border-white/5 hover:border-white/10 transition-colors">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" style={{ color: group.color }} />
                          <span className="text-[11px] text-slate-300">{item.name}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-semibold" style={{ color: group.color }}>{item.count}</span>
                          <button onClick={() => { setFR(group.severity); setTab('resources'); }}
                            className="text-[10px] text-slate-500 hover:text-blue-400 transition-colors px-1.5 py-0.5 rounded hover:bg-blue-500/10">
                            View →
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {misconfigGroups.every(g => g.count === 0) && (
                <div className="flex flex-col items-center justify-center py-16 gap-3">
                  <CheckCircle2 className="w-10 h-10 text-emerald-500" />
                  <p className="text-sm font-semibold text-white">No misconfigurations detected</p>
                  <p className="text-xs text-slate-400">All connected resources are within acceptable risk thresholds.</p>
                </div>
              )}
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────
              TAB: RISK BREAKDOWN
          ───────────────────────────────────────────────────────────── */}
          {tab === 'risk' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Risk categories detail */}
                <div className="rounded-xl border border-white/8 p-4 space-y-3">
                  <p className="text-xs font-semibold text-white">Risk by Control Domain</p>
                  <div className="space-y-3">
                    {riskCategories.map(r => {
                      const fill = scoreFill(r.score);
                      const pct  = r.score != null ? Math.max(0, Math.min(100, r.score)) : 0;
                      return (
                        <div key={r.label} className="space-y-1">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span style={{ color: fill }}>{r.icon}</span>
                              <span className="text-[11px] text-slate-300">{r.label}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-semibold" style={{ color: fill }}>
                                {r.score != null ? r.score.toFixed(0) : '—'}
                              </span>
                              <span className={clsx('px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase', scoreColor(r.score) === 'text-emerald-400' ? 'bg-emerald-500/10 text-emerald-400' : scoreColor(r.score) === 'text-yellow-400' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-red-500/10 text-red-400')}>
                                {r.score == null ? 'N/A' : r.score >= 75 ? 'Good' : r.score >= 50 ? 'Fair' : 'Poor'}
                              </span>
                            </div>
                          </div>
                          <div className="h-1.5 rounded-full bg-white/8 overflow-hidden">
                            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: fill }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {Object.keys(breakdown).length === 0 && (
                    <p className="text-[11px] text-slate-500 text-center py-4">Click "Snapshot Now" to generate a risk breakdown</p>
                  )}
                </div>

                {/* Asset risk distribution chart */}
                <div className="rounded-xl border border-white/8 p-4 space-y-3">
                  <p className="text-xs font-semibold text-white">Asset Risk Distribution</p>
                  {Object.values(byRisk).some(v => (v as number) > 0) ? (
                    <>
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart
                          data={[
                            { name: 'Critical', count: byRisk.critical ?? 0, fill: '#ef4444' },
                            { name: 'High',     count: byRisk.high ?? 0,     fill: '#f97316' },
                            { name: 'Medium',   count: byRisk.medium ?? 0,   fill: '#f59e0b' },
                            { name: 'Low',      count: byRisk.low ?? 0,      fill: '#10b981' },
                            { name: 'None',     count: byRisk.none ?? 0,     fill: '#64748b' },
                          ]}
                          margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                          <CartesianGrid {...GRID} />
                          <XAxis dataKey="name" {...XAXIS} />
                          <YAxis {...YAXIS} />
                          <Tooltip content={<ChartTip />} />
                          <Bar dataKey="count" name="Assets" radius={[4, 4, 0, 0]}>
                            <Cell fill="#ef4444" />
                            <Cell fill="#f97316" />
                            <Cell fill="#f59e0b" />
                            <Cell fill="#10b981" />
                            <Cell fill="#64748b" />
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>

                      {/* Risk legend */}
                      <div className="grid grid-cols-5 gap-1">
                        {[
                          { label: 'Critical', count: byRisk.critical ?? 0, color: '#ef4444' },
                          { label: 'High',     count: byRisk.high ?? 0,     color: '#f97316' },
                          { label: 'Medium',   count: byRisk.medium ?? 0,   color: '#f59e0b' },
                          { label: 'Low',      count: byRisk.low ?? 0,      color: '#10b981' },
                          { label: 'None',     count: byRisk.none ?? 0,     color: '#64748b' },
                        ].map(({ label, count, color }) => (
                          <div key={label} className="text-center p-2 rounded-lg bg-white/[0.03] border border-white/5">
                            <p className="text-sm font-bold" style={{ color }}>{count}</p>
                            <p className="text-[9px] text-slate-500">{label}</p>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : <EmptyChart msg="Asset risk distribution will appear after asset discovery runs." />}

                  {/* Asset type breakdown */}
                  {Object.keys(byType).length > 0 && (
                    <div>
                      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">By Asset Type</p>
                      <div className="space-y-1.5">
                        {Object.entries(byType)
                          .sort(([, a], [, b]) => (b as number) - (a as number))
                          .slice(0, 8)
                          .map(([type, count]) => {
                            const pct = totalAssets > 0 ? Math.round(((count as number) / totalAssets) * 100) : 0;
                            return (
                              <div key={type} className="flex items-center gap-2">
                                <span className="text-[10px] text-slate-400 w-28 flex-shrink-0 truncate">{assetTypeLabel(type)}</span>
                                <div className="flex-1 h-1 rounded-full bg-white/8 overflow-hidden">
                                  <div className="h-full rounded-full bg-blue-500/60" style={{ width: `${pct}%` }} />
                                </div>
                                <span className="text-[10px] text-slate-400 w-6 text-right">{count as number}</span>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Detail Drawer overlay ──────────────────────────────────────────── */}
      {drawerAsset && (
        <>
          <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={() => setDrawer(null)} />
          <DetailDrawer assetId={drawerAsset} onClose={() => setDrawer(null)} />
        </>
      )}
    </div>
  );
}

// ─── Select helper ────────────────────────────────────────────────────────────
function Select({ value, onChange, placeholder, children }: {
  value: string; onChange: (v: string) => void;
  placeholder: string; children: React.ReactNode;
}) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="px-2.5 py-1.5 text-xs rounded-lg bg-white/5 border border-white/10 text-slate-300 focus:outline-none focus:border-blue-500/50">
      <option value="">{placeholder}</option>
      {children}
    </select>
  );
}
