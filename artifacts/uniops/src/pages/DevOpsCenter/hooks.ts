// ─────────────────────────────────────────────────────────────────────────────
// DevOpsCenter — custom hooks (WebSocket-driven, no polling)
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback, useRef } from 'react';
import { useApi, apiPost, apiDelete } from '@/hooks/use-api';
import { useIntegrationsCtx } from '@/contexts/IntegrationsContext';
import { useWebSocket } from '@/contexts/WebSocketContext';
import type { PodStats, PipelineStats, LogLine } from './types';

// Safety-net fallback interval — only fires if WebSocket is disconnected
// 60s is acceptable because WS delivers updates instantly when connected
const FALLBACK_INTERVAL_MS = 60_000;

// Pod WS events that should trigger a data refresh
const POD_WS_EVENTS = ['pod.update', 'pod.failed', 'pod.restarted', 'integration.sync_done'];
// Pipeline WS events that should trigger a data refresh
const PIPE_WS_EVENTS = ['pipeline.update', 'pipeline.started', 'pipeline.completed', 'pipeline.failed'];

// ── Integration status (reads from global context — no HTTP request) ──────────
export function useDevOpsIntegrations() {
  const { integrations, isLoading, isConnected } = useIntegrationsCtx();

  const k8s = integrations.find(
    (i) => i.provider === 'kubernetes' && i.status === 'connected'
  );
  const git = integrations.find(
    (i) => (i.provider === 'github' || i.provider === 'gitlab') && i.status === 'connected'
  );

  return {
    isLoading,
    k8sConnected:   isConnected('kubernetes'),
    gitConnected:   isConnected('github') || isConnected('gitlab'), githubConnected: isConnected('github'), gitlabConnected: isConnected('gitlab'),
    k8sIntegration: k8s ?? null,
    gitIntegration: git ?? null,
  };
}

// ── Pods — WebSocket-driven, no polling ──────────────────────────────────────
export function usePods(namespace?: string) {
  const qs = new URLSearchParams({ page_size: '100' });
  if (namespace) qs.set('namespace', namespace);

  const { data, loading, error, refetch } = useApi<any>(`/kubernetes/pods?${qs}`);
  const { data: stats, refetch: refetchStats } = useApi<PodStats>('/kubernetes/pods/stats');
  const { subscribe, status: wsStatus } = useWebSocket();

  const refetchAll = useCallback((force?: boolean) => {
    refetch(force);
    refetchStats(force);
  }, [refetch, refetchStats]);

  // Subscribe to WebSocket pod events — instant updates when WS is connected
  useEffect(() => {
    const unsubs = POD_WS_EVENTS.map((evt) =>
      subscribe(evt, () => refetchAll(false))
    );
    return () => unsubs.forEach((u) => u());
  }, [subscribe, refetchAll]);

  // Safety-net fallback: only poll when WebSocket is NOT connected
  useEffect(() => {
    if (wsStatus === 'connected') return;
    const id = setInterval(refetchAll, FALLBACK_INTERVAL_MS);
    return () => clearInterval(id);
  }, [wsStatus, refetchAll]);

  return {
    pods:     (Array.isArray(data) ? data : data?.data ?? data ?? []) as any[],
    podStats: stats as PodStats | null,
    loading,
    error,
    refetch:  (force?: boolean) => refetchAll(force),
  };
}

// ── Pipelines — WebSocket-driven, no polling ─────────────────────────────────
export function usePipelines(repository?: string, branch?: string) {
  const qs = new URLSearchParams({ page_size: '30' });
  if (repository) qs.set('repository', repository);
  if (branch)     qs.set('branch', branch);

  const { data, loading, error, refetch } = useApi<any>(`/pipelines?${qs}`);
  const { data: stats } = useApi<PipelineStats>('/pipelines/stats');
  const { subscribe, status: wsStatus } = useWebSocket();

  // Subscribe to WebSocket pipeline events — instant updates when WS is connected
  useEffect(() => {
    const unsubs = PIPE_WS_EVENTS.map((evt) =>
      subscribe(evt, () => refetch())
    );
    return () => unsubs.forEach((u) => u());
  }, [subscribe, refetch]);

  // Safety-net fallback: only poll when WebSocket is NOT connected
  useEffect(() => {
    if (wsStatus === 'connected') return;
    const id = setInterval(refetch, FALLBACK_INTERVAL_MS);
    return () => clearInterval(id);
  }, [wsStatus, refetch]);

  return {
    pipelines:     (Array.isArray(data) ? data : data?.data ?? []) as any[],
    pipelineStats: stats as PipelineStats | null,
    total:         (data as any)?.total ?? 0,
    loading,
    error,
    refetch,
  };
}

