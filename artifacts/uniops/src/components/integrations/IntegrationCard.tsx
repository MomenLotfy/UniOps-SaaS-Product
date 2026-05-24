import { RefreshCw, Trash2, Settings, ExternalLink, MoreHorizontal } from 'lucide-react';
import { clsx } from 'clsx';
import { IntegrationStatus } from './IntegrationStatus';
import { formatRelative } from '@/lib/formatters';
import type { Integration } from '@/types/integration';
import { useState } from 'react';

const PROVIDER_ICONS: Record<string, string> = {
  aws: '🟠',
  gcp: '🔵',
  azure: '🟦',
  github: '⚫',
  gitlab: '🟠',
  kubernetes: '🔷',
  slack: '🟣',
  teams: '🔵',
  jenkins: '⚙️',
  argocd: '🔶',
};

interface IntegrationCardProps {
  integration: Integration;
  onTest?: (id: string) => void;
  onSync?: (id: string) => void;
  onEdit?: (integration: Integration) => void;
  onDelete?: (id: string) => void;
}

export function IntegrationCard({ integration, onTest, onSync, onEdit, onDelete }: IntegrationCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  const handleSync = async () => {
    setIsSyncing(true);
    try { await onSync?.(integration.id); } finally { setIsSyncing(false); }
  };

  return (
    <div className="relative p-4 rounded-xl border transition-all hover:border-border/60"
      style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
            style={{ background: 'hsl(230 15% 12%)', border: '1px solid hsl(230 15% 16%)' }}>
            {PROVIDER_ICONS[integration.provider] ?? '🔌'}
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{integration.name}</p>
            <p className="text-xs text-muted-foreground capitalize">{integration.provider.replace('_', ' ')}</p>
          </div>
        </div>

        <div className="relative">
          <button onClick={() => setMenuOpen((p) => !p)}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
            <MoreHorizontal className="w-4 h-4" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-8 z-50 w-44 rounded-lg border shadow-xl overflow-hidden"
              style={{ background: 'hsl(230 18% 10%)', borderColor: 'hsl(230 15% 14%)' }}>
              {[
                { icon: Settings, label: 'Configure', action: () => { onEdit?.(integration); setMenuOpen(false); } },
                { icon: RefreshCw, label: 'Sync now', action: () => { handleSync(); setMenuOpen(false); } },
                { icon: ExternalLink, label: 'Test connection', action: () => { onTest?.(integration.id); setMenuOpen(false); } },
                { icon: Trash2, label: 'Remove', action: () => { onDelete?.(integration.id); setMenuOpen(false); }, danger: true },
              ].map((item) => (
                <button key={item.label} onClick={item.action}
                  className={clsx('w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-accent',
                    item.danger ? 'text-red-400' : 'text-foreground')}>
                  <item.icon className="w-3.5 h-3.5" />{item.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <IntegrationStatus status={integration.status} />

      <div className="flex items-center justify-between mt-3 pt-3 border-t" style={{ borderColor: 'hsl(230 15% 14%)' }}>
        <div className="text-xs text-muted-foreground">
          {integration.lastSync ? `Synced ${formatRelative(integration.lastSync)}` : 'Never synced'}
        </div>
        <button onClick={handleSync} disabled={isSyncing}
          className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50">
          <RefreshCw className={clsx('w-3 h-3', isSyncing && 'animate-spin')} />
          {isSyncing ? 'Syncing...' : 'Sync'}
        </button>
      </div>
    </div>
  );
}
