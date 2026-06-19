import { useEffect, useState } from 'react';
import { useLanding } from '../context/LandingContext';
import FadeIn from './FadeIn';

const BASE = [98.7, 247, 128, 23];
const NOISE = [0.8, 12, 15, 8];
const DEC = [1, 0, 0, 0];

export default function Metrics() {
  const { t } = useLanding();
  const [vals, setVals] = useState(BASE);

  useEffect(() => {
    const id = setInterval(() => {
      setVals(BASE.map((b, i) => b + (Math.random() - 0.5) * NOISE[i]));
    }, 4000);
    return () => clearInterval(id);
  }, []);

  const fmt = (i: number) => (DEC[i] ? vals[i].toFixed(DEC[i]) : Math.round(vals[i]));

  return (
    <section id="metrics" className="lp-section">
      <div className="lp-sec-in">
        <FadeIn style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <span className="lp-sec-tag">{t('metrics_tag')}</span>
          <h2 className="lp-sec-h">{t('metrics_h')}</h2>
        </FadeIn>
        <FadeIn as="div" className="lp-metric-grid">
          <div className="lp-metric-card">
            <div className="lp-m-val lp-green">{fmt(0)}<span style={{ fontSize: '1rem' }}>%</span></div>
            <div className="lp-m-lbl">{t('metric1')}</div>
            <div className="lp-m-chg" style={{ color: '#4ade80' }}>↑ 2.3%</div>
          </div>
          <div className="lp-metric-card">
            <div className="lp-m-val lp-blue">{fmt(1)}</div>
            <div className="lp-m-lbl">{t('metric2')}</div>
            <div className="lp-m-chg" style={{ color: '#60a5fa' }}>↑ 12 today</div>
          </div>
          <div className="lp-metric-card">
            <div className="lp-m-val lp-amber">${fmt(2)}<span style={{ fontSize: '1rem' }}>K</span></div>
            <div className="lp-m-lbl">{t('metric3')}</div>
            <div className="lp-m-chg" style={{ color: '#f87171' }}>↑ 12.3% MTD</div>
          </div>
          <div className="lp-metric-card">
            <div className="lp-m-val lp-purple">{fmt(3)}<span style={{ fontSize: '1rem' }}>ms</span></div>
            <div className="lp-m-lbl">{t('metric4')}</div>
            <div className="lp-m-chg" style={{ color: '#4ade80' }}>↓ 4ms</div>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
