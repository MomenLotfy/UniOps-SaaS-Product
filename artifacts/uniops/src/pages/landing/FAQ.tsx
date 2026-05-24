import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Zap, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import { ROUTES } from '@/lib/constants';

const FAQS = [
  { q: 'How does the free trial work?', a: 'You get 14 days of full access to the Professional plan — no credit card required. At the end of the trial you can choose to upgrade or your workspace will move to the Starter plan (if available).' },
  { q: 'What cloud providers do you support?', a: 'UniOps integrates with AWS, Google Cloud, and Microsoft Azure for cost and infrastructure data. For CI/CD, we support GitHub Actions and GitLab CI. Kubernetes support works with any distribution via kubeconfig.' },
  { q: 'How do you handle my cloud credentials?', a: 'For AWS we use cross-account IAM roles with read-only permissions — we never store your access keys. For GCP we use service account keys with minimal permissions. All credentials are encrypted at rest using AES-256.' },
  { q: 'Can I self-host UniOps?', a: 'Self-hosted deployment is available on the Enterprise plan. We provide Helm charts and Terraform modules for deploying on your own infrastructure. Contact our sales team for details.' },
  { q: 'How does the ML-powered forecasting work?', a: 'Our models train on your historical metrics (CPU, memory, cost, build times) to predict future trends. Models are retrained weekly. You can also trigger manual retraining when your workload patterns change significantly.' },
  { q: 'What integrations are included in each plan?', a: 'Starter: 3 integrations. Professional: 15 integrations. Enterprise: unlimited. All plans include the same integration types — you\'re only limited by quantity.' },
  { q: 'How is pricing calculated for Enterprise?', a: 'Enterprise pricing is based on your team size, number of integrations, and data retention requirements. Contact our sales team for a custom quote.' },
  { q: 'Do you offer SSO and SCIM provisioning?', a: 'Yes, SSO via SAML 2.0 and SCIM provisioning are available on the Professional and Enterprise plans. We support Okta, Azure AD, Google Workspace, and any SAML-compatible IdP.' },
  { q: 'What is your uptime SLA?', a: 'We guarantee 99.9% uptime for all plans. Enterprise customers can negotiate a 99.99% SLA with dedicated infrastructure.' },
  { q: 'How do I export my data if I leave?', a: 'You can export all your data (costs, alerts, audit logs) in JSON or CSV format from the settings page at any time. We also support data export via our API.' },
];

export default function FAQ() {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

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

      <main className="max-w-3xl mx-auto px-6 py-12 space-y-8">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="text-center space-y-3">
          <h1 className="text-3xl font-extrabold text-foreground">Frequently Asked Questions</h1>
          <p className="text-muted-foreground">Everything you need to know about UniOps</p>
        </motion.div>

        <div className="space-y-2">
          {FAQS.map((faq, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
              className="rounded-xl border overflow-hidden" style={{ borderColor: 'hsl(230 15% 14%)' }}>
              <button
                onClick={() => setOpenIdx(openIdx === i ? null : i)}
                className="w-full flex items-center justify-between p-4 text-left transition-colors hover:bg-accent/30"
                style={{ background: openIdx === i ? 'hsl(220 90% 60% / 0.06)' : 'hsl(230 18% 8%)' }}>
                <span className="text-sm font-semibold text-foreground pr-4">{faq.q}</span>
                {openIdx === i ? <ChevronUp className="w-4 h-4 text-blue-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />}
              </button>
              {openIdx === i && (
                <div className="px-4 pb-4 pt-0" style={{ background: 'hsl(230 18% 8%)' }}>
                  <p className="text-sm text-muted-foreground leading-relaxed">{faq.a}</p>
                </div>
              )}
            </motion.div>
          ))}
        </div>

        <div className="text-center p-8 rounded-2xl border" style={{ background: 'hsl(220 90% 60% / 0.08)', borderColor: 'hsl(220 90% 60% / 0.2)' }}>
          <p className="text-foreground font-medium mb-1">Still have questions?</p>
          <p className="text-sm text-muted-foreground mb-4">Our team typically replies within 24 hours.</p>
          <a href="mailto:support@uniops.io"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-blue-400 hover:text-blue-300 transition-colors border border-blue-500/30 hover:bg-blue-500/10">
            Contact support →
          </a>
        </div>
      </main>
    </div>
  );
}
