import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Zap, Users, Target, Heart, ArrowRight } from 'lucide-react';
import { ROUTES } from '@/lib/constants';

const TEAM = [
  { name: 'Sarah Chen', role: 'CEO & Co-founder', bio: 'Ex-Google SRE, 12 years in platform engineering' },
  { name: 'Marcus Lee', role: 'CTO & Co-founder', bio: 'Built DevOps tooling at Stripe and HashiCorp' },
  { name: 'Aisha Patel', role: 'Head of Security', bio: 'Former security lead at Cloudflare' },
  { name: 'David Okonkwo', role: 'Head of Product', bio: 'Product at Datadog and New Relic for 8 years' },
];

const VALUES = [
  { icon: Target, title: 'Clarity over noise', desc: 'We believe ops teams are drowning in dashboards. We build for signal, not volume.' },
  { icon: Users, title: 'Teams first', desc: 'Great operations is a team sport. Everything we build enables collaboration.' },
  { icon: Heart, title: 'Empathy-driven', desc: 'We\'ve been on-call at 3am. We design for the person under pressure.' },
];

export default function About() {
  return (
    <div className="min-h-screen" style={{ background: 'hsl(230 18% 7%)' }}>
      <nav className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
        <Link to={ROUTES.HOME} className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'hsl(220 90% 60%)' }}>
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-foreground">UniOps</span>
        </Link>
        <Link to={ROUTES.REGISTER} className="px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: 'hsl(220 90% 60%)' }}>Get started</Link>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-16 space-y-16">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center space-y-4">
          <h1 className="text-4xl font-extrabold text-foreground">Building the command tower<br />for modern operations teams</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            UniOps was born from frustration — too many tools, too many dashboards, and no single place to see what's actually happening across your entire stack.
          </p>
        </motion.div>

        <div className="p-8 rounded-2xl border" style={{ background: 'hsl(220 90% 60% / 0.05)', borderColor: 'hsl(220 90% 60% / 0.15)' }}>
          <h2 className="text-xl font-bold text-foreground mb-3">Our mission</h2>
          <p className="text-muted-foreground leading-relaxed">
            To give every engineering team — from startups to enterprises — a unified operational intelligence platform that reduces cognitive load, cuts MTTR, and lets engineers focus on building rather than firefighting.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-bold text-foreground mb-6">Our values</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {VALUES.map((v, i) => (
              <motion.div key={v.title} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
                className="p-5 rounded-2xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: 'hsl(220 90% 60% / 0.15)' }}>
                  <v.icon className="w-5 h-5 text-blue-400" />
                </div>
                <h3 className="text-sm font-bold text-foreground mb-1.5">{v.title}</h3>
                <p className="text-xs text-muted-foreground">{v.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-xl font-bold text-foreground mb-6">The team</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {TEAM.map((m, i) => (
              <motion.div key={m.name} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.08 }}
                className="flex items-center gap-4 p-4 rounded-xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
                <div className="w-12 h-12 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0"
                  style={{ background: 'hsl(220 90% 60% / 0.15)', color: 'hsl(220 90% 70%)' }}>
                  {m.name.split(' ').map((n) => n[0]).join('')}
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">{m.name}</p>
                  <p className="text-xs text-blue-400">{m.role}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{m.bio}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        <div className="text-center p-12 rounded-2xl border" style={{ background: 'hsl(220 90% 60% / 0.08)', borderColor: 'hsl(220 90% 60% / 0.2)' }}>
          <h2 className="text-2xl font-bold text-foreground mb-3">Join 500+ teams on UniOps</h2>
          <Link to={ROUTES.REGISTER}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white hover:opacity-90"
            style={{ background: 'hsl(220 90% 60%)' }}>
            Start free trial <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </main>
    </div>
  );
}
