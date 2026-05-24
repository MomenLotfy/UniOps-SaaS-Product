import React, { createContext, useContext, useState, useCallback } from 'react';

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

const INITIAL: Notification[] = [
  { id: '1', title: 'SQL Injection Blocked', message: 'Threat THR-001 blocked from 185.142.53.179', type: 'error', read: false, createdAt: new Date(Date.now() - 300_000).toISOString() },
  { id: '2', title: 'Deployment Succeeded', message: 'api-gateway v2.1.0 deployed to production', type: 'success', read: false, createdAt: new Date(Date.now() - 7_200_000).toISOString() },
  { id: '3', title: 'Cost Anomaly Detected', message: 'EC2 spend +45% above forecast threshold', type: 'warning', read: true, createdAt: new Date(Date.now() - 10_800_000).toISOString() },
  { id: '4', title: 'ML Analysis Complete', message: '24 patterns discovered with 92% accuracy', type: 'info', read: true, createdAt: new Date(Date.now() - 18_000_000).toISOString() },
];

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>(INITIAL);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const addNotification = useCallback((n: Omit<Notification, 'id' | 'read' | 'createdAt'>) => {
    setNotifications((prev) => [
      { ...n, id: Math.random().toString(36).slice(2), read: false, createdAt: new Date().toISOString() },
      ...prev,
    ]);
  }, []);

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, read: true } : n));
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
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
