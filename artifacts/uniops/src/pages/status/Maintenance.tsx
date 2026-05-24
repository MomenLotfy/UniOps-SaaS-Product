import { Wrench, Clock } from 'lucide-react';

export default function Maintenance() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'hsl(230 20% 4%)' }}>
      <div className="text-center space-y-4">
        <div className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'hsl(220 90% 60% / 0.1)' }}>
          <Wrench className="w-10 h-10 text-blue-400" />
        </div>
        <div className="text-xl font-bold text-white">Scheduled Maintenance</div>
        <p className="text-sm max-w-sm" style={{ color: 'hsl(215 16% 57%)' }}>UniOps is undergoing scheduled maintenance to improve your experience. We'll be back shortly.</p>
        <div className="flex items-center justify-center gap-2 text-sm" style={{ color: 'hsl(215 16% 57%)' }}>
          <Clock className="w-4 h-4" />
          <span>Estimated downtime: 30 minutes</span>
        </div>
        <div className="w-64 mx-auto">
          <div className="progress-bar-base h-2">
            <div className="h-full rounded-full bg-blue-500" style={{ width: '65%', animation: 'pulse 2s infinite' }} />
          </div>
        </div>
      </div>
    </div>
  );
}
