import { Check, Minus } from 'lucide-react';
import { clsx } from 'clsx';
import { ROLE_LABELS } from '@/lib/constants';
import type { UserRole } from '@/types/user';

const RESOURCES = [
  { id: 'command_center', label: 'Command Center' },
  { id: 'devops', label: 'DevOps Center' },
  { id: 'security', label: 'Security Center' },
  { id: 'cost', label: 'Cost Center' },
  { id: 'ml_insights', label: 'ML Insights' },
  { id: 'users', label: 'User Management' },
  { id: 'roles', label: 'Role Management' },
  { id: 'audit_logs', label: 'Audit Logs' },
  { id: 'integrations', label: 'Integrations' },
  { id: 'billing', label: 'Billing' },
  { id: 'api_keys', label: 'API Keys' },
  { id: 'security_policies', label: 'Security Policies' },
];

type AccessLevel = 'full' | 'read' | 'none';

const MATRIX: Record<UserRole, Record<string, AccessLevel>> = {
  super_admin: { command_center: 'full', devops: 'full', security: 'full', cost: 'full', ml_insights: 'full', users: 'full', roles: 'full', audit_logs: 'full', integrations: 'full', billing: 'full', api_keys: 'full', security_policies: 'full' },
  admin: { command_center: 'full', devops: 'full', security: 'full', cost: 'full', ml_insights: 'full', users: 'full', roles: 'read', audit_logs: 'full', integrations: 'full', billing: 'read', api_keys: 'full', security_policies: 'read' },
  devops: { command_center: 'read', devops: 'full', security: 'read', cost: 'read', ml_insights: 'read', users: 'none', roles: 'none', audit_logs: 'read', integrations: 'read', billing: 'none', api_keys: 'read', security_policies: 'none' },
  security: { command_center: 'read', devops: 'read', security: 'full', cost: 'none', ml_insights: 'read', users: 'read', roles: 'none', audit_logs: 'full', integrations: 'read', billing: 'none', api_keys: 'none', security_policies: 'full' },
  finops: { command_center: 'read', devops: 'none', security: 'none', cost: 'full', ml_insights: 'read', users: 'none', roles: 'none', audit_logs: 'read', integrations: 'read', billing: 'full', api_keys: 'none', security_policies: 'none' },
  viewer: { command_center: 'read', devops: 'read', security: 'read', cost: 'read', ml_insights: 'read', users: 'none', roles: 'none', audit_logs: 'none', integrations: 'none', billing: 'none', api_keys: 'none', security_policies: 'none' },
};

const ROLES_TO_SHOW: UserRole[] = ['super_admin', 'admin', 'devops', 'security', 'finops', 'viewer'];

function AccessIcon({ level }: { level: AccessLevel }) {
  if (level === 'full') return <Check className="w-3.5 h-3.5 text-green-400" />;
  if (level === 'read') return <Minus className="w-3.5 h-3.5 text-blue-400" />;
  return <span className="text-muted-foreground/30 text-xs">—</span>;
}

export function PermissionMatrix() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="text-left py-2 px-3 text-muted-foreground font-medium min-w-[160px]">Resource</th>
            {ROLES_TO_SHOW.map((role) => (
              <th key={role} className="text-center py-2 px-3 text-muted-foreground font-medium min-w-[90px]">
                {ROLE_LABELS[role]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {RESOURCES.map((resource, idx) => (
            <tr key={resource.id} className={clsx(idx % 2 === 0 ? 'bg-accent/20' : '')}>
              <td className="py-2 px-3 text-foreground font-medium">{resource.label}</td>
              {ROLES_TO_SHOW.map((role) => (
                <td key={role} className="py-2 px-3 text-center">
                  <div className="flex justify-center">
                    <AccessIcon level={MATRIX[role][resource.id]} />
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-4 mt-3 px-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5"><Check className="w-3 h-3 text-green-400" /> Full access</div>
        <div className="flex items-center gap-1.5"><Minus className="w-3 h-3 text-blue-400" /> Read only</div>
        <div className="flex items-center gap-1.5"><span className="text-muted-foreground/30">—</span> No access</div>
      </div>
    </div>
  );
}
