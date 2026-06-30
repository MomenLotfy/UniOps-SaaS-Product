import { useMemo, useState } from 'react';
import { clsx } from 'clsx';
import { motion } from 'framer-motion';
import {
  Shield, TrendingUp, TrendingDown, Minus, RefreshCw,
  GitBranch, Server, Cpu, Bug, Zap, CheckSquare,
  AlertTriangle, Activity, Filter, X,
} from 'lucide-react';
import { useApi } from '@/hooks/use-api';
import OverviewCharts      from './OverviewCharts';
import OverviewFindings    from './OverviewFindings';
import OverviewCompliance  from './OverviewCompliance';
import OverviewInfra       from './OverviewInfra';
import OverviewActivity    from './OverviewActivity';

/* ── helpers ─────────────────────────────────────────────────────────── */
function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function grade(score: number): { letter: string; color: string } {
  if (score >= 90) return { letter: 'A', color: '#22c55e' };
  if (score >= 80) return { letter: 'B', color: '#3b82f6' };
  if (score >= 70) return { letter: 'C', color: '#eab308' };
  if (score >= 60) return { letter: 'D', color: '#f97316' };
  return              { letter: 'F', color: '#ef4444' };
}

function ScoreRing({ score }: { score: number }) {
  const { letter, color } = grade(score);
  const r    = 52;
  const circ = 2 * Math.PI * r;
  const arc  = circ * (score / 100);
  return (
    <svg width={130} height={130}>
      <circle cx={65} cy={65} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={8} />
      <circle cx={65} cy={65} r={r} fill="none" stroke={color} strokeWidth={8}
        strokeDasharray={`${arc} ${circ - arc}`}
        strokeDashoffset={circ / 4}
        strokeLinecap="round" />
      <text x={65} y={58} textAnchor="middle" dominantBaseline="middle"
        style={{ fill: 'hsl(215 20% 90%)', fontSize: 26, fontWeight: 700 }}>
        {Math.round(score)}
      </text>
      <text x={65} y={80} textAnchor="middle" dominantBaseline="middle"
        style={{ fill: color, fontSize: 16, fontWeight: 700 }}>
        {letter}
      </text>
    </svg>
  );
}

/* ── KPI card ────────────────────────────────────────────────────────── */
interface KpiDef {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
  sub?: string;
  alarm?: boolean;
}

function KpiCard({ k, idx }: { k: KpiDef; idx: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.04 }}
      className={clsx(
        'card-base p-4 border',
        k.alarm ? 'border-red-500/25 bg-red-500/5' : 'border-transparent',
      )}
    >
      <div className="flex items-start justify-between mb-2">
        <span className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', k.color)}>
          {k.icon}
        </span>
        {k.alarm && (
          <span className="w-2 h-2 rounded-full bg-red-400 mt-1 flex-shrink-0 animate-pulse" />
        )}
      </div>
      <p className="text-2xl font-bold text-foreground leading-none">{k.value}</p>
      <p className="text-xs text-muted-foreground mt-1">{k.label}</p>
      {k.sub && <p className="text-[10px] text-muted-foreground/60 mt-0.5">{k.sub}</p>}
    </motion.div>
  );
}

/* ── Filter bar ──────────────────────────────────────────────────────── */
const SEVERITY_OPTS = ['critical','high','medium','low'];
const ENV_OPTS      = ['production','staging','development','test'];
const CLOUD_OPTS    = ['aws','gcp','azure','on-prem'];

