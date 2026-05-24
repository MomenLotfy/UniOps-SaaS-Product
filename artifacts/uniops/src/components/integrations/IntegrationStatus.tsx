import { CheckCircle, XCircle, Clock, AlertTriangle, Loader } from 'lucide-react';
import { clsx } from 'clsx';

type IntegrationStatusType = 'connected' | 'disconnected' | 'pending' | 'error' | 'syncing';

interface IntegrationStatusProps {
  status: IntegrationStatusType;
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
  connected: { label: 'Connected', color: 'text-green-400', bg: 'bg-green-500/10', icon: CheckCircle },
  disconnected: { label: 'Disconnected', color: 'text-muted-foreground', bg: 'bg-muted/20', icon: XCircle },
  pending: { label: 'Pending', color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: Clock },
  error: { label: 'Error', color: 'text-red-400', bg: 'bg-red-500/10', icon: AlertTriangle },
  syncing: { label: 'Syncing', color: 'text-blue-400', bg: 'bg-blue-500/10', icon: Loader },
};

export function IntegrationStatus({ status, message, showIcon = true, size = 'sm' }: IntegrationStatusProps) {
  const cfg = STATUS_CONFIG[status];
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
