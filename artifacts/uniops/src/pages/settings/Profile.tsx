import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Camera, Save } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { initials } from '@/lib/formatters';

export default function Profile() {
  const { user, updateUser } = useAuth();
  const [form, setForm] = useState({
    firstName: '', lastName: '', email: '',
    title: '', bio: '', timezone: 'Africa/Cairo', language: 'en',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (user) {
      setForm(f => ({
        ...f,
        firstName: user.firstName ?? '',
        lastName: user.lastName ?? '',
        email: user.email ?? '',
      }));
    }
  }, [user]);

  if (!user) return null;

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm text-foreground border outline-none focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError('');
    try {
      await new Promise((r) => setTimeout(r, 500));
      updateUser({
        ...user,
        firstName: form.firstName,
        lastName: form.lastName,
        displayName: `${form.firstName} ${form.lastName}`.trim(),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err: any) {
      setError(err.message ?? 'Update failed');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div><h1 className="page-title">Profile</h1><p className="page-subtitle">Manage your personal information</p></div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="card-base flex flex-col items-center text-center gap-4">
          <div className="relative">
            <div className="w-24 h-24 rounded-full flex items-center justify-center text-3xl font-bold"
              style={{ background: 'hsl(220 90% 60% / 0.2)', color: 'hsl(220 90% 70%)' }}>
              {initials(user.displayName)}
            </div>
            <button className="absolute bottom-0 right-0 w-8 h-8 rounded-full flex items-center justify-center"
              style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
              <Camera className="w-3.5 h-3.5" />
            </button>
          </div>
          <div>
            <div className="font-semibold text-foreground">{user.displayName}</div>
            <div className="text-sm text-muted-foreground">{user.email}</div>
            <div className="mt-2"><span className="badge-medium capitalize">{user.role}</span></div>
          </div>
          <div className="w-full text-left space-y-2 pt-2 border-t border-border">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Member since</span>
              <span className="text-foreground">{user.createdAt ? new Date(user.createdAt).toLocaleDateString('en', { month: 'short', year: 'numeric' }) : '—'}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Email verified</span>
              <span className={user.emailVerified ? 'text-green-400' : 'text-yellow-400'}>
                {user.emailVerified ? '✓ Verified' : 'Pending'}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">2FA</span>
              <span className={user.twoFactorEnabled ? 'text-green-400' : 'text-muted-foreground'}>
                {user.twoFactorEnabled ? '✓ Enabled' : 'Disabled'}
              </span>
            </div>
          </div>
        </div>

        <div className="xl:col-span-2 card-base">
          <h2 className="text-sm font-semibold text-foreground mb-5">Personal Information</h2>
          <form onSubmit={handleSave} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">First name</label>
                <input value={form.firstName} onChange={e => setForm(f => ({ ...f, firstName: e.target.value }))}
                  className={inputCls} style={inputStyle} required />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">Last name</label>
                <input value={form.lastName} onChange={e => setForm(f => ({ ...f, lastName: e.target.value }))}
                  className={inputCls} style={inputStyle} required />
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">Email address</label>
              <input value={form.email} className={inputCls} style={{ ...inputStyle, opacity: 0.6 }} disabled />
              <p className="text-xs text-muted-foreground mt-1">Email cannot be changed here. Contact support.</p>
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">Timezone</label>
              <select value={form.timezone} onChange={e => setForm(f => ({ ...f, timezone: e.target.value }))}
                className={inputCls} style={inputStyle}>
                <option value="Africa/Cairo">Africa/Cairo (UTC+2)</option>
                <option value="Europe/London">Europe/London (UTC+0)</option>
                <option value="America/New_York">America/New_York (UTC-5)</option>
                <option value="America/Los_Angeles">America/Los_Angeles (UTC-8)</option>
                <option value="Asia/Dubai">Asia/Dubai (UTC+4)</option>
                <option value="Asia/Tokyo">Asia/Tokyo (UTC+9)</option>
              </select>
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <div className="flex items-center justify-between pt-2">
              <div>
                {saved && <span className="text-xs text-green-400">✓ Changes saved successfully</span>}
              </div>
              <button type="submit" disabled={isSaving} className="action-btn-primary">
                <Save className="w-4 h-4" />
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </motion.div>
  );
}
