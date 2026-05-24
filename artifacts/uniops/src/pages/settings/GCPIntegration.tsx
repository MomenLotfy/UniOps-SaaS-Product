import { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle, AlertCircle, Upload, FileJson } from 'lucide-react';
import { integrationsApi } from '@/services/api/integrations';

export default function GCPIntegration() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ projectId: '', serviceAccountKey: '' });
  const [fileName, setFileName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [error, setError] = useState('');

  const inputCls = 'w-full px-3 py-2.5 rounded-lg text-sm border outline-none transition-all focus:ring-2 focus:ring-blue-500/50';
  const inputStyle = { background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' } as React.CSSProperties;
  const labelCls = 'block text-xs font-medium mb-1.5 text-muted-foreground';

  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      try {
        const json = JSON.parse(text);
        setForm((p) => ({ ...p, serviceAccountKey: text, projectId: json.project_id ?? p.projectId }));
        setFileName(file.name);
      } catch {
        setError('Invalid JSON file');
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setStatus('idle');
    try {
      await integrationsApi.connectGCP({ projectId: form.projectId, serviceAccountKey: form.serviceAccountKey });
      setStatus('success');
      setTimeout(() => navigate(-1), 2000);
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="max-w-xl space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="action-btn"><ArrowLeft className="w-4 h-4" /> Back</button>
      </div>
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl" style={{ background: 'hsl(230 15% 12%)', border: '1px solid hsl(230 15% 16%)' }}>🔵</div>
        <div>
          <h1 className="text-xl font-bold text-foreground">Google Cloud Integration</h1>
          <p className="text-sm text-muted-foreground">Connect GCP for cost monitoring and resource visibility</p>
        </div>
      </div>
      <form onSubmit={handleSubmit} className="card-base space-y-4">
        {status === 'success' && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400" style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
            <CheckCircle className="w-4 h-4 flex-shrink-0" /> GCP connected successfully!
          </div>
        )}
        {status === 'error' && (
          <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400" style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
            <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
          </div>
        )}
        <div>
          <label className={labelCls}>GCP Project ID</label>
          <input type="text" required placeholder="my-project-id" value={form.projectId}
            onChange={(e) => setForm((p) => ({ ...p, projectId: e.target.value }))} className={inputCls} style={inputStyle} />
        </div>
        <div>
          <label className={labelCls}>Service Account Key (JSON)</label>
          {form.serviceAccountKey ? (
            <div className="flex items-center gap-3 p-3 rounded-lg border" style={{ background: 'hsl(230 18% 11%)', borderColor: 'hsl(230 15% 14%)' }}>
              <FileJson className="w-5 h-5 text-blue-400" />
              <span className="text-sm text-foreground flex-1">{fileName}</span>
              <button type="button" onClick={() => { setForm((p) => ({ ...p, serviceAccountKey: '' })); setFileName(''); }}
                className="text-xs text-muted-foreground hover:text-red-400">Remove</button>
            </div>
          ) : (
            <label className="flex flex-col items-center gap-2 p-6 rounded-lg border-2 border-dashed cursor-pointer hover:border-blue-500/50 transition-colors"
              style={{ borderColor: 'hsl(230 15% 18%)' }}>
              <Upload className="w-6 h-6 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Upload service-account.json</p>
              <input type="file" accept=".json" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileUpload(f); }} />
            </label>
          )}
          <p className="text-xs text-muted-foreground mt-1">Required roles: <code className="text-blue-400">Viewer</code>, <code className="text-blue-400">BigQuery Data Viewer</code></p>
        </div>
        <button type="submit" disabled={isLoading || !form.serviceAccountKey || !form.projectId}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm text-white disabled:opacity-60"
          style={{ background: 'hsl(220 90% 60%)' }}>
          {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : null}
          {isLoading ? 'Connecting...' : 'Connect Google Cloud'}
        </button>
      </form>
    </motion.div>
  );
}
