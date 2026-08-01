import { useState, useMemo } from 'react';
import { useApi } from '@/hooks/use-api';
import { clsx } from 'clsx';
import {
  Shield, Lock, AlertTriangle, Clock, TrendingUp, CheckCircle, XCircle,
  Users, FileText, BarChart, Target, Activity, Download, Search, Filter,
  MoreVertical, ChevronDown, BookOpen, ClipboardList, Globe, Server,
  Cloud, Cpu, Database, Key
} from 'lucide-react';

// Types
interface GovernanceSummary {
  overall_security_score: number;
  governance_score: number;
  compliance_percentage: number;
  risk_score: number;
  open_findings: number;
  critical_findings: number;
  breached_slas: number;
  open_exceptions: number;
  remediation_progress_percentage: number;
  policy_violations: number;
  protected_assets_percentage: number;
  repositories_covered_percentage: number;
  average_mttr: number;
}

interface HealthIndicator {
  resource_type: string;
  total: number;
  healthy: number;
  warning: number;
  critical: number;
  unknown: number;
}

interface RiskDistribution {
  by_severity: Record<string, number>;
  by_repository: Record<string, number>;
  by_business_unit: Record<string, number>;
  by_team: Record<string, number>;
  by_environment: Record<string, number>;
  by_cloud_provider: Record<string, number>;
  trend: Array<{ date: string; avg_risk: number }>;
}

interface OwnershipSummary {
  total_owned: number;
  teams_responsible: number;
  departments_responsible: number;
  owners: Array<{ name: string; count: number; last_updated?: string }>;
}

interface SLASummary {
  total_sla: number;
  compliant: number;
  breached: number;
  at_risk: number;
  compliance_rate: number;
  avg_response_time_hours: number;
}

interface RemediationOverview {
  total_open: number;
  total_resolved: number;
  avg_mttr_hours: number;
  by_severity: Record<string, number>;
  by_resource_type: Record<string, number>;
  trends: Array<{ week: string; total: number; resolved: number }>;
}

interface ComplianceOverview {
  total_checks: number;
  passed: number;
  failed: number;
  passed_rate: number;
  by_category: Record<string, number>;
  by_standard: Record<string, number>;
}

interface PolicyOverview {
  total_policies: number;
  active: number;
  violated: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
}

interface ThreatIntelligence {
  total_threats: number;
  open_threats: number;
  critical_threats: number;
  by_severity: Record<string, number>;
  by_source: Record<string, number>;
  top_threats: Array<{ id: string; title: string; severity: string; source: string }>;
}

interface ExecutiveTimeline {
  recent_events: Array<{ type: string; title: string; description: string; timestamp: string }>;
  upcoming_tasks: Array<{ title: string; description: string; due_date?: string }>;
  alerts: Array<{ severity: string; title: string; description: string }>;
}

interface BusinessImpact {
  high_risk_business_units: Array<{ name: string; critical_count: number; crit_risk: number }>;
  critical_applications: Array<{ name: string; type: string; risk: string }>;
  service_affected_count: number;
  estimated_impact_score: number;
}

interface GovernanceResponse {
  summary: GovernanceSummary;
  health_indicators: HealthIndicator[];
  risk_distribution: RiskDistribution;
  ownership_summary: OwnershipSummary;
  sla_summary: SLASummary;
  remediation_overview: RemediationOverview;
  compliance_overview: ComplianceOverview;
  policy_overview: PolicyOverview;
  threat_intelligence: ThreatIntelligence;
  executive_timeline: ExecutiveTimeline;
  business_impact: BusinessImpact;
}

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// Helper: Score indicator color
function getScoreColor(score: number, reverse = false): string {
  if (reverse) {
    if (score >= 80) return 'text-green-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-red-400';
  }
  if (score >= 80) return 'text-green-400';
  if (score >= 50) return 'text-yellow-400';
  return 'text-red-400';
}

