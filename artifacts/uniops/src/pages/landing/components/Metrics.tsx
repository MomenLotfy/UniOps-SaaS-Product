import { useLanding } from '../context/LandingContext';
import FadeIn from './FadeIn';

export default function Metrics() {
  const { t } = useLanding();

  return (
    <section id="metrics" className="lp-section">
      <div className="lp-sec-in">
        <FadeIn style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <span className="lp-sec-tag">{t('metrics_tag')}</span>
          <h2 className="lp-sec-h">{t('metrics_h')}</h2>
        </FadeIn>
        <FadeIn as="div" className="lp-metric-grid">
          <div className="lp-metric-card">
            <div className="lp-m-val lp-green">0<span style={{ fontSize: '1rem' }}>%</span></div>
            <div className="lp-m-lbl">{t('metric1')}</div>
            <div className="lp-m-chg" style={{ color: '#4ade80' }}>↑ 0%</div>
          </div>
          <div className="lp-metric-card">
            <div className="lp-m-val lp-blue">0</div>
            <div className="lp-m-lbl">{t('metric2')}</div>
            <div className="lp-m-chg" style={{ color: '#007acc' }}>↑ 0 today</div>
          </div>
          <div className="lp-metric-card">
            <div className="lp-m-val lp-amber">$0<span style={{ fontSize: '1rem' }}>K</span></div>
            <div className="lp-m-lbl">{t('metric3')}</div>
            <div className="lp-m-chg" style={{ color: '#f87171' }}>↑ 0% MTD</div>
          </div>
          <div className="lp-metric-card">
            <div className="lp-m-val lp-purple">0<span style={{ fontSize: '1rem' }}>ms</span></div>
            <div className="lp-m-lbl">{t('metric4')}</div>
            <div className="lp-m-chg" style={{ color: '#4ade80' }}>↓ 0ms</div>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
