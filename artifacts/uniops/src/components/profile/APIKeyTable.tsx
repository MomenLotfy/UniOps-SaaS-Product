import { useState, useEffect } from 'react';
import { Copy, Trash2, Plus, CheckCircle, Key, RefreshCw } from 'lucide-react';
import { clsx } from 'clsx';
import { formatDate } from '@/lib/formatters';
import apiClient from '@/services/api/client';

interface APIKey {
  id: string;
  name: string;
  prefix: string;
  last_used?: string;
  created_at: string;
  expires_at?: string;
  scopes: string[];
  active: boolean;
}

export function APIKeyTable() {
  const [keys, setKeys]             = useState<APIKey[]>([]);
  const [loading, setLoading]       = useState(true);
  const [copied, setCopied]         = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [creating, setCreating]     = useState(false);
  const [createdKey, setCreatedKey] = useState('');

  const loadKeys = () => {
    setLoading(true);
    apiClient.get<any>('/api-keys')
      .then((res) => {
        const items: APIKey[] = res.data?.data ?? [];
        setKeys(Array.isArray(items) ? items : []);
      })
      .catch(() => setKeys([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadKeys(); }, []);

  const handleCopy = (id: string, value: string) => {
    navigator.clipboard.writeText(value);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleDelete = async (id: string) => {
    await apiClient.delete(`/api-keys/${id}`).catch(() => null);
    setKeys((p) => p.filter((k) => k.id !== id));
  };

  const handleCreate = async () => {
    if (!newKeyName.trim()) return;
    setCreating(true);
    try {
      const res = await apiClient.post<any>('/api-keys', { name: newKeyName, scopes: ['read'] });
      const created = res.data?.data;
      if (created?.key) setCreatedKey(created.key);
      await loadKeys();
      setNewKeyName('');
      setShowCreate(false);
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
        <div className="w-4 h-4 rounded-full border-2 border-current border-t-transparent animate-spin mr-2" />
        Loading...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {createdKey && (
        <div className="p-3 rounded-lg text-xs" style={{ background: 'hsl(160 84% 39% / 0.08)', border: '1px solid hsl(160 84% 39% / 0.2)' }}>
          <p className="text-green-400 font-semibold mb-1">Key created — save it now, it won't be shown again:</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 font-mono text-green-300 break-all">{createdKey}</code>
            <button onClick={() => handleCopy('new', createdKey)} className="text-muted-foreground hover:text-foreground">
              {copied === 'new' ? <CheckCircle className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
          <button onClick={() => setCreatedKey('')} className="mt-2 text-xs text-muted-foreground hover:text-foreground">Dismiss</button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">API keys allow programmatic access to UniOps.</p>
        <div className="flex items-center gap-1.5">
          <button onClick={loadKeys}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground border border-border/50 hover:bg-accent/50 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setShowCreate((p) => !p)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
            <Plus className="w-3.5 h-3.5" /> New key
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="flex items-center gap-2 p-3 rounded-xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
          <Key className="w-4 h-4 text-muted-foreground flex-shrink-0" />
          <input type="text" placeholder="Key name (e.g. Production CI)" value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            className="flex-1 bg-transparent text-sm outline-none text-foreground placeholder:text-muted-foreground" />
          <button onClick={handleCreate} disabled={creating || !newKeyName.trim()}
            className="text-xs text-blue-400 hover:text-blue-300 font-medium disabled:opacity-50">
            {creating ? 'Creating...' : 'Create'}
          </button>
          <button onClick={() => setShowCreate(false)} className="text-xs text-muted-foreground hover:text-foreground">Cancel</button>
        </div>
      )}

      {keys.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
          <Key className="w-6 h-6 mb-2 opacity-40" />
          <p className="text-sm">No API keys yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map((key) => (
            <div key={key.id} className={clsx('p-4 rounded-xl border transition-opacity', !key.active && 'opacity-50')}
              style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-sm font-medium text-foreground">{key.name}</p>
                    {!key.active && <span className="text-xs px-1.5 py-0.5 rounded text-red-400 bg-red-500/10">Inactive</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <code className="text-xs font-mono text-muted-foreground">{key.prefix}••••••••</code>
                    <button onClick={() => handleCopy(key.id, key.prefix)}
                      className={clsx('transition-colors', copied === key.id ? 'text-green-400' : 'text-muted-foreground hover:text-foreground')}>
                      {copied === key.id ? <CheckCircle className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className="text-xs text-muted-foreground">Created {formatDate(key.created_at)}</span>
                    {key.last_used && <span className="text-xs text-muted-foreground">Last used {formatDate(key.last_used)}</span>}
                    <div className="flex gap-1">
                      {(key.scopes ?? []).map((s) => <span key={s} className="text-xs px-1.5 py-0.5 rounded text-blue-400 bg-blue-500/10">{s}</span>)}
                    </div>
                  </div>
                </div>
                <button onClick={() => handleDelete(key.id)}
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors flex-shrink-0">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
