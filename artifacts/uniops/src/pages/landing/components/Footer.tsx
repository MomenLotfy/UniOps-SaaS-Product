import { useLanding } from '../context/LandingContext';

export default function Footer() {
  const { t } = useLanding();
  return (
    <footer className="lp-footer">
      <div className="lp-foot-in">
        <div>
          <a href="#" className="lp-logo" style={{ marginBottom: '.3rem', display: 'inline-flex' }}>
            <div className="lp-logo-box" style={{ width: 26, height: 26, borderRadius: 6 }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5" />
                <line x1="12" y1="22" x2="12" y2="15.5" />
                <polyline points="22 8.5 12 15.5 2 8.5" />
              </svg>
            </div>
            <span className="lp-logo-name" style={{ fontSize: '1rem' }}>UniOps</span>
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
