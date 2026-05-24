import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { Company, UsageStats } from '@/types/company';
import { COMPANY_KEY } from '@/lib/constants';
import apiClient from '@/services/api/client';
import { useAuth } from '@/contexts/AuthContext';

interface CompanyContextValue {
  company: Company | null;
  usage: UsageStats | null;
  isLoading: boolean;
  updateCompany: (company: Company) => void;
  refetch: () => void;
}

const DEFAULT_COMPANY: Company = {
  id: 'tenant-001',
  name: 'My Company',
  domain: '',
  plan: 'professional',
  status: 'active',
  memberCount: 1,
  maxMembers: 25,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
} as unknown as Company;

const DEFAULT_USAGE: UsageStats = {
  users:        { used: 1,  limit: 25     },
  integrations: { used: 0,  limit: 15     },
  apiCalls:     { used: 0,  limit: 100000 },
} as unknown as UsageStats;

const CompanyContext = createContext<CompanyContextValue | null>(null);

export function CompanyProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [company, setCompany] = useState<Company | null>(null);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    // Don't fire API calls while auth is still resolving or user is not logged in
    if (authLoading || !isAuthenticated) {
      setIsLoading(false);
      return;
    }

    try {
      const [companyRes, usageRes] = await Promise.all([
        apiClient.get<any>('/companies').catch(() => null),
        apiClient.get<any>('/companies/stats').catch(() => null),
      ]);
      const c = companyRes?.data?.data ?? companyRes?.data ?? null;
      const u = usageRes?.data?.data ?? usageRes?.data ?? null;

      if (c && c.id) {
        setCompany(c as Company);
        localStorage.setItem(COMPANY_KEY, JSON.stringify(c));
      } else {
        const cached = localStorage.getItem(COMPANY_KEY);
        setCompany(cached ? JSON.parse(cached) : DEFAULT_COMPANY);
      }
      setUsage(u ?? DEFAULT_USAGE);
    } catch {
      const cached = localStorage.getItem(COMPANY_KEY);
      setCompany(cached ? JSON.parse(cached) : DEFAULT_COMPANY);
      setUsage(DEFAULT_USAGE);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, authLoading]);

  useEffect(() => { load(); }, [load]);

  const updateCompany = useCallback((c: Company) => {
    localStorage.setItem(COMPANY_KEY, JSON.stringify(c));
    setCompany(c);
  }, []);

  return (
    <CompanyContext.Provider value={{ company, usage, isLoading, updateCompany, refetch: load }}>
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany(): CompanyContextValue {
  const ctx = useContext(CompanyContext);
  if (!ctx) throw new Error('useCompany must be used within CompanyProvider');
  return ctx;
}
