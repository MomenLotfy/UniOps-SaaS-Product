import { Monitor, Smartphone, Globe, LogOut, Shield } from 'lucide-react';
import { clsx } from 'clsx';
import { formatRelative } from '@/lib/formatters';
import type { UserSession } from '@/types/user';

const MOCK_SESSIONS: UserSession[] = [
  { id: 'sess_1', device: 'MacBook Pro', browser: 'Chrome 124', os: 'macOS 14', ip: '192.168.1.45', location: 'Cairo, EG', current: true, lastActive: new Date().toISOString() },
  { id: 'sess_2', device: 'iPhone 15', browser: 'Safari', os: 'iOS 17', ip: '5.22.103.12', location: 'Dubai, AE', current: false, lastActive: new Date(Date.now() - 3600000 * 2).toISOString() },
  { id: 'sess_3', device: 'Windows PC', browser: 'Edge 124', os: 'Windows 11', ip: '82.44.15.200', location: 'London, UK', current: false, lastActive: new Date(Date.now() - 3600000 * 24).toISOString() },
];

interface SessionManagementProps {
  sessions?: UserSession[];
  onRevoke?: (sessionId: string) => void;
  onRevokeAll?: () => void;
}

function DeviceIcon({ os }: { os: string }) {
  if (os.toLowerCase().includes('ios') || os.toLowerCase().includes('android')) return <Smartphone className="w-5 h-5" />;
  return <Monitor className="w-5 h-5" />;
}

export function SessionManagement({ sessions = MOCK_SESSIONS, onRevoke, onRevokeAll }: SessionManagementProps) {
  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-blue-400" />
          <p className="text-sm text-foreground font-medium">Active Sessions ({sessions.length})</p>
        </div>
        {sessions.length > 1 && (
          <button onClick={onRevokeAll}
            className="text-xs text-red-400 hover:text-red-300 font-medium transition-colors px-2 py-1 rounded hover:bg-red-500/10">
            Revoke all other sessions
          </button>
        )}
      </div>

      <div className="space-y-2">
        {sessions.map((session) => (
          <div key={session.id}
            className={clsx('flex items-center gap-4 p-4 rounded-xl border transition-all', session.current && 'ring-1 ring-blue-500/30')}
            style={{ background: 'hsl(230 18% 8%)', borderColor: session.current ? 'hsl(220 90% 60% / 0.2)' : 'hsl(230 15% 14%)' }}>
            <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: session.current ? 'hsl(220 90% 60% / 0.15)' : 'hsl(230 15% 12%)' }}>
              <DeviceIcon os={session.os} />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <p className="text-sm font-medium text-foreground truncate">{session.device} · {session.browser}</p>
                {session.current && (
                  <span className="text-xs px-1.5 py-0.5 rounded font-medium text-blue-400 bg-blue-500/10 flex-shrink-0">Current</span>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Globe className="w-3 h-3" />
                <span>{session.location}</span>
                <span className="text-muted-foreground/40">·</span>
                <span className="font-mono">{session.ip}</span>
                <span className="text-muted-foreground/40">·</span>
                <span>{formatRelative(session.lastActive)}</span>
              </div>
            </div>

            {!session.current && (
              <button onClick={() => onRevoke?.(session.id)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-red-400 hover:bg-red-500/10 transition-colors flex-shrink-0 border border-red-500/20">
                <LogOut className="w-3 h-3" /> Revoke
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
