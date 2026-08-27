import React from 'react';
import { Card } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Table } from '../../../components/ui/table';
import { Share2, Box, Zap, Database, Activity, Target, GitBranch, Users } from 'lucide-react';
import { useApi } from '@/hooks/use-api';

type GraphStats = {
  total_entities?: number;
  total_relationships?: number;
  health_status?: string;
  entity_distribution?: Record<string, number>;
  relationship_distribution?: Record<string, number>;
  last_updated?: string;
};

const KnowledgeGraphSection = () => {
  const { data: rawStats, loading } = useApi<any>('/graph/statistics');

  const stats: GraphStats = rawStats?.data ?? rawStats ?? null;

  if (loading) {
    return (
      <div className="flex justify-center items-center p-12 text-muted-foreground text-sm">
        Loading Knowledge Graph…
      </div>
    );
  }

  const entityDist   = stats?.entity_distribution   ?? {};
  const relDist      = stats?.relationship_distribution ?? {};
  const totalEntities = stats?.total_entities ?? Object.values(entityDist).reduce((a, b) => a + b, 0);
  const totalRels     = stats?.total_relationships ?? Object.values(relDist).reduce((a, b) => a + b, 0);
  const health        = stats?.health_status ?? (totalEntities > 0 ? 'healthy' : 'empty');

  const isEmpty = totalEntities === 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-blue-500/15 rounded-full text-blue-500">
            <Box size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Total Entities</span>
            <span className="text-2xl font-bold">{totalEntities.toLocaleString()}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-purple-500/15 rounded-full text-purple-500">
            <Share2 size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Total Edges</span>
            <span className="text-2xl font-bold">{totalRels.toLocaleString()}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-green-500/15 rounded-full text-green-500">
            <Activity size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Graph Health</span>
            <span className="text-2xl font-bold capitalize">{health}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-orange-500/15 rounded-full text-orange-500">
            <Database size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Last Updated</span>
            <span className="text-sm font-medium truncate">
              {stats?.last_updated
                ? new Date(stats.last_updated).toLocaleTimeString()
                : '—'}
            </span>
          </div>
        </Card>
      </div>

      {isEmpty ? (
        <Card className="p-12 flex flex-col items-center justify-center text-muted-foreground">
          <Share2 size={40} className="mb-4 opacity-20" />
          <p className="text-sm">The knowledge graph is empty.</p>
          <p className="text-xs mt-1">Run security scans to populate entity relationships.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Entity Distribution</h3>
            {Object.keys(entityDist).length > 0 ? (
              <Table>
                <thead className="text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left">Entity Type</th>
                    <th className="text-right">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(entityDist).map(([type, count]) => (
                    <tr key={type} className="border-t border-white/5">
                      <td className="py-3 text-sm">{type}</td>
                      <td className="py-3 text-right font-mono text-sm">
                        {(count as number).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p className="text-xs text-muted-foreground">No entity breakdown available.</p>
            )}
          </Card>

          <Card className="p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Relationship Density</h3>
            {Object.keys(relDist).length > 0 ? (
              <Table>
                <thead className="text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left">Relationship</th>
                    <th className="text-right">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(relDist).map(([type, count]) => (
                    <tr key={type} className="border-t border-white/5">
                      <td className="py-3 text-sm">{type}</td>
                      <td className="py-3 text-right font-mono text-sm">
                        {(count as number).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p className="text-xs text-muted-foreground">No relationship data yet.</p>
            )}
          </Card>

          <Card className="p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Graph Info</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Entities</span>
                <span className="font-mono">{totalEntities.toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Edges</span>
                <span className="font-mono">{totalRels.toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Health</span>
                <Badge variant="outline" className="text-[9px] capitalize">{health}</Badge>
              </div>
            </div>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Ownership Insights</h3>
          <div className="flex items-center gap-4 p-3 bg-surface-2 rounded-lg border border-white/5">
            <Users className="text-blue-400" size={20} />
            <span className="text-xs text-muted-foreground">
              Automatic ownership resolution is active. Relationships are traced from{' '}
              <span className="text-foreground font-semibold">Asset → Namespace → Team → Business Owner</span>
            </span>
          </div>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Blast Radius Intelligence</h3>
          <div className="flex items-center gap-4 p-3 bg-surface-2 rounded-lg border border-white/5">
            <GitBranch className="text-purple-400" size={20} />
            <span className="text-xs text-muted-foreground">
              Multi-hop traversal identifies{' '}
              <span className="text-foreground font-semibold">immediate, extended, and potential</span>{' '}
              impact zones for every finding.
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default KnowledgeGraphSection;
