import { Link } from 'react-router-dom';
import { ShieldOff, ArrowLeft } from 'lucide-react';
import { ROUTES } from '@/lib/constants';

export default function Forbidden() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'hsl(230 20% 4%)' }}>
      <div className="text-center space-y-4">
        <div className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'hsl(0 72% 51% / 0.1)' }}>
          <ShieldOff className="w-10 h-10 text-red-400" />
        </div>
        <div className="text-6xl font-bold" style={{ color: 'hsl(0 72% 51%)' }}>403</div>
        <div className="text-xl font-semibold text-white">Access Forbidden</div>
        <p className="text-sm max-w-xs" style={{ color: 'hsl(215 16% 57%)' }}>You don't have permission to access this page. Contact your admin if this is a mistake.</p>
        <Link to={ROUTES.COMMAND} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-sm mt-4"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          <ArrowLeft className="w-4 h-4" /> Back to dashboard
        </Link>
      </div>
    </div>
  );
}
