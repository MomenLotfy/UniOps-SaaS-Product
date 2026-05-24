import { useState, useEffect, useCallback } from 'react';
import { integrationsApi } from '@/services/api/integrations';
import type { Integration } from '@/types/integration';

interface UseIntegrationsOptions {
  autoFetch?: boolean;
}

export function useIntegrations(options: UseIntegrationsOptions = {}) {
  const { autoFetch = true } = options;
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await integrationsApi.list();
      setIntegrations(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load integrations');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (autoFetch) fetch();
  }, [autoFetch, fetch]);

  const testConnection = useCallback(async (id: string) => {
    const result = await integrationsApi.testConnection(id);
    return result;
  }, []);

  const syncNow = useCallback(async (id: string) => {
    await integrationsApi.syncNow(id);
    await fetch();
  }, [fetch]);

  const remove = useCallback(async (id: string) => {
    await integrationsApi.delete(id);
    setIntegrations((prev) => prev.filter((i) => i.id !== id));
  }, []);

  const getByProvider = useCallback(
    (provider: string) => integrations.filter((i) => i.provider === provider),
    [integrations]
  );

  const getConnected = useCallback(
    () => integrations.filter((i) => i.status === 'connected'),
    [integrations]
  );

  return {
    integrations,
    isLoading,
    error,
    refetch: fetch,
    testConnection,
    syncNow,
    remove,
    getByProvider,
    getConnected,
    total: integrations.length,
    connectedCount: integrations.filter((i) => i.status === 'connected').length,
  };
}
