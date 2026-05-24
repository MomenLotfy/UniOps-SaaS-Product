import { useState } from 'react';
import { Bell, Mail, Smartphone, Globe, Save, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';

interface NotificationChannel {
  email: boolean;
  inApp: boolean;
  push: boolean;
  slack: boolean;
}

interface NotificationPreference {
  id: string;
  label: string;
  description: string;
  category: string;
  channels: NotificationChannel;
}

const DEFAULT_PREFS: NotificationPreference[] = [
  { id: 'security_alert', label: 'Security Alerts', description: 'Critical threats and security incidents', category: 'Security', channels: { email: true, inApp: true, push: true, slack: true } },
  { id: 'vuln_critical', label: 'Critical Vulnerabilities', description: 'New critical CVEs affecting your systems', category: 'Security', channels: { email: true, inApp: true, push: false, slack: true } },
  { id: 'pipeline_fail', label: 'Pipeline Failures', description: 'CI/CD pipeline failures and errors', category: 'DevOps', channels: { email: false, inApp: true, push: false, slack: true } },
  { id: 'pod_crash', label: 'Pod Crashes', description: 'Kubernetes pod crash loop backs', category: 'DevOps', channels: { email: false, inApp: true, push: false, slack: false } },
  { id: 'cost_anomaly', label: 'Cost Anomalies', description: 'Unusual spending patterns detected', category: 'FinOps', channels: { email: true, inApp: true, push: false, slack: false } },
  { id: 'budget_alert', label: 'Budget Alerts', description: 'Budget threshold warnings', category: 'FinOps', channels: { email: true, inApp: true, push: false, slack: true } },
  { id: 'ml_insight', label: 'ML Insights', description: 'New AI-generated recommendations', category: 'AI', channels: { email: false, inApp: true, push: false, slack: false } },
  { id: 'team_invite', label: 'Team Invitations', description: 'New team member invitations', category: 'Account', channels: { email: true, inApp: true, push: false, slack: false } },
];

const CHANNELS = [
  { key: 'email' as const, icon: Mail, label: 'Email' },
  { key: 'inApp' as const, icon: Bell, label: 'In-App' },
  { key: 'push' as const, icon: Smartphone, label: 'Push' },
  { key: 'slack' as const, icon: Globe, label: 'Slack' },
];

const CATEGORIES = ['Security', 'DevOps', 'FinOps', 'AI', 'Account'];

export function NotificationPreferences() {
  const [prefs, setPrefs] = useState(DEFAULT_PREFS);
  const [saved, setSaved] = useState(false);

  const toggle = (id: string, channel: keyof NotificationChannel) => {
    setPrefs((prev) => prev.map((p) => p.id === id ? { ...p, channels: { ...p.channels, [channel]: !p.channels[channel] } } : p));
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Configure how you receive notifications for each event type.</p>
        <button onClick={handleSave}
          className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all',
            saved ? 'text-green-400 bg-green-500/10' : 'text-white')}
          style={!saved ? { background: 'hsl(220 90% 60%)' } : undefined}>
          {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Saved' : 'Save'}
        </button>
      </div>

      {CATEGORIES.map((cat) => {
        const catPrefs = prefs.filter((p) => p.category === cat);
        return (
          <div key={cat}>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">{cat}</h3>
            <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'hsl(230 15% 14%)' }}>
              <div className="grid text-xs font-medium text-muted-foreground px-4 py-2 border-b" style={{ borderColor: 'hsl(230 15% 14%)', gridTemplateColumns: '1fr repeat(4, 72px)' }}>
                <span>Event</span>
                {CHANNELS.map((c) => (
                  <span key={c.key} className="text-center flex items-center justify-center gap-1">
                    <c.icon className="w-3 h-3" />{c.label}
                  </span>
                ))}
              </div>
              {catPrefs.map((pref, idx) => (
                <div key={pref.id}
                  className={clsx('grid items-center px-4 py-3', idx < catPrefs.length - 1 && 'border-b')}
                  style={{ gridTemplateColumns: '1fr repeat(4, 72px)', borderColor: 'hsl(230 15% 14%)' }}>
                  <div>
                    <p className="text-sm font-medium text-foreground">{pref.label}</p>
                    <p className="text-xs text-muted-foreground">{pref.description}</p>
                  </div>
                  {CHANNELS.map((c) => (
                    <div key={c.key} className="flex justify-center">
                      <button type="button" onClick={() => toggle(pref.id, c.key)}
                        className={clsx('w-5 h-5 rounded transition-colors flex items-center justify-center border',
                          pref.channels[c.key] ? 'text-white border-blue-500 bg-blue-500' : 'border-muted-foreground/30 text-transparent hover:border-blue-500/50')}>
                        <span className="text-xs">✓</span>
                      </button>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
