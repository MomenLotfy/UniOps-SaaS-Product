import { motion } from 'framer-motion';
import { Settings as SettingsIcon, Shield, Globe, Bell } from 'lucide-react';
import { CompanyInfoForm } from '@/components/company/CompanyInfoForm';
import { DomainVerification } from '@/components/company/DomainVerification';
import { useCompany } from '@/contexts/CompanyContext';
import { useState } from 'react';
import { clsx } from 'clsx';

const TABS = [
  { id: 'general', label: 'General', icon: SettingsIcon },
  { id: 'domain', label: 'Domain', icon: Globe },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'notifications', label: 'Notifications', icon: Bell },
];

export default function CompanySettings() {
  const { company, updateCompany } = useCompany();
  const [tab, setTab] = useState('general');

  if (!company) return null;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header mb-5">
        <div>
          <h1 className="page-title">Company Settings</h1>
          <p className="page-subtitle">Manage your organization configuration</p>
        </div>
      </div>

      <div className="flex gap-1 border-b mb-6" style={{ borderColor: 'hsl(230 15% 14%)' }}>
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={clsx('flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
              tab === t.id ? 'border-blue-500 text-blue-400' : 'border-transparent text-muted-foreground hover:text-foreground')}>
            <t.icon className="w-4 h-4" />{t.label}
          </button>
        ))}
      </div>

      {tab === 'general' && (
        <div className="card-base max-w-2xl">
          <CompanyInfoForm company={company} onSave={async (data) => updateCompany({ ...company, ...data })} />
        </div>
      )}

      {tab === 'domain' && (
        <div className="card-base max-w-xl">
          <h2 className="text-sm font-semibold text-foreground mb-4">Domain Verification</h2>
          <DomainVerification domain={company.domain} isVerified={company.domainVerified}
            onVerify={async () => { await new Promise((r) => setTimeout(r, 1500)); throw new Error('DNS record not found'); }} />
        </div>
      )}

      {tab === 'security' && (
        <div className="card-base max-w-xl space-y-5">
          <h2 className="text-sm font-semibold text-foreground">Security Policies</h2>
          {[
            { label: 'Enforce SSO', desc: 'Require all members to sign in via SSO', key: 'enforceSSO' },
            { label: 'Enforce 2FA', desc: 'Require all members to enable two-factor authentication', key: 'enforce2FA' },
          ].map((item) => (
            <div key={item.key} className="flex items-center justify-between p-4 rounded-xl border"
              style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
              <div>
                <p className="text-sm font-medium text-foreground">{item.label}</p>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
              <button
                className={clsx('w-11 h-6 rounded-full transition-colors relative flex-shrink-0',
                  company.settings[item.key as keyof typeof company.settings] ? 'bg-blue-500' : 'bg-muted/40')}>
                <span className={clsx('absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all',
                  company.settings[item.key as keyof typeof company.settings] ? 'left-5.5' : 'left-0.5')} />
              </button>
            </div>
          ))}
        </div>
      )}

      {tab === 'notifications' && (
        <div className="card-base max-w-xl">
          <p className="text-sm text-muted-foreground">Company-wide notification settings will be available here.</p>
        </div>
      )}
    </motion.div>
  );
}
