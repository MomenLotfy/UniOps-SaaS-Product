import React, { useEffect, useState } from 'react';
import { Card } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Table } from '../../../components/ui/table';
import { Button } from '../../../components/ui/button';
import { Share2, Box, Zap, Database, Activity, Target, GitBranch, Users } from 'lucide-react';

const KnowledgeGraphSection = () => {
  const [stats, setStats] = useState(null);
  const [impacts, setImpacts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const mockStats = {
          entity_distribution: { 'CVE': 1200, 'Package': 5000, 'Pod': 150, 'Cluster': 2 },
          relationship_distribution: { 'AFFECTS': 3000, 'RUNS_ON': 450, 'BELONGS_TO': 150 },
          total_entities: 6850,
          total_relationships: 3600,
          health_status: 'healthy',
          last_updated: new Date().toISOString()
        };
        const mockImpacts = [
          { id: 'CVE-2024-1234', affected_assets: 45, affected_services: 3, priority: 'critical' },
          { id: 'CVE-2023-9999', affected_assets: 12, affected_services: 1, priority: 'high' },
          { id: 'CVE-2024-5678', affected_assets: 8, affected_services: 0, priority: 'medium' },
        ];
        setStats(mockStats);
        setImpacts(mockImpacts);
      } catch (e) {
        console.error("Failed to load graph data", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <div className="flex justify-center p-8">Loading Knowledge Graph...</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-blue-500/15 rounded-full text-blue-500">
            <Box size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Total Entities</span>
            <span className="text-2xl font-bold">{stats?.total_entities.toLocaleString()}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-purple-500/15 rounded-full text-purple-500">
            <Share2 size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Total Edges</span>
            <span className="text-2xl font-bold">{stats?.total_relationships.toLocaleString()}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-green-500/15 rounded-full text-green-500">
            <Activity size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Graph Health</span>
            <span className="text-2xl font-bold">{stats?.health_status}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-orange-500/15 rounded-full text-orange-500">
            <Zap size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Avg Traversal</span>
            <span className="text-2xl font-bold">12ms</span>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Entity Distribution</h3>
          <Table>
            <thead className="text-xs text-muted-foreground uppercase">
              <tr>
                <th className="text-left">Entity Type</th>
                <th className="text-right">Count</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(stats?.entity_distribution || {}).map(([type, count]) => (
                <tr key={type} className="border-t border-white/5">
                  <td className="py-3">{type}</td>
                  <td className="py-3 text-right font-mono">{count}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Relationship Density</h3>
          <Table>
            <thead className="text-xs text-muted-foreground uppercase">
              <tr>
                <th className="text-left">Relationship Type</th>
                <th className="text-right">Count</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(stats?.relationship_distribution || {}).map(([type, count]) => (
                <tr key={type} className="border-t border-white/5">
                  <td className="py-3">{type}</td>
                  <td className="py-3 text-right font-mono">{count}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Top Impact Entities</h3>
          <div className="space-y-3">
            {impacts.map(imp => (
              <div key={imp.id} className="flex items-center justify-between p-2 bg-surface-2 rounded-lg border border-white/5">
                <div className="flex items-center gap-2">
                  <Target size={14} className="text-red-400" />
                  <span className="text-xs font-medium">{imp.id}</span>
                </div>
                <Badge variant={imp.priority === 'critical' ? 'destructive' : 'warning'} className="text-[9px]">
                  {imp.affected_assets} assets
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Ownership Insights</h3>
          <div className="flex items-center gap-4 p-3 bg-surface-2 rounded-lg border border-white/5">
            <Users className="text-blue-400" size={20} />
            <span className="text-xs text-muted-foreground">
              Automatic ownership resolution is active. Relationships are traced from <br/>
              <span className="text-foreground font-semibold">Asset → Namespace → Team → Business Owner</span>
            </span >
          </div>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Blast Radius Intelligence</h3>
          <div className="flex items-center gap-4 p-3 bg-surface-2 rounded-lg border border-white/5">
            <GitBranch className="text-purple-400" size={20} />
            <span className="text-xs text-muted-foreground">
              Multi-hop traversal is enabled. The engine identifies <br/>
              <span className="text-foreground font-semibold">immediate, extended, and potential</span> impact zones for every finding.
            </span >
          </div>
        </Card>
      </div>

      <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
        <span className="text-[10px] text-indigo-300 leading-relaxed">
          The Relationship Intelligence Engine transforms the static Knowledge Graph into a reasoning layer.
          It understands transitive dependencies and business impact, providing a deterministic view of a vulnerability's propagation.
        </span >
      </div>
    </div>
  );
};

export default KnowledgeGraphSection;
