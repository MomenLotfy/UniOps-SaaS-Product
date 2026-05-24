import { useState } from 'react';
import { Shield, AlertTriangle, Check, X, Info, ChevronRight, Lock, Clock, Key } from 'lucide-react';
import { clsx } from 'clsx';

interface Policy {
  id: string;
  category: string;
  name: string;
  description: string;
  enabled: boolean;
  level: 'critical' | 'high' | 'medium' | 'low';
  configurable: boolean;
  value?: string | number | boolean;
}

const POLICIES: Policy[] = [
  { id: 'mfa-required', category: 'Authentication', name: 'Require MFA', description: 'All users must enable multi-factor authentication.', enabled: true, level: 'critical', configurable: false },
  { id: 'session-timeout', category: 'Authentication', name: 'Session Timeout', description: 'Automatically log out inactive sessions after a set period.', enabled: true, level: 'high', configurable: true, value: 60 },
  { id: 'max-login-attempts', category: 'Authentication', name: 'Max Login Attempts', description: 'Lock accounts after N failed login attempts.', enabled: true, level: 'high', configurable: true, value: 5 },
  { id: 'sso-required', category: 'Authentication', name: 'Force SSO', description: 'Disable password login; require SSO for all users.', enabled: false, level: 'medium', configurable: false },
  { id: 'pwd-complexity', category: 'Passwords', name: 'Password Complexity', description: 'Enforce minimum length, upper, lower, digit, and symbol requirements.', enabled: true, level: 'high', configurable: false },
  { id: 'pwd-expiry', category: 'Passwords', name: 'Password Expiry', description: 'Require password rotation every N days.', enabled: true, level: 'medium', configurable: true, value: 90 },
  { id: 'pwd-history', category: 'Passwords', name: 'Password History', description: 'Prevent reuse of last N passwords.', enabled: true, level: 'medium', configurable: true, value: 5 },
  { id: 'api-key-expiry', category: 'API Keys', name: 'API Key Expiry', description: 'Require API keys to expire after N days.', enabled: true, level: 'medium', configurable: true, value: 30 },
  { id: 'api-key-scope', category: 'API Keys', name: 'Enforce API Key Scopes', description: 'Prevent creation of keys with full write access.', enabled: false, level: 'low', configurable: false },
  { id: 'audit-retention', category: 'Audit & Logging', name: 'Audit Log Retention', description: 'Retain audit logs for N days.', enabled: true, level: 'medium', configurable: true, value: 365 },
  { id: 'sensitive-masking', category: 'Audit & Logging', name: 'Mask Sensitive Data', description: 'Redact secrets and credentials from log output.', enabled: true, level: 'high', configurable: false },
  { id: 'ip-allowlist', category: 'Network', name: 'IP Allowlisting', description: 'Restrict platform access to specific IP ranges.', enabled: false, level: 'high', configurable: false },
  { id: 'cors-strict', category: 'Network', name: 'Strict CORS', description: 'Only allow API calls from approved origins.', enabled: true, level: 'critical', configurable: false },
];

const levelColors: Record<string, string> = {
  critical: 'text-red-400 bg-red-400/10 border-red-400/20',
  high:     'text-orange-400 bg-orange-400/10 border-orange-400/20',
  medium:   'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  low:      'text-blue-400 bg-blue-400/10 border-blue-400/20',
};

const categories = [...new Set(POLICIES.map((p) => p.category))];

export default function SecurityPolicies() {
  const [policies, setPolicies] = useState(POLICIES);
  const [filter, setFilter] = useState<string | null>(null);

  const toggle = (id: string) => setPolicies((prev) => prev.map((p) => p.id === id ? { ...p, enabled: !p.enabled } : p));

  const visible = filter ? policies.filter((p) => p.category === filter) : policies;
  const enabledCount = policies.filter((p) => p.enabled).length;
  const criticalDisabled = policies.filter((p) => p.level === 'critical' && !p.enabled).length;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Security Policies</h1>
          <p className="page-subtitle">Configure organization-wide security controls and compliance requirements.</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Policies', value: policies.length, icon: Shield, color: 'hsl(220 90% 60%)' },
          { label: 'Enabled', value: enabledCount, icon: Check, color: 'hsl(140 60% 45%)' },
          { label: 'Disabled', value: policies.length - enabledCount, icon: X, color: 'hsl(215 16% 50%)' },
          { label: 'Critical Disabled', value: criticalDisabled, icon: AlertTriangle, color: criticalDisabled > 0 ? 'hsl(0 80% 60%)' : 'hsl(140 60% 45%)' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card-base rounded-xl p-4 border border-border">
            <div className="flex items-center gap-2 mb-2">
              <Icon className="w-4 h-4" style={{ color }} />
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{value}</div>
          </div>
        ))}
      </div>

      {criticalDisabled > 0 && (
        <div className="flex items-center gap-3 p-3 rounded-xl border border-red-500/30 bg-red-500/10">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <p className="text-xs text-red-300">{criticalDisabled} critical security {criticalDisabled === 1 ? 'policy is' : 'policies are'} currently disabled. Review and enable them to maintain compliance.</p>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setFilter(null)} className={clsx('text-xs px-3 py-1.5 rounded-full border transition-colors', !filter ? 'border-primary/50 bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:border-primary/30')}>All</button>
        {categories.map((cat) => (
          <button key={cat} onClick={() => setFilter(cat)} className={clsx('text-xs px-3 py-1.5 rounded-full border transition-colors', filter === cat ? 'border-primary/50 bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:border-primary/30')}>
            {cat}
          </button>
        ))}
      </div>

      {/* Policy list */}
      <div className="space-y-2">
        {categories.filter((cat) => !filter || filter === cat).map((cat) => {
          const catPolicies = visible.filter((p) => p.category === cat);
          if (catPolicies.length === 0) return null;
          return (
            <div key={cat}>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-1">{cat}</div>
              <div className="space-y-2 mb-4">
                {catPolicies.map((policy) => (
                  <div key={policy.id} className="card-base rounded-xl p-4 border border-border flex items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-foreground">{policy.name}</span>
                        <span className={clsx('text-xs px-2 py-0.5 rounded-full border capitalize', levelColors[policy.level])}>{policy.level}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">{policy.description}</p>
                      {policy.configurable && policy.enabled && (
                        <div className="mt-2 flex items-center gap-2">
                          <input type="number" defaultValue={policy.value as number}
                            className="w-20 px-2 py-1 text-xs rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50" />
                          <span className="text-xs text-muted-foreground">{policy.id.includes('day') || policy.id.includes('timeout') || policy.id.includes('expiry') || policy.id.includes('retention') ? 'days' : ''}</span>
                        </div>
                      )}
                    </div>
                    <button onClick={() => toggle(policy.id)}
                      className={clsx('w-10 h-6 rounded-full relative transition-colors flex-shrink-0 mt-0.5', policy.enabled ? 'bg-primary' : 'bg-border')}>
                      <div className={clsx('absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all', policy.enabled ? 'left-[calc(100%-1.375rem)]' : 'left-0.5')} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-end">
        <button className="action-btn action-btn-primary">Save Policy Configuration</button>
      </div>
    </div>
  );
}
