import React, { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { Spinner } from '@/components/ui/spinner';
import { Badge } from '@/components/ui/badge';
import { BookOpen, Activity, List, Info } from 'lucide-react';

interface Rule {
  id: string;
  name: string;
  category: string;
  priority: number;
  status: 'active' | 'inactive';
  version: number;
}

const RulesSection = () => {
  const [loading, setLoading] = useState(true);
  const [rules, setRules] = useState<Rule[]>([]);
  const [stats, setStats] = useState({ total: 0, active: 0, matchRate: '0%' });

  useEffect(() => {
    async function fetchRules() {
      try {
        // Mocking API call for foundation
        const res = await fetch('/api/v1/security/rules');
        const data = await res.json();
        setRules(data);
        setStats({
          total: data.length,
          active: data.filter((r: any) => r.is_active).length,
          matchRate: '12.5%',
        });
      } catch (e) {
        console.error('Failed to fetch rules', e);
      } finally {
        setLoading(false);
      }
    }
    fetchRules();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full p-12">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPI Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-6 flex items-center space-x-4">
          <div className="p-3 bg-indigo-100 text-indigo-600 rounded-full">
            <BookOpen size={24} />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Total Rules</p>
            <p className="text-2xl font-bold">{stats.total}</p>
          </div>
        </Card>
        <Card className="p- la-6 flex items-center space-x-4">
          <div className="p-3 bg-green-100 text-green-600 rounded-full">
            <Activity size={24} />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Active Policies</p>
            <p className="text-2xl font-bold">{stats.active}</p>
          </div>
        </Card>
        <Card className="p-6 flex items-center space-x-4">
          <div className="p-3 bg-amber-100 text-amber-600 rounded-full">
            <List size={24} />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Average Match Rate</p>
            <p className="text-2xl font-bold">{stats.matchRate}</p>
          </div>
        </Card>
      </div>

      {/* Rules Table */}
      <Card className="overflow-hidden">
        <div className="p-6 border-b border-border flex justify-between items-center">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Info size={20} />
            Deterministic Decision Rules
          </h3>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Rule Name</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No rules defined. Rule engine is in default mode.
                </TableCell>
              </TableRow>
            ) : (
              rules.map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell className="font-medium">{rule.name}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{rule.category}</Badge>
                  </TableCell>
                  <TableCell>{rule.priority}</TableCell>
                  <TableCell>
                    <Badge variant={rule.status === 'active' ? 'success' : 'destructive'}>
                      {rule.status}
                    </Badge>
                  </TableCell>
                  <TableCell>v{rule.version}</TableCell>
                  <TableCell>
                    <button className="text-blue-600 hover:underline text-sm">Inspect</button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
};

export default RulesSection;
