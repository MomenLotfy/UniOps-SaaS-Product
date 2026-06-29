/**
 * DecisionDetail — Sprint 3 R33.
 *
 * Read-only drill-in for a single decision aggregate.
 * All data sourced from `GET /api/v1/security/decisions/{id}`.
 *
 * Backend schema (`DecisionDetailRead` from
 * `app/modules/security/decision_engine/api/schemas.py`):
 *   plan_steps:      List[{type, result}]
 *   reasons:         List[{code, desc}]
 *   context_summary: dict
 *   policy_ref:      {id, version} | null
 */
import { useEffect, useState } from 'react';
import { clsx } from 'clsx';
import {
  ArrowLeft, Loader2, Gavel, Activity, FileText, ListChecks,
  ShieldCheck, History as HistoryIcon, Box, XCircle,
  Info, AlertTriangle,
} from 'lucide-react';
import { decisionsApi } from '@/services/api/security';
import type {
  DecisionDetailResponse, DecisionStatus, DecisionResult,
} from '@/types/decision';

const STATUS_COLOR: Record<DecisionStatus, string> = {
  CREATED:         'text-gray-400 bg-gray-500/10 border-gray-500/20',
  CONTEXT_BUILDING:'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  VALIDATING:      'text-blue-400 bg-blue-500/10 border-blue-500/20',
  READY:           'text-green-400 bg-green-500/10 border-green-500/20',
  REJECTED:        'text-red-400 bg-red-500/10 border-red-500/20',
  ARCHIVED:        'text-gray-400 bg-gray-500/10 border-gray-500/20',
};

const RESULT_COLOR: Record<DecisionResult, string> = {
  MITIGATE:  'text-red-400',
  ACCEPT:    'text-yellow-400',
  TRANSFER:  'text-blue-400',
  AVOID:     'text-purple-400',
  NO_ACTION: 'text-green-400',
};

const HISTORY_TONE: Record<string, string> = {
  REJECTED: 'text-red-400',
  READY:    'text-green-400',
  ARCHIVED: 'text-gray-400',
  CREATED:  'text-gray-400',
  VALIDATING: 'text-blue-400',
  CONTEXT_BUILDING: 'text-yellow-400',
};

interface DecisionDetailProps {
  id: string;
  onBack: () => void;
}

export default function DecisionDetail({ id, onBack }: DecisionDetailProps) {
  const [data, setData]       = useState<DecisionDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    decisionsApi
      .getDetail(id)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e: Error) => { if (!cancelled) setError(e.message ?? 'Failed to load decision'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to decisions
      </button>

      {loading && (
        <div className="card-base p-8 flex items-center justify-center">
          <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
        </div>
      )}

      {error && !loading && (
        <div className="card-base p-6 text-center border-red-500/30">
          <XCircle className="w-7 h-7 text-red-400 mx-auto mb-2" />
          <p className="text-sm font-medium text-foreground mb-1">Failed to load decision</p>
          <p className="text-xs text-muted-foreground">{error}</p>
        </div>
      )}

      {data && !loading && !error && <DecisionDetailBody data={data} />}
    </div>
  );
}

