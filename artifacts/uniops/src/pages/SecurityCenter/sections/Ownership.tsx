import { useState } from 'react';
import { Users, Search, Filter, Edit3, Check, X, ChevronDown, Building2, User, GitBranch, Server, AlertTriangle, Bug } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const ENTITY_ICONS: Record<string, React.ReactNode> = {
  threat:        <AlertTriangle className="w-3.5 h-3.5 text-red-400" />,
  vulnerability: <Bug className="w-3.5 h-3.5 text-orange-400" />,
  repository:    <GitBranch className="w-3.5 h-3.5 text-blue-400" />,
  asset:         <Server className="w-3.5 h-3.5 text-purple-400" />,
};

const ENTITY_COLORS: Record<string, string> = {
  threat:        'text-red-400 bg-red-400/10 border-red-400/20',
  vulnerability: 'text-orange-400 bg-orange-400/10 border-orange-400/20',
  repository:    'text-blue-400 bg-blue-400/10 border-blue-400/20',
  asset:         'text-purple-400 bg-purple-400/10 border-purple-400/20',
};

const SEV_COLOR: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-green-400',
};

interface OwnershipEntry {
  entity_type: string;
  entity_id:   string;
  title?:      string;
  severity?:   string;
  status?:     string;
  cve_id?:     string;
  provider?:   string;
  type?:       string;
  risk_level?: string;
  owner?:      string | null;
  team?:       string | null;
  department?: string | null;
}

interface EditState {
  entity_type: string;
  entity_id:   string;
  owner:       string;
  team:        string;
  department:  string;
}

