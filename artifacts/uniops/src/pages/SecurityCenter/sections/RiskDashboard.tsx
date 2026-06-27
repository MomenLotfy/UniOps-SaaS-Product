import React, { useEffect, useState } from 'react';
import { Card } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Table } from '../../../components/ui/table';
import { Button } from '../../../components/ui/button';
import { AlertTriangle, TrendingUp, ShieldAlert, BarChart3 } from 'lucide-react';

const RiskDashboard = () => {
  const [repoRisks, setRepoRisks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadRiskData() {
      try {
        // This would call the actual /risk/repositories API
        const mockData = [
          { repository_id: 'core-api', overall_risk_score: 85.2, priority_level: 'critical', critical_findings_count: 3, high_findings_count: 12 },
          { repository_id: 'payment-gateway', overall_risk_score: 72.1, priority_level: 'high', critical_findings_count: 1, high_findings_count: 8 },
          { repository_id: 'auth-service', overall_risk_score: 45.5, priority_level: 'medium', critical_findings_count: 0, high_findings_count: 5 },
        ];
        setRepoRisks(mockData);
      } catch (e) {
        console.error("Failed to load risk data", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <div className="flex justify-center p-8">Loading Risk Intelligence...</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-red-500/15 rounded-full text-red-500">
            <ShieldAlert size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Critical Repos</span>
            <span className="text-2xl font-bold">{repoRisks.filter(r => r.priority_level === 'critical').length}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-orange-500/15 rounded-full text-orange-500">
            <AlertTriangle size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">High Risk Avg</span>
            <span className="text-2xl font-bold">
              {Math.round(repoRisks.reduce((acc, curr) => acc + curr.overall_risk_score, 0) / repoRisks.length)}
            </span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-blue-500/15 rounded-full text-blue-500">
            <TrendingUp size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Risk Trend</span>
            <span className="text-2xl font-bold">Stable</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-purple-500/15 rounded-full text-purple-500">
            <BarChart3 size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Priority Dist.</span>
            <span className="text-2xl font-bold">Bimodal</span>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-semibold text-foreground">Repository Risk Landscape</h3>
            <Button variant="outline" size="sm">Export Report</Button>
          </div>
          <Table>
            <thead className="text-xs text-muted-foreground uppercase">
              <tr>
                <th className="text-left">Repository</th>
                <th className="text-left">Risk Score</th>
                <th className="text-left">Priority</th>
                <th className="text-left">Critical Findings</th>
                <th className="text-left">High Findings</th>
              </tr>
            </thead>
            <tbody>
              {repoRisks.map(repo => (
                <tr key={repo.repository_id} className="border-t border-white/5 group">
                  <td className="py-4 font-medium">{repo.repository_id}</td>
                  <td className="py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-surface-3 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${repo.priority_level === 'critical' ? 'bg-red-500' : 'bg-orange-500'}`}
                          style={{ width: `${repo.overall_risk_score}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono">{repo.overall_risk_score}</span>
                    </div>
                  </td>
                  <td className="py-4">
                    <Badge variant={repo.priority_level === 'critical' ? 'destructive' : 'warning'}>
                      {repo.priority_level}
                    </Badge>
                  </td>
                  <td className="py-4">{repo.critical_findings_count}</td>
                  <td className="py-4">{repo.high_findings_count}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Risk Distribution</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <span className="text-xs text-muted-foreground">Critical</span>
              <span className="text-xs font-bold text-red-400">12%</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <span className="text-xs text-muted-foreground">High</span>
              <span className="text-xs font-bold text-orange-400">28%</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <span className="text-xs text-muted-foreground">Medium</span>
              <span className="text-xs font-bold text-blue-400">40%</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
              <span className="text-xs text-muted-foreground">Low</span>
              <span className="text-xs font-bold text-green-400">20%</span>
            </div>
          </div>
          <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
            <span className="text-[10px] text-blue-300 leading-relaxed">
              Risk scores are calculated using the <b>Risk Intelligence Engine v1.0</b>, synthesizing technical CVSS, asset criticality, and real-time exploit intelligence.
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default RiskDashboard;
