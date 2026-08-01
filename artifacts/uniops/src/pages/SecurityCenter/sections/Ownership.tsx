import {
  useState, useCallback, useEffect, useMemo, memo, React,
} from 'react';
import {
  Users, Search, Filter, Edit3, Check, X, ChevronDown, Building2, User, GitBranch,
  Server, AlertTriangle, Bug, Cloud, Layers, Database, Shield, Zap, Package,
  ChevronRight, Download, Upload, Plus, MoreVertical, Clock, Target, TrendingUp,
  Activity, Eye, Settings, Lock, Globe, Box, Layers as LayersIcon, Key,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost, apiPatch } from '@/hooks/use-api';
import { usePermissions } from '@/hooks/use-permissions';
import { canWriteSecurity } from '@/lib/permissions';

// ─── Constants ────────────────────────────────────────────────────────────────

const RESOURCE_ICONS: Record<string, React.ElementType> = {
  repository:            GitBranch,
  organization:          Building2,
  project:               Box,
  application:           LayersIcon,
  service:               Server,
  microservice:          Server,
  container_image:       Package,
  asset:                 Server,
  virtual_machine:       Server,
  cloud_account:         Cloud,
  kubernetes_cluster:    Layers,
  namespace:             Layers,
  deployment:            Layers,
  pod:                   Box,
  secret:                Key,
  database:              Database,
  storage_bucket:        Server,
  load_balancer:         Server,
  policy:                Shield,
  compliance_control:    Shield,
  exception:             AlertTriangle,
  threat:                AlertTriangle,
  vulnerability:         Bug,
  remediation_task:      Activity,
  sbom:                  Package,
};

const OWNER_TYPES = [
  { value: 'user', label: 'User', icon: User },
  { value: 'team', label: 'Team', icon: Users },
  { value: 'department', label: 'Department', icon: Building2 },
  { value: 'business_unit', label: 'Business Unit', icon: Building2 },
  { value: 'service_owner', label: 'Service Owner', icon: User },
  { value: 'application_owner', label: 'App Owner', icon: User },
  { value: 'security_owner', label: 'Security Team', icon: Shield },
  { value: 'infrastructure_owner', label: 'Infra Owner', icon: Server },
  { value: 'platform_team', label: 'Platform Team', icon: Users },
];

const CRITICALITY_OPTIONS = [
  { value: 'critical', label: 'Critical', color: 'text-red-400' },
  { value: 'high', label: 'High', color: 'text-orange-400' },
  { value: 'medium', label: 'Medium', color: 'text-yellow-400' },
  { value: 'low', label: 'Low', color: 'text-green-400' },
  { value: 'standard', label: 'Standard', color: 'text-blue-400' },
];

const ENVIRONMENT_OPTIONS = [
  { value: 'production', label: 'Production', color: 'text-red-400' },
  { value: 'staging', label: 'Staging', color: 'text-orange-400' },
  { value: 'development', label: 'Development', color: 'text-blue-400' },
  { value: 'testing', label: 'Testing', color: 'text-purple-400' },
  { value: 'unknown', label: 'Unknown', color: 'text-muted-foreground' },
];

const RISK_LEVEL_OPTIONS = [
  { value: 'critical', label: 'Critical', color: 'text-red-400' },
  { value: 'high', label: 'High', color: 'text-orange-400' },
  { value: 'medium', label: 'Medium', color: 'text-yellow-400' },
  { value: 'low', label: 'Low', color: 'text-green-400' },
  { value: 'none', label: 'None', color: 'text-muted-foreground' },
];

const SLA_STATUS_OPTIONS = [
  { value: 'compliant', label: 'Compliant', color: 'text-green-400' },
  { value: 'at_risk', label: 'At Risk', color: 'text-orange-400' },
  { value: 'violation', label: 'Violation', color: 'text-red-400' },
];

// ─── Types ────────────────────────────────────────────────────────────────────

interface OwnershipEntry {
  id: string;
  tenant_id: string;
  entity_type: string;
  entity_id: string;
  owner: string | null;
  owner_type: string;
  team: string | null;
  department: string | null;
  business_unit: string | null;
  backup_owner: string | null;
  escalation_chain: string[];
  business_criticality: string;
  environment: string;
  region: string | null;
  risk_level: string;
  sla_status: string;
  cloud_provider: string | null;
  cloud_account_id: string | null;
  cluster_name: string | null;
  namespace: string | null;
  last_updated: string | null;
  is_assigned: boolean;
  assignment_method: string;
  entity_name?: string;
}

interface ResourceSummary {
  entity_type: string;
  count: number;
  owned: number;
  unassigned: number;
}

