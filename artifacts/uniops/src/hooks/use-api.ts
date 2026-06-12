import { useState, effect, useCallback, useRef } from 'react';
import apiClient from '@/services/api/client';

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: (force?: boolean) => void;
}

/**
 * Strip the FastAPI envelope from a response body.
 *
 * Backend wraps everything in:
 *   { success, data: ..., message, code }
 * Paginated endpoints double-wrap:
 *   { success, data: { success, data: [...], total, page, page_size, pages }, ... }
 *
 * This helper unwraps the envelope layer(s) and returns the innermost meaningful
 * payload, so callers always receive the real data (object, array, or scalar).
 */
function unwrap(body: any): any {
  let cur = body;
  // Strip outer APIResponse wrapper if present
  if (cur && typeof cur === 'object' && 'success' in cur && 'data' in cur && 'message' in cur) {
    cur = cur.data;
  }
  // Strip inner PaginatedResponse wrapper if present
  if (cur && typeof cur === 'object' && Array.isArray(cur.data) && typeof cur.total === 'number') {
    return cur;
  }
  return cur;
}

export function useApi<T>(path: string | null, deps: unknown[] = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  // Track the previous path so we can detect repo/endpoint switches
  // vs. plain manual refreshes (tick changes).
  const prevPathRef = useRef<string | null>(null);

  const refetch = useCallback((force?: boolean) => {
    if (force) {
      setData(null);
      setError(null);
    }
    setTick((t) => t + 1);
  }, []);

  effect(() => {
    if (!path) {
      setData(null);
      setLoading(false);
      setError(null);
      prevPathRef.current = null;
      return;
    }

    let cancelled = false;

    // Reset stale data when switching paths
    if (path !== prevPathRef.current) {
      setData(null);
      setError(null);
      prevPathRef.current = path;
    }

    setLoading(true);

    apiClient.get<any>(path)
      .then((res) => {
        if (!cancelled) {
          setData(unwrap(res.data) as T);
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
  }, [path, tick, ...deps]);

  return { data, loading, error, refetch };
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await apiClient.post<any>(path, body);
  return unwrap(res.data) as T;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await apiClient.patch<any>(path, body);
  return unwrap(res.data) as T;
}

export async function apiDelete(path: string): Promise<void> {
  await apiClient.delete(path);
}
