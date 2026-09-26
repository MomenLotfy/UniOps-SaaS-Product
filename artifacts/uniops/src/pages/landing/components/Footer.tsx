import { useLanding } from '../context/LandingContext';
import darkModeLogo from '../../../assets/logo-darkmode.svg';
import lightModeLogo from '../../../assets/logo-lightmode.svg';

export default function Footer() {
  const { theme, t } = useLanding();
  return (
    <footer className="lp-footer">
      <div className="lp-foot-in">
        <div>
          <a href="#" className="lp-logo lp-footer-logo" aria-label="UniOps home">
            <img
              className={`lp-logo-img ${theme === 'dark' ? 'lp-logo-img-dark' : 'lp-logo-img-light'}`}
              src={theme === 'dark' ? darkModeLogo : lightModeLogo}
              alt="UniOps"
            />
          </a>
          <div className="lp-foot-copy">{t('foot_copy')}</div>
        </div>
        <div className="lp-foot-links">
          <a href="#">{t('foot_privacy')}</a>
          <a href="#">{t('foot_terms')}</a>
          <a href="#">{t('foot_contact')}</a>
        </div>
      </div>
    </footer>
  );
}
