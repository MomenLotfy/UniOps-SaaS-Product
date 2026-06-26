import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Wrench, Play, FileSearch, Activity,
  CheckCircle2, AlertCircle, Clock,
  ArrowRight, ShieldCheck, Database, Cpu, ListOrdered
} from 'lucide-react';
import { clsx } from 'clsx';

export default function Remediation() {
  const [activeTab, setActiveTab] = useState<'capabilities' | 'plans' | 'history' | 'monitoring' | 'governance'>('capabilities');
  const [isLoading, setIsLoading] = useState(false);

  // Mock data for the architecture preview
  const capabilities = [
    { id: 'DependencyUpgrade', name: 'Dependency Upgrade', desc: 'Automatically bump versions of vulnerable packages', status: 'Active' },
    { id: 'DockerImageHardening', name: 'Docker Image Hardening', desc: 'Apply security best practices to Dockerfiles', status: 'Beta' },
    { id: 'TfInfrastructureFix', name: 'Tf Infrastructure Fix', desc: 'Remediate insecure cloud resource configurations', status: 'Experimental' },
  ];

  const plans = [
    { id: 'plan-123', finding: 'CVE-2023-4567', tech: 'Docker', strategy: 'Multi-Stage Build', status: 'completed', date: '2026-06-20' },
    { id: 'plan-456', finding: 'S3 Bucket Public', tech: 'Terraform', strategy: 'Restrict Access', status: 'executing', date: '2026-06-25' },
    { id: 'plan-789', finding: 'Old Node.js Version', tech: 'npm', strategy: 'Semantic Version Bump', status: 'draft', date: '2026-06-26' },
  ];

  const workerStatus = [
    { name: 'PlanningWorker', status: 'active', load: 'Low' },
    { name: 'ExecutionWorker', status: 'active', load: 'Medium' },
    { name: 'ValidationWorker', status: 'active', load: 'Low' },
    { name: 'NotificationWorker', status: 'active', load: 'Low' },
    { name: 'MetricsWorker', status: 'active', load: 'Low' },
  ];

  const timeline = [
    { state: 'CREATED', time: '2026-06-26 10:00:00', icon: ListOrdered },
    { state: 'PLANNING', time: '2026-06-26 10:00:05', icon: FileSearch },
    { state: 'CAPABILITY_SELECTED', time: '2026-06-26 10:00:12', icon: ShieldCheck },
    { state: 'WAITING_FOR_VALIDATION', time: '2026-06-26 10:00:15', icon: Clock },
    { state: 'READY_FOR_EXECUTION', time: '2026-06-26 10:00:20', icon: CheckCircle2 },
    { state: 'EXECUTING', time: '2026-06-26 10:00:25', icon: Play },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div >
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Wrench className="w-6 h-6 text-blue-400" />
            Remediation Engine
          </h1>
          <p className="text-sm text-muted-foreground">
            Architectural foundation for automated security patching and infrastructure fixes.
          </p>
        </div >
        <div className="flex gap-2">
          <button className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-xs font-medium hover:bg-blue-500 transition-colors flex items-center gap-2">
            <Play className="w-3 h-3" />
            Run Auto-Remediation
          </button>
        </div >
      </div >

      {/* ── Tabs ────────────────────────────────────────────────────────────────── */}
      <div className="flex p-1 bg-white/5 rounded-lg w-fit border border-white/10">
        {(['capabilities', 'plans', 'history', 'monitoring', 'governance'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-4 py-1.5 rounded-md text-xs font-medium transition-all',
              activeTab === tab
                ? 'bg-white/10 text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div >

      {/* ── Content ──────────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {activeTab === 'capabilities' && (
          <>
            <div className="lg:col-span-2 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {capabilities.map(cap => (
                  <div key={cap.id} className="p-4 rounded-xl bg-surface-1 border border-white/10 hover:border-blue-500/50 transition-all group">
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                        <ShieldCheck className="w-5 h-5" />
                      </div >
                      <span className={clsx(
                        "text-[10px] font-bold px-2 py-0.5 rounded-full border",
                        cap.status === 'Active' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                        cap.status === 'Beta' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                        'bg-purple-500/10 text-purple-400 border-purple-500/20'
                      )}>
                        {cap.status}
                      </span >
                    </div >
                    <h3 className="text-sm font-semibold text-foreground mb-1">{cap.name}</h3>
                    <p className="text-xs text-muted-foreground mb-4">{cap.desc}</p>
                    <button className="w-full py-2 rounded-md bg-white/5 hover:bg-white/10 text-white text-xs font-medium transition-all flex items-center justify-center gap-2 group-hover:text-blue-400">
                      View Implementation <ArrowRight className="w-3 h-3" />
                    </button>
                  </div >
                ))}
              </div >
            </div >
            <div className="p-4 rounded-xl bg-surface-1 border border-white/10 space-y-4">
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Registry Status</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Registered Plugins</span>
                  <span className="font-mono text-foreground">3</span >
                </div >
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Active Capabilities</span>
                  <span className="font-mono text-foreground">12</span >
                </div >
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Engine Health</span>
                  <span className="text-green-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Optimal
                  </span >
                </div >
              </div >
            </div >
          </>
        )}

        {activeTab === 'plans' && (
          <div className="lg:col-span-3 overflow-hidden rounded-xl border border-white/10 bg-surface-1">
            <table className="w-full text-left text-xs">
              <thead className="bg-white/5 text-muted-foreground uppercase tracking-wider font-bold">
                <tr >
                  <th className="px-4 py-3">Plan ID</th>
                  <th className="px-4 py-3">Finding</th>
                  <th className="px-4 py-3">Technology</th>
                  <th className="px-4 py-3">Strategy</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Action</th>
                </tr >
              </thead >
              <tbody className="divide-y divide-white/5">
                {plans.map(plan => (
                  <tr key={plan.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3 font-mono text-muted-foreground">{plan.id}</td>
                    <td className="px-4 py-3 font-medium">{plan.finding}</td>
                    <td className="px-4 py-3">{plan.tech}</td>
                    <td className="px-4 py-3">{plan.strategy}</td>
                    <td className="px-4 py-3">
                      <span className={clsx(
                        "px-2 py-0.5 rounded-full text-[10px] font-bold border",
                        plan.status === 'completed' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                        plan.status === 'executing' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                        'bg-gray-500/10 text-gray-400 border-gray-500/20'
                      )}>
                        {plan.status}
                      </span >
                    </td >
                    <td className="px-4 py-3 text-muted-foreground">{plan.date}</td>
                    <td className="px-4 py-3">
                      <button className="p-1.5 rounded-md bg-white/5 hover:bg-blue-500/20 text-muted-foreground hover:text-blue-400 transition-all">
                        <Play className="w-3 h-3" />
                      </button>
                    </td >
                  </tr >
                ))}
              </tbody >
            </table >
          </div >
        )}

        {activeTab === 'history' && (
          <div className="lg:col-span-3 flex flex-col items-center justify-center py-20 text-center space-y-4">
            <div className="p-4 rounded-full bg-white/5 text-muted-foreground">
              <Activity className="w-8 h-8 opacity-50" />
            </div >
            <div >
              <h3 className="text-sm font-semibold text-foreground">Execution History</h3>
              <p className="text-xs text-muted-foreground max-w-xs">
                Detailed telemetry and logs for every remediation attempt will appear here.
              </p>
            </div >
            <div className="flex gap-2">
              <div className="px-3 py-1 rounded-full bg-white/5 text-[10px] text-muted-foreground border border-white/10 flex items-center gap-1">
                <Clock className="w-3 h-3" /> Real-time Tracking
              </div >
              <div className="px-3 py-1 rounded-full bg-white/5 text-[10px] text-muted-foreground border border-white/10 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> Error Analysis
              </div >
            </div >
          </div >
        )}

        {activeTab === 'governance' && (
          <div className="lg:col-span-3 space-y-6">
             <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-6 rounded-xl bg-surface-1 border border-white/10 space-y-4">
                    <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-blue-400" />
                        Execution Policies
                    </h3>
                    <div className="space-y-3">
                        {[
                            { id: 'POL-001', type: 'Manual Approval', desc: 'Critical Production Repositories' },
                            { id: 'POL-002', type: 'Production Freeze', desc: 'Peak Hour Constraints' },
                            { id: 'POL-003', type: 'Security Approval', desc: 'SVP Security Sign-off' },
                        ].map(p => (
                            <div key={p.id} className="p-3 rounded-lg bg-white/5 border border-white/10 flex justify-between items-center">
                                <div>
                                    <p className="text-xs font-medium text-foreground">{p.type}</p>
                                    <p className="text-[10px] text-muted-foreground">{p.desc}</p>
                                </div>
                                <span className="text-[10px] font-mono text-muted-foreground">{p.id}</span>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="p-6 rounded-xl bg-surface-1 border border-white/10 space-y-4">
                    <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                        <Database className="w-4 h-4 text-blue-400" />
                        Plugin Compatibility
                    </h3>
                    <div className="space-y-3">
                        {[
                            { id: 'dep-upgrader', ver: '1.2.0', min: '1.0.0', max: '2.0.0', status: 'Compatible' },
                            { id: 'docker-hardener', ver: '0.8.4', min: '1.0.0', max: '1.1.0', status: 'Compatible' },
                            { id: 'tf-fixer', ver: '0.5.0', min: '1.0.0', max: '1.0.0', status: 'Outdated' },
                        ].map(pl => (
                            <div key={pl.id} className="p-3 rounded-lg bg-white/5 border border-white/10 flex justify-between items-center">
                                <div>
                                    <p className="text-xs font-medium text-foreground">{pl.id}</p>
                                    <p className="text-[10px] text-muted-foreground">Ver {pl.ver} (Min: {pl.min}, Max: {pl.max})</p>
                                </div>
                                <span className={clsx(
                                    "text-[10px] px-2 py-0.5 rounded-full border",
                                    pl.status === 'Compatible' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'
                                )}>
                                    {pl.status}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
             </div >

             <div className="p-6 rounded-xl bg-surface-1 border border-white/10">
                <h3 className="text-sm font-bold text-foreground mb-4 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-blue-400" />
                    Engine Versions & Health
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                        <p className="text-[10px] text-muted-foreground uppercase tracking-widest">Planner Version</p>
                        <p className="text-sm font-mono text-foreground">v1.0.4-stable</p>
                    </div>
                    <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                        <p className="text-[10px] text-muted-foreground uppercase tracking-widest">Execution Engine</p>
                        <p className="text-sm font-mono text-foreground">v1.0.0-core</p>
                    </div>
                    <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                        <p className="text-[10px] text-muted-foreground uppercase tracking-widest">Registry Health</p>
                        <p className="text-sm font-medium text-green-400">Optimal</p>
                    </div>
                </div >
             </div >
          </div >
        )}

        {activeTab === 'monitoring' && (
          <>
            <div className="lg:col-span-2 space-y-6">
              {/* ── Execution Timeline ────────────────────────────────────────────────── */}
              <div className="p-6 rounded-xl bg-surface-1 border border-white/10">
                <h3 className="text-sm font-bold text-foreground mb-6 flex items-center gap-2">
                  <ListOrdered className="w-4 h-4 text-blue-400" />
                  Execution Timeline (Plan: plan-456)
                </h3>
                <div className="relative space-y-8 pl-4">
                  <div className="absolute left-0 top-0 bottom-0 w-px bg-white/10 ml-[-1px]" />
                  {timeline.map((step, i) => (
                    <div key={i} className="relative pl-8 group">
                      <div className="absolute left-[-18px] top-1 w-3 h-3 rounded-full bg-surface-1 border-2 border-blue-500 group-hover:bg-blue-500 transition-colors" />
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <step.icon className="w-4 h-4 text-muted-foreground group-hover:text-blue-400 transition-colors" />
                          <span className="text-xs font-semibold text-foreground">{step.state}</span>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground">{step.time}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div >

              {/* ── Runtime Metrics ────────────────────────────────────────────────── */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-surface-1 border border-white/10">
                  <div className="flex items-center gap-2 mb-4 text-muted-foreground">
                    <Activity className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-widest">Execution Rate</span>
                  </div >
                  <div className="text-2xl font-mono text-foreground">1.2 <span className="text-xs text-muted-foreground">plans/hr</span></div >
                  <div className="mt-2 text-[10px] text-green-400">↑ 12% from last week</div >
                </div >
                <div className="p-4 rounded-xl bg-surface-1 border border-white/10">
                  <div className="flex items-center gap-2 mb-4 text-muted-foreground">
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-widest">Success Rate</span>
                  </div >
                  <div className="text-2xl font-mono text-foreground">94.2%</div >
                  <div className="mt-2 text-[10px] text-muted-foreground">Based on 450 executions</div >
                </div >
              </div >
            </div >

            <div className="space-y-4">
              {/* ── Worker Status ────────────────────────────────────────────────── */}
              <div className="p-4 rounded-xl bg-surface-1 border border-white/10">
                <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-4 flex items-center gap-2">
                  <Cpu className="w-4 h-4" />
                  Worker Fleet
                </h3>
                <div className="space-y-3">
                  {workerStatus.map(w => (
                    <div key={w.name} className="flex items-center justify-between text-xs p-2 rounded-md bg-white/5">
                      <span className="text-foreground font-medium">{w.name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">{w.load} Load</span>
                        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                      </div >
                    </div >
                  ))}
                </div >
              </div >

              {/* ── Queue Health ────────────────────────────────────────────────── */}
              <div className="p-4 rounded-xl bg-surface-1 border border-white/10">
                <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-4 flex items-center gap-2">
                  <Database className="w-4 h-4" />
                  Queue Depth
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Planning</span>
                    <span className="font-mono text-foreground">0</span>
                  </div >
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Execution</span>
                    <span className="font-mono text-foreground">2</span>
                  </div >
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Validation</span>
                    <span className="font-mono text-foreground">0</span>
                  </div >
                </div >
              </div >
            </div >
          </>
        )}
      </div >
    </div >
  );
}
