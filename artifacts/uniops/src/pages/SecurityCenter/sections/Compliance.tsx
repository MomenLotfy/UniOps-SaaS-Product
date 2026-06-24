import { CheckSquare, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? '#22c55e' : score >= 60 ? '#eab308' : '#ef4444';
  return (
    <div className="w-full bg-white/5 rounded-full h-1.5 mt-2">
      <div className="h-1.5 rounded-full transition-all" style={{ width: `${score}%`, background: color }} />
    </div>
  );
}

export default function Compliance() {
  const { data: raw, loading, refetch } = useApi<any>('/compliance');
  const items = raw?.data ?? (Array.isArray(raw) ? raw : []);

  const avg = items.length > 0
    ? items.reduce((a: number, c: any) => a + (c.score ?? 0), 0) / items.length
    : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Compliance</h1>
          <p className="text-xs text-muted-foreground">
            {items.length} framework{items.length !== 1 ? 's' : ''} · avg score {avg.toFixed(0)}%
          </p>
        </div>
        <button onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
          style={{ borderColor: 'hsl(230 15% 20%)' }}>
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-3">
        {loading ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)
        ) : items.length === 0 ? (
          <div className="col-span-3 card-base py-12 text-center">
            <CheckSquare className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground mb-1">No compliance data</p>
            <p className="text-xs text-muted-foreground">Run a compliance scan to see framework scores here.</p>
          </div>
        ) : items.map((c: any) => {
          const score = c.score ?? 0;
          const color = score >= 80 ? 'text-green-400' : score >= 60 ? 'text-yellow-400' : 'text-red-400';
          return (
            <div key={c.id} className="card-base p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                    score >= 80 ? 'bg-green-500/10' : score >= 60 ? 'bg-yellow-500/10' : 'bg-red-500/10')}>
                    {score >= 80
                      ? <CheckCircle className="w-4 h-4 text-green-400" />
                      : <AlertTriangle className={clsx('w-4 h-4', score >= 60 ? 'text-yellow-400' : 'text-red-400')} />}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{c.framework}</p>
                    <p className={clsx('text-[10px] capitalize', c.status === 'compliant' ? 'text-green-400' : c.status === 'non_compliant' ? 'text-red-400' : 'text-yellow-400')}>
                      {c.status?.replace(/_/g, ' ') ?? 'in progress'}
                    </p>
                  </div>
                </div>
                <span className={clsx('text-lg font-bold', color)}>{score.toFixed(0)}%</span>
              </div>
              <ScoreBar score={score} />
              <div className="flex justify-between mt-2 text-[10px] text-muted-foreground">
                <span className="text-green-400">{c.passed ?? 0} passed</span>
                <span className="text-red-400">{c.failed ?? 0} failed</span>
                <span>{c.total ?? 0} total</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
