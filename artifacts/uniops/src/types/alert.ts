export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type AlertStatus = 'firing' | 'resolved' | 'acknowledged' | 'silenced';
export type AlertChannel = 'slack' | 'teams' | 'email' | 'pagerduty' | 'webhook';

export interface Alert {
  id: string;
  title: string;
  description: string;
  severity: AlertSeverity;
  status: AlertStatus;
  source: string;
  service: string;
  labels: Record<string, string>;
  startedAt: string;
  resolvedAt?: string;
  acknowledgedBy?: string;
  acknowledgedAt?: string;
  runbook?: string;
  channels: AlertChannel[];
}

export interface NotificationPreference {
  channel: AlertChannel;
  enabled: boolean;
  severities: AlertSeverity[];
  quietHours?: { start: string; end: string };
}

export interface AlertRule {
  id: string;
  name: string;
  condition: string;
  threshold: number;
  severity: AlertSeverity;
  enabled: boolean;
  channels: AlertChannel[];
}
