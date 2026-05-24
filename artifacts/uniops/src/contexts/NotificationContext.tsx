import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiClient from '@/services/api/client';

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  read: boolean;
  createdAt: string;
  link?: string;
}

interface NotificationContextValue {
  notifications: Notification[];
  unreadCount: number;
  addNotification: (n: Omit<Notification, 'id' | 'read' | 'createdAt'>) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  removeNotification: (id: string) => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

const SEV_TO_TYPE: Record<string, Notification['type']> = {
  critical: 'error', high: 'error', medium: 'warning',
  low: 'info', info: 'info', warning: 'warning',
};

function alertToNotification(a: any): Notification {
  return {
    id:        String(a.id),
    title:     a.title   ?? a.message ?? 'Alert',
    message:   a.message ?? a.title   ?? '',
    type:      SEV_TO_TYPE[a.severity ?? 'info'] ?? 'info',
    read:      a.status === 'resolved' || a.status === 'dismissed',
    createdAt: a.created_at ?? new Date().toISOString(),
  };
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    apiClient.get<any>('/alerts', { params: { page_size: 10 } })
      .then((res) => {
        const raw = res.data;
        // FastAPI wraps: { success, data: { data: [...], total, ... } }
        const items: any[] = raw?.data?.data ?? raw?.data ?? [];
        if (Array.isArray(items) && items.length > 0) {
          setNotifications(items.map(alertToNotification));
        }
      })
      .catch(() => {});
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const addNotification = useCallback((n: Omit<Notification, 'id' | 'read' | 'createdAt'>) => {
    setNotifications((prev) => [
      { ...n, id: crypto.randomUUID(), read: false, createdAt: new Date().toISOString() },
      ...prev,
    ]);
  }, []);

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, read: true } : n));
    apiClient.patch(`/alerts/${id}`, { status: 'resolved' }).catch(() => {});
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    apiClient.post('/alerts/bulk/mark-read', {}).catch(() => {});
  }, []);

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return (
    <NotificationContext.Provider value={{ notifications, unreadCount, addNotification, markAsRead, markAllAsRead, removeNotification }}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useNotifications must be used within NotificationProvider');
  return ctx;
}
