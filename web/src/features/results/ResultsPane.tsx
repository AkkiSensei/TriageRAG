import React from 'react'
import { SafetyBanner } from './SafetyBanner'
import { ScoreCard } from './ScoreCard'
import { AlertsList } from './AlertsList'
import { SkippedChecksList } from './SkippedChecksList'
import { VerifiedPlanView } from './VerifiedPlanView'
import { RetrievalView } from './RetrievalView'
import type { TriageResponse, Alert } from '@/lib/api'
import { Hash, Info, Loader2 } from 'lucide-react'

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
      <div className="flex min-h-[400px] flex-col items-center justify-center rounded-3xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-8 text-center shadow-soft">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 mb-4 shadow-soft-sm">
          <Loader2 className="h-7 w-7 animate-spin text-teal-600 dark:text-teal-400" />
        </div>
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">Executing Deterministic Safety Pipeline</h3>
        <p className="mt-1.5 max-w-sm text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
          Evaluating contraindication rules, calculating NEWS2/PEWS scores, checking formulary limits, and verifying plan citations...
        </p>
      </div>
    )
  }

  if (!triage) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-8 text-center shadow-soft">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-50 dark:bg-[#0c1618] text-slate-400 dark:text-slate-500 mb-4">
          <Info className="h-7 w-7" />
        </div>
        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">Awaiting Clinical Intake</h3>
        <p className="mt-1.5 max-w-sm text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
          Configure patient demographics, vitals, and medication history, or select a pre-engineered reference scenario above.
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
        <div className="flex items-center justify-between rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 text-xs font-mono text-slate-500 dark:text-slate-400 shadow-soft">
          <div className="flex items-center gap-2">
            <Hash className="h-4 w-4 text-teal-700 dark:text-teal-400" />
            <span className="text-slate-900 dark:text-slate-100 font-semibold">Record Audit SHA-256:</span>
          </div>
          <span className="truncate max-w-[280px] sm:max-w-md text-teal-800 dark:text-teal-300 select-all font-mono font-bold bg-teal-50 dark:bg-teal-950/60 px-2 py-0.5 rounded border border-teal-200 dark:border-teal-800">
            {triage.audit_hash}
          </span>
        </div>
      )}
    </div>
  )
}

export default ResultsPane
