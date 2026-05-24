import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Mail, CheckCircle } from 'lucide-react';

export default function Contact() {
  const [form, setForm] = useState({ name: '', email: '', company: '', message: '' });
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm text-white border outline-none focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)' } as React.CSSProperties;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 1000));
    setSent(true);
    setIsLoading(false);
  };

  return (
    <div style={{ background: 'hsl(230 20% 4%)', color: 'hsl(213 31% 91%)', minHeight: '100vh', padding: '4rem 2rem' }}>
      <nav className="flex items-center justify-between max-w-4xl mx-auto mb-16">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, hsl(220 90% 55%), hsl(260 70% 60%))' }}>
            <Activity className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold">UniOps</span>
        </Link>
      </nav>

      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Contact Sales</h1>
        <p className="mb-8" style={{ color: 'hsl(215 16% 57%)' }}>Tell us about your team and we'll get back to you within 24 hours.</p>

        {sent ? (
          <div className="text-center py-16 space-y-4">
            <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto" style={{ background: 'hsl(160 84% 39% / 0.15)' }}>
              <CheckCircle className="w-8 h-8 text-green-400" />
            </div>
            <p className="font-semibold text-white text-lg">Message sent!</p>
            <p style={{ color: 'hsl(215 16% 57%)' }}>Our team will get back to you within 24 hours.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Full name</label>
                <input required value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} placeholder="Alex Johnson" className={inputCls} style={inputStyle} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Work email</label>
                <input type="email" required value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} placeholder="alex@company.com" className={inputCls} style={inputStyle} />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Company</label>
              <input value={form.company} onChange={(e) => setForm((p) => ({ ...p, company: e.target.value }))} placeholder="Acme Corporation" className={inputCls} style={inputStyle} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'hsl(215 16% 57%)' }}>Message</label>
              <textarea required rows={5} value={form.message} onChange={(e) => setForm((p) => ({ ...p, message: e.target.value }))} placeholder="Tell us about your team size, current tools, and what you're looking to achieve..." className={inputCls} style={inputStyle} />
            </div>
            <button type="submit" disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-lg font-semibold disabled:opacity-60"
              style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
              {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Mail className="w-4 h-4" />}
              {isLoading ? 'Sending...' : 'Send message'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
