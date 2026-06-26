import React, { useEffect, useState } from 'react';
import { Card, Title, Text, Badge, Table, Button, Spinner } from '../../components/ui';
import { intelligenceApi, ProviderHealth, IntelligenceStatus } from '../../services/api/intelligence';
import { Activity, Server, Clock, ShieldCheck } from 'lucide-react';

const IntelligenceSection = () => {
  const [health, setHealth] = useState<ProviderHealth[]>([]);
  const [status, setStatus] = useState<IntelligenceStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [healthRes, statusRes] = await Promise.all([
          intelligenceApi.getHealth(),
          intelligenceApi.getStatus()
        ]);
        setHealth(healthRes);
        setStatus(statusRes);
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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-blue-100 rounded-full text-blue-600">
            <ShieldCheck size={24} />
          </div>
          <div>
            <Text className="text-sm text-muted-foreground">Active Providers</Text>
            <Title className="text-2xl font-bold">{status.length}</Title>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-green-100 rounded-full text-green-600">
            <Activity size={24} />
          </div>
          <div>
            <Text className="text-sm text-muted-foreground">System Health</Text>
            <Title className="text-2xl font-bold">
              {health.every(h => h.status === 'healthy') ? 'Healthy' : 'Degraded'}
            </Title>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-purple-100 rounded-full text-purple-600">
            <Clock size={24} />
          </div>
          <div>
            <Text className="text-sm text-muted-foreground">Cache Status</Text>
            <Title className="text-2xl font-bold">L1/L2 Active</Title>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <Title>Provider Health</Title>
            <Button variant="ghost" size="sm" onClick={() => window.location.reload()}>Refresh</Button>
          </div>
          <Table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Status</th>
                <th>Latency</th>
                <th>Last Check</th>
              </tr>
            </thead>
            <tbody>
              {health.map(h => (
                <tr key={h.provider_id}>
                  <td>{h.name}</td>
                  <td>
                    <Badge variant={h.status === 'healthy' ? 'success' : h.status === 'degraded' ? 'warning' : 'destructive'}>
                      {h.status}
                    </Badge>
                  </td>
                  <td>{h.latency_ms ? `${h.latency_ms}ms` : 'N/A'}</td>
                  <td>{new Date(h.last_check_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <Card className="p-6">
          <Title className="mb-4">Provider Registry</Title>
          <Table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Version</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {status.map(s => (
                <tr key={s.provider_id}>
                  <td><code>{s.provider_id}</code></td>
                  <td>{s.name}</td>
                  <td>{s.version}</td>
                  <td>
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
  );
};

export default IntelligenceSection;
