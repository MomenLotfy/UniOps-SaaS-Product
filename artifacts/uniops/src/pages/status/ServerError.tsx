import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react';
import { ROUTES } from '@/lib/constants';

export default function ServerError() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'hsl(230 20% 4%)' }}>
      <div className="text-center space-y-4">
        <div className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'hsl(38 92% 50% / 0.1)' }}>
          <AlertTriangle className="w-10 h-10 text-yellow-400" />
        </div>
        <div className="text-6xl font-bold" style={{ color: 'hsl(38 92% 50%)' }}>500</div>
        <div className="text-xl font-semibold text-white">Internal Server Error</div>
        <p className="text-sm max-w-xs" style={{ color: 'hsl(215 16% 57%)' }}>Something went wrong on our end. Our team has been notified and is working on a fix.</p>
        <div className="flex items-center justify-center gap-3 mt-4">
          <button onClick={() => window.location.reload()}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-sm border"
            style={{ borderColor: 'hsl(230 15% 14%)', color: 'hsl(215 16% 77%)', background: 'transparent' }}>
            <RefreshCw className="w-4 h-4" /> Try again
          </button>
          <Link to={ROUTES.COMMAND} className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-sm"
            style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
            <ArrowLeft className="w-4 h-4" /> Go home
          </Link>
        </div>
      </div>
    </div>
  );
}