interface CoverageData {
  by_team: { team: string; count: number; coverage_percent: number }[];
  by_department: { department: string; count: number; coverage_percent: number }[];
  by_environment: { environment: string; count: number; owned: number }[];
  by_cloud_provider: { provider: string; count: number; owned: number }[];
  by_resource_type: { resource_type: string; count: number; owned: number }[];
}

interface OwnerProfile {
  owner: string;
  owner_type: string;
  email?: string;
  team?: string;
  department?: string;
  business_unit?: string;
  total_resources: number;
  total_vulnerabilities: number;
  total_threats: number;
  total_remediations: number;
  compliance_violations: number;
  avg_mttr_hours?: number;
  sla_compliance_rate?: number;
  critical_risk_count: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  repository_ownership: { name: string; id: string; team: string; environment: string; risk_level: string }[];
  infrastructure_ownership: { name: string; id: string; type: string; team: string; environment: string; cloud_provider: string | null }[];
  application_ownership: { name: string; id: string; type: string; team: string; environment: string }[];
  overdue_tasks: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function getEntityName(entityType: string, id: string, nameOverride?: string): string {
  if (nameOverride) return nameOverride;
  const parts = id.split('-');
  if (parts.length > 1 && parts[0] && parts[1]) {
    return `${parts[0]}-${parts[1]}`;
  }
  return id;
}

// ─── Components ───────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// ─── Summary Card ─────────────────────────────────────────────────────────────

function SummaryCard({
  label, value, sub, icon: Icon, color = 'text-blue-400', onClick, loading,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  color?: string;
  onClick?: () => void;
  loading?: boolean;
}) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-500/10',
    green: 'bg-green-500/10',
    red: 'bg-red-500/10',
    orange: 'bg-orange-500/10',
    purple: 'bg-purple-500/10',
    yellow: 'bg-yellow-500/10',
    cyan: 'bg-cyan-500/10',
    indigo: 'bg-indigo-500/10',
    slate: 'bg-slate-500/10',
  };

  return (
    <div
      onClick={onClick}
      className={clsx(
        'card-base p-4 flex items-center gap-3 cursor-pointer transition-all',
        'hover:scale-[1.01] hover:border-white/20',
        loading ? '' : 'cursor-pointer',
      )}
    >
      <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', colors[color.split('-')[0]] || 'bg-blue-500/10')}>
        <Icon className={clsx('w-5 h-5', color)} />
      </div>
      <div>
        {loading ? (
          <>
            <Skeleton className="h-6 w-12 mb-1" />
            <Skeleton className="h-3 w-20" />
          </>
        ) : (
          <>
            <p className={clsx('text-2xl font-bold tabular-nums', color)}>{value}</p>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</p>
            {sub && <p className="text-[9px] text-muted-foreground/60 mt-0.5">{sub}</p>}
          </>
        )}
      </div>
    </div>
  );
}

// ─── Filter Pill ──────────────────────────────────────────────────────────────

function FilterPill({
  label, active, onClick, color,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  color?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'px-3 py-1 rounded-md text-xs font-medium transition-colors whitespace-nowrap',
        active
          ? color || 'bg-blue-600 text-white'
          : 'text-muted-foreground hover:text-foreground hover:bg-white/5',
      )}
    >
      {label}
    </button>
  );
}

// ─── Badge Component ──────────────────────────────────────────────────────────

