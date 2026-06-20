// ─────────────────────────────────────────────────────────────────────────────
// Section 2 — Platform Observability
// Sub-tabs: Observability | Alerts
// ─────────────────────────────────────────────────────────────────────────────

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Bell } from 'lucide-react';
import { clsx } from 'clsx';

import { ObservabilityTab } from './ObservabilityTab';
import { AlertsTab } from './AlertsTab';
import { useDevOpsIntegrations, usePods } from './hooks';

type ObsSection = 'observability' | 'alerts';

const SUB_TABS: { id: ObsSection; label: string; icon: React.ElementType }[] = [
  { id: 'observability', label: 'Observability', icon: Activity },
  { id: 'alerts',        label: 'Alerts',        icon: Bell     },
];

interface Props {
  showToast: (ok: boolean, msg: string) => void;
}

export function PlatformObservability({ showToast }: Props) {
  const [tab, setTab] = useState<ObsSection>('observability');
  const { k8sConnected } = useDevOpsIntegrations();
  const { pods } = usePods();

  return (
    <div>
      {/* Sub-tab bar */}
      <div
        className="flex gap-1 mb-5 p-1 rounded-xl"
        style={{ background: 'hsl(230 15% 10%)' }}
      >
        {SUB_TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              'flex items-center gap-1.5 px-4 py-2 text-xs rounded-lg transition-all font-medium',
              tab === t.id
                ? 'bg-white/8 text-white shadow-sm'
                : 'text-gray-500 hover:text-gray-300',
            )}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.18 }}
        >
          {tab === 'observability' && (
            <ObservabilityTab k8sConnected={k8sConnected} pods={pods} />
          )}
          {tab === 'alerts' && (
            <AlertsTab showToast={showToast} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
