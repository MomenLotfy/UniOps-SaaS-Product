import React, { createContext, useContext, useEffect, useReducer, useCallback } from 'react';
import type { User, LoginCredentials, RegisterData, AuthTokens } from '@/types/user';
import { TOKEN_KEY, REFRESH_TOKEN_KEY, USER_KEY } from '@/lib/constants';
import apiClient from '@/services/api/client';

// ── Shape of what the backend actually sends ──────────────────────────────────
interface BackendUserInfo {
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

interface BackendTokenResponse {
  access_token:  string;
  refresh_token: string;
  token_type:    string;
  expires_in:    number;   // seconds
  user:          BackendUserInfo;
}

interface BackendAPIResponse<T> {
  success: boolean;
  data:    T;
  message: string;
}

// ── Map backend snake_case user → frontend camelCase User ─────────────────────
function mapBackendUser(u: BackendUserInfo): User {
  const fullName = u.full_name ?? u.username ?? u.email;
  const parts    = fullName.split(' ');
  return {
    id:               u.id,
    email:            u.email,
    firstName:        parts[0] ?? '',
    lastName:         parts.slice(1).join(' ') ?? '',
    displayName:      fullName || u.email,
    role:             (u.role ?? 'viewer') as User['role'],
    status:           u.is_active ? 'active' : 'inactive',
    companyId:        u.tenant_id ?? '',
    teamIds:          [],
    permissions:      [],
    createdAt:        new Date().toISOString(),
    updatedAt:        new Date().toISOString(),
    twoFactorEnabled: false,
    emailVerified:    u.is_verified ?? false,
    avatar:           u.avatar_url ?? undefined,
  } as unknown as User;
}

function makeTokens(raw: BackendTokenResponse): AuthTokens {
  return {
    accessToken:  raw.access_token,
    refreshToken: raw.refresh_token,
    expiresAt:    Date.now() + raw.expires_in * 1_000,
  };
}

// ── State & reducer ───────────────────────────────────────────────────────────
interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

type AuthAction =
  | { type: 'AUTH_START' }
  | { type: 'AUTH_SUCCESS'; payload: { user: User; tokens: AuthTokens } }
  | { type: 'AUTH_FAILURE'; payload: string }
  | { type: 'LOGOUT' }
  | { type: 'UPDATE_USER'; payload: User }
  | { type: 'CLEAR_ERROR' };

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'AUTH_START':   return { ...state, isLoading: true, error: null };
    case 'AUTH_SUCCESS': return { ...state, isLoading: false, user: action.payload.user, tokens: action.payload.tokens, isAuthenticated: true, error: null };
    case 'AUTH_FAILURE': return { ...state, isLoading: false, error: action.payload, isAuthenticated: false };
    case 'LOGOUT':       return { user: null, tokens: null, isAuthenticated: false, isLoading: false, error: null };
    case 'UPDATE_USER':  return { ...state, user: action.payload };
    case 'CLEAR_ERROR':  return { ...state, error: null };
    default:             return state;
  }
}

// ── Context definition ────────────────────────────────────────────────────────
interface AuthContextValue extends AuthState {
  login:      (credentials: LoginCredentials) => Promise<void>;
  register:   (data: RegisterData)             => Promise<void>;
  logout:     ()                               => void;
  updateUser: (user: User)                     => void;
  clearError: ()                               => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, {
    user: null, tokens: null, isAuthenticated: false, isLoading: true, error: null,
  });

  // Restore session from localStorage on mount
  useEffect(() => {
    const storedUser  = localStorage.getItem(USER_KEY);
    const storedToken = localStorage.getItem(TOKEN_KEY);
    if (storedUser && storedToken) {
      try {
        const user: User = JSON.parse(storedUser);
        const tokens: AuthTokens = {
          accessToken:  storedToken,
          refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) ?? '',
          expiresAt:    Date.now() + 3_600_000,  // assume 1 h remaining
        };
        dispatch({ type: 'AUTH_SUCCESS', payload: { user, tokens } });
        return;
      } catch {
        // Corrupt stored data — clear and show login
        localStorage.removeItem(USER_KEY);
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
      }
    }
    dispatch({ type: 'LOGOUT' });
  }, []);

  // ── login ────────────────────────────────────────────────────────────────
  const login = useCallback(async (credentials: LoginCredentials) => {
    dispatch({ type: 'AUTH_START' });
    try {
      const { data: body } = await apiClient.post<BackendAPIResponse<BackendTokenResponse>>(
        '/auth/login',
        { email: credentials.email, password: credentials.password },
      );

      // body.data IS the TokenResponse (flat, not nested)
      const raw    = body.data;
      const tokens = makeTokens(raw);
      const user   = mapBackendUser(raw.user);

      localStorage.setItem(TOKEN_KEY,         tokens.accessToken);
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
      localStorage.setItem(USER_KEY,          JSON.stringify(user));

      dispatch({ type: 'AUTH_SUCCESS', payload: { user, tokens } });
    } catch (e: any) {
      const message = e?.response?.data?.message ?? e?.message ?? 'Login failed';
      dispatch({ type: 'AUTH_FAILURE', payload: message });
    }
  }, []);

  // ── register ─────────────────────────────────────────────────────────────
  const register = useCallback(async (data: RegisterData) => {
    dispatch({ type: 'AUTH_START' });
    try {
      // Transform frontend camelCase → backend snake_case
      const username  = data.email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_');
      const full_name = [data.firstName, data.lastName].filter(Boolean).join(' ') || username;

      const { data: body } = await apiClient.post<BackendAPIResponse<BackendTokenResponse>>(
        '/auth/register',
        {
          email:    data.email,
          username,
          full_name,
          password: data.password,
        },
      );

      const raw    = body.data;
      const tokens = makeTokens(raw);
      const user   = mapBackendUser(raw.user);

      localStorage.setItem(TOKEN_KEY,         tokens.accessToken);
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
      localStorage.setItem(USER_KEY,          JSON.stringify(user));

      dispatch({ type: 'AUTH_SUCCESS', payload: { user, tokens } });
    } catch (e: any) {
      const message = e?.response?.data?.message ?? e?.message ?? 'Registration failed';
      dispatch({ type: 'AUTH_FAILURE', payload: message });
    }
  }, []);

  // ── logout ────────────────────────────────────────────────────────────────
  const logout = useCallback(() => {
    // Fire-and-forget server-side invalidation
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (refreshToken) {
      apiClient.post('/auth/logout', null, {
        headers: { 'X-Refresh-Token': refreshToken },
      }).catch(() => null);
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    dispatch({ type: 'LOGOUT' });
  }, []);

  const updateUser = useCallback((user: User) => {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    dispatch({ type: 'UPDATE_USER', payload: user });
  }, []);

  const clearError = useCallback(() => dispatch({ type: 'CLEAR_ERROR' }), []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, updateUser, clearError }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
