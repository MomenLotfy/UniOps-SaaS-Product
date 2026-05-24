import { useState } from 'react';
import { Save, CheckCircle, AlertCircle } from 'lucide-react';
import { CompanyLogo } from './CompanyLogo';
import type { Company } from '@/types/company';

interface CompanyInfoFormProps {
  company: Company;
  onSave: (data: Partial<Company>) => Promise<void>;
}

const INDUSTRIES = ['Technology', 'Finance', 'Healthcare', 'Retail', 'Manufacturing', 'Education', 'Government', 'Media', 'Consulting', 'Other'];
const SIZES = ['1-10', '11-50', '51-200', '201-500', '501-1000', '1000+'];

export function CompanyInfoForm({ company, onSave }: CompanyInfoFormProps) {
  const [form, setForm] = useState({
    name: company.name,
    slug: company.slug,
    domain: company.domain,
    logoUrl: '',
    industry: 'Technology',
    size: '51-200',
    website: '',
    country: 'US',
    description: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;
  const labelCls = 'block text-xs font-medium mb-1.5 text-muted-foreground';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setStatus('idle');
    try {
      await onSave({ name: form.name, slug: form.slug, domain: form.domain } as Partial<Company>);
      setStatus('success');
      setTimeout(() => setStatus('idle'), 3000);
    } catch {
      setStatus('error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <CompanyLogo name={company.name} logoUrl={form.logoUrl || undefined} onUpload={(url) => setForm((p) => ({ ...p, logoUrl: url }))} editable size="lg" />

      {status === 'success' && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400"
          style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
          <CheckCircle className="w-4 h-4 flex-shrink-0" /> Company information saved
        </div>
      )}
      {status === 'error' && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
          style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" /> Failed to save changes
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Company name</label>
          <input type="text" required value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} className={inputCls} style={inputStyle} />
        </div>
        <div>
          <label className={labelCls}>Workspace slug</label>
          <input type="text" required value={form.slug} onChange={(e) => setForm((p) => ({ ...p, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') }))} className={inputCls} style={inputStyle} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Domain</label>
          <input type="text" placeholder="company.com" value={form.domain} onChange={(e) => setForm((p) => ({ ...p, domain: e.target.value }))} className={inputCls} style={inputStyle} />
        </div>
        <div>
          <label className={labelCls}>Website</label>
          <input type="url" placeholder="https://company.com" value={form.website} onChange={(e) => setForm((p) => ({ ...p, website: e.target.value }))} className={inputCls} style={inputStyle} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Industry</label>
          <select value={form.industry} onChange={(e) => setForm((p) => ({ ...p, industry: e.target.value }))} className={inputCls} style={inputStyle}>
            {INDUSTRIES.map((i) => <option key={i} value={i}>{i}</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Company size</label>
          <select value={form.size} onChange={(e) => setForm((p) => ({ ...p, size: e.target.value }))} className={inputCls} style={inputStyle}>
            {SIZES.map((s) => <option key={s} value={s}>{s} employees</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className={labelCls}>Description</label>
        <textarea rows={3} placeholder="Brief description of your company..." value={form.description}
          onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
          className={inputCls + ' resize-none'} style={inputStyle} />
      </div>

      <div className="flex justify-end">
        <button type="submit" disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-semibold text-sm disabled:opacity-60"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Save className="w-4 h-4" />}
          {isLoading ? 'Saving...' : 'Save changes'}
        </button>
      </div>
    </form>
  );
}
