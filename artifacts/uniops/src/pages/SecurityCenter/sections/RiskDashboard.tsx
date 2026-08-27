import React from 'react';
import { Card } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Table } from '../../../components/ui/table';
import { Button } from '../../../components/ui/button';
import { AlertTriangle, TrendingUp, TrendingDown, Minus, ShieldAlert, BarChart3 } from 'lucide-react';
import { useApi } from '@/hooks/use-api';

type RiskRow = {
  repo_id: string;
  repo_name: string;
  risk_level: string;
  risk_score: number;
  critical_count: number;
  high_count: number;
  trend: string;
  factors?: Record<string, any>;
};

type RiskHistoryPoint = { date: string; [repoId: string]: number | string };

const LEVEL_COLOR: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-green-400',
};

const LEVEL_BG: Record<string, string> = {
  critical: 'bg-red-500',
  high:     'bg-orange-500',
  medium:   'bg-yellow-500',
  low:      'bg-green-500',
};

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'worsening') return <TrendingUp className="text-red-400 inline-block" size={12} />;
  if (trend === 'improving') return <TrendingDown className="text-green-400 inline-block" size={12} />;
  return <Minus className="text-muted-foreground inline-block" size={12} />;
}

const RiskDashboard = () => {
  const { data: rawRisks, loading } = useApi<any>('/repos/risk');

  const repoRisks: RiskRow[] = Array.isArray(rawRisks?.data)
    ? rawRisks.data
    : Array.isArray(rawRisks)
    ? rawRisks
    : [];

  const critCount    = repoRisks.filter(r => r.risk_level === 'critical').length;
  const highCount    = repoRisks.filter(r => r.risk_level === 'high').length;
  const avgRisk      = repoRisks.length
    ? Math.round(repoRisks.reduce((s, r) => s + (r.risk_score ?? 0), 0) / repoRisks.length)
    : 0;
  const trendUp      = repoRisks.filter(r => r.trend === 'worsening').length;
  const trendDown    = repoRisks.filter(r => r.trend === 'improving').length;
  const overallTrend = trendUp > trendDown ? 'Worsening' : trendDown > trendUp ? 'Improving' : 'Stable';

  // Distribution by level
  const total = repoRisks.length || 1;
  const dist = ['critical', 'high', 'medium', 'low'].map(lvl => ({
    level: lvl,
    count: repoRisks.filter(r => r.risk_level === lvl).length,
    pct:   Math.round((repoRisks.filter(r => r.risk_level === lvl).length / total) * 100),
  }));

  if (loading) {
    return (
      <div className="flex justify-center items-center p-12 text-muted-foreground text-sm">
        Loading Risk Intelligence…
      </div>
    );
  }

  if (!repoRisks.length) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-muted-foreground">
        <ShieldAlert size={40} className="mb-4 opacity-20" />
        <p className="text-sm">No risk data yet. Run a security scan on a repository to populate this dashboard.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-red-500/15 rounded-full text-red-500">
            <ShieldAlert size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Critical Repos</span>
            <span className="text-2xl font-bold">{critCount}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-orange-500/15 rounded-full text-orange-500">
            <AlertTriangle size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Avg Risk Score</span>
            <span className="text-2xl font-bold">{avgRisk}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-blue-500/15 rounded-full text-blue-500">
            <TrendingUp size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">Portfolio Trend</span>
            <span className="text-2xl font-bold">{overallTrend}</span>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-purple-500/15 rounded-full text-purple-500">
            <BarChart3 size={24} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm text-muted-foreground">High-Risk Repos</span>
            <span className="text-2xl font-bold">{critCount + highCount}</span>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Risk table */}
        <Card className="lg:col-span-2 p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-semibold text-foreground">Repository Risk Landscape</h3>
          </div>
          <Table>
            <thead className="text-xs text-muted-foreground uppercase">
              <tr>
                <th className="text-left">Repository</th>
                <th className="text-left">Risk Score</th>
                <th className="text-left">Level</th>
                <th className="text-right">Critical</th>
                <th className="text-right">High</th>
                <th className="text-center">Trend</th>
              </tr>
            </thead>
            <tbody>
              {repoRisks.map(repo => (
                <tr key={repo.repo_id} className="border-t border-white/5 group">
                  <td className="py-3 font-medium text-sm">
                    {repo.repo_name ?? repo.repo_id}
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${LEVEL_BG[repo.risk_level] ?? 'bg-slate-500'}`}
                          style={{ width: `${Math.min(100, repo.risk_score ?? 0)}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono tabular-nums">
                        {Math.round(repo.risk_score ?? 0)}
                      </span>
                    </div>
                  </td>
                  <td className="py-3">
                    <Badge variant="outline" className={`text-[10px] capitalize ${LEVEL_COLOR[repo.risk_level] ?? ''}`}>
                      {repo.risk_level ?? '—'}
                    </Badge>
                  </td>
                  <td className="py-3 text-right text-sm font-mono">
                    {repo.critical_count ?? 0}
                  </td>
                  <td className="py-3 text-right text-sm font-mono">
                    {repo.high_count ?? 0}
                  </td>
                  <td className="py-3 text-center">
                    <TrendIcon trend={repo.trend ?? 'stable'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        {/* Risk distribution */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Risk Distribution</h3>
          <div className="space-y-3">
            {dist.map(d => (
              <div key={d.level} className="flex justify-between items-center p-3 bg-surface-2 rounded-lg">
                <span className="text-xs text-muted-foreground capitalize">{d.level}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono tabular-nums text-muted-foreground">{d.count}</span>
                  <span className={`text-xs font-bold ${LEVEL_COLOR[d.level]}`}>{d.pct}%</span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
            <span className="text-[10px] text-blue-300 leading-relaxed">
              Scores are computed from real scan findings — critical/high counts, detected secrets,
              container issues, compliance violations, and exposure factors.
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default RiskDashboard;
