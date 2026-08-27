import React from 'react';
import { Card } from '@/components/ui/card';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { BookOpen, Activity, List, Info } from 'lucide-react';
import { useApi } from '@/hooks/use-api';

interface Rule {
  id: string;
  name: string;
  category?: string;
  priority?: number;
  is_active?: boolean;
  status?: string;
  version?: number;
}

const RulesSection = () => {
  // Rules are stored in the security_rules table and exposed via the
  // decision engine's /security/decisions endpoint family.
  // If there is no dedicated /security/rules list endpoint the table
  // simply shows an empty state — rules are configured via the
  // Decision Engine, not imported externally.
  const { data: rawRules, loading } = useApi<any>('/security/rules');

  const rules: Rule[] = Array.isArray(rawRules?.data)
    ? rawRules.data
    : Array.isArray(rawRules)
    ? rawRules
    : [];

  const totalActive = rules.filter(r => r.is_active || r.status === 'active').length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full p-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPI Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-6 flex items-center space-x-4">
          <div className="p-3 bg-indigo-500/15 text-indigo-400 rounded-full">
            <BookOpen size={24} />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Total Rules</p>
            <p className="text-2xl font-bold">{rules.length}</p>
          </div>
        </Card>
        <Card className="p-6 flex items-center space-x-4">
          <div className="p-3 bg-green-500/15 text-green-400 rounded-full">
            <Activity size={24} />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Active Rules</p>
            <p className="text-2xl font-bold">{totalActive}</p>
          </div>
        </Card>
        <Card className="p-6 flex items-center space-x-4">
          <div className="p-3 bg-amber-500/15 text-amber-400 rounded-full">
            <List size={24} />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Inactive Rules</p>
            <p className="text-2xl font-bold">{rules.length - totalActive}</p>
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
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                  No rules defined. Rules are configured via the Decision Engine.
                </TableCell>
              </TableRow>
            ) : (
              rules.map((rule) => {
                const isActive = rule.is_active || rule.status === 'active';
                return (
                  <TableRow key={rule.id}>
                    <TableCell className="font-medium">{rule.name}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{rule.category ?? '—'}</Badge>
                    </TableCell>
                    <TableCell>{rule.priority ?? '—'}</TableCell>
                    <TableCell>
                      <Badge variant={isActive ? 'default' : 'destructive'}>
                        {isActive ? 'active' : 'inactive'}
                      </Badge>
                    </TableCell>
                    <TableCell>{rule.version != null ? `v${rule.version}` : '—'}</TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
};

export default RulesSection;
