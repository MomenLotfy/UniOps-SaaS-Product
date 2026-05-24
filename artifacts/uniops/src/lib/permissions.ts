import type { UserRole, Permission } from '@/types/user';

type Action = 'read' | 'write' | 'delete' | 'admin';

const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  super_admin: [{ resource: '*', actions: ['read', 'write', 'delete', 'admin'] }],
  admin: [
    { resource: 'users', actions: ['read', 'write', 'delete', 'admin'] },
    { resource: 'integrations', actions: ['read', 'write', 'delete', 'admin'] },
    { resource: 'billing', actions: ['read', 'write', 'admin'] },
    { resource: 'audit', actions: ['read'] },
    { resource: 'dashboard', actions: ['read', 'write'] },
  ],
  devops: [
    { resource: 'dashboard', actions: ['read', 'write'] },
    { resource: 'pipelines', actions: ['read', 'write'] },
    { resource: 'kubernetes', actions: ['read', 'write'] },
    { resource: 'integrations', actions: ['read'] },
  ],
  security: [
    { resource: 'dashboard', actions: ['read'] },
    { resource: 'threats', actions: ['read', 'write'] },
    { resource: 'vulnerabilities', actions: ['read', 'write'] },
    { resource: 'compliance', actions: ['read', 'write'] },
    { resource: 'audit', actions: ['read'] },
    { resource: 'users', actions: ['read'] },
  ],
  finops: [
    { resource: 'dashboard', actions: ['read'] },
    { resource: 'costs', actions: ['read', 'write'] },
    { resource: 'billing', actions: ['read'] },
    { resource: 'savings', actions: ['read', 'write'] },
  ],
  viewer: [
    { resource: 'dashboard', actions: ['read'] },
  ],
};

export function can(role: UserRole, resource: string, action: Action): boolean {
  const perms = ROLE_PERMISSIONS[role] ?? [];
  for (const perm of perms) {
    if ((perm.resource === '*' || perm.resource === resource) && perm.actions.includes(action)) {
      return true;
    }
  }
  return false;
}

export function getRolePermissions(role: UserRole): Permission[] {
  return ROLE_PERMISSIONS[role] ?? [];
}

export const ADMIN_ROLES: UserRole[] = ['super_admin', 'admin'];
export const DEVOPS_ROLES: UserRole[] = ['super_admin', 'admin', 'devops'];
export const SECURITY_ROLES: UserRole[] = ['super_admin', 'admin', 'security'];
export const FINOPS_ROLES: UserRole[] = ['super_admin', 'admin', 'finops'];

export function isAdmin(role: UserRole): boolean {
  return ADMIN_ROLES.includes(role);
}
