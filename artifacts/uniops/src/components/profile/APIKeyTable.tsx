import { useState } from 'react';
import { Copy, Eye, EyeOff, Trash2, Plus, CheckCircle, Key } from 'lucide-react';
import { clsx } from 'clsx';
import { formatDate } from '@/lib/formatters';

interface APIKey {
  id: string;
  name: string;
  prefix: string;
  lastUsed?: string;
  createdAt: string;
  expiresAt?: string;
  scopes: string[];
  active: boolean;
}

const MOCK_KEYS: APIKey[] = [
  { id: '1', name: 'Production CI/CD', prefix: 'uniops_sk_prod', lastUsed: new Date(Date.now() - 3600000).toISOString(), createdAt: '2025-12-01T00:00:00Z', scopes: ['pipelines:read', 'pods:read'], active: true },
  { id: '2', name: 'Monitoring Script', prefix: 'uniops_sk_mon', lastUsed: new Date(Date.now() - 86400000).toISOString(), createdAt: '2025-11-15T00:00:00Z', expiresAt: '2026-11-15T00:00:00Z', scopes: ['metrics:read'], active: true },
  { id: '3', name: 'Legacy Integration', prefix: 'uniops_sk_leg', createdAt: '2025-09-01T00:00:00Z', scopes: ['all'], active: false },
];

export function APIKeyTable() {
  const [keys, setKeys] = useState(MOCK_KEYS);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');

  const handleCopy = (id: string, value: string) => {
    navigator.clipboard.writeText(value);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleDelete = (id: string) => setKeys((p) => p.filter((k) => k.id !== id));

  const handleCreate = () => {
    if (!newKeyName.trim()) return;
    const newKey: APIKey = {
      id: Date.now().toString(),
      name: newKeyName,
      prefix: `uniops_sk_${newKeyName.toLowerCase().replace(/\s+/g, '_').slice(0, 8)}`,
      createdAt: new Date().toISOString(),
      scopes: ['read'],
      active: true,
    };
    setKeys((p) => [newKey, ...p]);
    setNewKeyName('');
    setShowCreate(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">API keys allow programmatic access to UniOps.</p>
        <button onClick={() => setShowCreate((p) => !p)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          <Plus className="w-3.5 h-3.5" /> New key
        </button>
      </div>

      {showCreate && (
        <div className="flex items-center gap-2 p-3 rounded-xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
          <Key className="w-4 h-4 text-muted-foreground flex-shrink-0" />
          <input
            type="text" placeholder="Key name (e.g. Production CI)" value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            className="flex-1 bg-transparent text-sm outline-none text-foreground placeholder:text-muted-foreground"
          />
          <button onClick={handleCreate} className="text-xs text-blue-400 hover:text-blue-300 font-medium">Create</button>
          <button onClick={() => setShowCreate(false)} className="text-xs text-muted-foreground hover:text-foreground">Cancel</button>
        </div>
      )}

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
                  <code className="text-xs font-mono text-muted-foreground">
                    {revealed === key.id ? `${key.prefix}_xxxxxxxxxxxx` : `${key.prefix.slice(0, 18)}••••••••`}
                  </code>
                  <button onClick={() => setRevealed(revealed === key.id ? null : key.id)}
                    className="text-muted-foreground hover:text-foreground transition-colors">
                    {revealed === key.id ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                  </button>
                  <button onClick={() => handleCopy(key.id, `${key.prefix}_xxxxxxxxxxxx`)}
                    className={clsx('transition-colors', copied === key.id ? 'text-green-400' : 'text-muted-foreground hover:text-foreground')}>
                    {copied === key.id ? <CheckCircle className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  </button>
                </div>
                <div className="flex items-center gap-3 mt-1.5">
                  <span className="text-xs text-muted-foreground">Created {formatDate(key.createdAt)}</span>
                  {key.lastUsed && <span className="text-xs text-muted-foreground">Last used {formatDate(key.lastUsed)}</span>}
                  <div className="flex gap-1">
                    {key.scopes.map((s) => <span key={s} className="text-xs px-1.5 py-0.5 rounded text-blue-400 bg-blue-500/10">{s}</span>)}
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
    </div>
  );
}
