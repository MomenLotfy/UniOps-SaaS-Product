import { motion } from 'framer-motion';
import { Monitor, Sun, Moon, Check } from 'lucide-react';
import { useTheme, type Theme } from '@/contexts/ThemeContext';
import { clsx } from 'clsx';

const themes: { value: Theme; label: string; icon: React.ElementType; desc: string }[] = [
  { value: 'dark', label: 'Dark', icon: Moon, desc: 'Optimized for low-light environments' },
  { value: 'light', label: 'Light', icon: Sun, desc: 'Clean and bright interface' },
  { value: 'system', label: 'System', icon: Monitor, desc: 'Follows your OS preference' },
];

const ACCENT_COLORS = [
  { name: 'Blue', value: '220 90% 60%' },
  { name: 'Purple', value: '260 70% 60%' },
  { name: 'Cyan', value: '190 90% 50%' },
  { name: 'Green', value: '160 84% 39%' },
  { name: 'Orange', value: '25 90% 55%' },
];

const DENSITY = ['Compact', 'Default', 'Comfortable'];

export default function Appearance() {
  const { theme, setTheme } = useTheme();

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      <div className="page-header">
        <div>
          <h1 className="page-title">Appearance</h1>
          <p className="page-subtitle">Customize the look and feel of UniOps</p>
        </div>
      </div>

      {/* Theme */}
      <div className="card-base">
        <h2 className="text-sm font-semibold text-foreground mb-4">Color Theme</h2>
        <div className="grid grid-cols-3 gap-3">
          {themes.map((t) => (
            <button key={t.value} onClick={() => setTheme(t.value)}
              className={clsx('p-4 rounded-xl border-2 transition-all text-left', theme === t.value ? 'border-blue-500' : 'border-border hover:border-muted-foreground')}
              style={{ background: theme === t.value ? 'hsl(220 90% 60% / 0.08)' : 'hsl(230 18% 9%)' }}>
              <div className="flex items-center justify-between mb-2">
                <t.icon className={clsx('w-5 h-5', theme === t.value ? 'text-blue-400' : 'text-muted-foreground')} />
                {theme === t.value && <Check className="w-4 h-4 text-blue-400" />}
              </div>
              <div className={clsx('text-sm font-semibold', theme === t.value ? 'text-foreground' : 'text-muted-foreground')}>{t.label}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{t.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Accent color */}
      <div className="card-base">
        <h2 className="text-sm font-semibold text-foreground mb-4">Accent Color</h2>
        <div className="flex items-center gap-3">
          {ACCENT_COLORS.map((c) => (
            <button key={c.name} title={c.name}
              className="w-8 h-8 rounded-full border-2 border-transparent hover:scale-110 transition-all focus:border-white"
              style={{ background: `hsl(${c.value})` }} />
          ))}
        </div>
      </div>

      {/* Density */}
      <div className="card-base">
        <h2 className="text-sm font-semibold text-foreground mb-4">Information Density</h2>
        <div className="flex gap-2">
          {DENSITY.map((d) => (
            <button key={d}
              className={clsx('px-4 py-2 rounded-lg text-sm font-medium border transition-all', d === 'Default' ? 'border-blue-500 text-blue-400 bg-blue-500/10' : 'border-border text-muted-foreground hover:border-muted-foreground')}>
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Font */}
      <div className="card-base">
        <h2 className="text-sm font-semibold text-foreground mb-4">Interface Font</h2>
        <div className="grid grid-cols-2 gap-3">
          {['Inter (Default)', 'System UI'].map((f) => (
            <button key={f}
              className={clsx('p-3 rounded-lg border text-left transition-all', f.includes('Default') ? 'border-blue-500 bg-blue-500/08' : 'border-border hover:border-muted-foreground')}
              style={{ background: f.includes('Default') ? 'hsl(220 90% 60% / 0.06)' : 'hsl(230 18% 9%)' }}>
              <div className="text-sm font-semibold text-foreground">{f}</div>
              <div className="text-xs text-muted-foreground mt-1" style={{ fontFamily: f.includes('System') ? 'system-ui' : 'Inter' }}>
                The quick brown fox jumps over the lazy dog
              </div>
            </button>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
