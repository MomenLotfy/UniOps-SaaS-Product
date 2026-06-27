import apiClient from './client';
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

export interface ProviderCapability {
  provider_id: string;
  capability_type: string;
  is_supported: boolean;
  confidence_level: number;
}

export interface ProviderDetails {
  provider_id: string;
  name: string;
  description: string | null;
  version: string;
  provider_type: string;
  is_active: boolean;
  capabilities: ProviderCapability[];
  config: any;
  health: ProviderHealth | null;
}

export const intelligenceApi = {
  async getHealth(): Promise<ProviderHealth[]> {
    const res = await apiClient.get('/intelligence/health');
    return res.data;
  },

  async getStatus(): Promise<IntelligenceStatus[]> {
    const res = await apiClient.get('/intelligence/status');
    return res.data;
  },

  async getProviders(): Promise<ProviderDetails[]> {
    const res = await apiClient.get('/intelligence/providers');
    return res.data;
  },

  async lookup(id: string): Promise<any> {
    const res = await apiClient.get(`/intelligence/lookup/${id}`);
    return res.data;
  }
};
