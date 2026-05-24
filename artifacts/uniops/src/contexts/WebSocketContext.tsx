import React, { createContext, useContext, useEffect, useRef, useCallback, useState } from 'react';
import { useAuth } from './AuthContext';

type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface WSMessage {
  event: string;   // ← backend sends 'event', not 'type'
  data:    unknown;
  timestamp?: string;
}

type MessageHandler = (data: unknown) => void;

interface WebSocketContextValue {
  status:    WSStatus;
  send:      (event: string, data?: unknown) => void;
  subscribe: (eventType: string, handler: MessageHandler) => () => void;
  lastPing:  number | null;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

const WS_BASE = import.meta.env.VITE_WS_URL
  ?? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;

const RECONNECT_DELAY         = 3_000;
const MAX_RECONNECT_ATTEMPTS  = 10;
const HEARTBEAT_INTERVAL      = 25_000;

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, tokens, user } = useAuth();
  const ws               = useRef<WebSocket | null>(null);
  const reconnectCount   = useRef(0);
  const reconnectTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimer   = useRef<ReturnType<typeof setInterval> | null>(null);
  const handlers         = useRef<Map<string, Set<MessageHandler>>>(new Map());
  const [status, setStatus]   = useState<WSStatus>('disconnected');
  const [lastPing, setLastPing] = useState<number | null>(null);

  // Store auth values in refs so connect() callback is stable (no re-creation on token change)
  const accessTokenRef = useRef<string | undefined>(tokens?.accessToken);
  const tenantIdRef    = useRef<string>((user as any)?.tenant_id ?? 'unknown');
  const isAuthRef      = useRef<boolean>(isAuthenticated);

  useEffect(() => {
    accessTokenRef.current = tokens?.accessToken;
    tenantIdRef.current    = (user as any)?.tenant_id ?? 'unknown';
    isAuthRef.current      = isAuthenticated;
  });

  const connect = useCallback(() => {
    if (!isAuthRef.current || !accessTokenRef.current) return;
    if (ws.current?.readyState === WebSocket.OPEN) return;

    // tenant_id is part of the backend URL: /ws/{tenant_id}?token=...
    const tenantId = tenantIdRef.current;
    const url = `${WS_BASE}/ws/${tenantId}?token=${accessTokenRef.current}`;

    try {
      setStatus('connecting');
      const socket = new WebSocket(url);
      ws.current = socket;

      socket.onopen = () => {
        setStatus('connected');
        reconnectCount.current = 0;

        // Subscribe to all operational channels on connect
        socket.send(JSON.stringify({
          event: 'subscribe',
          data: {
            channels: [
              'pods', 'pipelines', 'threats', 'costs', 'ml', 'alerts',
            ],
          },
        }));

        // Start heartbeat
        heartbeatTimer.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ event: 'ping', data: {} }));
          }
        }, HEARTBEAT_INTERVAL);
      };

      socket.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data as string);

          // Handle pong from backend
          if (msg.event === 'pong') {
            setLastPing(Date.now());
            return;
          }

          // Dispatch to registered handlers by event name
          const subs = handlers.current.get(msg.event);
          if (subs) subs.forEach((h) => h(msg.data));

          // Wildcard handlers receive the full message envelope
          const wildcards = handlers.current.get('*');
          if (wildcards) wildcards.forEach((h) => h(msg));
        } catch { /* ignore malformed frames */ }
      };

      socket.onerror = () => setStatus('error');

      socket.onclose = () => {
        setStatus('disconnected');
        ws.current = null;
        if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);

        // Exponential back-off reconnect
        if (reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = RECONNECT_DELAY * Math.pow(1.5, reconnectCount.current);
          reconnectCount.current++;
          reconnectTimer.current = setTimeout(connect, delay);
        }
      };
    } catch {
      setStatus('error');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // stable: reads auth state from refs, not reactive deps

  useEffect(() => {
    if (isAuthenticated) {
      connect();
    } else {
      ws.current?.close();
      setStatus('disconnected');
    }
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
      ws.current?.close();
    };
  }, [isAuthenticated, connect]);

  const send = useCallback((event: string, data?: unknown) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        event,
        data: data ?? {},
        timestamp: new Date().toISOString(),
      }));
    }
  }, []);

  const subscribe = useCallback(
    (eventType: string, handler: MessageHandler): (() => void) => {
      if (!handlers.current.has(eventType)) {
        handlers.current.set(eventType, new Set());
      }
      handlers.current.get(eventType)!.add(handler);
      return () => handlers.current.get(eventType)?.delete(handler);
    },
    [],
  );

  return (
    <WebSocketContext.Provider value={{ status, send, subscribe, lastPing }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error('useWebSocket must be used within WebSocketProvider');
  return ctx;
}
