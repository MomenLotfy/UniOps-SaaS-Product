import { CheckCircle, XCircle, Clock, AlertTriangle, Loader, WifiOff } from 'lucide-react';
import { clsx } from 'clsx';

// All known statuses — old 'error' maps to credentials_invalid for display
type IntegrationStatusType =
  | 'connected'
  | 'sync_failed'
  | 'credentials_invalid'
  | 'pending'
  | 'error'
  | 'syncing'
  | 'disconnected';

interface IntegrationStatusProps {
  status: string;  // use string so unknown statuses don't crash
  message?: string;
  showIcon?: boolean;
  size?: 'sm' | 'md';
}

const STATUS_CONFIG: Record<IntegrationStatusType, {
  label: string;
  color: string;
  bg: string;
  icon: React.ElementType;
}> = {
  connected:           { label: 'Connected',           color: 'text-green-400',            bg: 'bg-green-500/10',   icon: CheckCircle  },
  sync_failed:         { label: 'Sync Failed',          color: 'text-orange-400',           bg: 'bg-orange-500/10', icon: AlertTriangle },
  credentials_invalid: { label: 'Invalid Credentials',  color: 'text-red-400',              bg: 'bg-red-500/10',    icon: XCircle      },
  pending:             { label: 'Verifying…',           color: 'text-yellow-400',           bg: 'bg-yellow-500/10', icon: Clock        },
  error:               { label: 'Invalid Credentials',  color: 'text-red-400',              bg: 'bg-red-500/10',    icon: XCircle      },
  syncing:             { label: 'Syncing',              color: 'text-blue-400',             bg: 'bg-blue-500/10',   icon: Loader       },
  disconnected:        { label: 'Not Connected',        color: 'text-muted-foreground',     bg: 'bg-muted/20',      icon: WifiOff      },
};

const FALLBACK_CONFIG = { label: 'Unknown', color: 'text-muted-foreground', bg: 'bg-muted/20', icon: Clock };

export function IntegrationStatus({ status, message, showIcon = true, size = 'sm' }: IntegrationStatusProps) {
  const cfg = STATUS_CONFIG[status as IntegrationStatusType] ?? FALLBACK_CONFIG;
  const Icon = cfg.icon;

  return (
    <div className="flex items-center gap-2">
      <span className={clsx(
        'inline-flex items-center gap-1.5 rounded-md font-medium',
        cfg.color, cfg.bg,
        size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-2.5 py-1'
      )}>
        {showIcon && <Icon className={clsx(size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5', status === 'syncing' && 'animate-spin')} />}
        {cfg.label}
      </span>
      {message && <span className="text-xs text-muted-foreground">{message}</span>}
    </div>
  );
}
