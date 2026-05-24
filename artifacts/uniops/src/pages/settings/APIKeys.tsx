import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Key, Plus, Copy, Trash2, Eye, EyeOff, RefreshCw } from 'lucide-react';
import { formatDate } from '@/lib/formatters';
import { clsx } from 'clsx';
import apiClient from '@/services/api/client';

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  last_used?: string;
  expires_at?: string;
  created_at: string;
  active: boolean;
}

const ALL_SCOPES = ['pipelines:read', 'pipelines:write', 'pods:read', 'pods:write', 'metrics:read', 'alerts:read', 'alerts:write', 'costs:read', 'threats:read'];

export default function APIKeys() {
  const [keys, setKeys]             = useState<ApiKey[]>([]);
  const [loading, setLoading]       = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [revealedKey, setRevealedKey]       = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState('');
  const [error, setError]           = useState('');

  const loadKeys = () => {
    setLoading(true);
    apiClient.get<any>('/api-keys')
      .then((res) => {
        const items: ApiKey[] = res.data?.data ?? [];
        setKeys(Array.isArray(items) ? items : []);
      })
      .catch(() => setError('Failed to load API keys'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadKeys(); }, []);

  const handleCreate = async () => {
    if (!newKeyName.trim()) return;
    setIsCreating(true);
    setError('');
    try {
      const res = await apiClient.post<any>('/api-keys', { name: newKeyName, scopes: selectedScopes });
      const created = res.data?.data;
      setCreatedKey(created?.key ?? '');
      await loadKeys();
      setNewKeyName('');
      setSelectedScopes([]);
    } catch {
      setError('Failed to create API key');
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopy = (text: string) => { navigator.clipboard?.writeText(text); };

  const handleDelete = async (id: string) => {
    try {
      await apiClient.delete(`/api-keys/${id}`);
      setKeys((prev) => prev.filter((k) => k.id !== id));
    } catch {
      setError('Failed to delete API key');
    }
  };

  const toggleScope = (s: string) =>
    setSelectedScopes((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">API Keys</h1>
          <p className="page-subtitle">Manage API keys for programmatic access</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={loadKeys} className="action-btn" disabled={loading}>
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
          </button>
          <button onClick={() => { setShowCreate((p) => !p); setCreatedKey(''); }} className="action-btn-primary">
            <Plus className="w-4 h-4" />Create API Key
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
          {error}
        </div>
      )}

      {showCreate && (
        <div className="card-base mb-5">
          {createdKey ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-400">
                <Key className="w-4 h-4" />
                <span className="text-sm font-semibold">API Key Created — copy it now, it won't be shown again!</span>
              </div>
              <div className="flex items-center gap-2 p-3 rounded-lg font-mono text-sm" style={{ background: 'hsl(160 84% 39% / 0.08)', border: '1px solid hsl(160 84% 39% / 0.2)' }}>
                <span className="flex-1 text-green-400 break-all">{createdKey}</span>
                <button onClick={() => handleCopy(createdKey)} className="p-1.5 rounded text-muted-foreground hover:text-foreground"><Copy className="w-4 h-4" /></button>
              </div>
              <button onClick={() => { setCreatedKey(''); setShowCreate(false); }} className="action-btn">Done</button>
            </div>
          ) : (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-foreground">New API Key</h2>
              <div>
                <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Key name</label>
                <input value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="e.g. CI/CD Pipeline"
                  className="w-full px-3 py-2.5 rounded-lg text-sm text-foreground border outline-none focus:ring-2 focus:ring-blue-500/50"
                  style={inputStyle} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-2 text-muted-foreground">Permissions</label>
                <div className="flex flex-wrap gap-2">
                  {ALL_SCOPES.map((s) => (
                    <button key={s} onClick={() => toggleScope(s)} type="button"
                      className={clsx('px-2.5 py-1 rounded-md text-xs font-mono transition-all border', selectedScopes.includes(s) ? 'text-blue-400 border-blue-500/50 bg-blue-500/10' : 'text-muted-foreground border-border bg-transparent')}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={handleCreate} disabled={isCreating || !newKeyName.trim()} className="action-btn-primary">
                  {isCreating ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Key className="w-4 h-4" />}
                  {isCreating ? 'Generating...' : 'Generate key'}
                </button>
                <button onClick={() => setShowCreate(false)} className="action-btn">Cancel</button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card-base overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
            <div className="w-5 h-5 rounded-full border-2 border-current border-t-transparent animate-spin mr-2" />
            Loading API keys...
          </div>
        ) : keys.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Key className="w-8 h-8 mb-3 opacity-40" />
            <p className="text-sm">No API keys yet</p>
            <p className="text-xs mt-1">Create a key to enable programmatic access</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Key</th>
                <th>Scopes</th>
                <th>Last used</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td><span className="text-sm font-medium text-foreground">{k.name}</span></td>
                  <td>
                    <div className="flex items-center gap-2">
                      <code className="text-xs font-mono text-muted-foreground">
                        {revealedKey === k.id ? k.prefix + '••••••' : k.prefix.slice(0, 12) + '••••'}
                      </code>
                      <button onClick={() => setRevealedKey(revealedKey === k.id ? null : k.id)} className="text-muted-foreground hover:text-foreground">
                        {revealedKey === k.id ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>
                      <button onClick={() => handleCopy(k.prefix)} className="text-muted-foreground hover:text-foreground"><Copy className="w-3.5 h-3.5" /></button>
                    </div>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {(k.scopes ?? []).slice(0, 2).map((s) => <code key={s} className="text-xs font-mono badge-medium">{s}</code>)}
                      {(k.scopes ?? []).length > 2 && <span className="text-xs text-muted-foreground">+{k.scopes.length - 2}</span>}
                    </div>
                  </td>
                  <td><span className="text-xs text-muted-foreground">{k.last_used ? formatDate(k.last_used) : 'Never'}</span></td>
                  <td><span className="text-xs text-muted-foreground">{formatDate(k.created_at)}</span></td>
                  <td>
                    <button onClick={() => handleDelete(k.id)} className="p-1.5 rounded-md text-muted-foreground hover:text-red-400 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </motion.div>
  );
}
