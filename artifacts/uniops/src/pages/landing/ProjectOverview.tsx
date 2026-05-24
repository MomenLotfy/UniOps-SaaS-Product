import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, Brain, Cloud, Shield, BarChart3, Users, Server } from 'lucide-react';
import { ROUTES } from '@/lib/constants';

const ROWS = [
  ['Frontend', 'React 19 + TypeScript + Vite + Tailwind CSS + Framer Motion'],
  ['Backend', 'Node.js + Express + AWS SDK + Octokit + Kubernetes client'],
  ['Security', 'AES-256-GCM credential encryption + RBAC + endpoint protection model'],
  ['Data Sources', 'AWS Cost Explorer + GitHub + Kubernetes'],
  ['Analytics', 'ML insights over DevOps / Security / Cost signals'],
  ['Transport', 'REST API + WebSocket real-time updates'],
];

export default function ProjectOverview() {
  return (
    <div className="min-h-screen" style={{ background: 'hsl(230 18% 7%)' }}>
      <nav className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
        <Link to={ROUTES.HOME} className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'hsl(220 90% 60%)' }}>
            <Server className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-foreground">UniOps Control Tower</span>
        </Link>
        <Link to={ROUTES.REGISTER} className="px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: 'hsl(220 90% 60%)' }}>Start free trial</Link>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-14 space-y-10">
        <motion.section initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <p className="text-sm text-blue-400 font-semibold">تخيل معي...</p>
          <h1 className="text-4xl font-extrabold text-foreground leading-tight">UniOps Control Tower — Unified SaaS Operations Intelligence</h1>
          <p className="text-muted-foreground leading-relaxed max-w-4xl">
            منصة واحدة تجمع DevOps, Security, FinOps, and ML signals في dashboard موحد، بحيث يرى CTO وفِرق التشغيل الصورة الكاملة بدل التشتت بين أدوات متعددة.
          </p>
        </motion.section>

        <section className="grid md:grid-cols-2 gap-4">
          {[
            { icon: Cloud, title: 'Cloud & DevOps', desc: 'Cluster health, pipelines, and infrastructure signals.' },
            { icon: Shield, title: 'Security', desc: 'Threats, policies, and risk posture.' },
            { icon: BarChart3, title: 'FinOps', desc: 'Cost visibility, savings, and budget intelligence.' },
            { icon: Brain, title: 'ML Insights', desc: 'Correlations, anomalies, and predictions.' },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.title} className="p-5 rounded-2xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: 'hsl(220 90% 60% / 0.12)' }}>
                  <Icon className="w-5 h-5 text-blue-400" />
                </div>
                <h2 className="text-sm font-bold text-foreground mb-1.5">{item.title}</h2>
                <p className="text-xs text-muted-foreground leading-relaxed">{item.desc}</p>
              </div>
            );
          })}
        </section>

        <section className="rounded-2xl border overflow-hidden" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
          <div className="px-5 py-4 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
            <h2 className="text-lg font-bold text-foreground">Architecture Snapshot</h2>
          </div>
          <div className="p-5 grid gap-3">
            {ROWS.map(([name, value]) => (
              <div key={name} className="grid md:grid-cols-3 gap-3 text-sm">
                <div className="font-semibold text-blue-400">{name}</div>
                <div className="md:col-span-2 text-muted-foreground">{value}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="grid md:grid-cols-2 gap-4">
          <div className="p-6 rounded-2xl border" style={{ background: 'hsl(220 90% 60% / 0.06)', borderColor: 'hsl(220 90% 60% / 0.18)' }}>
            <h2 className="text-lg font-bold text-foreground mb-3">الجمهور المستهدف</h2>
            <ul className="space-y-2 text-sm text-muted-foreground leading-relaxed">
              <li>CTO: executive visibility and decision speed.</li>
              <li>DevOps Engineers: cluster and pipeline control.</li>
              <li>Security Engineers: risk and policy posture.</li>
              <li>FinOps: cost and savings intelligence.</li>
              <li>Data Scientists: unified signals for modeling.</li>
            </ul>
          </div>
          <div className="p-6 rounded-2xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
            <h2 className="text-lg font-bold text-foreground mb-3">تدفق البيانات</h2>
            <pre className="text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed">{`K8s / AWS / GitHub
      ↓
Backend Integrations
      ↓
REST API + WebSocket
      ↓
Unified Dashboard
      ↓
ML Engine → correlations / anomalies / predictions`}</pre>
          </div>
        </section>

        <section className="p-6 rounded-2xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
          <h2 className="text-lg font-bold text-foreground mb-3">الخاتمة</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            UniOps Control Tower يقدّم value واضحة: تقليل التشتت، رفع الوعي التشغيلي، وربط DevOps وSecurity وFinOps في layer واحدة مفهومة وقابلة للتوسع.
          </p>
          <div className="mt-5">
            <Link to={ROUTES.REGISTER} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-white" style={{ background: 'hsl(220 90% 60%)' }}>
              Explore the platform <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
