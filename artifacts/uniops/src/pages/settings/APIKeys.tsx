import { useState } from 'react';
import { motion } from 'framer-motion';
import { Key, Plus, Copy, Trash2, Eye, EyeOff, RefreshCw } from 'lucide-react';
import { formatDate } from '@/lib/formatters';
import { clsx } from 'clsx';

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  lastUsed?: string;
  expiresAt?: string;
  createdAt: string;
}

const MOCK_KEYS: ApiKey[] = [
  { id: 'k1', name: 'CI/CD Pipeline', prefix: 'uo_live_sk_abc1', scopes: ['pipelines:read', 'pods:read'], lastUsed: new Date(Date.now() - 3_600_000).toISOString(), createdAt: '2026-01-10T09:00:00Z' },
  { id: 'k2', name: 'Monitoring Script', prefix: 'uo_live_sk_def2', scopes: ['metrics:read', 'alerts:read'], lastUsed: new Date(Date.now() - 86_400_000).toISOString(), expiresAt: '2027-01-10T00:00:00Z', createdAt: '2026-02-15T09:00:00Z' },
  { id: 'k3', name: 'Cost Exporter', prefix: 'uo_live_sk_ghi3', scopes: ['costs:read'], createdAt: '2026-03-01T09:00:00Z' },
];

const ALL_SCOPES = ['pipelines:read', 'pipelines:write', 'pods:read', 'pods:write', 'metrics:read', 'alerts:read', 'alerts:write', 'costs:read', 'threats:read'];

export default function APIKeys() {
  const [keys, setKeys] = useState<ApiKey[]>(MOCK_KEYS);
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState('');

  const handleCreate = async () => {
    if (!newKeyName.trim()) return;
    setIsCreating(true);
    await new Promise((r) => setTimeout(r, 800));
    const newKey = `uo_live_sk_${Math.random().toString(36).slice(2, 10)}xxxxxxxxxxxx`;
    const key: ApiKey = { id: `k${Date.now()}`, name: newKeyName, prefix: newKey.slice(0, 16) + '...', scopes: selectedScopes, createdAt: new Date().toISOString() };
    setKeys((prev) => [key, ...prev]);
    setCreatedKey(newKey);
    setIsCreating(false);
    setNewKeyName('');
    setSelectedScopes([]);
  };

  const handleCopy = (text: string) => { navigator.clipboard?.writeText(text); };
  const handleDelete = (id: string) => setKeys((prev) => prev.filter((k) => k.id !== id));
  const toggleScope = (s: string) => setSelectedScopes((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">API Keys</h1>
          <p className="page-subtitle">Manage API keys for programmatic access</p>
        </div>
        <button onClick={() => setShowCreate((p) => !p)} className="action-btn-primary">
          <Plus className="w-4 h-4" />Create API Key
        </button>
      </div>

      {/* Create form */}
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
                <input value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} placeholder="e.g. CI/CD Pipeline"
                  className="w-full px-3 py-2.5 rounded-lg text-sm text-foreground border outline-none focus:ring-2 focus:ring-blue-500/50" style={inputStyle} />
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
                    <code className="text-xs font-mono text-muted-foreground">{revealedKey === k.id ? k.prefix + '••••••' : k.prefix.slice(0, 12) + '••••'}</code>
                    <button onClick={() => setRevealedKey(revealedKey === k.id ? null : k.id)} className="text-muted-foreground hover:text-foreground">
                      {revealedKey === k.id ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                    <button onClick={() => handleCopy(k.prefix)} className="text-muted-foreground hover:text-foreground"><Copy className="w-3.5 h-3.5" /></button>
                  </div>
                </td>
                <td>
                  <div className="flex flex-wrap gap-1">
                    {k.scopes.slice(0, 2).map((s) => <code key={s} className="text-xs font-mono badge-medium">{s}</code>)}
                    {k.scopes.length > 2 && <span className="text-xs text-muted-foreground">+{k.scopes.length - 2}</span>}
                  </div>
                </td>
                <td><span className="text-xs text-muted-foreground">{k.lastUsed ? formatDate(k.lastUsed) : 'Never'}</span></td>
                <td><span className="text-xs text-muted-foreground">{formatDate(k.createdAt)}</span></td>
                <td>
                  <button onClick={() => handleDelete(k.id)} className="p-1.5 rounded-md text-muted-foreground hover:text-red-400 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
