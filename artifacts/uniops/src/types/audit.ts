export type AuditAction =
  | 'user.login' | 'user.logout' | 'user.create' | 'user.update' | 'user.delete' | 'user.invite'
  | 'integration.connect' | 'integration.disconnect' | 'integration.update'
  | 'role.assign' | 'role.revoke'
  | 'policy.create' | 'policy.update' | 'policy.delete'
  | 'api_key.create' | 'api_key.revoke'
  | 'settings.update'
  | 'billing.update';

export interface AuditLog {
  id: string;
  action: AuditAction;
  userId: string;
  userEmail: string;
  userName: string;
  resource: string;
  resourceId?: string;
  changes?: Record<string, { from: unknown; to: unknown }>;
  ip: string;
  userAgent: string;
  location: string;
  status: 'success' | 'failure';
  createdAt: string;
}
