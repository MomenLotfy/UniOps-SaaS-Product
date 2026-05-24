import { useState } from 'react';
import { motion } from 'framer-motion';
import { Bell, Mail, MessageSquare, Smartphone, Save } from 'lucide-react';

type Channel = 'email' | 'slack' | 'push';
type Category = 'security' | 'deployments' | 'costs' | 'ml' | 'system';

const CATEGORIES: { key: Category; label: string; desc: string }[] = [
  { key: 'security', label: 'Security Alerts', desc: 'Threats, CVEs, and compliance updates' },
  { key: 'deployments', label: 'Deployments', desc: 'Pipeline and deployment status changes' },
  { key: 'costs', label: 'Cost Alerts', desc: 'Budget limits and cost anomalies' },
  { key: 'ml', label: 'ML Insights', desc: 'New patterns and recommendations' },
  { key: 'system', label: 'System Updates', desc: 'Maintenance and platform updates' },
];

const CHANNELS: { key: Channel; label: string; icon: React.ElementType }[] = [
  { key: 'email', label: 'Email', icon: Mail },
  { key: 'slack', label: 'Slack', icon: MessageSquare },
  { key: 'push', label: 'Push', icon: Smartphone },
];

type Prefs = Record<Category, Record<Channel, boolean>>;

const DEFAULT: Prefs = {
  security:    { email: true,  slack: true,  push: true  },
  deployments: { email: true,  slack: true,  push: false },
  costs:       { email: true,  slack: false, push: false },
  ml:          { email: false, slack: true,  push: false },
  system:      { email: true,  slack: false, push: false },
};

export default function NotificationsSettings() {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const toggle = (cat: Category, ch: Channel) => {
    setPrefs((p) => ({ ...p, [cat]: { ...p[cat], [ch]: !p[cat][ch] } }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    await new Promise((r) => setTimeout(r, 600));
    setSaved(true);
    setIsSaving(false);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      <div className="page-header">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">Choose what you want to be notified about</p>
        </div>
        <button onClick={handleSave} disabled={isSaving}
          className="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm disabled:opacity-60"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          {isSaving ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Save className="w-4 h-4" />}
          {isSaving ? 'Saving...' : saved ? '✓ Saved' : 'Save preferences'}
        </button>
      </div>

      <div className="card-base overflow-hidden">
        <table className="data-table">
          <thead>
            <tr>
              <th>Category</th>
              {CHANNELS.map((ch) => (
                <th key={ch.key}>
                  <div className="flex items-center gap-1.5">
                    <ch.icon className="w-3.5 h-3.5" />
                    {ch.label}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {CATEGORIES.map((cat) => (
              <tr key={cat.key}>
                <td>
                  <div className="font-medium text-foreground">{cat.label}</div>
                  <div className="text-xs text-muted-foreground">{cat.desc}</div>
                </td>
                {CHANNELS.map((ch) => (
                  <td key={ch.key}>
                    <button onClick={() => toggle(cat.key, ch.key)}
                      className="w-9 h-5 rounded-full transition-all relative flex-shrink-0"
                      style={{ background: prefs[cat.key][ch.key] ? 'hsl(220 90% 60%)' : 'hsl(230 15% 14%)' }}>
                      <div className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all shadow-sm"
                        style={{ left: prefs[cat.key][ch.key] ? '18px' : '2px' }} />
                    </button>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card-base">
        <h2 className="text-sm font-semibold text-foreground mb-4">Quiet Hours</h2>
        <div className="flex items-center gap-4">
          <label className="text-sm text-muted-foreground">Silence notifications from</label>
          <input type="time" defaultValue="22:00"
            className="px-3 py-1.5 rounded-lg text-sm text-foreground border outline-none"
            style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' }} />
          <label className="text-sm text-muted-foreground">to</label>
          <input type="time" defaultValue="08:00"
            className="px-3 py-1.5 rounded-lg text-sm text-foreground border outline-none"
            style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' }} />
        </div>
      </div>
    </motion.div>
  );
}
