import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Shield, Key, Smartphone, Monitor, LogOut, AlertCircle, Save } from 'lucide-react';
import { usersApi } from '@/services/api/users';
import type { UserSession } from '@/types/user';
import { formatRelative } from '@/lib/formatters';

export default function SecuritySettings() {
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [pwdForm, setPwdForm] = useState({ current: '', newPwd: '', confirm: '' });
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [twoFactor] = useState(false);

  useEffect(() => { usersApi.getSessions().then(setSessions); }, []);

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm text-foreground border outline-none focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const handleChangePwd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pwdForm.newPwd !== pwdForm.confirm) { setError('Passwords do not match'); return; }
    if (pwdForm.newPwd.length < 8) { setError('Password must be at least 8 characters'); return; }
    setError(''); setIsSaving(true);
    await new Promise((r) => setTimeout(r, 800));
    setSaved(true); setIsSaving(false);
    setPwdForm({ current: '', newPwd: '', confirm: '' });
    setTimeout(() => setSaved(false), 2000);
  };

  const handleRevokeSession = async (id: string) => {
    await usersApi.revokeSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      <div className="page-header">
        <div>
          <h1 className="page-title">Security</h1>
          <p className="page-subtitle">Manage your account security settings</p>
        </div>
      </div>

      {/* Change password */}
      <form onSubmit={handleChangePwd} className="card-base space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Key className="w-4 h-4 text-blue-400" />
          <h2 className="text-sm font-semibold text-foreground">Change Password</h2>
        </div>
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
            <AlertCircle className="w-4 h-4" />{error}
          </div>
        )}
        {[{ k: 'current', l: 'Current password' }, { k: 'newPwd', l: 'New password' }, { k: 'confirm', l: 'Confirm new password' }].map((f) => (
          <div key={f.k}>
            <label className="block text-xs font-medium mb-1.5 text-muted-foreground">{f.l}</label>
            <input type="password" value={pwdForm[f.k as keyof typeof pwdForm]}
              onChange={(e) => setPwdForm((p) => ({ ...p, [f.k]: e.target.value }))}
              placeholder="••••••••" className={inputCls} style={inputStyle} />
          </div>
        ))}
        <div className="flex items-center gap-3">
          <button type="submit" disabled={isSaving}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-sm disabled:opacity-60"
            style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
            {isSaving ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Save className="w-4 h-4" />}
            {isSaving ? 'Updating...' : 'Update password'}
          </button>
          {saved && <span className="text-sm text-green-400">✓ Password updated</span>}
        </div>
      </form>

      {/* 2FA */}
      <div className="card-base">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
              <Smartphone className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground">Two-Factor Authentication</div>
              <div className="text-xs text-muted-foreground">Add an extra layer of security to your account</div>
            </div>
          </div>
          <button className="px-4 py-2 rounded-lg text-sm font-medium border transition-colors"
            style={{ borderColor: twoFactor ? 'hsl(0 72% 51% / 0.4)' : 'hsl(220 90% 60%)', color: twoFactor ? 'hsl(0 90% 70%)' : 'hsl(220 90% 70%)', background: 'transparent' }}>
            {twoFactor ? 'Disable 2FA' : 'Enable 2FA'}
          </button>
        </div>
      </div>

      {/* Sessions */}
      <div className="card-base">
        <div className="flex items-center gap-2 mb-4">
          <Monitor className="w-4 h-4 text-blue-400" />
          <h2 className="text-sm font-semibold text-foreground">Active Sessions</h2>
        </div>
        <div className="space-y-3">
          {sessions.map((session) => (
            <div key={session.id} className="flex items-center gap-3 p-3 rounded-lg border border-border/50" style={{ background: 'hsl(230 18% 9%)' }}>
              <Monitor className="w-5 h-5 text-muted-foreground flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{session.device}</span>
                  {session.current && <span className="text-xs px-1.5 py-0.5 rounded-full" style={{ background: 'hsl(160 84% 39% / 0.15)', color: 'hsl(160 84% 55%)' }}>Current</span>}
                </div>
                <div className="text-xs text-muted-foreground">{session.browser} · {session.os} · {session.ip} · {session.location}</div>
                <div className="text-xs text-muted-foreground">Active {formatRelative(session.lastActive)}</div>
              </div>
              {!session.current && (
                <button onClick={() => handleRevokeSession(session.id)}
                  className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 transition-colors flex-shrink-0">
                  <LogOut className="w-3.5 h-3.5" />Revoke
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
