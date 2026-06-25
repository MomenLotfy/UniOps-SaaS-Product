import { useState } from 'react';
import { FileText, Download, RefreshCw, Package, Filter, Shield } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi } from '@/hooks/use-api';
import apiClient from '@/services/api/client';

function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-white/5', className)} />;
}

const FORMAT_STYLE: Record<string, string> = {
  cyclonedx: 'bg-blue-500/15 text-blue-400 border border-blue-500/20',
  spdx:      'bg-purple-500/15 text-purple-400 border border-purple-500/20',
};

export default function SBOM() {
  const [repoFilter, setRepoFilter] = useState('');
  const [downloading, setDownloading] = useState<string | null>(null);

  const qs = repoFilter ? `?repo_id=${repoFilter}` : '';
  const { data: raw, loading, refetch } = useApi<any>(`/sbom${qs}`);

  const sboms: any[] = Array.isArray(raw?.data) ? raw.data : (Array.isArray(raw) ? raw : []);

  // Collect unique repos from sboms for filter
  const repoOptions = Array.from(
    new Map(sboms.map(s => [s.repo_id, s.repo_name])).entries()
  );

  const handleDownload = async (sbom: any) => {
    setDownloading(sbom.id);
    try {
      const res = await apiClient.get(`/sbom/${sbom.id}/download`, { responseType: 'blob' });
      const url  = URL.createObjectURL(new Blob([res.data], { type: 'application/json' }));
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `sbom-${(sbom.repo_name ?? 'repo').replace(/\//g, '-')}-${sbom.format}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('SBOM download failed', e);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-lg font-bold text-foreground">Software Bill of Materials</h1>
          <p className="text-xs text-muted-foreground">
            {sboms.length} SBOM{sboms.length !== 1 ? 's' : ''} generated from repository scans
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border text-muted-foreground hover:text-foreground transition-colors"
          style={{ borderColor: 'hsl(230 15% 20%)' }}
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Info banner */}
      <div className="card-base p-3 flex items-start gap-3 border border-blue-500/15"
           style={{ background: 'hsl(230 15% 8%)' }}>
        <Package className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-medium text-blue-400">Auto-generated after each scan</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            SBOMs are automatically generated in CycloneDX and SPDX formats when a repository scan completes.
            They list all detected packages and dependencies.
          </p>
        </div>
      </div>

      {/* Repo filter */}
      {repoOptions.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-muted-foreground" />
          <button
            onClick={() => setRepoFilter('')}
            className={clsx('px-2.5 py-1 rounded text-xs transition-colors',
              repoFilter === '' ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}
          >
            All
          </button>
          {repoOptions.map(([repoId, repoName]) => (
            <button
              key={repoId}
              onClick={() => setRepoFilter(repoId)}
              className={clsx('px-2.5 py-1 rounded text-xs transition-colors truncate max-w-[200px]',
                repoFilter === repoId ? 'bg-blue-600 text-white' : 'text-muted-foreground hover:text-foreground')}
            >
              {repoName ?? repoId}
            </button>
          ))}
        </div>
      )}

      {/* SBOM list */}
      <div className="space-y-2">
        {loading ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
        ) : sboms.length === 0 ? (
          <div className="card-base py-12 text-center">
            <Shield className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground mb-1">No SBOMs yet</p>
            <p className="text-xs text-muted-foreground">
              Run a repository scan from the Repositories section to generate SBOMs automatically.
            </p>
          </div>
        ) : sboms.map((sbom: any) => (
          <div key={sbom.id} className="card-base p-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-md bg-blue-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <FileText className="w-4 h-4 text-blue-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className={clsx(
                    'text-[10px] px-1.5 py-0.5 rounded font-medium uppercase',
                    FORMAT_STYLE[sbom.format] ?? 'bg-white/5 text-muted-foreground border border-white/10',
                  )}>
                    {sbom.format}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground border border-white/10">
                    {sbom.component_count} components
                  </span>
                </div>
                <p className="text-sm font-medium text-foreground truncate">
                  {sbom.repo_name || sbom.repo_id}
                </p>
                <div className="flex items-center gap-3 mt-0.5 text-[11px] text-muted-foreground flex-wrap">
                  <span>Generated {new Date(sbom.generated_at || sbom.created_at).toLocaleString()}</span>
                  {sbom.scan_id && (
                    <span className="font-mono text-[10px]">scan: {sbom.scan_id.slice(0, 8)}</span>
                  )}
                  {sbom.generator && (
                    <span className="capitalize">via {sbom.generator.replace('-', ' ')}</span>
                  )}
                </div>
              </div>
              <button
                onClick={() => handleDownload(sbom)}
                disabled={downloading === sbom.id}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border font-medium transition-all flex-shrink-0',
                  downloading === sbom.id
                    ? 'opacity-50 cursor-not-allowed border-white/10 text-muted-foreground'
                    : 'border-blue-500/30 text-blue-400 hover:bg-blue-500/10',
                )}
              >
                <Download className="w-3.5 h-3.5" />
                {downloading === sbom.id ? 'Downloading…' : 'Download'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
