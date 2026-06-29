import { memo } from 'react';
import { clsx } from 'clsx';
import {
  GitBranch, Lock, Unlock, TrendingUp, TrendingDown, Minus,
  Bug, Key, Container, AlertTriangle, CheckCircle, Clock,
  Play, Code2,
} from 'lucide-react';
import type { MergedRepo, RiskLevel } from './types';
import { RISK_STYLES } from './types';

function RiskBadge({ level }: { level: RiskLevel | string }) {
  const s = RISK_STYLES[level as RiskLevel] ?? RISK_STYLES.low;
  return (
    <span className={clsx(
      'flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-full font-bold border uppercase tracking-wider',
      s.bg, s.text, s.border,
    )}>
      <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', s.dot)} />
      {level}
    </span>
  );
}

function ScoreRing({ score, size = 36 }: { score: number; size?: number }) {
  const r   = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const fill = circ * (1 - score / 100);
  const color =
    score >= 80 ? '#22c55e'
    : score >= 60 ? '#eab308'
    : score >= 40 ? '#f97316'
    : '#ef4444';
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={4} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={4}
        strokeDasharray={circ} strokeDashoffset={fill} strokeLinecap="round" />
      <text x={size / 2} y={size / 2} textAnchor="middle" dominantBaseline="central"
        style={{ transform: 'rotate(90deg)', transformOrigin: `${size / 2}px ${size / 2}px`, fill: color, fontSize: 10, fontWeight: 700 }}>
        {Math.round(score)}
      </text>
    </svg>
  );
}

function TrendIcon({ trend }: { trend?: string }) {
  if (!trend || trend === 'stable') return <Minus className="w-3 h-3 text-muted-foreground" />;
  if (trend === 'worsening') return <TrendingUp className="w-3 h-3 text-red-400" />;
  if (trend === 'improving') return <TrendingDown className="w-3 h-3 text-green-400" />;
  return null;
}

function ProviderIcon({ provider, className }: { provider: string; className?: string }) {
  const base = clsx('text-[9px] font-bold px-1.5 py-0.5 rounded font-mono uppercase tracking-wide', className);
  if (provider === 'github')   return <span className={clsx(base, 'bg-gray-700 text-gray-200')}>GH</span>;
  if (provider === 'gitlab')   return <span className={clsx(base, 'bg-orange-600/30 text-orange-300')}>GL</span>;
  if (provider === 'azure')    return <span className={clsx(base, 'bg-blue-700/30 text-blue-300')}>AZ</span>;
  if (provider === 'bitbucket') return <span className={clsx(base, 'bg-blue-800/30 text-blue-300')}>BB</span>;
  return <GitBranch className="w-3.5 h-3.5 text-muted-foreground" />;
}

function CountPill({ count, color, title }: { count: number; color: string; title: string }) {
  if (!count) return null;
  return (
    <span title={`${count} ${title}`}
      className={clsx('flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-md font-mono font-semibold', color)}>
      {count}
    </span>
  );
}

const LANG_COLORS: Record<string, string> = {
  typescript: 'text-blue-300',  javascript: 'text-yellow-300',
  python: 'text-green-300',     go: 'text-cyan-300',
  java: 'text-orange-300',      ruby: 'text-red-300',
  rust: 'text-orange-400',      php: 'text-purple-300',
  c: 'text-gray-300',           cpp: 'text-pink-300',
};

interface RepoCardProps {
  repo: MergedRepo;
  onClick: () => void;
  onScan: () => void;
  canScan: boolean;
  isScanning: boolean;
}

