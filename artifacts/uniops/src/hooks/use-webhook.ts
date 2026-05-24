import { useEffect, useRef, useCallback } from 'react';
import { useWebSocket } from '@/contexts/WebSocketContext';

type EventHandler<T = unknown> = (data: T) => void;

interface UseWebhookOptions {
  onAlert?: EventHandler;
  onPipelineUpdate?: EventHandler;
  onThreatDetected?: EventHandler;
  onCostAnomaly?: EventHandler;
  onPodStatusChange?: EventHandler;
  onUserActivity?: EventHandler;
}

export function useWebhook(options: UseWebhookOptions = {}) {
  const { subscribe, status, send } = useWebSocket();
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    const unsubscribers: (() => void)[] = [];

    if (optionsRef.current.onAlert) {
      unsubscribers.push(subscribe('alert', (data) => optionsRef.current.onAlert?.(data)));
    }
    if (optionsRef.current.onPipelineUpdate) {
      unsubscribers.push(subscribe('pipeline.updated', (data) => optionsRef.current.onPipelineUpdate?.(data)));
    }
    if (optionsRef.current.onThreatDetected) {
      unsubscribers.push(subscribe('threat.detected', (data) => optionsRef.current.onThreatDetected?.(data)));
    }
    if (optionsRef.current.onCostAnomaly) {
      unsubscribers.push(subscribe('cost.anomaly', (data) => optionsRef.current.onCostAnomaly?.(data)));
    }
    if (optionsRef.current.onPodStatusChange) {
      unsubscribers.push(subscribe('pod.status_changed', (data) => optionsRef.current.onPodStatusChange?.(data)));
    }
    if (optionsRef.current.onUserActivity) {
      unsubscribers.push(subscribe('user.activity', (data) => optionsRef.current.onUserActivity?.(data)));
    }

    return () => unsubscribers.forEach((unsub) => unsub());
  }, [subscribe]);

  const sendEvent = useCallback((type: string, payload?: unknown) => {
    send(type, payload);
  }, [send]);

  return { wsStatus: status, sendEvent };
}
