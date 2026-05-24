import { clsx } from 'clsx';

interface UsageMeterProps {
  label: string;
  used: number;
  limit: number;
  unit?: string;
  formatter?: (n: number) => string;
  showNumbers?: boolean;
}

export function UsageMeter({ label, used, limit, unit = '', formatter, showNumbers = true }: UsageMeterProps) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const isUnlimited = limit >= 999_999;
  const isCritical = pct >= 90;
  const isWarning = pct >= 75;

  const fmt = formatter ?? ((n: number) => n.toLocaleString());

  const barColor = isCritical ? 'bg-red-500' : isWarning ? 'bg-yellow-400' : 'bg-blue-500';
  const textColor = isCritical ? 'text-red-400' : isWarning ? 'text-yellow-400' : 'text-muted-foreground';

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-foreground">{label}</span>
        {showNumbers && (
          <span className={clsx('text-xs font-medium', textColor)}>
            {fmt(used)}{unit} / {isUnlimited ? '∞' : `${fmt(limit)}${unit}`}
          </span>
        )}
      </div>
      <div className="h-2 rounded-full overflow-hidden bg-muted/30">
        {isUnlimited ? (
          <div className="h-full w-full bg-green-500/20" />
        ) : (
          <div
            className={clsx('h-full rounded-full transition-all duration-500', barColor)}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      {!isUnlimited && (
        <p className={clsx('text-xs', isCritical ? 'text-red-400' : isWarning ? 'text-yellow-400' : 'text-muted-foreground')}>
          {isUnlimited ? 'Unlimited' : `${pct.toFixed(0)}% used`}
          {isCritical && ' — Consider upgrading your plan'}
        </p>
      )}
    </div>
  );
}
