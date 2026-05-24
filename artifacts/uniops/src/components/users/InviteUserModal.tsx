import { useState } from 'react';
import { X, UserPlus, Mail, AlertCircle, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { ROLE_LABELS } from '@/lib/constants';
import type { UserRole } from '@/types/user';

interface InviteUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onInvite: (email: string, role: UserRole, teamId?: string) => Promise<void>;
  teams?: { id: string; name: string }[];
}

export function InviteUserModal({ isOpen, onClose, onInvite, teams = [] }: InviteUserModalProps) {
  const [emails, setEmails] = useState('');
  const [role, setRole] = useState<UserRole>('viewer');
  const [teamId, setTeamId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const emailList = emails.split(/[\n,;]/).map((e) => e.trim()).filter(Boolean);
      for (const email of emailList) {
        await onInvite(email, role, teamId || undefined);
      }
      setSuccess(true);
      setTimeout(() => { setSuccess(false); onClose(); }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send invitations');
    } finally {
      setIsLoading(false);
    }
  };

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-2xl border shadow-2xl"
        style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' }}>
        <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: 'hsl(220 90% 60% / 0.15)' }}>
              <UserPlus className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">Invite Team Members</h2>
              <p className="text-xs text-muted-foreground">Send invitations via email</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
              style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
              <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400"
              style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
              <CheckCircle className="w-4 h-4 flex-shrink-0" />Invitations sent successfully!
            </div>
          )}

          <div>
            <label className="block text-xs font-medium mb-1.5 text-muted-foreground">
              Email addresses <span className="text-muted-foreground/60">(one per line or comma-separated)</span>
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
              <textarea
                required
                rows={3}
                placeholder="john@company.com, jane@company.com"
                value={emails}
                onChange={(e) => setEmails(e.target.value)}
                className={clsx(inputCls, 'pl-9 resize-none')}
                style={inputStyle}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Role</label>
              <select value={role} onChange={(e) => setRole(e.target.value as UserRole)}
                className={inputCls} style={inputStyle}>
                {(Object.keys(ROLE_LABELS) as UserRole[]).filter((r) => r !== 'super_admin').map((r) => (
                  <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                ))}
              </select>
            </div>
            {teams.length > 0 && (
              <div>
                <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Team (optional)</label>
                <select value={teamId} onChange={(e) => setTeamId(e.target.value)}
                  className={inputCls} style={inputStyle}>
                  <option value="">No team</option>
                  {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
            )}
          </div>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors text-muted-foreground hover:text-foreground hover:bg-accent border"
              style={{ borderColor: 'hsl(230 15% 14%)' }}>
              Cancel
            </button>
            <button type="submit" disabled={isLoading || success}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm disabled:opacity-60 disabled:cursor-not-allowed"
              style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
              {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <UserPlus className="w-4 h-4" />}
              Send Invites
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