// Helper: Severity color
function getSeverityColor(severity: string): string {
  switch (severity?.toLowerCase()) {
    case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/25';
    case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/25';
    case 'medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/25';
    case 'low': return 'bg-blue-500/20 text-blue-400 border-blue-500/25';
    default: return 'bg-white/5 text-muted-foreground border-white/10';
  }
}

// Stat Card Component
function StatCard({
  label, value, sub, icon: Icon, color, loading,
}: {
  label: string; value?: string | number; sub?: string;
  icon: React.ElementType; color: string; loading?: boolean;
}) {
  return (
    <div className="card-base p-4 flex items-center gap-3">
      <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0', color)}>
        <Icon className="w-4.5 h-4.5" />
      </div>
      <div className="min-w-0 flex-1">
        {loading ? (
          <Skeleton className="h-5 w-12 mb-1" />
        ) : (
          <>
            <p className="text-xl font-bold text-foreground">{value ?? '—'}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </>
        )}
        {sub && !loading && <p className="text-[10px] text-muted-foreground/70 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// Health Indicator Component
function HealthIndicatorCard({
  indicator, loading,
}: {
  indicator: HealthIndicator;
  loading?: boolean;
}) {
  const total = loading ? 0 : indicator.total;
  const healthy = loading ? 0 : indicator.healthy;
  const warning = loading ? 0 : indicator.warning;
  const critical = loading ? 0 : indicator.critical;
  const percent = total > 0 ? Math.round((healthy / total) * 100) : 0;

  return (
    <div className="card-base p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-white/5 flex items-center justify-center">
            {indicator.resource_type === 'Repository' && <FileText className="w-4 h-4 text-blue-400" />}
            {indicator.resource_type === 'Infrastructure' && <Server className="w-4 h-4 text-orange-400" />}
            {indicator.resource_type === 'Cloud Account' && <Cloud className="w-4 h-4 text-cyan-400" />}
            {indicator.resource_type === 'Kubernetes Cluster' && <Activity className="w-4 h-4 text-purple-400" />}
            {indicator.resource_type === 'Application' && <Target className="w-4 h-4 text-pink-400" />}
            {indicator.resource_type === 'Service' && <Globe className="w-4 h-4 text-green-400" />}
            {indicator.resource_type === 'Asset' && <Database className="w-4 h-4 text-yellow-400" />}
            {!['Repository', 'Infrastructure', 'Cloud Account', 'Kubernetes Cluster', 'Application', 'Service', 'Asset'].includes(indicator.resource_type) && <Shield className="w-4 h-4 text-gray-400" />}
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{indicator.resource_type}</p>
            <p className="text-xs text-muted-foreground">{total} resources</p>
          </div>
        </div>
        <div className={clsx('font-bold text-lg', getScoreColor(percent))}>{percent}%</div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-3 text-xs">
          <div className="w-12 font-medium text-green-400">Healthy: {healthy}</div>
          <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div className="h-full bg-green-500/50 rounded-full" style={{ width: `${(healthy / max(total, 1)) * 100}%` }} />
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <div className="w-12 font-medium text-yellow-400">Warning: {warning}</div>
          <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div className="h-full bg-yellow-500/50 rounded-full" style={{ width: `${(warning / max(total, 1)) * 100}%` }} />
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <div className="w-12 font-medium text-red-400">Critical: {critical}</div>
          <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div className="h-full bg-red-500/50 rounded-full" style={{ width: `${(critical / max(total, 1)) * 100}%` }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function max(a: number, b: number): number {
  return a > b ? a : b;
}

// Donut Chart Component (Simplified)
function DonutChart({ value, total, color }: { value: number; total: number; color: string }) {
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / total) * circumference;
  const percent = total > 0 ? Math.round((value / total) * 100) : 0;

  return (
    <div className="relative flex items-center justify-center">
      <svg className="w-16 h-16 -rotate-90" viewBox="0 0 50 50">
        <circle cx="25" cy="25" r={radius} fill="transparent" stroke="hsl(230 15% 16%)" strokeWidth="4" />
        <circle
          cx="25" cy="25" r={radius} fill="transparent" stroke={color} strokeWidth="4"
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
        />
      </svg>
      <span className={clsx('absolute text-sm font-bold', getScoreColor(percent))}>{percent}%</span>
    </div>
  );
}

// Bar Chart Component (Simplified)
function BarChartContainer({ data, maxVal, height = 80 }: { data: Array<{ label: string; value: number }>; maxVal?: number; height?: number }) {
  const maxValue = maxVal ?? Math.max(...data.map(d => d.value), 1);
  const barHeight = Math.max(20, (height - 20) / data.length);

  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="text-xs font-medium text-muted-foreground truncate w-20">{d.label}</span>
          <div className="flex-1 h-3 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500/30 to-blue-500/60 rounded-full"
              style={{ width: `${(d.value / maxValue) * 100}%` }}
            />
          </div>
          <span className="text-xs font-bold text-foreground w-12 text-right">{d.value}</span>
        </div>
      ))}
    </div>
  );
}

// Severity Distribution Component
function SeverityDistribution({ data }: { data: Record<string, number> }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  const colors = {
    critical: 'bg-red-500/20 border-red-500/25',
    high: 'bg-orange-500/20 border-orange-500/25',
    medium: 'bg-yellow-500/20 border-yellow-500/25',
    low: 'bg-blue-500/20 border-blue-500/25',
  };

  const sorted = Object.entries(data).sort(([, a], [, b]) => b - a);

  return (
    <div className="space-y-3">
      {sorted.map(([severity, count]) => (
        <div key={severity} className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <span className={clsx('w-2 h-2 rounded-full',
              severity === 'critical' ? 'bg-red-500' :
              severity === 'high' ? 'bg-orange-500' :
              severity === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
            )} />
            <span className="capitalize text-muted-foreground">{severity}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-bold text-foreground">{count}</span>
            {total > 0 && (
              <span className="text-xs text-muted-foreground">
                ({Math.round((count / total) * 100)}%)
              </span>
            )}
          </div>
        </div>
      ))}
      {sorted.length === 0 && (
        <div className="text-center py-4 text-muted-foreground text-sm">No data available</div>
      )}
    </div>
  );
}

// Risk Trend Chart Component
function RiskTrendChart({ data }: { data: Array<{ date: string; avg_risk: number }> }) {
  if (!data || data.length === 0) {
    return <div className="text-center py-4 text-muted-foreground text-sm">No trend data available</div>;
  }

  const maxRisk = Math.max(...data.map(d => d.avg_risk), 100);
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * 200;
    const y = 50 - (d.avg_risk / maxRisk) * 50;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="relative w-full overflow-hidden">
      <svg className="w-full h-24" viewBox="0 0 200 50" preserveAspectRatio="none">
        {/* Grid lines */}
        <line x1="0" y1="0" x2="200" y2="0" stroke="hsl(230 15% 20%)" strokeWidth="0.5" />
        <line x1="0" y1="25" x2="200" y2="25" stroke="hsl(230 15% 20%)" strokeWidth="0.5" />
        <line x1="0" y1="50" x2="200" y2="50" stroke="hsl(230 15% 20%)" strokeWidth="0.5" />

        {/* Trend line */}
        <polyline
          points={points}
          fill="none"
          stroke="#3b82f6"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Area fill */}
        <polygon
          points={`0,50 ${points} 200,50`}
          fill="rgba(59, 130, 246, 0.1)"
        />
      </svg>
      <div className="flex justify-between mt-2 text-xs text-muted-foreground">
        <span>{data[0]?.date}</span>
        <span>{data[data.length - 1]?.date}</span>
      </div>
    </div>
  );
}

