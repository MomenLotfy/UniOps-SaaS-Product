// ─────────────────────────────────────────────────────────────────────────────
// Section 4 — Self-Service Catalog (Epic 6)
// Service cards + 6-step Create Wizard
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback, useId } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus, Search, Package, Database, Cpu, MessageSquare,
  Globe, CheckCircle2, ArrowRight, ArrowLeft, X, Tag,
  GitBranch, Server, Layers, Zap, Clock, RefreshCw,
  ChevronDown, ExternalLink,
} from 'lucide-react';
import { clsx } from 'clsx';
import type { CatalogService, ServiceType, TechStack, CreateServicePayload } from './types';

// ── Mock seed data ─────────────────────────────────────────────────────────────
const SEED_SERVICES: CatalogService[] = [
  {
    id: 'svc-001', name: 'api-gateway', type: 'Gateway', status: 'Running',
    tech_stack: 'Node.js', cluster: 'prod-eks', namespace: 'platform',
    git_repo: 'github.com/acme/api-gateway', last_deployment: '2025-06-19T14:22:00Z',
    replicas: 3, created_at: '2025-01-10T08:00:00Z', owner: 'platform-team',
    description: 'Main API gateway routing traffic to downstream services.',
    tags: ['gateway', 'ingress', 'platform'],
  },
  {
    id: 'svc-002', name: 'user-service', type: 'Microservice', status: 'Running',
    tech_stack: 'Go', cluster: 'prod-eks', namespace: 'backend',
    git_repo: 'github.com/acme/user-service', last_deployment: '2025-06-18T09:10:00Z',
    replicas: 2, created_at: '2025-02-05T10:00:00Z', owner: 'backend-team',
    description: 'Handles user authentication, profiles, and preferences.',
    tags: ['auth', 'users'],
  },
  {
    id: 'svc-003', name: 'postgres-primary', type: 'Database', status: 'Running',
    tech_stack: 'Other', cluster: 'prod-eks', namespace: 'data',
    git_repo: '', last_deployment: '2025-05-01T06:00:00Z',
    replicas: 1, created_at: '2025-01-01T00:00:00Z', owner: 'data-team',
    description: 'Primary PostgreSQL database cluster.',
    tags: ['postgres', 'database', 'stateful'],
  },
  {
    id: 'svc-004', name: 'notification-worker', type: 'Worker', status: 'Running',
    tech_stack: 'Python', cluster: 'staging-eks', namespace: 'workers',
    git_repo: 'github.com/acme/notification-worker', last_deployment: '2025-06-17T11:00:00Z',
    replicas: 1, created_at: '2025-03-12T12:00:00Z', owner: 'platform-team',
    description: 'Background worker for sending email and SMS notifications.',
    tags: ['worker', 'notifications'],
  },
  {
    id: 'svc-005', name: 'event-queue', type: 'Queue', status: 'Running',
    tech_stack: 'Other', cluster: 'prod-eks', namespace: 'messaging',
    git_repo: '', last_deployment: '2025-04-20T08:00:00Z',
    replicas: 3, created_at: '2025-01-15T08:00:00Z', owner: 'platform-team',
    description: 'RabbitMQ event queue for async service communication.',
    tags: ['queue', 'messaging', 'rabbitmq'],
  },
  {
    id: 'svc-006', name: 'analytics-service', type: 'Microservice', status: 'Deploying',
    tech_stack: 'FastAPI', cluster: 'staging-eks', namespace: 'analytics',
    git_repo: 'github.com/acme/analytics', last_deployment: '2025-06-20T07:30:00Z',
    replicas: 2, created_at: '2025-05-20T14:00:00Z', owner: 'data-team',
    description: 'ClickHouse-backed analytics ingestion and query service.',
    tags: ['analytics', 'clickhouse', 'data'],
  },
];

// ── Style maps ─────────────────────────────────────────────────────────────────
const TYPE_ICONS: Record<ServiceType, React.ElementType> = {
  Microservice: Cpu,
  Database:     Database,
  Worker:       Zap,
  Queue:        MessageSquare,
  Gateway:      Globe,
};

