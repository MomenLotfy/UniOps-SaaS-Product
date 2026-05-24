import { useState } from 'react';
import { Plus, Zap, Trash2, RefreshCw, CheckCircle, XCircle, Clock, Copy, Eye, EyeOff } from 'lucide-react';
import { clsx } from 'clsx';

interface Webhook {
  id: string; url: string; name: string; events: string[];
  status: 'active' | 'inactive' | 'failing';
  lastTriggered: string; successRate: number; secret: string;
}

const ALL_EVENTS = [
  'deployment.started', 'deployment.succeeded', 'deployment.failed',
  'incident.created', 'incident.resolved',
  'alert.triggered', 'alert.resolved',
  'user.created', 'user.deleted',
  'cost.budget_exceeded', 'cost.anomaly_detected',
];

const WEBHOOKS: Webhook[] = [
  { id: '1', name: 'Slack Alerts', url: 'https://hooks.slack.com/services/T00/B00/xxx', events: ['alert.triggered', 'incident.created', 'deployment.failed'], status: 'active', lastTriggered: '2 mins ago', successRate: 99.2, secret: 'whsec_abc123xyz789' },
  { id: '2', name: 'PagerDuty', url: 'https://events.pagerduty.com/integration/v2/enqueue', events: ['incident.created', 'alert.triggered'], status: 'active', lastTriggered: '1 hour ago', successRate: 100, secret: 'whsec_pagerduty456' },
  { id: '3', name: 'Internal SIEM', url: 'https://siem.internal.company.com/webhook', events: ['user.created', 'user.deleted', 'alert.triggered'], status: 'failing', lastTriggered: '3 days ago', successRate: 42.1, secret: 'whsec_siem789abc' },
];

const statusConfig = {
  active:   { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-400/10 border-green-400/20' },
  inactive: { icon: Clock,       color: 'text-muted-foreground', bg: 'bg-border/30 border-border' },
  failing:  { icon: XCircle,     color: 'text-red-400', bg: 'bg-red-400/10 border-red-400/20' },
};

export default function Webhooks() {
  const [webhooks, setWebhooks] = useState(WEBHOOKS);
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});
  const [showNew, setShowNew] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [newName, setNewName] = useState('');
  const [newEvents, setNewEvents] = useState<string[]>([]);

  const toggleSecret = (id: string) => setShowSecret((s) => ({ ...s, [id]: !s[id] }));
  const toggleEvent = (ev: string) => setNewEvents((evs) => evs.includes(ev) ? evs.filter((e) => e !== ev) : [...evs, ev]);
  const deleteWebhook = (id: string) => setWebhooks((prev) => prev.filter((w) => w.id !== id));

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Webhooks</h1>
          <p className="page-subtitle">Send real-time event notifications to external services.</p>
        </div>
        <button onClick={() => setShowNew(true)} className="action-btn action-btn-primary"><Plus className="w-4 h-4" /> Add Webhook</button>
      </div>

      {/* New webhook form */}
      {showNew && (
        <div className="card-base rounded-xl p-5 border border-primary/30 space-y-4">
          <h3 className="text-sm font-semibold text-foreground">New Webhook</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Name</label>
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="My Webhook"
                className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Endpoint URL</label>
              <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="https://..."
                className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50" />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-2">Events to Subscribe</label>
            <div className="grid grid-cols-3 gap-2">
              {ALL_EVENTS.map((ev) => (
                <button key={ev} onClick={() => toggleEvent(ev)}
                  className={clsx('text-xs px-3 py-1.5 rounded-lg border text-left transition-colors', newEvents.includes(ev) ? 'border-primary/50 bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:border-primary/30')}>
                  {ev}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-3 justify-end">
            <button onClick={() => setShowNew(false)} className="action-btn">Cancel</button>
            <button disabled={!newUrl || !newName || newEvents.length === 0} className="action-btn action-btn-primary disabled:opacity-40">Create Webhook</button>
          </div>
        </div>
      )}

      {/* Webhook list */}
      <div className="space-y-3">
        {webhooks.map((wh) => {
          const { icon: Icon, color, bg } = statusConfig[wh.status];
          return (
            <div key={wh.id} className="card-base rounded-xl p-5 border border-border space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Zap className="w-4 h-4 text-primary" />
                    <span className="text-sm font-semibold text-foreground">{wh.name}</span>
                    <span className={clsx('text-xs px-2 py-0.5 rounded-full border flex items-center gap-1', bg)}>
                      <Icon className={clsx('w-3 h-3', color)} />{wh.status}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground font-mono truncate max-w-sm">{wh.url}</div>
                </div>
                <div className="flex gap-2">
                  <button className="action-btn"><RefreshCw className="w-3.5 h-3.5" /> Test</button>
                  <button onClick={() => deleteWebhook(wh.id)} className="action-btn text-red-400 hover:bg-red-500/10"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>

              {/* Secret */}
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">Signing Secret</label>
                <div className="flex items-center gap-2">
                  <div className="flex-1 px-3 py-2 rounded-lg border border-border bg-background/50 text-xs font-mono text-foreground flex items-center gap-2">
                    <span>{showSecret[wh.id] ? wh.secret : '•'.repeat(20)}</span>
                  </div>
                  <button onClick={() => toggleSecret(wh.id)} className="action-btn">{showSecret[wh.id] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}</button>
                  <button className="action-btn"><Copy className="w-3.5 h-3.5" /></button>
                </div>
              </div>

              {/* Events + stats */}
              <div className="flex items-center justify-between">
                <div className="flex flex-wrap gap-1.5">
                  {wh.events.map((ev) => (
                    <span key={ev} className="text-xs px-2 py-0.5 rounded-full border border-border text-muted-foreground">{ev}</span>
                  ))}
                </div>
                <div className="text-xs text-muted-foreground text-right">
                  <div>Last: {wh.lastTriggered}</div>
                  <div>Success: <span className={wh.successRate >= 90 ? 'text-green-400' : 'text-red-400'}>{wh.successRate}%</span></div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