// Export Options
const ExportFormats = ['json', 'csv', 'excel'] as const;

export default function GovernanceOverview() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'health' | 'risk' | 'compliance' | 'remediation'>('dashboard');
  const [dateRange, setDateRange] = useState('30');
  const [exportFormat, setExportFormat] = useState<string>('json');

  const { data, loading } = useApi<GovernanceResponse>(`/governance/overview?days=${dateRange}`);

  const governance = data?.data ?? data;
  const summary = governance?.summary;

  // Derived metrics
  const securityScore = summary?.overall_security_score ?? 0;
  const complianceScore = summary?.compliance_percentage ?? 0;
  const riskScore = summary?.risk_score ?? 0;
  const remediationProgress = summary?.remediation_progress_percentage ?? 0;
  const protectedAssets = summary?.protected_assets_percentage ?? 0;

  // Health indicators data
  const healthIndicators = governance?.health_indicators ?? [];

  // Risk distribution data
  const riskData = governance?.risk_distribution ?? { by_severity: {}, by_repository: {}, by_environment: {}, trend: [] };
  const bySeverity = riskData.by_severity ?? {};
  const byEnvironment = riskData.by_environment ?? {};

  // Compliance data
  const complianceData = governance?.compliance_overview;
  const compliancePassed = complianceData?.passed ?? 0;
  const complianceFailed = complianceData?.failed ?? 0;
  const complianceTotal = compliancePassed + complianceFailed;

  // Remediation data
  const remediationData = governance?.remediation_overview;
  const remediationOpen = remediationData?.total_open ?? 0;
  const remediationResolved = remediationData?.total_resolved ?? 0;

  // Policy data
  const policyData = governance?.policy_overview;
  const policyViolations = policyData?.violated ?? 0;
  const policyActive = policyData?.active ?? 0;

  // Threats data
  const threatsData = governance?.threat_intelligence;
  const openThreats = threatsData?.open_threats ?? 0;
  const criticalThreats = threatsData?.critical_threats ?? 0;

  // SLA data
  const slaData = governance?.sla_summary;
  const slaBreached = slaData?.breached ?? 0;
  const slaCompliant = slaData?.compliant ?? 0;

  // Timelines
  const timelineEvents = governance?.executive_timeline?.recent_events ?? [];
  const alerts = governance?.executive_timeline?.alerts ?? [];
  const businessImpact = governance?.business_impact;

  // Search/filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<string>('');

  // Filter timeline events
  const filteredEvents = useMemo(() => {
    if (!searchTerm) return timelineEvents;
    return timelineEvents.filter(e =>
      e.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.description.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [timelineEvents, searchTerm]);

  // Export handler
  const handleExport = async () => {
    const response = await fetch('/api/v1/governance/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        format: exportFormat,
        include_charts: true,
        date_range: `last_${dateRange}_days`,
      }),
    });
    const result = await response.json();
    if (result.data?.data) {
      const blob = new Blob([result.data.data], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `governance-report.${exportFormat}`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="space-y-5">
        <div>
          <h1 className="text-lg font-bold text-foreground">Governance Overview</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Loading governance data...</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card-base p-4">
              <Skeleton className="h-10 w-10 mb-3" />
              <Skeleton className="h-6 w-24 mb-2" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card-base p-4 space-y-3">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-24 w-full" />
          </div>
          <div className="card-base p-4 space-y-3">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-24 w-full" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-foreground">Governance Overview</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Executive dashboard with KPIs, health indicators, and business impact
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Date Filter */}
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="pl-9 pr-8 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-foreground focus:ring-2 focus:ring-blue-500/50 focus:border-transparent outline-none"
            >
              <option value="7">Last 7 Days</option>
              <option value="30">Last 30 Days</option>
              <option value="90">Last 90 Days</option>
              <option value="180">Last 180 Days</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
          </div>
          {/* Export Button */}
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Download className="w-4 h-4" />
            <span>Export</span>
          </button>
        </div>
      </div>

      {/* Executive KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Overall Security Score"
          value={`${securityScore}/100`}
          sub={securityScore >= 80 ? 'Excellent' : securityScore >= 50 ? 'Good' : 'Needs Attention'}
          icon={Shield}
          color="bg-blue-500/15 text-blue-400"
          loading={!summary}
        />
        <StatCard
          label="Governance Score"
          value={`${summary?.governance_score ?? '—'}/100`}
          sub={securityScore >= 80 ? 'Strong Controls' : securityScore >= 50 ? 'Moderate' : 'Weak'}
          icon={BookOpen}
          color="bg-purple-500/15 text-purple-400"
          loading={!summary}
        />
        <StatCard
          label="Compliance %"
          value={`${complianceScore}%`}
          sub={complianceScore >= 90 ? 'Compliant' : complianceScore >= 70 ? 'Mostly Compliant' : 'Non-Compliant'}
          icon={CheckCircle}
          color="bg-green-500/15 text-green-400"
          loading={!summary}
        />
        <StatCard
          label="Risk Score"
          value={`${riskScore}`}
          sub={riskScore <= 20 ? 'Low Risk' : riskScore <= 50 ? 'Moderate Risk' : 'High Risk'}
          icon={AlertTriangle}
          color="bg-red-500/15 text-red-400"
          loading={!summary}
        />
        <StatCard
          label="Open Findings"
          value={summary?.open_findings ?? '—'}
          sub={summary?.critical_findings ?? 0} critical findings
          icon={FileText}
          color="bg-orange-500/15 text-orange-400"
          loading={!summary}
        />
        <StatCard
          label="Breached SLAs"
          value={slaBreached}
          sub={slaBreached > 0 ? 'Action Required' : 'All Compliant'}
          icon={Clock}
          color="bg-red-500/15 text-red-400"
          loading={!slaData}
        />
        <StatCard
          label="Remediation Progress"
          value={`${remediationProgress}%`}
          sub={`${remediationResolved} resolved`}
          icon={Target}
          color="bg-green-500/15 text-green-400"
          loading={!remediationData}
        />
        <StatCard
          label="Open Exceptions"
          value={summary?.open_exceptions ?? '—'}
          sub={policyViolations} policy violations
          icon={ClipboardList}
          color="bg-yellow-500/15 text-yellow-400"
          loading={!summary}
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-white/10">
        <nav className="flex gap-6">
          {[
            { id: 'dashboard', label: 'Dashboard', icon: Activity },
            { id: 'health', label: 'Health', icon: Shield },
            { id: 'risk', label: 'Risk Analysis', icon: BarChart },
            { id: 'compliance', label: 'Compliance', icon: CheckCircle },
            { id: 'remediation', label: 'Remediation', icon: Target },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={clsx(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              )}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content based on active tab */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {/* Health Indicators Grid */}
          <div className="card-base p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-400" />
              Executive Health Indicators
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {loading ? (
                [...Array(8)].map((_, i) => <Skeleton key={i} className="h-32" />)
              ) : healthIndicators.length > 0 ? (
                healthIndicators.map((indicator, i) => (
                  <HealthIndicatorCard key={i} indicator={indicator} loading={false} />
                ))
              ) : (
                <div className="col-span-full text-center py-8 text-muted-foreground">
                  No health indicators available
                </div>
              )}
            </div>
          </div>

          {/* Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Risk Distribution */}
            <div className="card-base p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <BarChart className="w-4 h-4 text-purple-400" />
                Risk Distribution by Severity
              </h2>
              <div className="flex items-center justify-center py-4">
                <DonutChart
                  value={Object.values(bySeverity).reduce((a, b) => a + b, 0)}
                  total={100}
                  color="#a78bfa"
                />
              </div>
              <SeverityDistribution data={bySeverity} />
            </div>

            {/* Risk Trend */}
            <div className="card-base p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-400" />
                Risk Trend (30 Days)
              </h2>
              <RiskTrendChart data={riskData.trend || []} />
            </div>
          </div>

          {/* Compliance & Policy Overview */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card-base p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-400" />
                Compliance Overview
              </h2>
              <div className="flex items-center justify-center py-4">
                <DonutChart value={compliancePassed} total={complianceTotal || 1} color="#22c55e" />
              </div>
              <div className="space-y-3 mt-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-green-400">Passed</span>
                  <span className="font-bold">{compliancePassed}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-red-400">Failed</span>
                  <span className="font-bold">{complianceFailed}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Rate</span>
                  <span className="font-bold text-green-400">{complianceData?.passed_rate ?? 0}%</span>
                </div>
              </div>
            </div>

            <div className="card-base p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-purple-400" />
                Policy Overview
              </h2>
              <div className="flex items-center justify-center py-4">
                <DonutChart value={policyActive} total={(policyData?.total_policies ?? 1)} color="#8b5cf6" />
              </div>
              <div className="space-y-3 mt-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-green-400">Active</span>
                  <span className="font-bold">{policyActive}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-red-400">Violated</span>
                  <span className="font-bold">{policyViolations}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Total</span>
                  <span className="font-bold">{policyData?.total_policies ?? 0}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Threats & SLA Summary */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card-base p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                Threat Intelligence
              </h2>
              <div className="grid grid-cols-3 gap-4 text-center mb-4">
                <div>
                  <p className="text-2xl font-bold text-foreground">{openThreats}</p>
                  <p className="text-xs text-muted-foreground">Open Threats</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-400">{criticalThreats}</p>
                  <p className="text-xs text-muted-foreground">Critical</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-blue-400">{threatsData?.total_threats ?? 0}</p>
                  <p className="text-xs text-muted-foreground">Total</p>
                </div>
              </div>
              <SeverityDistribution data={threatsData?.by_severity ?? {}} />
            </div>

            <div className="card-base p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <Clock className="w-4 h-4 text-cyan-400" />
                SLA Summary
              </h2>
              <div className="flex items-center justify-center py-4">
                <DonutChart value={slaCompliant} total={(slaData?.total_sla ?? 1)} color="#06b6d4" />
              </div>
              <div className="space-y-3 mt-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-green-400">Compliant</span>
                  <span className="font-bold">{slaCompliant}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-red-400">Breached</span>
                  <span className="font-bold">{slaBreached}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Compliance Rate</span>
                  <span className="font-bold text-green-400">{slaData?.compliance_rate ?? 0}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Business Impact */}
          {businessImpact && (
            <div className="card-base p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <Target className="w-4 h-4 text-pink-400" />
                Business Impact Analysis
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <p className="text-xs text-muted-foreground mb-2">High Risk Business Units</p>
                  <div className="space-y-2">
                    {businessImpact.high_risk_business_units.length > 0 ? (
                      businessImpact.high_risk_business_units.map((bu, i) => (
                        <div key={i} className="flex items-center justify-between text-sm p-2 rounded bg-white/5 border border-white/5">
                          <span className="font-medium">{bu.name}</span>
                          <span className={clsx(
                            'px-2 py-0.5 rounded text-xs',
                            bu.crit_risk > 0 ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'
                          )}>
                            {bu.critical_count} critical
                          </span>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-muted-foreground">No high-risk business units identified</p>
                    )}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-2">Estimated Impact Score</p>
                  <div className="flex items-center gap-4">
                    <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className={clsx('h-full rounded-full', businessImpact.estimated_impact_score >= 70 ? 'bg-red-500' : businessImpact.estimated_impact_score >= 40 ? 'bg-yellow-500' : 'bg-green-500')}
                        style={{ width: `${businessImpact.estimated_impact_score}%` }}
                      />
                    </div>
                    <span className={clsx('font-bold', businessImpact.estimated_impact_score >= 70 ? 'text-red-400' : businessImpact.estimated_impact_score >= 40 ? 'text-yellow-400' : 'text-green-400')}>
                      {businessImpact.estimated_impact_score}/100
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Executive Timeline */}
          <div className="card-base p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Activity className="w-4 h-4 text-purple-400" />
                Executive Timeline
              </h2>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search events..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9 pr-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-xs text-foreground focus:ring-2 focus:ring-blue-500/50 outline-none"
                />
              </div>
            </div>
            <div className="space-y-3">
              {filteredEvents.length > 0 ? (
                filteredEvents.map((event, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white/5 border border-white/5">
                    <div className={clsx(
                      'mt-1 w-2 h-2 rounded-full flex-shrink-0',
                      event.type === 'vulnerability' ? 'bg-orange-500' :
                      event.type === 'policy' ? 'bg-purple-500' :
                      event.type === 'compliance' ? 'bg-blue-500' : 'bg-gray-500'
                    )} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-sm font-medium text-foreground truncate">{event.title}</p>
                        <span className="text-xs text-muted-foreground">
                          {new Date(event.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground truncate">{event.description}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-muted-foreground text-sm">No events found</div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'health' && (
        <div className="card-base p-5">
          <h2 className="text-sm font-semibold text-foreground mb-4">Resource Health Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {healthIndicators.map((indicator, i) => (
              <HealthIndicatorCard key={i} indicator={indicator} loading={false} />
            ))}
          </div>
        </div>
      )}

      {activeTab === 'risk' && (
        <div className="space-y-6">
          <div className="card-base p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Risk Distribution</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div>
                <p className="text-xs text-muted-foreground mb-3">By Severity</p>
                <SeverityDistribution data={bySeverity} />
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-3">By Environment</p>
                <BarChartContainer
                  data={Object.entries(byEnvironment).map(([k, v]) => ({ label: k, value: v }))}
                />
              </div>
            </div>
          </div>
          <div className="card-base p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Risk Trend</h2>
            <RiskTrendChart data={riskData.trend || []} />
          </div>
        </div>
      )}

      {activeTab === 'compliance' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="card-base p-5 text-center">
              <p className="text-3xl font-bold text-green-400">{compliancePassed}</p>
              <p className="text-sm text-muted-foreground mt-1">Passed Checks</p>
            </div>
            <div className="card-base p-5 text-center">
              <p className="text-3xl font-bold text-red-400">{complianceFailed}</p>
              <p className="text-sm text-muted-foreground mt-1">Failed Checks</p>
            </div>
            <div className="card-base p-5 text-center">
              <p className="text-3xl font-bold text-blue-400">{complianceTotal}</p>
              <p className="text-sm text-muted-foreground mt-1">Total Checks</p>
            </div>
          </div>
          <div className="card-base p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Compliance by Category</h2>
            <BarChartContainer
              data={Object.entries(complianceData?.by_category ?? {}).map(([k, v]) => ({ label: k, value: v }))}
            />
          </div>
        </div>
      )}

      {activeTab === 'remediation' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card-base p-4 text-center">
              <p className="text-2xl font-bold text-foreground">{remediationOpen}</p>
              <p className="text-xs text-muted-foreground mt-1">Open Tasks</p>
            </div>
            <div className="card-base p-4 text-center">
              <p className="text-2xl font-bold text-green-400">{remediationResolved}</p>
              <p className="text-xs text-muted-foreground mt-1">Resolved Tasks</p>
            </div>
            <div className="card-base p-4 text-center">
              <p className="text-2xl font-bold text-blue-400">{remediationData?.avg_mttr_hours ?? 0}</p>
              <p className="text-xs text-muted-foreground mt-1">Avg MTTR (hours)</p>
            </div>
            <div className="card-base p-4 text-center">
              <p className="text-2xl font-bold text-green-400">{remediationProgress}%</p>
              <p className="text-xs text-muted-foreground mt-1">Progress</p>
            </div>
          </div>
          <div className="card-base p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Remediation by Severity</h2>
            <SeverityDistribution data={remediationData?.by_severity ?? {}} />
          </div>
          <div className="card-base p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Remediation by Resource Type</h2>
            <BarChartContainer
              data={Object.entries(remediationData?.by_resource_type ?? {}).map(([k, v]) => ({ label: k, value: v }))}
            />
          </div>
        </div>
      )}

      {/* Alerts Banner */}
      {alerts.length > 0 && (
        <div className="border border-red-500/20 bg-red-500/10 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-red-500" />
            <h3 className="text-sm font-semibold text-red-400">Critical Alerts</h3>
          </div>
          <div className="space-y-2">
            {alerts.map((alert, i) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <div className="w-2 h-2 rounded-full bg-red-500 mt-1.5" />
                <div className="min-w-0">
                  <p className="text-red-300 font-medium">{alert.title}</p>
                  <p className="text-xs text-red-400/70">{alert.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
