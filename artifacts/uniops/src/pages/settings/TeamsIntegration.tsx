import { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, AlertCircle, ExternalLink, Bell, Shield, DollarSign, Code2 } from 'lucide-react';
import { integrationsApi } from '@/services/api/integrations';

export default function TeamsIntegration() {
  const navigate = useNavigate();
  const [webhookUrl, setWebhookUrl] = useState('');
  const [selectedEvents, setSelectedEvents] = useState<string[]>(['security_alert', 'pipeline_fail']);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [error, setError] = useState('');

  const EVENTS = [
    { id: 'security_alert', label: 'Security Alerts', icon: Shield },
    { id: 'pipeline_fail', label: 'Pipeline Failures', icon: Code2 },
    { id: 'cost_anomaly', label: 'Cost Anomalies', icon: DollarSign },
    { id: 'critical_alert', label: 'Critical Alerts', icon: Bell },
  ];

  const toggleEvent = (id: string) =>
    setSelectedEvents((p) => p.includes(id) ? p.filter((e) => e !== id) : [...p, id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setStatus('idle');
    try {
      await integrationsApi.connectTeams(webhookUrl);
      setStatus('success');
      setTimeout(() => navigate(-1), 2000);
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="max-w-xl space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="action-btn"><ArrowLeft className="w-4 h-4" /> Back</button>
      </div>
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl" style={{ background: 'hsl(230 15% 12%)', border: '1px solid hsl(230 15% 16%)' }}>🔵</div>
        <div>
          <h1 className="text-xl font-bold text-foreground">Microsoft Teams Integration</h1>
          <p className="text-sm text-muted-foreground">Send real-time alerts to your Teams channels</p>
        </div>
      </div>
      <form onSubmit={handleSubmit} className="card-base space-y-5">
        {status === 'success' && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400" style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
            <CheckCircle className="w-4 h-4 flex-shrink-0" /> Microsoft Teams connected!
          </div>
        )}
        {status === 'error' && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
            <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
          </div>
        )}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-muted-foreground">Incoming Webhook URL</label>
            <a href="https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook" target="_blank" rel="noreferrer"
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">How to create <ExternalLink className="w-3 h-3" /></a>
          </div>
          <input type="url" required placeholder="https://your-org.webhook.office.com/webhookb2/..."
            value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/50"
            style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' }} />
        </div>
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Notify me about</p>
          <div className="grid grid-cols-2 gap-2">
            {EVENTS.map((ev) => (
              <label key={ev.id} className={`flex items-center gap-2.5 p-3 rounded-lg border cursor-pointer transition-all ${selectedEvents.includes(ev.id) ? 'border-blue-500/50 bg-blue-500/10' : 'border-border/50 hover:border-border'}`}>
                <input type="checkbox" checked={selectedEvents.includes(ev.id)} onChange={() => toggleEvent(ev.id)} className="w-4 h-4 accent-blue-500" />
                <ev.icon className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground">{ev.label}</span>
              </label>
            ))}
          </div>
        </div>
        <button type="submit" disabled={isLoading || !webhookUrl}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm text-white disabled:opacity-60"
          style={{ background: 'hsl(220 90% 60%)' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : null}
          {isLoading ? 'Connecting...' : 'Connect Teams'}
        </button>
      </form>
    </motion.div>
  );
}
