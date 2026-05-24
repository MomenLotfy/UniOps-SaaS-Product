import { motion } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Home, Search } from 'lucide-react';
import { ROUTES } from '@/lib/constants';
import { useAuth } from '@/contexts/AuthContext';

export default function NotFound() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const homeRoute = isAuthenticated ? ROUTES.COMMAND : ROUTES.HOME;

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'hsl(230 18% 7%)' }}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="text-center max-w-md w-full space-y-6"
      >
        <div className="relative mx-auto w-32 h-32">
          <div className="absolute inset-0 rounded-3xl opacity-20 blur-2xl" style={{ background: 'hsl(220 90% 60%)' }} />
          <div className="relative w-32 h-32 rounded-3xl flex items-center justify-center border"
            style={{ background: 'hsl(220 90% 60% / 0.1)', borderColor: 'hsl(220 90% 60% / 0.2)' }}>
            <Search className="w-14 h-14 text-blue-400 opacity-60" />
          </div>
        </div>

        <div>
          <h1 className="text-6xl font-extrabold tracking-tight mb-2" style={{ color: 'hsl(220 90% 60%)' }}>404</h1>
          <h2 className="text-xl font-bold text-foreground mb-2">Page not found</h2>
          <p className="text-sm text-muted-foreground">
            The page you're looking for doesn't exist or has been moved. Let's get you back on track.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium border transition-colors hover:bg-accent text-muted-foreground"
            style={{ borderColor: 'hsl(230 15% 18%)' }}>
            <ArrowLeft className="w-4 h-4" /> Go back
          </button>
          <Link
            to={homeRoute}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white"
            style={{ background: 'hsl(220 90% 60%)' }}>
            <Home className="w-4 h-4" />
            {isAuthenticated ? 'Go to dashboard' : 'Go home'}
          </Link>
        </div>

        {isAuthenticated && (
          <div className="pt-2 border-t" style={{ borderColor: 'hsl(230 15% 14%)' }}>
            <p className="text-xs text-muted-foreground mb-2">Or jump to a section:</p>
            <div className="flex gap-2 flex-wrap justify-center">
              {[
                { label: 'DevOps', to: ROUTES.DEVOPS },
                { label: 'Security', to: ROUTES.SECURITY },
                { label: 'FinOps', to: ROUTES.COST },
                { label: 'ML Insights', to: ROUTES.INSIGHTS },
              ].map((link) => (
                <Link key={link.label} to={link.to}
                  className="text-xs px-3 py-1.5 rounded-lg text-blue-400 hover:text-blue-300 transition-colors"
                  style={{ background: 'hsl(220 90% 60% / 0.1)', border: '1px solid hsl(220 90% 60% / 0.2)' }}>
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