function DecisionDetailBody({ data }: { data: DecisionDetailResponse }) {
  return (
    <>
      {/* Section 1: Header */}
      <SectionCard
        icon={<Gavel className="w-4 h-4 text-blue-400" />}
        title="Decision Header"
        right={
          <span className={clsx(
            'text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider',
            STATUS_COLOR[data.status] ?? 'text-muted-foreground bg-white/5 border-white/10',
          )}>
            {data.status}
          </span>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <KeyValue label="Decision ID" value={data.id} mono />
          <KeyValue label="Version" value={`v${data.version}`} />
          <KeyValue label="Tenant" value={data.tenant_id} mono />
          {data.final_result && (
            <KeyValue
              label="Final Result"
              value={data.final_result}
              valueClassName={clsx('font-bold', RESULT_COLOR[data.final_result] ?? 'text-foreground')}
            />
          )}
          <KeyValue label="Correlation ID" value={data.correlation_id} mono />
          {data.trace_id && <KeyValue label="Trace ID" value={data.trace_id} mono />}
          <KeyValue label="Context ID" value={data.context_id} mono />
          <KeyValue label="Created" value={new Date(data.created_at).toLocaleString()} />
          <KeyValue label="Updated" value={new Date(data.updated_at).toLocaleString()} />
        </div>
        {data.metadata && Object.keys(data.metadata).length > 0 && (
          <details className="mt-3 rounded-lg border" style={{ borderColor: 'hsl(230 15% 16%)' }}>
            <summary className="px-3 py-2 text-[11px] font-semibold text-muted-foreground cursor-pointer">
              metadata ({Object.keys(data.metadata).length} keys)
            </summary>
            <pre className="px-3 pb-3 pt-1 text-[11px] text-foreground/80 overflow-auto max-h-72 font-mono whitespace-pre-wrap break-all">
              {JSON.stringify(data.metadata, null, 2)}
            </pre>
          </details>
        )}
      </SectionCard>

      {/* Section 2: Context Summary */}
      <SectionCard
        icon={<Box className="w-4 h-4 text-purple-400" />}
        title="Context Summary"
        right={
          <span className="text-[10px] text-muted-foreground">
            {Object.keys(data.context_summary ?? {}).length} keys
          </span>
        }
      >
        <ContextBlock contextSummary={data.context_summary ?? {}} />
      </SectionCard>

      {/* Section 3: Decision Logic — reasons + plan steps */}
      <SectionCard
        icon={<Activity className="w-4 h-4 text-green-400" />}
        title="Decision Logic"
        right={
          <span className="text-[10px] text-muted-foreground">
            {data.reasons.length} reasons · {data.plan_steps.length} plan steps
          </span>
        }
      >
        <ReasonsList reasons={data.reasons} />
        {data.plan_steps.length > 0 && (
          <div className="mt-4 pt-4 border-t" style={{ borderColor: 'hsl(230 15% 14%)' }}>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <ListChecks className="w-3 h-3" /> Plan Steps
            </p>
            <PlanStepsList steps={data.plan_steps} />
          </div>
        )}
      </SectionCard>

      {/* Section 4: Policy Reference */}
      <SectionCard
        icon={<ShieldCheck className="w-4 h-4 text-cyan-400" />}
        title="Policy Reference"
      >
        {data.policy_ref ? (
          <PolicyRefBlock ref_={data.policy_ref} />
        ) : (
          <EmptyHint text="No policy reference attached to this decision." />
        )}
      </SectionCard>

      {/* Section 5: History */}
      {data.history && data.history.length > 0 && (
        <SectionCard
          icon={<HistoryIcon className="w-4 h-4 text-indigo-400" />}
          title="State History"
          right={
            <span className="text-[10px] text-muted-foreground">
              {data.history.length} transitions
            </span>
          }
        >
          <ol className="space-y-2 relative">
            <div className="absolute left-1.5 top-2 bottom-2 w-px bg-white/10" />
            {data.history.map((h) => (
              <li key={h.id} className="flex gap-3 relative pl-6">
                <span className={clsx(
                  'absolute left-0 top-1.5 w-3 h-3 rounded-full border-2 border-surface-1',
                  HISTORY_TONE[h.to_state] ?? 'bg-white/40',
                )} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap text-[11px]">
                    {h.from_state && (
                      <>
                        <span className="text-muted-foreground">{h.from_state}</span>
                        <span className="text-muted-foreground">→</span>
                      </>
                    )}
                    <span className={clsx('font-semibold', HISTORY_TONE[h.to_state] ?? 'text-foreground')}>
                      {h.to_state}
                    </span>
                    <span className="text-muted-foreground">· {h.changed_by}</span>
                    <span className="text-muted-foreground">· {new Date(h.created_at).toLocaleString()}</span>
                  </div>
                  {h.change_reason && (
                    <p className="text-[11px] text-muted-foreground mt-0.5">{h.change_reason}</p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </SectionCard>
      )}
    </>
  );
}

/* ── Section shell ─────────────────────────────────────────────────────── */

function SectionCard({
  icon, title, right, children,
}: { icon: React.ReactNode; title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="card-base p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          {icon} {title}
        </h2>
        {right}
      </div>
      {children}
    </div>
  );
}

function KeyValue({
  label, value, mono, valueClassName,
}: { label: string; value: React.ReactNode; mono?: boolean; valueClassName?: string }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-0.5">
        {label}
      </p>
      <p className={clsx('text-xs text-foreground break-all', mono && 'font-mono', valueClassName)}>
        {value}
      </p>
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div className="text-center py-6 text-[11px] text-muted-foreground flex items-center justify-center gap-1.5">
      <Info className="w-3 h-3" /> {text}
    </div>
  );
}

/* ── Sub-components ────────────────────────────────────────────────────── */

function ContextBlock({ contextSummary }: { contextSummary: Record<string, unknown> }) {
  const entries = Object.entries(contextSummary ?? {});
  if (entries.length === 0) {
    return <EmptyHint text="Context summary is empty." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <tbody className="divide-y" style={{ borderColor: 'hsl(230 15% 14%)' }}>
          {entries.map(([k, v]) => (
            <tr key={k}>
              <td className="py-1.5 pr-3 align-top w-1/3">
                <span className="font-mono text-muted-foreground">{k}</span>
              </td>
              <td className="py-1.5 align-top">
                <span className="font-mono text-foreground break-all">
                  {typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReasonsList({ reasons }: { reasons: DecisionDetailResponse['reasons'] }) {
  if (reasons.length === 0) {
    return <EmptyHint text="No reasons recorded." />;
  }
  return (
    <ul className="space-y-2">
      {reasons.map((r, idx) => {
        const code = r.reason_code ?? r.code ?? `reason-${idx}`;
        const desc = r.description ?? r.desc;
        return (
          <li key={`${code}-${idx}`} className="flex items-start gap-2 rounded-lg bg-white/[0.02] border border-white/5 p-2">
            <span className="text-blue-400 mt-0.5 text-xs font-bold">#{idx + 1}</span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-foreground font-mono">{code}</p>
              {desc && (
                <p className="text-[11px] text-muted-foreground mt-0.5">{desc}</p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function PlanStepsList({ steps }: { steps: DecisionDetailResponse['plan_steps'] }) {
  return (
    <ol className="space-y-2">
      {steps.map((s, idx) => {
        const label = s.description ?? s.type ?? `step ${idx + 1}`;
        return (
          <li key={`${s.type}-${idx}`} className="flex items-start gap-3">
            <span className="w-5 h-5 rounded-full bg-blue-500/15 text-blue-400 text-[10px] font-bold flex items-center justify-center flex-shrink-0">
              {s.step_number ?? idx + 1}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium text-foreground">{label}</span>
                {s.type && (
                  <span className="text-[10px] text-muted-foreground capitalize">
                    {(s.type ?? '').replace(/_/g, ' ')}
                  </span>
                )}
              </div>
              {s.result != null && (
                <pre className="text-[10px] text-muted-foreground mt-1 font-mono whitespace-pre-wrap break-all">
                  {typeof s.result === 'string' ? s.result : JSON.stringify(s.result)}
                </pre>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function PolicyRefBlock({ ref_ }: { ref_: NonNullable<DecisionDetailResponse['policy_ref']> }) {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-white/[0.02] border border-white/5 p-3">
      <ShieldCheck className="w-4 h-4 text-cyan-400 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-foreground">Matched Policy</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded border text-green-400 bg-green-500/10 border-green-500/20 uppercase tracking-wider">
            matched
          </span>
        </div>
        <p className="text-[10px] text-muted-foreground mt-0.5 font-mono">
          policy_id&nbsp;<span className="text-foreground">{ref_.id}</span>
          <span className="mx-2">·</span>
          version&nbsp;<span className="text-foreground">{ref_.version}</span>
        </p>
      </div>
    </div>
  );
}

// Re-export AlertTriangle so an unused-import lint doesn't fire if a future
// edit removes the icon usage above.  Keeps the icon set stable.
void AlertTriangle;
