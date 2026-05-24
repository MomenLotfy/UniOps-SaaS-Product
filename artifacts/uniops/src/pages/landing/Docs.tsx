import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Zap, Search, Book, Code2, Shield, DollarSign, Brain, Plug, ChevronRight } from 'lucide-react';
import { ROUTES } from '@/lib/constants';
import { useState } from 'react';

const SECTIONS = [
  { icon: Book, title: 'Getting Started', color: 'text-blue-400', items: ['Quick start guide', 'Setting up your workspace', 'Inviting team members', 'Connecting your first integration'] },
  { icon: Code2, title: 'DevOps Center', color: 'text-blue-400', items: ['CI/CD pipeline monitoring', 'Kubernetes integration', 'GitHub Actions setup', 'GitLab CI/CD setup'] },
  { icon: Shield, title: 'Security Center', color: 'text-red-400', items: ['Threat detection overview', 'Vulnerability scanning', 'Compliance reporting', 'Security policies'] },
  { icon: DollarSign, title: 'FinOps Center', color: 'text-green-400', items: ['Cost visibility setup', 'Budget alerts', 'Savings recommendations', 'Tagging strategies'] },
  { icon: Brain, title: 'ML Insights', color: 'text-purple-400', items: ['Workload forecasting', 'Anomaly detection', 'Metric correlations', 'Custom models'] },
  { icon: Plug, title: 'Integrations', color: 'text-yellow-400', items: ['AWS CloudFormation', 'Google Cloud setup', 'Azure Active Directory', 'Kubernetes kubeconfig'] },
];

export default function Docs() {
  const [search, setSearch] = useState('');

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

      <main className="max-w-5xl mx-auto px-6 py-12 space-y-10">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="text-center space-y-4">
          <h1 className="text-3xl font-extrabold text-foreground">Documentation</h1>
          <p className="text-muted-foreground">Everything you need to get the most out of UniOps</p>
          <div className="relative max-w-lg mx-auto">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input type="text" placeholder="Search documentation..." value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-3 rounded-xl text-sm border outline-none focus:ring-2 focus:ring-blue-500/50"
              style={{ background: 'hsl(230 18% 10%)', borderColor: 'hsl(230 15% 16%)', color: 'white' }} />
          </div>
        </motion.div>

        <div className="p-6 rounded-2xl border" style={{ background: 'hsl(220 90% 60% / 0.08)', borderColor: 'hsl(220 90% 60% / 0.2)' }}>
          <div className="flex items-center gap-3 mb-3">
            <Book className="w-5 h-5 text-blue-400" />
            <h2 className="font-semibold text-foreground">New to UniOps?</h2>
          </div>
          <p className="text-sm text-muted-foreground mb-3">Get up and running in under 5 minutes with our quick start guide.</p>
          <Link to="#" className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 font-medium">
            Read quick start guide <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {SECTIONS.map((section, i) => {
            const Icon = section.icon;
            return (
              <motion.div key={section.title} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}
                className="p-5 rounded-2xl border" style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
                <div className="flex items-center gap-2.5 mb-3">
                  <Icon className={`w-4 h-4 ${section.color}`} />
                  <h3 className="text-sm font-bold text-foreground">{section.title}</h3>
                </div>
                <ul className="space-y-1.5">
                  {section.items.map((item) => (
                    <li key={item}>
                      <Link to="#" className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-blue-400 transition-colors">
                        <ChevronRight className="w-3 h-3 flex-shrink-0" />{item}
                      </Link>
                    </li>
                  ))}
                </ul>
              </motion.div>
            );
          })}
        </div>
      </main>
    </div>
  );
}
