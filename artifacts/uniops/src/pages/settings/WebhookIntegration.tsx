import { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, AlertCircle, Copy, Plus, Trash2, Globe } from 'lucide-react';
import { clsx } from 'clsx';

interface WebhookConfig {
  url: string;
  secret: string;
  events: string[];
  contentType: 'json' | 'form';
  active: boolean;
}

const ALL_EVENTS = [
  { group: 'Security', events: ['threat.detected', 'vulnerability.new', 'alert.critical'] },
  { group: 'DevOps', events: ['pipeline.failed', 'pipeline.completed', 'pod.crashed'] },
  { group: 'FinOps', events: ['cost.anomaly', 'budget.exceeded', 'savings.new'] },
  { group: 'System', events: ['user.invited', 'integration.connected', 'integration.error'] },
];

export default function WebhookIntegration() {
  const navigate = useNavigate();
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([
    { url: '', secret: '', events: ['threat.detected', 'pipeline.failed'], contentType: 'json', active: true },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [copiedSecret, setCopiedSecret] = useState<number | null>(null);

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;

  const generateSecret = () => Array.from(crypto.getRandomValues(new Uint8Array(24))).map((b) => b.toString(16).padStart(2, '0')).join('');

  const addWebhook = () => setWebhooks((p) => [...p, { url: '', secret: generateSecret(), events: [], contentType: 'json', active: true }]);
  const removeWebhook = (idx: number) => setWebhooks((p) => p.filter((_, i) => i !== idx));
  const updateWebhook = (idx: number, field: keyof WebhookConfig, value: unknown) =>
    setWebhooks((p) => p.map((w, i) => i === idx ? { ...w, [field]: value } : w));
  const toggleEvent = (idx: number, event: string) => {
    const w = webhooks[idx];
    const events = w.events.includes(event) ? w.events.filter((e) => e !== event) : [...w.events, event];
    updateWebhook(idx, 'events', events);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setStatus('success');
    setIsLoading(false);
    setTimeout(() => setStatus('idle'), 3000);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="max-w-2xl space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="action-btn"><ArrowLeft className="w-4 h-4" /> Back</button>
      </div>
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{ background: 'hsl(230 15% 12%)', border: '1px solid hsl(230 15% 16%)' }}>
          <Globe className="w-7 h-7 text-blue-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">Webhook Integration</h1>
          <p className="text-sm text-muted-foreground">Send real-time event notifications to external URLs</p>
        </div>
      </div>

      {status === 'success' && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400" style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
          <CheckCircle className="w-4 h-4 flex-shrink-0" /> Webhooks saved successfully!
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-4">
        {webhooks.map((wh, idx) => (
          <div key={idx} className="card-base space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">Webhook {idx + 1}</p>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => updateWebhook(idx, 'active', !wh.active)}
                  className={clsx('w-10 h-5.5 rounded-full transition-colors relative', wh.active ? 'bg-blue-500' : 'bg-muted/40')}>
                  <span className={clsx('absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all', wh.active ? 'left-5' : 'left-0.5')} />
                </button>
                {webhooks.length > 1 && (
                  <button type="button" onClick={() => removeWebhook(idx)} className="p-1.5 rounded-lg text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Payload URL</label>
              <input type="url" required placeholder="https://your-server.com/webhook" value={wh.url}
                onChange={(e) => updateWebhook(idx, 'url', e.target.value)} className={inputCls} style={inputStyle} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Secret</label>
              <div className="flex gap-2">
                <input type="text" value={wh.secret} onChange={(e) => updateWebhook(idx, 'secret', e.target.value)} className={clsx(inputCls, 'font-mono')} style={inputStyle} />
                <button type="button" onClick={() => { navigator.clipboard.writeText(wh.secret); setCopiedSecret(idx); setTimeout(() => setCopiedSecret(null), 2000); }}
                  className={clsx('px-3 rounded-lg border text-sm transition-colors flex-shrink-0', copiedSecret === idx ? 'text-green-400 border-green-500/30' : 'text-muted-foreground border-border hover:text-foreground')}
                  style={{ borderColor: 'hsl(230 15% 14%)' }}>
                  {copiedSecret === idx ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium mb-2 text-muted-foreground">Events to send</label>
              <div className="space-y-2">
                {ALL_EVENTS.map((group) => (
                  <div key={group.group}>
                    <p className="text-xs text-muted-foreground/70 mb-1">{group.group}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {group.events.map((ev) => (
                        <button type="button" key={ev} onClick={() => toggleEvent(idx, ev)}
                          className={clsx('text-xs px-2 py-1 rounded-md font-mono transition-all', wh.events.includes(ev) ? 'text-blue-300 bg-blue-500/15 border border-blue-500/30' : 'text-muted-foreground bg-muted/20 border border-border/30 hover:border-border')}>
                          {ev}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}

        <button type="button" onClick={addWebhook}
          className="flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 font-medium transition-colors">
          <Plus className="w-4 h-4" /> Add another webhook
        </button>

        <div className="flex gap-3">
          <button type="button" onClick={() => navigate(-1)}
            className="px-4 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground border transition-colors"
            style={{ borderColor: 'hsl(230 15% 14%)' }}>Cancel</button>
          <button type="submit" disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-semibold text-sm text-white disabled:opacity-60"
            style={{ background: 'hsl(220 90% 60%)' }}>
            {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : null}
            {isLoading ? 'Saving...' : 'Save webhooks'}
          </button>
        </div>
      </form>
    </motion.div>
  );
}
