/**
 * TicketModal — create or link tickets in Jira / Linear / Azure DevOps.
 * Usage:
 *   <TicketModal
 *     entityType="vulnerability"
 *     entityId="abc-123"
 *     entityTitle="CVE-2024-1234 — lodash prototype pollution"
 *     severity="high"
 *     onClose={() => setOpen(false)}
 *   />
 */
import { useState, useEffect } from 'react';
import { X, ExternalLink, Plus, Link2, Loader2, CheckCircle2, AlertTriangle, Ticket } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';

type Provider = 'jira' | 'linear' | 'azure_devops';
type Mode     = 'create' | 'link';

interface Props {
  entityType:  string;
  entityId:    string;
  entityTitle: string;
  severity?:   string;
  onClose:     () => void;
  onCreated?:  (ticket: any) => void;
}

const PROVIDER_LABELS: Record<Provider, string> = {
  jira:          'Jira',
  linear:        'Linear',
  azure_devops:  'Azure DevOps',
};

const PROVIDER_COLORS: Record<Provider, string> = {
  jira:          'bg-blue-500/20 text-blue-400 border-blue-400/20',
  linear:        'bg-purple-500/20 text-purple-400 border-purple-400/20',
  azure_devops:  'bg-cyan-500/20 text-cyan-400 border-cyan-400/20',
};

