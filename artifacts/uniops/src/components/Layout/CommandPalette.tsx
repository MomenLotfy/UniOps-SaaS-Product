import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  LayoutDashboard,
  Server,
  Shield,
  DollarSign,
  Brain,
  Command,
  Settings,
  FileText,
  Zap,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useStore } from '@/store';

interface CommandItem {
  id: string;
  title: string;
  description?: string;
  icon: React.ElementType;
  action: () => void;
  shortcut?: string;
  category: string;
}

export const CommandPalette = () => {
  const { commandPaletteOpen, setCommandPaletteOpen } = useStore();
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
      if (e.key === 'Escape') {
        setCommandPaletteOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [setCommandPaletteOpen]);

  useEffect(() => {
    if (!commandPaletteOpen) {
      setSearch('');
      setSelectedIndex(0);
    }
  }, [commandPaletteOpen]);

  const commands: CommandItem[] = [
    {
      id: 'command',
      title: 'Command Center',
      description: 'Unified operations overview',
      icon: LayoutDashboard,
      action: () => navigate('/command'),
      shortcut: '⌘1',
      category: 'Navigation',
    },
    {
      id: 'devops',
      title: 'DevOps Center',
      description: 'Pipelines, Kubernetes & deployments',
      icon: Server,
      action: () => navigate('/devops'),
      shortcut: '⌘2',
      category: 'Navigation',
    },
    {
      id: 'security',
      title: 'Security Center',
      description: 'Threats, vulnerabilities & compliance',
      icon: Shield,
      action: () => navigate('/security'),
      shortcut: '⌘3',
      category: 'Navigation',
    },
    {
      id: 'cost',
      title: 'Cost Center',
      description: 'Cloud cost analysis & optimization',
      icon: DollarSign,
      action: () => navigate('/cost'),
      shortcut: '⌘4',
      category: 'Navigation',
    },
    {
      id: 'insights',
      title: 'ML Insights',
      description: 'AI-powered pattern discovery',
      icon: Brain,
      action: () => navigate('/insights'),
      shortcut: '⌘5',
      category: 'Navigation',
    },
    {
      id: 'settings',
      title: 'Settings',
      description: 'Platform configuration',
      icon: Settings,
      action: () => {},
      category: 'General',
    },
    {
      id: 'docs',
      title: 'Documentation',
      description: 'Platform documentation & guides',
      icon: FileText,
      action: () => {},
      category: 'General',
    },
    {
      id: 'deploy',
      title: 'Trigger Deployment',
      description: 'Start a new deployment pipeline',
      icon: Zap,
      action: () => navigate('/devops'),
      shortcut: '⌘D',
      category: 'Actions',
    },
  ];

  const filtered = commands.filter(
    (c) =>
      c.title.toLowerCase().includes(search.toLowerCase()) ||
      c.description?.toLowerCase().includes(search.toLowerCase()) ||
      c.category.toLowerCase().includes(search.toLowerCase())
  );

  const categories = Array.from(new Set(filtered.map((c) => c.category)));

  const handleSelect = (item: CommandItem) => {
    item.action();
    setCommandPaletteOpen(false);
  };

  const allFiltered = filtered;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, allFiltered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && allFiltered[selectedIndex]) {
      handleSelect(allFiltered[selectedIndex]);
    }
  };

  let globalIndex = 0;

  return (
    <AnimatePresence>
      {commandPaletteOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm"
            onClick={() => setCommandPaletteOpen(false)}
          />
          <div className="fixed inset-0 z-[101] flex items-start justify-center pt-[15vh] pointer-events-none px-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -20 }}
              transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
              className="w-full max-w-xl pointer-events-auto rounded-xl border border-border shadow-2xl overflow-hidden"
              style={{ background: 'hsl(230 18% 8%)' }}
              onKeyDown={handleKeyDown}
            >
              {/* Search Input */}
              <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
                <Search className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <input
                  autoFocus
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setSelectedIndex(0);
                  }}
                  placeholder="Search commands, pages, actions..."
                  className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
                />
                <kbd className="text-xs px-1.5 py-0.5 rounded border border-border bg-accent font-mono text-muted-foreground">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div className="max-h-80 overflow-y-auto py-2">
                {filtered.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                    No results for &quot;{search}&quot;
                  </div>
                ) : (
                  categories.map((category) => {
                    const items = filtered.filter((c) => c.category === category);
                    return (
                      <div key={category}>
                        <div className="px-4 py-1.5">
                          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {category}
                          </span>
                        </div>
                        {items.map((item) => {
                          const isSelected = globalIndex === selectedIndex;
                          const idx = globalIndex++;
                          return (
                            <button
                              key={item.id}
                              onClick={() => handleSelect(item)}
                              onMouseEnter={() => setSelectedIndex(idx)}
                              className={clsx(
                                'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors',
                                isSelected ? 'bg-primary/10' : 'hover:bg-accent/50'
                              )}
                            >
                              <div className={clsx(
                                'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                                isSelected ? 'bg-primary/20' : 'bg-accent'
                              )}>
                                <item.icon className={clsx('w-4 h-4', isSelected ? 'text-primary' : 'text-muted-foreground')} />
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-foreground">{item.title}</div>
                                {item.description && (
                                  <div className="text-xs text-muted-foreground truncate">{item.description}</div>
                                )}
                              </div>
                              {item.shortcut && (
                                <span className="text-xs text-muted-foreground font-mono flex-shrink-0">
                                  {item.shortcut}
                                </span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    );
                  })
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center gap-4 px-4 py-2 border-t border-border">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <kbd className="px-1 py-0.5 rounded border border-border bg-accent font-mono text-xs">↑↓</kbd>
                  <span>navigate</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <kbd className="px-1 py-0.5 rounded border border-border bg-accent font-mono text-xs">↵</kbd>
                  <span>select</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <kbd className="px-1 py-0.5 rounded border border-border bg-accent font-mono text-xs">ESC</kbd>
                  <span>dismiss</span>
                </div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
};
