import { useEffect, useMemo, useState } from 'react';
import { useLanding } from '../context/LandingContext';

function buildSparkPath(data: number[]) {
  const W = 255, H = 130;
  const mn = Math.min(...data), mx = Math.max(...data);
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - 10 - ((v - mn) / (mx - mn + 0.001)) * (H - 30);
    return [x, y];
  });
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join('');
  const area = line + `L${W},${H} L0,${H}Z`;
  return { line, area };
}

function DeployCard() {
  const data = Array.from({ length: 30 }, () => 0);
  const { line, area } = useMemo(() => buildSparkPath(data), [data]);
  const last = data[data.length - 1];
  return (
    <div className="lp-card lp-w2 lp-h1" style={{ padding: 0 }}>
      <div style={{ position: 'absolute', top: 10, left: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span className="lp-dot" style={{ background: '#4ade80' }}></span>
        <span className="lp-label">Deploy Frequency</span>
      </div>
      <svg width="255" height="130" style={{ display: 'block' }}>
        <defs>
          <linearGradient id="gSparkDeploy" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4ade80" stopOpacity=".25" />
            <stop offset="100%" stopColor="#4ade80" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#gSparkDeploy)" />
        <path d={line} fill="none" stroke="#4ade80" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="lp-val lp-green" style={{ position: 'absolute', bottom: 10, right: 12, fontSize: 18 }}>
        {last.toFixed(2)}<span style={{ fontSize: 11, fontWeight: 400, color: 'var(--lp-muted)', opacity: 1 }}>/day</span>
      </div>
    </div>
  );
}

function CICDCard() {
  return (
    <div className="lp-card lp-w1 lp-h1" style={{ padding: 12, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
      <span className="lp-label">CI/CD</span>
      <i className="ti ti-git-branch lp-blue" style={{ fontSize: 26 }}></i>
      <span style={{ fontSize: 11, color: 'var(--lp-muted)' }}>build #000</span>
      <span className="lp-badge lp-bg-green" style={{ marginTop: 2 }}>pass</span>
      <div className="lp-dot" style={{ background: '#4ade80', position: 'absolute', bottom: 10, right: 10 }}></div>
    </div>
  );
}

function CloudCostCard() {
  return (
    <div className="lp-card lp-w1 lp-h1" style={{ padding: 12, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 6 }}>
      <span className="lp-label">Cloud Cost</span>
      <div className="lp-val lp-amber">$0<span style={{ fontSize: 13, fontWeight: 400, opacity: .6 }}>.00</span></div>
      <div style={{ fontSize: 11 }}><span className="lp-red">↑ 0%</span> <span style={{ color: 'var(--lp-muted)', opacity: 1 }}>MTD</span></div>
      <div style={{ fontSize: 10, color: 'var(--lp-muted)', opacity: 1, marginTop: 2 }}>AWS $0 · GCP $0</div>
    </div>
  );
}

function ActiveTasksCard() {
  const p1 = 0;
  const p2 = 0;
  const p3 = 0;
  return (
    <div className="lp-card lp-w2 lp-h1" style={{ padding: '12px 14px' }}>
      <div className="lp-label" style={{ marginBottom: 8 }}>Active Tasks</div>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--lp-text)' }}>ML Training</span>
          <span className="lp-badge lp-bg-purple">{p1}%</span>
        </div>
        <div className="lp-prog-bg"><div className="lp-prog-fill" style={{ width: p1 + '%', background: 'linear-gradient(90deg,#007acc,#006db8)' }}></div></div>
      </div>
      <div style={{ marginTop: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--lp-text)' }}>Security Scan</span>
          <span className="lp-badge lp-bg-green">{p2}%</span>
        </div>
        <div className="lp-prog-bg"><div className="lp-prog-fill" style={{ width: p2 + '%', background: 'linear-gradient(90deg,#059669,#4ade80)' }}></div></div>
      </div>
      <div style={{ marginTop: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--lp-text)' }}>Model Serving</span>
          <span className="lp-badge lp-bg-amber">{p3}%</span>
        </div>
        <div className="lp-prog-bg"><div className="lp-prog-fill" style={{ width: p3 + '%', background: 'linear-gradient(90deg,#b45309,#fbbf24)' }}></div></div>
      </div>
    </div>
  );
}

function ThemeModeCard() {
  const { theme, toggleTheme } = useLanding();
  const isLight = theme === 'light';
  return (
    <div className="lp-card lp-w1 lp-h1" style={{ padding: 12, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', gap: 6 }}>
      <div style={{ fontSize: 26, transition: 'all .35s' }}>{isLight ? '☀️' : '🌙'}</div>
      <span className="lp-label" style={{ marginTop: 2 }}>Theme Mode</span>
      <button
        onClick={toggleTheme}
        style={{ marginTop: 4, borderRadius: 99, padding: '2px 12px', fontSize: 11, fontWeight: 600, cursor: 'pointer', transition: 'all .35s', background: isLight ? 'rgba(251,191,36,.1)' : 'rgba(0,122,204,.1)', border: `1px solid ${isLight ? 'rgba(251,191,36,.35)' : 'rgba(0,122,204,.35)'}`, color: isLight ? '#b77900' : '#007acc' }}>
        {isLight ? 'LIGHT' : 'DARK'}
      </button>
    </div>
  );
}

function MLServingCard() {
  const lat = 0;
  return (
    <div className="lp-card lp-w1 lp-h1" style={{ padding: 12, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', gap: 2 }}>
      <span className="lp-label">ML Serving</span>
      <i className="ti ti-cpu lp-purple" style={{ fontSize: 26, margin: '2px 0' }}></i>
      <div className="lp-val lp-purple" style={{ fontSize: 18 }}>{lat}<span style={{ fontSize: 11, fontWeight: 400, color: 'var(--lp-muted)', opacity: 1 }}>ms</span></div>
      <span style={{ fontSize: 10, color: 'var(--lp-muted)', opacity: 1 }}>P0 latency</span>
      <div className="lp-dot" style={{ background: '#4ade80', position: 'absolute', bottom: 10, right: 10 }}></div>
    </div>
  );
}

function ClockCard() {
  const time = '00:00:00';
  const date = 'Day 00';
  return (
    <div className="lp-card lp-w1 lp-h1" style={{ padding: 12, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', gap: 4 }}>
      <span className="lp-val" style={{ fontSize: 20, letterSpacing: '-1px' }}>{time}</span>
      <span className="lp-sub">{date}</span>
    </div>
  );
}

const ALERTS = [
  { cls: 'lp-bg-red', txt: 'CPU spike · node-00' },
  { cls: 'lp-bg-amber', txt: 'Redis memory 0%' },
  { cls: 'lp-bg-blue', txt: 'Deploy #000 started' },
  { cls: 'lp-bg-green', txt: 'ML model v0.0 ready' },
  { cls: 'lp-bg-purple', txt: 'Scan scheduled' },
];

function AlertsCard() {
  const [ai, setAi] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setAi((v) => v + 1), 3500);
    return () => clearInterval(id);
  }, []);
  const visible = [ALERTS[ai % 5], ALERTS[(ai + 1) % 5]];
  return (
    <div className="lp-card lp-w2 lp-h1" style={{ padding: '12px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span className="lp-label">Live Alerts</span>
        <div className="lp-dot" style={{ background: '#f87171' }}></div>
      </div>
      <div>
        {visible.map((x, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', borderBottom: '1px solid var(--lp-border)' }}>
            <span className={`lp-badge ${x.cls}`} style={{ flexShrink: 0, fontSize: 9 }}>!</span>
            <span style={{ fontSize: 11, color: 'var(--lp-text)', opacity: 1 }}>{x.txt}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HeroWidgets() {
  return (
    <div className="lp-hero-visual">
      <div className="lp-panel-glow"></div>
      <div className="lp-wrap">
        <DeployCard />
        <CICDCard />
        <CloudCostCard />
        <ActiveTasksCard />
        <ThemeModeCard />
        <MLServingCard />
        <ClockCard />
        <AlertsCard />
      </div>
    </div>
  );
}
