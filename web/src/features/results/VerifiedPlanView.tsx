import React, { useState } from 'react'
import {
  CheckCircle2,
  AlertOctagon,
  AlertTriangle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Quote,
  ShieldAlert,
} from 'lucide-react'
import type { VerifiedStep } from '@/lib/api'

interface VerifiedPlanViewProps {
  steps: VerifiedStep[]
}

export const VerifiedPlanView: React.FC<VerifiedPlanViewProps> = ({ steps }) => {
  const [openCitationIdx, setOpenCitationIdx] = useState<number | null>(null)

  if (!steps || steps.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 text-xs text-slate-500 dark:text-slate-400 shadow-soft">
        No protocol orders were generated or verified for this case.
      </div>
    )
  }

  const toggleCitation = (idx: number) => {
    setOpenCitationIdx(openCitationIdx === idx ? null : idx)
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span
            title="Passed all configured deterministic formulary, dose ceiling, and citation checks."
            className="flex items-center gap-1.5 rounded-full bg-teal-100 dark:bg-teal-950/70 border border-teal-300 dark:border-teal-700 px-3 py-1 text-[11px] font-mono font-bold text-teal-900 dark:text-teal-200 shadow-soft-sm"
          >
            <CheckCircle2 className="h-3.5 w-3.5 text-teal-700 dark:text-teal-400" />
            <span>Passed Configured Software Checks</span>
          </span>
        )
      case 'BLOCKED_STRUCK_THROUGH':
        return (
          <span
            title="Prohibited by a deterministic BLOCK rule. Cannot be approved or overridden."
            className="flex items-center gap-1.5 rounded-full bg-rose-100 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-700 px-3 py-1 text-[11px] font-mono font-bold text-rose-900 dark:text-rose-200 shadow-soft-sm"
          >
            <AlertOctagon className="h-3.5 w-3.5 text-rose-700 dark:text-rose-400" />
            <span>Blocked by Configured Rule</span>
          </span>
        )
      case 'FLAGGED_HIGH':
        return (
          <span
            title="High-severity safety warning. Requires logged clinician override rationale."
            className="flex items-center gap-1.5 rounded-full bg-amber-100 dark:bg-amber-950/70 border border-amber-300 dark:border-amber-700 px-3 py-1 text-[11px] font-mono font-bold text-amber-950 dark:text-amber-200 shadow-soft-sm"
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-700 dark:text-amber-400" />
            <span>High-Severity Warning</span>
          </span>
        )
      case 'FLAGGED_MODERATE':
        return (
          <span
            title="Moderate clinical alert requiring careful review."
            className="flex items-center gap-1.5 rounded-full bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800 px-3 py-1 text-[11px] font-mono font-bold text-amber-900 dark:text-amber-300"
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
            <span>Moderate Warning</span>
          </span>
        )
      case 'REQUIRES_CLINICIAN_CONFIRMATION':
        return (
          <span
            title="ADR-0007: Protocol was inferred from vitals rather than clinician selection. Requires explicit confirmation."
            className="flex items-center gap-1.5 rounded-full bg-amber-100 dark:bg-amber-950/70 border border-amber-400 dark:border-amber-700 px-3 py-1 text-[11px] font-mono font-bold text-amber-950 dark:text-amber-200"
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
            <span>Requires Clinician Confirmation</span>
          </span>
        )
      case 'CITATION_UNVERIFIED':
        return (
          <span
            title="Action could not be verified against verbatim text in retrieved protocol."
            className="flex items-center gap-1.5 rounded-full bg-purple-100 dark:bg-purple-950/70 border border-purple-300 dark:border-purple-700 px-3 py-1 text-[11px] font-mono font-bold text-purple-900 dark:text-purple-200"
          >
            <HelpCircle className="h-3.5 w-3.5 text-purple-700 dark:text-purple-400" />
            <span>Citation Unverified</span>
          </span>
        )
      case 'UNVERIFIED_MISSING_DATA':
      default:
        return (
          <span
            title="Essential patient parameters missing for verification."
            className="flex items-center gap-1.5 rounded-full bg-purple-100 dark:bg-purple-950/70 border border-purple-300 dark:border-purple-700 px-3 py-1 text-[11px] font-mono font-bold text-purple-900 dark:text-purple-200"
          >
            <HelpCircle className="h-3.5 w-3.5 text-purple-700 dark:text-purple-400" />
            <span>Required Data Missing</span>
          </span>
        )
    }
  }

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-col gap-3">
        {steps.map((step, idx) => {
          const draft = step.draft
          const isBlocked = step.status === 'BLOCKED_STRUCK_THROUGH'
          const isPassed = step.status === 'APPROVED'

          return (
            <div
              key={draft.step_number || idx}
              className={`rounded-2xl border p-4 sm:p-5 shadow-soft transition-all ${
                isBlocked
                  ? 'border-rose-200 dark:border-rose-900/60 bg-rose-50/40 dark:bg-rose-950/20'
                  : isPassed
                  ? 'border-teal-200 dark:border-[#1e3840] bg-white dark:bg-[#132226]'
                  : 'border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226]'
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 mb-3 border-b border-slate-100 dark:border-slate-800 pb-3">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-slate-100 dark:bg-[#0c1618] font-mono text-xs font-bold text-slate-800 dark:text-slate-200">
                    {draft.step_number}
                  </span>
                  <span className="font-mono text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                    Action: {draft.action_type}
                  </span>
                </div>
                {getStatusBadge(step.status)}
              </div>

              {/* Narrative Instruction */}
              <div className="mb-3">
                <p
                  className={`text-xs sm:text-sm font-sans leading-relaxed ${
                    isBlocked
                      ? 'text-rose-900 dark:text-rose-200 line-through decoration-rose-500 decoration-2'
                      : 'text-slate-900 dark:text-slate-100'
                  }`}
                >
                  {draft.narrative_instruction}
                </p>

                {draft.requested_dose && (
                  <div className="mt-2 inline-flex items-center gap-2 text-[11px] font-mono px-2.5 py-1 rounded-md bg-slate-100 dark:bg-[#0c1618] text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800">
                    <span className="font-bold text-teal-700 dark:text-teal-400">Order:</span>
                    <span>
                      {draft.requested_dose.amount} {draft.requested_dose.unit}
                      {draft.route ? ` (${draft.route})` : ''}
                    </span>
                  </div>
                )}
              </div>

              {/* Rejection Reasons if rejected */}
              {step.rejection_reasons && step.rejection_reasons.length > 0 && (
                <div className="mb-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 p-3 text-xs text-rose-900 dark:text-rose-200">
                  <div className="flex items-center gap-1.5 font-bold mb-1">
                    <ShieldAlert className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" />
                    <span>Safety Interlock Triggered:</span>
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 font-sans">
                    {step.rejection_reasons.map((r, rIdx) => (
                      <li key={rIdx}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Citations Footer */}
              {draft.citations && draft.citations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 flex flex-col gap-2">
                  <button
                    type="button"
                    onClick={() => toggleCitation(idx)}
                    className="flex items-center justify-between text-[11px] font-mono text-teal-700 dark:text-teal-300 hover:underline"
                  >
                    <div className="flex items-center gap-1.5">
                      <Quote className="h-3.5 w-3.5" />
                      <span>
                        Citations ({draft.citations.length}) &bull; Overlap:{' '}
                        {step.citation_overlap_score
                          ? `${(Number(step.citation_overlap_score) * 100).toFixed(0)}%`
                          : '0%'}
                      </span>
                    </div>
                    {openCitationIdx === idx ? (
                      <ChevronUp className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5" />
                    )}
                  </button>

                  {openCitationIdx === idx && (
                    <div className="flex flex-col gap-2 pt-1 text-xs">
                      {draft.citations.map((c, cIdx) => (
                        <div
                          key={cIdx}
                          className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#0c1618] p-3 font-mono text-[11px]"
                        >
                          <div className="flex items-center justify-between text-slate-500 mb-1">
                            <span className="font-bold text-slate-800 dark:text-slate-200">{c.doc_id}</span>
                            <span>{c.chunk_id}</span>
                          </div>
                          <p className="text-slate-700 dark:text-slate-300 font-serif italic text-xs">
                            &ldquo;{c.quoted_span}&rdquo;
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default VerifiedPlanView
