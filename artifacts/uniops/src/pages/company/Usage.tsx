import { motion } from 'framer-motion';
import { TrendingUp, Users, Zap, Database, Clock, Loader2 } from 'lucide-react';
import { useCompany } from '@/contexts/CompanyContext';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useApi } from '@/hooks/use-api';

export default function Usage() {
  const { usage, company } = useCompany();
  const { data: auditData, loading } = useApi<any>('/audit-logs/summary');

  // ✅ بدلاً من return null، نعرض واجهة تحميل
  if (!usage || !company) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        <span className="ml-3 text-gray-400">جاري تحميل بيانات الاستخدام...</span>
      </div>
    );
  }

  const trendData = Array.isArray(auditData?.daily_calls) ? auditData.daily_calls : [];
  const retentionDays = usage?.dataRetention?.days ?? 0;
  const retentionLimit = usage?.dataRetention?.limit ?? 0;

  const metrics = [
    { label: 'Members', icon: Users, used: usage?.users?.used ?? 0, limit: usage?.users?.limit ?? 1, color: '#3b82f6' },
    { label: 'Integrations', icon: Zap, used: usage?.integrations?.used ?? 0, limit: usage?.integrations?.limit ?? 1, color: '#8b5cf6' },
    { label: 'API Calls', icon: TrendingUp, used: usage?.apiCalls?.used ?? 0, limit: usage?.apiCalls?.limit ?? 1, color: '#10b981' },
    { label: 'Retention', icon: Database, used: retentionDays, limit: retentionLimit, color: '#f59e0b', unit: ' days' },
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      <div className="page-header">
        <div>
          <h1 className="page-title">Platform Usage</h1>
          <p className="page-subtitle">
            {company?.plan ? `${company.plan} Plan` : 'Active Plan'}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="w-4 h-4" />
          Resets May 1, 2026
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {metrics.map((m) => {
          const pct = Math.min((m.used / m.limit) * 100, 100);
          return (
            <div key={m.label} className="card-base">
              <div className="flex items-center gap-2 mb-3">
                <m.icon className="w-4 h-4" style={{ color: m.color }} />
                <span className="text-sm font-medium text-foreground">{m.label}</span>
              </div>
              <div className="text-2xl font-bold text-foreground mb-1">
                {m.used.toLocaleString()}{m.unit ?? ''}
              </div>
              <div className="text-xs text-muted-foreground mb-2">
                of {m.limit.toLocaleString()}{m.unit ?? ''} limit
              </div>
              <div className="progress-bar-base">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${pct}%`,
                    background: pct > 85 ? '#ef4444' : m.color,
                  }}
                />
              </div>
              <div className="text-xs text-muted-foreground mt-1 text-right">{pct.toFixed(0)}%</div>
            </div>
          );
        })}
      </div>

      <div className="card-base">
        <h2 className="text-sm font-semibold text-foreground mb-4">API Calls — Last 30 Days</h2>
        {loading ? (
          <div className="h-[200px] flex items-center justify-center text-sm text-muted-foreground">
            Loading live usage data…
          </div>
        ) : trendData.length === 0 ? (
          <div className="h-[200px] flex items-center justify-center text-sm text-muted-foreground">
            No live usage trend available yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="apiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(230 15% 14%)" />
              <XAxis dataKey="day" tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} tickLine={false} axisLine={false} interval={4} />
              <YAxis tick={{ fill: 'hsl(215 16% 47%)', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: 'hsl(230 18% 10%)', border: '1px solid hsl(230 15% 14%)', borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="calls" stroke="#10b981" strokeWidth={2} fill="url(#apiGrad)" name="API Calls" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </motion.div>
  );
}
