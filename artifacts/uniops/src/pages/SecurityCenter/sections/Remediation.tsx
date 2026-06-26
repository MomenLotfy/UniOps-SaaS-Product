import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Wrench, Play, FileSearch, Activity,
  CheckCircle2, AlertCircle, Clock,
  ArrowRight, ShieldCheck
} from 'lucide-react';
import { clsx } from 'clsx';

export default function Remediation() {
  const [activeTab, setActiveTab] = useState<'capabilities' | 'plans' | 'history'>('capabilities');
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Wrench className="w-6 h-6 text-blue-400" />
            Remediation Engine
          </h1>
          <p className="text-sm text-muted-foreground">
            Architectural foundation for automated security patching and infrastructure fixes.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-xs font-medium hover:bg-blue-500 transition-colors flex items-center gap-2">
            <Play className="w-3 h-3" />
            Run Auto-Remediation
          </button>
        </div>
      </div>

      {/* ── Tabs ────────────────────────────────────────────────────────────────── */}
      <div className="flex p-1 bg-white/5 rounded-lg w-fit border border-white/10">
        {(['capabilities', 'plans', 'history'] as const).map(tab => (
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
      </div>

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
                      </div>
                      <span className={clsx(
                        "text-[10px] font-bold px-2 py-0.5 rounded-full border",
                        cap.status === 'Active' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                        cap.status === 'Beta' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                        'bg-purple-500/10 text-purple-400 border-purple-500/20'
                      )}>
                        {cap.status}
                      </span>
                    </div>
                    <h3 className="text-sm font-semibold text-foreground mb-1">{cap.name}</h3>
                    <p className="text-xs text-muted-foreground mb-4">{cap.desc}</p>
                    <button className="w-full py-2 rounded-md bg-white/5 hover:bg-white/10 text-white text-xs font-medium transition-all flex items-center justify-center gap-2 group-hover:text-blue-400">
                      View Implementation <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
            <div className="p-4 rounded-xl bg-surface-1 border border-white/10 space-y-4">
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Registry Status</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Registered Plugins</span>
                  <span className="font-mono text-foreground">3</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Active Capabilities</span>
                  <span className="font-mono text-foreground">12</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Engine Health</span>
                  <span className="text-green-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Optimal
                  </span>
                </div>
              </div>
            </div>
          </>
        )}

        {activeTab === 'plans' && (
          <div className="lg:col-span-3 overflow-hidden rounded-xl border border-white/10 bg-surface-1">
            <table className="w-full text-left text-xs">
              <thead className="bg-white/5 text-muted-foreground uppercase tracking-wider font-bold">
                <tr>
                  <th className="px-4 py-3">Plan ID</th>
                  <th className="px-4 py-3">Finding</th>
                  <th className="px-4 py-3">Technology</th>
                  <th className="px-4 py-3">Strategy</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Action</th>
                </tr>
              </thead>
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
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{plan.date}</td>
                    <td className="px-4 py-3">
                      <button className="p-1.5 rounded-md bg-white/5 hover:bg-blue-500/20 text-muted-foreground hover:text-blue-400 transition-all">
                        <Play className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="lg:col-span-3 flex flex-col items-center justify-center py-20 text-center space-y-4">
            <div className="p-4 rounded-full bg-white/5 text-muted-foreground">
              <Activity className="w-8 h-8 opacity-50" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-foreground">Execution History</h3>
              <p className="text-xs text-muted-foreground max-w-xs">
                Detailed telemetry and logs for every remediation attempt will appear here.
              </p>
            </div>
            <div className="flex gap-2">
              <div className="px-3 py-1 rounded-full bg-white/5 text-[10px] text-muted-foreground border border-white/10 flex items-center gap-1">
                <Clock className="w-3 h-3" /> Real-time Tracking
              </div>
              <div className="px-3 py-1 rounded-full bg-white/5 text-[10px] text-muted-foreground border border-white/10 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> Error Analysis
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
