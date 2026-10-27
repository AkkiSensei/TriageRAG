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
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
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
          <ShieldAlert className="h-4 w-4 text-amber-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
            Safety Alerts & Contraindications ({alerts.length})
          </h3>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {alerts.map((alert, idx) => {
          const isBlock = alert.severity === 'BLOCK'
          const isHigh = alert.severity === 'HIGH'
          const isModerate = alert.severity === 'MODERATE'

          let cardBorder = 'border-slate-800 bg-slate-900/80'
          let severityBadge = 'border-blue-900/60 bg-blue-950/40 text-blue-300'
          let SeverityIcon = Info

          if (isBlock) {
            cardBorder = 'border-red-900/80 bg-red-950/30'
            severityBadge = 'border-red-900/80 bg-red-950 text-red-400 font-bold'
            SeverityIcon = AlertOctagon
          } else if (isHigh) {
            cardBorder = 'border-amber-900/80 bg-amber-950/30'
            severityBadge = 'border-amber-900/80 bg-amber-950 text-amber-400 font-bold'
            SeverityIcon = AlertTriangle
          } else if (isModerate) {
            cardBorder = 'border-amber-900/50 bg-slate-900'
            severityBadge = 'border-amber-900/40 bg-amber-950/30 text-amber-300'
            SeverityIcon = AlertTriangle
          }

          const isDraftProvenance =
            alert.provenance?.source_status === 'PLACEHOLDER_UNRETRIEVED' ||
            !alert.provenance?.verified

          const stepNumber = findMatchingStepNumber(alert.rule_id)

          return (
            <div key={`${alert.rule_id}-${idx}`} className={`rounded-xl border p-4 ${cardBorder}`}>
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono border ${severityBadge}`}
                  >
                    <SeverityIcon className="h-3 w-3" />
                    {alert.severity}
                  </span>
                  <span className="font-mono text-xs font-semibold text-slate-200">
                    {alert.rule_id}
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">({alert.rule_type})</span>
                </div>

                {isDraftProvenance && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono border border-amber-900/60 bg-amber-950/60 text-amber-300 uppercase">
                    Draft Rule Formulation
                  </span>
                )}
              </div>

              {/* Target drugs */}
              {alert.drug_ids && alert.drug_ids.length > 0 && (
                <div className="mb-2 flex items-center gap-2 flex-wrap text-xs">
                  <span className="text-slate-400">Target Agent(s):</span>
                  {alert.drug_ids.map((drug) => (
                    <span
                      key={drug}
                      className={`font-mono px-2 py-0.5 rounded text-xs font-bold ${
                        isBlock
                          ? 'line-through text-red-400 bg-red-950/80 border border-red-900/80'
                          : 'text-amber-300 bg-amber-950/60 border border-amber-900/60'
                      }`}
                    >
                      {drug}
                    </span>
                  ))}
                </div>
              )}

              {/* Consequence */}
              <div className="mb-2 text-xs text-slate-200 leading-relaxed">
                <strong className="text-slate-400 font-medium">Clinical Hazard: </strong>
                {alert.consequence}
              </div>

              {/* Required action */}
              <div className="mb-3 text-xs text-teal-300 bg-teal-950/30 border border-teal-900/40 rounded-lg p-2.5">
                <strong className="font-semibold text-teal-200">Required Action: </strong>
                {alert.action}
              </div>

              {/* Action Buttons: Absolute Contraindication vs High Override */}
              {isBlock ? (
                <div className="flex items-center gap-1.5 rounded bg-red-950/80 border border-red-900/80 px-3 py-1.5 text-[11px] font-mono text-red-300">
                  <Ban className="h-3.5 w-3.5 shrink-0" />
                  <span>
                    ABSOLUTE CONTRAINDICATION: Administration prohibited by safety rule. Override is
                    not permitted.
                  </span>
                </div>
              ) : isHigh ? (
                <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-800/80">
                  <span className="text-[11px] text-amber-300/80">
                    High clinical hazard. Requires recorded clinician justification.
                  </span>
                  {onOverrideHighAlert && (
                    <button
                      type="button"
                      onClick={() => onOverrideHighAlert(alert.rule_id, stepNumber)}
                      className="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-mono font-medium transition-colors"
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
