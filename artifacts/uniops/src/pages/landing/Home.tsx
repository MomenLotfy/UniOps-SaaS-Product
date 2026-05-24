import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Activity, Shield, DollarSign, Brain, GitBranch, ArrowRight, CheckCircle, Star } from 'lucide-react';
import { ROUTES } from '@/lib/constants';

const FEATURES = [
  { icon: Activity, title: 'Command Center', desc: 'Unified operational overview of your entire infrastructure in real time.', color: 'text-blue-400', bg: 'bg-blue-500/10' },
  { icon: GitBranch, title: 'DevOps Engine', desc: 'CI/CD pipelines, Kubernetes pods, and deployments all in one place.', color: 'text-cyan-400', bg: 'bg-cyan-500/10' },
  { icon: Shield, title: 'Security Center', desc: 'Live threat detection, CVE tracking, and compliance monitoring.', color: 'text-red-400', bg: 'bg-red-500/10' },
  { icon: DollarSign, title: 'Cost Intelligence', desc: 'Cloud spend analysis, anomaly detection, and savings opportunities.', color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  { icon: Brain, title: 'ML Insights', desc: 'AI-powered pattern discovery, predictions, and smart recommendations.', color: 'text-purple-400', bg: 'bg-purple-500/10' },
];

const STATS = [
  { value: '99.9%', label: 'Uptime SLA' },
  { value: '< 2s', label: 'Threat detection' },
  { value: '40%', label: 'Avg. cost savings' },
  { value: '10k+', label: 'Services monitored' },
];

const TESTIMONIALS = [
  { quote: 'UniOps gave our team a single pane of glass for all ops. We cut incident response time by 60%.', author: 'Sarah Chen', title: 'Head of Engineering, TechFlow' },
  { quote: 'The ML insights alone saved us $18k/month by catching waste we didn\'t even know existed.', author: 'Marcus Johnson', title: 'FinOps Lead, ScaleUp Inc' },
];

export default function Home() {
  return (
    <div style={{ background: 'hsl(230 20% 4%)', color: 'hsl(213 31% 91%)', minHeight: '100vh' }}>
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-4 border-b" style={{ borderColor: 'hsl(230 15% 10%)' }}>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, hsl(220 90% 55%), hsl(260 70% 60%))' }}>
            <Activity className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold">UniOps</span>
        </div>
        <div className="flex items-center gap-6">
          <Link to={ROUTES.FEATURES} className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>Features</Link>
          <Link to={ROUTES.PRICING} className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>Pricing</Link>
          <Link to={ROUTES.LOGIN} className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>Sign in</Link>
          <Link to={ROUTES.COMPANY_SIGNUP}
            className="px-4 py-1.5 rounded-lg text-sm font-semibold"
            style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
            Get started free
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="text-center px-8 py-24 max-w-4xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs mb-6 border"
            style={{ background: 'hsl(220 90% 60% / 0.1)', borderColor: 'hsl(220 90% 60% / 0.3)', color: 'hsl(220 90% 75%)' }}>
            <Star className="w-3 h-3" /> Trusted by 500+ engineering teams worldwide
          </div>
          <h1 className="text-5xl font-bold leading-tight mb-6" style={{ color: 'hsl(213 31% 91%)' }}>
            The Enterprise Operations<br />
            <span style={{ background: 'linear-gradient(135deg, hsl(220 90% 70%), hsl(260 80% 70%))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Control Tower
            </span>
          </h1>
          <p className="text-lg mb-8" style={{ color: 'hsl(215 16% 57%)' }}>
            Unify your DevOps, Security, Cost, and ML operations into one intelligent platform.
            Stop context-switching. Start shipping faster.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link to={ROUTES.COMPANY_SIGNUP}
              className="flex items-center gap-2 px-6 py-3 rounded-lg font-semibold"
              style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
              Start free trial <ArrowRight className="w-4 h-4" />
            </Link>
            <Link to={ROUTES.COMMAND}
              className="flex items-center gap-2 px-6 py-3 rounded-lg font-semibold border"
              style={{ borderColor: 'hsl(230 15% 14%)', color: 'hsl(215 16% 77%)' }}>
              View live demo
            </Link>
          </div>
        </motion.div>
      </section>

      {/* Stats */}
      <section className="px-8 py-12 border-y" style={{ borderColor: 'hsl(230 15% 10%)' }}>
        <div className="grid grid-cols-4 gap-8 max-w-4xl mx-auto">
          {STATS.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-3xl font-bold" style={{ background: 'linear-gradient(135deg, hsl(220 90% 70%), hsl(260 80% 70%))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{s.value}</div>
              <div className="text-sm mt-1" style={{ color: 'hsl(215 16% 57%)' }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="px-8 py-20 max-w-6xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-12">Everything your team needs</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {FEATURES.map((f, i) => (
            <motion.div key={f.title} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
              className="p-6 rounded-xl border" style={{ background: 'hsl(230 18% 7%)', borderColor: 'hsl(230 15% 12%)' }}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 ${f.bg}`}>
                <f.icon className={`w-5 h-5 ${f.color}`} />
              </div>
              <h3 className="font-semibold mb-2">{f.title}</h3>
              <p className="text-sm" style={{ color: 'hsl(215 16% 57%)' }}>{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Testimonials */}
      <section className="px-8 py-16" style={{ background: 'hsl(230 18% 6%)' }}>
        <div className="max-w-4xl mx-auto grid grid-cols-2 gap-6">
          {TESTIMONIALS.map((t) => (
            <div key={t.author} className="p-6 rounded-xl border" style={{ borderColor: 'hsl(230 15% 12%)' }}>
              <div className="flex gap-1 mb-3">{[...Array(5)].map((_, i) => <Star key={i} className="w-4 h-4 text-yellow-400 fill-yellow-400" />)}</div>
              <p className="text-sm mb-4" style={{ color: 'hsl(215 16% 77%)' }}>"{t.quote}"</p>
              <div className="text-sm font-semibold">{t.author}</div>
              <div className="text-xs" style={{ color: 'hsl(215 16% 57%)' }}>{t.title}</div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="text-center px-8 py-20">
        <h2 className="text-3xl font-bold mb-4">Ready to take control?</h2>
        <p className="text-lg mb-8" style={{ color: 'hsl(215 16% 57%)' }}>Join 500+ teams already using UniOps Control Tower.</p>
        <Link to={ROUTES.COMPANY_SIGNUP}
          className="inline-flex items-center gap-2 px-8 py-3 rounded-lg font-semibold text-lg"
          style={{ background: 'hsl(220 90% 60%)', color: 'white' }}>
          Get started — it's free <ArrowRight className="w-5 h-5" />
        </Link>
        <p className="text-xs mt-4" style={{ color: 'hsl(215 16% 47%)' }}>14-day free trial · No credit card required</p>
      </section>
    </div>
  );
}
