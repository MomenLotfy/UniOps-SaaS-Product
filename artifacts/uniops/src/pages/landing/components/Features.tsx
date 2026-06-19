import { useLanding } from '../context/LandingContext';
import FadeIn from './FadeIn';

export default function Features() {
  const { t } = useLanding();

  const features = [
    { icon: 'ti-settings-automation', iconColor: '#818cf8', bg: 'rgba(99,102,241,.12)', title: t('f1_t'), desc: t('f1_d'), tags: ['Kubernetes', 'CI/CD', 'Auto-Deploy'] },
    { icon: 'ti-shield-lock', iconColor: '#f87171', bg: 'rgba(239,68,68,.1)', title: t('f2_t'), desc: t('f2_d'), tags: ['CVE Scan', 'Compliance', 'Threat Intel'] },
    { icon: 'ti-coins', iconColor: '#fbbf24', bg: 'rgba(245,158,11,.1)', title: t('f3_t'), desc: t('f3_d'), tags: ['Cost Anomaly', 'AWS Billing', 'Savings AI'] },
    { icon: 'ti-brain', iconColor: '#60a5fa', bg: 'rgba(6,182,212,.1)', title: t('f4_t'), desc: t('f4_d'), tags: ['Predictive AI', 'Root Cause', 'Anomaly ML'] },
  ];

  return (
    <section id="features" className="lp-section">
      <div className="lp-sec-in">
        <FadeIn>
          <span className="lp-sec-tag">{t('feat_tag')}</span>
          <h2 className="lp-sec-h">{t('feat_h')}</h2>
          <p className="lp-sec-sub">{t('feat_sub')}</p>
        </FadeIn>
        <div className="lp-feat-grid">
          {features.map((f, i) => (
            <FadeIn as="div" className="lp-fc" key={i}>
              <div className="lp-fc-top"></div>
              <div className="lp-fi" style={{ background: f.bg }}><i className={`ti ${f.icon}`} style={{ color: f.iconColor }}></i></div>
              <div className="lp-ft">{f.title}</div>
              <div className="lp-fd">{f.desc}</div>
              <div className="lp-ftags">
                {f.tags.map((tag, j) => <span className="lp-ftag" key={j}>{tag}</span>)}
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}
