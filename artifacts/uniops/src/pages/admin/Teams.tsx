import { useState } from 'react';
import { Users, Plus, Search, MoreHorizontal, Mail, Crown, UserMinus } from 'lucide-react';
import { clsx } from 'clsx';
import { initials } from '@/lib/formatters';

interface Member { id: string; name: string; email: string; role: string; avatar?: string; }
interface Team { id: string; name: string; description: string; color: string; lead: string; memberCount: number; members: Member[]; }

const TEAMS: Team[] = [
  {
    id: '1', name: 'Platform Engineering', description: 'Owns infrastructure, CI/CD, and internal tooling.', color: 'hsl(220 90% 60%)', lead: 'Alice Johnson', memberCount: 6,
    members: [
      { id: 'a1', name: 'Alice Johnson',   email: 'alice@uniops.dev',   role: 'Lead' },
      { id: 'a2', name: 'Bob Smith',       email: 'bob@uniops.dev',     role: 'Engineer' },
      { id: 'a3', name: 'Carol Williams',  email: 'carol@uniops.dev',   role: 'Engineer' },
      { id: 'a4', name: 'David Lee',       email: 'david@uniops.dev',   role: 'Engineer' },
    ],
  },
  {
    id: '2', name: 'Security Operations', description: 'Monitors threats, manages compliance, and responds to incidents.', color: 'hsl(0 80% 60%)', lead: 'Eve Martinez', memberCount: 4,
    members: [
      { id: 'b1', name: 'Eve Martinez',    email: 'eve@uniops.dev',     role: 'Lead' },
      { id: 'b2', name: 'Frank Chen',      email: 'frank@uniops.dev',   role: 'Analyst' },
    ],
  },
  {
    id: '3', name: 'FinOps', description: 'Manages cloud spend, budgets, and cost optimization.', color: 'hsl(260 70% 60%)', lead: 'Grace Park', memberCount: 3,
    members: [
      { id: 'c1', name: 'Grace Park',      email: 'grace@uniops.dev',   role: 'Lead' },
      { id: 'c2', name: 'Henry Wilson',    email: 'henry@uniops.dev',   role: 'Analyst' },
    ],
  },
  {
    id: '4', name: 'ML Platform', description: 'Builds and maintains ML infrastructure and model pipelines.', color: 'hsl(140 60% 45%)', lead: 'Iris Thompson', memberCount: 5,
    members: [
      { id: 'd1', name: 'Iris Thompson',   email: 'iris@uniops.dev',    role: 'Lead' },
      { id: 'd2', name: 'Jack Brown',      email: 'jack@uniops.dev',    role: 'Engineer' },
    ],
  },
];

const roleBadge: Record<string, string> = {
  Lead: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  Engineer: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
  Analyst: 'text-purple-400 bg-purple-400/10 border-purple-400/20',
};

export default function Teams() {
  const [selected, setSelected] = useState<Team>(TEAMS[0]);
  const [search, setSearch] = useState('');

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Teams</h1>
          <p className="page-subtitle">Organize members into functional teams with shared access.</p>
        </div>
        <button className="action-btn action-btn-primary"><Plus className="w-4 h-4" /> New Team</button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Team list */}
        <div className="col-span-4 space-y-2">
          {TEAMS.map((team) => (
            <button key={team.id} onClick={() => setSelected(team)}
              className={clsx('w-full text-left rounded-xl p-4 border transition-all', selected.id === team.id ? 'border-primary/50 bg-primary/5' : 'border-border card-base hover:border-primary/30')}>
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 text-white text-xs font-bold" style={{ background: team.color }}>
                  {team.name.slice(0, 2)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-foreground truncate">{team.name}</div>
                  <div className="text-xs text-muted-foreground">{team.memberCount} members · {team.lead}</div>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Team detail */}
        <div className="col-span-8 space-y-4">
          <div className="card-base rounded-xl p-5 border border-border">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl flex items-center justify-center text-white font-bold" style={{ background: selected.color }}>
                  {selected.name.slice(0, 2)}
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">{selected.name}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">{selected.description}</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button className="action-btn"><Mail className="w-4 h-4" /> Email Team</button>
                <button className="action-btn action-btn-primary"><Plus className="w-4 h-4" /> Add Member</button>
              </div>
            </div>

            {/* Search */}
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search members…"
                className="w-full pl-8 pr-3 py-2 text-xs rounded-lg border border-border bg-background/50 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50" />
            </div>

            {/* Members table */}
            <div className="divide-y divide-border">
              {selected.members.filter((m) => m.name.toLowerCase().includes(search.toLowerCase())).map((member) => (
                <div key={member.id} className="flex items-center gap-3 py-3">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                    style={{ background: 'hsl(220 90% 60% / 0.2)', color: 'hsl(220 90% 75%)' }}>
                    {initials(member.name)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-foreground">{member.name}</span>
                      {member.role === 'Lead' && <Crown className="w-3 h-3 text-yellow-400" />}
                    </div>
                    <div className="text-xs text-muted-foreground">{member.email}</div>
                  </div>
                  <span className={clsx('text-xs px-2 py-0.5 rounded-full border', roleBadge[member.role] ?? 'text-muted-foreground border-border')}>
                    {member.role}
                  </span>
                  <button className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-red-400 transition-colors">
                    <UserMinus className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
