import { useState } from 'react';
import { MessageSquare, CheckCircle, Settings, Bell, BellOff, Hash, Plus, Trash2 } from 'lucide-react';
import { clsx } from 'clsx';

interface Channel { id: string; name: string; purpose: string; events: string[]; active: boolean; }

const ALL_EVENTS = ['deployment.failed', 'deployment.succeeded', 'incident.created', 'alert.triggered', 'cost.budget_exceeded', 'security.threat_detected'];

const CHANNELS: Channel[] = [
  { id: '1', name: '#platform-alerts',  purpose: 'Critical system alerts',     events: ['deployment.failed', 'incident.created', 'alert.triggered'], active: true },
  { id: '2', name: '#deployments',      purpose: 'CI/CD pipeline notifications', events: ['deployment.failed', 'deployment.succeeded'],               active: true },
  { id: '3', name: '#security',         purpose: 'Security events and threats', events: ['security.threat_detected', 'alert.triggered'],              active: true },
  { id: '4', name: '#finops',           purpose: 'Cost anomalies and budgets',  events: ['cost.budget_exceeded'],                                     active: false },
];

export default function SlackIntegration() {
  const [channels, setChannels] = useState(CHANNELS);
  const [showAdd, setShowAdd] = useState(false);
  const [newChannel, setNewChannel] = useState('');
  const [newEvents, setNewEvents] = useState<string[]>([]);

  const toggleChannel = (id: string) => setChannels((prev) => prev.map((c) => c.id === id ? { ...c, active: !c.active } : c));
  const removeChannel = (id: string) => setChannels((prev) => prev.filter((c) => c.id !== id));
  const toggleEvent = (ev: string) => setNewEvents((evs) => evs.includes(ev) ? evs.filter((e) => e !== ev) : [...evs, ev]);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'hsl(15 90% 55% / 0.2)' }}>
            <MessageSquare className="w-5 h-5 text-orange-400" />
          </div>
          <div>
            <h1 className="page-title">Slack</h1>
            <p className="page-subtitle">Workspace: UniOps · 4 channels configured</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowAdd(true)} className="action-btn action-btn-primary"><Plus className="w-4 h-4" /> Add Channel</button>
          <button className="action-btn"><Settings className="w-4 h-4" /> Configure</button>
        </div>
      </div>

      <div className="card-base rounded-xl p-4 border border-green-500/30 flex items-center gap-3">
        <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
        <span className="text-xs text-foreground">Slack App installed · Bot token active · Workspace: UniOps Engineering</span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Notifications Sent (7d)', value: '1,284' },
          { label: 'Active Channels',         value: channels.filter((c) => c.active).length.toString() },
          { label: 'Avg Response Time',       value: '< 1s' },
        ].map(({ label, value }) => (
          <div key={label} className="card-base rounded-xl p-4 border border-border text-center">
            <div className="text-2xl font-bold text-foreground">{value}</div>
            <div className="text-xs text-muted-foreground mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Add channel form */}
      {showAdd && (
        <div className="card-base rounded-xl p-5 border border-primary/30 space-y-4">
          <h3 className="text-sm font-semibold text-foreground">Add Channel</h3>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1.5">Channel Name</label>
            <div className="relative">
              <Hash className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input value={newChannel} onChange={(e) => setNewChannel(e.target.value)} placeholder="channel-name"
                className="w-full pl-8 pr-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50" />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-2">Subscribe to Events</label>
            <div className="grid grid-cols-2 gap-2">
              {ALL_EVENTS.map((ev) => (
                <button key={ev} onClick={() => toggleEvent(ev)}
                  className={clsx('text-xs px-3 py-1.5 rounded-lg border text-left transition-colors', newEvents.includes(ev) ? 'border-primary/50 bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:border-primary/30')}>
                  {ev}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-3 justify-end">
            <button onClick={() => { setShowAdd(false); setNewChannel(''); setNewEvents([]); }} className="action-btn">Cancel</button>
            <button disabled={!newChannel || newEvents.length === 0} className="action-btn action-btn-primary disabled:opacity-40">Add Channel</button>
          </div>
        </div>
      )}

      {/* Channels */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-foreground">Configured Channels</h3>
        {channels.map((ch) => (
          <div key={ch.id} className={clsx('card-base rounded-xl p-4 border transition-all', ch.active ? 'border-border' : 'border-border/50 opacity-60')}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Hash className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-semibold text-foreground">{ch.name}</span>
                <span className="text-xs text-muted-foreground">· {ch.purpose}</span>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => toggleChannel(ch.id)} className="action-btn">
                  {ch.active ? <BellOff className="w-3.5 h-3.5" /> : <Bell className="w-3.5 h-3.5" />}
                  {ch.active ? 'Mute' : 'Unmute'}
                </button>
                <button onClick={() => removeChannel(ch.id)} className="action-btn text-red-400 hover:bg-red-500/10"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {ch.events.map((ev) => (
                <span key={ev} className="text-xs px-2 py-0.5 rounded-full border border-primary/30 bg-primary/5 text-primary">{ev}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