export default function Ownership() {
  const [entityType, setEntityType]   = useState<string>('');
  const [search, setSearch]           = useState('');
  const [editing, setEditing]         = useState<EditState | null>(null);
  const [saving, setSaving]           = useState(false);

  const params = new URLSearchParams();
  if (entityType) params.set('entity_type', entityType);

  const { data: raw, loading, refetch } = useApi<any>(`/ownership?${params}&limit=200`);
  const rows: OwnershipEntry[] = Array.isArray(raw?.data ?? raw) ? (raw?.data ?? raw) : [];

  const filtered = rows.filter(r => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (r.title        || '').toLowerCase().includes(q) ||
      (r.owner        || '').toLowerCase().includes(q) ||
      (r.team         || '').toLowerCase().includes(q) ||
      (r.department   || '').toLowerCase().includes(q) ||
      (r.cve_id       || '').toLowerCase().includes(q)
    );
  });

  const startEdit = (row: OwnershipEntry) =>
    setEditing({
      entity_type: row.entity_type,
      entity_id:   row.entity_id,
      owner:       row.owner || '',
      team:        row.team  || '',
      department:  row.department || '',
    });

  const saveEdit = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await apiClient.patch(`/ownership/${editing.entity_type}/${editing.entity_id}`, {
        owner:      editing.owner      || null,
        team:       editing.team       || null,
        department: editing.department || null,
      });
      await refetch();
      setEditing(null);
    } finally { setSaving(false); }
  };

  // Summaries
  const withOwner      = rows.filter(r => r.owner).length;
  const withTeam       = rows.filter(r => r.team).length;
  const withDept       = rows.filter(r => r.department).length;
  const unowned        = rows.filter(r => !r.owner && !r.team).length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Ownership Management</h1>
          <p className="text-xs text-muted-foreground">
            Assign owners, teams, and departments to repositories, assets, threats, and vulnerabilities
          </p>
        </div>
      </div>

      {/* Summary cards */}
      {!loading && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: 'With Owner',  value: withOwner,  color: 'text-green-400',  icon: <User className="w-3.5 h-3.5" /> },
            { label: 'With Team',   value: withTeam,   color: 'text-blue-400',   icon: <Users className="w-3.5 h-3.5" /> },
            { label: 'With Dept',   value: withDept,   color: 'text-purple-400', icon: <Building2 className="w-3.5 h-3.5" /> },
            { label: 'Unowned',     value: unowned,    color: 'text-red-400',    icon: <X className="w-3.5 h-3.5" /> },
          ].map(({ label, value, color, icon }) => (
            <div key={label} className="card-base p-4 flex items-center gap-3">
              <span className={clsx('w-8 h-8 rounded-lg flex items-center justify-center bg-white/5', color)}>{icon}</span>
              <div>
                <p className={clsx('text-xl font-bold', color)}>{value}</p>
                <p className="text-[10px] text-muted-foreground">{label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-white/5 border border-white/10 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/50"
            placeholder="Search by title, owner, team, CVE…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex rounded-lg border border-white/10 overflow-hidden">
          {[
            { v: '',              label: 'All' },
            { v: 'threat',        label: 'Threats' },
            { v: 'vulnerability', label: 'Vulns' },
            { v: 'repository',    label: 'Repos' },
            { v: 'asset',         label: 'Assets' },
          ].map(({ v, label }) => (
            <button key={v} onClick={() => setEntityType(v)}
              className={clsx('px-3 py-1.5 text-[11px] font-medium transition-colors',
                entityType === v ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card-base py-14 text-center">
          <Users className="w-8 h-8 text-muted-foreground opacity-30 mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No entities found.</p>
        </div>
      ) : (
        <div className="card-base overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
                {['Type', 'Entity', 'Severity / Risk', 'Owner', 'Team', 'Department', ''].map(h => (
                  <th key={h} className="px-3 py-2.5 text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: 'hsl(230 15% 12%)' }}>
              {filtered.map(row => {
                const isEditing = editing?.entity_id === row.entity_id && editing?.entity_type === row.entity_type;
                return (
                  <tr key={`${row.entity_type}-${row.entity_id}`}
                    className="hover:bg-white/[0.02] transition-colors">
                    {/* Type */}
                    <td className="px-3 py-2.5">
                      <span className={clsx('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border', ENTITY_COLORS[row.entity_type])}>
                        {ENTITY_ICONS[row.entity_type]}
                        {row.entity_type}
                      </span>
                    </td>
                    {/* Entity */}
                    <td className="px-3 py-2.5 max-w-[220px]">
                      <p className="truncate text-foreground font-medium">{row.title || row.entity_id}</p>
                      {row.cve_id && <p className="text-[10px] text-muted-foreground">{row.cve_id}</p>}
                      {row.provider && <p className="text-[10px] text-muted-foreground">{row.provider}</p>}
                    </td>
                    {/* Severity */}
                    <td className="px-3 py-2.5">
                      {row.severity && (
                        <span className={clsx('capitalize text-[11px] font-medium', SEV_COLOR[row.severity])}>{row.severity}</span>
                      )}
                      {row.risk_level && !row.severity && (
                        <span className={clsx('capitalize text-[11px] font-medium', SEV_COLOR[row.risk_level])}>{row.risk_level}</span>
                      )}
                    </td>
                    {/* Owner / Team / Department — inline edit */}
                    {isEditing ? (
                      <>
                        <td className="px-2 py-1.5">
                          <input className="w-full px-2 py-1 text-xs rounded bg-white/10 border border-white/20 text-foreground focus:outline-none focus:border-blue-500/50"
                            placeholder="owner@company.com"
                            value={editing.owner}
                            onChange={e => setEditing(p => p ? { ...p, owner: e.target.value } : p)} />
                        </td>
                        <td className="px-2 py-1.5">
                          <input className="w-full px-2 py-1 text-xs rounded bg-white/10 border border-white/20 text-foreground focus:outline-none focus:border-blue-500/50"
                            placeholder="Security"
                            value={editing.team}
                            onChange={e => setEditing(p => p ? { ...p, team: e.target.value } : p)} />
                        </td>
                        <td className="px-2 py-1.5">
                          <input className="w-full px-2 py-1 text-xs rounded bg-white/10 border border-white/20 text-foreground focus:outline-none focus:border-blue-500/50"
                            placeholder="Engineering"
                            value={editing.department}
                            onChange={e => setEditing(p => p ? { ...p, department: e.target.value } : p)} />
                        </td>
                        <td className="px-2 py-1.5">
                          <div className="flex gap-1">
                            <button onClick={saveEdit} disabled={saving}
                              className="p-1 rounded bg-green-600/20 text-green-400 hover:bg-green-600/30 disabled:opacity-50">
                              <Check className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => setEditing(null)}
                              className="p-1 rounded bg-white/5 text-muted-foreground hover:text-foreground">
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-3 py-2.5">
                          {row.owner
                            ? <span className="flex items-center gap-1"><User className="w-3 h-3 text-muted-foreground" />{row.owner}</span>
                            : <span className="text-muted-foreground/40 italic">unassigned</span>}
                        </td>
                        <td className="px-3 py-2.5">
                          {row.team
                            ? <span className="flex items-center gap-1"><Users className="w-3 h-3 text-muted-foreground" />{row.team}</span>
                            : <span className="text-muted-foreground/40 italic">—</span>}
                        </td>
                        <td className="px-3 py-2.5">
                          {row.department
                            ? <span className="flex items-center gap-1"><Building2 className="w-3 h-3 text-muted-foreground" />{row.department}</span>
                            : <span className="text-muted-foreground/40 italic">—</span>}
                        </td>
                        <td className="px-3 py-2.5">
                          <button onClick={() => startEdit(row)}
                            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors">
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
