import { apiClient } from './client';
import type { Company, CompanySettings, UsageStats } from '@/types/company';

// FastAPI router: /companies (tenant-scoped — no :id in path, tenant resolved from JWT)
export const companiesApi = {
  // GET /companies — returns current tenant
  get: (_id?: string) =>
    apiClient.get<Company>('/companies').then((r) => r.data),

  // PUT /companies — update current tenant
  update: (_id: string, data: Partial<CompanySettings>) =>
    apiClient.put<Company>('/companies', data).then((r) => r.data),

  // GET /companies/stats — usage/stats for current tenant
  getUsage: (_id?: string) =>
    apiClient.get<UsageStats>('/companies/stats').then((r) => r.data),

  // Logo upload — not in FastAPI yet, graceful no-op
  uploadLogo: (_id: string, file: File): Promise<{ logoUrl: string }> =>
    Promise.reject(new Error('Logo upload not yet available')),

  // Domain verification
  verifyDomain: (_id: string, domain: string) =>
    apiClient.post<{ verified: boolean; token: string }>(
      '/companies/domain/verify/initiate',
      { domain },
    ).then((r) => r.data),

  confirmDomainVerification: () =>
    apiClient.post('/companies/domain/verify/confirm').then((r) => r.data),

  // Member management not in FastAPI companies router — use users API
  inviteMember: (_id: string, payload: { email: string; role: string; teamId?: string }) =>
    apiClient.post('/users/invite', { email: payload.email, role: payload.role }).then((r) => r.data),

  getMembers: (_id?: string) =>
    apiClient.get('/users').then((r) => r.data),

  removeMember: (_companyId: string, userId: string) =>
    apiClient.delete(`/users/${userId}`),
};