const TYPE_COLOR: Record<ServiceType, string> = {
  Microservice: 'text-blue-400 bg-blue-500/10',
  Database:     'text-emerald-400 bg-emerald-500/10',
  Worker:       'text-yellow-400 bg-yellow-500/10',
  Queue:        'text-purple-400 bg-purple-500/10',
  Gateway:      'text-cyan-400 bg-cyan-500/10',
};

const STATUS_COLOR: Record<string, string> = {
  Running:   'text-green-400 bg-green-500/10',
  Failed:    'text-red-400 bg-red-500/10',
  Deploying: 'text-blue-400 bg-blue-500/10 animate-pulse',
  Pending:   'text-yellow-400 bg-yellow-500/10',
  Stopped:   'text-gray-400 bg-gray-500/10',
};

const STATUS_DOT: Record<string, string> = {
  Running:   'bg-green-400',
  Failed:    'bg-red-400',
  Deploying: 'bg-blue-400 animate-pulse',
  Pending:   'bg-yellow-400',
  Stopped:   'bg-gray-400',
};

// ── Constants ──────────────────────────────────────────────────────────────────
const SERVICE_TYPES: ServiceType[] = ['Microservice', 'Database', 'Worker', 'Queue', 'Gateway'];
const TECH_STACKS: TechStack[] = [
  'Node.js', 'Python', 'Go', 'Java', 'Rust', 'React', 'Next.js', 'FastAPI', 'Django', 'Spring Boot', 'Other',
];
const CLUSTERS = ['prod-eks', 'staging-eks', 'dev-cluster', 'on-prem-k8s'];
const NAMESPACES = ['default', 'platform', 'backend', 'data', 'workers', 'messaging', 'analytics', 'monitoring'];

// ── Wizard steps ───────────────────────────────────────────────────────────────
const WIZARD_STEPS = [
  { label: 'Service Type',  description: 'Choose what to deploy' },
  { label: 'Basic Info',    description: 'Name & description'    },
  { label: 'Source Code',   description: 'Git repo & stack'      },
  { label: 'Target',        description: 'Cluster & namespace'   },
  { label: 'Scaling',       description: 'Replicas & resources'  },
  { label: 'Review',        description: 'Confirm & deploy'      },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtTime(iso?: string) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function fmtAge(iso: string) {
  const ms = Date.now() - new Date(iso).getTime();
  const d = Math.floor(ms / 86400000);
  if (d > 0) return `${d}d`;
  const h = Math.floor(ms / 3600000);
  if (h > 0) return `${h}h`;
  return `${Math.floor(ms / 60000)}m`;
}

// ── Service Card ──────────────────────────────────────────────────────────────
function ServiceCard({ svc, onClick }: { svc: CatalogService; onClick: () => void }) {
  const Icon = TYPE_ICONS[svc.type] ?? Package;
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.15 }}
      className="w-full text-left rounded-xl border p-4 transition-colors hover:border-white/15 group"
      style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0', TYPE_COLOR[svc.type])}>
            <Icon className="w-4 h-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white group-hover:text-blue-300 transition-colors">
              {svc.name}
            </p>
            <p className="text-xs text-gray-500">{svc.namespace} / {svc.cluster}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', STATUS_DOT[svc.status])} />
          <span className={clsx('px-2 py-0.5 rounded text-xs font-medium', STATUS_COLOR[svc.status])}>
            {svc.status}
          </span>
        </div>
      </div>

      {svc.description && (
        <p className="text-xs text-gray-500 mb-3 line-clamp-2">{svc.description}</p>
      )}

      <div className="flex items-center gap-3 text-xs text-gray-600">
        <div className="flex items-center gap-1">
          <Layers className="w-3 h-3" />
          <span>{svc.replicas} replica{svc.replicas !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-1">
          <Cpu className="w-3 h-3" />
          <span>{svc.tech_stack}</span>
        </div>
        {svc.last_deployment && (
          <div className="flex items-center gap-1 ml-auto">
            <Clock className="w-3 h-3" />
            <span>{fmtTime(svc.last_deployment)}</span>
          </div>
        )}
      </div>

      {svc.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {svc.tags.slice(0, 4).map(t => (
            <span key={t} className="px-1.5 py-0.5 rounded text-xs bg-white/5 text-gray-500">
              {t}
            </span>
          ))}
          {svc.tags.length > 4 && (
            <span className="px-1.5 py-0.5 rounded text-xs bg-white/5 text-gray-600">
              +{svc.tags.length - 4}
            </span>
          )}
        </div>
      )}
    </motion.button>
  );
}

