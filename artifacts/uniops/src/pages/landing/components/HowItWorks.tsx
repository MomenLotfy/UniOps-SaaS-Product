import { useLanding } from '../context/LandingContext';
import FadeIn from './FadeIn';

export default function HowItWorks() {
  const { t } = useLanding();

  const steps = [
    { n: '01', title: t('step1_t'), desc: t('step1_d') },
    { n: '02', title: t('step2_t'), desc: t('step2_d') },
    { n: '03', title: t('step3_t'), desc: t('step3_d') },
  ];

  return (
    <section id="how" className="lp-section">
      <div className="lp-sec-in">
        <FadeIn style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <span className="lp-sec-tag">{t('how_tag')}</span>
          <h2 className="lp-sec-h">{t('how_h')}</h2>
          <p className="lp-sec-sub" style={{ textAlign: 'center' }}>{t('how_sub')}</p>
        </FadeIn>
        <FadeIn as="div" className="lp-how-grid">
          <div className="lp-how-line"></div>
          {steps.map((s) => (
            <div className="lp-step" key={s.n}>
              <div className="lp-step-n"><span>{s.n}</span></div>
              <div className="lp-step-t">{s.title}</div>
              <div className="lp-step-d">{s.desc}</div>
            </div>
          ))}
        </FadeIn>
      </div>
    </section>
  );
}
