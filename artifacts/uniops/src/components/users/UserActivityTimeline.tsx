import { Shield, LogIn, LogOut, Settings, Key, Users, AlertTriangle, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { formatRelative } from '@/lib/formatters';
import type { AuditLog } from '@/types/audit';

interface UserActivityTimelineProps {
  logs: AuditLog[];
  isLoading?: boolean;
  maxItems?: number;
}

const ACTION_CONFIG: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  login: { icon: LogIn, color: 'text-green-400', bg: 'bg-green-500/10' },
  logout: { icon: LogOut, color: 'text-muted-foreground', bg: 'bg-muted/20' },
  password_change: { icon: Key, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  settings_update: { icon: Settings, color: 'text-blue-400', bg: 'bg-blue-500/10' },
  user_invite: { icon: Users, color: 'text-purple-400', bg: 'bg-purple-500/10' },
  security_alert: { icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10' },
  role_change: { icon: Shield, color: 'text-orange-400', bg: 'bg-orange-500/10' },
  default: { icon: CheckCircle, color: 'text-blue-400', bg: 'bg-blue-500/10' },
};

export function UserActivityTimeline({ logs, isLoading, maxItems = 20 }: UserActivityTimelineProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-start gap-3 animate-pulse">
            <div className="w-7 h-7 rounded-full bg-accent flex-shrink-0" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3 bg-accent rounded w-3/4" />
              <div className="h-2.5 bg-accent rounded w-1/2" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!logs.length) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-2">
        <p className="text-sm text-muted-foreground">No activity found</p>
      </div>
    );
  }

  const displayed = logs.slice(0, maxItems);

  return (
    <div className="relative">
      <div className="absolute left-3.5 top-0 bottom-0 w-px bg-border" />
      <div className="space-y-4">
        {displayed.map((log, idx) => {
          const cfg = ACTION_CONFIG[log.action] ?? ACTION_CONFIG.default;
          const Icon = cfg.icon;
          return (
            <div key={log.id ?? idx} className="flex items-start gap-3 relative pl-0.5">
              <div className={clsx('w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 z-10', cfg.bg)}>
                <Icon className={clsx('w-3.5 h-3.5', cfg.color)} />
              </div>
              <div className="flex-1 min-w-0 pb-1">
                <p className="text-sm text-foreground leading-snug">{log.action.replace(/\./g, ' ')}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-muted-foreground">{formatRelative(log.createdAt)}</span>
                  {log.ip && (
                    <>
                      <span className="text-muted-foreground/40">·</span>
                      <span className="text-xs text-muted-foreground font-mono">{log.ip}</span>
                    </>
                  )}
                  {log.status && (
                    <>
                      <span className="text-muted-foreground/40">·</span>
                      <span className={clsx('text-xs capitalize font-medium', log.status === 'success' ? 'text-green-400' : 'text-red-400')}>
                        {log.status}
                      </span>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