function FilterBar({
  repos, orgs,
  filters, onChange, onClear,
}: {
  repos: any[]; orgs: string[];
  filters: Record<string, string>;
  onChange: (k: string, v: string) => void;
  onClear: () => void;
}) {
  const activeCount = Object.values(filters).filter(Boolean).length;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {([
        { key: 'severity', label: 'Severity', opts: SEVERITY_OPTS },
        { key: 'env',      label: 'Environment', opts: ENV_OPTS    },
        { key: 'cloud',    label: 'Cloud',       opts: CLOUD_OPTS  },
      ] as const).map(({ key, label, opts }) => (
        <select key={key}
          value={filters[key] ?? ''}
          onChange={e => onChange(key, e.target.value)}
          className="h-7 px-2 text-xs rounded-lg bg-white/5 border border-white/10 text-muted-foreground
                     hover:border-white/20 focus:outline-none focus:border-blue-500/50 cursor-pointer"
        >
          <option value="">{label}</option>
          {opts.map(o => (
            <option key={o} value={o} className="bg-[hsl(230_15%_10%)] capitalize">{o}</option>
          ))}
        </select>
      ))}

      {activeCount > 0 && (
        <button onClick={onClear}
          className="h-7 px-2 text-xs rounded-lg bg-red-500/10 border border-red-500/20
                     text-red-400 hover:bg-red-500/20 flex items-center gap-1 transition-colors">
          <X className="w-3 h-3" />
          Clear ({activeCount})
        </button>
      )}
    </div>
  );
}

/* ── Section header ──────────────────────────────────────────────────── */
function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="h-px flex-1 bg-white/6" />
      <span className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-widest">{label}</span>
      <div className="h-px flex-1 bg-white/6" />
    </div>
  );
}

