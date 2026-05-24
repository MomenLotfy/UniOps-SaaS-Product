import { useState } from 'react';
import { AlertTriangle, Trash2, Download, Globe, Clock } from 'lucide-react';

const TIMEZONES = ['UTC', 'America/New_York', 'America/Los_Angeles', 'America/Chicago', 'Europe/London', 'Europe/Berlin', 'Asia/Tokyo', 'Asia/Shanghai', 'Australia/Sydney'];
const LANGUAGES = [{ code: 'en', label: 'English' }, { code: 'de', label: 'Deutsch' }, { code: 'fr', label: 'Français' }, { code: 'ja', label: '日本語' }, { code: 'zh', label: '中文' }];
const DATE_FORMATS = ['MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD'];

export default function Account() {
  const [timezone, setTimezone] = useState('UTC');
  const [language, setLanguage] = useState('en');
  const [dateFormat, setDateFormat] = useState('YYYY-MM-DD');
  const [showDelete, setShowDelete] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState('');

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="page-title">Account Settings</h1>
        <p className="page-subtitle">Manage your regional preferences and account data.</p>
      </div>

      {/* Locale */}
      <div className="card-base rounded-xl p-6 border border-border space-y-5">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2"><Globe className="w-4 h-4" />Locale & Region</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1.5">Language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50">
              {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1.5">Date Format</label>
            <select value={dateFormat} onChange={(e) => setDateFormat(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50">
              {DATE_FORMATS.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1.5 flex items-center gap-1"><Clock className="w-3.5 h-3.5" />Timezone</label>
          <select value={timezone} onChange={(e) => setTimezone(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50">
            {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
          </select>
        </div>
        <div className="flex justify-end">
          <button className="action-btn action-btn-primary">Save Preferences</button>
        </div>
      </div>

      {/* Data export */}
      <div className="card-base rounded-xl p-6 border border-border space-y-4">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2"><Download className="w-4 h-4" />Data Export</h2>
        <p className="text-xs text-muted-foreground">Download a copy of all your account data including activity logs, API keys, settings, and profile information. The export will be emailed to you when ready.</p>
        <div className="flex gap-3">
          <button className="action-btn">Request Data Export</button>
        </div>
      </div>

      {/* Danger zone */}
      <div className="rounded-xl p-6 border border-red-500/30 space-y-4" style={{ background: 'hsl(0 80% 60% / 0.03)' }}>
        <h2 className="text-sm font-semibold text-red-400 flex items-center gap-2"><AlertTriangle className="w-4 h-4" />Danger Zone</h2>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-foreground">Delete Account</div>
            <div className="text-xs text-muted-foreground mt-0.5">Permanently delete your account and all associated data. This action is irreversible.</div>
          </div>
          <button onClick={() => setShowDelete(true)} className="action-btn border-red-500/40 text-red-400 hover:bg-red-500/10">
            <Trash2 className="w-4 h-4" /> Delete Account
          </button>
        </div>

        {showDelete && (
          <div className="border-t border-red-500/20 pt-4 space-y-3">
            <p className="text-xs text-red-300">Type <strong>delete my account</strong> to confirm:</p>
            <input value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder="delete my account"
              className="w-full px-3 py-2 text-sm rounded-lg border border-red-500/40 bg-background/50 text-foreground focus:outline-none focus:border-red-500" />
            <div className="flex gap-3">
              <button onClick={() => { setShowDelete(false); setDeleteConfirm(''); }} className="action-btn">Cancel</button>
              <button disabled={deleteConfirm !== 'delete my account'}
                className="action-btn border-red-500/40 text-red-400 hover:bg-red-500/10 disabled:opacity-40 disabled:cursor-not-allowed">
                <Trash2 className="w-4 h-4" /> Permanently Delete
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