function RepoCard({ repo, onClick, onScan, canScan, isScanning }: RepoCardProps) {
  const risk    = repo.risk;
  const rl      = (risk?.risk_level ?? 'low') as RiskLevel;
  const rs      = RISK_STYLES[rl];
  const score   = risk?.security_score ?? repo.last_scan_score;
  const scanned = !!repo.last_scan_at || !!risk?.last_scan_at;
  const owner   = risk?.owner ?? repo.full_name.split('/')[0];
  const langClass = LANG_COLORS[repo.language?.toLowerCase() ?? ''] ?? 'text-muted-foreground';

  const lastScanDate = repo.last_scan_at ?? risk?.last_scan_at;
  const lastScanFmt  = lastScanDate
    ? new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(
        Math.round((new Date(lastScanDate).getTime() - Date.now()) / 86400000), 'day'
      )
    : null;

  return (
    <button
      onClick={onClick}
      className={clsx(
        'relative flex flex-col text-left w-full rounded-xl border p-4 transition-all duration-150 group',
        'hover:scale-[1.01] hover:shadow-xl hover:shadow-black/30',
        rl === 'critical' ? 'border-red-500/25 bg-red-500/5'
        : rl === 'high'   ? 'border-orange-500/20 bg-orange-500/5'
        : 'border-white/8 bg-white/3',
      )}
      style={{ background: rl === 'critical' ? 'hsl(0 60% 8%)' : rl === 'high' ? 'hsl(25 60% 8%)' : 'hsl(230 15% 9%)' }}
    >
      {/* Risk stripe */}
      <div className={clsx('absolute left-0 top-3 bottom-3 w-0.5 rounded-r-full', rs.dot)} />

      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-3 pl-2">
        <div className="flex items-center gap-2 min-w-0">
          <ProviderIcon provider={repo.provider} />
          <div className="min-w-0">
            <p className="text-xs font-semibold text-foreground truncate leading-tight">
              {repo.name}
            </p>
            <p className="text-[10px] text-muted-foreground truncate">{owner}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {risk && <RiskBadge level={rl} />}
          {!risk && !scanned && (
            <span className="text-[9px] px-2 py-0.5 rounded-full border border-white/10 text-muted-foreground bg-white/5">
              Unscanned
            </span>
          )}
        </div>
      </div>

      {/* Meta row */}
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground mb-3 pl-2 flex-wrap">
        {repo.is_private
          ? <><Lock className="w-3 h-3" /><span>Private</span></>
          : <><Unlock className="w-3 h-3" /><span>Public</span></>}
        <span className="opacity-30">·</span>
        <GitBranch className="w-3 h-3" />
        <span>{repo.default_branch}</span>
        {repo.language && (
          <>
            <span className="opacity-30">·</span>
            <Code2 className={clsx('w-3 h-3', langClass)} />
            <span className={langClass}>{repo.language}</span>
          </>
        )}
        {risk?.trend && (
          <>
            <span className="opacity-30">·</span>
            <TrendIcon trend={risk.trend} />
            <span className={risk.trend === 'improving' ? 'text-green-400' : risk.trend === 'worsening' ? 'text-red-400' : ''}>
              {risk.trend}
            </span>
          </>
        )}
      </div>

      {/* Score + findings row */}
      <div className="flex items-center justify-between pl-2">
        <div className="flex items-center gap-3">
          {/* Security score ring */}
          {score != null ? (
            <div className="flex flex-col items-center gap-0.5">
              <ScoreRing score={score} size={38} />
              <span className="text-[8px] text-muted-foreground">Health</span>
            </div>
          ) : (
            <div className="w-9 h-9 rounded-full border border-dashed border-white/15 flex items-center justify-center">
              <span className="text-[8px] text-muted-foreground">—</span>
            </div>
          )}

          {/* Finding counts */}
          {risk && (
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-muted-foreground w-12">Findings</span>
                <CountPill count={risk.critical_count} color="bg-red-500/15 text-red-400" title="critical" />
                <CountPill count={risk.high_count}     color="bg-orange-500/15 text-orange-400" title="high" />
                <CountPill count={Math.max(0, risk.open_findings - risk.critical_count - risk.high_count)}
                  color="bg-yellow-500/15 text-yellow-400" title="medium/low" />
              </div>
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-muted-foreground w-12">Other</span>
                {risk.secret_count    > 0 && (
                  <span title={`${risk.secret_count} secrets`}
                    className="flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-md bg-yellow-500/10 text-yellow-400 font-mono">
                    <Key className="w-2.5 h-2.5" />{risk.secret_count}
                  </span>
                )}
                {risk.container_count > 0 && (
                  <span title={`${risk.container_count} container issues`}
                    className="flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-md bg-blue-500/10 text-blue-400 font-mono">
                    <Container className="w-2.5 h-2.5" />{risk.container_count}
                  </span>
                )}
                {risk.compliance_violations > 0 && (
                  <span title={`${risk.compliance_violations} violations`}
                    className="flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-md bg-purple-500/10 text-purple-400 font-mono">
                    <AlertTriangle className="w-2.5 h-2.5" />{risk.compliance_violations}
                  </span>
                )}
                {!risk.secret_count && !risk.container_count && !risk.compliance_violations && (
                  <span className="text-[9px] text-muted-foreground/50">None</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right side: scan info + scan button */}
        <div className="flex flex-col items-end gap-1.5">
          {canScan && (
            <button
              onClick={e => { e.stopPropagation(); onScan(); }}
              disabled={isScanning}
              className={clsx(
                'flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all',
                isScanning
                  ? 'bg-blue-500/10 text-blue-400/50 cursor-not-allowed'
                  : 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 border border-blue-500/20',
              )}
            >
              <Play className="w-2.5 h-2.5" />
              {isScanning ? 'Running…' : 'Scan'}
            </button>
          )}
          {lastScanFmt && (
            <div className="flex items-center gap-1 text-[9px] text-muted-foreground">
              <Clock className="w-2.5 h-2.5" />
              <span>{lastScanFmt}</span>
            </div>
          )}
          {!scanned && (
            <div className="flex items-center gap-1 text-[9px] text-muted-foreground/50">
              <Clock className="w-2.5 h-2.5" />
              <span>Never scanned</span>
            </div>
          )}
        </div>
      </div>

      {/* Footer badges */}
      <div className="flex items-center gap-1.5 mt-3 pl-2 flex-wrap">
        {repo.has_dockerfile && (
          <span className="text-[8px] px-1.5 py-0.5 rounded border border-blue-500/20 bg-blue-500/10 text-blue-400 font-medium">
            Docker
          </span>
        )}
        {repo.has_cicd && (
          <span className="text-[8px] px-1.5 py-0.5 rounded border border-green-500/20 bg-green-500/10 text-green-400 font-medium">
            CI/CD
          </span>
        )}
        {risk?.risk_score != null && (
          <span className="text-[8px] px-1.5 py-0.5 rounded border border-white/10 bg-white/5 text-muted-foreground font-mono">
            Risk {Math.round(risk.risk_score)}/100
          </span>
        )}
        {score != null && (
          <span className={clsx('text-[8px] px-1.5 py-0.5 rounded border font-mono',
            score >= 80 ? 'border-green-500/20 bg-green-500/10 text-green-400'
            : score >= 60 ? 'border-yellow-500/20 bg-yellow-500/10 text-yellow-400'
            : 'border-red-500/20 bg-red-500/10 text-red-400'
          )}>
            Score {Math.round(score)}
          </span>
        )}
        {!risk && scanned && (
          <span className="flex items-center gap-1 text-[8px] text-green-400">
            <CheckCircle className="w-2.5 h-2.5" />Scanned
          </span>
        )}
      </div>
    </button>
  );
}

export default memo(RepoCard);
