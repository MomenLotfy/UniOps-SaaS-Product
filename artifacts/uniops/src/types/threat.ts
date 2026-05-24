export type ThreatSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export type ThreatStatus = 'active' | 'investigating' | 'mitigated' | 'resolved' | 'false_positive';

export type ThreatCategory =
  | 'malware'
  | 'phishing'
  | 'brute_force'
  | 'data_exfiltration'
  | 'privilege_escalation'
  | 'lateral_movement'
  | 'ransomware'
  | 'insider_threat'
  | 'ddos'
  | 'supply_chain';

export interface MitreAttack {
  tacticId: string;
  tacticName: string;
  techniqueId: string;
  techniqueName: string;
  subtechniqueId?: string;
}

export interface ThreatIndicator {
  type: 'ip' | 'domain' | 'hash' | 'url' | 'email';
  value: string;
  confidence: number;
}

export interface Threat {
  id: string;
  title: string;
  description: string;
  severity: ThreatSeverity;
  status: ThreatStatus;
  category: ThreatCategory;
  mitre?: MitreAttack;
  indicators: ThreatIndicator[];
  affectedAssets: string[];
  sourceIP?: string;
  destinationIP?: string;
  country?: string;
  assignedTo?: string;
  detectedAt: string;
  updatedAt: string;
  resolvedAt?: string;
  companyId: string;
  riskScore: number;
}

export interface ThreatStats {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  active: number;
  resolved: number;
  mttr: number;
}
