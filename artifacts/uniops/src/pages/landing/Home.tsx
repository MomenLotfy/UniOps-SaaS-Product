import './landing.css';
import { LandingProvider, useLanding } from './context/LandingContext';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Ticker from './components/Ticker';
import Metrics from './components/Metrics';
import Features from './components/Features';
import HowItWorks from './components/HowItWorks';
import CTA from './components/CTA';
import Footer from './components/Footer';

function Page() {
  const { theme } = useLanding();
  return (
    <div className="lp-root" data-theme={theme}>
      <div className="lp-orb lp-orb1"></div>
      <div className="lp-orb lp-orb2"></div>
      <Navbar />
      <Hero />
      <Ticker />
      <Metrics />
      <div className="lp-divider"></div>
      <Features />
      <div className="lp-divider"></div>
      <HowItWorks />
      <div className="lp-divider"></div>
      <CTA />
      <Footer />
    </div>
  );
}

export default function Home() {
  return (
    <LandingProvider>
      <Page />
    </LandingProvider>
  );
}
