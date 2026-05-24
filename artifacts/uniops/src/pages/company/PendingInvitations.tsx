import { useState } from 'react';
import { Mail, Clock, Check, X, RefreshCw, Plus } from 'lucide-react';
import { clsx } from 'clsx';

interface Invite {
  id: string; email: string; role: string; invitedBy: string;
  sentAt: string; expiresAt: string; status: 'pending' | 'expired';
}

const INVITES: Invite[] = [
  { id: '1', email: 'newengineer@company.com', role: 'devops',   invitedBy: 'Alice Johnson', sentAt: '2 days ago', expiresAt: '5 days',  status: 'pending' },
  { id: '2', email: 'analyst@company.com',     role: 'security', invitedBy: 'Eve Martinez',  sentAt: '4 days ago', expiresAt: '3 days',  status: 'pending' },
  { id: '3', email: 'olduser@company.com',     role: 'viewer',   invitedBy: 'Bob Smith',     sentAt: '12 days ago', expiresAt: 'Expired', status: 'expired' },
  { id: '4', email: 'financeuser@company.com', role: 'finops',   invitedBy: 'Grace Park',    sentAt: '1 day ago',  expiresAt: '6 days',  status: 'pending' },
];

const ROLE_COLORS: Record<string, string> = {
  devops:   'text-blue-400 bg-blue-400/10 border-blue-400/20',
  security: 'text-red-400 bg-red-400/10 border-red-400/20',
  finops:   'text-purple-400 bg-purple-400/10 border-purple-400/20',
  viewer:   'text-muted-foreground bg-border/30 border-border',
  admin:    'text-orange-400 bg-orange-400/10 border-orange-400/20',
};

export default function PendingInvitations() {
  const [invites, setInvites] = useState(INVITES);
  const [showNew, setShowNew] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState('viewer');

  const revoke = (id: string) => setInvites((prev) => prev.filter((i) => i.id !== id));
  const resend = (id: string) => { /* toast */ };

  const pending = invites.filter((i) => i.status === 'pending');
  const expired = invites.filter((i) => i.status === 'expired');

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
        <div className="card-base rounded-xl p-5 border border-primary/30 space-y-4">
          <h3 className="text-sm font-semibold text-foreground">Send Invitation</h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2">
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Email Address</label>
              <input value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="colleague@company.com"
                className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Role</label>
              <select value={newRole} onChange={(e) => setNewRole(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50">
                {['viewer', 'devops', 'security', 'finops', 'admin'].map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-3 justify-end">
            <button onClick={() => setShowNew(false)} className="action-btn">Cancel</button>
            <button disabled={!newEmail} className="action-btn action-btn-primary disabled:opacity-40"><Mail className="w-4 h-4" /> Send Invite</button>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Pending', value: pending.length, color: 'hsl(220 90% 60%)' },
          { label: 'Expired', value: expired.length, color: 'hsl(0 80% 60%)' },
          { label: 'Sent This Month', value: 7, color: 'hsl(140 60% 45%)' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card-base rounded-xl p-4 border border-border text-center">
            <div className="text-2xl font-bold" style={{ color }}>{value}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        ))}
      </div>

      {/* Pending invites */}
      {pending.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Active Invites</div>
          <div className="space-y-2">
            {pending.map((invite) => (
              <div key={invite.id} className="card-base rounded-xl p-4 border border-border flex items-center gap-4">
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: 'hsl(220 90% 60% / 0.15)' }}>
                  <Mail className="w-4 h-4 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground">{invite.email}</div>
                  <div className="text-xs text-muted-foreground">Invited by {invite.invitedBy} · {invite.sentAt}</div>
                </div>
                <span className={clsx('text-xs px-2 py-0.5 rounded-full border', ROLE_COLORS[invite.role])}>{invite.role}</span>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="w-3.5 h-3.5" /> Expires in {invite.expiresAt}
                </div>
                <div className="flex gap-1.5">
                  <button onClick={() => resend(invite.id)} className="action-btn"><RefreshCw className="w-3.5 h-3.5" /> Resend</button>
                  <button onClick={() => revoke(invite.id)} className="action-btn text-red-400 hover:bg-red-500/10"><X className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Expired */}
      {expired.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Expired Invites</div>
          <div className="space-y-2">
            {expired.map((invite) => (
              <div key={invite.id} className="card-base rounded-xl p-4 border border-border flex items-center gap-4 opacity-60">
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-border/30">
                  <Mail className="w-4 h-4 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground">{invite.email}</div>
                  <div className="text-xs text-muted-foreground">Invited by {invite.invitedBy} · {invite.sentAt}</div>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full border border-border text-muted-foreground">{invite.role}</span>
                <span className="text-xs text-red-400">Expired</span>
                <button onClick={() => revoke(invite.id)} className="action-btn"><X className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
