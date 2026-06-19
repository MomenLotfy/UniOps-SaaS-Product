import { useLanding } from '../context/LandingContext';
import HeroWidgets from './HeroWidgets';

export default function Hero() {
  const { t } = useLanding();
  return (
    <section className="lp-hero">
      <div className="lp-hero-in">
        <div>
          <div className="lp-hero-badge">
            <span className="lp-badge-dot"></span>
            <span>{t('hero_badge')}</span>
          </div>
          <h1 className="lp-hero-h1">
            <span>{t('hero_t1')}</span><br />
            <span className="lp-gt">{t('hero_t2')}</span><br />
            <span>{t('hero_t3')}</span>
          </h1>
          <p className="lp-hero-sub">{t('hero_sub')}</p>
          <div className="lp-hero-btns">
            <a href="/auth/company-signup" className="lp-btn-hero">
              <span>{t('hero_btn1')}</span>
              <i className="ti ti-rocket" style={{ fontSize: '.95rem' }}></i>
            </a>
            <a href="#features" className="lp-btn-hero2">
              <i className="ti ti-player-play" style={{ fontSize: '.9rem' }}></i>
              <span>{t('hero_btn2')}</span>
            </a>
          </div>
          <div className="lp-hero-stats">
            <div>
              <div className="lp-stat-num">500+</div>
              <div className="lp-stat-lbl">{t('stat1')}</div>
            </div>
            <div>
              <div className="lp-stat-num">99.9%</div>
              <div className="lp-stat-lbl">{t('stat2')}</div>
            </div>
            <div>
              <div className="lp-stat-num">40%</div>
              <div className="lp-stat-lbl">{t('stat3')}</div>
            </div>
          </div>
        </div>
        <HeroWidgets />
      </div>
    </section>
  );
}
