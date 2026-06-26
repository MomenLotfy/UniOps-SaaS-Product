import { useState, useEffect } from 'react';
import { Shield, AlertTriangle, Check, X, Info, Clock, FileText, User, Calendar, Search } from 'lucide-react';
import { clsx } from 'clsx';
import { exceptionsApi, SecurityException } from '../../services/api/security';

interface ExceptionStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  expired: number;
}

export default function SecurityExceptions() {
  const [exceptions, setExceptions] = useState<SecurityException[]>([]);
  const [stats, setStats] = useState<ExceptionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ status: '', type: '', search: '' });
  const [page, setPage] = useState(1);

  useEffect(() => {
    loadData();
  }, [filter, page]);

  async function loadData() {
    setLoading(true);
    try {
      const [excsData, statsData] = await Promise.all([
        exceptionsApi.list({
          page,
          page_size: 20,
          status: filter.status || undefined,
          exception_type: filter.type || undefined
        }),
        exceptionsApi.stats()
      ]);

      setExceptions(excsData.data || []);
      setStats(statsData.data || null);
    } catch (e) {
      console.error('Failed to load exceptions', e);
    } finally {
      setLoading(false);
    }
  }

  const visible = exceptions.filter(e =>
    (!filter.search || (e.title.toLowerCase().includes(filter.search.toLowerCase()) || e.justification.toLowerCase().includes(filter.search.toLowerCase())))
  );

  const statusColors: Record<string, string> = {
    pending: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
    approved: 'text-green-400 bg-green-400/10 border-green-400/20',
    rejected: 'text-red-400 bg-red-400/10 border-red-400/20',
    expired: 'text-gray-400 bg-gray-400/10 border-gray-400/20',
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="page-header">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="page-title">Security Exceptions</h1>
            <p className="page-subtitle">Manage temporary risk acceptances and policy overrides.</p>
          </div>
          <button className="action-btn action-btn-primary flex items-center gap-2">
            <FileText className="w-4 h-4" /> Request Exception
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-5 gap-4">
        {[
          { label: 'Total Requests', value: stats?.total || 0, icon: FileText, color: 'hsl(220 90% 60%)' },
          { label: 'Pending', value: stats?.pending || 0, icon: Clock, color: 'hsl(45 90% 60%)' },
          { label: 'Approved', value: stats?.approved || 0, icon: Check, color: 'hsl(140 60% 45%)' },
          { label: 'Rejected', value: stats?.rejected || 0, icon: X, color: 'hsl(0 80% 60%)' },
          { label: 'Expired', value: stats?.expired || 0, icon: AlertTriangle, color: 'hsl(215 16% 50%)' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card-base rounded-xl p-4 border border-border">
            <div className="flex items-center gap-2 mb-2">
              <Icon className="w-4 h-4" style={{ color }} />
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 items-center bg-background/50 p-3 rounded-xl border border-border">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search exceptions, justifications..."
            className="w-full pl-9 pr-4 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
            value={filter.search}
            onChange={e => setFilter(prev => ({ ...prev, search: e.target.value }))}
          />
        </div>

        <select
          className="px-3 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
          value={filter.status}
          onChange={e => setFilter(prev => ({ ...prev, status: e.target.value }))}
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="expired">Expired</option>
        </select>

        <select
          className="px-3 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
          value={filter.type}
          onChange={e => setFilter(prev => ({ ...prev, type: e.target.value }))}
        >
          <option value="">All Types</option>
          <option value="temporary">Temporary</option>
          <option value="permanent">Permanent</option>
          <option value="business">Business Risk</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary"></div>
        </div>
      ) : (
        <div className="space-y-3">
          {visible.length === 0 ? (
            <div className="text-center py-20 bg-background/50 rounded-xl border border-dashed border-border">
              <Shield className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-20" />
              <p className="text-sm text-muted-foreground">No security exceptions found matching the filters.</p>
            </div>
          ) : (
            visible.map((exc) => (
              <div key={exc.id} className="card-base rounded-xl p-4 border border-border flex items-start gap-4 hover:border-primary/30 transition-colors group">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-foreground">{exc.title}</span>
                    <span className={clsx('text-xs px-2 py-0.5 rounded-full border capitalize', statusColors[exc.status] || 'text-muted-foreground bg-muted/10 border-muted/20')}>
                      {exc.status}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{exc.justification}</p>

                  <div className="grid grid-cols-3 gap-4 text-[10px] text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <User className="w-3 h-3" /> {exc.requested_by}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3 h-3" /> Expires: {exc.expires_at ? new Date(exc.expires_at).toLocaleDateString() : 'Permanent'}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Shield className="w-3 h-3" /> Policy: {exc.policy_id?.slice(0, 8) || 'N/A'}
                    </div>
                  </div>
                </div>
                <button className="opacity-0 group-hover:opacity-100 transition-opacity p-2 rounded-lg border border-border hover:bg-primary/10 hover:text-primary">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>
      )}

      <div className="flex justify-between items-center pt-4">
        <div className="text-xs text-muted-foreground">
          Showing {visible.length} of {exceptions.length} exceptions
        </div>
        <div className="flex gap-2">
          <button
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1 text-xs rounded-lg border border-border disabled:opacity-50 hover:bg-primary/10"
          >
            Previous
          </button>
          <button
            disabled={visible.length < 20}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 text-xs rounded-lg border border-border disabled:opacity-50 hover:bg-primary/10"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

function ChevronRight(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9 18l6-6-6-6" />
    </svg>
  );
}
