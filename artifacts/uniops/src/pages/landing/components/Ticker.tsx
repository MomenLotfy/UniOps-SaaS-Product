const ITEMS = [
  { color: '#4ade80', label: 'Real-time Monitoring' },
  { color: '#60a5fa', label: 'Kubernetes Orchestration' },
  { color: '#f87171', label: 'Security Vulnerability Scan' },
  { color: '#fbbf24', label: 'Cloud Cost Intelligence' },
  { color: '#c084fc', label: 'AI-Powered Root Cause Analysis' },
  { color: '#2dd4bf', label: 'CI/CD Pipeline Automation' },
];

export default function Ticker() {
  const doubled = [...ITEMS, ...ITEMS];
  return (
    <div className="lp-ticker-wrap">
      <div className="lp-ticker">
        {doubled.map((item, i) => (
          <span className="lp-tick-item" key={i}>
            <span className="lp-td" style={{ background: item.color }}></span>
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