function StatusBadge({
  value, options, colorOverride,
}: {
  value: string;
  options: { value: string; label: string; color: string }[];
  colorOverride?: string;
}) {
  const option = options.find(o => o.value === value) || options[0];
  const color = colorOverride || option.color;
  return (
    <span className={clsx('text-[10px] px-2 py-0.5 rounded-full border font-medium capitalize', color, 'border-transparent bg-opacity-10')}>
      {option.label}
    </span>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Ownership() {
  const { role } = usePermissions();
  const canWrite = canWriteSecurity(role);

  // State
  const [search, setSearch] = useState('');
  const [entityType, setEntityType] = useState<string>('');
  const [ownerFilter, setOwnerFilter] = useState('');
  const [teamFilter, setTeamFilter] = useState('');
  const [environmentFilter, setEnvironmentFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [page, setPage] = useState(1);
  const [detailsPanel, setDetailsPanel] = useState<OwnershipEntry | null>(null);
  const [ownerPanel, setOwnerPanel] = useState<{ owner: string; show: boolean } | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [showExport, setShowExport] = useState(false);

  // Constants
  const PAGE_SIZE = 50;

  // Build query params
  const params = useMemo(() => {
    const p = new URLSearchParams();
    if (entityType) p.set('entity_type', entityType);
    if (ownerFilter) p.set('owner', ownerFilter);
    if (teamFilter) p.set('team', teamFilter);
    if (environmentFilter) p.set('environment', environmentFilter);
    if (riskFilter) p.set('risk_level', riskFilter);
    p.set('limit', PAGE_SIZE.toString());
    p.set('offset', ((page - 1) * PAGE_SIZE).toString());
    return p.toString();
  }, [entityType, ownerFilter, teamFilter, environmentFilter, riskFilter, page]);

  // Data fetch
  const { data: raw, loading, refetch } = useApi<any>(`/ownership?${params}`);
  const { data: summaryRaw, refetch: refetchSummary } = useApi<any>('/ownership/summary');
  const { data: coverageRaw, refetch: refetchCoverage } = useApi<any>('/ownership/coverage');
  const { data: resourceTypesRaw } = useApi<any>('/ownership/resource-types');

  const rows: OwnershipEntry[] = useMemo(() => {
    const data = raw?.data ?? raw;
    return Array.isArray(data) ? data : [];
  }, [raw]);

  const summary = useMemo(() => {
    const data = summaryRaw?.data ?? summaryRaw;
    return data || {
      total_resources: 0,
      owned_resources: 0,
      unassigned_resources: 0,
      teams: 0,
      departments: 0,
      security_owners: 0,
      repositories_covered: 0,
      clusters_covered: 0,
      sla_violations: 0,
      ownership_coverage_percent: 0,
    };
  }, [summaryRaw]);

  const coverage = useMemo(() => {
    const data = coverageRaw?.data ?? coverageRaw;
    return data || {
      total: 0,
      owned: 0,
      unassigned: 0,
      coverage_percent: 0,
      by_team: [],
      by_department: [],
      by_environment: [],
      by_cloud_provider: [],
      by_resource_type: [],
    };
  }, [coverageRaw]);

  const resourceTypes = useMemo(() => {
    const data = resourceTypesRaw?.data ?? resourceTypesRaw;
    return (data as Record<string, string>) || {};
  }, [resourceTypesRaw]);

  // Filtering
  const filtered = useMemo(() => {
    if (!search) return rows;
    const q = search.toLowerCase();
    return rows.filter(r =>
      (r.entity_id || '').toLowerCase().includes(q) ||
      (r.entity_name || '').toLowerCase().includes(q) ||
      (r.owner || '').toLowerCase().includes(q) ||
      (r.team || '').toLowerCase().includes(q) ||
      (r.department || '').toLowerCase().includes(q) ||
      (r.business_unit || '').toLowerCase().includes(q)
    );
  }, [rows, search]);

  const totalPages = Math.ceil(summary.total_resources / PAGE_SIZE);

  // Handlers
  const handleExport = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/ownership/export', {
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      const csv = await response.text();
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ownership_export_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setShowExport(false);
    } catch {
      // Fallback: use API client
    }
  }, []);

  const handleImport = useCallback(async (csvContent: string) => {
    try {
      await apiPost<{ data: any }>('/ownership/import', {
        content: csvContent,
        mapping_type: 'overwrite',
      });
      await refetch();
      await refetchSummary();
      setShowImport(false);
    } catch (err) {
      console.error('Import failed:', err);
    }
  }, [refetch, refetchSummary]);

  // Stats derived
  const coverageColor = useMemo(() => {
    if (summary.ownership_coverage_percent >= 80) return 'text-green-400';
    if (summary.ownership_coverage_percent >= 50) return 'text-yellow-400';
    return 'text-red-400';
  }, [summary]);

  // Render
  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-bold text-foreground flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Users className="w-4 h-4 text-blue-400" />
            </div>
            Ownership Management
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage accountability across {summary.total_resources || 'all'} resources
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowImport(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-white/5 border border-border text-muted-foreground hover:text-foreground hover:border-white/20 transition-colors"
          >
            <Upload className="w-3.5 h-3.5" /> Import
          </button>
          <button
            onClick={() => setShowExport(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-white/5 border border-border text-muted-foreground hover:text-foreground hover:border-white/20 transition-colors"
          >
            <Download className="w-3.5 h-3.5" /> Export
          </button>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors"
          >
            <svg className="w-3.5 h-3.5 animate-spin-slow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
              <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
              <path d="M16 21h5v-5" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <SummaryCard label="Total Resources" value={summary.total_resources} icon={Layers} color="text-foreground" loading={loading} />
        <SummaryCard label="Owned" value={summary.owned_resources} icon={Users} color="text-green-400" loading={loading} />
        <SummaryCard label="Unassigned" value={summary.unassigned_resources} icon={X} color="text-red-400" loading={loading} />
        <SummaryCard label="Coverage" value={`${summary.ownership_coverage_percent}%`} icon={Target} color={coverageColor} loading={loading} />
        <SummaryCard label="SLA Violations" value={summary.sla_violations} icon={AlertTriangle} color="text-orange-400" loading={loading} />
      </div>

      {/* Coverage Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Coverage by Environment */}
        <div className="card-base p-4">
          <div className="flex items-center gap-2 mb-3">
            <Cloud className="w-4 h-4 text-blue-400" />
            <h3 className="text-xs font-semibold text-foreground">Coverage by Environment</h3>
          </div>
          <div className="space-y-2">
            {coverage.by_environment.slice(0, 5).map(env => (
              <div key={env.environment} className="space-y-1">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-muted-foreground capitalize">{env.environment}</span>
                  <span className="text-foreground">{env.count} resources</span>
                </div>
                <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${(env.owned / (env.count || 1)) * 100}%` }}
                  />
                </div>
                <div className="flex justify-between text-[9px] text-muted-foreground/60">
                  <span>{env.owned} owned</span>
                  <span>{env.count - env.owned} unassigned</span>
                </div>
              </div>
            ))}
            {coverage.by_environment.length === 0 && (
              <p className="text-[10px] text-muted-foreground text-center py-4">No environment data</p>
            )}
          </div>
        </div>

        {/* Coverage by Cloud Provider */}
        <div className="card-base p-4">
          <div className="flex items-center gap-2 mb-3">
            <Cloud className="w-4 h-4 text-purple-400" />
            <h3 className="text-xs font-semibold text-foreground">Coverage by Provider</h3>
          </div>
          <div className="space-y-2">
            {coverage.by_cloud_provider.slice(0, 5).map(provider => (
              <div key={provider.provider} className="space-y-1">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-muted-foreground">{provider.provider || 'Unknown'}</span>
                  <span className="text-foreground">{provider.count} resources</span>
                </div>
                <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full"
                    style={{ width: `${(provider.owned / (provider.count || 1)) * 100}%` }}
                  />
                </div>
              </div>
            ))}
            {coverage.by_cloud_provider.length === 0 && (
              <p className="text-[10px] text-muted-foreground text-center py-4">No cloud provider data</p>
            )}
          </div>
        </div>

        {/* Coverage by Resource Type */}
        <div className="card-base p-4">
          <div className="flex items-center gap-2 mb-3">
            <LayersIcon className="w-4 h-4 text-indigo-400" />
            <h3 className="text-xs font-semibold text-foreground">Coverage by Type</h3>
          </div>
          <div className="space-y-2 max-h-32 overflow-y-auto custom-scrollbar">
            {coverage.by_resource_type.slice(0, 8).map(rtype => (
              <div key={rtype.resource_type} className="flex items-center justify-between text-[10px] p-1.5 rounded hover:bg-white/5">
                <div className="flex items-center gap-2 min-w-0">
                  {Object.entries(RESOURCE_ICONS).find(([k]) => k === rtype.resource_type)?.[1] ? (
                    <div className="w-4 h-4 text-muted-foreground flex-shrink-0">
                      {React.createElement(RESOURCE_ICONS[rtype.resource_type] || LayersIcon, { className: 'w-3 h-3' })}
                    </div>
                  ) : (
                    <div className="w-4 h-4 text-muted-foreground flex-shrink-0">
                      <LayersIcon className="w-3 h-3" />
                    </div>
                  )}
                  <span className="text-foreground truncate capitalize">{rtype.resource_type}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">{rtype.owned}/{rtype.count}</span>
                  <div className="w-12 h-1 bg-white/5 rounded-full overflow-hidden flex-shrink-0">
                    <div
                      className="h-full bg-indigo-500 rounded-full"
                      style={{ width: `${(rtype.owned / (rtype.count || 1)) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-64">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-white/5 border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/50"
            placeholder="Search resources, owners, teams..."
            value={search}
            onChange={e => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors',
            showFilters ? 'border-blue-500/40 text-blue-400 bg-blue-500/8' : 'border-border text-muted-foreground hover:text-foreground',
          )}
        >
          <Filter className="w-3.5 h-3.5" /> Filters
        </button>
      </div>

      {/* Extended Filters */}
      {showFilters && (
        <div className="card-base p-4 grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">Resource Type</label>
            <select
              value={entityType}
              onChange={e => {
                setEntityType(e.target.value);
                setPage(1);
              }}
              className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none"
            >
              <option value="">All Types</option>
              {Object.entries(resourceTypes).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">Environment</label>
            <select
              value={environmentFilter}
              onChange={e => {
                setEnvironmentFilter(e.target.value);
                setPage(1);
              }}
              className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none"
            >
              <option value="">All Environments</option>
              {ENVIRONMENT_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">Risk Level</label>
            <select
              value={riskFilter}
              onChange={e => {
                setRiskFilter(e.target.value);
                setPage(1);
              }}
              className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none"
            >
              <option value="">All Risks</option>
              {RISK_LEVEL_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">Team</label>
            <select
              value={teamFilter}
              onChange={e => {
                setTeamFilter(e.target.value);
                setPage(1);
              }}
              className="w-full text-xs px-2 py-1.5 bg-white/5 border border-border rounded-md text-foreground focus:outline-none"
            >
              <option value="">All Teams</option>
              {[...new Set(rows.filter(r => r.team).map(r => r.team))].map(team => (
                <option key={team} value={team}>{team}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Active Filter Chips */}
      <div className="flex flex-wrap items-center gap-2">
        {entityType && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border border-border text-muted-foreground cursor-pointer bg-white/5">
            {entityType} <X className="w-2.5 h-2.5" onClick={() => { setEntityType(''); setPage(1); }} />
          </span>
        )}
        {environmentFilter && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border border-border text-muted-foreground cursor-pointer bg-white/5">
            {environmentFilter} <X className="w-2.5 h-2.5" onClick={() => { setEnvironmentFilter(''); setPage(1); }} />
          </span>
        )}
        {riskFilter && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border border-border text-muted-foreground cursor-pointer bg-white/5">
            {riskFilter} <X className="w-2.5 h-2.5" onClick={() => { setRiskFilter(''); setPage(1); }} />
          </span>
        )}
        {teamFilter && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border border-border text-muted-foreground cursor-pointer bg-white/5">
            Team: {teamFilter} <X className="w-2.5 h-2.5" onClick={() => { setTeamFilter(''); setPage(1); }} />
          </span>
        )}
        {ownerFilter && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border border-border text-muted-foreground cursor-pointer bg-white/5">
            Owner: {ownerFilter} <X className="w-2.5 h-2.5" onClick={() => { setOwnerFilter(''); setPage(1); }} />
          </span>
        )}
        <span className="ml-auto text-xs text-muted-foreground">{filtered.length} shown</span>
      </div>

      {/* Table */}
      <div className="card-base overflow-hidden flex-1 min-h-0 flex flex-col">
        <div className="overflow-x-auto overflow-y-auto custom-scrollbar flex-1 min-h-0">
          <table className="w-full min-w-[1000px]">
            <thead className="sticky top-0 z-10 bg-[hsl(230_15%_9%)]">
              <tr className="border-b border-border">
                {[
                  'Resource', 'Type', 'Owner', 'Team', 'Department', 'Environment', 'Risk', 'SLA', 'Last Updated', 'Actions',
                ].map(h => (
                  <th key={h} className="text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-4 py-3 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {loading ? (
                [...Array(6)].map((_, i) => (
                  <tr key={i} className="border-b border-border/40">
                    {[...Array(10)].map((_, j) => (
                      <td key={j} className="px-4 py-3"><Skeleton className="h-4 rounded" /></td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center">
                    <div className="space-y-3">
                      <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto">
                        <Users className="w-6 h-6 text-muted-foreground/40" />
                      </div>
                      <p className="text-sm text-foreground">No resources found</p>
                      <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                        No ownership data available. Use Import to add ownership mappings or assign owners to resources.
                      </p>
                      {canWrite && (
                        <button
                          onClick={() => setShowImport(true)}
                          className="px-4 py-2 text-xs bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded-lg hover:bg-blue-600/30 transition-colors"
                        >
                          Import Ownership Mapping
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                filtered.map(row => {
                  const Icon = RESOURCE_ICONS[row.entity_type] || LayersIcon;
                  return (
                    <tr key={`${row.entity_type}-${row.entity_id}`} className="hover:bg-white/5 transition-colors">
                      {/* Resource */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2 min-w-0">
                          <Icon className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-foreground truncate">{row.entity_name || row.entity_id}</p>
                            <p className="text-[9px] text-muted-foreground truncate">{row.entity_id}</p>
                          </div>
                        </div>
                      </td>
                      {/* Type */}
                      <td className="px-4 py-3">
                        <span className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-muted-foreground capitalize">
                          {row.entity_type}
                        </span>
                      </td>
                      {/* Owner */}
                      <td className="px-4 py-3">
                        {row.owner ? (
                          <button
                            onClick={() => setOwnerPanel({ owner: row.owner, show: true })}
                            className="flex items-center gap-1.5 text-xs hover:text-blue-400 transition-colors"
                          >
                            <User className="w-3 h-3 text-muted-foreground" />
                            <span className="truncate max-w-[100px]">{row.owner}</span>
                          </button>
                        ) : (
                          <span className="text-[10px] text-muted-foreground/40 italic">unassigned</span>
                        )}
                      </td>
                      {/* Team */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 text-xs">
                          <Users className="w-3 h-3 text-muted-foreground/50" />
                          <span className="text-muted-foreground truncate max-w-[80px]">{row.team || '—'}</span>
                        </div>
                      </td>
                      {/* Department */}
                      <td className="px-4 py-3">
                        <span className="text-xs text-muted-foreground truncate max-w-[80px]">{row.department || '—'}</span>
                      </td>
                      {/* Environment */}
                      <td className="px-4 py-3">
                        <StatusBadge
                          value={row.environment}
                          options={ENVIRONMENT_OPTIONS}
                          colorOverride={ENVIRONMENT_OPTIONS.find(o => o.value === row.environment)?.color}
                        />
                      </td>
                      {/* Risk */}
                      <td className="px-4 py-3">
                        <StatusBadge
                          value={row.risk_level}
                          options={RISK_LEVEL_OPTIONS}
                          colorOverride={RISK_LEVEL_OPTIONS.find(o => o.value === row.risk_level)?.color}
                        />
                      </td>
                      {/* SLA */}
                      <td className="px-4 py-3">
                        <StatusBadge
                          value={row.sla_status}
                          options={SLA_STATUS_OPTIONS}
                          colorOverride={SLA_STATUS_OPTIONS.find(o => o.value === row.sla_status)?.color}
                        />
                      </td>
                      {/* Last Updated */}
                      <td className="px-4 py-3">
                        <span className="text-[10px] text-muted-foreground">{timeAgo(row.last_updated)}</span>
                      </td>
                      {/* Actions */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => setDetailsPanel(row)}
                            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
                            title="View details"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          {canWrite && (
                            <button
                              className="p-1 rounded text-muted-foreground hover:text-blue-400 hover:bg-blue-500/10 transition-colors"
                              title="Assign owner"
                              onClick={() => setDetailsPanel({ ...row, owner: null, team: null, department: null })}
                            >
                              <Plus className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {filtered.length > 0 && totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-[hsl(230_15%_9%)]">
            <span className="text-xs text-muted-foreground">
              {Math.min((page - 1) * PAGE_SIZE + 1, filtered.length)}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length} resources
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4 rotate-180" />
              </button>
              <span className="text-xs text-foreground px-2">{page} / {totalPages}</span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 rounded text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Resource Details Drawer */}
      {detailsPanel && (
        <div className="fixed inset-y-0 right-0 z-50 flex">
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setDetailsPanel(null)} />
          <div className="relative ml-auto w-full max-w-2xl bg-[hsl(230_15%_9%)] border-l border-border flex flex-col shadow-2xl">
            {/* Header */}
            <div className="flex items-start justify-between px-5 py-4 border-b border-border flex-shrink-0">
              <div className="flex items-start gap-3 min-w-0 flex-1">
                {Object.entries(RESOURCE_ICONS).find(([k]) => k === detailsPanel.entity_type)?.[1] ? (
                  <div className={clsx('w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5',
                    detailsPanel.risk_level === 'critical' ? 'bg-red-500/10' :
                    detailsPanel.risk_level === 'high' ? 'bg-orange-500/10' :
                    detailsPanel.risk_level === 'medium' ? 'bg-yellow-500/10' : 'bg-blue-500/10',
                  )}>
                    {React.createElement(RESOURCE_ICONS[detailsPanel.entity_type], { className: clsx('w-4 h-4',
                      detailsPanel.risk_level === 'critical' ? 'text-red-400' :
                      detailsPanel.risk_level === 'high' ? 'text-orange-400' :
                      detailsPanel.risk_level === 'medium' ? 'text-yellow-400' : 'text-blue-400'
                    )})}
                  </div>
                ) : (
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 bg-blue-500/10">
                    <LayersIcon className="w-4 h-4 text-blue-400" />
                  </div>
                )}
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold text-foreground">{detailsPanel.entity_name || detailsPanel.entity_id}</h2>
                  <p className="text-[10px] text-muted-foreground font-mono mt-0.5">{detailsPanel.entity_id}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-[10px] px-2 py-0.5 rounded border border-border text-muted-foreground capitalize">
                      {detailsPanel.entity_type}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded border border-border text-muted-foreground capitalize">
                      {detailsPanel.environment}
                    </span>
                  </div>
                </div>
              </div>
              <button onClick={() => setDetailsPanel(null)} className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors flex-shrink-0">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-5 space-y-5">
              {/* Owner Information */}
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Owner Information</p>
                <div className="space-y-3">
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">Primary Owner</label>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-foreground">{detailsPanel.owner || <span className="text-red-400 italic">unassigned</span>}</span>
                      {canWrite && !detailsPanel.owner && (
                        <button
                          onClick={() => {
                            // Assignment would happen here
                            alert('Owner assignment would open here');
                          }}
                          className="px-2 py-1 text-xs bg-blue-600/20 text-blue-400 rounded hover:bg-blue-600/30"
                        >
                          Assign
                        </button>
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">Backup Owner</label>
                    <span className="text-sm text-muted-foreground">{detailsPanel.backup_owner || '—'}</span>
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">Escalation Chain</label>
                    <div className="flex flex-wrap gap-1">
                      {detailsPanel.escalation_chain.length > 0 ? (
                        detailsPanel.escalation_chain.map((escalation, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-muted-foreground border border-border">
                            {escalation}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-muted-foreground italic">No escalation defined</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Organization */}
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Organization</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">Team</label>
                    <span className="text-sm text-foreground flex items-center gap-1.5">
                      <Users className="w-3 h-3 text-muted-foreground/50" />
                      {detailsPanel.team || '—'}
                    </span>
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">Department</label>
                    <span className="text-sm text-foreground">{detailsPanel.department || '—'}</span>
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">Business Unit</label>
                    <span className="text-sm text-foreground">{detailsPanel.business_unit || '—'}</span>
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">Business Criticality</label>
                    <span className="text-sm text-foreground capitalize">{detailsPanel.business_criticality}</span>
                  </div>
                </div>
              </div>

              {/* Risk & Compliance */}
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Risk & Compliance</p>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">Risk Level</label>
                    <span className={clsx('text-sm font-semibold capitalize', RISK_LEVEL_OPTIONS.find(o => o.value === detailsPanel.risk_level)?.color)}>
                      {detailsPanel.risk_level}
                    </span>
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">SLA Status</label>
                    <span className={clsx('text-sm font-semibold capitalize', SLA_STATUS_OPTIONS.find(o => o.value === detailsPanel.sla_status)?.color)}>
                      {detailsPanel.sla_status}
                    </span>
                  </div>
                  <div>
                    <label className="text-[9px] text-muted-foreground block mb-1">Last Updated</label>
                    <span className="text-sm text-muted-foreground">{timeAgo(detailsPanel.last_updated)}</span>
                  </div>
                </div>
              </div>

              {/* Cloud/Environment Info */}
              {detailsPanel.cloud_provider && (
                <div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Infrastructure</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[9px] text-muted-foreground block mb-1">Cloud Provider</label>
                      <span className="text-sm text-foreground flex items-center gap-1.5">
                        <Cloud className="w-3 h-3" />
                        {detailsPanel.cloud_provider}
                      </span>
                    </div>
                    {detailsPanel.cloud_account_id && (
                      <div>
                        <label className="text-[9px] text-muted-foreground block mb-1">Account ID</label>
                        <span className="text-sm font-mono text-muted-foreground">{detailsPanel.cloud_account_id}</span>
                      </div>
                    )}
                    {detailsPanel.region && (
                      <div>
                        <label className="text-[9px] text-muted-foreground block mb-1">Region</label>
                        <span className="text-sm text-foreground">{detailsPanel.region}</span>
                      </div>
                    )}
                    {detailsPanel.cluster_name && (
                      <div>
                        <label className="text-[9px] text-muted-foreground block mb-1">Cluster</label>
                        <span className="text-sm text-foreground">{detailsPanel.cluster_name}</span>
                      </div>
                    )}
                    {detailsPanel.namespace && (
                      <div>
                        <label className="text-[9px] text-muted-foreground block mb-1">Namespace</label>
                        <span className="text-sm text-foreground">{detailsPanel.namespace}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Assignment History */}
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Assignment Method</p>
                <div className="flex items-center gap-2 text-xs">
                  <span className={clsx('px-2 py-0.5 rounded border',
                    detailsPanel.assignment_method === 'import' ? 'border-purple-500/30 text-purple-400 bg-purple-500/10' :
                    detailsPanel.assignment_method === 'bulk' ? 'border-orange-500/30 text-orange-400 bg-orange-500/10' :
                    'border-blue-500/30 text-blue-400 bg-blue-500/10'
                  )}>
                    {detailsPanel.assignment_method}
                  </span>
                  {detailsPanel.is_assigned && (
                    <span className="flex items-center gap-1 text-xs text-green-400">
                      <Check className="w-3 h-3" /> Assigned
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Footer Actions */}
            <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border flex-shrink-0 bg-[hsl(230_15%_8%)]">
              <button
                onClick={() => setDetailsPanel(null)}
                className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Close
              </button>
              {canWrite && (
                <button
                  onClick={() => {
                    alert('Edit ownership would open here');
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 hover:bg-blue-600/30 transition-colors"
                >
                  <Edit3 className="w-3 h-3" /> Edit Assignment
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Owner Profile Modal */}
      {ownerPanel?.show && ownerPanel.owner && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setOwnerPanel(null)} />
          <div className="relative w-full max-w-2xl bg-[hsl(230_15%_9%)] border border-border rounded-2xl shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-[hsl(230_15%_10%)]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                  <User className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">{ownerPanel.owner}</h3>
                  <p className="text-[10px] text-muted-foreground">Primary Owner</p>
                </div>
              </div>
              <button onClick={() => setOwnerPanel(null)} className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-px bg-border">
              <div className="p-3 text-center bg-[hsl(230_15%_9%)]">
                <div className="text-lg font-bold text-foreground">{ownerPanel.owner}</div>
                <div className="text-[9px] text-muted-foreground">Resources</div>
              </div>
              <div className="p-3 text-center bg-[hsl(230_15%_8%)]">
                <div className="text-lg font-bold text-blue-400">{summary.owned_resources}</div>
                <div className="text-[9px] text-muted-foreground">Owned</div>
              </div>
              <div className="p-3 text-center bg-[hsl(230_15%__7%)]">
                <div className="text-lg font-bold text-orange-400">{summary.sla_violations}</div>
                <div className="text-[9px] text-muted-foreground">Violations</div>
              </div>
            </div>

            {/* Content */}
            <div className="p-6">
              <div className="space-y-6">
                <div>
                  <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Assigned Resources</h4>
                  <div className="space-y-2">
                    {rows.filter(r => r.owner === ownerPanel.owner).slice(0, 5).map(r => (
                      <div key={r.entity_id} className="flex items-center justify-between text-xs p-2 rounded bg-white/5">
                        <div className="flex items-center gap-2 min-w-0">
                          {React.createElement(RESOURCE_ICONS[r.entity_type] || LayersIcon, { className: 'w-3 h-3 text-muted-foreground' })}
                          <span className="text-foreground truncate">{r.entity_name || r.entity_id}</span>
                        </div>
                        <span className="text-muted-foreground text-[10px]">{r.environment}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Performance</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 rounded-lg bg-white/5 border border-border">
                      <div className="text-[10px] text-muted-foreground mb-1">Avg MTTR</div>
                      <div className="text-lg font-semibold text-foreground">4.5h</div>
                    </div>
                    <div className="p-3 rounded-lg bg-white/5 border border-border">
                      <div className="text-[10px] text-muted-foreground mb-1">SLA Compliance</div>
                      <div className="text-lg font-semibold text-green-400">92%</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {showImport && (
        <ImportOwnershipModal
          onClose={() => setShowImport(false)}
          onImport={handleImport}
        />
      )}

      {/* Export Modal */}
      {showExport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/70" onClick={() => setShowExport(false)} />
          <div className="relative w-full max-w-md bg-[hsl(230_15%_9%)] border border-border rounded-2xl shadow-2xl p-6">
            <h3 className="text-sm font-semibold text-foreground mb-4">Export Ownership</h3>
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Export all ownership mappings as CSV for backup or analysis.
              </p>
              <button
                onClick={handleExport}
                className="w-full py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Export CSV
              </button>
              <button
                onClick={() => setShowExport(false)}
                className="w-full py-2 text-xs text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Import Modal Component ─────────────────────────────────────────────────────

function ImportOwnershipModal({
  onClose,
  onImport,
}: {
  onClose: () => void;
  onImport: (csv: string) => void;
}) {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);

  const handleImport = useCallback(async () => {
    if (!content.trim()) return;
    setLoading(true);
    try {
      await onImport(content);
    } finally {
      setLoading(false);
    }
  }, [content, onImport]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/70" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-[hsl(230_15%_9%)] border border-border rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-[hsl(230_15%_10%)]">
          <h3 className="text-sm font-semibold text-foreground">Import Ownership Mapping</h3>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <p className="text-xs text-muted-foreground">
            Import ownership mappings from a CSV file. The CSV should have columns:
            <code className="block mt-2 px-2 py-1 rounded bg-white/5 text-[10px] font-mono">
              entity_type,entity_id,owner,team,department,environment,risk_level
            </code>
          </p>
          <textarea
            className="w-full h-48 text-xs font-mono p-3 rounded-lg bg-white/5 border border-border text-foreground focus:outline-none focus:border-blue-500/50"
            placeholder={`entity_type,entity_id,owner,team,department,environment,risk_level
repository,repo-123,dev-team@example.com,Engineering,Platform,production,critical
vulnerability,vuln-456,security-team@example.com,Security,Platform,staging,high`}
            value={content}
            onChange={e => setContent(e.target.value)}
          />
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border bg-[hsl(230_15%_8%)] flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleImport}
            disabled={!content.trim() || loading}
            className="px-4 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Importing...' : 'Import CSV'}
          </button>
        </div>
      </div>
    </div>
  );
}
