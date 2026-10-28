import React from 'react'
import { AlertOctagon, AlertTriangle, Info, ShieldAlert, Ban } from 'lucide-react'
import type { Alert, VerifiedStep } from '@/lib/api'

interface AlertsListProps {
  alerts: Alert[]
  verifiedSteps?: VerifiedStep[]
  onOverrideHighAlert?: (ruleId: string, stepNumber: number) => void
}

export const AlertsList: React.FC<AlertsListProps> = ({
  alerts,
  verifiedSteps,
  onOverrideHighAlert,
}) => {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="rounded-xl border border-[#E1E7E1] bg-white p-4 text-xs text-[#5C6B64] shadow-xs">
        No active clinical safety alerts triggered in this run.
      </div>
    )
  }

  // Helper to find matching step for an alert
  const findMatchingStepNumber = (ruleId: string): number => {
    if (!verifiedSteps || verifiedSteps.length === 0) return 1
    const matchingStep = verifiedSteps.find((s) => s.triggered_rule_ids?.includes(ruleId))
    return matchingStep ? matchingStep.draft.step_number : 1
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-amber-500" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#1A2421]">
            Safety Alerts & Contraindications ({alerts.length})
          </h3>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {alerts.map((alert, idx) => {
          const isBlock = alert.severity === 'BLOCK'
          const isHigh = alert.severity === 'HIGH'
          const isModerate = alert.severity === 'MODERATE'

          let cardBorder = 'border-[#E1E7E1] bg-white shadow-xs'
          let severityBadge = 'border-blue-200 bg-blue-50 text-blue-800'
          let SeverityIcon = Info

          if (isBlock) {
            cardBorder = 'border-red-300 bg-red-50/60 shadow-xs'
            severityBadge = 'border-red-300 bg-red-100 text-red-800 font-bold'
            SeverityIcon = AlertOctagon
          } else if (isHigh) {
            cardBorder = 'border-amber-300 bg-amber-50/60 shadow-xs'
            severityBadge = 'border-amber-300 bg-amber-100 text-amber-900 font-bold'
            SeverityIcon = AlertTriangle
          } else if (isModerate) {
            cardBorder = 'border-amber-200 bg-amber-50/40 shadow-xs'
            severityBadge = 'border-amber-200 bg-amber-100 text-amber-800 font-semibold'
            SeverityIcon = AlertTriangle
          }

          const isDraftProvenance =
            alert.provenance?.source_status === 'PLACEHOLDER_UNRETRIEVED' ||
            !alert.provenance?.verified

          const stepNumber = findMatchingStepNumber(alert.rule_id)

          return (
            <div key={`${alert.rule_id}-${idx}`} className={`rounded-2xl border p-4 ${cardBorder}`}>
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono border ${severityBadge}`}
                  >
                    <SeverityIcon className="h-3 w-3" />
                    {alert.severity}
                  </span>
                  <span className="font-mono text-xs font-bold text-[#1A2421]">
                    {alert.rule_id}
                  </span>
                  <span className="text-[10px] text-[#5C6B64] font-mono">({alert.rule_type})</span>
                </div>

                {isDraftProvenance && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border border-amber-300 bg-amber-100 text-amber-800 uppercase font-semibold">
                    Draft Rule Formulation
                  </span>
                )}
              </div>

              {/* Target drugs */}
              {alert.drug_ids && alert.drug_ids.length > 0 && (
                <div className="mb-2 flex items-center gap-2 flex-wrap text-xs">
                  <span className="text-[#5C6B64]">Target Agent(s):</span>
                  {alert.drug_ids.map((drug) => (
                    <span
                      key={drug}
                      className={`font-mono px-2 py-0.5 rounded-md text-xs font-bold ${
                        isBlock
                          ? 'line-through text-red-800 bg-red-100 border border-red-300'
                          : 'text-amber-900 bg-amber-100 border border-amber-300'
                      }`}
                    >
                      {drug}
                    </span>
                  ))}
                </div>
              )}

              {/* Consequence */}
              <div className="mb-2 text-xs text-[#1A2421] leading-relaxed">
                <strong className="text-[#5C6B64] font-semibold">Clinical Hazard: </strong>
                {alert.consequence}
              </div>

              {/* Required action */}
              <div className="mb-3 text-xs text-[#1B4D39] bg-[#E8F5E9] border border-[#A5D6A7] rounded-xl p-2.5">
                <strong className="font-bold text-[#1B4D39]">Required Action: </strong>
                {alert.action}
              </div>

              {/* Action Buttons: Absolute Contraindication vs High Override */}
              {isBlock ? (
                <div className="flex items-center gap-1.5 rounded-xl bg-red-100 border border-red-300 px-3 py-1.5 text-[11px] font-mono text-red-900 font-semibold">
                  <Ban className="h-3.5 w-3.5 shrink-0 text-red-700" />
                  <span>
                    ABSOLUTE CONTRAINDICATION: Administration prohibited by safety rule. Override is
                    not permitted.
                  </span>
                </div>
              ) : isHigh ? (
                <div className="flex items-center justify-between gap-2 pt-2 border-t border-[#E1E7E1]">
                  <span className="text-[11px] text-amber-900 font-medium">
                    High clinical hazard. Requires recorded clinician justification.
                  </span>
                  {onOverrideHighAlert && (
                    <button
                      type="button"
                      onClick={() => onOverrideHighAlert(alert.rule_id, stepNumber)}
                      className="px-2.5 py-1 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-900 border border-amber-300 text-xs font-mono font-bold transition-colors shadow-xs"
                    >
                      Override Alert (Step #{stepNumber})...
                    </button>
                  )}
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default AlertsList
