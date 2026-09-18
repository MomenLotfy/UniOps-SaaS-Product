import { useCallback, useEffect, useState } from 'react';
import { Mail, Clock, X, Plus, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import apiClient from '@/services/api/client';

interface Invite {
  id: string; email: string; role: string; invited_by: string;
  status: 'pending'; created_at: string;
}

interface APIResponse<T> { success: boolean; data: T; message: string }

/** Canonical role contract — mirrors backend app/constants/roles.py. */
const ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: 'viewer',            label: 'Viewer' },
  { value: 'admin',             label: 'Admin' },
  { value: 'devops_engineer',   label: 'DevOps Engineer' },
  { value: 'security_engineer', label: 'Security Engineer' },
  { value: 'cost_analyst',      label: 'Cost Analyst' },
];

const ROLE_COLORS: Record<string, string> = {
  devops_engineer:   'text-blue-400 bg-blue-400/10 border-blue-400/20',
  security_engineer: 'text-red-400 bg-red-400/10 border-red-400/20',
  cost_analyst:      'text-purple-400 bg-purple-400/10 border-purple-400/20',
  viewer:            'text-muted-foreground bg-border/30 border-border',
  admin:             'text-orange-400 bg-orange-400/10 border-orange-400/20',
};

function roleBadge(role: string) { return ROLE_COLORS[role] ?? ROLE_COLORS.viewer; }

function roleLabel(role: string) {
  return ROLE_OPTIONS.find((r) => r.value === role)?.label ?? role;
}

export default function PendingInvitations() {
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState('viewer');
  const [sending, setSending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<APIResponse<Invite[]>>('/users/invitations');
      setInvites(data.data ?? []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load invitations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const sendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim() || !newName.trim()) return;
    setSending(true);
    setFormError(null);
    try {
      await apiClient.post('/users/invite', {
        email: newEmail.trim(),
        role: newRole,
        full_name: newName.trim(),
      });
      setShowNew(false);
      setNewEmail('');
      setNewName('');
      setNewRole('viewer');
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setFormError(typeof detail === 'string' ? detail : (err?.message || 'Failed to send invitation'));
    } finally {
      setSending(false);
    }
  };

  const revoke = async (id: string) => {
    setRevokingId(id);
    try {
      await apiClient.delete(`/users/invitations/${id}`);
      setInvites((prev) => prev.filter((i) => i.id !== id));
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to revoke invitation');
    } finally {
      setRevokingId(null);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Pending Invitations</h1>
          <p className="page-subtitle">Manage outstanding team invites and send new ones.</p>
        </div>
        <button onClick={() => setShowNew(true)} className="action-btn action-btn-primary"><Plus className="w-4 h-4" /> Invite Member</button>
      </div>

      {/* New invite form */}
      {showNew && (
        <form onSubmit={sendInvite} className="card-base rounded-xl p-5 border border-primary/30 space-y-4">
          <h3 className="text-sm font-semibold text-foreground">Send Invitation</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Full Name</label>
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Jane Doe" required
                className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Email Address</label>
              <input value={newEmail} onChange={(e) => setNewEmail(e.target.value)} type="email" placeholder="colleague@company.com" required
                className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Role</label>
              <select value={newRole} onChange={(e) => setNewRole(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50">
                {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
          </div>
          {formError && <p className="text-xs text-red-400">{formError}</p>}
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => { setShowNew(false); setFormError(null); }} className="action-btn">Cancel</button>
            <button type="submit" disabled={!newEmail || !newName || sending} className="action-btn action-btn-primary disabled:opacity-40">
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />} Send Invite
            </button>
          </div>
        </form>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 max-w-md">
        <div className="card-base rounded-xl p-4 border border-border text-center">
          <div className="text-2xl font-bold" style={{ color: 'hsl(220 90% 60%)' }}>{invites.length}</div>
          <div className="text-xs text-muted-foreground">Pending</div>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading invitations…
        </div>
      )}

      {!loading && error && (
        <div className="card-base rounded-xl p-4 border border-red-500/30 text-sm text-red-400">{error}</div>
      )}

      {!loading && !error && invites.length === 0 && (
        <div className="card-base rounded-xl p-10 border border-border text-center space-y-2">
          <Mail className="w-8 h-8 text-muted-foreground mx-auto" />
          <p className="text-sm text-foreground font-medium">No pending invitations</p>
          <p className="text-xs text-muted-foreground">Invitations you send will appear here until accepted or expired (48h).</p>
        </div>
      )}

      {/* Pending invites */}
      {!loading && invites.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Active Invites</div>
          <div className="space-y-2">
            {invites.map((invite) => (
              <div key={invite.id} className="card-base rounded-xl p-4 border border-border flex items-center gap-4">
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: 'hsl(220 90% 60% / 0.15)' }}>
                  <Mail className="w-4 h-4 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground">{invite.email}</div>
                  <div className="text-xs text-muted-foreground">Invited {invite.invited_by ? `by ${invite.invited_by} · ` : ''}expires 48h after sending</div>
                </div>
                <span className={clsx('text-xs px-2 py-0.5 rounded-full border', roleBadge(invite.role))}>{roleLabel(invite.role)}</span>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="w-3.5 h-3.5" /> Pending
                </div>
                <div className="flex gap-1.5">
                  <button onClick={() => revoke(invite.id)} disabled={revokingId === invite.id}
                    className="action-btn text-red-400 hover:bg-red-500/10 disabled:opacity-40">
                    {revokingId === invite.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
