import { api } from './client';
import { ProviderHealthSchema } from '../../types/intelligence'; // Need to define this type first

export interface IntelligenceStatus {
  provider_id: string;
  name: string;
  version: string;
  is_active: boolean;
}

export interface ProviderHealth {
  provider_id: string;
  name: string;
  status: string;
  latency_ms: number | null;
  last_check_at: string;
}

export const intelligenceApi = {
  async getHealth(): Promise<ProviderHealth[]> {
    const res = await api.get('/intelligence/health');
    return res.data;
  },

  async getStatus(): Promise<IntelligenceStatus[]> {
    const res = await api.get('/intelligence/status');
    return res.data;
  },

  async lookup(id: string): Promise<any> {
    const res = await api.get(`/intelligence/lookup/${id}`);
    return res.data;
  }
};
