import { useAuth } from '@/contexts/AuthContext';
import { can, isAdmin } from '@/lib/permissions';
import type { UserRole } from '@/types/user';

type Action = 'read' | 'write' | 'delete' | 'admin';

export function usePermissions() {
  const { user } = useAuth();

  const role = (user?.role ?? 'viewer') as UserRole;

  return {
    role,
    can: (resource: string, action: Action) => can(role, resource, action),
    isAdmin: () => isAdmin(role),
    isSuperAdmin: () => role === 'super_admin',
    hasRole: (...roles: UserRole[]) => roles.includes(role),
  };
}
