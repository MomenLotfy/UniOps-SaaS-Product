import { useState, useEffect, useCallback, useRef } from 'react';
import apiClient from '@/services/api/client';

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(path: string | null, deps: unknown[] = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  // Track the previous path so we can detect repo/endpoint switches
  // vs. plain manual refreshes (tick changes). Only clear stale data
  // when the path itself changes — a tick-only refresh keeps the
  // existing data visible while the refresh completes (no flash).
  const prevPathRef = useRef<string | null>(null);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!path) {
      // Path became null (e.g. user deselected repo) — clear immediately
      setData(null);
      setLoading(false);
      setError(null);
      prevPathRef.current = null;
      return;
    }

    let cancelled = false;

    // ── Reset stale data when switching paths (repo change, tab change, etc.) ──
    // This prevents data from Repo A briefly showing under Repo B's queries.
    // We do NOT reset on tick-only changes so manual refresh feels smooth.
    if (path !== prevPathRef.current) {
      setData(null);
      setError(null);
      prevPathRef.current = path;
    }

    setLoading(true);

    apiClient.get<any>(path)
      .then((res) => {
        if (!cancelled) {
          const body = res.data;
          setData(body?.data !== undefined ? body.data : body);
          setLoading(false);
        }
      })
      .catch((err: any) => {
        if (!cancelled) {
          setError(err.message ?? 'Request failed');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps]);

  return { data, loading, error, refetch };
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await apiClient.post<any>(path, body);
  const d = res.data;
  return (d?.data !== undefined ? d.data : d) as T;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await apiClient.patch<any>(path, body);
  const d = res.data;
  return (d?.data !== undefined ? d.data : d) as T;
}

export async function apiDelete(path: string): Promise<void> {
  await apiClient.delete(path);
}