// ── Service Detail Drawer ─────────────────────────────────────────────────────
function ServiceDetail({ svc, onClose }: { svc: CatalogService; onClose: () => void }) {
  const Icon = TYPE_ICONS[svc.type] ?? Package;
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 20 }}
        transition={{ duration: 0.2 }}
        className="w-full max-w-lg rounded-2xl border p-6"
        style={{ background: 'hsl(230 15% 11%)', borderColor: 'hsl(230 15% 20%)' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center', TYPE_COLOR[svc.type])}>
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">{svc.name}</h3>
              <p className="text-xs text-gray-500">{svc.type} · {svc.tech_stack}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {svc.description && (
          <p className="text-sm text-gray-400 mb-5">{svc.description}</p>
        )}

        <div className="grid grid-cols-2 gap-3 mb-5">
          {[
            { label: 'Cluster',    value: svc.cluster },
            { label: 'Namespace',  value: svc.namespace },
            { label: 'Replicas',   value: String(svc.replicas) },
            { label: 'Status',     value: svc.status },
            { label: 'Owner',      value: svc.owner ?? '—' },
            { label: 'Age',        value: fmtAge(svc.created_at) },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-lg p-3"
              style={{ background: 'hsl(230 15% 8%)', border: '1px solid hsl(230 15% 15%)' }}>
              <p className="text-xs text-gray-500 mb-1">{label}</p>
              <p className="text-sm font-medium text-white">{value}</p>
            </div>
          ))}
        </div>

        {svc.git_repo && (
          <a
            href={`https://${svc.git_repo}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 mb-4 transition-colors"
          >
            <GitBranch className="w-3.5 h-3.5" />
            {svc.git_repo}
            <ExternalLink className="w-3 h-3" />
          </a>
        )}

        <div className="text-xs text-gray-500">
          Last deployed: <span className="text-gray-300">{fmtTime(svc.last_deployment)}</span>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ── Create Wizard ─────────────────────────────────────────────────────────────
const EMPTY_PAYLOAD: CreateServicePayload = {
  name: '', type: 'Microservice', tech_stack: 'Node.js',
  git_repo: '', cluster: CLUSTERS[0], namespace: NAMESPACES[0],
  replicas: 1, description: '', tags: [],
};

function CreateWizard({ onClose, onCreate }: {
  onClose: () => void;
  onCreate: (svc: CatalogService) => void;
}) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<CreateServicePayload>(EMPTY_PAYLOAD);
  const [tagInput, setTagInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const uid = useId();

  const set = useCallback(<K extends keyof CreateServicePayload>(key: K, val: CreateServicePayload[K]) => {
    setForm(f => ({ ...f, [key]: val }));
  }, []);

  const addTag = useCallback(() => {
    const t = tagInput.trim().toLowerCase().replace(/\s+/g, '-');
    if (t && !form.tags.includes(t)) set('tags', [...form.tags, t]);
    setTagInput('');
  }, [tagInput, form.tags, set]);

  const removeTag = useCallback((t: string) => {
    set('tags', form.tags.filter(x => x !== t));
  }, [form.tags, set]);

  const canNext: boolean = (() => {
    if (step === 0) return !!form.type;
    if (step === 1) return form.name.trim().length >= 2;
    if (step === 2) return !!form.tech_stack;
    if (step === 3) return !!(form.cluster && form.namespace);
    if (step === 4) return form.replicas >= 1;
    return true;
  })();

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    await new Promise(r => setTimeout(r, 900));
    const now = new Date().toISOString();
    const svc: CatalogService = {
      id:    `svc-${Date.now()}`,
      ...form,
      status:          'Deploying',
      created_at:      now,
      last_deployment: now,
    };
    onCreate(svc);
    setSubmitting(false);
  }, [form, onCreate]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)' }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 24 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 24 }}
        transition={{ duration: 0.22 }}
        className="w-full max-w-lg rounded-2xl border flex flex-col"
        style={{
          background: 'hsl(230 15% 11%)',
          borderColor: 'hsl(230 15% 20%)',
          maxHeight: '90vh',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b flex-shrink-0"
          style={{ borderColor: 'hsl(230 15% 18%)' }}>
          <div>
            <h2 className="text-base font-bold text-white">Create Service</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Step {step + 1} of {WIZARD_STEPS.length} — {WIZARD_STEPS[step].description}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Progress */}
        <div className="px-6 pt-4 flex-shrink-0">
          <div className="flex items-center gap-2 mb-1">
            {WIZARD_STEPS.map((s, i) => (
              <div key={i} className="flex-1">
                <div className={clsx('h-1 rounded-full transition-all',
                  i <= step ? 'bg-blue-500' : 'bg-white/8')} />
              </div>
            ))}
          </div>
          <div className="flex justify-between text-xs text-gray-600 mt-1">
            {WIZARD_STEPS.map((s, i) => (
              <span key={i} className={clsx(i === step && 'text-blue-400 font-medium')}>
                {s.label}
              </span>
            ))}
          </div>
        </div>

        {/* Step content */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.18 }}
            >

              {/* Step 0 — Service Type */}
              {step === 0 && (
                <div className="grid grid-cols-2 gap-3">
                  {SERVICE_TYPES.map(type => {
                    const Icon = TYPE_ICONS[type];
                    const active = form.type === type;
                    return (
                      <button
                        key={type}
                        onClick={() => set('type', type)}
                        className={clsx(
                          'flex flex-col items-center gap-2.5 p-4 rounded-xl border text-sm font-medium transition-all',
                          active
                            ? 'border-blue-500 bg-blue-500/10 text-blue-300'
                            : 'border-white/8 text-gray-400 hover:border-white/15 hover:text-white',
                        )}
                      >
                        <Icon className="w-6 h-6" />
                        {type}
                        {active && <CheckCircle2 className="w-4 h-4 text-blue-400" />}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Step 1 — Basic Info */}
              {step === 1 && (
                <div className="space-y-4">
                  <div>
                    <label htmlFor={`${uid}-name`} className="block text-xs font-medium text-gray-300 mb-1.5">
                      Service Name <span className="text-red-400">*</span>
                    </label>
                    <input
                      id={`${uid}-name`}
                      value={form.name}
                      onChange={e => set('name', e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))}
                      placeholder="my-service"
                      className="w-full px-3 py-2.5 rounded-lg text-sm text-white placeholder-gray-600 border outline-none focus:border-blue-500 transition-colors"
                      style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 20%)' }}
                    />
                    <p className="text-xs text-gray-600 mt-1">Lowercase letters, numbers, and hyphens only.</p>
                  </div>
                  <div>
                    <label htmlFor={`${uid}-desc`} className="block text-xs font-medium text-gray-300 mb-1.5">
                      Description
                    </label>
                    <textarea
                      id={`${uid}-desc`}
                      value={form.description}
                      onChange={e => set('description', e.target.value)}
                      rows={3}
                      placeholder="What does this service do?"
                      className="w-full px-3 py-2.5 rounded-lg text-sm text-white placeholder-gray-600 border outline-none focus:border-blue-500 transition-colors resize-none"
                      style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 20%)' }}
                    />
                  </div>
                </div>
              )}

              {/* Step 2 — Source Code */}
              {step === 2 && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-300 mb-2">
                      Tech Stack <span className="text-red-400">*</span>
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {TECH_STACKS.map(ts => (
                        <button
                          key={ts}
                          onClick={() => set('tech_stack', ts)}
                          className={clsx(
                            'px-2 py-2 rounded-lg border text-xs font-medium transition-all',
                            form.tech_stack === ts
                              ? 'border-blue-500 bg-blue-500/10 text-blue-300'
                              : 'border-white/8 text-gray-400 hover:border-white/15 hover:text-white',
                          )}
                        >
                          {ts}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label htmlFor={`${uid}-repo`} className="block text-xs font-medium text-gray-300 mb-1.5">
                      Git Repository
                    </label>
                    <div className="relative">
                      <GitBranch className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
                      <input
                        id={`${uid}-repo`}
                        value={form.git_repo}
                        onChange={e => set('git_repo', e.target.value)}
                        placeholder="github.com/org/repo"
                        className="w-full pl-9 pr-3 py-2.5 rounded-lg text-sm text-white placeholder-gray-600 border outline-none focus:border-blue-500 transition-colors"
                        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 20%)' }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Step 3 — Target */}
              {step === 3 && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-300 mb-1.5">
                      Cluster <span className="text-red-400">*</span>
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      {CLUSTERS.map(c => (
                        <button key={c} onClick={() => set('cluster', c)}
                          className={clsx('flex items-center gap-2 px-3 py-2.5 rounded-lg border text-xs font-medium transition-all text-left',
                            form.cluster === c
                              ? 'border-blue-500 bg-blue-500/10 text-blue-300'
                              : 'border-white/8 text-gray-400 hover:border-white/15 hover:text-white')}>
                          <Server className="w-3.5 h-3.5 flex-shrink-0" />
                          {c}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-300 mb-1.5">
                      Namespace <span className="text-red-400">*</span>
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {NAMESPACES.map(ns => (
                        <button key={ns} onClick={() => set('namespace', ns)}
                          className={clsx('px-2 py-2 rounded-lg border text-xs font-medium transition-all',
                            form.namespace === ns
                              ? 'border-blue-500 bg-blue-500/10 text-blue-300'
                              : 'border-white/8 text-gray-400 hover:border-white/15 hover:text-white')}>
                          {ns}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Step 4 — Scaling */}
              {step === 4 && (
                <div className="space-y-5">
                  <div>
                    <label className="block text-xs font-medium text-gray-300 mb-2">
                      Replicas
                    </label>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => set('replicas', Math.max(1, form.replicas - 1))}
                        className="w-9 h-9 rounded-lg border text-white text-lg font-bold transition-colors hover:border-white/25"
                        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 20%)' }}
                      >
                        −
                      </button>
                      <div className="flex-1 text-center">
                        <span className="text-3xl font-bold text-white">{form.replicas}</span>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {form.replicas === 1 ? 'No redundancy' : form.replicas >= 3 ? 'High availability' : 'Basic redundancy'}
                        </p>
                      </div>
                      <button
                        onClick={() => set('replicas', Math.min(20, form.replicas + 1))}
                        className="w-9 h-9 rounded-lg border text-white text-lg font-bold transition-colors hover:border-white/25"
                        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 20%)' }}
                      >
                        +
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-300 mb-1.5">
                      Tags
                    </label>
                    <div className="flex gap-2 mb-2">
                      <input
                        value={tagInput}
                        onChange={e => setTagInput(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                        placeholder="Add tag…"
                        className="flex-1 px-3 py-2 rounded-lg text-sm text-white placeholder-gray-600 border outline-none focus:border-blue-500 transition-colors"
                        style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 20%)' }}
                      />
                      <button onClick={addTag}
                        className="px-3 py-2 rounded-lg border text-xs font-medium text-gray-300 hover:text-white transition-colors"
                        style={{ borderColor: 'hsl(230 15% 20%)', background: 'hsl(230 15% 8%)' }}>
                        Add
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {form.tags.map(t => (
                        <span key={t}
                          className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-white/8 text-gray-300">
                          <Tag className="w-2.5 h-2.5" />
                          {t}
                          <button onClick={() => removeTag(t)} className="text-gray-500 hover:text-white ml-0.5">
                            <X className="w-2.5 h-2.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Step 5 — Review */}
              {step === 5 && (
                <div>
                  <div className="rounded-xl border p-4 mb-4"
                    style={{ background: 'hsl(230 15% 8%)', borderColor: 'hsl(230 15% 18%)' }}>
                    <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                      {(() => { const Icon = TYPE_ICONS[form.type]; return <Icon className="w-4 h-4 text-blue-400" />; })()}
                      {form.name || '(unnamed)'}
                    </h4>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {[
                        ['Type',       form.type],
                        ['Stack',      form.tech_stack],
                        ['Cluster',    form.cluster],
                        ['Namespace',  form.namespace],
                        ['Replicas',   String(form.replicas)],
                        ['Git Repo',   form.git_repo || '—'],
                      ].map(([k, v]) => (
                        <div key={k}>
                          <span className="text-gray-500">{k}: </span>
                          <span className="text-white">{v}</span>
                        </div>
                      ))}
                    </div>
                    {form.description && (
                      <p className="mt-3 text-xs text-gray-400">{form.description}</p>
                    )}
                    {form.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-3">
                        {form.tags.map(t => (
                          <span key={t} className="px-1.5 py-0.5 rounded text-xs bg-white/8 text-gray-400">{t}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-xs text-blue-300"
                    style={{ background: 'hsl(210 100% 50% / 0.05)', border: '1px solid hsl(210 100% 50% / 0.15)' }}>
                    <Zap className="w-3.5 h-3.5 flex-shrink-0" />
                    This will create the service definition and trigger an initial deployment to {form.cluster}/{form.namespace}.
                  </div>
                </div>
              )}

            </motion.div>
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t flex-shrink-0"
          style={{ borderColor: 'hsl(230 15% 18%)' }}>
          <button
            onClick={() => step === 0 ? onClose() : setStep(s => s - 1)}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-gray-400 hover:text-white transition-colors rounded-lg border"
            style={{ borderColor: 'hsl(230 15% 20%)' }}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            {step === 0 ? 'Cancel' : 'Back'}
          </button>

          {step < WIZARD_STEPS.length - 1 ? (
            <button
              onClick={() => setStep(s => s + 1)}
              disabled={!canNext}
              className={clsx(
                'flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg transition-all',
                canNext
                  ? 'bg-blue-600 hover:bg-blue-500 text-white'
                  : 'bg-white/5 text-gray-600 cursor-not-allowed',
              )}
            >
              Next
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="flex items-center gap-1.5 px-5 py-2 text-xs font-semibold rounded-lg bg-green-600 hover:bg-green-500 text-white transition-colors disabled:opacity-60"
            >
              {submitting ? (
                <><RefreshCw className="w-3.5 h-3.5 animate-spin" />Deploying…</>
              ) : (
                <><Zap className="w-3.5 h-3.5" />Deploy Service</>
              )}
            </button>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

// ── Main CatalogTab ───────────────────────────────────────────────────────────
interface Props {
  showToast: (ok: boolean, msg: string) => void;
}

export function CatalogTab({ showToast }: Props) {
  const [services, setServices] = useState<CatalogService[]>(SEED_SERVICES);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<ServiceType | 'All'>('All');
  const [filterStatus, setFilterStatus] = useState<string>('All');
  const [showWizard, setShowWizard] = useState(false);
  const [selectedSvc, setSelectedSvc] = useState<CatalogService | null>(null);

  const filtered = services.filter(s => {
    if (search && !s.name.includes(search.toLowerCase()) && !s.description?.toLowerCase().includes(search.toLowerCase())) return false;
    if (filterType !== 'All' && s.type !== filterType) return false;
    if (filterStatus !== 'All' && s.status !== filterStatus) return false;
    return true;
  });

  const stats = {
    total:     services.length,
    running:   services.filter(s => s.status === 'Running').length,
    deploying: services.filter(s => s.status === 'Deploying').length,
    failed:    services.filter(s => s.status === 'Failed').length,
  };

  const handleCreate = useCallback((svc: CatalogService) => {
    setServices(prev => [svc, ...prev]);
    setShowWizard(false);
    showToast(true, `Service "${svc.name}" is deploying to ${svc.cluster}/${svc.namespace}`);
  }, [showToast]);

  return (
    <div>
      {/* ── Stats strip ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Total Services', value: stats.total,     color: 'text-blue-400',   bg: 'bg-blue-500/10'   },
          { label: 'Running',        value: stats.running,   color: 'text-green-400',  bg: 'bg-green-500/10'  },
          { label: 'Deploying',      value: stats.deploying, color: 'text-blue-400',   bg: 'bg-blue-500/10'   },
          { label: 'Failed',         value: stats.failed,    color: 'text-red-400',    bg: 'bg-red-500/10'    },
        ].map(({ label, value, color, bg }) => (
          <div key={label} className="rounded-xl border p-4"
            style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
            <p className="text-xs text-gray-500 mb-1">{label}</p>
            <div className={clsx('inline-flex items-center justify-center w-8 h-8 rounded-lg text-sm font-bold mb-0.5', bg, color)}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* ── Toolbar ────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 mb-5">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search services…"
            className="w-full pl-9 pr-3 py-2 rounded-lg text-sm text-white placeholder-gray-600 border outline-none focus:border-blue-500 transition-colors"
            style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}
          />
        </div>

        <div className="relative">
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value as any)}
            className="pl-3 pr-8 py-2 rounded-lg text-xs text-gray-300 border outline-none appearance-none transition-colors cursor-pointer"
            style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}
          >
            <option value="All">All Types</option>
            {SERVICE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-500 pointer-events-none" />
        </div>

        <div className="relative">
          <select
            value={filterStatus}
            onChange={e => setFilterStatus(e.target.value)}
            className="pl-3 pr-8 py-2 rounded-lg text-xs text-gray-300 border outline-none appearance-none transition-colors cursor-pointer"
            style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}
          >
            {['All', 'Running', 'Deploying', 'Pending', 'Failed', 'Stopped'].map(s => (
              <option key={s} value={s}>{s === 'All' ? 'All Statuses' : s}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-500 pointer-events-none" />
        </div>

        <button
          onClick={() => setShowWizard(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-colors ml-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          New Service
        </button>
      </div>

      {/* ── Service grid ───────────────────────────────────────────────────── */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center">
            <Package className="w-6 h-6 text-gray-500" />
          </div>
          <p className="text-sm font-medium text-gray-400">No services found</p>
          <p className="text-xs text-gray-600">
            {search || filterType !== 'All' || filterStatus !== 'All'
              ? 'Try adjusting your filters.'
              : 'Create your first service to get started.'}
          </p>
          {!search && filterType === 'All' && filterStatus === 'All' && (
            <button
              onClick={() => setShowWizard(true)}
              className="mt-2 flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Create First Service
            </button>
          )}
        </div>
      ) : (
        <motion.div
          layout
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
        >
          <AnimatePresence mode="popLayout">
            {filtered.map(svc => (
              <motion.div
                key={svc.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2 }}
              >
                <ServiceCard svc={svc} onClick={() => setSelectedSvc(svc)} />
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      )}

      {/* ── Drawers & Dialogs ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {showWizard && (
          <CreateWizard onClose={() => setShowWizard(false)} onCreate={handleCreate} />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {selectedSvc && (
          <ServiceDetail svc={selectedSvc} onClose={() => setSelectedSvc(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}
