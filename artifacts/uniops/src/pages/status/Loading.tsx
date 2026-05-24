import { Activity } from 'lucide-react';

export default function Loading() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'hsl(230 18% 6%)' }}>
      <div className="text-center">
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-6"
          style={{ background: 'linear-gradient(135deg, hsl(220 90% 55%), hsl(260 70% 60%))' }}>
          <Activity className="w-7 h-7 text-white" />
        </div>
        <div className="w-8 h-8 rounded-full border-2 border-primary/20 border-t-primary animate-spin mx-auto mb-4" />
        <p className="text-sm text-muted-foreground">Loading UniOps…</p>
      </div>
    </div>
  );
}
