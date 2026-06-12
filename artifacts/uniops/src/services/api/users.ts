import { apiClient } from './client';
import type { User } from '@/types/user';

interface ListParams {
  search?: string;
  role?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

// FastAPI router: /users/*
// Response shape: { success, data: { data: User[], total, page, page_size, pages }, message, code }
function unwrapPaginated<T>(body: any): T[] {
  if (Array.isArray(body)) return body;
  if (Array.isArray(body?.data)) return body.data;          // already-unwrapped list
  if (Array.isArray(body?.data?.data)) return body.data.data; // nested APIResponse → PaginatedResponse
  return [];
}

export const usersApi = {
  list: (params?: ListParams) =>
    apiClient.get('/users', { params }).then((r) => unwrapPaginated<User>(r.data)),

  get: (id: string) =>
    apiClient.get<User>(`/users/${id}`).then((r) => r.data),

  update: (id: string, data: Partial<User>) =>
    apiClient.put<User>(`/users/${id}`, data).then((r) => r.data),

  // FastAPI uses PUT /users/me
  updateMe: (data: Partial<User>) =>
    apiClient.put<User>('/users/me', data).then((r) => r.data),

  invite: (email: string, role: string) =>
    apiClient.post('/users/invite', { email, role }).then((r) => r.data),

  // FastAPI uses DELETE /{user_id} for deactivation
  deactivate: (id: string) =>
    apiClient.delete(`/users/${id}`).then((r) => r.data),

  getSessions: () =>
    apiClient.get<any>('/users/me/sessions')
      .catch(() => ({ data: [] }))
      .then((r: any) => Array.isArray(r.data) ? r.data : r.data?.data ?? []),

  revokeSession: (id: string) =>
    apiClient.delete(`/users/me/sessions/${id}`).catch(() => null),

  changePassword: (currentPassword: string, newPassword: string) =>
    apiClient.post('/users/me/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }).then((r) => r.data),
};
