import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { FileSearch, Filter, Download, RefreshCw, CheckCircle, XCircle } from 'lucide-react';
import { formatDateTime, initials } from '@/lib/formatters';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';

const ACTION_LABELS: Record<string, string> = {
  'user.login': 'User Login', 'user.logout': 'User Logout', 'user.create': 'User Created',
  'user.update': 'User Updated', 'user.delete': 'User Deleted', 'user.invite': 'User Invited',
  'integration.connect': 'Integration Connected', 'integration.disconnect': 'Integration Disconnected',
  'role.assign': 'Role Assigned', 'role.revoke': 'Role Revoked',
  'api_key.create': 'API Key Created', 'api_key.revoke': 'API Key Revoked',
  'settings.update': 'Settings Updated',
};

export default function AuditLogs() {
  const [filter, setFilter] = useState<'all' | 'success' | 'failure'>('all');
  const [page, setPage] = useState(1);

  const statusParam = filter === 'all' ? '' : `&status=${filter}`;
  const { data, loading, refetch } = useApi<any>(`/audit-logs?page=${page}&page_size=20${statusParam}`);

  const logs = (Array.isArray(data) ? data : data?.data) ?? [];
  const total = Array.isArray(data) ? data.length : (data?.total ?? 0);
  const pages = Array.isArray(data) ? 1 : (data?.pages ?? 1);

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit Logs</h1>
          <p className="page-subtitle">Complete record of all actions in your workspace — {total} total events</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="action-btn"><Download className="w-4 h-4" />Export</button>
          <button onClick={() => refetch()} className="action-btn" disabled={loading}>
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />Refresh
          </button>
        </div>
      </div>

      <div className="tab-bar mb-5">
        {(['all', 'success', 'failure'] as const).map(f => (
          <button key={f} onClick={() => { setFilter(f); setPage(1); }} className={clsx('tab-btn capitalize', filter === f && 'active')}>
            {f === 'all' ? 'All Events' : f === 'success' ? 'Successful' : 'Failed'}
          </button>
        ))}
      </div>

      <div className="card-base overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">Loading audit logs...</div>
        ) : logs.length === 0 ? (
          <div className="py-12 text-center">
            <FileSearch className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">No audit logs found</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>User</th>
                <th>Resource</th>
                <th>IP Address</th>
                <th>Status</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log: any) => (
                <tr key={log.id}>
                  <td>
                    <span className="text-xs font-medium text-foreground">
                      {ACTION_LABELS[log.action] ?? log.action}
                    </span>
                    <div className="text-xs text-muted-foreground font-mono">{log.action}</div>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center text-xs text-blue-400 font-medium flex-shrink-0">
                        {initials(log.user_name ?? log.user_email ?? 'U')}
                      </div>
                      <div>
                        <div className="text-xs font-medium text-foreground">{log.user_name ?? 'Unknown'}</div>
                        <div className="text-xs text-muted-foreground">{log.user_email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className="text-xs text-muted-foreground capitalize">{log.resource_type ?? log.resource}</span>
                    {log.resource_id && <div className="text-xs text-muted-foreground font-mono truncate max-w-[100px]">{log.resource_id?.substring(0, 8)}</div>}
                  </td>
                  <td><code className="text-xs font-mono text-muted-foreground">{log.ip_address ?? log.ip ?? '—'}</code></td>
                  <td>
                    <span className={clsx('flex items-center gap-1.5 text-xs font-medium', log.status === 'success' ? 'text-green-400' : 'text-red-400')}>
                      {log.status === 'success' ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                      {log.status}
                    </span>
                  </td>
                  <td>
                    <span className="text-xs text-muted-foreground">
                      {log.created_at ? formatDateTime(log.created_at) : '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <span className="text-xs text-muted-foreground">Page {page} of {pages}</span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="action-btn text-xs py-1">Prev</button>
              <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages} className="action-btn text-xs py-1">Next</button>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
