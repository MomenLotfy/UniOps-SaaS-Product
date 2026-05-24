/**
 * IntegrationsContext.tsx
 *
 * PROBLEM SOLVED
 * ──────────────
 * Before this file: every page that needs to know "is AWS connected?" called
 * either useApi('/integrations') or useIntegrations() independently.
 * With 5 major pages open simultaneously that is 5 identical GET /integrations
 * requests fired in parallel, each maintaining its own loading/error state.
 * If one page updated an integration (e.g. connected Kubernetes), the other
 * four pages still showed the stale "disconnected" badge until their next
 * fetch cycle.
 *
 * After this file: ONE fetch at app startup, shared via React Context.
 * All pages call useIntegrationsCtx() — they subscribe to the same state.
 * Connecting a new integration calls refetch() once and ALL pages update.
 *
 * DESIGN DECISIONS
 * ────────────────
 * 1. Wraps the existing useIntegrations() hook — zero logic duplication.
 * 2. Adds isConnected(provider) helper so pages never need to write
 *    integrations.some(i => i.provider === 'aws' && i.status === 'connected')
 * 3. Provider lives in main.tsx INSIDE AuthProvider so it only fetches when
 *    the user is authenticated (unauthenticated: returns empty state instantly).
 * 4. useIntegrationsCtx() throws if used outside the provider so misuse is
 *    caught at development time, not silently in production.
 *
 * MIGRATION GUIDE (for existing pages)
 * ─────────────────────────────────────
 * Replace:
 *   import { useApi } from '@/hooks/use-api';
 *   const { data: integrationsRaw } = useApi<any>('/integrations');
 *   const integrations = Array.isArray(integrationsRaw) ? integrationsRaw : integrationsRaw?.data ?? [];
 *
 * With:
 *   import { useIntegrationsCtx } from '@/contexts/IntegrationsContext';
 *   const { integrations, isConnected } = useIntegrationsCtx();
 *
 * Replace:
 *   import { useIntegrations } from '@/hooks/use-integrations';
 *   const { integrations, getByProvider } = useIntegrations();
 *
 * With:
 *   import { useIntegrationsCtx } from '@/contexts/IntegrationsContext';
 *   const { integrations, getByProvider } = useIntegrationsCtx();
 */

import {
  createContext,
  useContext,
  type ReactNode,
} from 'react';
import { useIntegrations } from '@/hooks/use-integrations';
import { useAuth } from '@/contexts/AuthContext';
import type { Integration, IntegrationProvider } from '@/types/integration';

// ── Context shape ─────────────────────────────────────────────────────────────

interface IntegrationsCtx {
  /** Full list of integrations for this tenant. */
  integrations:   Integration[];
  /** True while the initial fetch is in-flight. */
  isLoading:      boolean;
  /** Error message string, or null when healthy. */
  error:          string | null;
  /** Re-fetch the integrations list from the API. Call after connect/disconnect. */
  refetch:        () => Promise<void>;
  /** True if at least one integration with this provider has status='connected'. */
  isConnected:    (provider: IntegrationProvider | string) => boolean;
  /** Number of integrations currently in 'connected' status. */
  connectedCount: number;
  /** All integrations in 'connected' status. */
  getConnected:   () => Integration[];
  /** All integrations matching the given provider string. */
  getByProvider:  (provider: IntegrationProvider | string) => Integration[];
  /** Total number of integrations (connected + disconnected). */
  total:          number;
}

// ── Context creation ──────────────────────────────────────────────────────────

const IntegrationsContext = createContext<IntegrationsCtx | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────

interface IntegrationsProviderProps {
  children: ReactNode;
}

export function IntegrationsProvider({ children }: IntegrationsProviderProps) {
  /**
   * Only auto-fetch integrations when the user is authenticated.
   * Without this guard, every page load (including /auth/login) fires
   * GET /integrations which returns 401, triggering the redirect interceptor.
   */
  const { isAuthenticated } = useAuth();
  const hook = useIntegrations({ autoFetch: isAuthenticated });

  /**
   * isConnected: O(n) lookup over the integrations array.
   * n is always small (< 20 integrations per tenant) — no memoization needed.
   * Using an inline function (not useCallback) is intentional: the context
   * value is already stable between re-renders via the hook's own memoization.
   */
  const isConnected = (provider: IntegrationProvider | string): boolean =>
    hook.integrations.some(
      (i) => i.provider === provider && i.status === 'connected',
    );

  const value: IntegrationsCtx = {
    integrations:   hook.integrations,
    isLoading:      hook.isLoading,
    error:          hook.error,
    refetch:        hook.refetch,
    isConnected,
    connectedCount: hook.connectedCount,
    getConnected:   hook.getConnected,
    getByProvider:  hook.getByProvider,
    total:          hook.total,
  };

  return (
    <IntegrationsContext.Provider value={value}>
      {children}
    </IntegrationsContext.Provider>
  );
}

// ── Consumer hook ─────────────────────────────────────────────────────────────

/**
 * useIntegrationsCtx — access the global integrations state from any component.
 *
 * Throws a descriptive error if called outside <IntegrationsProvider>.
 * This surfaces misconfiguration at dev-time instead of silently returning
 * empty state in production.
 *
 * Usage:
 *   const { isConnected, integrations, refetch } = useIntegrationsCtx();
 *   const hasAWS = isConnected('aws');
 */
export function useIntegrationsCtx(): IntegrationsCtx {
  const ctx = useContext(IntegrationsContext);
  if (!ctx) {
    throw new Error(
      '[useIntegrationsCtx] must be used inside <IntegrationsProvider>. ' +
      'Make sure IntegrationsProvider is mounted in main.tsx inside AuthProvider.',
    );
  }
  return ctx;
}
