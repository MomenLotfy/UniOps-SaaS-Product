import { useLanding } from '../context/LandingContext';
import FadeIn from './FadeIn';

export default function CTA() {
  const { t } = useLanding();
  return (
    <section className="lp-section">
      <div className="lp-sec-in">
        <FadeIn as="div" className="lp-cta-box">
          <div className="lp-cta-orb"></div>
          <span className="lp-sec-tag">{t('cta_tag')}</span>
          <h2 className="lp-cta-h">{t('cta_h')}</h2>
          <p className="lp-cta-sub">{t('cta_sub')}</p>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap', position: 'relative', zIndex: 1 }}>
            <a href="/auth/company-signup" className="lp-btn-hero">
              <span>{t('cta_btn1')}</span>
              <i className="ti ti-rocket" style={{ fontSize: '.95rem' }}></i>
            </a>
            <a href="#" className="lp-btn-hero2">
              <i className="ti ti-calendar" style={{ fontSize: '.9rem' }}></i>
              <span>{t('cta_btn2')}</span>
            </a>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
