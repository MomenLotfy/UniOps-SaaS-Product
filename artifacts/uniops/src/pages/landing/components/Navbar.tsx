import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLanding } from '../context/LandingContext';

export default function Navbar() {
  const { theme, toggleTheme, lang, setLang, t } = useLanding();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <nav className={`lp-nav${scrolled ? ' sc' : ''}`}>
      <div className="lp-nav-in">
        <a href="#" className="lp-logo">
          <div className="lp-logo-box">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5" />
              <line x1="12" y1="22" x2="12" y2="15.5" />
              <polyline points="22 8.5 12 15.5 2 8.5" />
            </svg>
          </div>
          <span className="lp-logo-name">UniOps</span>
        </a>

        <div className="lp-nav-links">
          <a href="#features" className="lp-nl">{t('nav_features')}</a>
          <a href="#how" className="lp-nl">{t('nav_how')}</a>
          <a href="#metrics" className="lp-nl">{t('nav_metrics')}</a>
        </div>

        <div className="lp-nav-right">
          <div className="lp-pill-switch">
            <button className={`lp-pill-btn${lang === 'en' ? ' active' : ''}`} onClick={() => setLang('en')}>EN</button>
            <button className={`lp-pill-btn${lang === 'ar' ? ' active' : ''}`} onClick={() => setLang('ar')}>AR</button>
          </div>

          <button className="lp-theme-btn" onClick={toggleTheme} title="Toggle theme">
            <i className={theme === 'dark' ? 'ti ti-moon' : 'ti ti-sun'}></i>
          </button>

          <Link to="/auth/login" className="lp-btn-login">
            <i className="ti ti-login" style={{ fontSize: '.88rem' }}></i>
            Log In
          </Link>

          <Link to="/auth/company-signup" className="lp-btn-p">
            {t('nav_cta')}
            <i className="ti ti-arrow-right" style={{ fontSize: '.85rem' }}></i>
          </Link>
        </div>
      </div>
    </nav>
  );
}
