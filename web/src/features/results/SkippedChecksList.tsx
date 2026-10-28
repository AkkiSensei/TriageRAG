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
    <div className="flex flex-col gap-3 rounded-2xl border border-purple-200 bg-purple-50/60 p-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-purple-200 pb-2">
        <div className="flex items-center gap-2">
          <HelpCircle className="h-4 w-4 text-purple-600" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-purple-950">
            Unverified Safety Checks ({skippedChecks.length}) — Missing Clinical Data
          </h3>
        </div>
        {onFixInIntake && (
          <button
            type="button"
            onClick={onFixInIntake}
            className="flex items-center gap-1 text-[11px] font-mono text-purple-700 hover:text-purple-950 hover:underline transition-colors font-semibold"
          >
            <ArrowLeft className="h-3 w-3" />
            <span>Supply missing data in Intake</span>
          </button>
        )}
      </div>

      <p className="text-xs text-purple-900/90 leading-relaxed">
        The following clinical rules could not be evaluated due to missing, incomplete, or unresolved patient fields. Under the fail-closed safety protocol, these remain unverified rather than assumed safe:
      </p>

      <div className="flex flex-col gap-2">
        {skippedChecks.map((check: SkippedCheck, idx: number) => (
          <div
            key={`${check.rule_id}-${idx}`}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-xl border border-purple-200 bg-white p-3 text-xs shadow-xs"
          >
            <div className="flex flex-col gap-0.5">
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-purple-950">{check.rule_id}</span>
                <span className="text-[10px] text-purple-600 font-mono">({check.rule_type})</span>
              </div>
              <span className="text-[#5C6B64] text-[11px]">{check.reason}</span>
            </div>

            {check.missing_fields && check.missing_fields.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[10px] text-[#5C6B64]">Missing:</span>
                {check.missing_fields.map((f: string) => (
                  <span
                    key={f}
                    className="flex items-center gap-1 rounded-md bg-purple-100 border border-purple-300 px-2 py-0.5 text-[10px] font-mono font-bold text-purple-800"
                  >
                    <AlertCircle className="h-2.5 w-2.5 text-purple-600" />
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

