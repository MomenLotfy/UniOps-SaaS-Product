import { clsx } from 'clsx';
import { Shield, Code2, Lock, DollarSign, Eye, Crown } from 'lucide-react';
import { ROLE_LABELS } from '@/lib/constants';
import type { UserRole } from '@/types/user';

interface UserRoleBadgeProps {
  role: UserRole;
  size?: 'sm' | 'md';
  showIcon?: boolean;
}

const ROLE_CONFIG: Record<UserRole, { color: string; bg: string; icon: React.ElementType }> = {
  super_admin: { color: 'text-red-400', bg: 'bg-red-500/10', icon: Crown },
  admin: { color: 'text-orange-400', bg: 'bg-orange-500/10', icon: Shield },
  devops: { color: 'text-blue-400', bg: 'bg-blue-500/10', icon: Code2 },
  security: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: Lock },
  finops: { color: 'text-green-400', bg: 'bg-green-500/10', icon: DollarSign },
  viewer: { color: 'text-slate-400', bg: 'bg-slate-500/10', icon: Eye },
};

export function UserRoleBadge({ role, size = 'sm', showIcon = true }: UserRoleBadgeProps) {
  const config = ROLE_CONFIG[role];
  const Icon = config.icon;

  return (
    <span className={clsx(
      'inline-flex items-center gap-1 rounded-md font-medium',
      config.color, config.bg,
      size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-2.5 py-1'
    )}>
      {showIcon && <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />}
      {ROLE_LABELS[role]}
    </span>
  );
}
