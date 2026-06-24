import type { UserRole, Permission } from '@/types/user';

type Action = 'read' | 'write' | 'delete' | 'admin';

const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  super_admin: [{ resource: '*', actions: ['read', 'write', 'delete', 'admin'] }],
  admin: [
    { resource: '*', actions: ['read', 'write', 'delete', 'admin'] },
  ],
  security_engineer: [
    { resource: 'security', actions: ['read', 'write', 'admin'] },
    { resource: 'threats', actions: ['read', 'write', 'delete', 'admin'] },
    { resource: 'vulnerabilities', actions: ['read', 'write', 'admin'] },
    { resource: 'compliance', actions: ['read', 'write'] },
    { resource: 'policies', actions: ['read', 'write', 'delete', 'admin'] },
    { resource: 'exceptions', actions: ['read', 'write', 'admin'] },
    { resource: 'reports', actions: ['read', 'write', 'admin'] },
    { resource: 'posture', actions: ['read', 'write'] },
    { resource: 'assets', actions: ['read', 'write'] },
    { resource: 'repositories', actions: ['read', 'write'] },
    { resource: 'users', actions: ['read'] },
  ],
  security_analyst: [
    { resource: 'security', actions: ['read'] },
    { resource: 'threats', actions: ['read'] },
    { resource: 'vulnerabilities', actions: ['read'] },
    { resource: 'compliance', actions: ['read'] },
    { resource: 'policies', actions: ['read'] },
    { resource: 'exceptions', actions: ['read', 'write'] },
    { resource: 'reports', actions: ['read'] },
    { resource: 'posture', actions: ['read'] },
    { resource: 'assets', actions: ['read'] },
    { resource: 'repositories', actions: ['read'] },
  ],
  devops_engineer: [
    { resource: 'security', actions: ['read'] },
    { resource: 'threats', actions: ['read'] },
    { resource: 'vulnerabilities', actions: ['read'] },
    { resource: 'policies', actions: ['read'] },
    { resource: 'reports', actions: ['read'] },
    { resource: 'repositories', actions: ['read', 'write'] },
    { resource: 'assets', actions: ['read'] },
    { resource: 'pipelines', actions: ['read', 'write'] },
    { resource: 'integrations', actions: ['read'] },
  ],
  compliance_manager: [
    { resource: 'security', actions: ['read'] },
    { resource: 'compliance', actions: ['read', 'write', 'admin'] },
    { resource: 'policies', actions: ['read', 'write', 'admin'] },
    { resource: 'exceptions', actions: ['read', 'write', 'admin'] },
    { resource: 'reports', actions: ['read', 'write', 'admin'] },
    { resource: 'posture', actions: ['read'] },
    { resource: 'threats', actions: ['read'] },
    { resource: 'vulnerabilities', actions: ['read'] },
  ],
  auditor: [
    { resource: 'security', actions: ['read'] },
    { resource: 'threats', actions: ['read'] },
    { resource: 'vulnerabilities', actions: ['read'] },
    { resource: 'compliance', actions: ['read'] },
    { resource: 'policies', actions: ['read'] },
    { resource: 'exceptions', actions: ['read'] },
    { resource: 'reports', actions: ['read'] },
    { resource: 'posture', actions: ['read'] },
    { resource: 'audit', actions: ['read'] },
  ],
  executive: [
    { resource: 'security', actions: ['read'] },
    { resource: 'reports', actions: ['read'] },
    { resource: 'posture', actions: ['read'] },
    { resource: 'compliance', actions: ['read'] },
    { resource: 'costs', actions: ['read'] },
  ],
  cost_analyst: [
    { resource: 'dashboard', actions: ['read'] },
    { resource: 'costs', actions: ['read', 'write'] },
    { resource: 'billing', actions: ['read'] },
    { resource: 'savings', actions: ['read', 'write'] },
  ],
  developer: [
    { resource: 'security', actions: ['read'] },
    { resource: 'repositories', actions: ['read'] },
    { resource: 'pipelines', actions: ['read'] },
  ],
  viewer: [
    { resource: 'security', actions: ['read'] },
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
export const SECURITY_WRITE_ROLES: UserRole[] = ['super_admin', 'admin', 'security_engineer'];
export const SECURITY_READ_ROLES: UserRole[] = [
  'super_admin', 'admin', 'security_engineer', 'security_analyst',
  'devops_engineer', 'compliance_manager', 'auditor', 'executive',
];
export const COMPLIANCE_ROLES: UserRole[] = ['super_admin', 'admin', 'security_engineer', 'compliance_manager'];
export const AUDIT_ROLES: UserRole[] = [
  'super_admin', 'admin', 'security_engineer', 'security_analyst',
  'compliance_manager', 'auditor', 'executive',
];

export function isAdmin(role: UserRole): boolean {
  return ADMIN_ROLES.includes(role);
}

export function canWriteSecurity(role: UserRole): boolean {
  return SECURITY_WRITE_ROLES.includes(role);
}

export function canReadSecurity(role: UserRole): boolean {
  return SECURITY_READ_ROLES.includes(role);
}

export function canManageCompliance(role: UserRole): boolean {
  return COMPLIANCE_ROLES.includes(role);
}

export const ROLE_LABELS: Record<UserRole, string> = {
  super_admin:       'Super Administrator',
  admin:             'Administrator',
  security_engineer: 'Security Engineer',
  security_analyst:  'Security Analyst',
  devops_engineer:   'DevOps Engineer',
  compliance_manager:'Compliance Manager',
  auditor:           'Auditor',
  executive:         'Executive',
  cost_analyst:      'Cost Analyst',
  developer:         'Developer',
  viewer:            'Viewer',
};
