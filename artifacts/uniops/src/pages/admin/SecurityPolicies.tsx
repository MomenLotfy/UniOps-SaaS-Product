import { useState, useEffect, useRef } from 'react';
import { Shield, AlertTriangle, Check, X, Info, ChevronRight, Lock, Clock, Key, Plus, Save, Search, FileText } from 'lucide-react';
import { clsx } from 'clsx';
import { policiesApi, SecurityPolicy, PolicyStats } from '../../services/api/security';

interface PolicyFilter {
  category: string;
  status: string;
  severity: string;
  enforcement: string;
  framework: string;
  search: string;
}

export default function SecurityPolicies() {
  const [policies, setPolicies] = useState<SecurityPolicy[]>([]);
  const [stats, setStats] = useState<PolicyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<PolicyFilter>({
    category: '', status: '', severity: '', enforcement: '', framework: '', search: ''
  });
  const [page, setPage] = useState(1);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<SecurityPolicy | null>(null);

  const nameRef = useRef<HTMLInputElement>(null);
  const descRef = useRef<HTMLTextAreaElement>(null);
  const sevRef = useRef<HTMLSelectElement>(null);
  const enfRef = useRef<HTMLSelectElement>(null);

  useEffect(() => {
    loadData();
  }, [filter, page]);

  async function loadData() {
    setLoading(true);
    try {
      const [pData, sData] = await Promise.all([
        policiesApi.list({
          page,
          page_size: 20,
          ...filter
        }),
        policiesApi.stats()
      ]);
      setPolicies(pData.data || []);
      setStats(sData.data || null);
    } catch (e) {
      console.error('Failed to load policies', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    const data = {
      name: nameRef.current?.value,
      description: descRef.current?.value,
      severity: sevRef.current?.value,
      enforcement: enfRef.current?.value,
    };

    try {
      if (editingPolicy) {
        await policiesApi.update(editingPolicy.id, data);
      } else {
        await policiesApi.create(data);
      }
      setIsModalOpen(false);
      setEditingPolicy(null);
      await loadData();
    } catch (e) {
      console.error('Failed to save policy', e);
    }
  }

  const visible = policies.filter(p =>
    (!filter.search || (p.name.toLowerCase().includes(filter.search.toLowerCase()) || p.description?.toLowerCase().includes(filter.search.toLowerCase())))
  );

  const levelColors: Record<string, string> = {
    critical: 'text-red-400 bg-red-400/10 border-red-400/20',
    high:     'text-orange-400 bg-orange-400/10 border-orange-400/20',
    medium:   'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
    low:      'text-blue-400 bg-blue-400/10 border-blue-400/20',
  };

  const categories = [...new Set(policies.map((p) => p.category))];

  async function handleToggle(policy: SecurityPolicy) {
    const newStatus = policy.status === 'active' ? 'inactive' : 'active';
    try {
      await policiesApi.update(policy.id, { status: newStatus });
      await loadData();
    } catch (e) {
      console.error('Failed to update policy status', e);
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="page-header">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="page-title">Security Policies</h1>
            <p className="page-subtitle">Configure organization-wide security controls and compliance requirements.</p>
          </div>
          <button
            onClick={() => { setEditingPolicy(null); setIsModalOpen(true); }}
            className="action-btn action-btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Create Policy
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Policies', value: stats?.total || 0, icon: Shield, color: 'hsl(220 90% 60%)' },
          { label: 'Active', value: stats?.active || 0, icon: Check, color: 'hsl(140 60% 45%)' },
          { label: 'Inactive', value: stats?.inactive || 0, icon: X, color: 'hsl(215 16% 50%)' },
          { label: 'Drafts', value: stats?.draft || 0, icon: Clock, color: 'hsl(45 90% 60%)' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card-base rounded-xl p-4 border border-border">
            <div className="flex items-center gap-2 mb-2">
              <Icon className="w-4 h-4" style={{ color }} />
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 items-center bg-background/50 p-3 rounded-xl border border-border">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search policies..."
            className="w-full pl-9 pr-4 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
            value={filter.search}
            onChange={e => setFilter(prev => ({ ...prev, search: e.target.value }))}
          />
        </div>
        <select
          className="px-3 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
          value={filter.category}
          onChange={e => setFilter(prev => ({ ...prev, category: e.target.value }))}
        >
          <option value="">All Categories</option>
          {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
        </select>
        <select
          className="px-3 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
          value={filter.severity}
          onChange={e => setFilter(prev => ({ ...prev, severity: e.target.value }))}
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary"></div>
        </div>
      ) : (
        <div className="space-y-2">
          {visible.length === 0 ? (
            <div className="text-center py-20 bg-background/50 rounded-xl border border-dashed border-border">
              <Shield className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-20" />
              <p className="text-sm text-muted-foreground">No security policies found matching the filters.</p>
            </div>
          ) : (
            visible.map((policy) => (
              <div key={policy.id} className="card-base rounded-xl p-4 border border-border flex items-start gap-4 hover:border-primary/30 transition-colors group">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-foreground">{policy.name}</span>
                    <span className={clsx('text-xs px-2 py-0.5 rounded-full border capitalize', levelColors[policy.severity])}>{policy.severity}</span>
                    <span className="text-[10px] text-muted-foreground ml-2">{policy.status}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{policy.description}</p>
                  <div className="mt-2 flex items-center gap-4 text-[10px] text-muted-foreground">
                    <span className="flex items-center gap-1"><Lock className="w-3 h-3" /> {policy.enforcement}</span>
                    <span className="flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> {policy.violations_count} violations</span>
                    <span className="flex items-center gap-1"><FileText className="w-3 h-3" /> {policy.exceptions_count} exceptions</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => { setEditingPolicy(policy); setIsModalOpen(true); }}
                    className="p-2 rounded-lg border border-border hover:bg-primary/10 hover:text-primary transition-colors"
                  >
                    <Save className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleToggle(policy)}
                    className={clsx('w-10 h-6 rounded-full relative transition-colors flex-shrink-0 mt-0.5', policy.status === 'active' ? 'bg-primary' : 'bg-border')}
                  >
                    <div className={clsx('absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all', policy.status === 'active' ? 'left-[calc(100%-1.375rem)]' : 'left-0.5')} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      <div className="flex justify-between items-center pt-4">
        <div className="text-xs text-muted-foreground">
          Showing {visible.length} of {policies.length} policies
        </div>
        <div className="flex gap-2">
          <button
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1 text-xs rounded-lg border border-border disabled:opacity-50 hover:bg-primary/10"
          >
            Previous
          </button>
          <button
            disabled={visible.length < 20}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 text-xs rounded-lg border border-border disabled:opacity-50 hover:bg-primary/10"
          >
            Next
          </button>
        </div>
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-background border border-border rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-border flex justify-between items-center">
              <h3 className="text-sm font-semibold">{editingPolicy ? 'Edit Policy' : 'Create Policy'}</h3>
              <button onClick={() => setIsModalOpen(false)} className="p-1 hover:bg-muted rounded-md"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Policy Name</label>
                <input
                  ref={nameRef}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
                  defaultValue={editingPolicy?.name || ''}
                  placeholder="e.g. No Critical CVEs"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Description</label>
                <textarea
                  ref={descRef}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
                  defaultValue={editingPolicy?.description || ''}
                  rows={3}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Severity</label>
                  <select
                    ref={sevRef}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
                    defaultValue={editingPolicy?.severity || 'medium'}
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Enforcement</label>
                  <select
                    ref={enfRef}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-primary/50"
                    defaultValue={editingPolicy?.enforcement || 'audit'}
                  >
                    <option value="audit">Audit</option>
                    <option value="enforce">Enforce</option>
                    <option value="advisory">Advisory</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="p-4 border-t border-border flex justify-end gap-2">
              <button onClick={() => setIsModalOpen(false)} className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted">Cancel</button>
              <button
                onClick={handleSave}
                className="px-3 py-1.5 text-xs rounded-lg bg-primary text-white hover:bg-primary/90 flex items-center gap-2"
              >
                <Save className="w-3 h-3" /> Save Policy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
