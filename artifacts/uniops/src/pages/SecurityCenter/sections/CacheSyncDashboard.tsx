import React, { useEffect, useState } from 'react';
import { Card } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Table } from '../../../components/ui/table';
import { Button } from '../../../components/ui/button';
import { Activity, Clock, Database, RefreshCcw, CheckCircle2, XCircle } from 'lucide-react';

const CacheSyncDashboard = () => {
  const [syncJobs, setSyncJobs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        // Mock API calls
        const mockStats = {
          total_entries: 12500,
          hit_ratio: 0.84,
          miss_ratio: 0.16,
          avg_lookup_time_ms: 12.5,
          l1_size: '150MB',
          l2_size: '2.4GB'
        };
        const mockJobs = [
          { job_id: 'sync_ghsa_2', provider: 'ghsa', status: 'synchronizing', progress: 45.0 },
          { job_id: 'sync_nvd_1', provider: 'nvd', status: 'completed', progress: 100.0 },
          { job_id: 'sync_osv_1', provider: 'osv', status: 'failed', progress: 12.0 },
        ];
        setStats(mockStats);
        setSyncJobs(mockJobs);
      } catch (e) {
        console.error("Failed to load cache/sync data", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <div className="flex justify-center p-8">Loading Cache Intelligence...</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-blue-500/15 rounded-full text-blue-500">
            <Database size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Total Entries</span>
            <span className="text-2xl font-bold">{stats?.total_entries.toLocaleString()}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-green-500/15 rounded-full text-green-500">
            <Activity size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Hit Ratio</span>
            <span className="text-2xl font-bold">{(stats?.hit_ratio * 100).toFixed(1)}%</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-purple-500/15 rounded-full text-purple-500">
            <Clock size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Avg Latency</span>
            <span className="text-2xl font-bold">{stats?.avg_lookup_time_ms}ms</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-orange-500/15 rounded-full text-orange-500">
            <RefreshCcw size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">L2 Size</span>
            <span className="text-2xl font-bold">{stats?.l2_size}</span>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-semibold text-foreground">Active Synchronization Jobs</h3>
            <Button variant="outline" size="sm">View Full History</Button>
          </div>
          <Table>
            <thead className="text-xs text-muted-foreground uppercase">
              <tr>
                <th className="text-left">Job ID</th>
                <th className="text-left">Provider</th>
                <th className="text-left">Status</th>
                <th className="text-left">Progress</th>
              </tr>
            </thead>
            <tbody>
              {syncJobs.map(job => (
                <tr key={job.job_id} className="border-t border-white/5 group">
                  <td className="py-4 font-mono text-xs">{job.job_id}</td>
                  <td className="py-4 capitalize">{job.provider}</td>
                  <td className="py-4">
                    <Badge variant={job.status === 'completed' ? 'success' : job.status === 'failed' ? 'destructive' : 'secondary'}>
                      {job.status}
                    </Badge>
                  </td>
                  <td className="py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${job.status === 'completed' ? 'bg-green-500' : job.status === 'failed' ? 'bg-red-500' : 'bg-blue-500'}`}
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                      <span className="text-[10px] font-mono">{job.progress}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Sync Health</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-green-500" />
                <span className="text-xs text-muted-foreground">Queue Health</span>
              </div>
              <span className="text-xs font-bold text-green-400">Optimal</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <div className="flex items-center gap-2">
                <Activity size={14} className="text-blue-500" />
                <span className="text-xs text-muted-foreground">L2 Latency</span>
              </div>
              <span className="text-xs font-bold text-blue-400">1.2ms</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <div className="flex items-center gap-2">
                <XCircle size={14} className="text-red-500" />
                <span className="text-xs text-muted-foreground">Sync Failures (24h)</span>
              </div>
              <span className="text-xs font-bold text-red-400">2</span>
            </div>
          </div>
          <div className="mt-6 p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
            <span className="text-[10px] text-indigo-300 leading-relaxed">
              The Synchronization Engine uses a checkpoint-based incremental strategy to minimize provider load and ensure deterministic state recovery.
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default CacheSyncDashboard;
