import { useRef, useState } from 'react';
import { Upload, FileCode2, CheckCircle, AlertCircle, X, Server } from 'lucide-react';
import { clsx } from 'clsx';

interface KubeconfigUploaderProps {
  onUpload: (kubeconfig: string, clusterName: string) => Promise<void>;
}

export function KubeconfigUploader({ onUpload }: KubeconfigUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [content, setContent] = useState('');
  const [clusterName, setClusterName] = useState('');
  const [fileName, setFileName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const processFile = (file: File) => {
    if (!file.name.includes('kubeconfig') && !file.name.endsWith('.yaml') && !file.name.endsWith('.yml') && !file.name.endsWith('.conf')) {
      setStatus('error');
      setErrorMsg('Please upload a valid kubeconfig file (.yaml, .yml, .conf)');
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      setContent(text);
      setFileName(file.name);
      const match = text.match(/name:\s*([^\n]+)/);
      if (match && !clusterName) setClusterName(match[1].trim());
      setStatus('idle');
    };
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  };

  const handleConnect = async () => {
    if (!content || !clusterName) return;
    setIsLoading(true);
    setStatus('idle');
    try {
      await onUpload(content, clusterName);
      setStatus('success');
    } catch (err) {
      setStatus('error');
      setErrorMsg(err instanceof Error ? err.message : 'Failed to connect cluster');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {!content ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={clsx('flex flex-col items-center justify-center gap-3 p-8 rounded-xl border-2 border-dashed cursor-pointer transition-all',
            isDragging ? 'border-blue-500 bg-blue-500/10' : 'border-border/50 hover:border-border hover:bg-accent/30')}
        >
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{ background: 'hsl(220 90% 60% / 0.1)' }}>
            <Upload className="w-7 h-7 text-blue-400" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">Drop your kubeconfig file here</p>
            <p className="text-xs text-muted-foreground mt-1">or click to browse · .yaml, .yml, .conf</p>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 p-4 rounded-xl border"
          style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
          <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-blue-500/10 flex-shrink-0">
            <FileCode2 className="w-5 h-5 text-blue-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{fileName}</p>
            <p className="text-xs text-muted-foreground">{(content.length / 1024).toFixed(1)} KB · Valid YAML</p>
          </div>
          <button onClick={() => { setContent(''); setFileName(''); setClusterName(''); }}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {status === 'error' && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-red-400"
          style={{ background: 'hsl(0 72% 51% / 0.1)', border: '1px solid hsl(0 72% 51% / 0.2)' }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" />{errorMsg}
        </div>
      )}
      {status === 'success' && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm text-green-400"
          style={{ background: 'hsl(142 70% 45% / 0.1)', border: '1px solid hsl(142 70% 45% / 0.2)' }}>
          <CheckCircle className="w-4 h-4 flex-shrink-0" />Cluster connected successfully!
        </div>
      )}

      {content && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Cluster name</label>
            <input type="text" placeholder="e.g. production-k8s" value={clusterName}
              onChange={(e) => setClusterName(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/50"
              style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' }} />
          </div>
          <button onClick={handleConnect} disabled={isLoading || !clusterName.trim()}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm text-white disabled:opacity-60"
            style={{ background: 'hsl(220 90% 60%)' }}>
            {isLoading ? <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white animate-spin" /> : <Server className="w-4 h-4" />}
            {isLoading ? 'Connecting...' : 'Connect cluster'}
          </button>
        </div>
      )}

      <input ref={inputRef} type="file" accept=".yaml,.yml,.conf" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) processFile(f); }} />
    </div>
  );
}
