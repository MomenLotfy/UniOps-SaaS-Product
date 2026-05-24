import { useState } from 'react';
import { Save, AlertCircle, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { AvatarUploader } from './AvatarUploader';
import type { User } from '@/types/user';

interface ProfileFormProps {
  user: User;
  onSave: (data: Partial<User>) => Promise<void>;
}

export function ProfileForm({ user, onSave }: ProfileFormProps) {
  const [form, setForm] = useState({
    firstName: user.firstName,
    lastName: user.lastName,
    displayName: user.displayName,
    avatar: user.avatar,
    jobTitle: '',
    department: '',
    timezone: 'UTC',
    language: 'en',
    bio: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;
  const labelCls = 'block text-xs font-medium mb-1.5 text-muted-foreground';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setStatus('idle');
    try {
      await onSave({ firstName: form.firstName, lastName: form.lastName, displayName: form.displayName, avatar: form.avatar });
      setStatus('success');
      setTimeout(() => setStatus('idle'), 3000);
    } catch {
      setStatus('error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="flex items-start gap-6">
        <AvatarUploader
          name={user.displayName}
          currentAvatar={form.avatar}
          onUpload={(url) => setForm((p) => ({ ...p, avatar: url }))}
        />
        <div className="flex-1 space-y-1">
          <p className="text-sm font-medium text-foreground">{user.displayName}</p>
          <p className="text-xs text-muted-foreground">{user.email}</p>
          <p className="text-xs text-muted-foreground capitalize">{user.role.replace('_', ' ')}</p>
        </div>
      </div>

      {status === 'success' && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400"
          style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
          <CheckCircle className="w-4 h-4 flex-shrink-0" /> Profile updated successfully
        </div>
      )}
      {status === 'error' && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
          style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> Failed to update profile
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>First name</label>
          <input type="text" value={form.firstName} onChange={(e) => setForm((p) => ({ ...p, firstName: e.target.value }))} className={inputCls} style={inputStyle} />
        </div>
        <div>
          <label className={labelCls}>Last name</label>
          <input type="text" value={form.lastName} onChange={(e) => setForm((p) => ({ ...p, lastName: e.target.value }))} className={inputCls} style={inputStyle} />
        </div>
      </div>

      <div>
        <label className={labelCls}>Display name</label>
        <input type="text" value={form.displayName} onChange={(e) => setForm((p) => ({ ...p, displayName: e.target.value }))} className={inputCls} style={inputStyle} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Job title</label>
          <input type="text" placeholder="e.g. Senior DevOps Engineer" value={form.jobTitle} onChange={(e) => setForm((p) => ({ ...p, jobTitle: e.target.value }))} className={inputCls} style={inputStyle} />
        </div>
        <div>
          <label className={labelCls}>Department</label>
          <input type="text" placeholder="e.g. Engineering" value={form.department} onChange={(e) => setForm((p) => ({ ...p, department: e.target.value }))} className={inputCls} style={inputStyle} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Timezone</label>
          <select value={form.timezone} onChange={(e) => setForm((p) => ({ ...p, timezone: e.target.value }))} className={inputCls} style={inputStyle}>
            {['UTC', 'America/New_York', 'America/Chicago', 'America/Los_Angeles', 'Europe/London', 'Europe/Berlin', 'Asia/Dubai', 'Asia/Tokyo'].map((tz) => (
              <option key={tz} value={tz}>{tz.replace('_', ' ')}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Language</label>
          <select value={form.language} onChange={(e) => setForm((p) => ({ ...p, language: e.target.value }))} className={inputCls} style={inputStyle}>
            <option value="en">English</option>
            <option value="ar">Arabic</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="es">Spanish</option>
          </select>
        </div>
      </div>

      <div>
        <label className={labelCls}>Bio</label>
        <textarea rows={3} placeholder="Tell your team about yourself..." value={form.bio}
          onChange={(e) => setForm((p) => ({ ...p, bio: e.target.value }))}
          className={clsx(inputCls, 'resize-none')} style={inputStyle} />
      </div>

      <div className="flex justify-end">
        <button type="submit" disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-semibold text-sm disabled:opacity-60 disabled:cursor-not-allowed"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Save className="w-4 h-4" />}
          {isLoading ? 'Saving...' : 'Save changes'}
        </button>
      </div>
    </form>
  );
}
