import { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, UserPlus, Mail, CheckCircle, AlertCircle, Send } from 'lucide-react';
import { clsx } from 'clsx';
import { ROLE_LABELS, ROUTES } from '@/lib/constants';
import type { UserRole } from '@/types/user';

interface InviteEntry { email: string; role: UserRole; status: 'pending' | 'sent' | 'error' }

export default function InviteUser() {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<InviteEntry[]>([{ email: '', role: 'viewer', status: 'pending' }]);
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;

  const addRow = () => setEntries((p) => [...p, { email: '', role: 'viewer', status: 'pending' }]);
  const removeRow = (idx: number) => setEntries((p) => p.filter((_, i) => i !== idx));
  const updateRow = (idx: number, field: keyof InviteEntry, value: string) =>
    setEntries((p) => p.map((e, i) => i === idx ? { ...e, [field]: value } : e));

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1200));
    setEntries((p) => p.map((e) => ({ ...e, status: 'sent' as const })));
    setSent(true);
    setIsLoading(false);
    setTimeout(() => navigate(ROUTES.ADMIN_USERS), 2000);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="max-w-2xl space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="action-btn"><ArrowLeft className="w-4 h-4" /> Back</button>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">Invite Team Members</h1>
          <p className="page-subtitle">Send email invitations to join your workspace</p>
        </div>
      </div>

      {sent && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400"
          style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          Invitations sent! Redirecting to users list...
        </div>
      )}

      <form onSubmit={handleSend} className="card-base space-y-4">
        <div className="space-y-2">
          <div className="grid gap-2" style={{ gridTemplateColumns: '1fr 160px 32px' }}>
            <p className="text-xs font-medium text-muted-foreground px-1">Email address</p>
            <p className="text-xs font-medium text-muted-foreground px-1">Role</p>
            <span />
          </div>
          {entries.map((entry, idx) => (
            <div key={idx} className="grid items-center gap-2" style={{ gridTemplateColumns: '1fr 160px 32px' }}>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <input
                  type="email" required placeholder="user@company.com" value={entry.email}
                  onChange={(e) => updateRow(idx, 'email', e.target.value)}
                  className={clsx(inputCls, 'pl-8', entry.status === 'sent' && 'opacity-50')}
                  style={inputStyle} disabled={entry.status === 'sent'} />
                {entry.status === 'sent' && <CheckCircle className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-400" />}
                {entry.status === 'error' && <AlertCircle className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-red-400" />}
              </div>
              <select value={entry.role} onChange={(e) => updateRow(idx, 'role', e.target.value)}
                className={inputCls} style={inputStyle} disabled={entry.status === 'sent'}>
                {(Object.keys(ROLE_LABELS) as UserRole[]).filter((r) => r !== 'super_admin').map((r) => (
                  <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                ))}
              </select>
              <button type="button" onClick={() => removeRow(idx)} disabled={entries.length === 1}
                className="w-8 h-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-30">
                ×
              </button>
            </div>
          ))}
        </div>

        <button type="button" onClick={addRow}
          className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium transition-colors px-1">
          + Add another person
        </button>

        <div>
          <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Personal message (optional)</label>
          <textarea rows={3} placeholder="Add a welcome message to the invitation email..."
            value={message} onChange={(e) => setMessage(e.target.value)}
            className={clsx(inputCls, 'resize-none')} style={inputStyle} />
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button type="button" onClick={() => navigate(-1)}
            className="px-4 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground border transition-colors"
            style={{ borderColor: 'hsl(230 15% 14%)' }}>Cancel</button>
          <button type="submit" disabled={isLoading || sent}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-semibold text-sm text-white disabled:opacity-60"
            style={{ background: 'hsl(220 90% 60%)' }}>
            {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Send className="w-4 h-4" />}
            {isLoading ? 'Sending...' : `Send ${entries.length} Invitation${entries.length > 1 ? 's' : ''}`}
          </button>
        </div>
      </form>
    </motion.div>
  );
}
