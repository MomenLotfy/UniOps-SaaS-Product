import { useState } from 'react';
import { FileText, Plus, RefreshCw, Filter, Loader2, Trash2, Download, CheckCircle, AlertTriangle, Clock } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';
import type { SecurityReport } from '@/services/api/security';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const REPORT_TYPES = [
  { value: 'executive_summary',    label: 'Executive Summary' },
  { value: 'threat_assessment',    label: 'Threat Assessment' },
  { value: 'vulnerability_report', label: 'Vulnerability Report' },
  { value: 'compliance_report',    label: 'Compliance Status' },
  { value: 'posture_report',       label: 'Security Posture' },
  { value: 'exception_report',     label: 'Exception Management' },
  { value: 'full_audit',           label: 'Full Audit Report' },
];

const STATUS_ICON: Record<string, React.ElementType> = {
  completed:  CheckCircle,
  generating: Loader2,
  failed:     AlertTriangle,
};
const STATUS_COLOR: Record<string, string> = {
  completed:  'text-green-400',
  generating: 'text-blue-400',
  failed:     'text-red-400',
};

function GenerateReportModal({ onClose, onGenerated }: { onClose: () => void; onGenerated: () => void }) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', report_type: 'executive_summary', description: '' });

  const handle = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await apiClient.post('/security-reports', form);
      onGenerated();
      onClose();
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md mx-4 rounded-xl border p-5 shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <h3 className="text-sm font-semibold text-foreground mb-4">Generate Security Report</h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Report Name *</label>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              placeholder="e.g. Q2 2026 Security Review" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Report Type</label>
            <select value={form.report_type} onChange={e => setForm(f => ({ ...f, report_type: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}>
              {REPORT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Description</label>
            <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              className="w-full px-3 py-2 text-xs rounded-lg border outline-none focus:border-blue-500/50 resize-none"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
              rows={2} placeholder="Optional description" />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>Cancel</button>
          <button onClick={handle} disabled={saving || !form.name.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors disabled:opacity-50">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
            {saving ? 'Generating…' : 'Generate Report'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Reports() {
  const { role } = usePermissions();
  const canGenerate = canWriteSecurity(role);

  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [deleting, setDeleting]     = useState<string | null>(null);
  const [expanded, setExpanded]     = useState<string | null>(null);

  const qs = new URLSearchParams({ page: '1', page_size: '20' });
  if (typeFilter)   qs.set('report_type', typeFilter);
  if (statusFilter) qs.set('status', statusFilter);

  const { data: raw, loading, refetch } = useApi<any>(`/security-reports?${qs}`);
  const result  = raw?.data ?? raw;
  const reports = result?.data ?? [];
  const total   = result?.total ?? 0;

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await apiClient.delete(`/security-reports/${id}`);
      refetch();
    } finally { setDeleting(null); }
  };

  return (
    <div className="space-y-4">
      {showCreate && <GenerateReportModal onClose={() => setShowCreate(false)} onGenerated={refetch} />}

      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Security Reports</h1>
          <p className="text-xs text-muted-foreground">{total} reports generated</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}>
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          {canGenerate && (
            <button onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors">
              <Plus className="w-3.5 h-3.5" /> Generate Report
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <Filter className="w-3.5 h-3.5 text-muted-foreground" />
        <button onClick={() => setTypeFilter('')}
          className={clsx('px-2.5 py-1 rounded transition-colors', !typeFilter ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
          All
        </button>
        {REPORT_TYPES.map(t => (
          <button key={t.value} onClick={() => setTypeFilter(t.value)}
            className={clsx('px-2.5 py-1 rounded transition-colors',
              typeFilter === t.value ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {t.label}
          </button>
        ))}
        <div className="w-px h-4 bg-border mx-1" />
        {['', 'completed', 'generating', 'failed'].map(s => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={clsx('px-2.5 py-1 rounded capitalize transition-colors',
              statusFilter === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}>
            {s || 'All Status'}
          </button>
        ))}
      </div>

      {/* Report list */}
      <div className="space-y-2">
        {loading ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
        ) : reports.length === 0 ? (
          <div className="card-base py-12 text-center">
            <FileText className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground mb-1">No reports yet</p>
            {canGenerate && <p className="text-xs text-muted-foreground">Click "Generate Report" to create your first security report.</p>}
          </div>
        ) : reports.map((r: SecurityReport) => {
          const StatusIcon = STATUS_ICON[r.status] ?? Clock;
          const isExpanded = expanded === r.id;
          const summary = r.summary as Record<string, unknown>;
          const type = REPORT_TYPES.find(t => t.value === r.report_type)?.label ?? r.report_type;

          return (
            <div key={r.id} className="card-base">
              <div className="p-4">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-4 h-4 text-blue-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-0.5">
                      <p className="text-sm font-medium text-foreground">{r.name}</p>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground">{type}</span>
                      <div className={clsx('flex items-center gap-1 text-[10px]', STATUS_COLOR[r.status] ?? 'text-muted-foreground')}>
                        <StatusIcon className={clsx('w-3 h-3', r.status === 'generating' && 'animate-spin')} />
                        {r.status}
                      </div>
                    </div>
                    {r.description && <p className="text-xs text-muted-foreground">{r.description}</p>}
                    <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                      <span>{new Date(r.created_at).toLocaleString()}</span>
                      {r.completed_at && (
                        <><span>·</span><span>completed {new Date(r.completed_at).toLocaleString()}</span></>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {r.status === 'completed' && (
                      <button onClick={() => setExpanded(isExpanded ? null : r.id)}
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded text-muted-foreground hover:text-foreground transition-colors">
                        {isExpanded ? 'Hide' : 'View'}
                      </button>
                    )}
                    {canGenerate && (
                      <button onClick={() => handleDelete(r.id)} disabled={deleting === r.id}
                        className="text-muted-foreground hover:text-red-400 transition-colors disabled:opacity-40">
                        {deleting === r.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded summary */}
                {isExpanded && r.status === 'completed' && summary && (
                  <div className="mt-3 p-3 rounded-lg grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs"
                    style={{ background: 'hsl(230 15% 10%)' }}>
                    {[
                      { label: 'Open Threats',       value: summary.open_threats },
                      { label: 'Critical Threats',   value: summary.critical_threats },
                      { label: 'Open Vulns',         value: summary.open_vulnerabilities },
                      { label: 'Critical Vulns',     value: summary.critical_vulnerabilities },
                      { label: 'Compliance Score',   value: summary.avg_compliance_score != null ? `${summary.avg_compliance_score}%` : undefined },
                      { label: 'Frameworks',         value: summary.compliance_frameworks },
                      { label: 'Active Policies',    value: summary.active_policies },
                      { label: 'Pending Exceptions', value: summary.pending_exceptions },
                    ].filter(i => i.value != null).map(({ label, value }) => (
                      <div key={label} className="text-center">
                        <p className="text-sm font-bold text-foreground">{String(value)}</p>
                        <p className="text-[10px] text-muted-foreground">{label}</p>
                      </div>
                    ))}
                  </div>
                )}
                {isExpanded && r.error && (
                  <p className="mt-2 text-xs text-red-400">Error: {r.error}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
