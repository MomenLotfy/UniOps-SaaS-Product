import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Code2, Shield, DollarSign, Brain, Zap, Globe, Bell, GitMerge, Server, BarChart3, ArrowRight } from 'lucide-react';
import { ROUTES } from '@/lib/constants';

const FEATURES = [
  { icon: Code2, title: 'DevOps Center', color: 'hsl(220 90% 60%)', bg: 'hsl(220 90% 60% / 0.1)', desc: 'Monitor CI/CD pipelines, Kubernetes pods, and deployment health across all your infrastructure in one unified view.', highlights: ['Pipeline run tracking', 'Real-time pod metrics', 'Deployment status', 'Log streaming'] },
  { icon: Shield, title: 'Security Center', color: 'hsl(0 72% 55%)', bg: 'hsl(0 72% 55% / 0.1)', desc: 'Detect threats, track vulnerabilities, and maintain compliance with automated scanning and AI-powered risk scoring.', highlights: ['Threat detection', 'CVE tracking', 'Compliance reports', 'Incident timeline'] },
  { icon: DollarSign, title: 'FinOps Center', color: 'hsl(142 70% 45%)', bg: 'hsl(142 70% 45% / 0.1)', desc: 'Track cloud spend across AWS, GCP, and Azure. Get AI-powered recommendations to reduce waste and optimize costs.', highlights: ['Multi-cloud costs', 'Budget alerts', 'Savings recommendations', 'Anomaly detection'] },
  { icon: Brain, title: 'ML Insights', color: 'hsl(280 70% 60%)', bg: 'hsl(280 70% 60% / 0.1)', desc: 'Predictive workload forecasting, anomaly detection, and correlation analysis powered by machine learning models.', highlights: ['Workload forecasting', 'Anomaly alerts', 'Metric correlations', 'Pattern recognition'] },
  { icon: Bell, title: 'Unified Alerts', color: 'hsl(40 90% 55%)', bg: 'hsl(40 90% 55% / 0.1)', desc: 'Centralized alert management with intelligent routing, deduplication, and cross-center correlation.', highlights: ['Smart grouping', 'Multi-channel routing', 'Escalation policies', 'Alert suppression'] },
  { icon: Globe, title: 'Integrations', color: 'hsl(190 80% 50%)', bg: 'hsl(190 80% 50% / 0.1)', desc: 'Connect your entire stack — AWS, GCP, Azure, GitHub, GitLab, Kubernetes, Slack, Teams, and more.', highlights: ['50+ integrations', 'OAuth & API keys', 'Real-time sync', 'Custom webhooks'] },
];

const STATS = [
  { value: '50+', label: 'Integrations' },
  { value: '< 60s', label: 'Setup time' },
  { value: '99.9%', label: 'Uptime SLA' },
  { value: '10x', label: 'Faster MTTR' },
];

export default function Features() {
  return (
    <div className="min-h-screen" style={{ background: 'hsl(230 18% 7%)' }}>
      <nav className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
        <Link to={ROUTES.HOME} className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'hsl(220 90% 60%)' }}>
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-foreground">UniOps</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link to={ROUTES.LOGIN} className="text-sm text-muted-foreground hover:text-foreground transition-colors">Sign in</Link>
          <Link to={ROUTES.REGISTER} className="px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all"
            style={{ background: 'hsl(220 90% 60%)' }}>Get started</Link>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-16 space-y-20">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center space-y-4">
          <h1 className="text-4xl md:text-5xl font-extrabold text-foreground">
            One platform for <span style={{ color: 'hsl(220 90% 65%)' }}>every ops discipline</span>
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            UniOps unifies DevOps, SecOps, FinOps, and AI Insights in a single control tower, so your team can focus on shipping, not context-switching.
          </p>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {STATS.map((s, i) => (
            <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
              className="text-center p-5 rounded-2xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
              <div className="text-3xl font-extrabold text-foreground">{s.value}</div>
              <div className="text-sm text-muted-foreground mt-1">{s.label}</div>
            </motion.div>
          ))}
        </div>

        <div className="grid md:grid-cols-2 gap-5">
          {FEATURES.map((feat, i) => {
            const Icon = feat.icon;
            return (
              <motion.div key={feat.title} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
                className="p-6 rounded-2xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: feat.bg }}>
                    <Icon className="w-6 h-6" style={{ color: feat.color }} />
                  </div>
                  <h2 className="text-base font-bold text-foreground">{feat.title}</h2>
                </div>
                <p className="text-sm text-muted-foreground mb-4">{feat.desc}</p>
                <ul className="space-y-1.5">
                  {feat.highlights.map((h) => (
                    <li key={h} className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span style={{ color: feat.color }}>✓</span>{h}
                    </li>
                  ))}
                </ul>
              </motion.div>
            );
          })}
        </div>

        <div className="text-center p-12 rounded-2xl border" style={{ background: 'hsl(220 90% 60% / 0.08)', borderColor: 'hsl(220 90% 60% / 0.2)' }}>
          <h2 className="text-2xl font-bold text-foreground mb-3">Ready to unify your operations?</h2>
          <p className="text-muted-foreground mb-6">Start your free trial — no credit card required.</p>
          <Link to={ROUTES.REGISTER}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white transition-all hover:opacity-90"
            style={{ background: 'hsl(220 90% 60%)' }}>
            Start free trial <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </main>
    </div>
  );
}
