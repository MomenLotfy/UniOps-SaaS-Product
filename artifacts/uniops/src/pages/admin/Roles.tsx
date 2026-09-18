import { useEffect, useMemo, useState } from 'react';
import { Shield, Lock, Check, Eye, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { ROLE_PERMISSIONS, LEGACY_ROLE_ALIASES, normalizeRole } from '@/lib/permissions';
import type { UserRole } from '@/types/user';
import apiClient from '@/services/api/client';

interface Permission { id: string; label: string; category: string }
interface RoleDef { name: UserRole; label: string; description: string; color: string }

/* Real permission matrix — derived from ROLE_PERMISSIONS (the same map that
 * actually gates the UI) instead of a hand-written fake list. */
const ACTION_ORDER = ['read', 'write', 'delete', 'admin'] as const;

const PERMISSIONS: Permission[] = (() => {
  const seen = new Set<string>();
  const out: Permission[] = [];
  const ROLE_LABEL: Record<string, string> = {
    devops: 'DevOps', security: 'Security', cost: 'FinOps', users: 'Users',
    audit: 'Audit', billing: 'Billing', api: 'API', integrations: 'Integrations',
    pipelines: 'DevOps', pods: 'DevOps', deployments: 'DevOps',
  };
  for (const perms of Object.values(ROLE_PERMISSIONS)) {
    for (const p of perms) {
      for (const a of p.actions as string[]) {
        const id = `${p.resource}.${a}`;
        if (seen.has(id)) continue;
        seen.add(id);
        const cat = ROLE_LABEL[p.resource] ?? (p.resource.charAt(0).toUpperCase() + p.resource.slice(1));
        out.push({
          id,
          label: `${a.charAt(0).toUpperCase() + a.slice(1)} ${p.resource.replace(/_/g, ' ')}`,
          category: cat,
        });
      }
    }
  }
  const order = { Users: 0, DevOps: 1, Security: 2, FinOps: 3, Audit: 4, Integrations: 5, Billing: 6, API: 7 };
  return out.sort((a, b) => ((order as any)[a.category] ?? 99) - ((order as any)[b.category] ?? 99) || ACTION_ORDER.indexOf(a.id.split('.')[1] as any) - ACTION_ORDER.indexOf(b.id.split('.')[1] as any));
})();

function rolePermissions(role: UserRole): string[] {
  const perms = ROLE_PERMISSIONS[role] ?? [];
  const out: string[] = [];
  for (const p of perms) {
    if (p.resource === '*') return PERMISSIONS.map((x) => x.id); // wildcard
    for (const a of p.actions as string[]) out.push(`${p.resource}.${a}`);
  }
  return out;
}

const ROLES: RoleDef[] = [
  { name: 'super_admin',       label: 'Super Admin',       description: 'Full unrestricted access to all resources and settings.',            color: 'hsl(0 80% 60%)' },
  { name: 'admin',             label: 'Admin',             description: 'Manages users, teams, and platform configuration.',                  color: 'hsl(25 80% 55%)' },
  { name: 'devops_engineer',   label: 'DevOps Engineer',   description: 'Manages pipelines, deployments, and infrastructure.',                color: 'hsl(220 80% 60%)' },
  { name: 'security_engineer', label: 'Security Engineer', description: 'Monitors threats, reviews alerts, and manages security operations.', color: 'hsl(140 60% 45%)' },
  { name: 'cost_analyst',      label: 'Cost Analyst',      description: 'Manages cloud cost optimization and budget planning.',               color: 'hsl(270 70% 60%)' },
  { name: 'viewer',            label: 'Viewer',            description: 'Read-only access to dashboards and metrics.',                        color: 'hsl(215 16% 50%)' },
];

interface UserRow { id: string; role: string; tenant_id: string }

export default function Roles() {
  const [selected, setSelected] = useState<RoleDef>(ROLES[0]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [countsLoading, setCountsLoading] = useState(true);

  /* Real member counts from the users endpoint — never fabricated. */
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await apiClient.get<{ success: boolean; data: UserRow[] }>('/users/');
        if (!alive) return;
        const tally: Record<string, number> = {};
        for (const u of data.data ?? []) {
          // legacy names are normalized so old rows group into canonical roles
          const r = LEGACY_ROLE_ALIASES[u.role]?.toString() ?? normalizeRole(u.role);
          tally[r] = (tally[r] ?? 0) + 1;
        }
        setCounts(tally);
      } catch {
        /* counts unavailable — leave empty rather than fake them */
      } finally {
        if (alive) setCountsLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const selectedPerms = useMemo(() => rolePermissions(selected.name), [selected]);
  const permCategories = [...new Set(PERMISSIONS.map((p) => p.category))];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Roles & Permissions</h1>
          <p className="page-subtitle">System roles and their effective capabilities. Role changes are made per user in Team Settings.</p>
        </div>
        <span className="text-xs text-muted-foreground flex items-center gap-1.5"><Lock className="w-3.5 h-3.5" /> System-defined — read-only</span>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Roles list */}
        <div className="col-span-4 space-y-2">
          {ROLES.map((role) => (
            <button key={role.name} onClick={() => setSelected(role)}
              className={clsx('w-full text-left rounded-xl p-4 border transition-all', selected.name === role.name ? 'border-primary/50 bg-primary/5' : 'border-border card-base hover:border-primary/30')}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: `${role.color}22` }}>
                  <Shield className="w-4 h-4" style={{ color: role.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-semibold text-foreground truncate">{role.label}</span>
                    <Lock className="w-3 h-3 text-muted-foreground" />
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {countsLoading ? '…' : `${counts[role.name] ?? 0} members`}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Permission viewer */}
        <div className="col-span-8 card-base rounded-xl p-6 space-y-5">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-foreground text-sm">{selected.label}</h3>
              <p className="text-xs text-muted-foreground mt-0.5">{selected.description}</p>
            </div>
            <span className="text-xs text-muted-foreground flex items-center gap-1"><Lock className="w-3 h-3" /> System role</span>
          </div>

          <div className="space-y-4">
            {permCategories.map((cat) => {
              const catPerms = PERMISSIONS.filter((p) => p.category === cat);
              return (
                <div key={cat}>
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">{cat}</div>
                  <div className="grid grid-cols-2 gap-2">
                    {catPerms.map((perm) => {
                      const has = selectedPerms.includes(perm.id);
                      return (
                        <div key={perm.id}
                          className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all text-left',
                            has ? 'border-primary/40 bg-primary/5 text-foreground' : 'border-border text-muted-foreground opacity-70')}>
                          <div className={clsx('w-4 h-4 rounded flex items-center justify-center border flex-shrink-0', has ? 'border-primary bg-primary' : 'border-border')}>
                            {has && <Check className="w-2.5 h-2.5 text-white" />}
                          </div>
                          {perm.label}
                          {has && <Eye className="w-3 h-3 ml-auto text-muted-foreground" />}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
