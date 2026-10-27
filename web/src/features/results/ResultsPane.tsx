import React from 'react'
import { SafetyBanner } from './SafetyBanner'
import { ScoreCard } from './ScoreCard'
import { AlertsList } from './AlertsList'
import { SkippedChecksList } from './SkippedChecksList'
import { VerifiedPlanView } from './VerifiedPlanView'
import { RetrievalView } from './RetrievalView'
import type { TriageResponse, Alert } from '@/lib/api'
import { ShieldCheck, Hash, Info } from 'lucide-react'

interface ResultsPaneProps {
  triage: TriageResponse | null
  isLoading?: boolean
  onOverrideHighAlert?: (ruleId: string) => void
}

export const ResultsPane: React.FC<ResultsPaneProps> = ({
  triage,
  isLoading,
  onOverrideHighAlert,
}) => {
  if (isLoading) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/40 p-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-400 mb-4 animate-pulse">
          <ShieldCheck className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-slate-200">Executing Deterministic Safety Pipeline</h3>
        <p className="mt-1.5 max-w-sm text-xs text-slate-400 leading-relaxed">
          Evaluating contraindication rules, calculating physiological scores, checking formulary limits, and verifying plan citations...
        </p>
      </div>
    )
  }

  if (!triage) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/20 p-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-slate-400 mb-4">
          <Info className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-slate-300">Awaiting Clinical Intake</h3>
        <p className="mt-1.5 max-w-sm text-xs text-slate-400 leading-relaxed">
          Configure patient demographics, vitals, and medication history on the left, or select a pre-engineered reference scenario above.
        </p>
      </div>
    )
  }

  const engine = triage.engine
  const allAlerts: Alert[] = [
    ...(engine.baseline_alerts || []),
    ...(engine.plan_alerts || []),
  ]

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Top-Level Safety Banner (NEVER animated) */}
      <SafetyBanner report={engine} />

      {/* 2. Physiological Score */}
      {engine.score && <ScoreCard score={engine.score} />}

      {/* 3. Safety Alerts & Blocked Contraindications */}
      <AlertsList alerts={allAlerts} onOverrideHighAlert={onOverrideHighAlert} />

      {/* 4. Skipped Checks / Fail Closed */}
      {engine.checks_skipped && engine.checks_skipped.length > 0 && (
        <SkippedChecksList skippedChecks={engine.checks_skipped} />
      )}

      {/* 5. Verified Plan Steps */}
      {triage.verified_steps && triage.verified_steps.length > 0 && (
        <VerifiedPlanView steps={triage.verified_steps} />
      )}

      {/* 6. Retrieval Context & Chunks */}
      <RetrievalView triage={triage} />

      {/* 7. Cryptographic Audit Hash Bar */}
      {triage.audit_hash && (
        <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950 p-3 text-[11px] font-mono text-slate-400">
          <div className="flex items-center gap-2">
            <Hash className="h-3.5 w-3.5 text-teal-400" />
            <span>Record Audit SHA-256:</span>
          </div>
          <span className="truncate max-w-[280px] sm:max-w-md text-slate-300 select-all font-mono">
            {triage.audit_hash}
          </span>
        </div>
      )}
    </div>
  )
}
