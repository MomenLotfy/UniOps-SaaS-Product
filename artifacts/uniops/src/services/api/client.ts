import axios from 'axios';
import { API_BASE_URL, TOKEN_KEY, REFRESH_TOKEN_KEY } from '@/lib/constants';
import { AppError } from '@/lib/error-handler';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT access token to every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401: attempt token refresh once, then redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    const isAuthEndpoint = original?.url?.includes('/auth/');
    const publicPaths    = ['/', '/landing', '/features', '/pricing', '/contact', '/about', '/faq', '/docs', '/blog'];
    const isOnAuthPage   = window.location.pathname.startsWith('/auth/')
      || publicPaths.includes(window.location.pathname);

    if (error.response?.status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

      if (refreshToken) {
        try {
          const { data: body } = await axios.post(
            `${API_BASE_URL}/auth/refresh`,
            { refresh_token: refreshToken },
            { headers: { 'Content-Type': 'application/json' } },
          );

          // FastAPI returns: { success, data: { access_token, refresh_token, ... } }
          const newAccessToken  = body?.data?.access_token  ?? body?.access_token;
          const newRefreshToken = body?.data?.refresh_token ?? body?.refresh_token;

          if (!newAccessToken) throw new Error('No access_token in refresh response');

          localStorage.setItem(TOKEN_KEY, newAccessToken);
          if (newRefreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, newRefreshToken);

          original.headers.Authorization = `Bearer ${newAccessToken}`;
          return apiClient(original);
        } catch {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(REFRESH_TOKEN_KEY);
          localStorage.removeItem('uniops_user');
          if (!isOnAuthPage) window.location.href = '/auth/login';
        }
      } else {
        if (!isOnAuthPage) window.location.href = '/auth/login';
      }
    }

    // FastAPI error shape: { success: false, message: string, code: string }
    const errBody = error.response?.data;
    const message = errBody?.message ?? errBody?.detail ?? error.message ?? 'Unknown error';
    const code    = errBody?.code    ?? 'UNKNOWN';
    const status  = error.response?.status ?? 500;
    return Promise.reject(new AppError(message, code, status, errBody?.details));
  },
);

export default apiClient;
