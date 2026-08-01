import { useState, useMemo, useCallback } from 'react';
import { useApi } from '@/hooks/use-api';
import { clsx } from 'clsx';
import {
  FileText, Download, RefreshCw, Package, Filter, Shield, Search, X, ChevronRight,
  Layers, GitBranch, GitCommit, ExternalLink, AlertTriangle, CheckCircle, Clock,
  Library, Box, Cpu, Database, Globe, Key, Lock, Eye, MoreVertical, ChevronDown,
  ArrowUpDown, Activity, Terminal, Code, FileJson, ChevronLeft, Info
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

// Types
interface SBOM {
  id: string;
  tenant_id: string;
  repo_id: string;
  repo_name: string;
  scan_id?: string;
  format: string;
  component_count: number;
  generated_at: string;
  generator: string;
  created_at: string;
}

interface SBOMListResponse {
  data: SBOM[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface SBOMDetailResponse {
  data: SBOM & { content: string; meta: Record<string, any> };
}

interface Component {
  name: string;
  version: string;
  purl?: string;
  type?: string;
  license?: string;
  supplier?: string;
  homepage?: string;
  repository?: string;
  description?: string;
  purlInfo?: {
    type?: string;
    namespace?: string;
    name?: string;
    version?: string;
  };
  vulnerabilities?: ComponentVulnerability[];
  risk_score?: number;
  cvss_max?: number;
  cves?: string[];
  cpe?: string;
  sha256?: string;
  latest_version?: string;
  maintainer?: string;
  dependency_depth?: number;
  dependency_type?: string;
}

interface ComponentVulnerability {
  id: string;
  cve_id: string;
  title: string;
  description?: string;
  severity: string;
  cvss_score?: number;
  status: string;
  package_name?: string;
  package_version?: string;
  fixed_version?: string;
  detected_by?: string[];
}

interface DependencyTreeNode {
  id: string;
  name: string;
  version: string;
  purl?: string;
  parent_id?: string;
  depth: number;
  children: string[];
  transitive_count: number;
}

interface DependencyTreeResponse {
  data: {
    roots: DependencyTreeNode[];
    nodes: Record<string, DependencyTreeNode>;
    total_packages: number;
    depth_max: number;
  };
}

interface EnterprisePackage {
  id: string;
  name: string;
  version: string;
  latest_version?: string;
  purl?: string;
  cpe?: string;
  sha256?: string;
  license?: string;
  supplier?: string;
  maintainer?: string;
  homepage?: string;
  repository?: string;
  description?: string;
  risk_score: number;
  vulnerability_count: number;
  cvss_max?: number;
  epss_score?: number;
  kev: boolean;
  cves: string[];
  dependency_depth: number;
  dependency_type: string;
  last_updated: string;
}

interface PackageDetailsResponse {
  data: EnterprisePackage;
}

interface SBOMSummaryStats {
  total_sboms: number;
  total_components: number;
  unique_packages: number;
  by_format: Record<string, number>;
  by_generator: Record<string, number>;
  by_repo: Record<string, number>;
  average_components: number;
}

// Constants
const FORMAT_COLORS: Record<string, string> = {
  cyclonedx: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  spdx:      'bg-purple-500/15 text-purple-400 border-purple-500/20',
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/25',
  high:     'bg-orange-500/20 text-orange-400 border-orange-500/25',
  medium:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/25',
  low:      'bg-blue-500/20 text-blue-400 border-blue-500/25',
};

const RISK_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400',
  high:     'bg-orange-500/20 text-orange-400',
  medium:   'bg-yellow-500/20 text-yellow-400',
  low:      'bg-green-500/20 text-green-400',
};

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

// Helper functions
function parsePurl(purl?: string): { type?: string; namespace?: string; name?: string; version?: string } {
  if (!purl || !purl.startsWith('pkg:')) return {};
  const parts = purl.slice(4).split('@');
  const typeNs = parts[0].split('/');
  return {
    type: typeNs[0],
    namespace: typeNs.length >= 2 ? typeNs[1] : undefined,
    name: typeNs.length >= 3 ? typeNs.slice(2).join('/') : undefined,
    version: parts.length >= 2 ? parts[1] : undefined,
  };
}

function getSeverityColor(severity: string): string {
  return SEVERITY_COLORS[severity.toLowerCase()] || SEVERITY_COLORS['low'];
}

function getRiskColor(risk: number): string {
  if (risk >= 70) return 'bg-red-500/20 text-red-400';
  if (risk >= 40) return 'bg-orange-500/20 text-orange-400';
  if (risk >= 20) return 'bg-yellow-500/20 text-yellow-400';
  return 'bg-green-500/20 text-green-400';
}

function formatDate(isoString: string): string {
  try {
    return new Date(isoString).toLocaleString();
  } catch {
    return isoString;
  }
}

// Risk Indicator Component
function RiskIndicator({ risk, showValue = false }: { risk: number; showValue?: boolean }) {
  let label = 'Unknown';
  let colorClass = 'text-gray-400';

  if (risk >= 70) {
    label = 'Critical';
    colorClass = 'text-red-400';
  } else if (risk >= 40) {
    label = 'High';
    colorClass = 'text-orange-400';
  } else if (risk >= 20) {
    label = 'Medium';
    colorClass = 'text-yellow-400';
  } else if (risk > 0) {
    label = 'Low';
    colorClass = 'text-green-400';
  }

  return (
    <div className="flex items-center gap-2">
      <span className={clsx('text-xs font-medium px-2 py-0.5 rounded-full border', getRiskColor(risk), showValue && 'border-current')}>
        {risk}
      </span>
      {showValue && <span className="text-xs text-muted-foreground">/ 100</span>}
      <span className={clsx('text-xs', colorClass)}>{label}</span>
    </div>
  );
}

// Severity Badge Component
function SeverityBadge({ severity }: { severity: string }) {
  const colorClass = getSeverityColor(severity);
  return (
    <span className={clsx(
      'text-[10px] px-1.5 py-0.5 rounded font-medium uppercase border',
      colorClass
    )}>
      {severity}
    </span>
  );
}

// SBOM Page Component
export default function SBOM() {
  const { toast } = useToast();
  const [repoFilter, setRepoFilter] = useState<string | null>(null);
  const [formatFilter, setFormatFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [selectedSBOM, setSelectedSBOM] = useState<SBOM | null>(null);
  const [selectedPackage, setSelectedPackage] = useState<EnterprisePackage | null>(null);
  const [dependencyTree, setDependencyTree] = useState<DependencyTreeResponse['data'] | null>(null);
  const [showPackageDetails, setShowPackageDetails] = useState(false);
  const [showDependencyTree, setShowDependencyTree] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadingAll, setDownloadingAll] = useState(false);

  // Fetch SBOMs
  const qs = useMemo(() => {
    const parts = [`page=${page}`, `page_size=${pageSize}`];
    if (repoFilter) parts.push(`repo_id=${repoFilter}`);
    if (formatFilter) parts.push(`format_filter=${formatFilter}`);
    if (search) parts.push(`search=${encodeURIComponent(search)}`);
    if (sortBy) parts.push(`sort_by=${sortBy}`);
    if (sortOrder !== 'asc') parts.push(`sort_order=${sortOrder}`);
    return parts.join('&');
  }, [repoFilter, formatFilter, page, pageSize, search, sortBy, sortOrder]);

  const { data: rawList, loading: loadingList, refetch: refetchList } = useApi<SBOMListResponse>(`/sbom?${qs}`);
  const { data: summaryStats, loading: loadingSummary, refetch: refetchSummary } = useApi<SBOMSummaryStats>('/sbom/summary');

  const sboms: SBOM[] = rawList?.data ?? (Array.isArray(rawList) ? rawList : []);
  const total = rawList?.total ?? sboms.length;
  const pages = rawList?.pages ?? 1;

  // Get unique repos for filter
  const repoOptions = useMemo(() => {
    const map = new Map<string, string>();
    sboms.forEach(sbom => {
      if (sbom.repo_id && sbom.repo_name) {
        map.set(sbom.repo_id, sbom.repo_name);
      }
    });
    return Array.from(map.entries());
  }, [sboms]);

  // Fetch SBOM content when selected
  const { data: sbomContent, loading: loadingContent, refetch: refetchContent } = useApi<any>(
    selectedSBOM ? `/sbom/${selectedSBOM.id}` : null
  );

  // Fetch enterprise packages for selected SBOM
  const { data: enterprisePackages, loading: loadingPackages } = useApi<any>(
    selectedSBOM ? `/sbom/${selectedSBOM.id}/enterprise-packages?page=1&page_size=100` : null
  );

  // Fetch dependency tree
  const fetchDependencyTree = useCallback(async () => {
    if (!selectedSBOM) return;
    try {
      const response = await fetch(`/api/sbom/${selectedSBOM.id}/dependency-tree`);
      const result = await response.json();
      if (result.data) {
        setDependencyTree(result.data);
      }
    } catch (e) {
      console.error('Failed to fetch dependency tree:', e);
    }
  }, [selectedSBOM]);

  const fetchPackageDetails = useCallback(async (packageName: string, packageVersion?: string) => {
    if (!selectedSBOM) return;
    try {
      const response = await fetch(`/api/sbom/${selectedSBOM.id}/package/${encodeURIComponent(packageName)}${packageVersion ? `?package_version=${encodeURIComponent(packageVersion)}` : ''}`);
      const result = await response.json();
      if (result.data) {
        setSelectedPackage(result.data);
        setShowPackageDetails(true);
      }
    } catch (e) {
      console.error('Failed to fetch package details:', e);
    }
  }, [selectedSBOM]);

  const handleDownload = async (sbom: SBOM, format: 'json' | 'cyclonedx' | 'spdx' = 'json') => {
    setDownloading(sbom.id);
    try {
      const response = await fetch(`/api/sbom/${sbom.id}/download?export_format=${format}`);
      if (!response.ok) throw new Error('Download failed');

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sbom-${sbom.repo_name.replace(/\//g, '-')}-${format}-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('SBOM download failed:', e);
      toast?.({
        title: 'Download Failed',
        description: 'Failed to download SBOM',
        variant: 'destructive',
      });
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadAll = async (format: 'json' | 'cyclonedx' | 'spdx' = 'json') => {
    setDownloadingAll(true);
    try {
      // Download each SBOM
      for (const sbom of sboms) {
        await handleDownload(sbom, format);
      }
      toast?.({
        title: 'Export Complete',
        description: `Downloaded ${sboms.length} SBOM(s)`,
      });
    } finally {
      setDownloadingAll(false);
    }
  };

  const handlePackageClick = (pkg: EnterprisePackage) => {
    if (selectedPackage?.id === pkg.id) {
      setShowPackageDetails(false);
      setSelectedPackage(null);
    } else {
      fetchPackageDetails(pkg.name, pkg.version);
    }
  };

  const handleSBOMSelect = (sbom: SBOM) => {
    if (selectedSBOM?.id === sbom.id) {
      setSelectedSBOM(null);
      setShowDependencyTree(false);
    } else {
      setSelectedSBOM(sbom);
      setShowDependencyTree(true);
      fetchDependencyTree();
    }
  };

  // Get components from SBOM content
  const components = useMemo(() => {
    if (!sbomContent?.data?.content) return [];
    try {
      const data = JSON.parse(sbomContent.data.content);
      return data.components || data.packages || [];
    } catch {
      return [];
    }
  }, [sbomContent]);

  // Filtered components
  const filteredComponents = useMemo(() => {
    if (!components.length) return [];
    if (!search) return components;
    const searchLower = search.toLowerCase();
    return components.filter(c =>
      (c.name || '').toLowerCase().includes(searchLower) ||
      (c.version || '').toLowerCase().includes(searchLower) ||
      (c.purl || '').toLowerCase().includes(searchLower)
    );
  }, [components, search]);

  // Sort components
  const sortedComponents = useMemo(() => {
    if (!filteredComponents.length) return [];
    if (!sortBy) return filteredComponents;
    const sorted = [...filteredComponents];
    sorted.sort((a, b) => {
      let valA, valB;
      switch (sortBy) {
        case 'name':
          valA = (a.name || '').toLowerCase();
          valB = (b.name || '').toLowerCase();
          break;
        case 'version':
          valA = a.version || '';
          valB = b.version || '';
          break;
        case 'license':
          valA = (a.license || '').toLowerCase();
          valB = (b.license || '').toLowerCase();
          break;
        case 'risk_score':
        case 'vulnerability_count':
          valA = 0;
          valB = 0;
          break;
        default:
          return 0;
      }
      if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
      if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [filteredComponents, sortBy, sortOrder]);

  // Paginated components
  const paginatedComponents = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sortedComponents.slice(start, start + pageSize);
  }, [sortedComponents, page, pageSize]);

  // Stats
  const summary = summaryStats?.data;

  // Export options
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exportFormat, setExportFormat] = useState<'json' | 'cyclonedx' | 'spdx'>('json');

  // Empty state
  if (loadingList && sboms.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold text-foreground">Software Bill of Materials</h1>
          <button
            onClick={() => refetchList()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="card-base p-4">
              <Skeleton className="h-4 w-20 mb-2" />
              <Skeleton className="h-8 w-16" />
            </div>
          ))}
        </div>
        <div className="card-base p-4">
          <Skeleton className="h-6 w-40 mb-3" />
          <Skeleton className="h-20 w-full mb-2" />
          <Skeleton className="h-20 w-full" />
        </div>
      </div>
    );
  }

  // Empty state - no SBOMs
  if (sboms.length === 0 && !loadingList) {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-bold text-foreground">Software Bill of Materials</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            No SBOMs found for this tenant
          </p>
        </div>
        <div className="card-base py-16 text-center">
          <Package className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-sm font-medium text-foreground mb-2">No SBOMs generated yet</p>
          <p className="text-xs text-muted-foreground max-w-md mx-auto mb-4">
            Run a repository scan from the Repositories or Security Scan section to automatically
            generate Software Bill of Materials in CycloneDX and SPDX formats.
          </p>
          <button
            onClick={() => window.location.href = '/security-center/security-scans'}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg"
          >
            Go to Security Scans
          </button>
        </div>
      </div>
    );
  }

  // Error state
  if (rawList?.message && !loadingList) {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-bold text-foreground">Software Bill of Materials</h1>
        </div>
        <div className="card-base p-6 border border-red-500/20 bg-red-500/5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-400">Error Loading SBOMs</p>
              <p className="text-xs text-red-300/80 mt-1">{rawList.message}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Main render
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-foreground">Software Bill of Materials</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {summary?.total_sboms || sboms.length} SBOM{summary?.total_sboms && summary.total_sboms !== 1 ? 's' : ''} with {summary?.total_components || '0'} components
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Format Filter Dropdown */}
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
            <select
              value={formatFilter || ''}
              onChange={(e) => {
                setFormatFilter(e.target.value || null);
                setPage(1);
              }}
              className="pl-9 pr-8 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm text-foreground focus:ring-2 focus:ring-blue-500/50 focus:border-transparent outline-none appearance-none"
            >
              <option value="">All Formats</option>
              <option value="cyclonedx">CycloneDX</option>
              <option value="spdx">SPDX</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
          </div>
          <button
            onClick={() => refetchList()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: 'hsl(230 15% 20%)' }}
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="card-base p-3 flex items-start gap-3 border border-blue-500/15" style={{ background: 'hsl(230 15% 8%)' }}>
        <Package className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-medium text-blue-400">Auto-generated from repository scans</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            SBOMs are automatically generated in CycloneDX and SPDX formats when a repository scan completes.
            They list all detected packages and their dependencies.
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="card-base p-4">
            <p className="text-xs text-muted-foreground mb-1">Total SBOMs</p>
            <p className="text-2xl font-bold text-foreground">{summary.total_sboms}</p>
          </div>
          <div className="card-base p-4">
            <p className="text-xs text-muted-foreground mb-1">Total Components</p>
            <p className="text-2xl font-bold text-foreground">{summary.total_components}</p>
          </div>
          <div className="card-base p-4">
            <p className="text-xs text-muted-foreground mb-1">Unique Packages</p>
            <p className="text-2xl font-bold text-foreground">{summary.unique_packages}</p>
          </div>
          <div className="card-base p-4">
            <p className="text-xs text-muted-foreground mb-1">Avg Components</p>
            <p className="text-2xl font-bold text-foreground">{summary.average_components}</p>
          </div>
        </div>
      )}

      {/* Repository Selector */}
      {repoOptions.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap p-2 rounded-lg bg-white/5 border border-white/5">
          <Filter className="w-3.5 h-3.5 text-muted-foreground" />
          <button
            onClick={() => {
              setRepoFilter(null);
              setPage(1);
            }}
            className={clsx(
              'px-3 py-1.5 rounded text-xs transition-colors',
              repoFilter === null ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            All Repositories
          </button>
          {repoOptions.map(([repoId, repoName]) => (
            <button
              key={repoId}
              onClick={() => {
                setRepoFilter(repoId);
                setPage(1);
              }}
              className={clsx(
                'px-3 py-1.5 rounded text-xs transition-colors truncate max-w-[150px]',
                repoFilter === repoId ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground'
              )}
              title={repoName}
            >
              {repoName}
            </button>
          ))}
        </div>
      )}

      {/* Search and Sort Controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-auto flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search packages by name, version, or PURL..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-foreground focus:ring-2 focus:ring-blue-500/50 outline-none"
          />
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground">Show:</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            className="px-2 py-1 bg-white/5 border border-white/10 rounded text-sm outline-none"
          >
            <option value={50}>50 per page</option>
            <option value={100}>100 per page</option>
            <option value={200}>200 per page</option>
            <option value={500}>500 per page</option>
          </select>
        </div>
      </div>

      {/* SBOM List */}
      <div className="card-base">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-foreground">SBOMs</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{total} SBOMs</span>
          </div>
        </div>
        <div className="space-y-2">
          {sboms.map((sbom) => (
            <div
              key={sbom.id}
              className={clsx(
                'p-4 rounded-lg border transition-all cursor-pointer',
                selectedSBOM?.id === sbom.id
                  ? 'border-blue-500 bg-blue-500/5 shadow-sm'
                  : 'border-white/10 hover:border-white/20 hover:bg-white/5'
              )}
              onClick={() => handleSBOMSelect(sbom)}
            >
              <div className="flex items-start gap-3">
                <div className={clsx(
                  'w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5',
                  FORMAT_COLORS[sbom.format] || 'bg-white/5 text-muted-foreground'
                )}>
                  <FileText className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <span className={clsx(
                      'text-[10px] px-1.5 py-0.5 rounded font-medium uppercase',
                      FORMAT_COLORS[sbom.format] || 'bg-white/5 text-muted-foreground border border-white/10'
                    )}>
                      {sbom.format}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground border border-white/10">
                      {sbom.component_count} components
                    </span>
                    {sbom.generator && (
                      <span className="text-[10px] text-muted-foreground capitalize">
                        via {sbom.generator.replace('-', ' ')}
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-medium text-foreground truncate">{sbom.repo_name || sbom.repo_id}</p>
                  <div className="flex items-center gap-3 mt-1 text-[11px] text-muted-foreground flex-wrap">
                    <span className="flex items-center gap-1">
                      <Clock className="w-2.5 h-2.5" />
                      {formatDate(sbom.generated_at || sbom.created_at)}
                    </span>
                    {sbom.scan_id && (
                      <span className="font-mono text-[10px]">scan: {sbom.scan_id.slice(0, 8)}</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDownload(sbom);
                  }}
                  disabled={downloading === sbom.id}
                  className={clsx(
                    'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border font-medium transition-all flex-shrink-0',
                    downloading === sbom.id
                      ? 'opacity-50 cursor-not-allowed border-white/10 text-muted-foreground'
                      : 'border-blue-500/30 text-blue-400 hover:bg-blue-500/10'
                  )}
                >
                  <Download className="w-3.5 h-3.5" />
                  {downloading === sbom.id ? 'Downloading…' : 'Download'}
                </button>
              </div>
            </div>
          ))}
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
                className="px-2 py-1 text-xs rounded border border-white/10 text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed hover:text-foreground"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setPage(Math.min(pages, page + 1))}
                disabled={page === pages}
                className="px-2 py-1 text-xs rounded border border-white/10 text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed hover:text-foreground"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* SBOM Details Drawer */}
      {selectedSBOM && sbomContent?.data && (
        <div className="card-base">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-foreground">SBOM Details: {selectedSBOM.repo_name}</h2>
            <button
              onClick={() => {
                setSelectedSBOM(null);
                setShowDependencyTree(false);
              }}
              className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* SBOM Metadata */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <div className="p-3 rounded-lg bg-white/5 border border-white/5">
              <p className="text-[10px] text-muted-foreground mb-1">Format</p>
              <p className="text-sm font-medium capitalize">{selectedSBOM.format}</p>
            </div>
            <div className="p-3 rounded-lg bg-white/5 border border-white/5">
              <p className="text-[10px] text-muted-foreground mb-1">Generator</p>
              <p className="text-sm font-medium capitalize">{selectedSBOM.generator}</p>
            </div>
            <div className="p-3 rounded-lg bg-white/5 border border-white/5">
              <p className="text-[10px] text-muted-foreground mb-1">Generated</p>
              <p className="text-sm font-medium">{formatDate(selectedSBOM.generated_at)}</p>
            </div>
            <div className="p-3 rounded-lg bg-white/5 border border-white/5">
              <p className="text-[10px] text-muted-foreground mb-1">Components</p>
              <p className="text-sm font-medium">{selectedSBOM.component_count}</p>
            </div>
          </div>

          {/* Enterprise Package Table */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-medium text-foreground flex items-center gap-2">
                <Library className="w-3.5 h-3.5 text-blue-400" />
                Enterprise Package Table
              </h3>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-muted-foreground">
                  {sortedComponents.length} packages found
                </span>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-4 py-2 font-medium text-muted-foreground">Package</th>
                    <th className="px-4 py-2 font-medium text-muted-foreground cursor-pointer hover:text-foreground" onClick={() => {
                      setSortBy('name');
                      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                    }}>
                      <div className="flex items-center gap-1">Version <ArrowUpDown className="w-3 h-3" /></div>
                    </th>
                    <th className="px-4 py-2 font-medium text-muted-foreground">License</th>
                    <th className="px-4 py-2 font-medium text-muted-foreground cursor-pointer hover:text-foreground" onClick={() => {
                      setSortBy('risk_score');
                      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                    }}>
                      <div className="flex items-center gap-1">Risk Score <ArrowUpDown className="w-3 h-3" /></div>
                    </th>
                    <th className="px-4 py-2 font-medium text-muted-foreground cursor-pointer hover:text-foreground" onClick={() => {
                      setSortBy('vulnerability_count');
                      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                    }}>
                      <div className="flex items-center gap-1">Vulns <ArrowUpDown className="w-3 h-3" /></div>
                    </th>
                    <th className="px-4 py-2 font-medium text-muted-foreground">CVEs</th>
                    <th className="px-4 py-2 font-medium text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedComponents.map((comp, i) => {
                    const purlInfo = parsePurl(comp.purl);
                    const risk = (comp as any).risk_score ?? 0;
                    const vulns = (comp as any).vulnerabilities || [];
                    const cves = (comp as any).cves || [];

                    return (
                      <tr
                        key={i}
                        className="border-b border-white/5 hover:bg-white/5 transition-colors"
                      >
                        <td className="px-4 py-2">
                          <div className="font-medium text-foreground">{comp.name}</div>
                          <div className="text-[10px] text-muted-foreground truncate max-w-[200px]">
                            {comp.purl || 'No PURL'}
                          </div>
                        </td>
                        <td className="px-4 py-2 font-mono text-muted-foreground">{comp.version}</td>
                        <td className="px-4 py-2">
                          <span className="text-xs text-blue-400">{comp.license || 'Unknown'}</span>
                        </td>
                        <td className="px-4 py-2">
                          <div className="w-16">
                            <RiskIndicator risk={risk} />
                          </div>
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-2">
                            <span className={clsx(
                              'text-xs font-medium px-2 py-0.5 rounded-full border',
                              getRiskColor(vulns.length)
                            )}>
                              {vulns.length}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">{cves.length}</span>
                            {cves.length > 0 && (
                              <span className="text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
                                {cves.slice(0, 3).join(', ')}
                                {cves.length > 3 && `+${cves.length - 3}`}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-2">
                          <button
                            onClick={() => fetchPackageDetails(comp.name, comp.version)}
                            className="px-2 py-1 text-xs bg-white/5 border border-white/10 rounded hover:bg-white/10 text-blue-400 hover:text-blue-300"
                          >
                            Details
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {paginatedComponents.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                        No packages found matching your filters
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Dependency Tree */}
          {showDependencyTree && dependencyTree && (
            <div className="mt-6 pt-6 border-t border-white/10">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-medium text-foreground flex items-center gap-2">
                  <Layers className="w-3.5 h-3.5 text-purple-400" />
                  Dependency Tree
                </h3>
                <span className="text-xs text-muted-foreground">
                  {dependencyTree.total_packages} packages, max depth: {dependencyTree.depth_max}
                </span>
              </div>
              <div className="overflow-x-auto">
                <div className="space-y-0.5">
                  {dependencyTree.roots.map((root) => (
                    <DependencyTreeItem
                      key={root.id}
                      node={root}
                      nodes={dependencyTree.nodes}
                      depth={0}
                      onSelectPackage={(pkg) => fetchPackageDetails(pkg.name, pkg.version)}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Export Menu */}
      <div className="fixed bottom-4 right-4 z-50">
        <div className="relative">
          <button
            onClick={() => setShowExportMenu(!showExportMenu)}
            className="flex items-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-full shadow-lg transition-all"
          >
            <Download className="w-4 h-4" />
            <span className="font-medium">Export</span>
            <ChevronDown className="w-4 h-4" />
          </button>
          {showExportMenu && (
            <div className="absolute bottom-full right-0 mb-2 w-48 bg-slate-900 border border-white/10 rounded-lg shadow-xl overflow-hidden">
              <button
                onClick={() => {
                  handleDownloadAll('json');
                  setShowExportMenu(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-muted-foreground hover:bg-white/5 hover:text-foreground flex items-center gap-2"
              >
                <FileJson className="w-4 h-4" />
                All SBOMs (JSON)
              </button>
              <button
                onClick={() => {
                  handleDownloadAll('cyclonedx');
                  setShowExportMenu(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-muted-foreground hover:bg-white/5 hover:text-foreground flex items-center gap-2"
              >
                <Code className="w-4 h-4" />
                All SBOMs (CycloneDX)
              </button>
              <button
                onClick={() => {
                  handleDownloadAll('spdx');
                  setShowExportMenu(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-muted-foreground hover:bg-white/5 hover:text-foreground flex items-center gap-2"
              >
                <Library className="w-4 h-4" />
                All SBOMs (SPDX)
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Package Details Modal */}
      {showPackageDetails && selectedPackage && (
        <PackageDetailsModal
          packageDetails={selectedPackage}
          onClose={() => {
            setShowPackageDetails(false);
            setSelectedPackage(null);
          }}
        />
      )}
    </div>
  );
}

// Dependency Tree Item Component
function DependencyTreeItem({
  node,
  nodes,
  depth,
  onSelectPackage,
}: {
  node: DependencyTreeNode;
  nodes: Record<string, DependencyTreeNode>;
  depth: number;
  onSelectPackage: (pkg: { name: string; version: string }) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  const renderNode = (currentNode: DependencyTreeNode, currentDepth: number) => {
    const indent = currentDepth * 16;

    return (
      <div key={currentNode.id} className="group">
        <div
          className="flex items-center py-1.5 px-2 hover:bg-white/5 rounded cursor-pointer transition-colors"
          style={{ paddingLeft: `${Math.max(0, indent)}px` }}
          onClick={() => {
            if (currentNode.children.length > 0) {
              setExpanded(!expanded);
            }
            onSelectPackage({ name: currentNode.name, version: currentNode.version });
          }}
        >
          <div className="flex items-center gap-1.5">
            {currentNode.children.length > 0 && (
              <ChevronRight
                className={clsx(
                  'w-3 h-3 text-muted-foreground transition-transform',
                  expanded ? 'rotate-90' : ''
                )}
              />
            )}
            <span className="text-xs font-medium text-foreground truncate max-w-[150px]">
              {currentNode.name}
            </span>
            <span className="text-xs text-muted-foreground">{currentNode.version}</span>
          </div>
          {currentNode.transitive_count > 0 && (
            <span className="ml-auto text-[10px] text-muted-foreground">
              {currentNode.transitive_count} deps
            </span>
          )}
        </div>
        {expanded && currentNode.children.length > 0 && (
          <div>
            {currentNode.children.map(childId => {
              const childNode = nodes[childId];
              return childNode ? (
                <DependencyTreeItem
                  key={childId}
                  node={childNode}
                  nodes={nodes}
                  depth={currentDepth + 1}
                  onSelectPackage={onSelectPackage}
                />
              ) : null;
            })}
          </div>
        )}
      </div>
    );
  };

  return renderNode(node, depth);
}

// Package Details Modal Component
function PackageDetailsModal({
  packageDetails,
  onClose,
}: {
  packageDetails: EnterprisePackage;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState<'overview' | 'dependencies' | 'vulnerabilities' | 'analysis'>('overview');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-white/10 rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-foreground">{packageDetails.name}</h2>
            <p className="text-xs text-muted-foreground">Version: {packageDetails.version}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex items-center px-6 pt-4 gap-6 border-b border-white/10">
          <button
            onClick={() => setActiveTab('overview')}
            className={clsx(
              'py-2 text-sm font-medium transition-colors',
              activeTab === 'overview' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('vulnerabilities')}
            className={clsx(
              'py-2 text-sm font-medium transition-colors',
              activeTab === 'vulnerabilities' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Vulnerabilities
            {packageDetails.vulnerability_count > 0 && (
              <span className={clsx(
                'ml-2 px-1.5 py-0.5 rounded-full text-[10px]',
                getRiskColor(packageDetails.vulnerability_count)
              )}>
                {packageDetails.vulnerability_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('dependencies')}
            className={clsx(
              'py-2 text-sm font-medium transition-colors',
              activeTab === 'dependencies' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Dependencies
          </button>
          <button
            onClick={() => setActiveTab('analysis')}
            className={clsx(
              'py-2 text-sm font-medium transition-colors',
              activeTab === 'analysis' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Analysis
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Key Info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-white/5 border border-white/5">
                  <p className="text-[10px] text-muted-foreground mb-2 uppercase tracking-wider">Package Information</p>
                  <div className="space-y-2">
                    <InfoRow label="Name" value={packageDetails.name} />
                    <InfoRow label="Version" value={packageDetails.version} />
                    <InfoRow label="Latest Version" value={packageDetails.latest_version || 'Unknown'} />
                    <InfoRow label="License" value={packageDetails.license || 'Unknown'} />
                    <InfoRow label="Type" value={packageDetails.dependency_type || 'direct'} />
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-white/5 border border-white/5">
                  <p className="text-[10px] text-muted-foreground mb-2 uppercase tracking-wider">Package References</p>
                  <div className="space-y-2">
                    <InfoRow label="PURL" value={packageDetails.purl || 'Not available'} copyable />
                    <InfoRow label="CPE" value={packageDetails.cpe || 'Not available'} copyable />
                    <InfoRow label="SHA256" value={packageDetails.sha256 || 'Not available'} copyable />
                    <InfoRow label="Maintainer" value={packageDetails.maintainer || 'Unknown'} />
                    <InfoRow label="Homepage" value={packageDetails.homepage || 'Unknown'} />
                    <InfoRow label="Repository" value={packageDetails.repository || 'Unknown'} />
                  </div>
                </div>
              </div>

              {/* Risk Score */}
              <div className="p-4 rounded-lg bg-white/5 border border-white/5">
                <p className="text-[10px] text-muted-foreground mb-3 uppercase tracking-wider">Risk Analysis</p>
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <p className="text-xs text-muted-foreground mb-2">Risk Score</p>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-3 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className={clsx(
                            'h-full rounded-full transition-all',
                            packageDetails.risk_score >= 70 ? 'bg-red-500' :
                            packageDetails.risk_score >= 40 ? 'bg-orange-500' :
                            packageDetails.risk_score >= 20 ? 'bg-yellow-500' : 'bg-green-500'
                          )}
                          style={{ width: `${packageDetails.risk_score}%` }}
                        />
                      </div>
                      <span className={clsx(
                        'text-lg font-bold',
                        packageDetails.risk_score >= 70 ? 'text-red-400' :
                        packageDetails.risk_score >= 40 ? 'text-orange-400' :
                        packageDetails.risk_score >= 20 ? 'text-yellow-400' : 'text-green-400'
                      )}>
                        {packageDetails.risk_score}/100
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'vulnerabilities' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {packageDetails.vulnerability_count} vulnerabilities found for this package
                </p>
                {packageDetails.cves.length > 0 && (
                  <span className="text-xs text-red-400 bg-red-500/10 px-2 py-1 rounded">
                    {packageDetails.cves.length} CVEs
                  </span>
                )}
              </div>
              {packageDetails.vulnerability_count > 0 ? (
                <div className="space-y-2">
                  {packageDetails.cves.slice(0, 10).map((cve, i) => (
                    <div key={i} className="p-3 rounded-lg bg-white/5 border border-white/5">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-bold text-red-300">CVE-{cve}</span>
                            {packageDetails.kev && (
                              <span className="text-[10px] px-1.5 py-0.5 bg-red-500/20 text-red-300 rounded">KEV</span>
                            )}
                            {packageDetails.epss_score && (
                              <span className="text-[10px] px-1.5 py-0.5 bg-orange-500/20 text-orange-300 rounded">
                                EPSS: {(packageDetails.epss_score * 100).toFixed(1)}%
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mb-2">
                            CVSS: {packageDetails.cvss_max || 'N/A'} • Severity: {packageDetails.risk_score >= 70 ? 'Critical' : 'High'}
                          </p>
                          <div className="text-xs text-muted-foreground">
                            {packageDetails.cves.length > 10 && (
                              <span className="italic">Showing {packageDetails.cves.length} of {packageDetails.cves.length} CVEs</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No known vulnerabilities found for this package
                </div>
              )}
            </div>
          )}

          {activeTab === 'dependencies' && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Dependency depth: {packageDetails.dependency_depth}
              </p>
              <div className="p-4 rounded-lg bg-white/5 border border-white/5">
                <div className="flex items-center justify-center py-8">
                  <Layers className="w-16 h-16 text-muted-foreground" />
                </div>
                <p className="text-center text-xs text-muted-foreground">
                  Dependency tree visualization requires full dependency graph analysis
                </p>
              </div>
            </div>
          )}

          {activeTab === 'analysis' && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <AnalysisCard
                  title="CVSS Score"
                  value={packageDetails.cvss_max?.toFixed(1) || 'N/A'}
                  sub={packageDetails.cvss_max ? 'Based on CVE data' : ''}
                />
                <AnalysisCard
                  title="KEV Status"
                  value={packageDetails.kev ? 'Yes' : 'No'}
                  sub={packageDetails.kev ? 'Known Exploited' : 'Not in KEV catalog'}
                />
                <AnalysisCard
                  title="EPSS Score"
                  value={packageDetails.epss_score ? (packageDetails.epss_score * 100).toFixed(1) + '%' : 'N/A'}
                  sub={packageDetails.epss_score ? 'Probability of exploitation' : ''}
                />
                <AnalysisCard
                  title="Last Updated"
                  value={new Date(packageDetails.last_updated).toLocaleDateString()}
                  sub="Package data last updated"
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Helper Components
function InfoRow({ label, value, copyable = false }: { label: string; value: string; copyable?: boolean }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (value) {
      navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-foreground font-mono truncate max-w-[150px]">{value}</span>
        {copyable && value && (
          <button
            onClick={handleCopy}
            className="p-1 text-muted-foreground hover:text-blue-400"
          >
            {copied ? <CheckCircle className="w-3 h-3" /> : <FileText className="w-3 h-3" />}
          </button>
        )}
      </div>
    </div>
  );
}

function AnalysisCard({ title, value, sub }: { title: string; value: string; sub: string }) {
  return (
    <div className="p-4 rounded-lg bg-white/5 border border-white/5">
      <p className="text-[10px] text-muted-foreground mb-1">{title}</p>
      <p className="text-lg font-bold text-foreground mb-1">{value}</p>
      <p className="text-[10px] text-muted-foreground/70">{sub}</p>
    </div>
  );
}
