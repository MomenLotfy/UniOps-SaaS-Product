import { memo, useMemo } from 'react';
import { clsx } from 'clsx';
import { CheckCircle, XCircle, AlertTriangle, CheckSquare, Shield } from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const FRAMEWORKS = ['SOC 2', 'ISO 27001', 'CIS', 'NIST', 'PCI DSS'];

const FRAMEWORK_META: Record<string, { abbr: string; color: string; bg: string; border: string }> = {
  'SOC 2':    { abbr: 'SOC2',  color: 'text-blue-400',   bg: 'bg-blue-500/10',   border: 'border-blue-500/20'   },
  'ISO 27001':{ abbr: 'ISO',   color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
  'CIS':      { abbr: 'CIS',   color: 'text-cyan-400',   bg: 'bg-cyan-500/10',   border: 'border-cyan-500/20'   },
  'NIST':     { abbr: 'NIST',  color: 'text-green-400',  bg: 'bg-green-500/10',  border: 'border-green-500/20'  },
  'PCI DSS':  { abbr: 'PCI',   color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
};

function ScoreArc({ score }: { score: number }) {
  const r    = 28;
  const circ = 2 * Math.PI * r;
  const color =
    score >= 90 ? '#22c55e'
    : score >= 75 ? '#3b82f6'
    : score >= 60 ? '#eab308'
    : '#ef4444';
  const arc = circ * (score / 100);
  return (
    <svg width={72} height={72} className="flex-shrink-0">
      <circle cx={36} cy={36} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={6} />
      <circle cx={36} cy={36} r={r} fill="none" stroke={color} strokeWidth={6}
        strokeDasharray={`${arc} ${circ - arc}`}
        strokeDashoffset={circ / 4}
        strokeLinecap="round" />
      <text x={36} y={36} textAnchor="middle" dominantBaseline="central"
        style={{ fill: color, fontSize: 14, fontWeight: 700 }}>
        {Math.round(score)}%
      </text>
    </svg>
  );
}

function FrameworkCard({ framework, comp }: {
  framework: string;
  comp: any | undefined;
}) {
  const meta = FRAMEWORK_META[framework] ?? { abbr: framework.slice(0, 4), color: 'text-muted-foreground', bg: 'bg-white/5', border: 'border-white/10' };
  const score   = comp?.score ?? comp?.compliance_score ?? 0;
  const passed  = comp?.passed  ?? comp?.controls_passed   ?? comp?.checks_passed   ?? 0;
  const failed  = comp?.failed  ?? comp?.controls_failed   ?? comp?.checks_failed   ?? 0;
  const warnings= comp?.warnings ?? comp?.controls_warning ?? 0;
  const total   = passed + failed + warnings;

  if (!comp) {
    return (
      <div className={clsx('card-base p-4 border flex flex-col items-center justify-center gap-2 opacity-40', meta.border)}>
        <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold font-mono', meta.bg, meta.color)}>
          {meta.abbr.slice(0, 3)}
        </div>
        <p className="text-xs font-semibold text-foreground">{framework}</p>
        <p className="text-[10px] text-muted-foreground">Not configured</p>
      </div>
    );
  }

  return (
    <div className={clsx('card-base p-4 border flex flex-col gap-3', meta.border, meta.bg)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-bold text-foreground">{framework}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            {total > 0 ? `${total} controls` : 'No controls data'}
          </p>
        </div>
        <ScoreArc score={score} />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-1.5">
        <div className="flex flex-col items-center p-1.5 rounded-lg bg-green-500/10 border border-green-500/15">
          <CheckCircle className="w-3 h-3 text-green-400 mb-0.5" />
          <span className="text-sm font-bold text-green-400">{passed}</span>
          <span className="text-[9px] text-muted-foreground">Passed</span>
        </div>
        <div className="flex flex-col items-center p-1.5 rounded-lg bg-red-500/10 border border-red-500/15">
          <XCircle className="w-3 h-3 text-red-400 mb-0.5" />
          <span className="text-sm font-bold text-red-400">{failed}</span>
          <span className="text-[9px] text-muted-foreground">Failed</span>
        </div>
        <div className="flex flex-col items-center p-1.5 rounded-lg bg-yellow-500/10 border border-yellow-500/15">
          <AlertTriangle className="w-3 h-3 text-yellow-400 mb-0.5" />
          <span className="text-sm font-bold text-yellow-400">{warnings}</span>
          <span className="text-[9px] text-muted-foreground">Warnings</span>
        </div>
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div className="w-full h-1.5 rounded-full bg-white/6 overflow-hidden flex">
          <div className="bg-green-500 h-full" style={{ width: `${(passed / total) * 100}%` }} />
          <div className="bg-yellow-500 h-full" style={{ width: `${(warnings / total) * 100}%` }} />
          <div className="bg-red-500 h-full"   style={{ width: `${(failed / total) * 100}%` }} />
        </div>
      )}
    </div>
  );
}

interface OverviewComplianceProps {
  complianceData: any[] | null;
  loading: boolean;
}

function OverviewCompliance({ complianceData, loading }: OverviewComplianceProps) {
  const compMap = useMemo(() => {
    if (!complianceData) return new Map<string, any>();
    const map = new Map<string, any>();
    for (const c of complianceData) {
      const name = (c.framework ?? c.name ?? '').toUpperCase();
      // Try to match to known frameworks
      for (const fw of FRAMEWORKS) {
        if (name.includes(fw.replace(' ', '').toUpperCase()) ||
            name.includes(fw.toUpperCase()) ||
            fw.toUpperCase().includes(name)) {
          map.set(fw, c);
          break;
        }
      }
      // Also try direct name match
      if (!map.has(c.framework ?? c.name ?? '')) {
        const key = Object.keys(FRAMEWORK_META).find(k =>
          k.toLowerCase() === (c.framework ?? c.name ?? '').toLowerCase()
        );
        if (key) map.set(key, c);
      }
    }
    return map;
  }, [complianceData]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground flex items-center gap-2">
          <CheckSquare className="w-4 h-4 text-blue-400" />
          Compliance Frameworks
        </p>
        {complianceData && (
          <span className="text-[10px] text-muted-foreground">
            {complianceData.length} framework{complianceData.length !== 1 ? 's' : ''} configured
          </span>
        )}
      </div>

      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-36 rounded-xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {FRAMEWORKS.map(fw => (
            <FrameworkCard key={fw} framework={fw} comp={compMap.get(fw)} />
          ))}
        </div>
      )}

      {!loading && complianceData?.length === 0 && (
        <div className="card-base py-8 text-center">
          <Shield className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-30" />
          <p className="text-sm font-medium text-foreground">No compliance data yet</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            Run a compliance scan to populate framework scores
          </p>
        </div>
      )}
    </div>
  );
}

export default memo(OverviewCompliance);
