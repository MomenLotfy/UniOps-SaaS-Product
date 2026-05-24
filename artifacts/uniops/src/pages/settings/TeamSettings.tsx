import { useState } from 'react';
import { Users, Mail, Shield, Link2, Bell, Plus, Trash2 } from 'lucide-react';
import { clsx } from 'clsx';

const DOMAIN_ALLOWLIST = ['uniops.dev', 'company.com'];
const DEFAULT_ROLES = ['viewer', 'devops', 'security', 'finops', 'admin'];

export default function TeamSettings() {
  const [joinByLink, setJoinByLink] = useState(true);
  const [requireApproval, setRequireApproval] = useState(true);
  const [defaultRole, setDefaultRole] = useState('viewer');
  const [domains, setDomains] = useState(DOMAIN_ALLOWLIST);
  const [newDomain, setNewDomain] = useState('');
  const [notifyOnJoin, setNotifyOnJoin] = useState(true);
  const [notifyOnLeave, setNotifyOnLeave] = useState(false);

  const addDomain = () => {
    if (newDomain && !domains.includes(newDomain)) { setDomains((d) => [...d, newDomain]); setNewDomain(''); }
  };
  const removeDomain = (d: string) => setDomains((ds) => ds.filter((x) => x !== d));

  const ToggleSwitch = ({ enabled, onChange }: { enabled: boolean; onChange: () => void }) => (
    <button onClick={onChange} className={clsx('w-10 h-6 rounded-full relative transition-colors flex-shrink-0', enabled ? 'bg-primary' : 'bg-border')}>
      <div className={clsx('absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all', enabled ? 'left-[calc(100%-1.375rem)]' : 'left-0.5')} />
    </button>
  );

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="page-title">Team Settings</h1>
        <p className="page-subtitle">Configure how members join, their default permissions, and team notifications.</p>
      </div>

      {/* Membership */}
      <div className="card-base rounded-xl p-6 border border-border space-y-5">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2"><Users className="w-4 h-4" />Membership</h2>

        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-foreground">Allow Join via Link</div>
            <div className="text-xs text-muted-foreground mt-0.5">Anyone with an invite link can request to join.</div>
          </div>
          <ToggleSwitch enabled={joinByLink} onChange={() => setJoinByLink((v) => !v)} />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-foreground">Require Admin Approval</div>
            <div className="text-xs text-muted-foreground mt-0.5">New members must be approved by an admin before gaining access.</div>
          </div>
          <ToggleSwitch enabled={requireApproval} onChange={() => setRequireApproval((v) => !v)} />
        </div>

        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1.5 flex items-center gap-1"><Shield className="w-3.5 h-3.5" />Default Role for New Members</label>
          <select value={defaultRole} onChange={(e) => setDefaultRole(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50">
            {DEFAULT_ROLES.map((r) => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
          </select>
        </div>
      </div>

      {/* Domain allowlist */}
      <div className="card-base rounded-xl p-6 border border-border space-y-5">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2"><Mail className="w-4 h-4" />Email Domain Allowlist</h2>
        <p className="text-xs text-muted-foreground">Only users with these email domains can join. Leave empty to allow all domains.</p>

        <div className="flex flex-wrap gap-2">
          {domains.map((d) => (
            <div key={d} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border text-xs text-foreground">
              <Link2 className="w-3 h-3 text-muted-foreground" />
              {d}
              <button onClick={() => removeDomain(d)} className="ml-1 text-muted-foreground hover:text-red-400 transition-colors"><Trash2 className="w-3 h-3" /></button>
            </div>
          ))}
        </div>

        <div className="flex gap-2">
          <input value={newDomain} onChange={(e) => setNewDomain(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addDomain()}
            placeholder="example.com"
            className="flex-1 px-3 py-2 text-sm rounded-lg border border-border bg-background/50 text-foreground focus:outline-none focus:border-primary/50" />
          <button onClick={addDomain} className="action-btn action-btn-primary"><Plus className="w-4 h-4" /> Add</button>
        </div>
      </div>

      {/* Notifications */}
      <div className="card-base rounded-xl p-6 border border-border space-y-5">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2"><Bell className="w-4 h-4" />Team Notifications</h2>

        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-foreground">Notify Admins on Member Join</div>
            <div className="text-xs text-muted-foreground mt-0.5">Send an email when a new member joins the organization.</div>
          </div>
          <ToggleSwitch enabled={notifyOnJoin} onChange={() => setNotifyOnJoin((v) => !v)} />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-foreground">Notify Admins on Member Leave</div>
            <div className="text-xs text-muted-foreground mt-0.5">Send an email when a member removes themselves.</div>
          </div>
          <ToggleSwitch enabled={notifyOnLeave} onChange={() => setNotifyOnLeave((v) => !v)} />
        </div>
      </div>

      <div className="flex justify-end">
        <button className="action-btn action-btn-primary">Save Team Settings</button>
      </div>
    </div>
  );
}