// ── Pod log streaming — WS-triggered refetch, no aggressive polling ───────────
export function usePodLogs(podId: string | null, enabled: boolean) {
  const [lines, setLines]     = useState<LogLine[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const intervalRef           = useRef<ReturnType<typeof setInterval> | null>(null);
  const { subscribe, status: wsStatus } = useWebSocket();

  const fetchLogs = useCallback(async () => {
    if (!podId) return;
    try {
      const { default: apiClient } = await import('@/services/api/client');
      // podId is "namespace/name" — maps to /:namespace/:name/logs
      const res  = await apiClient.get<any>(`/kubernetes/pods/${podId}/logs?tail=200`);
      const json = res.data;
      const raw: string = json?.data?.content ?? json?.content ?? json?.data ?? '';
      const parsed: LogLine[] = (typeof raw === 'string' ? raw : '')
        .split('\n')
        .filter(Boolean)
        .map((text: string) => {
          const m = text.match(/^(\d{4}-\d{2}-\d{2}T[\d:.Z+-]+)\s+(.*)/);
          return m ? { timestamp: m[1], text: m[2] } : { text };
        });
      setLines(parsed);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? 'Failed to fetch logs');
    }
  }, [podId]);

  // Initial fetch + subscribe to pod events to refresh logs reactively
  useEffect(() => {
    if (!enabled || !podId) return;
    setLines([]);
    setLoading(true);
    fetchLogs().finally(() => setLoading(false));

    // Refresh logs when this specific pod gets a WS update
    const unsubs = [...POD_WS_EVENTS, 'k8s.events'].map((evt) =>
      subscribe(evt, (data: any) => {
        // Only refetch if the event is for our pod (or no pod_id in payload)
        const evtPod = data?.pod_id ?? data?.name;
        if (!evtPod || podId.includes(evtPod)) {
          fetchLogs();
        }
      })
    );

    return () => unsubs.forEach((u) => u());
  }, [enabled, podId, fetchLogs, subscribe]);

  // Fallback poll — 30s when WS is connected, 15s when disconnected
  // (much gentler than previous 5s aggressive polling)
  useEffect(() => {
    if (!enabled || !podId) return;
    const interval = wsStatus === 'connected' ? 30_000 : 15_000;
    intervalRef.current = setInterval(fetchLogs, interval);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [enabled, podId, fetchLogs, wsStatus]);

  return { lines, loading, error };
}

// ── Pod actions ───────────────────────────────────────────────────────────────
export function usePodActions(refetchPods: () => void) {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  // podId = "namespace/name"
  const restart = useCallback(async (podId: string): Promise<string> => {
    setLoading(true); setError(null);
    try {
      const res: any = await apiPost(`/kubernetes/pods/${podId}/restart`, {});
      refetchPods();
      return res?.message ?? 'Pod restart initiated';
    } catch (e: any) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [refetchPods]);

  const forceDelete = useCallback(async (podId: string): Promise<string> => {
    setLoading(true); setError(null);
    try {
      await apiDelete(`/kubernetes/pods/${podId}`);
      refetchPods();
      return 'Pod force-deleted';
    } catch (e: any) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [refetchPods]);

  return { loading, error, restart, forceDelete };
}

// ── Pipeline actions ──────────────────────────────────────────────────────────
export function usePipelineActions(refetchPipelines: () => void) {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const rerun = useCallback(async (pipelineId: string, failedOnly = true): Promise<string> => {
    setLoading(true); setError(null);
    try {
      const res: any = await apiPost(
        `/pipelines/${pipelineId}/rerun?failed_only=${failedOnly}`,
        {}
      );
      // WS event will trigger refetch automatically; optimistic 1.5s local refresh as fallback
      setTimeout(refetchPipelines, 1500);
      return res?.message ?? 'Pipeline re-run queued';
    } catch (e: any) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [refetchPipelines]);

  const cancel = useCallback(async (pipelineId: string): Promise<string> => {
    setLoading(true); setError(null);
    try {
      const res: any = await apiPost(`/pipelines/${pipelineId}/cancel`, {});
      // WS event will trigger refetch automatically; optimistic local refresh as fallback
      setTimeout(refetchPipelines, 800);
      return res?.message ?? 'Pipeline cancelled';
    } catch (e: any) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [refetchPipelines]);

  return { loading, error, rerun, cancel };
}
