import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useApi } from '@/hooks/use-api';
import { initials, formatDateTime } from '@/lib/formatters';
import { ROLE_LABELS, ROLE_COLORS } from '@/lib/constants';
import { clsx } from 'clsx';
import { Shield, Mail, Clock } from 'lucide-react';

export default function UserDetails() {
  const { id } = useParams<{ id: string }>();
  const { data: user, loading } = useApi<any>(id ? `/users/${id}` : null);
  const { data: logsData } = useApi<any>(id ? `/audit-logs?user_id=${id}&page_size=10` : null);

  const logs = logsData?.data ?? [];

  if (loading) return <div className="flex items-center justify-center h-60"><div className="w-8 h-8 rounded-full border-2 border-primary/20 border-t-primary animate-spin" /></div>;
  if (!user) return <div className="card-base text-center py-8 text-muted-foreground">User not found</div>;

  const u = user.data ?? user;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">User Details</h1>
          <p className="page-subtitle">{u.full_name ?? u.username}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="card-base flex flex-col items-center text-center gap-3">
          <div className="w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold"
            style={{ background: 'hsl(220 90% 60% / 0.2)', color: 'hsl(220 90% 70%)' }}>
            {initials(u.full_name ?? u.username ?? 'U')}
          </div>
          <div>
            <div className="font-semibold text-foreground">{u.full_name ?? u.username}</div>
            <div className="text-sm text-muted-foreground">{u.email}</div>
            <div className="mt-2 flex items-center justify-center gap-2 flex-wrap">
              <span className={clsx('text-xs font-medium capitalize', ROLE_COLORS[u.role] ?? 'text-muted-foreground')}>
                {ROLE_LABELS[u.role] ?? u.role}
              </span>
              <span className={clsx('text-xs', u.is_active ? 'text-green-400' : 'text-muted-foreground')}>
                {u.is_active ? '● Active' : '● Inactive'}
              </span>
            </div>
          </div>
          <div className="w-full text-left space-y-2 pt-2 border-t border-border text-xs">
            <div className="flex justify-between"><span className="text-muted-foreground">2FA</span><span className={u.two_factor_enabled ? 'text-green-400' : 'text-muted-foreground'}>{u.two_factor_enabled ? 'Enabled' : 'Disabled'}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Verified</span><span className={u.is_verified ? 'text-green-400' : 'text-yellow-400'}>{u.is_verified ? 'Yes' : 'Pending'}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Joined</span><span className="text-foreground">{u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}</span></div>
          </div>
        </div>

        <div className="xl:col-span-2 card-base">
          <h2 className="text-sm font-semibold text-foreground mb-4">Recent Activity</h2>
          {logs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No recent activity found.</p>
          ) : (
            <div className="space-y-2">
              {logs.map((log: any) => (
                <div key={log.id} className="flex items-start gap-3 py-2 border-b border-border/50 last:border-0">
                  <div className={clsx('w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5',
                    log.status === 'success' ? 'bg-green-500/10' : 'bg-red-500/10')}>
                    <Shield className={clsx('w-3 h-3', log.status === 'success' ? 'text-green-400' : 'text-red-400')} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-foreground">{log.action}</div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                      <Clock className="w-3 h-3" />
                      {log.created_at ? formatDateTime(log.created_at) : '—'}
                      {log.ip_address && <span>· {log.ip_address}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
