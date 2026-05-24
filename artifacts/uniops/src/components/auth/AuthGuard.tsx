import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { ROUTES } from '@/lib/constants';
import type { UserRole } from '@/types/user';

interface AuthGuardProps {
  children: React.ReactNode;
  requireAuth?: boolean;
  allowedRoles?: UserRole[];
  redirectTo?: string;
  fallback?: React.ReactNode;
}

export function AuthGuard({
  children,
  requireAuth = true,
  allowedRoles,
  redirectTo,
  fallback,
}: AuthGuardProps) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (isLoading) return;

    if (requireAuth && !isAuthenticated) {
      navigate(ROUTES.LOGIN, { state: { from: location }, replace: true });
      return;
    }

    if (!requireAuth && isAuthenticated) {
      navigate(redirectTo ?? ROUTES.COMMAND, { replace: true });
      return;
    }

    if (requireAuth && isAuthenticated && allowedRoles && user) {
      const hasRole = allowedRoles.includes(user.role);
      if (!hasRole) {
        navigate(ROUTES.FORBIDDEN, { replace: true });
      }
    }
  }, [isLoading, isAuthenticated, user, requireAuth, allowedRoles, redirectTo, navigate, location]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'hsl(230 18% 7%)' }}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-full border-2 border-blue-500/20 border-t-blue-500 animate-spin" />
          <p className="text-sm text-muted-foreground">Authenticating...</p>
        </div>
      </div>
    );
  }

  if (requireAuth && !isAuthenticated) return fallback ?? null;

  if (requireAuth && isAuthenticated && allowedRoles && user) {
    if (!allowedRoles.includes(user.role)) return fallback ?? null;
  }

  return <>{children}</>;
}
