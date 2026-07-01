import apiClient from './client';

// ─── Provider Types ───────────────────────────────────────────────────────────

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

// ─── Summary ──────────────────────────────────────────────────────────────────

export interface IntelligenceSummary {
  total_records: number;
  active_providers: number;
  healthy_providers: number;
  critical_advisories: number;
  new_cves_today: number;
  kev_cves: number;
  high_epss: number;
  active_campaigns: number;
  known_threat_actors: number;
  malware_families: number;
  ioc_count: number;
  high_confidence: number;
  last_feed_update: string | null;
}

// ─── Feeds ────────────────────────────────────────────────────────────────────

export interface IntelligenceFeed {
  provider_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  last_sync: string | null;
  records: number;
  errors: number;
  latency_ms: number | null;
  status: string;
  last_error: string | null;
  sync_status: string | null;
}

// ─── Records ──────────────────────────────────────────────────────────────────

export interface IntelligenceRecord {
  id: string;
  title: string;
  type: string;
  severity: string;
  cvss_score: number | null;
  epss_score: number;
  is_kev: boolean;
  threat_actor: string | null;
  malware: string | null;
  mitre_technique: string | null;
  affected_products: string[];
  published_at: string | null;
  updated_at: string | null;
  confidence: string;
  sources: string[];
  description: string | null;
  references: string[];
  cwe_ids: string[];
  capec_ids: string[];
}

export interface RecordPage {
  data: IntelligenceRecord[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ─── IOCs ─────────────────────────────────────────────────────────────────────

export interface IOC {
  id: string;
  type: string;
  value: string;
  confidence: string;
  first_seen: string | null;
  last_seen: string | null;
  source: string | string[];
  observed_internally: boolean;
  related_intel_id: string;
}

export interface IOCPage {
  data: IOC[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ─── Threat Actors ────────────────────────────────────────────────────────────

export interface ThreatActor {
  name: string;
  aliases: string[];
  country: string | null;
  motivation: string | null;
  known_campaigns: string[];
  known_malware: string[];
  mitre_techniques: string[];
  target_industries: string[];
  target_countries: string[];
  associated_cves: string[];
  associated_iocs: string[];
}

// ─── Malware ──────────────────────────────────────────────────────────────────

export interface MalwareFamily {
  family: string;
  category: string | null;
  severity: string;
  associated_threat_actor: string | null;
  delivery_method: string | null;
  persistence: string | null;
  mitre_mapping: string | null;
  related_cves: string[];
}

// ─── Techniques ───────────────────────────────────────────────────────────────

export interface AttackTechnique {
  technique: string;
  tactic: string | null;
  sub_technique: string | null;
  coverage: string;
  affected_assets: string[];
  observed_events: number;
  related_intel_ids: string[];
}

// ─── API Client ───────────────────────────────────────────────────────────────

export const intelligenceApi = {
  async getSummary(): Promise<IntelligenceSummary> {
    const res = await apiClient.get('/intelligence/summary');
    return res.data;
  },

  async getFeeds(): Promise<IntelligenceFeed[]> {
    const res = await apiClient.get('/intelligence/feeds');
    return res.data;
  },

  async triggerSync(providerId: string): Promise<{ success: boolean; message: string }> {
    const res = await apiClient.post(`/intelligence/feeds/${providerId}/sync`, {});
    return res.data;
  },

  async getRecords(params: {
    page?: number;
    page_size?: number;
    severity?: string;
    search?: string;
    kev_only?: boolean;
    high_epss?: boolean;
    record_type?: string;
  }): Promise<RecordPage> {
    const res = await apiClient.get('/intelligence/records', { params });
    return res.data;
  },

  async getIOCs(params: {
    page?: number;
    page_size?: number;
    ioc_type?: string;
  }): Promise<IOCPage> {
    const res = await apiClient.get('/intelligence/iocs', { params });
    return res.data;
  },

  async getThreatActors(): Promise<ThreatActor[]> {
    const res = await apiClient.get('/intelligence/threat-actors');
    return res.data;
  },

  async getMalwareFamilies(): Promise<MalwareFamily[]> {
    const res = await apiClient.get('/intelligence/malware');
    return res.data;
  },

  async getAttackTechniques(): Promise<AttackTechnique[]> {
    const res = await apiClient.get('/intelligence/techniques');
    return res.data;
  },

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
  },

  async getCanonicalCVE(cveId: string): Promise<any> {
    const res = await apiClient.get(`/intelligence/canonical/cve/${cveId}`);
    return res.data;
  },
};
