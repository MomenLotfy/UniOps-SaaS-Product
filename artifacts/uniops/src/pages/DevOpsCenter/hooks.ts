// ─────────────────────────────────────────────────────────────────────────────
// DevOpsCenter — custom hooks
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback, useRef } from 'react';
import { useApi, apiPost, apiDelete } from '@/hooks/use-api';
import { useIntegrationsCtx } from '@/contexts/IntegrationsContext';
import type { PodStats, PipelineStats, LogLine } from './types';

const POLL_INTERVAL = 15_000; // 15 seconds

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
    gitConnected:   isConnected('github') || isConnected('gitlab'),
    k8sIntegration: k8s ?? null,
    gitIntegration: git ?? null,
  };
}

// ── Pods (with 15-second auto-polling) ───────────────────────────────────────
export function usePods(namespace?: string) {
  const qs = new URLSearchParams({ page_size: '100' });
  if (namespace) qs.set('namespace', namespace);

  const { data, loading, error, refetch } = useApi<any>(`/kubernetes/pods?${qs}`);
  const { data: stats, refetch: refetchStats } = useApi<PodStats>('/kubernetes/pods/stats');

  const refetchAll = useCallback(() => { refetch(); refetchStats(); }, [refetch, refetchStats]);

  // Auto-poll every 15 s
  useEffect(() => {
    const id = setInterval(refetchAll, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [refetchAll]);

  return {
    pods:      (Array.isArray(data) ? data : data?.data ?? data ?? []) as any[],
    podStats:  stats as PodStats | null,
    loading,
    error,
    refetch:   refetchAll,
  };
}

// ── Pipelines (with 15-second auto-polling) ───────────────────────────────────
export function usePipelines(repository?: string, branch?: string) {
  const qs = new URLSearchParams({ page_size: '30' });
  if (repository) qs.set('repository', repository);
  if (branch)     qs.set('branch', branch);

  const { data, loading, error, refetch } = useApi<any>(`/pipelines?${qs}`);
  const { data: stats } = useApi<PipelineStats>('/pipelines/stats');

  // Auto-poll every 15 s
  useEffect(() => {
    const id = setInterval(refetch, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [refetch]);

  return {
    pipelines:     (Array.isArray(data) ? data : data?.data ?? []) as any[],
    pipelineStats: stats as PipelineStats | null,
    total:         (data as any)?.total ?? 0,
    loading,
    error,
    refetch,
  };
}

// ── Log streaming (polling every 5 s) ────────────────────────────────────────
export function usePodLogs(podId: string | null, enabled: boolean) {
  const [lines, setLines]     = useState<LogLine[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const intervalRef            = useRef<ReturnType<typeof setInterval> | null>(null);

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

  useEffect(() => {
    if (!enabled || !podId) return;
    setLines([]);
    setLoading(true);
    fetchLogs().finally(() => setLoading(false));

    intervalRef.current = setInterval(fetchLogs, 5_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [enabled, podId, fetchLogs]);

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
      setTimeout(refetchPipelines, 1000);
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
