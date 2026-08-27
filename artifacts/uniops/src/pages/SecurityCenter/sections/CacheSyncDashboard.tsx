import React from 'react';
import { Card } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Table } from '../../../components/ui/table';
import { Activity, Clock, Database, RefreshCcw, CheckCircle2, XCircle } from 'lucide-react';
import { useApi } from '@/hooks/use-api';

type Feed = {
  id?: string;
  provider_name?: string;
  name?: string;
  is_active?: boolean;
  last_sync?: string;
  record_count?: number;
  total_records?: number;
  sync_status?: string;
  status?: string;
  error_count?: number;
};

type HealthData = {
  total_providers?: number;
  healthy_providers?: number;
  cache_entries?: number;
  last_full_sync?: string;
};

const CacheSyncDashboard = () => {
  const { data: rawFeeds, loading: feedsLoading } = useApi<any>('/intelligence/feeds');
  const { data: rawHealth, loading: healthLoading } = useApi<any>('/intelligence/health');

  const loading = feedsLoading || healthLoading;

  const feeds: Feed[] = Array.isArray(rawFeeds?.data)
    ? rawFeeds.data
    : Array.isArray(rawFeeds)
    ? rawFeeds
    : [];

  const health: HealthData = rawHealth?.data ?? rawHealth ?? {};

  const totalEntries    = health.cache_entries ?? 0;
  const totalProviders  = health.total_providers ?? feeds.length;
  const healthyProviders = health.healthy_providers ?? feeds.filter((f) => f.status === 'healthy' || f.sync_status === 'success').length;
  const syncFailures    = feeds.filter((f) => f.status === 'error' || f.sync_status === 'failed' || (f.error_count ?? 0) > 0).length;

  const statusVariant = (status?: string) => {
    if (status === 'completed' || status === 'success' || status === 'healthy') return 'success';
    if (status === 'failed' || status === 'error') return 'destructive';
    return 'secondary';
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center p-12 text-muted-foreground text-sm">
        Loading sync status…
      </div>
    );
  }

  if (!feeds.length) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-muted-foreground">
        <Database size={40} className="mb-4 opacity-20" />
        <p className="text-sm">No intelligence providers configured.</p>
        <p className="text-xs mt-1">Connect a threat intelligence feed to populate this dashboard.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-blue-500/15 rounded-full text-blue-500">
            <Database size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Cache Entries</span>
            <span className="text-2xl font-bold">{totalEntries.toLocaleString()}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-green-500/15 rounded-full text-green-500">
            <Activity size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Healthy Providers</span>
            <span className="text-2xl font-bold">{healthyProviders} / {totalProviders}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-purple-500/15 rounded-full text-purple-500">
            <Clock size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Last Full Sync</span>
            <span className="text-sm font-medium">
              {health.last_full_sync
                ? new Date(health.last_full_sync).toLocaleDateString()
                : '—'}
            </span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-orange-500/15 rounded-full text-orange-500">
            <RefreshCcw size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Sync Failures</span>
            <span className={`text-2xl font-bold ${syncFailures > 0 ? 'text-red-400' : 'text-green-400'}`}>
              {syncFailures}
            </span>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-semibold text-foreground">Provider Sync Status</h3>
          </div>
          <Table>
            <thead className="text-xs text-muted-foreground uppercase">
              <tr>
                <th className="text-left">Provider</th>
                <th className="text-left">Status</th>
                <th className="text-right">Records</th>
                <th className="text-right">Last Sync</th>
              </tr>
            </thead>
            <tbody>
              {feeds.map((feed, i) => {
                const name   = feed.provider_name ?? feed.name ?? `provider-${i}`;
                const status = feed.sync_status ?? feed.status ?? 'unknown';
                const count  = feed.total_records ?? feed.record_count ?? 0;
                const synced = feed.last_sync;
                return (
                  <tr key={feed.id ?? i} className="border-t border-white/5 group">
                    <td className="py-3 capitalize font-medium text-sm">{name}</td>
                    <td className="py-3">
                      <Badge variant={statusVariant(status) as any} className="text-[10px] capitalize">
                        {status}
                      </Badge>
                    </td>
                    <td className="py-3 text-right font-mono text-xs">{count.toLocaleString()}</td>
                    <td className="py-3 text-right text-xs text-muted-foreground">
                      {synced ? new Date(synced).toLocaleString() : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Sync Health</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle2
                  size={14}
                  className={healthyProviders === totalProviders ? 'text-green-500' : 'text-yellow-500'}
                />
                <span className="text-xs text-muted-foreground">Provider Health</span>
              </div>
              <span className={`text-xs font-bold ${healthyProviders === totalProviders ? 'text-green-400' : 'text-yellow-400'}`}>
                {totalProviders === 0 ? 'N/A' : `${Math.round((healthyProviders / totalProviders) * 100)}%`}
              </span>
            </div>
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <div className="flex items-center gap-2">
                <Activity size={14} className="text-blue-500" />
                <span className="text-xs text-muted-foreground">Active Feeds</span>
              </div>
              <span className="text-xs font-bold text-blue-400">
                {feeds.filter(f => f.is_active !== false).length}
              </span>
            </div>
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <div className="flex items-center gap-2">
                <XCircle size={14} className={syncFailures > 0 ? 'text-red-500' : 'text-green-500'} />
                <span className="text-xs text-muted-foreground">Failures (24h)</span>
              </div>
              <span className={`text-xs font-bold ${syncFailures > 0 ? 'text-red-400' : 'text-green-400'}`}>
                {syncFailures}
              </span>
            </div>
          </div>
          <div className="mt-6 p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
            <span className="text-[10px] text-indigo-300 leading-relaxed">
              Sync data is pulled from configured intelligence providers. Connect additional feeds
              in the Integrations section to expand coverage.
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default CacheSyncDashboard;
