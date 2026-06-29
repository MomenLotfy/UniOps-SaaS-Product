import { useApi } from '@/hooks/use-api';
import { clsx } from 'clsx';
import { BookOpen, ClipboardList, Clock, Users, TrendingUp, CheckSquare } from 'lucide-react';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

function StatCard({
  label, value, sub, icon: Icon, color, loading,
}: {
  label: string; value?: string | number; sub?: string;
  icon: React.ElementType; color: string; loading?: boolean;
}) {
  return (
    <div className="card-base p-4 flex items-center gap-3">
      <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0', color)}>
        <Icon className="w-4.5 h-4.5" />
      </div>
      <div className="min-w-0">
        {loading ? <Skeleton className="h-5 w-12 mb-1" /> : (
          <p className="text-xl font-bold text-foreground">{value ?? '—'}</p>
        )}
        <p className="text-xs text-muted-foreground">{label}</p>
        {sub && !loading && <p className="text-[10px] text-muted-foreground/70">{sub}</p>}
      </div>
    </div>
  );
}

export default function GovernanceOverview() {
  const { data: policyRaw,    loading: policyLoading }    = useApi<any>('/security-policies/stats');
  const { data: exRaw,        loading: exLoading }        = useApi<any>('/security-exceptions/stats');
  const { data: slaRaw,       loading: slaLoading }       = useApi<any>('/sla/stats');
  const { data: ownershipRaw, loading: ownershipLoading } = useApi<any>('/ownership/stats');

  const pol = policyRaw?.data  ?? policyRaw;
  const ex  = exRaw?.data      ?? exRaw;
  const sla = slaRaw?.data     ?? slaRaw;
  const own = ownershipRaw?.data ?? ownershipRaw;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-bold text-foreground">Governance Overview</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Policies, exceptions, SLA compliance and ownership summary
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard
          icon={BookOpen} color="bg-purple-500/15 text-purple-400"
          label="Active Policies" loading={policyLoading}
          value={pol?.active} sub={`${pol?.total ?? '—'} total`}
        />
        <StatCard
          icon={ClipboardList} color="bg-yellow-500/15 text-yellow-400"
          label="Pending Exceptions" loading={exLoading}
          value={ex?.pending} sub={`${ex?.approved ?? '—'} approved`}
        />
        <StatCard
          icon={Clock} color="bg-red-500/15 text-red-400"
          label="SLA Breaches" loading={slaLoading}
          value={sla?.breached} sub={sla != null ? undefined : 'endpoint pending'}
        />
        <StatCard
          icon={Users} color="bg-blue-500/15 text-blue-400"
          label="Owned Assets" loading={ownershipLoading}
          value={own?.owned_count} sub={own != null ? undefined : 'endpoint pending'}
        />
        <StatCard
          icon={TrendingUp} color="bg-green-500/15 text-green-400"
          label="Policy Pass Rate" loading={policyLoading}
          value={pol?.pass_rate != null ? `${Math.round(pol.pass_rate)}%` : undefined}
          sub="last 30 days"
        />
        <StatCard
          icon={CheckSquare} color="bg-cyan-500/15 text-cyan-400"
          label="Compliance Score" loading={policyLoading}
          value={pol?.compliance_score != null ? `${Math.round(pol.compliance_score)}%` : undefined}
        />
      </div>

      {/* Policy category breakdown */}
      {!policyLoading && pol?.by_category && Object.keys(pol.by_category).length > 0 && (
        <div className="card-base p-4">
          <p className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-purple-400" />
            Policies by Category
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {Object.entries(pol.by_category as Record<string, number>)
              .sort(([, a], [, b]) => b - a)
              .map(([cat, count]) => (
                <div
                  key={cat}
                  className="flex items-center justify-between px-3 py-2 rounded-lg border"
                  style={{ borderColor: 'hsl(230 15% 16%)', background: 'hsl(230 15% 8%)' }}
                >
                  <span className="text-xs text-muted-foreground capitalize truncate">{cat.replace(/_/g, ' ')}</span>
                  <span className="text-sm font-bold text-foreground ml-2">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Exceptions status breakdown */}
      {!exLoading && ex?.by_status && Object.keys(ex.by_status).length > 0 && (
        <div className="card-base p-4">
          <p className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-yellow-400" />
            Exception Status Breakdown
          </p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ex.by_status as Record<string, number>).map(([status, count]) => {
              const color =
                status === 'approved'  ? 'bg-green-500/15 text-green-400 border-green-500/25'
                : status === 'pending'   ? 'bg-yellow-500/15 text-yellow-400 border-yellow-500/25'
                : status === 'rejected'  ? 'bg-red-500/15 text-red-400 border-red-500/25'
                : 'bg-white/5 text-muted-foreground border-white/10';
              return (
                <div key={status} className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg border text-xs', color)}>
                  <span className="capitalize font-medium">{status}</span>
                  <span className="font-bold text-sm">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {policyLoading && (
        <div className="card-base p-4 space-y-3">
          <Skeleton className="h-5 w-40" />
          <div className="grid grid-cols-3 gap-2">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}
          </div>
        </div>
      )}
    </div>
  );
}
