import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Users as UsersIcon, UserPlus, Search, RefreshCw, Filter, Shield, Trash2, Mail, MoreHorizontal } from 'lucide-react';
import { ROLE_LABELS, ROLE_COLORS } from '@/lib/constants';
import { formatRelative, initials } from '@/lib/formatters';
import { useDebounce } from '@/hooks/use-debounce';
import { clsx } from 'clsx';
import { useApi, apiPatch, apiPost } from '@/hooks/use-api';

export default function AdminUsers() {
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');
  const [showInvite, setShowInvite] = useState(false);
  const [inviting, setInviting] = useState(false);

  const debouncedSearch = useDebounce(search);
  const searchParam = debouncedSearch ? `&search=${encodeURIComponent(debouncedSearch)}` : '';
  const roleParam = roleFilter ? `&role=${roleFilter}` : '';

  const { data, loading, refetch } = useApi<any>(`/users?page_size=50${searchParam}${roleParam}`);
  const users = (Array.isArray(data) ? data : data?.data) ?? [];

  const statusBadge: Record<string, string> = {
    active: 'text-green-400', inactive: 'text-muted-foreground',
    pending: 'text-yellow-400', suspended: 'text-red-400',
  };

  const handleDeactivate = async (userId: string) => {
    await apiPatch(`/users/${userId}`, { is_active: false });
    refetch();
    setOpenMenu(null);
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviting(true);
    try {
      await apiPost('/users/invite', { email: inviteEmail, role: inviteRole });
      setShowInvite(false);
      setInviteEmail('');
      refetch();
    } finally {
      setInviting(false);
    }
  };

  const inputCls = 'px-3 py-2 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/50 text-foreground';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">User Management</h1>
          <p className="page-subtitle">Manage team members, roles & access</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => refetch()} className="action-btn" disabled={loading}>
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />Refresh
          </button>
          <button onClick={() => setShowInvite(true)} className="action-btn-primary">
            <UserPlus className="w-4 h-4" />Invite User
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
        {[
          { label: 'Total Members', value: users.length, color: 'text-blue-400', bg: 'bg-blue-500/10' },
          { label: 'Active', value: users.filter((u: any) => u.is_active).length, color: 'text-green-400', bg: 'bg-green-500/10' },
          { label: 'Pending', value: users.filter((u: any) => u.status === 'pending').length, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
          { label: '2FA Enabled', value: users.filter((u: any) => u.two_factor_enabled).length, color: 'text-purple-400', bg: 'bg-purple-500/10' },
        ].map(s => (
          <div key={s.label} className="card-base flex items-center gap-4">
            <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center', s.bg)}>
              <UsersIcon className={clsx('w-5 h-5', s.color)} />
            </div>
            <div><div className="stat-value text-xl">{s.value}</div><div className="stat-label">{s.label}</div></div>
          </div>
        ))}
      </div>

      {/* Invite Modal */}
      {showInvite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card-base w-full max-w-md mx-4">
            <h2 className="text-sm font-semibold text-foreground mb-4">Invite Team Member</h2>
            <form onSubmit={handleInvite} className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Email address</label>
                <input type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)}
                  placeholder="colleague@company.com" required
                  className={clsx(inputCls, 'w-full')} style={inputStyle} />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Role</label>
                <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}
                  className={clsx(inputCls, 'w-full')} style={inputStyle}>
                  {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div className="flex gap-2 pt-1">
                <button type="button" onClick={() => setShowInvite(false)} className="action-btn flex-1">Cancel</button>
                <button type="submit" disabled={inviting} className="action-btn-primary flex-1">
                  {inviting ? 'Sending...' : 'Send Invitation'}
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}

      <div className="card-base">
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <div className="flex-1 relative min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search by name or email..."
              className={clsx(inputCls, 'w-full pl-9')} style={inputStyle} />
          </div>
          <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}
            className={clsx(inputCls)} style={inputStyle}>
            <option value="">All Roles</option>
            {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>

        {loading ? (
          <div className="py-8 text-center text-sm text-muted-foreground">Loading users...</div>
        ) : users.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">No users found</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th><th>Role</th><th>Status</th><th>2FA</th><th>Last Active</th><th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u: any) => (
                <tr key={u.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                        style={{ background: 'hsl(220 90% 60% / 0.15)', color: 'hsl(220 90% 70%)' }}>
                        {initials(u.full_name ?? u.username ?? 'U')}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-foreground">{u.full_name ?? u.username}</div>
                        <div className="text-xs text-muted-foreground">{u.email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={clsx('text-xs font-medium capitalize', ROLE_COLORS[u.role] ?? 'text-muted-foreground')}>
                      {ROLE_LABELS[u.role] ?? u.role}
                    </span>
                  </td>
                  <td>
                    <span className={clsx('text-xs font-medium capitalize', u.is_active ? 'text-green-400' : 'text-muted-foreground')}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <span className={clsx('text-xs', u.two_factor_enabled ? 'text-green-400' : 'text-muted-foreground')}>
                      {u.two_factor_enabled ? '✓ Enabled' : '—'}
                    </span>
                  </td>
                  <td>
                    <span className="text-xs text-muted-foreground">
                      {u.updated_at ? formatRelative(u.updated_at) : '—'}
                    </span>
                  </td>
                  <td>
                    <div className="relative">
                      <button onClick={() => setOpenMenu(openMenu === u.id ? null : u.id)} className="p-1.5 rounded-md hover:bg-accent text-muted-foreground">
                        <MoreHorizontal className="w-4 h-4" />
                      </button>
                      {openMenu === u.id && (
                        <div className="absolute right-0 top-8 w-36 rounded-lg border border-border z-10 overflow-hidden"
                          style={{ background: 'hsl(230 18% 10%)' }}>
                          <button className="w-full px-3 py-2 text-xs text-left hover:bg-accent flex items-center gap-2 text-muted-foreground">
                            <Mail className="w-3.5 h-3.5" />Send Email
                          </button>
                          <button className="w-full px-3 py-2 text-xs text-left hover:bg-accent flex items-center gap-2 text-muted-foreground">
                            <Shield className="w-3.5 h-3.5" />Change Role
                          </button>
                          <button onClick={() => handleDeactivate(u.id)}
                            className="w-full px-3 py-2 text-xs text-left hover:bg-accent flex items-center gap-2 text-red-400">
                            <Trash2 className="w-3.5 h-3.5" />Deactivate
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </motion.div>
  );
}