export default function TicketModal({ entityType, entityId, entityTitle, severity = 'high', onClose, onCreated }: Props) {
  const [mode, setMode]           = useState<Mode>('create');
  const [provider, setProvider]   = useState<Provider>('jira');
  const [submitting, setSubmit]   = useState(false);
  const [success, setSuccess]     = useState<any>(null);
  const [error, setError]         = useState('');

  // Create form state
  const [title, setTitle]         = useState(`[Security] ${entityTitle}`);
  const [description, setDescription] = useState(
    `Security finding requires remediation.\n\nEntity: ${entityType}/${entityId}\nSeverity: ${severity}\nTitle: ${entityTitle}`
  );
  const [jiraProject, setJiraProject] = useState('');
  const [linearTeamId, setLinearTeam] = useState('');
  const [adoType, setAdoType]         = useState('Bug');

  // Link form state
  const [linkKey, setLinkKey]     = useState('');
  const [linkUrl, setLinkUrl]     = useState('');
  const [linkTitle, setLinkTitle] = useState('');

  // Which providers are configured
  const { data: provRaw } = useApi<any>('/tickets/providers');
  const providerStatus: Record<string, boolean> = provRaw?.data ?? provRaw ?? {};
  const configuredProviders = (Object.keys(PROVIDER_LABELS) as Provider[]).filter(p => providerStatus[p]);

  // Existing tickets for this entity
  const { data: tickRaw, refetch: refetchTickets } = useApi<any>(
    `/tickets?entity_type=${entityType}&entity_id=${entityId}`
  );
  const tickets: any[] = Array.isArray(tickRaw?.data ?? tickRaw) ? (tickRaw?.data ?? tickRaw) : [];

  const handleCreate = async () => {
    setSubmit(true);
    setError('');
    try {
      const payload: any = {
        entity_type: entityType,
        entity_id:   entityId,
        provider,
        title,
        description,
        severity,
      };
      if (provider === 'jira')         payload.jira_project_key   = jiraProject;
      if (provider === 'linear')       payload.linear_team_id     = linearTeamId || undefined;
      if (provider === 'azure_devops') payload.ado_work_item_type = adoType;

      const res  = await apiClient.post('/tickets', payload);
      const data = (res as any)?.data ?? res;
      setSuccess(data);
      onCreated?.(data);
      await refetchTickets();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Failed to create ticket';
      setError(msg);
    } finally { setSubmit(false); }
  };

  const handleLink = async () => {
    if (!linkKey || !linkUrl) { setError('Ticket key and URL are required'); return; }
    setSubmit(true);
    setError('');
    try {
      const res  = await apiClient.post('/tickets/link', {
        entity_type:  entityType,
        entity_id:    entityId,
        provider,
        ticket_key:   linkKey,
        ticket_url:   linkUrl,
        ticket_title: linkTitle,
      });
      const data = (res as any)?.data ?? res;
      setSuccess(data);
      onCreated?.(data);
      await refetchTickets();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Failed to link ticket';
      setError(msg);
    } finally { setSubmit(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative w-full max-w-lg rounded-xl border shadow-2xl flex flex-col max-h-[90vh]"
        style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 16%)' }}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <div className="flex items-center gap-2">
            <Ticket className="w-4 h-4 text-blue-400" />
            <div>
              <p className="text-sm font-semibold text-foreground">Security Ticket</p>
              <p className="text-[11px] text-muted-foreground truncate max-w-[280px]">{entityTitle}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 p-5 space-y-4">

          {/* Existing tickets */}
          {tickets.length > 0 && (
            <div className="space-y-1">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Linked Tickets</p>
              {tickets.map(t => (
                <div key={t.id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10">
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border font-medium capitalize', PROVIDER_COLORS[t.provider as Provider])}>
                    {PROVIDER_LABELS[t.provider as Provider] || t.provider}
                  </span>
                  <span className="text-xs font-medium text-foreground">{t.ticket_key}</span>
                  <span className="text-[11px] text-muted-foreground flex-1 truncate">{t.ticket_title}</span>
                  <span className="text-[10px] text-muted-foreground capitalize">{t.ticket_status}</span>
                  {t.ticket_url && (
                    <a href={t.ticket_url} target="_blank" rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-foreground">
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Success */}
          {success && (
            <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-green-500/10 border border-green-500/20">
              <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-xs font-medium text-green-400">Ticket {success.link_type === 'created' ? 'created' : 'linked'} successfully</p>
                <p className="text-[11px] text-muted-foreground">{success.ticket_key}</p>
              </div>
              {success.ticket_url && (
                <a href={success.ticket_url} target="_blank" rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 text-[11px] flex items-center gap-1">
                  Open <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20">
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-400">{error}</p>
            </div>
          )}

          {/* Mode tabs */}
          <div className="flex rounded-lg border border-white/10 overflow-hidden">
            <button onClick={() => { setMode('create'); setSuccess(null); setError(''); }}
              className={clsx('flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors',
                mode === 'create' ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              <Plus className="w-3.5 h-3.5" /> Create Ticket
            </button>
            <button onClick={() => { setMode('link'); setSuccess(null); setError(''); }}
              className={clsx('flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors',
                mode === 'link' ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground hover:bg-white/5')}>
              <Link2 className="w-3.5 h-3.5" /> Link Existing
            </button>
          </div>

          {/* Provider picker */}
          <div>
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Provider</p>
            <div className="grid grid-cols-3 gap-2">
              {(Object.keys(PROVIDER_LABELS) as Provider[]).map(p => {
                const isConfigured = providerStatus[p];
                return (
                  <button key={p} onClick={() => setProvider(p)} disabled={!isConfigured}
                    className={clsx('py-2 px-3 rounded-lg border text-[11px] font-medium transition-colors flex flex-col items-center gap-1',
                      provider === p
                        ? 'bg-blue-600/20 border-blue-500/40 text-blue-400'
                        : isConfigured
                          ? 'border-white/10 text-muted-foreground hover:text-foreground hover:bg-white/5'
                          : 'border-white/5 text-muted-foreground/40 cursor-not-allowed')}>
                    {PROVIDER_LABELS[p]}
                    {!isConfigured && (
                      <span className="text-[9px] text-muted-foreground/40">not configured</span>
                    )}
                  </button>
                );
              })}
            </div>
            {configuredProviders.length === 0 && (
              <p className="text-[11px] text-yellow-400 mt-2">
                No providers configured. Set JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN, LINEAR_API_KEY, or ADO_ORG/ADO_PROJECT/ADO_PAT.
              </p>
            )}
          </div>

          {/* Create form */}
          {mode === 'create' && (
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Title</label>
                <input className="mt-1 w-full px-3 py-2 text-xs rounded-lg bg-white/5 border border-white/10 text-foreground focus:outline-none focus:border-blue-500/50"
                  value={title} onChange={e => setTitle(e.target.value)} />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Description</label>
                <textarea rows={4} className="mt-1 w-full px-3 py-2 text-xs rounded-lg bg-white/5 border border-white/10 text-foreground focus:outline-none focus:border-blue-500/50 resize-none"
                  value={description} onChange={e => setDescription(e.target.value)} />
              </div>
              {/* Provider-specific fields */}
              {provider === 'jira' && (
                <div>
                  <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Jira Project Key <span className="text-red-400">*</span>
                  </label>
                  <input className="mt-1 w-full px-3 py-2 text-xs rounded-lg bg-white/5 border border-white/10 text-foreground focus:outline-none focus:border-blue-500/50"
                    placeholder="e.g. SEC, ENG, OPS"
                    value={jiraProject} onChange={e => setJiraProject(e.target.value)} />
                </div>
              )}
              {provider === 'linear' && (
                <div>
                  <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Linear Team ID (optional)</label>
                  <input className="mt-1 w-full px-3 py-2 text-xs rounded-lg bg-white/5 border border-white/10 text-foreground focus:outline-none focus:border-blue-500/50"
                    placeholder="Leave blank to use first available team"
                    value={linearTeamId} onChange={e => setLinearTeam(e.target.value)} />
                </div>
              )}
              {provider === 'azure_devops' && (
                <div>
                  <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Work Item Type</label>
                  <select className="mt-1 w-full px-3 py-2 text-xs rounded-lg bg-white/5 border border-white/10 text-foreground focus:outline-none focus:border-blue-500/50"
                    value={adoType} onChange={e => setAdoType(e.target.value)}>
                    {['Bug', 'Task', 'User Story', 'Feature'].map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
              )}
            </div>
          )}

          {/* Link form */}
          {mode === 'link' && (
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Ticket Key <span className="text-red-400">*</span>
                </label>
                <input className="mt-1 w-full px-3 py-2 text-xs rounded-lg bg-white/5 border border-white/10 text-foreground focus:outline-none focus:border-blue-500/50"
                  placeholder="e.g. SEC-123, ENG-456, #789"
                  value={linkKey} onChange={e => setLinkKey(e.target.value)} />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Ticket URL <span className="text-red-400">*</span>
                </label>
                <input className="mt-1 w-full px-3 py-2 text-xs rounded-lg bg-white/5 border border-white/10 text-foreground focus:outline-none focus:border-blue-500/50"
                  placeholder="https://…"
                  value={linkUrl} onChange={e => setLinkUrl(e.target.value)} />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Title (optional)</label>
                <input className="mt-1 w-full px-3 py-2 text-xs rounded-lg bg-white/5 border border-white/10 text-foreground focus:outline-none focus:border-blue-500/50"
                  placeholder="Ticket title or summary"
                  value={linkTitle} onChange={e => setLinkTitle(e.target.value)} />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-2 px-5 py-4 border-t" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          <button onClick={onClose}
            className="flex-1 py-2 text-xs rounded-lg border border-white/10 text-muted-foreground hover:text-foreground transition-colors">
            Cancel
          </button>
          <button
            onClick={mode === 'create' ? handleCreate : handleLink}
            disabled={submitting || (mode === 'create' && provider === 'jira' && !jiraProject)}
            className="flex-1 py-2 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5">
            {submitting
              ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Processing…</>
              : mode === 'create'
                ? <><Plus className="w-3.5 h-3.5" /> Create Ticket</>
                : <><Link2 className="w-3.5 h-3.5" /> Link Ticket</>
            }
          </button>
        </div>
      </div>
    </div>
  );
}
