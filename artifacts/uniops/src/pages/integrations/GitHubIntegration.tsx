import { useState } from 'react';
import { GitBranch, CheckCircle, RefreshCw, Settings, Star, GitPullRequest, AlertCircle, Circle, XCircle, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { useApi, apiPost } from '@/hooks/use-api';
import { useIntegrationsCtx } from '@/contexts/IntegrationsContext';
import { formatRelative } from '@/lib/formatters';

const langColors: Record<string, string> = {
  TypeScript: 'bg-blue-500', JavaScript: 'bg-yellow-400', Python: 'bg-yellow-500',
  Go: 'bg-cyan-500', HCL: 'bg-purple-500', Ruby: 'bg-red-500', Java: 'bg-orange-500',
  Rust: 'bg-orange-400', Shell: 'bg-green-600', Dockerfile: 'bg-blue-400',
};

export default function GitHubIntegration() {
  const [syncing, setSyncing] = useState(false);

  const { data: reposRaw, loading: reposLoading, refetch: refetchRepos } = useApi<any>('/security/repos');
  const { data: pipelinesRaw, loading: pipelinesLoading } = useApi<any>('/pipelines?page_size=8');

  // ── Global context — no extra GET /integrations needed ────────────────────
  const { integrations, isConnected } = useIntegrationsCtx();
  const ghIntg = integrations.find(
    (i) => i.provider === 'github' && i.status === 'connected'
  );

  const repos:     any[] = (Array.isArray(reposRaw) ? reposRaw : reposRaw?.data) ?? [];
  const pipelines: any[] = (Array.isArray(pipelinesRaw) ? pipelinesRaw : pipelinesRaw?.data) ?? [];

  const username  = ghIntg?.config?.username  ?? null;
  const repoCount = (ghIntg?.config as any)?.repo_count ?? repos.length;
  const connected = isConnected('github');

  const handleSync = async () => {
    setSyncing(true);
    try {
      if (ghIntg?.id) await apiPost(`/integrations/${ghIntg.id}/sync`, {});
      await Promise.allSettled([
        apiPost('/security/repos/sync', {}),
        refetchRepos(),
      ]);
    } finally {
      setSyncing(false);
    }
  };

  if (!connected) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="card-base py-16 text-center space-y-3">
          <XCircle className="w-10 h-10 text-muted-foreground mx-auto" />
          <p className="text-sm font-semibold text-foreground">GitHub not connected</p>
          <p className="text-xs text-muted-foreground">Connect a GitHub token in Settings → Integrations to see your repositories.</p>
        </div>
      </div>
    );
  }

  // Derive simple stats from real data
  const openPRs    = pipelines.filter((p: any) => p.status === 'running' || p.status === 'pending').length;
  const failedBuilds = pipelines.filter((p: any) => p.status === 'failed').length;
  const ciCount    = Math.max(pipelines.length, repoCount);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-foreground/5 border border-border">
            <GitBranch className="w-5 h-5 text-foreground" />
          </div>
          <div>
            <h1 className="page-title">GitHub</h1>
            <p className="page-subtitle">
              {username ? `@${username}` : 'Connected'}{repoCount ? ` · ${repoCount} repositories synced` : ''}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSync} disabled={syncing} className="action-btn">
            {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {syncing ? 'Syncing…' : 'Sync'}
          </button>
          <button className="action-btn"><Settings className="w-4 h-4" /> Configure</button>
        </div>
      </div>

      <div className="card-base rounded-xl p-4 border border-green-500/30 flex items-center gap-3">
        <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
        <span className="text-xs text-foreground">
          GitHub connected{username ? ` as @${username}` : ''} ·{' '}
          {ghIntg?.lastSync ? `Last sync ${formatRelative(ghIntg.lastSync)}` : 'Webhooks active'}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Repositories',  value: repoCount ?? '—' },
          { label: 'Active Runs',   value: openPRs },
          { label: 'CI Pipelines',  value: ciCount },
          { label: 'Failed Builds', value: failedBuilds },
        ].map(({ label, value }) => (
          <div key={label} className="card-base rounded-xl p-4 border border-border text-center">
            <div className="text-2xl font-bold text-foreground">{value}</div>
            <div className="text-xs text-muted-foreground mt-1">{label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Repos */}
        <div className="col-span-2 card-base rounded-xl p-5 border border-border">
          <h3 className="text-sm font-semibold text-foreground mb-4">Repositories</h3>
          {reposLoading ? (
            <div className="space-y-2">
              {[1,2,3,4].map(i => <div key={i} className="h-10 rounded-lg bg-surface-2 animate-pulse" />)}
            </div>
          ) : repos.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-6">No repositories found. Try syncing.</p>
          ) : (
            <div className="space-y-2">
              {repos.slice(0, 8).map((repo: any, idx: number) => (
                <div key={repo.id ?? repo.full_name ?? idx}
                  className="flex items-center gap-3 p-3 rounded-xl border border-border/50 hover:border-border transition-colors">
                  <GitBranch className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-foreground truncate">{repo.name ?? repo.full_name}</div>
                    {repo.full_name && repo.full_name !== repo.name && (
                      <div className="text-xs text-muted-foreground truncate">{repo.full_name}</div>
                    )}
                  </div>
                  {repo.language && (
                    <div className="flex items-center gap-1">
                      <div className={clsx('w-2.5 h-2.5 rounded-full', langColors[repo.language] ?? 'bg-gray-500')} />
                      <span className="text-xs text-muted-foreground ml-1">{repo.language}</span>
                    </div>
                  )}
                  {repo.stargazers_count != null && (
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Star className="w-3 h-3" />{repo.stargazers_count}
                    </div>
                  )}
                  {repo.open_issues_count != null && (
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <GitPullRequest className="w-3 h-3" />{repo.open_issues_count}
                    </div>
                  )}
                  {repo.last_scan_score != null ? (
                    <span className={clsx('text-xs font-mono',
                      repo.last_scan_score >= 80 ? 'text-green-400' : repo.last_scan_score >= 60 ? 'text-yellow-400' : 'text-red-400')}>
                      {repo.last_scan_score}
                    </span>
                  ) : (
                    <Circle className="w-2.5 h-2.5 fill-current text-muted-foreground" />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent pipeline runs */}
        <div className="card-base rounded-xl p-5 border border-border">
          <h3 className="text-sm font-semibold text-foreground mb-4">Recent Runs</h3>
          {pipelinesLoading ? (
            <div className="space-y-3">
              {[1,2,3,4].map(i => <div key={i} className="h-12 rounded-lg bg-surface-2 animate-pulse" />)}
            </div>
          ) : pipelines.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-6">No recent pipeline runs.</p>
          ) : (
            <div className="space-y-3">
              {pipelines.slice(0, 6).map((run: any, i: number) => {
                const isFailed  = run.status === 'failed';
                const isRunning = run.status === 'running';
                const isPending = run.status === 'pending';
                const EventIcon = isFailed ? AlertCircle : isRunning || isPending ? Circle : CheckCircle;
                const color = isFailed ? 'text-red-400' : isRunning || isPending ? 'text-yellow-400' : 'text-green-400';
                return (
                  <div key={run.id ?? i} className="flex items-start gap-2.5">
                    <EventIcon className={clsx('w-4 h-4 flex-shrink-0 mt-0.5', color)} />
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-foreground truncate">{run.name || run.id}</div>
                      <div className="text-xs text-muted-foreground truncate">{run.repo || run.branch}</div>
                      {run.created_at && (
                        <div className="text-xs text-muted-foreground">{formatRelative(run.created_at)}</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
