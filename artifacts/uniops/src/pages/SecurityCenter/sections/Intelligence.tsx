import React, { useEffect, useState } from 'react';
import { Card } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Table } from '../../../components/ui/table';
import { Button } from '../../../components/ui/button';
import { Spinner } from '../../../components/ui/spinner';
import { intelligenceApi, ProviderHealth, IntelligenceStatus, ProviderDetails } from '../../../services/api/intelligence';
import { Activity, Server, Clock, ShieldCheck, Settings, Info } from 'lucide-react';

const IntelligenceSection = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'management'>('overview');
  const [health, setHealth] = useState<ProviderHealth[]>([]);
  const [status, setStatus] = useState<IntelligenceStatus[]>([]);
  const [providers, setProviders] = useState<ProviderDetails[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [healthRes, statusRes, providersRes] = await Promise.all([
          intelligenceApi.getHealth(),
          intelligenceApi.getStatus(),
          intelligenceApi.getProviders()
        ]);
        setHealth(healthRes);
        setStatus(statusRes);
        setProviders(providersRes);
      } catch (e) {
        console.error("Failed to load intelligence data", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <div className="flex justify-center p-8"><Spinner /></div>;

  return (
    <div className="space-y-6">
      {/* ── Tab Navigation ───────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 p-1 bg-surface-2 rounded-lg w-fit border border-white/5">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
            activeTab === 'overview' ? 'bg-surface-1 text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('management')}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
            activeTab === 'management' ? 'bg-surface-1 text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Provider Management
        </button>
      </div>

      {activeTab === 'overview' ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="p-4 flex items-center gap-4">
              <div className="p-3 bg-blue-100 rounded-full text-blue-600">
                <ShieldCheck size={24} />
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-muted-foreground">Active Providers</span>
                <span className="text-2xl font-bold">{status.filter(s => s.is_active).length}</span>
              </div>
            </Card>
            <Card className="p-4 flex items-center gap-4">
              <div className="p-3 bg-green-100 rounded-full text-green-600">
                <Activity size={24} />
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-muted-foreground">System Health</span>
                <span className="text-2xl font-bold">
                  {health.every(h => h.status === 'healthy') ? 'Healthy' : 'Degraded'}
                </span>
              </div>
            </Card>
            <Card className="p-4 flex items-center gap-4">
              <div className="p-3 bg-purple-100 rounded-full text-purple-600">
                <Clock size={24} />
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-muted-foreground">Cache Status</span>
                <span className="text-2xl font-bold">L1/L2 Active</span>
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-foreground">Provider Health</h3>
                <Button variant="ghost" size="sm" onClick={() => window.location.reload()}>Refresh</Button>
              </div>
              <Table>
                <thead className="text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left">Provider</th>
                    <th className="text-left">Status</th>
                    <th className="text-left">Latency</th>
                    <th className="text-left">Last Check</th>
                  </tr>
                </thead>
                <tbody>
                  {health.map(h => (
                    <tr key={h.provider_id} className="border-t border-white/5">
                      <td className="py-3">{h.name}</td>
                      <td className="py-3">
                        <Badge variant={h.status === 'healthy' ? 'success' : h.status === 'degraded' ? 'warning' : 'destructive'}>
                          {h.status}
                        </Badge>
                      </td>
                      <td className="py-3">{h.latency_ms ? `${h.latency_ms}ms` : 'N/A'}</td>
                      <td className="py-3 text-xs">{new Date(h.last_check_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>

            <Card className="p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Provider Registry</h3>
              <Table>
                <thead className="text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left">ID</th>
                    <th className="text-left">Name</th>
                    <th className="text-left">Version</th>
                    <th className="text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {status.map(s => (
                    <tr key={s.provider_id} className="border-t border-white/5">
                      <td className="py-3"><code className="text-xs bg-white/5 px-1 rounded">{s.provider_id}</code></td>
                      <td className="py-3">{s.name}</td>
                      <td className="py-3 text-xs">{s.version}</td>
                      <td className="py-3">
                        <Badge variant={s.is_active ? 'success' : 'destructive'}>
                          {s.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex justify-between items-center mb-6">
              <div className="flex flex-col">
                <h3 className="text-lg font-semibold text-foreground">Provider Management</h3>
                <span className="text-sm text-muted-foreground">Configure and monitor detailed provider capabilities</span>
              </div>
              <Button size="sm" variant="outline" onClick={() => window.location.reload()}>Sync Registry</Button>
            </div>
            <Table>
              <thead className="text-xs text-muted-foreground uppercase">
                <tr>
                  <th className="text-left">Provider</th>
                  <th className="text-left">Type</th>
                  <th className="text-left">Capabilities</th>
                  <th className="text-left">Health</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {providers.map(p => (
                  <tr key={p.provider_id} className="border-t border-white/5 group">
                    <td className="py-4">
                      <div className="flex flex-col">
                        <span className="font-medium">{p.name}</span>
                        <span className="text-[10px] text-muted-foreground">{p.provider_id} v{p.version}</span>
                      </div>
                    </td>
                    <td className="py-4">
                      <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
                        {p.provider_type}
                      </Badge>
                    </td>
                    <td className="py-4">
                      <div className="flex flex-wrap gap-1">
                        {p.capabilities.map(cap => (
                          <Badge key={cap.capability_type} variant="secondary" className="text-[9px] py-0 px-1.5">
                            {cap.capability_type}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="py-4">
                      {p.health ? (
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${p.health.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`} />
                          <span className="text-xs">{p.health.status}</span>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">No data</span>
                      )}
                    </td>
                    <td className="py-4 text-right">
                      <Button variant="ghost" size="sm" className="p-1" title="View Details">
                        <Info size={14} />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        </div>
      )}
    </div>
  );
};

export default IntelligenceSection;