/* ── Overview page ───────────────────────────────────────────────────── */
export default function OverviewPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});

  /* ── API calls ──────────────────────────────────────────────────────── */
  const { data: postureRaw,  loading: postureLoading  } = useApi('/security-posture/summary');
  const { data: historyRaw,  loading: historyLoading  } = useApi('/security-posture/history');
  const { data: threatRaw,   loading: threatLoading   } = useApi('/threats/stats');
  const { data: vulnRaw,     loading: vulnLoading     } = useApi('/vulnerabilities/stats');
  const { data: compRaw,     loading: compLoading     } = useApi('/compliance');
  const { data: reposRaw,    loading: reposLoading    } = useApi('/security/repos');
  const { data: riskRaw,     loading: riskLoading     } = useApi('/repos/risk');
  const { data: assetsRaw,   loading: assetsLoading   } = useApi('/assets');
  const { data: clustersRaw, loading: clustersLoading } = useApi('/clusters');
  const { data: scoreRaw,    loading: scoreLoading    } = useApi('/security/score');
  const { data: scanHistRaw, loading: scanHistLoading } = useApi('/security/scan-history?limit=20');
  const { data: critVulnsRaw,loading: critVulnsLoading} = useApi('/vulnerabilities?severity=critical&status=open&page_size=10');
  const { data: exRaw,       loading: exLoading       } = useApi('/security-exceptions/stats');

  /* ── Normalise ──────────────────────────────────────────────────────── */
  const ps      = useMemo(() => (postureRaw ?? {}) as any, [postureRaw]);
  const ts      = useMemo(() => (threatRaw  ?? {}) as any, [threatRaw]);
  const vs      = useMemo(() => (vulnRaw    ?? {}) as any, [vulnRaw]);
  const repos   = useMemo(() => {
    const raw = reposRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [reposRaw]);
  const riskList = useMemo(() => {
    const raw = riskRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [riskRaw]);
  const assets  = useMemo(() => {
    const raw = assetsRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [assetsRaw]);
  const clusters = useMemo(() => {
    const raw = clustersRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [clustersRaw]);
  const complianceList = useMemo(() => {
    const raw = compRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [compRaw]);
  const historyList = useMemo(() => {
    const raw = historyRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    if (Array.isArray(ps.history)) return ps.history as any[];
    return [] as any[];
  }, [historyRaw, ps]);
  const scanHistory = useMemo(() => {
    const raw = scanHistRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [scanHistRaw]);
  const critVulns = useMemo(() => {
    const raw = critVulnsRaw as any;
    if (Array.isArray(raw))       return raw as any[];
    if (Array.isArray(raw?.data)) return raw.data as any[];
    return [] as any[];
  }, [critVulnsRaw]);
  const scoreData = useMemo(() => (scoreRaw ?? null) as any, [scoreRaw]);

  /* ── Derived values ──────────────────────────────────────────────────── */
  const overallScore = ps.current_score ?? scoreData?.score ?? 0;
  const trendDir     = (ps.trend ?? '').toLowerCase();
  const trendIcon    =
    trendDir === 'improving' || trendDir === 'up'
      ? <TrendingUp className="w-4 h-4 text-green-400" />
      : trendDir === 'declining' || trendDir === 'down'
      ? <TrendingDown className="w-4 h-4 text-red-400" />
      : <Minus className="w-4 h-4 text-muted-foreground" />;

  const avgCompliance = useMemo(() => {
    const scores = complianceList.map((c: any) => c.score ?? c.compliance_score ?? 0).filter((n: number) => n > 0);
    return scores.length ? Math.round(scores.reduce((a: number, b: number) => a + b, 0) / scores.length) : (ps.compliance_score ?? 0);
  }, [complianceList, ps]);

  const orgs = useMemo(() => {
    const set = new Set<string>();
    repos.forEach((r: any) => { if (r.owner) set.add(r.owner); });
    return Array.from(set);
  }, [repos]);

  const anyLoading = postureLoading || reposLoading || assetsLoading || clustersLoading;
  const lastUpdated = ps.last_updated ?? scoreData?.last_updated;

  /* ── KPIs ──────────────────────────────────────────────────────────── */
  const kpis: KpiDef[] = [
    {
      label: 'Total Repositories',
      value: reposLoading ? '…' : repos.length,
      icon:  <GitBranch className="w-4 h-4 text-blue-400" />,
      color: 'bg-blue-500/10',
    },
    {
      label: 'Total Assets',
      value: assetsLoading ? '…' : assets.length,
      icon:  <Server className="w-4 h-4 text-purple-400" />,
      color: 'bg-purple-500/10',
    },
    {
      label: 'Active K8s Clusters',
      value: clustersLoading ? '…' : clusters.length,
      icon:  <Cpu className="w-4 h-4 text-cyan-400" />,
      color: 'bg-cyan-500/10',
    },
    {
      label: 'Critical Vulnerabilities',
      value: vulnLoading ? '…' : (vs.critical ?? vs.by_severity?.critical ?? 0),
      icon:  <Bug className="w-4 h-4 text-red-400" />,
      color: 'bg-red-500/10',
      alarm: !vulnLoading && (vs.critical ?? vs.by_severity?.critical ?? 0) > 0,
    },
    {
      label: 'Active Threats',
      value: threatLoading ? '…' : (ts.open ?? ts.active ?? 0),
      icon:  <AlertTriangle className="w-4 h-4 text-orange-400" />,
      color: 'bg-orange-500/10',
      alarm: !threatLoading && (ts.open ?? ts.active ?? 0) > 0,
    },
    {
      label: 'Compliance Score',
      value: compLoading ? '…' : `${avgCompliance}%`,
      icon:  <CheckSquare className="w-4 h-4 text-green-400" />,
      color: 'bg-green-500/10',
      sub:   `${complianceList.length} frameworks`,
    },
    {
      label: 'Overall Risk Score',
      value: postureLoading ? '…' : Math.round(overallScore),
      icon:  <Shield className="w-4 h-4 text-indigo-400" />,
      color: 'bg-indigo-500/10',
      sub:   trendDir || undefined,
    },
    {
      label: 'Open Remediations',
      value: postureLoading ? '…' : (ps.open_remediations ?? ps.pending_remediations ?? ts.open ?? '—'),
      icon:  <Zap className="w-4 h-4 text-yellow-400" />,
      color: 'bg-yellow-500/10',
    },
  ];

  return (
    <div className="space-y-6 pb-8">

      {/* ── Page header ─────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
        <div>
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-400" />
            Security Overview
          </h2>
          {lastUpdated && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Last updated · {new Date(lastUpdated).toLocaleString()}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
          <FilterBar
            repos={repos} orgs={orgs}
            filters={filters}
            onChange={(k, v) => setFilters(prev => ({ ...prev, [k]: v }))}
            onClear={() => setFilters({})}
          />
        </div>
      </div>

      {/* ── 8 KPI Cards ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-3">
        {kpis.map((k, i) => <KpiCard key={k.label} k={k} idx={i} />)}
      </div>

      {/* ── Security Score Hero ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Score card */}
        <div className="card-base p-6 flex flex-col items-center justify-center gap-2 border border-indigo-500/20 bg-indigo-500/5">
          {postureLoading ? (
            <div className="flex flex-col items-center gap-3">
              <Skeleton className="w-[130px] h-[130px] rounded-full" />
              <Skeleton className="w-24 h-4 rounded" />
            </div>
          ) : (
            <>
              <ScoreRing score={overallScore} />
              <div className="text-center">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Overall Security Score</p>
                <div className="flex items-center justify-center gap-2 mt-1">
                  {trendIcon}
                  <span className="text-xs capitalize text-muted-foreground">{trendDir || 'Stable'}</span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Score breakdown */}
        <div className="xl:col-span-2 card-base p-5">
          <p className="text-xs font-semibold text-muted-foreground mb-4 uppercase tracking-wide">Score Breakdown</p>
          {postureLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-6 rounded" />)}
            </div>
          ) : (
            <div className="space-y-3">
              {([
                { label: 'Threat Score',         value: ps.threat_score       ?? 0, color: 'bg-red-500'    },
                { label: 'Vulnerability Score',  value: ps.vulnerability_score ?? 0, color: 'bg-orange-500' },
                { label: 'Compliance Score',     value: ps.compliance_score   ?? avgCompliance, color: 'bg-green-500'  },
                { label: 'Asset Risk Score',     value: ps.asset_score        ?? 0, color: 'bg-purple-500' },
                { label: 'Policy Score',         value: ps.policy_score       ?? 0, color: 'bg-blue-500'   },
              ] as const).map(({ label, value, color }) => (
                <div key={label}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="font-bold text-foreground font-mono">{Math.round(value)}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/6 overflow-hidden">
                    <motion.div
                      className={clsx('h-full rounded-full', color)}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(Math.round(value), 100)}%` }}
                      transition={{ duration: 0.6, ease: 'easeOut' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Charts ──────────────────────────────────────────────────── */}
      <SectionDivider label="Analytics" />
      <OverviewCharts
        postureHistory={historyList}
        repos={repos}
        riskList={riskList}
        scanHistory={scanHistory}
        assets={assets}
        loading={historyLoading || reposLoading || riskLoading || scanHistLoading}
      />

      {/* ── Infrastructure + Threat Summary ─────────────────────────── */}
      <SectionDivider label="Infrastructure & Threats" />
      <OverviewInfra
        repos={repos}
        assets={assets}
        clusters={clusters}
        threatStats={ts}
        loading={anyLoading || threatLoading}
      />

      {/* ── Critical Findings ───────────────────────────────────────── */}
      <SectionDivider label="Critical Findings" />
      <OverviewFindings
        vulns={critVulns}
        loading={critVulnsLoading}
      />

      {/* ── Compliance ──────────────────────────────────────────────── */}
      <SectionDivider label="Compliance" />
      <OverviewCompliance
        complianceData={complianceList}
        loading={compLoading}
      />

      {/* ── Activity + Remediation + AI ─────────────────────────────── */}
      <SectionDivider label="Activity & Remediation" />
      <OverviewActivity
        scanHistory={scanHistory}
        postureSummary={ps}
        scoreData={scoreData}
        exceptionStats={exRaw ?? null}
        loading={scanHistLoading || postureLoading || scoreLoading || exLoading}
      />
    </div>
  );
}
