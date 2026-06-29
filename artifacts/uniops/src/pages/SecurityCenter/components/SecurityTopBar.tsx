import { memo, useState } from 'react';
import {
  Shield, Search, RefreshCw, Download, SlidersHorizontal,
  ChevronDown, Calendar, Menu,
} from 'lucide-react';
import { clsx } from 'clsx';

interface SecurityTopBarProps {
  activeLabel: string;
  onMobileMenuOpen: () => void;
  onRefresh: () => void;
}

const BORDER = 'hsl(230 15% 16%)';
const BG     = 'hsl(230 15% 8%)';

function Selector({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <button
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors hover:border-blue-500/40 hover:bg-white/5"
      style={{ borderColor: BORDER, color: 'hsl(215 16% 65%)' }}
    >
      <span className="text-[10px] font-medium uppercase tracking-wide opacity-50">{label}</span>
      <span className="font-medium" style={{ color: 'hsl(215 16% 85%)' }}>{value}</span>
      <ChevronDown className="w-3 h-3 opacity-50" />
    </button>
  );
}

const TIME_RANGES = ['1h', '6h', '24h', '7d', '30d', '90d'];

function SecurityTopBar({ activeLabel, onMobileMenuOpen, onRefresh }: SecurityTopBarProps) {
  const [search, setSearch]       = useState('');
  const [timeRange, setTimeRange] = useState('24h');

  return (
    <header
      className="flex-shrink-0 border-b flex flex-col"
      style={{ borderColor: BORDER, background: BG }}
    >
      {/* Top row */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b" style={{ borderColor: BORDER }}>
        {/* Mobile menu */}
        <button
          onClick={onMobileMenuOpen}
          className="lg:hidden text-muted-foreground hover:text-foreground mr-1"
        >
          <Menu className="w-4 h-4" />
        </button>

        {/* Brand */}
        <div className="flex items-center gap-2 mr-3">
          <div className="w-6 h-6 rounded bg-red-500/20 flex items-center justify-center">
            <Shield className="w-3.5 h-3.5 text-red-400" />
          </div>
          <span className="text-sm font-semibold text-foreground hidden sm:block">Security Center</span>
          <span className="text-muted-foreground hidden sm:block">/</span>
          <span className="text-sm text-muted-foreground hidden sm:block">{activeLabel}</span>
        </div>

        {/* Selectors */}
        <div className="hidden md:flex items-center gap-1.5 flex-wrap">
          <Selector label="Workspace" value="Production" />
          <Selector label="Repository" value="All Repos" />
          <Selector label="Cloud" value="All Clouds" />
          <Selector label="Environment" value="All Envs" />
        </div>

        {/* Right actions */}
        <div className="ml-auto flex items-center gap-1.5">
          {/* Search */}
          <div className="relative hidden sm:block">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search findings…"
              className="pl-8 pr-3 py-1.5 text-xs rounded-md border outline-none focus:border-blue-500/50 w-48 transition-all focus:w-64 bg-transparent"
              style={{ borderColor: BORDER, color: 'hsl(215 16% 80%)' }}
            />
          </div>

          {/* Time range */}
          <div
            className="hidden sm:flex items-center gap-1 px-2 py-1.5 rounded-md border text-xs"
            style={{ borderColor: BORDER }}
          >
            <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
            {TIME_RANGES.map(t => (
              <button
                key={t}
                onClick={() => setTimeRange(t)}
                className={clsx(
                  'px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors',
                  timeRange === t
                    ? 'bg-blue-600/30 text-blue-400'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Filters */}
          <button
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: BORDER }}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Filters</span>
          </button>

          {/* Export */}
          <button
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: BORDER }}
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export</span>
          </button>

          {/* Refresh */}
          <button
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs text-muted-foreground hover:text-foreground transition-colors"
            style={{ borderColor: BORDER }}
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>
  );
}

export default memo(SecurityTopBar);
