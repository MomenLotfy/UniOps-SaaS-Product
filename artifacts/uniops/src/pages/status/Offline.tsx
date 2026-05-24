import { WifiOff, RefreshCw } from 'lucide-react';

export default function Offline() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'hsl(230 18% 6%)' }}>
      <div className="text-center max-w-md px-6">
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6" style={{ background: 'hsl(215 16% 25% / 0.4)' }}>
          <WifiOff className="w-8 h-8 text-muted-foreground" />
        </div>
        <h1 className="text-2xl font-bold text-foreground mb-3">You're offline</h1>
        <p className="text-muted-foreground text-sm mb-8">UniOps can't reach the internet. Check your connection and try again.</p>
        <button onClick={() => window.location.reload()} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-colors"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          <RefreshCw className="w-4 h-4" /> Try Again
        </button>
      </div>
    </div>
  );
}
