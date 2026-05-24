/**
 * auth.ts — Auth API service (uses AuthContext for state, direct API calls for network)
 *
 * BACKEND CONTRACT (from app/schemas/auth.py)
 * ──────────────────────────────────────────
 * POST /auth/login        → { email, password }
 *                         ← APIResponse<TokenResponse>
 *
 * POST /auth/register     → { email, username, full_name, password, company_name? }
 *                         ← APIResponse<TokenResponse>
 *
 * POST /auth/refresh      → { refresh_token }   ← snake_case
 *                         ← APIResponse<TokenResponse>
 *
 * TokenResponse shape (FLAT — no nesting):
 *   { access_token, refresh_token, token_type, expires_in, user: { id, email, full_name, ... } }
 *
 * FIXES APPLIED:
 * 1. Reads flat token response (not payload.tokens)
 * 2. Reads user from response.data.user (not payload.user from a nested structure)
 * 3. Sends snake_case to backend (refresh_token, not refreshToken)
 * 4. Uses bare axios for refresh to avoid triggering 401 interceptor recursively
 */

import apiClient from '@/services/api/client';
import { TOKEN_KEY, REFRESH_TOKEN_KEY, USER_KEY } from '@/lib/constants';
import type { LoginCredentials, RegisterData, AuthTokens } from '@/types/user';

// ── Backend response shapes ───────────────────────────────────────────────────
export interface BackendUserInfo {
  id:          string;
  email:       string;
  full_name:   string;
  username:    string;
  role:        string;
  tenant_id:   string;
  is_active:   boolean;
  is_verified: boolean;
  avatar_url?: string | null;
}

export interface BackendTokenResponse {
  access_token:  string;
  refresh_token: string;
  token_type:    string;
  expires_in:    number;
  user:          BackendUserInfo;
}

interface ApiResponse<T> {
  data:    T;
  message: string;
  success: boolean;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function toAuthTokens(raw: BackendTokenResponse): AuthTokens {
  return {
    accessToken:  raw.access_token,
    refreshToken: raw.refresh_token,
    expiresAt:    Date.now() + raw.expires_in * 1_000,
  };
}

function storeTokens(tokens: AuthTokens): void {
  localStorage.setItem(TOKEN_KEY,         tokens.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
}

function clearStoredAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// ── Public API ────────────────────────────────────────────────────────────────
export const authApi = {

  async login(credentials: LoginCredentials): Promise<{ tokens: AuthTokens; user: BackendUserInfo }> {
    const { data: body } = await apiClient.post<ApiResponse<BackendTokenResponse>>(
      '/auth/login',
      { email: credentials.email, password: credentials.password },
    );
    // body.data is the flat TokenResponse — NOT nested under .tokens
    const tokens = toAuthTokens(body.data);
    storeTokens(tokens);
    return { tokens, user: body.data.user };
  },

  async register(data: RegisterData): Promise<{ tokens: AuthTokens; user: BackendUserInfo }> {
    const username  = data.email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_');
    const full_name = [data.firstName, data.lastName].filter(Boolean).join(' ') || username;

    const { data: body } = await apiClient.post<ApiResponse<BackendTokenResponse>>(
      '/auth/register',
      {
        email:    data.email,
        username,
        full_name,
        password: data.password,
      },
    );
    const tokens = toAuthTokens(body.data);
    storeTokens(tokens);
    return { tokens, user: body.data.user };
  },

  /**
   * Exchange refresh token for a new pair.
   * Uses bare axios (not apiClient) to avoid 401 interceptor recursion.
   * Sends { refresh_token } in snake_case as backend Pydantic model requires.
   */
  async refreshToken(refreshToken: string): Promise<AuthTokens> {
    const { default: axios } = await import('axios');
    const { API_BASE_URL }   = await import('@/lib/constants');

    const { data: body } = await axios.post<ApiResponse<BackendTokenResponse>>(
      `${API_BASE_URL}/auth/refresh`,
      { refresh_token: refreshToken },   // ← snake_case
      { headers: { 'Content-Type': 'application/json' } },
    );
    const tokens = toAuthTokens(body.data);
    storeTokens(tokens);
    return tokens;
  },

  async logout(): Promise<void> {
    try {
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      await apiClient.post('/auth/logout', null, {
        headers: refreshToken ? { 'X-Refresh-Token': refreshToken } : {},
      });
    } catch {
      // Intentionally silent
    } finally {
      clearStoredAuth();
    }
  },

  async requestPasswordReset(email: string): Promise<void> {
    await apiClient.post('/auth/forgot-password', { email });
  },

  async resetPassword(token: string, newPassword: string): Promise<void> {
    await apiClient.post('/auth/reset-password', {
      token,
      new_password: newPassword,
    });
  },

  async verifyTwoFactor(code: string): Promise<void> {
    await apiClient.post('/auth/2fa/verify', { code });
  },

  async verifyEmail(token: string): Promise<void> {
    await apiClient.post('/auth/verify-email', { token });
  },
};
