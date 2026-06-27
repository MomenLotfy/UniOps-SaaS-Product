import React, { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { Spinner } from '@/components/ui/spinner';
import { Badge } from '@/components/ui/badge';
import { Gavel, Activity, History, Info } from 'lucide-react';

interface Decision {
  id: string;
  status: string;
  final_result: string;
  created_at: string;
  tenant_id: string;
}

const DecisionsSection = () => {
  const [loading, setLoading] = useState(true);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [stats, setStats] = useState({ total: 0, ready: 0, rejected: 0 });

  useEffect(() => {
    async function fetchDecisions() {
      try {
        // In a real app, we would use the api service.
        // Mocking the fetch for the foundation view.
        const res = await fetch('/api/v1/security/decisions');
        const data = await res.json();
        setDecisions(data);
        setStats({
          total: data.length,
          ready: data.filter((d: any) => d.status === 'READY').length,
          rejected: data.filter((d: any) => d.status === 'REJECTED').length,
        });
      } catch (e) {
        console.error('Failed to fetch decisions', e);
      } finally {
        setLoading(false);
      }
    }
    fetchDecisions();
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
          <div className="p-3 bg-blue-100 text-blue-600 rounded-full">
            <Gavel size={24} />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Total Decisions</p>
            <p className="text-2xl font-bold">{stats.total}</p>
          </div>
        </Card>
        <Card className="p-6 flex items-center space-x-4">
          <div className="p-3 bg-green-100 text-green-600 rounded-full">
            <Activity size={24} />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Ready for Action</p>
            <p className="text-2xl font-bold">{stats.ready}</p>
          </div>
        </Card>
        <Card className="p-6 flex items-center space-x-4">
          <div className="p-3 bg-red-100 text-red-600 rounded-full">
            <History size={24} />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Rejected</p>
            <p className="text-2xl font-bold">{stats.rejected}</p>
          </div>
        </Card>
      </div>

      {/* Recent Decisions Table */}
      <Card className="overflow-hidden">
        <div className="p-6 border-b border-border flex justify-between items-center">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Info size={20} />
            Recent Security Decisions
          </h3>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Decision ID</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Result</TableHead>
              <TableHead>Created At</TableHead>
              <TableHead>Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {decisions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                  No decisions found. Pipeline is idle.
                </TableCell>
              </TableRow>
            ) : (
              decisions.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="font-mono text-xs">{d.id}</TableCell>
                  <TableCell>
                    <Badge variant={d.status === 'READY' ? 'success' : d.status === 'REJECTED' ? 'destructive' : 'secondary'}>
                      {d.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{d.final_result || 'N/A'}</TableCell>
                  <TableCell>{new Date(d.created_at).toLocaleString()}</TableCell>
                  <TableCell>
                    <button className="text-blue-600 hover:underline text-sm">Details</button>
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

export default DecisionsSection;
