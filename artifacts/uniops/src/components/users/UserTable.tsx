import { useState } from 'react';
import { MoreHorizontal, Shield, Mail, Trash2, UserCheck, Ban } from 'lucide-react';
import { clsx } from 'clsx';
import { UserAvatar } from './UserAvatar';
import { UserRoleBadge } from './UserRoleBadge';
import { formatRelative } from '@/lib/formatters';
import type { User } from '@/types/user';

interface UserTableProps {
  users: User[];
  isLoading?: boolean;
  onChangeRole?: (user: User) => void;
  onResendInvite?: (user: User) => void;
  onSuspend?: (user: User) => void;
  onRemove?: (user: User) => void;
  onViewDetails?: (user: User) => void;
}

const statusConfig: Record<User['status'], { label: string; color: string }> = {
  active: { label: 'Active', color: 'text-green-400' },
  inactive: { label: 'Inactive', color: 'text-muted-foreground' },
  pending: { label: 'Pending', color: 'text-yellow-400' },
  suspended: { label: 'Suspended', color: 'text-red-400' },
};

export function UserTable({ users, isLoading, onChangeRole, onResendInvite, onSuspend, onRemove, onViewDetails }: UserTableProps) {
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-8 h-8 rounded-full border-2 border-blue-500/20 border-t-blue-500 animate-spin" />
      </div>
    );
  }

  if (!users.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-2">
        <p className="text-sm text-muted-foreground">No users found</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Role</th>
            <th>Status</th>
            <th>2FA</th>
            <th>Last Login</th>
            <th>Joined</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id} className="cursor-pointer" onClick={() => onViewDetails?.(user)}>
              <td>
                <div className="flex items-center gap-3">
                  <UserAvatar name={user.displayName} avatar={user.avatar} size="sm" />
                  <div>
                    <div className="text-sm font-medium text-foreground">{user.displayName}</div>
                    <div className="text-xs text-muted-foreground">{user.email}</div>
                  </div>
                </div>
              </td>
              <td onClick={(e) => e.stopPropagation()}>
                <UserRoleBadge role={user.role} />
              </td>
              <td>
                <span className={clsx('text-xs font-medium capitalize', statusConfig[user.status].color)}>
                  {statusConfig[user.status].label}
                </span>
              </td>
              <td>
                <span className={clsx('text-xs', user.twoFactorEnabled ? 'text-green-400' : 'text-muted-foreground')}>
                  {user.twoFactorEnabled ? '✓ On' : '✗ Off'}
                </span>
              </td>
              <td>
                <span className="text-xs text-muted-foreground">
                  {user.lastLogin ? formatRelative(user.lastLogin) : 'Never'}
                </span>
              </td>
              <td>
                <span className="text-xs text-muted-foreground">{formatRelative(user.createdAt)}</span>
              </td>
              <td onClick={(e) => e.stopPropagation()}>
                <div className="relative">
                  <button
                    onClick={() => setOpenMenu(openMenu === user.id ? null : user.id)}
                    className="p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </button>
                  {openMenu === user.id && (
                    <div className="absolute right-0 top-8 z-50 w-48 rounded-lg border shadow-xl overflow-hidden"
                      style={{ background: 'hsl(230 18% 10%)', borderColor: 'hsl(230 15% 14%)' }}>
                      {[
                        { icon: Shield, label: 'Change role', action: () => { onChangeRole?.(user); setOpenMenu(null); } },
                        { icon: UserCheck, label: 'View details', action: () => { onViewDetails?.(user); setOpenMenu(null); } },
                        { icon: Mail, label: 'Resend invite', action: () => { onResendInvite?.(user); setOpenMenu(null); } },
                        { icon: Ban, label: 'Suspend', action: () => { onSuspend?.(user); setOpenMenu(null); }, danger: true },
                        { icon: Trash2, label: 'Remove', action: () => { onRemove?.(user); setOpenMenu(null); }, danger: true },
                      ].map((item) => (
                        <button
                          key={item.label}
                          onClick={item.action}
                          className={clsx('w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-accent',
                            item.danger ? 'text-red-400' : 'text-foreground')}
                        >
                          <item.icon className="w-3.5 h-3.5" />
                          {item.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
