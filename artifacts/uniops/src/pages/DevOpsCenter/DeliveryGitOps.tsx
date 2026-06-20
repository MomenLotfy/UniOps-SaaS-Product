// ─────────────────────────────────────────────────────────────────────────────
// Section 3 — Delivery & GitOps
// Sub-tabs: GitOps | CI/CD Pipelines | Deploy History
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GitBranch, History, CheckCircle } from 'lucide-react';
import { clsx } from 'clsx';

import { ConfirmDialog, EmptyState, RowSkeleton, PipelineTableRow, JobsDrawer } from './components';
import { GitOpsTab } from './GitOpsTab';
import { useDevOpsIntegrations, usePipelines, usePipelineActions } from './hooks';
import type { PipelineRow } from './types';

type DeliverySection = 'gitops' | 'pipelines' | 'history';

const SUB_TABS: { id: DeliverySection; label: string; icon: React.ElementType }[] = [
  { id: 'gitops',     label: 'GitOps',   icon: GitBranch },
  { id: 'pipelines',  label: 'CI/CD',    icon: GitBranch },
  { id: 'history',    label: 'History',  icon: History   },
];

interface Props {
  showToast: (ok: boolean, msg: string) => void;
  canAct:    boolean;
}

export function DeliveryGitOps({ showToast, canAct }: Props) {
  const [tab, setTab] = useState<DeliverySection>('gitops');

  const { gitConnected, isLoading: intLoading } = useDevOpsIntegrations();
  const { pipelines, loading: pipesLoading, error: pipesError, refetch: refetchPipes } = usePipelines();
  const pipeActions = usePipelineActions(refetchPipes);

  const [confirmRerun, setConfirmRerun]   = useState<{ pipeline: PipelineRow; failedOnly: boolean } | null>(null);
  const [confirmCancel, setConfirmCancel] = useState<PipelineRow | null>(null);
  const [jobsPipeline, setJobsPipeline]   = useState<PipelineRow | null>(null);

  const handlePipelineConfirm = useCallback(async () => {
    if (!confirmRerun) return;
    const { pipeline, failedOnly } = confirmRerun;
    try {
      const msg = await pipeActions.rerun(pipeline.id, failedOnly);
      showToast(true, msg);
    } catch (e: any) {
      showToast(false, e.message ?? 'Re-run failed');
    } finally {
      setConfirmRerun(null);
    }
  }, [confirmRerun, pipeActions, showToast]);

  const handleCancelConfirm = useCallback(async () => {
    if (!confirmCancel) return;
    try {
      const msg = await pipeActions.cancel(confirmCancel.id);
      showToast(true, msg);
    } catch (e: any) {
      showToast(false, e.message ?? 'Cancel failed');
    } finally {
      setConfirmCancel(null);
    }
  }, [confirmCancel, pipeActions, showToast]);

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

          {/* ── GitOps ─────────────────────────────────────────────────────── */}
          {tab === 'gitops' && (
            <GitOpsTab showToast={showToast} />
          )}

          {/* ── CI/CD Pipelines ────────────────────────────────────────────── */}
          {tab === 'pipelines' && (
            <div className="rounded-xl border overflow-hidden"
              style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
              <div className="flex items-center justify-between px-5 py-4 border-b"
                style={{ borderColor: 'hsl(230 15% 15%)' }}>
                <div className="flex items-center gap-2">
                  <GitBranch className="w-4 h-4 text-purple-400" />
                  <span className="text-sm font-semibold text-white">Pipelines</span>
                  {pipelines.length > 0 && (
                    <span className="text-xs text-gray-500 font-mono">({pipelines.length})</span>
                  )}
                </div>
                {canAct && gitConnected && (
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <CheckCircle className="w-3 h-3 text-green-500" />
                    Re-run enabled
                  </div>
                )}
              </div>
              <div className="p-4">
                {!intLoading && !gitConnected && (
                  <EmptyState icon={GitBranch} title="GitHub / GitLab not connected"
                    description="Connect your GitHub or GitLab account to monitor pipelines and trigger re-runs directly from UniOps."
                    action={{ label: 'Connect GitHub / GitLab', href: '/settings/integrations' }} />
                )}
                {gitConnected && pipesLoading && <RowSkeleton rows={5} />}
                {gitConnected && !pipesLoading && pipesError && (
                  <div className="flex flex-col items-center gap-3 py-10 text-center">
                    <p className="text-sm text-red-400">{pipesError}</p>
                    <button onClick={() => refetchPipes()}
                      className="text-xs px-3 py-1.5 rounded-lg text-gray-300 hover:text-white border border-border transition-colors">
                      Retry
                    </button>
                  </div>
                )}
                {gitConnected && !pipesLoading && !pipesError && pipelines.length === 0 && (
                  <EmptyState icon={GitBranch} title="No pipelines found"
                    description="No pipeline runs detected. Push a commit or trigger a workflow to see results here." />
                )}
                {gitConnected && !pipesLoading && pipelines.length > 0 && (
                  <div className="space-y-2">
                    {pipelines.map((pl: PipelineRow) => (
                      <PipelineTableRow
                        key={pl.id}
                        pipeline={pl}
                        canAct={canAct}
                        onRerun={(p, failedOnly) => setConfirmRerun({ pipeline: p, failedOnly })}
                        onCancel={p => setConfirmCancel(p)}
                        onViewJobs={p => setJobsPipeline(p)}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Deploy History ─────────────────────────────────────────────── */}
          {tab === 'history' && (
            <div className="rounded-xl border overflow-hidden"
              style={{ background: 'hsl(230 15% 9%)', borderColor: 'hsl(230 15% 15%)' }}>
              <div className="flex items-center gap-2 px-5 py-4 border-b"
                style={{ borderColor: 'hsl(230 15% 15%)' }}>
                <History className="w-4 h-4 text-gray-400" />
                <span className="text-sm font-semibold text-white">Deploy History</span>
              </div>
              <div className="p-4">
                {pipelines.filter((p: PipelineRow) =>
                  ['success', 'failed', 'error'].includes(p.status?.toLowerCase())
                ).length === 0 ? (
                  <EmptyState icon={History} title="No completed deployments"
                    description="Completed pipeline runs will appear here for audit and review." />
                ) : (
                  <div className="space-y-2">
                    {pipelines
                      .filter((p: PipelineRow) =>
                        ['success', 'failed', 'error'].includes(p.status?.toLowerCase())
                      )
                      .map((pl: PipelineRow) => (
                        <PipelineTableRow
                          key={pl.id}
                          pipeline={pl}
                          canAct={false}
                          onRerun={() => {}}
                          onViewJobs={p => setJobsPipeline(p)}
                        />
                      ))}
                  </div>
                )}
              </div>
            </div>
          )}

        </motion.div>
      </AnimatePresence>

      {/* ── Dialogs ──────────────────────────────────────────────────────────── */}
      <ConfirmDialog
        open={!!confirmRerun}
        title={
          confirmRerun?.failedOnly
            ? `Re-run failed jobs in "${confirmRerun.pipeline.name}"?`
            : `Re-run all jobs in "${confirmRerun?.pipeline.name}"?`
        }
        description={
          confirmRerun?.failedOnly
            ? `Only failed jobs will be re-queued on ${confirmRerun.pipeline.repository}. Successful jobs are skipped.`
            : `All jobs will be re-queued from scratch on ${confirmRerun?.pipeline.repository}.`
        }
        confirmLabel={confirmRerun?.failedOnly ? 'Re-run Failed Jobs' : 'Re-run All Jobs'}
        danger={false}
        loading={pipeActions.loading}
        onConfirm={handlePipelineConfirm}
        onCancel={() => setConfirmRerun(null)}
      />

      <ConfirmDialog
        open={!!confirmCancel}
        title={`Cancel pipeline "${confirmCancel?.name}"?`}
        description="This will send a cancellation request to GitHub. Currently running jobs will be stopped."
        confirmLabel="Cancel Pipeline"
        danger={true}
        loading={pipeActions.loading}
        onConfirm={handleCancelConfirm}
        onCancel={() => setConfirmCancel(null)}
      />

      <AnimatePresence>
        {jobsPipeline && (
          <JobsDrawer pipeline={jobsPipeline} onClose={() => setJobsPipeline(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}
