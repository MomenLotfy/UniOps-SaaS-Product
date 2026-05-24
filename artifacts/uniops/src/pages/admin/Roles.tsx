import { useState } from 'react';
import { Shield, Plus, Edit, Trash2, Check, Lock, Eye } from 'lucide-react';
import { clsx } from 'clsx';

interface Permission { id: string; label: string; category: string; }
interface Role { id: string; name: string; label: string; description: string; users: number; color: string; permissions: string[]; locked: boolean; }

const PERMISSIONS: Permission[] = [
  { id: 'users.read',    label: 'View Users',       category: 'Users' },
  { id: 'users.write',   label: 'Manage Users',      category: 'Users' },
  { id: 'users.invite',  label: 'Invite Users',      category: 'Users' },
  { id: 'users.delete',  label: 'Delete Users',      category: 'Users' },
  { id: 'audit.read',    label: 'View Audit Logs',   category: 'Audit' },
  { id: 'audit.export',  label: 'Export Audit Logs', category: 'Audit' },
  { id: 'devops.read',   label: 'View Pipelines',    category: 'DevOps' },
  { id: 'devops.write',  label: 'Manage Pipelines',  category: 'DevOps' },
  { id: 'pods.read',     label: 'View Pods',         category: 'DevOps' },
  { id: 'pods.restart',  label: 'Restart Pods',      category: 'DevOps' },
  { id: 'security.read', label: 'View Threats',      category: 'Security' },
  { id: 'security.ack',  label: 'Acknowledge Threats', category: 'Security' },
  { id: 'cost.read',     label: 'View Costs',        category: 'FinOps' },
  { id: 'cost.write',    label: 'Manage Budgets',    category: 'FinOps' },
  { id: 'billing.read',  label: 'View Billing',      category: 'Billing' },
  { id: 'billing.write', label: 'Manage Billing',    category: 'Billing' },
  { id: 'api.read',      label: 'View API Keys',     category: 'API' },
  { id: 'api.write',     label: 'Manage API Keys',   category: 'API' },
  { id: 'integrations.read',  label: 'View Integrations',   category: 'Integrations' },
  { id: 'integrations.write', label: 'Manage Integrations', category: 'Integrations' },
];

const ROLES: Role[] = [
  { id: '1', name: 'super_admin', label: 'Super Admin', description: 'Full unrestricted access to all resources and settings.', users: 1, color: 'hsl(0 80% 60%)', permissions: PERMISSIONS.map((p) => p.id), locked: true },
  { id: '2', name: 'admin', label: 'Admin', description: 'Manages users, teams, and platform configuration.', users: 3, color: 'hsl(25 80% 55%)', permissions: PERMISSIONS.filter((p) => !p.id.startsWith('billing.write')).map((p) => p.id), locked: true },
  { id: '3', name: 'devops', label: 'DevOps Engineer', description: 'Manages pipelines, deployments, and infrastructure.', users: 8, color: 'hsl(220 80% 60%)', permissions: ['devops.read', 'devops.write', 'pods.read', 'pods.restart', 'audit.read'], locked: false },
  { id: '4', name: 'security', label: 'Security Analyst', description: 'Monitors threats, reviews alerts, and audits logs.', users: 4, color: 'hsl(140 60% 45%)', permissions: ['security.read', 'security.ack', 'audit.read', 'audit.export'], locked: false },
  { id: '5', name: 'finops', label: 'FinOps Analyst', description: 'Manages cloud cost optimization and budget planning.', users: 2, color: 'hsl(270 70% 60%)', permissions: ['cost.read', 'cost.write', 'billing.read', 'audit.read'], locked: false },
  { id: '6', name: 'viewer', label: 'Viewer', description: 'Read-only access to dashboards and metrics.', users: 15, color: 'hsl(215 16% 50%)', permissions: ['devops.read', 'pods.read', 'security.read', 'cost.read'], locked: false },
];

const permCategories = [...new Set(PERMISSIONS.map((p) => p.category))];

export default function Roles() {
  const [selected, setSelected] = useState<Role>(ROLES[0]);
  const [roles, setRoles] = useState(ROLES);

  const togglePermission = (permId: string) => {
    if (selected.locked) return;
    setRoles((prev) => prev.map((r) => r.id === selected.id
      ? { ...r, permissions: r.permissions.includes(permId) ? r.permissions.filter((p) => p !== permId) : [...r.permissions, permId] }
      : r));
    setSelected((s) => ({ ...s, permissions: s.permissions.includes(permId) ? s.permissions.filter((p) => p !== permId) : [...s.permissions, permId] }));
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Roles & Permissions</h1>
          <p className="page-subtitle">Define access levels and capabilities for your team members.</p>
        </div>
        <button className="action-btn action-btn-primary"><Plus className="w-4 h-4" /> Create Role</button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Roles list */}
        <div className="col-span-4 space-y-2">
          {roles.map((role) => (
            <button key={role.id} onClick={() => setSelected(role)}
              className={clsx('w-full text-left rounded-xl p-4 border transition-all', selected.id === role.id ? 'border-primary/50 bg-primary/5' : 'border-border card-base hover:border-primary/30')}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: `${role.color}22` }}>
                  <Shield className="w-4 h-4" style={{ color: role.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-semibold text-foreground truncate">{role.label}</span>
                    {role.locked && <Lock className="w-3 h-3 text-muted-foreground" />}
                  </div>
                  <div className="text-xs text-muted-foreground">{role.users} members</div>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Permission editor */}
        <div className="col-span-8 card-base rounded-xl p-6 space-y-5">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-foreground text-sm">{selected.label}</h3>
              <p className="text-xs text-muted-foreground mt-0.5">{selected.description}</p>
            </div>
            {!selected.locked && (
              <div className="flex gap-2">
                <button className="action-btn"><Edit className="w-4 h-4" /></button>
                <button className="action-btn text-red-400 hover:text-red-300"><Trash2 className="w-4 h-4" /></button>
              </div>
            )}
            {selected.locked && (
              <span className="text-xs text-muted-foreground flex items-center gap-1"><Lock className="w-3 h-3" /> System role</span>
            )}
          </div>

          <div className="space-y-4">
            {permCategories.map((cat) => {
              const catPerms = PERMISSIONS.filter((p) => p.category === cat);
              return (
                <div key={cat}>
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">{cat}</div>
                  <div className="grid grid-cols-2 gap-2">
                    {catPerms.map((perm) => {
                      const has = selected.permissions.includes(perm.id);
                      return (
                        <button key={perm.id} onClick={() => togglePermission(perm.id)}
                          disabled={selected.locked}
                          className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all text-left',
                            has ? 'border-primary/40 bg-primary/5 text-foreground' : 'border-border text-muted-foreground',
                            !selected.locked && 'hover:border-primary/60 cursor-pointer',
                            selected.locked && 'cursor-default opacity-80')}>
                          <div className={clsx('w-4 h-4 rounded flex items-center justify-center border flex-shrink-0', has ? 'border-primary bg-primary' : 'border-border')}>
                            {has && <Check className="w-2.5 h-2.5 text-white" />}
                          </div>
                          {perm.label}
                          {selected.locked && has && <Eye className="w-3 h-3 ml-auto text-muted-foreground" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          {!selected.locked && (
            <div className="flex justify-end pt-2 border-t border-border">
              <button className="action-btn action-btn-primary">Save Changes</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
