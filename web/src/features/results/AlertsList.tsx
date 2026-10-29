import React from 'react'
import { AlertOctagon, AlertTriangle, Info, ShieldAlert, Ban, Sparkles } from 'lucide-react'
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
      <div className="rounded-2xl border border-[#d9e8e6] dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 text-xs text-slate-500 dark:text-slate-400 shadow-soft">
        <div className="flex items-center gap-2 text-teal-800 dark:text-teal-300 font-semibold">
          <Sparkles className="h-4 w-4 text-teal-600 dark:text-teal-400" />
          <span>No active clinical safety alerts or contraindications triggered.</span>
        </div>
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
    <div className="flex flex-col gap-3.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
            <ShieldAlert className="h-4 w-4" />
          </div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-100">
            Safety Alerts &amp; Contraindications ({alerts.length})
          </h3>
        </div>
        <span className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
          Ranked by Clinical Acuity
        </span>
      </div>

      <div className="flex flex-col gap-3">
        {alerts.map((alert, idx) => {
          const isBlock = alert.severity === 'BLOCK'
          const isHigh = alert.severity === 'HIGH'
          const isModerate = alert.severity === 'MODERATE'

          let cardBorder = 'border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] shadow-soft'
          let severityBadge = 'border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/60 text-sky-800 dark:text-sky-300 font-bold'
          let SeverityIcon = Info

          if (isBlock) {
            cardBorder = 'border-rose-200/90 dark:border-rose-900/60 bg-gradient-to-r from-rose-50/40 dark:from-rose-950/30 via-white dark:via-[#132226] to-white dark:to-[#132226] shadow-soft'
            severityBadge = 'border-rose-300 dark:border-rose-700 bg-rose-100 dark:bg-rose-950/70 text-rose-900 dark:text-rose-200 font-extrabold'
            SeverityIcon = AlertOctagon
          } else if (isHigh) {
            cardBorder = 'border-amber-200/90 dark:border-amber-900/60 bg-gradient-to-r from-amber-50/40 dark:from-amber-950/30 via-white dark:via-[#132226] to-white dark:to-[#132226] shadow-soft'
            severityBadge = 'border-amber-300 dark:border-amber-700 bg-amber-100 dark:bg-amber-950/70 text-amber-900 dark:text-amber-200 font-bold'
            SeverityIcon = AlertTriangle
          } else if (isModerate) {
            cardBorder = 'border-amber-200 dark:border-amber-800/60 bg-white dark:bg-[#132226] shadow-soft-sm'
            severityBadge = 'border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 font-semibold'
            SeverityIcon = AlertTriangle
          }

          const isDraftProvenance =
            alert.provenance?.source_status === 'PLACEHOLDER_UNRETRIEVED' ||
            !alert.provenance?.verified

          const stepNumber = findMatchingStepNumber(alert.rule_id)

          return (
            <div key={`${alert.rule_id}-${idx}`} className={`rounded-2xl border p-4 sm:p-5 ${cardBorder}`}>
              <div className="flex items-start justify-between gap-3 mb-2.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`flex items-center gap-1 px-3 py-1 rounded-full text-[11px] font-mono border shadow-soft-sm ${severityBadge}`}
                  >
                    <SeverityIcon className="h-3.5 w-3.5" />
                    {alert.severity}
                  </span>
                  <span className="font-mono text-xs font-extrabold text-slate-900 dark:text-slate-100">
                    {alert.rule_id}
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">({alert.rule_type})</span>
                </div>

                {isDraftProvenance && (
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 uppercase font-semibold">
                    Draft Rule Formulation
                  </span>
                )}
              </div>

              {/* Target drugs */}
              {alert.drug_ids && alert.drug_ids.length > 0 && (
                <div className="mb-2.5 flex items-center gap-2 flex-wrap text-xs">
                  <span className="text-slate-500 dark:text-slate-400 font-medium">Target Agent(s):</span>
                  {alert.drug_ids.map((drug) => (
                    <span
                      key={drug}
                      className={`font-mono px-2.5 py-0.5 rounded-lg text-xs font-bold ${
                        isBlock
                          ? 'line-through text-rose-800 dark:text-rose-200 bg-rose-100 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-700 shadow-soft-sm'
                          : 'text-amber-950 dark:text-amber-200 bg-amber-100 dark:bg-amber-950/70 border border-amber-300 dark:border-amber-700'
                      }`}
                    >
                      {drug}
                    </span>
                  ))}
                </div>
              )}

              {/* Consequence */}
              <div className="mb-2 text-xs text-slate-800 dark:text-slate-200 leading-relaxed">
                <strong className="text-slate-600 dark:text-slate-400 font-semibold">Clinical Hazard: </strong>
                {alert.consequence}
              </div>

              {/* Required action */}
              <div className="mb-3 text-xs text-teal-950 dark:text-teal-100 bg-teal-50/80 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800/80 rounded-xl p-3">
                <strong className="font-bold text-teal-900 dark:text-teal-200">Required Action: </strong>
                {alert.action}
              </div>

              {/* Action Buttons: Absolute Contraindication vs High Override */}
              {isBlock ? (
                <div className="flex items-center gap-2 rounded-xl bg-rose-100 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800/80 px-3.5 py-2 text-[11px] font-mono text-rose-950 dark:text-rose-200 font-semibold">
                  <Ban className="h-4 w-4 shrink-0 text-rose-700 dark:text-rose-400" />
                  <span>
                    RULE R11 INVIOLABLE: Administration prohibited by safety rule. Zero override code path exists.
                  </span>
                </div>
              ) : isHigh ? (
                <div className="flex items-center justify-between gap-2 pt-2.5 border-t border-slate-100 dark:border-[#1e3840]">
                  <span className="text-[11px] text-amber-950 dark:text-amber-300 font-medium">
                    High clinical hazard. Requires recorded clinician justification (&ge; 15 chars).
                  </span>
                  {onOverrideHighAlert && (
                    <button
                      type="button"
                      onClick={() => onOverrideHighAlert(alert.rule_id, stepNumber)}
                      className="px-3 py-1.5 rounded-xl bg-amber-100 hover:bg-amber-200 dark:bg-amber-950/80 dark:hover:bg-amber-900 text-amber-950 dark:text-amber-200 border border-amber-300 dark:border-amber-700 text-xs font-mono font-bold transition-colors shadow-soft-sm"
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
