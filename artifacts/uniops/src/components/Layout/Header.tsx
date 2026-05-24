import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Bell,
  ChevronDown,
  CheckCircle,
  AlertTriangle,
  Info,
  XCircle,
  LogOut,
  Settings,
  UserCircle,
  Command,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useStore } from '@/store';
import { useAuth } from '@/contexts/AuthContext';
import { useNotifications } from '@/contexts/NotificationContext';
import { initials } from '@/lib/formatters';
import { ROUTES } from '@/lib/constants';


const notifIcon: Record<string, React.ElementType> = {
  error:   XCircle,
  critical: XCircle,
  warning: AlertTriangle,
  success: CheckCircle,
  info: Info,
};

const notifColor: Record<string, string> = {
  error:   'text-red-400',
  critical: 'text-red-400',
  warning: 'text-yellow-400',
  success: 'text-green-400',
  info: 'text-blue-400',
};

export const Header = () => {
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const { setCommandPaletteOpen } = useStore();
  const { user, logout } = useAuth();
  const { notifications: liveNotifs, unreadCount, markAllAsRead } = useNotifications();
  const navigate = useNavigate();

  const handleLogout = () => { logout(); navigate(ROUTES.LOGIN); };

  return (
    <header
      className="fixed top-0 right-0 left-0 z-40 flex items-center px-4 h-14 border-b border-border"
      style={{ background: 'hsl(230 18% 5% / 0.9)', backdropFilter: 'blur(12px)' }}
    >
      {/* Spacer for sidebar */}
      <div className="flex-1" />

      {/* Search */}
      <button
        onClick={() => setCommandPaletteOpen(true)}
        className={clsx(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
          'text-muted-foreground hover:text-foreground border border-border hover:border-primary/30',
          'bg-surface-1 hover:bg-accent'
        )}
        style={{ minWidth: 200 }}
      >
        <Search className="w-3.5 h-3.5" />
        <span className="flex-1 text-left">Search or run command...</span>
        <div className="flex items-center gap-0.5 ml-2">
          <kbd className="text-xs px-1 py-0.5 rounded border border-border bg-accent font-mono">⌘</kbd>
          <kbd className="text-xs px-1 py-0.5 rounded border border-border bg-accent font-mono">K</kbd>
        </div>
      </button>

      {/* Right actions */}
      <div className="flex items-center gap-2 ml-3">
        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => {
              setShowNotifications(!showNotifications);
              setShowProfile(false);
            }}
            className="relative w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500 ring-2 ring-background" />
            )}
          </button>

          <AnimatePresence>
            {showNotifications && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowNotifications(false)} />
                <motion.div
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8, scale: 0.96 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full mt-2 w-80 rounded-xl border border-border shadow-2xl z-50 overflow-hidden"
                  style={{ background: 'hsl(230 18% 8%)' }}
                >
                  <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                    <h3 className="text-sm font-semibold text-foreground">Notifications</h3>
                    {unreadCount > 0 && (
                      <span className="text-xs text-primary font-medium">{unreadCount} unread</span>
                    )}
                  </div>
                  <div className="flex items-center justify-between px-4 py-2 border-b border-border">
                    <span className="text-xs text-muted-foreground">{unreadCount} unread</span>
                    <button onClick={markAllAsRead} className="text-xs text-primary hover:text-primary/80">Mark all read</button>
                  </div>
                  <div className="divide-y divide-border/50 max-h-72 overflow-y-auto">
                    {liveNotifs.slice(0, 4).map((n) => {
                      const Icon = notifIcon[n.type as keyof typeof notifIcon] ?? Info;
                      return (
                        <div
                          key={n.id}
                          className={clsx(
                            'flex gap-3 px-4 py-3 transition-colors hover:bg-accent/50 cursor-pointer',
                            !n.read && 'bg-primary/5'
                          )}
                        >
                          <Icon className={clsx('w-4 h-4 flex-shrink-0 mt-0.5', notifColor[n.type as keyof typeof notifColor] ?? 'text-blue-400')} />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-2">
                              <p className={clsx('text-xs font-medium leading-tight', !n.read ? 'text-foreground' : 'text-muted-foreground')}>
                                {n.title}
                              </p>
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5 truncate">{n.message}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="px-4 py-2 border-t border-border">
                    <button className="w-full text-center text-xs text-primary hover:text-primary/80 py-1 transition-colors">
                      View all notifications
                    </button>
                  </div>
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </div>

        {/* Profile */}
        <div className="relative">
          <button
            onClick={() => {
              setShowProfile(!showProfile);
              setShowNotifications(false);
            }}
            className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-accent transition-colors"
          >
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-semibold"
              style={{ background: 'linear-gradient(135deg, hsl(220 90% 55%), hsl(260 70% 60%))' }}>
              {user ? initials(user.displayName) : 'U'}
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
          </button>

          <AnimatePresence>
            {showProfile && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowProfile(false)} />
                <motion.div
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8, scale: 0.96 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full mt-2 w-52 rounded-xl border border-border shadow-2xl z-50 overflow-hidden"
                  style={{ background: 'hsl(230 18% 8%)' }}
                >
                  <div className="px-4 py-3 border-b border-border">
                    <p className="text-sm font-semibold text-foreground">{user?.displayName ?? 'User'}</p>
                    <p className="text-xs text-muted-foreground">{user?.email ?? ''}</p>
                  </div>
                  <div className="p-1.5 space-y-0.5">
                    <button onClick={() => { navigate(ROUTES.SETTINGS_PROFILE); setShowProfile(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                      <UserCircle className="w-4 h-4" /> Profile
                    </button>
                    <button onClick={() => { navigate(ROUTES.SETTINGS_SECURITY); setShowProfile(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                      <Settings className="w-4 h-4" /> Settings
                    </button>
                    <div className="border-t border-border my-1" />
                    <button onClick={handleLogout} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors">
                      <LogOut className="w-4 h-4" />
                      Sign out
                    </button>
                  </div>
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
};
