import { useState, useEffect, useCallback } from 'react';
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

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

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
