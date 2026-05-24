import { Activity } from 'lucide-react';
import { Link } from 'react-router-dom';

interface AuthLayoutProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
}

export function AuthLayout({ children, title, subtitle }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex" style={{ background: 'hsl(230 20% 4%)' }}>
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: 'linear-gradient(135deg, hsl(220 90% 8%) 0%, hsl(260 60% 10%) 100%)' }}>
        <div className="absolute inset-0 opacity-5"
          style={{ backgroundImage: 'radial-gradient(circle at 30% 30%, hsl(220 90% 60%) 0%, transparent 60%), radial-gradient(circle at 80% 80%, hsl(260 70% 60%) 0%, transparent 60%)' }} />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, hsl(220 90% 55%), hsl(260 70% 60%))' }}>
              <Activity className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="font-bold text-white text-lg">UniOps</div>
              <div className="text-xs" style={{ color: 'hsl(215 16% 47%)' }}>Control Tower</div>
            </div>
          </div>
          <h2 className="text-3xl font-bold text-white mb-4 leading-tight">
            Unified operational<br />intelligence for your<br />entire stack.
          </h2>
          <p style={{ color: 'hsl(215 16% 57%)' }} className="text-base leading-relaxed">
            Monitor DevOps pipelines, security threats, cloud costs, and ML insights — all in one control plane.
          </p>
        </div>
        <div className="relative z-10 space-y-4">
          {[
            { metric: '99.9%', label: 'Platform uptime SLA' },
            { metric: '< 2s',  label: 'Threat detection latency' },
            { metric: '40%',   label: 'Average cloud savings' },
          ].map((s) => (
            <div key={s.label} className="flex items-center gap-4">
              <div className="text-2xl font-bold" style={{ color: 'hsl(220 90% 70%)' }}>{s.metric}</div>
              <div style={{ color: 'hsl(215 16% 57%)' }} className="text-sm">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex flex-col justify-center px-6 py-12 lg:px-12">
        <div className="mx-auto w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, hsl(220 90% 55%), hsl(260 70% 60%))' }}>
              <Activity className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-white">UniOps</span>
          </div>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-white mb-1">{title}</h1>
            {subtitle && <p style={{ color: 'hsl(215 16% 47%)' }} className="text-sm">{subtitle}</p>}
          </div>

          {children}
        </div>
      </div>
    </div>
  );
}
