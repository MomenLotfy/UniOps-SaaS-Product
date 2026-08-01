import { useState, useMemo } from 'react';
import { useApi } from '@/hooks/use-api';
import { clsx } from 'clsx';
import {
  FileText, Plus, RefreshCw, Filter, Loader2, Trash2, Download, CheckCircle, AlertTriangle, Clock,
  Calendar, Mail, Users, Settings, Zap, Shield, Activity, Database, Globe, Key, Eye, MoreVertical,
  ChevronDown, Search, X, DownloadCloud, Send, Clock as ClockIcon, BarChart, List, FileJson,
  FileSpreadsheet, FileText as FileTextIcon, Eye as EyeIcon
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

// Report templates definitions
const REPORT_TEMPLATES = [
  { value: 'executive_security_report', label: 'Executive Security Report', category: 'executive', icon: 'Shield', description: 'High-level security posture and risk assessment' },
  { value: 'vulnerability_report', label: 'Vulnerability Report', category: 'security', icon: 'AlertTriangle', description: 'Detailed vulnerability assessment' },
  { value: 'threat_intelligence_report', label: 'Threat Intelligence Report', category: 'security', icon: 'Eye', description: 'Current threats and attack patterns' },
  { value: 'repository_security_report', label: 'Repository Security Report', category: 'security', icon: 'FileCode', description: 'Repository scan findings' },
  { value: 'asset_inventory_report', label: 'Asset Inventory Report', category: 'infrastructure', icon: 'Database', description: 'Complete asset inventory' },
  { value: 'kubernetes_security_report', label: 'Kubernetes Security Report', category: 'infrastructure', icon: 'Activity', description: 'K8s cluster security assessment' },
  { value: 'security_posture_report', label: 'Security Posture Report', category: 'compliance', icon: 'Activity', description: 'Overall security posture score' },
  { value: 'compliance_report', label: 'Compliance Report', category: 'compliance', icon: 'CheckSquare', description: 'Compliance status across frameworks' },
  { value: 'policy_compliance_report', label: 'Policy Compliance Report', category: 'compliance', icon: 'FileText', description: 'Security policy adherence' },
  { value: 'exception_report', label: 'Exception Report', category: 'operational', icon: 'FileText', description: 'Security exceptions with status' },
  { value: 'remediation_progress_report', label: 'Remediation Progress Report', category: 'operational', icon: 'Wrench', description: 'Remediation progress and metrics' },
  { value: 'sbom_report', label: 'SBOM Report', category: 'operational', icon: 'Layers', description: 'Software Bill of Materials' },
  { value: 'container_image_report', label: 'Container Image Report', category: 'infrastructure', icon: 'Box', description: 'Container image security scan' },
  { value: 'risk_trend_report', label: 'Risk Trend Report', category: 'executive', icon: 'TrendingUp', description: 'Security risk trends over time' },
  { value: 'attack_surface_report', label: 'Attack Surface Report', category: 'executive', icon: 'Target', description: 'Attack surface analysis' },
  { value: 'license_compliance_report', label: 'License Compliance Report', category: 'compliance', icon: 'BookOpen', description: 'Software license audit' },
  { value: 'cloud_security_report', label: 'Cloud Security Report', category: 'infrastructure', icon: 'Cloud', description: 'Cloud infrastructure security' },
  { value: 'iam_report', label: 'IAM Report', category: 'security', icon: 'Users', description: 'Identity and access management audit' },
  { value: 'secrets_exposure_report', label: 'Secrets Exposure Report', category: 'security', icon: 'Key', description: 'Detected secrets and exposure' },
  { value: 'audit_report', label: 'Audit Report', category: 'operational', icon: 'FileText', description: 'Comprehensive security audit' },
];

const STATUS_ICON: Record<string, React.ElementType> = {
  pending: Clock,
  generating: Loader2,
  completed: CheckCircle,
  failed: AlertTriangle,
  scheduled: Calendar,
};
const STATUS_COLOR: Record<string, string> = {
  pending: 'text-blue-400',
  generating: 'text-blue-400',
  completed: 'text-green-400',
  failed: 'text-red-400',
  scheduled: 'text-purple-400',
};

const CATEGORY_COLORS: Record<string, string> = {
  executive: 'text-purple-400 bg-purple-500/10',
  security: 'text-orange-400 bg-orange-500/10',
  infrastructure: 'text-cyan-400 bg-cyan-500/10',
  compliance: 'text-green-400 bg-green-500/10',
  operational: 'text-yellow-400 bg-yellow-500/10',
};

// Types
interface Report {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  template: string;
  status: string;
  format: string;
  created_by: string;
  parameters: Record<string, any>;
  summary: Record<string, any>;
  findings: Record<string, any>;
  metrics: Record<string, any>;
  charts: Record<string, any>;
  period_start: string | null;
  period_end: string | null;
  completed_at: string | null;
  error: string | null;
  is_scheduled: boolean;
  schedule_cron: string | null;
  schedule_timezone: string | null;
  next_run_at: string | null;
  last_run_at: string | null;
  recipients: string[];
  created_at: string;
  updated_at: string;
}

interface ReportListResponse {
  data: Report[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface ReportTemplateInfo {
  key: string;
  name: string;
  description: string;
  category: string;
  icon?: string;
}

// Skeleton Component
function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// Template Icon Component
function TemplateIcon({ template }: { template: string }) {
  const templateInfo = REPORT_TEMPLATES.find(t => t.value === template);
  const iconClass = CATEGORY_COLORS[templateInfo?.category || 'security'] + ' w-3 h-3';

  switch (templateInfo?.icon) {
    case 'Shield': return <Shield className={iconClass} />;
    case 'AlertTriangle': return <AlertTriangle className={iconClass} />;
    case 'Eye': return <Eye className={iconClass} />;
    case 'FileCode': return <FileTextIcon className={iconClass} />;
    case 'Database': return <Database className={iconClass} />;
    case 'Activity': return <Activity className={iconClass} />;
    case 'CheckSquare': return <CheckCircle className={iconClass} />;
    case 'FileText': return <FileTextIcon className={iconClass} />;
    case 'Wrench': return <Settings className={iconClass} />;
    case 'Layers': return <List className={iconClass} />;
    case 'Box': return <FileSpreadsheet className={iconClass} />;
    case 'TrendingUp': return <BarChart className={iconClass} />;
    case 'Target': return <Zap className={iconClass} />;
    case 'BookOpen': return <FileSpreadsheet className={iconClass} />;
    case 'Cloud': return <Globe className={iconClass} />;
    case 'Users': return <Users className={iconClass} />;
    case 'Key': return <Key className={iconClass} />;
    default: return <FileText className={iconClass} />;
  }
}

// Report Generate Modal
function GenerateReportModal({
  onClose,
  onGenerated,
  templates,
}: {
  onClose: () => void;
  onGenerated: () => void;
  templates: ReportTemplateInfo[];
}) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    template: 'executive_security_report',
    name: '',
    description: '',
    format: 'json',
    include_charts: true,
    include_findings: true,
    schedule_cron: '',
    recipients: '',
  });
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [selectedTemplate, setSelectedTemplate] = useState<string>('executive_security_report');

  const categoryTemplates = useMemo(() => {
    if (activeCategory === 'all') return templates;
    return templates.filter(t => t.category === activeCategory);
  }, [templates, activeCategory]);

  const handleGenerate = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const data = {
        template: form.template,
        name: form.name,
        description: form.description,
        format: form.format,
        include_charts: form.include_charts,
        include_findings: form.include_findings,
        parameters: form.schedule_cron ? { schedule_cron: form.schedule_cron } : {},
        schedule_cron: form.schedule_cron || undefined,
        recipients: form.recipients.split(',').map(r => r.trim()).filter(Boolean),
      };
      await fetch('/api/v1/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      onGenerated();
      onClose();
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl mx-4 rounded-xl border shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <h3 className="text-base font-semibold text-foreground">Generate Report</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-white/10">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Template List */}
          <div className="w-1/3 border-r border-white/10 p-3 overflow-y-auto">
            <div className="text-xs font-medium text-muted-foreground mb-3">Categories</div>
            <div className="space-y-1 mb-4">
              <button
                onClick={() => setActiveCategory('all')}
                className={clsx('w-full px-2 py-1.5 text-xs rounded text-left', activeCategory === 'all' ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:bg-white/5')}
              >
                All Templates
              </button>
              {['executive', 'security', 'infrastructure', 'compliance', 'operational'].map(cat => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={clsx('w-full px-2 py-1.5 text-xs rounded text-left capitalize', activeCategory === cat ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:bg-white/5')}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="text-xs font-medium text-muted-foreground mb-2">Templates</div>
            <div className="space-y-1">
              {categoryTemplates.map(t => (
                <button
                  key={t.key}
                  onClick={() => {
                    setSelectedTemplate(t.key);
                    setForm(f => ({ ...f, template: t.key, name: t.name }));
                  }}
                  className={clsx('w-full px-2 py-2 text-xs rounded text-left border transition-colors', selectedTemplate === t.key ? 'border-blue-500 bg-blue-500/10' : 'border-white/5 hover:border-white/10')}
                >
                  <div className="flex items-center gap-2">
                    <FileText className="w-3 h-3 text-muted-foreground" />
                    <span className="text-foreground">{t.name}</span>
                  </div>
                  <p className="mt-0.5 text-[10px] text-muted-foreground line-clamp-2">{t.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Form */}
          <div className="flex-1 p-5 overflow-y-auto">
            <div className="space-y-4">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Report Name *</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2 text-sm rounded-lg border outline-none"
                  style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
                  placeholder="e.g. Q3 2026 Security Review"
                />
              </div>

              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Description</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  className="w-full px-3 py-2 text-sm rounded-lg border outline-none resize-none"
                  style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
                  rows={2}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Format</label>
                  <select
                    value={form.format}
                    onChange={e => setForm(f => ({ ...f, format: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border outline-none"
                    style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
                  >
                    <option value="json">JSON</option>
                    <option value="csv">CSV</option>
                    <option value="excel">Excel</option>
                    <option value="pdf">PDF</option>
                    <option value="html">HTML</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Send to Email</label>
                  <input
                    value={form.recipients}
                    onChange={e => setForm(f => ({ ...f, recipients: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border outline-none"
                    style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
                    placeholder="user@company.com"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 text-xs text-foreground cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.include_charts}
                    onChange={e => setForm(f => ({ ...f, include_charts: e.target.checked }))}
                    className="rounded text-blue-500 focus:ring-blue-500"
                  />
                  Include Charts & Visualizations
                </label>
              </div>

              <div className="border-t border-white/10 pt-4">
                <label className="text-xs text-muted-foreground mb-1 block">Schedule (Optional)</label>
                <div className="flex gap-2">
                  <input
                    value={form.schedule_cron}
                    onChange={e => setForm(f => ({ ...f, schedule_cron: e.target.value }))}
                    className="flex-1 px-3 py-2 text-sm rounded-lg border outline-none"
                    style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
                    placeholder="0 0 * * * (Cron expression)"
                  />
                </div>
                <p className="text-[10px] text-muted-foreground mt-1">
                  Enter a cron expression to schedule recurring reports (e.g., "0 0 * * *" for daily at midnight)
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-white/10 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}
          >
            Cancel
          </button>
          <button
            onClick={handleGenerate}
            disabled={saving || !form.name.trim()}
            className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            {saving ? 'Generating...' : 'Generate Report'}
          </button>
        </div>
      </div>
    </div>
  );
}

// Export Modal
function ExportModal({
  report,
  onClose,
}: {
  report: Report;
  onClose: () => void;
}) {
  const [format, setFormat] = useState('json');

  const handleExport = async () => {
    const response = await fetch(`/api/v1/reports/${report.id}/download?format=${format}`);
    if (response.ok) {
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${report.template}-${report.id.slice(0, 8)}.${format === 'json' ? 'json' : format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      onClose();
    }
  };

  const handleEmail = async () => {
    const response = await fetch('/api/v1/reports/email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        report_id: report.id,
        recipients: ['user@company.com'],
        format: format,
      }),
    });
    if (response.ok) {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md mx-4 rounded-xl border shadow-2xl"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <h3 className="text-base font-semibold text-foreground">Export Report</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-white/10">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Format</label>
            <select
              value={format}
              onChange={e => setFormat(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border outline-none"
              style={{ background: 'hsl(230 15% 12%)', borderColor: 'hsl(230 15% 20%)', color: 'white' }}
            >
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
              <option value="excel">Excel</option>
              <option value="pdf">PDF</option>
              <option value="html">HTML</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Destination</label>
            <div className="flex gap-2">
              <button
                onClick={handleExport}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm rounded-lg border border-white/10 hover:bg-white/5 transition-colors"
              >
                <Download className="w-4 h-4" /> Download
              </button>
              <button
                onClick={handleEmail}
                className="flex items-center justify-center gap-2 px-3 py-2 text-sm rounded-lg border border-white/10 hover:bg-white/5 transition-colors"
              >
                <Send className="w-4 h-4" /> Email
              </button>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-white/10 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// Report Preview Modal
function ReportPreviewModal({
  report,
  onClose,
}: {
  report: Report;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-4xl mx-4 rounded-xl border shadow-2xl flex flex-col max-h-[90vh]"
        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 16%)' }}>
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <h3 className="text-base font-semibold text-foreground">{report.name}</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-white/10">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="p-4 rounded-lg bg-white/5 border border-white/10">
              <p className="text-[10px] text-muted-foreground mb-1">Total Vulnerabilities</p>
              <p className="text-2xl font-bold text-foreground">{report.findings?.vulnerabilities?.total || 0}</p>
            </div>
            <div className="p-4 rounded-lg bg-white/5 border border-white/10">
              <p className="text-[10px] text-muted-foreground mb-1">Open Vulnerabilities</p>
              <p className="text-2xl font-bold text-foreground">{report.findings?.vulnerabilities?.open || 0}</p>
            </div>
            <div className="p-4 rounded-lg bg-white/5 border border-white/10">
              <p className="text-[10px] text-muted-foreground mb-1">Total Threats</p>
              <p className="text-2xl font-bold text-foreground">{report.findings?.threats?.total || 0}</p>
            </div>
            <div className="p-4 rounded-lg bg-white/5 border border-white/10">
              <p className="text-[10px] text-muted-foreground mb-1">Active Policies</p>
              <p className="text-2xl font-bold text-foreground">{report.findings?.policies?.active || 0}</p>
            </div>
          </div>

          {report.metrics && Object.keys(report.metrics).length > 0 && (
            <div className="space-y-4">
              <h4 className="text-sm font-medium text-foreground">Metrics</h4>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(report.metrics).map(([key, value]) => (
                  <div key={key} className="p-3 rounded-lg bg-white/5 border border-white/10">
                    <p className="text-[10px] text-muted-foreground capitalize mb-1">{key}</p>
                    <p className="text-lg font-bold text-foreground">{String(value)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.findings && (
            <div className="space-y-4 mt-6">
              <h4 className="text-sm font-medium text-foreground">Findings</h4>
              <div className="p-4 rounded-lg bg-white/5 border border-white/10 max-h-64 overflow-y-auto">
                <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                  {JSON.stringify(report.findings, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-white/10 flex justify-end gap-2">
          <button
            onClick={() => { onClose(); }}
            className="px-4 py-2 text-sm rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// Main Reports Component
export default function Reports() {
  const { toast } = useToast();
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [showExport, setShowExport] = useState<Report | null>(null);
  const [showPreview, setShowPreview] = useState<Report | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  // Query params
  const qs = useMemo(() => {
    const params = new URLSearchParams({ page: page.toString(), page_size: pageSize.toString() });
    if (typeFilter) params.set('template', typeFilter);
    if (statusFilter) params.set('status', statusFilter);
    if (search) params.set('search', search);
    return params.toString();
  }, [typeFilter, statusFilter, search, page, pageSize]);

  // Fetch reports and templates
  const { data: rawList, loading: loadingList, refetch: refetchList } = useApi<ReportListResponse>(`/reports?${qs}`);
  const { data: rawTemplates, loading: loadingTemplates } = useApi<ReportTemplateInfo[]>(`/reports/templates`);

  const reports: Report[] = rawList?.data ?? (Array.isArray(rawList) ? rawList : []);
  const templates: ReportTemplateInfo[] = rawTemplates?.data ?? rawTemplates ?? REPORT_TEMPLATES;
  const total = rawList?.total ?? reports.length;
  const pages = rawList?.pages ?? 1;

  // Get report template info
  const getTemplateInfo = (template: string): ReportTemplateInfo => {
    const info = templates.find(t => t.key === template);
    return info || { key: template, name: template, description: '', category: 'security' };
  };

  // Filter reports by category
  const filteredReports = useMemo(() => {
    let result = reports;
    if (categoryFilter !== 'all') {
      result = result.filter(r => getTemplateInfo(r.template).category === categoryFilter);
    }
    if (search) {
      const searchLower = search.toLowerCase();
      result = result.filter(r =>
        r.name.toLowerCase().includes(searchLower) ||
        r.description?.toLowerCase().includes(searchLower) ||
        r.template.toLowerCase().includes(searchLower)
      );
    }
    return result;
  }, [reports, categoryFilter, search]);

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await fetch(`/api/v1/reports/${id}`, { method: 'DELETE' });
      refetchList();
    } catch (e) {
      toast?.({ title: 'Delete Failed', variant: 'destructive' });
    } finally {
      setDeleting(null);
    }
  };

  const handleRegenerate = async (id: string) => {
    setRegenerating(id);
    try {
      await fetch(`/api/v1/reports/${id}/regenerate`, { method: 'POST' });
      refetchList();
    } catch (e) {
      toast?.({ title: 'Regenerate Failed', variant: 'destructive' });
    } finally {
      setRegenerating(null);
    }
  };

  const handleGenerate = () => {
    setShowCreate(true);
  };

  const filteredTemplates = useMemo(() => {
    if (categoryFilter === 'all') return templates;
    return templates.filter(t => t.category === categoryFilter);
  }, [templates, categoryFilter]);

  // Empty state
  if (loadingList && reports.length === 0) {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-bold text-foreground">Reports</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Loading reports...</p>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-24" />)}
        </div>
      </div>
    );
  }

  // Empty state - no reports
  if (!loadingList && filteredReports.length === 0) {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-bold text-foreground">Reports</h1>
          <p className="text-xs text-muted-foreground mt-0.5">No reports found</p>
        </div>
        <div className="card-base py-12 text-center">
          <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-sm font-medium text-foreground mb-1">No reports yet</p>
          <p className="text-xs text-muted-foreground mb-4">
            {templates.length > 0 ? 'Select a template below to generate your first report.' : 'Report generation is not available.'}
          </p>
          <button
            onClick={handleGenerate}
            disabled={templates.length === 0}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Generate Report
          </button>
        </div>
      </div>
    );
  }

  // Main render
  return (
    <div className="space-y-4">
      {showCreate && (
        <GenerateReportModal
          onClose={() => setShowCreate(false)}
          onGenerated={refetchList}
          templates={templates}
        />
      )}
      {showExport && (
        <ExportModal
          report={showExport}
          onClose={() => setShowExport(null)}
        />
      )}
      {showPreview && (
        <ReportPreviewModal
          report={showPreview}
          onClose={() => setShowPreview(null)}
        />
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-foreground">Reports</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {total} report{total !== 1 ? 's' : ''} generated
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={refetchList}
            disabled={loadingList}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            style={{ borderColor: 'hsl(230 15% 20%)' }}
          >
            <RefreshCw className={clsx('w-3.5 h-3.5', loadingList && 'animate-spin')} />
            Refresh
          </button>
          <button
            onClick={handleGenerate}
            disabled={templates.length === 0 || loadingList}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="w-3.5 h-3.5" />
            Generate Report
          </button>
        </div>
      </div>

      {/* Category Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-muted-foreground">Categories:</span>
        <button
          onClick={() => setCategoryFilter('all')}
          className={clsx(
            'px-2.5 py-1 rounded text-xs transition-colors',
            categoryFilter === 'all' ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          All
        </button>
        {['executive', 'security', 'infrastructure', 'compliance', 'operational'].map(cat => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={clsx(
              'px-2.5 py-1 rounded text-xs capitalize transition-colors',
              categoryFilter === cat ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="text-muted-foreground">Filters:</span>
          <button
            onClick={() => setStatusFilter('')}
            className={clsx(
              'px-2.5 py-1 rounded transition-colors',
              statusFilter === '' ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            All Status
          </button>
          {['pending', 'generating', 'completed', 'failed', 'scheduled'].map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={clsx(
                'px-2.5 py-1 rounded capitalize transition-colors',
                statusFilter === s ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search reports..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9 pr-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm text-foreground focus:ring-2 focus:ring-blue-500/50 outline-none"
          />
        </div>
      </div>

      {/* Page Size */}
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted-foreground">Show:</span>
        <select
          value={pageSize}
          onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}
          className="px-2 py-1 bg-white/5 border border-white/10 rounded text-sm outline-none"
        >
          <option value={50}>50 per page</option>
          <option value={100}>100 per page</option>
          <option value={200}>200 per page</option>
        </select>
      </div>

      {/* Report List */}
      <div className="card-base">
        <div className="space-y-2">
          {loadingList ? (
            [...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
          ) : filteredReports.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No reports found matching your filters
            </div>
          ) : filteredReports.map((r) => {
            const StatusIcon = STATUS_ICON[r.status] ?? Clock;
            const isExpanded = expanded === r.id;
            const templateInfo = getTemplateInfo(r.template);

            return (
              <div key={r.id} className={clsx(
                'p-4 rounded-lg border transition-all',
                isExpanded ? 'border-blue-500 bg-blue-500/5' : 'border-white/10 hover:border-white/20'
              )}>
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
                    <TemplateIcon template={r.template} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <p className="text-sm font-medium text-foreground truncate max-w-[200px]">{r.name}</p>
                      <span className={clsx(
                        'text-[10px] px-1.5 py-0.5 rounded capitalize',
                        CATEGORY_COLORS[templateInfo.category] || 'bg-white/5 text-muted-foreground'
                      )}>
                        {templateInfo.category}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground border border-white/10">
                        {r.template}
                      </span>
                      <div className={clsx('flex items-center gap-1 text-[10px]', STATUS_COLOR[r.status] ?? 'text-muted-foreground')}>
                        <StatusIcon className={clsx('w-3 h-3', r.status === 'generating' && 'animate-spin')} />
                        {r.status}
                      </div>
                    </div>
                    {r.description && <p className="text-xs text-muted-foreground mb-1">{r.description}</p>}
                    <div className="flex items-center gap-2 text-[10px] text-muted-foreground flex-wrap">
                      <span>{new Date(r.created_at).toLocaleDateString()}</span>
                      {r.completed_at && (
                        <><span className="text-muted-foreground">•</span>
                          <span>completed {new Date(r.completed_at).toLocaleDateString()}</span>
                        </>
                      )}
                      {r.is_scheduled && (
                        <><span className="text-muted-foreground">•</span>
                          <span className="text-purple-400 flex items-center gap-0.5">
                            <Calendar className="w-2.5 h-2.5" /> scheduled
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {r.status === 'completed' && (
                      <button
                        onClick={() => setShowPreview(r)}
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded text-blue-400 hover:bg-blue-500/10 transition-colors"
                        title="Preview Report"
                      >
                        <EyeIcon className="w-3.5 h-3.5" /> Preview
                      </button>
                    )}
                    <button
                      onClick={() => setShowExport(r)}
                      className="flex items-center gap-1 text-xs px-2 py-1 rounded text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
                      title="Export Report"
                    >
                      <Download className="w-3.5 h-3.5" />
                    </button>
                    {r.status !== 'generating' && (
                      <button
                        onClick={() => handleRegenerate(r.id)}
                        disabled={regenerating === r.id}
                        className="flex items-center gap-1 text-xs px-2 py-1 rounded text-muted-foreground hover:text-blue-400 transition-colors disabled:opacity-50"
                        title="Regenerate Report"
                      >
                        {regenerating === r.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(r.id)}
                      disabled={deleting === r.id}
                      className="text-muted-foreground hover:text-red-400 transition-colors disabled:opacity-50"
                      title="Delete Report"
                    >
                      {deleting === r.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Expanded Summary */}
                {isExpanded && r.status === 'completed' && (
                  <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <SummaryCard label="Open Threats" value={r.findings?.threats?.open || r.summary?.open_threats} />
                    <SummaryCard label="Open Vulnerabilities" value={r.findings?.vulnerabilities?.open || r.summary?.open_vulnerabilities} />
                    <SummaryCard label="Critical Findings" value={r.findings?.threats?.critical || r.findings?.vulnerabilities?.critical} />
                    <SummaryCard label="Active Policies" value={r.findings?.policies?.active || r.summary?.active_policies} />
                  </div>
                )}

                {/* Error */}
                {isExpanded && r.error && (
                  <div className="mt-3 p-3 rounded bg-red-500/5 border border-red-500/20">
                    <p className="text-xs text-red-400">Error: {r.error}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/10">
            <span className="text-xs text-muted-foreground">
              Page {page} of {pages} ({total} items)
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-2 py-1 text-xs rounded border border-white/10 text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white/5"
              >
                <ChevronDown className="w-3.5 h-3.5 rotate-90" />
              </button>
              <button
                onClick={() => setPage(Math.min(pages, page + 1))}
                disabled={page === pages}
                className="px-2 py-1 text-xs rounded border border-white/10 text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white/5"
              >
                <ChevronDown className="w-3.5 h-3.5 -rotate-90" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Summary Card Component
function SummaryCard({ label, value }: { label: string; value?: any }) {
  return (
    <div className="p-3 rounded-lg bg-white/5 border border-white/5">
      <p className="text-[10px] text-muted-foreground mb-1">{label}</p>
      <p className="text-lg font-bold text-foreground">{String(value ?? 0)}</p>
    </div>
  );
}
