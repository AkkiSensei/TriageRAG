import React from 'react'
import { HelpCircle, AlertCircle, ArrowLeft } from 'lucide-react'
import type { components } from '@/types/api'

export type SkippedCheck = components['schemas']['SkippedCheck']

interface SkippedChecksListProps {
  skippedChecks: SkippedCheck[]
  onFixInIntake?: () => void
}

export const SkippedChecksList: React.FC<SkippedChecksListProps> = ({
  skippedChecks,
  onFixInIntake,
}) => {
  if (!skippedChecks || skippedChecks.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-violet-200 bg-gradient-to-r from-violet-50/70 via-white to-violet-50/40 p-5 shadow-soft">
      <div className="flex items-center justify-between border-b border-violet-200 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-100 text-violet-700">
            <HelpCircle className="h-4 w-4" />
          </div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-violet-950">
            Unverified Safety Checks ({skippedChecks.length}) &bull; Fail Closed
          </h3>
        </div>
        {onFixInIntake && (
          <button
            type="button"
            onClick={onFixInIntake}
            className="flex items-center gap-1.5 text-xs font-mono text-violet-800 hover:text-violet-950 transition-colors font-bold bg-violet-100 px-3 py-1 rounded-xl border border-violet-300 shadow-soft-sm"
          >
            <ArrowLeft className="h-3 w-3" />
            <span>Fix in Intake</span>
          </button>
        )}
      </div>

      <p className="text-xs text-violet-900/90 leading-relaxed font-medium">
        The following clinical rules could not be evaluated due to missing, incomplete, or unresolved patient fields. Under the <strong>Rule R2 Fail-Closed protocol</strong>, these remain unverified rather than assumed safe:
      </p>

      <div className="flex flex-col gap-2.5">
        {skippedChecks.map((check: SkippedCheck, idx: number) => (
          <div
            key={`${check.rule_id}-${idx}`}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 rounded-xl border border-violet-200 bg-white p-3.5 text-xs shadow-soft-sm"
          >
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-violet-950">{check.rule_id}</span>
                <span className="text-[10px] text-violet-600 font-mono">({check.rule_type})</span>
              </div>
              <span className="text-slate-600 text-xs">{check.reason}</span>
            </div>

            {check.missing_fields && check.missing_fields.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] text-slate-400 font-mono">Missing:</span>
                {check.missing_fields.map((f: string) => (
                  <span
                    key={f}
                    className="flex items-center gap-1 rounded-lg bg-violet-100 border border-violet-300 px-2.5 py-0.5 text-[10px] font-mono font-bold text-violet-900"
                  >
                    <AlertCircle className="h-2.5 w-2.5 text-violet-600" />
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default SkippedChecksList
