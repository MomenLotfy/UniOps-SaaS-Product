import { useEffect, useMemo, useState } from 'react';
import { Users, Search, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { initials } from '@/lib/formatters';
import { normalizeRole } from '@/lib/permissions';
import type { UserRole } from '@/types/user';
import apiClient from '@/services/api/client';

interface Member { id: string; name: string; email: string; role: UserRole; avatar_url?: string }

/** Functional groups are derived from each member's REAL canonical role —
 *  there is no separate "teams" entity in the backend; role grouping is the
 *  truthful representation of team organization in UniOps. */
const ROLE_GROUPS: { id: string; name: string; description: string; color: string; roles: UserRole[] }[] = [
  { id: 'platform', name: 'Platform Engineering', description: 'Owns infrastructure, CI/CD, and internal tooling.',                color: 'hsl(220 90% 60%)', roles: ['devops_engineer', 'developer'] },
  { id: 'security', name: 'Security Operations',  description: 'Monitors threats, manages compliance, and responds to incidents.', color: 'hsl(0 80% 60%)',   roles: ['security_engineer', 'security_analyst', 'compliance_manager', 'auditor'] },
  { id: 'finops',   name: 'FinOps',               description: 'Manages cloud spend, budgets, and cost optimization.',             color: 'hsl(260 70% 60%)', roles: ['cost_analyst'] },
  { id: 'admins',   name: 'Administrators',       description: 'Tenant administration and platform configuration.',                color: 'hsl(25 80% 55%)',  roles: ['super_admin', 'admin'] },
  { id: 'others',   name: 'Viewers & Others',     description: 'Read-only and stakeholder access to dashboards and metrics.',      color: 'hsl(215 16% 50%)', roles: ['viewer', 'executive'] },
];

interface UserRow { id: string; email: string; full_name: string; role: string; avatar_url?: string; is_active?: boolean }

export default function Teams() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string>('platform');
  const [search, setSearch] = useState('');

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await apiClient.get<{ success: boolean; data: any }>('/users/?page_size=200');
        if (!alive) return;
        // GET /users/ is PaginatedResponse — tolerate both shapes
        const rows: UserRow[] = Array.isArray(data.data) ? data.data : (data.data?.items ?? []);
        setMembers(rows.map((u) => ({
          id: u.id, name: u.full_name || u.email, email: u.email,
          role: normalizeRole(u.role), avatar_url: u.avatar_url,
        })));
      } catch (e: any) {
        if (alive) setError(e?.response?.data?.detail || e?.message || 'Failed to load members');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const teams = useMemo(() => {
    const byGroup = new Map<string, Member[]>();
    const grouped = new Set<UserRole>(ROLE_GROUPS.flatMap((g) => g.roles));
    for (const g of ROLE_GROUPS) byGroup.set(g.id, []);
    for (const m of members) {
      const gid = ROLE_GROUPS.find((g) => g.roles.includes(m.role))?.id ?? 'others';
      byGroup.get(gid)!.push(m);
    }
    return ROLE_GROUPS.map((g) => ({ ...g, members: byGroup.get(g.id) ?? [] }))
      .filter((g) => g.members.length > 0 || g.id === selectedId);
  }, [members, selectedId]);

  const selected = teams.find((t) => t.id === selectedId) ?? teams[0];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Teams</h1>
          <p className="page-subtitle">Your organization, grouped by role. Manage membership in Team Settings.</p>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16 text-muted-foreground gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading organization…
        </div>
      )}

      {!loading && error && (
        <div className="card-base rounded-xl p-4 border border-red-500/30 text-sm text-red-400">{error}</div>
      )}

      {!loading && !error && members.length === 0 && (
        <div className="card-base rounded-xl p-10 border border-border text-center space-y-2">
          <Users className="w-8 h-8 text-muted-foreground mx-auto" />
          <p className="text-sm text-foreground font-medium">No members found</p>
          <p className="text-xs text-muted-foreground">Invite team members from Pending Invitations to populate this view.</p>
        </div>
      )}

      {!loading && !error && members.length > 0 && selected && (
        <div className="grid grid-cols-12 gap-6">
          {/* Group list */}
          <div className="col-span-4 space-y-2">
            {teams.map((team) => (
              <button key={team.id} onClick={() => setSelectedId(team.id)}
                className={clsx('w-full text-left rounded-xl p-4 border transition-all', selected.id === team.id ? 'border-primary/50 bg-primary/5' : 'border-border card-base hover:border-primary/30')}>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 text-white text-xs font-bold" style={{ background: team.color }}>
                    {team.name.slice(0, 2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-foreground truncate">{team.name}</div>
                    <div className="text-xs text-muted-foreground">{team.members.length} members</div>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Group detail */}
          <div className="col-span-8 space-y-4">
            <div className="card-base rounded-xl p-5 border border-border">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-11 h-11 rounded-xl flex items-center justify-center text-white font-bold" style={{ background: selected.color }}>
                  {selected.name.slice(0, 2)}
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">{selected.name}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">{selected.description}</p>
                </div>
              </div>

              {/* Search */}
              <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search members…"
                  className="w-full pl-8 pr-3 py-2 text-xs rounded-lg border border-border bg-background/50 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50" />
              </div>

              {/* Members — real users, read-only */}
              <div className="divide-y divide-border">
                {selected.members.filter((m) => (m.name + m.email).toLowerCase().includes(search.toLowerCase())).map((member) => (
                  <div key={member.id} className="flex items-center gap-3 py-3">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                      style={{ background: 'hsl(220 90% 60% / 0.2)', color: 'hsl(220 90% 75%)' }}>
                      {initials(member.name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-foreground">{member.name}</div>
                      <div className="text-xs text-muted-foreground">{member.email}</div>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded-full border border-border text-muted-foreground">
                      {member.role}
                    </span>
                  </div>
                ))}
                {selected.members.length === 0 && (
                  <div className="py-6 text-center text-xs text-muted-foreground">No members in this group yet.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
