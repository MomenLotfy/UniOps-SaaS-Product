import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLanding } from '../context/LandingContext';
import darkModeLogo from '../../../assets/logo-darkmode.svg';
import lightModeLogo from '../../../assets/logo-lightmode.svg';
import cloudOne from '../../../assets/theme-switch/cloud-1.svg';
import cloudTwo from '../../../assets/theme-switch/cloud-2.svg';
import moon from '../../../assets/theme-switch/moon.svg';
import stars from '../../../assets/theme-switch/stars.svg';

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
        <a href="#" className="lp-logo" aria-label="UniOps home">
          <img
            className={`lp-logo-img ${theme === 'dark' ? 'lp-logo-img-dark' : 'lp-logo-img-light'}`}
            src={theme === 'dark' ? darkModeLogo : lightModeLogo}
            alt="UniOps"
          />
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

          <span className="lp-theme-shadow">
            <button
              className={`lp-theme-switch${theme === 'dark' ? ' is-active' : ''}`}
              onClick={toggleTheme}
              type="button"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              aria-pressed={theme === 'dark'}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              <img
                className="lp-theme-cloud lp-theme-cloud-two"
                src={cloudOne}
                alt=""
                aria-hidden="true"
              />
              <img
                className="lp-theme-cloud lp-theme-cloud-one"
                src={cloudTwo}
                alt=""
                aria-hidden="true"
              />
              <span className="lp-theme-inner" aria-hidden="true">
                <span className="lp-theme-globe">
                  <img
                    className="lp-theme-moon"
                    src={moon}
                    alt=""
                  />
                  <span className="lp-theme-globe-circle" />
                </span>
                <img
                  className="lp-theme-stars"
                  src={stars}
                  alt=""
                />
              </span>
            </button>
          </span>

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
