import React, { useState } from 'react'
import {
  CheckCircle2,
  AlertOctagon,
  AlertTriangle,
  HelpCircle,
  FileCheck,
  ChevronDown,
  ChevronUp,
  Quote,
} from 'lucide-react'
import type { VerifiedStep } from '@/lib/api'

interface VerifiedPlanViewProps {
  steps: VerifiedStep[]
}

export const VerifiedPlanView: React.FC<VerifiedPlanViewProps> = ({ steps }) => {
  const [openCitationIdx, setOpenCitationIdx] = useState<number | null>(null)

  if (!steps || steps.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 text-xs text-slate-500 shadow-soft">
        No machine-verified plan steps generated.
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
          <span className="flex items-center gap-1 rounded-full bg-teal-100 border border-teal-300 px-3 py-0.5 text-[11px] font-mono font-bold text-teal-900 shadow-soft-sm">
            <CheckCircle2 className="h-3 w-3 text-teal-700" /> APPROVED
          </span>
        )
      case 'BLOCKED_STRUCK_THROUGH':
        return (
          <span className="flex items-center gap-1 rounded-full bg-rose-100 border border-rose-300 px-3 py-0.5 text-[11px] font-mono font-bold text-rose-900 shadow-soft-sm">
            <AlertOctagon className="h-3 w-3 text-rose-700" /> BLOCKED (STRUCK THROUGH)
          </span>
        )
      case 'FLAGGED_HIGH':
        return (
          <span className="flex items-center gap-1 rounded-full bg-amber-100 border border-amber-300 px-3 py-0.5 text-[11px] font-mono font-bold text-amber-950 shadow-soft-sm">
            <AlertTriangle className="h-3 w-3 text-amber-700" /> FLAGGED HIGH
          </span>
        )
      case 'FLAGGED_MODERATE':
        return (
          <span className="flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-3 py-0.5 text-[11px] font-mono font-bold text-amber-900">
            <AlertTriangle className="h-3 w-3 text-amber-600" /> FLAGGED MODERATE
          </span>
        )
      case 'REQUIRES_CLINICIAN_CONFIRMATION':
        return (
          <span className="flex items-center gap-1 rounded-full bg-amber-100 border border-amber-400 px-3 py-0.5 text-[11px] font-mono font-bold text-amber-950">
            <AlertTriangle className="h-3 w-3" /> REQUIRES CONFIRMATION
          </span>
        )
      case 'CITATION_UNVERIFIED':
        return (
          <span className="flex items-center gap-1 rounded-full bg-violet-100 border border-violet-300 px-3 py-0.5 text-[11px] font-mono font-bold text-violet-900">
            <HelpCircle className="h-3 w-3 text-violet-700" /> CITATION UNVERIFIED
          </span>
        )
      case 'UNVERIFIED_MISSING_DATA':
      default:
        return (
          <span className="flex items-center gap-1 rounded-full bg-violet-100 border border-violet-300 px-3 py-0.5 text-[11px] font-mono font-bold text-violet-900">
            <HelpCircle className="h-3 w-3 text-violet-700" /> UNVERIFIED
          </span>
        )
    }
  }

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
        <div className="flex items-center gap-2">
          <FileCheck className="h-4 w-4 text-teal-700" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
            Machine-Verified Protocol Orders ({steps.length} Steps)
          </h3>
        </div>
        <span className="text-[11px] font-mono text-teal-800 font-semibold bg-teal-50 px-2.5 py-0.5 rounded-full border border-teal-200">
          Pass 2 Machine Gate Verified
        </span>
      </div>

      <div className="flex flex-col gap-3">
        {steps.map((step, idx) => {
          const draft = step.draft
          const isBlocked = step.status === 'BLOCKED_STRUCK_THROUGH'
          const isApproved = step.status === 'APPROVED'
          const hasCitations = draft.citations && draft.citations.length > 0
          const isCitationOpen = openCitationIdx === idx

          return (
            <div
              key={`${draft.step_number}-${idx}`}
              className={`rounded-2xl border p-4 sm:p-5 transition-all shadow-soft ${
                isBlocked
                  ? 'border-rose-300/80 bg-rose-50/40'
                  : isApproved
                  ? 'border-[#d9e8e6] bg-white'
                  : 'border-amber-300/80 bg-amber-50/40'
              }`}
            >
              {/* Header: step number, action type, status */}
              <div className="flex items-center justify-between gap-2 flex-wrap mb-2.5">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-xl bg-teal-50 text-[11px] font-mono font-bold text-teal-800 border border-teal-200">
                    {draft.step_number}
                  </span>
                  <span className="font-mono text-xs uppercase px-2.5 py-0.5 rounded-lg bg-slate-100 text-slate-700 border border-slate-200 font-semibold">
                    {draft.action_type}
                  </span>
                  {draft.drug_id && (
                    <span
                      className={`font-mono text-xs font-bold px-2.5 py-0.5 rounded-lg ${
                        isBlocked
                          ? 'line-through text-rose-900 bg-rose-100 border border-rose-300'
                          : 'text-teal-900 bg-teal-100 border border-teal-300'
                      }`}
                    >
                      {draft.drug_id}
                    </span>
                  )}
                </div>
                <div>{getStatusBadge(step.status)}</div>
              </div>

              {/* Narrative Instruction */}
              <div
                className={`text-xs sm:text-sm leading-relaxed my-2 ${
                  isBlocked ? 'line-through text-slate-400 font-medium' : 'text-slate-800 font-normal'
                }`}
              >
                {draft.narrative_instruction}
              </div>

              {/* Rejection reasons if blocked or flagged */}
              {step.rejection_reasons && step.rejection_reasons.length > 0 && (
                <div className="mt-2.5 rounded-xl bg-rose-100 border border-rose-200 p-3 text-xs text-rose-950 font-medium leading-relaxed">
                  <strong className="text-rose-900 font-bold">Rejection Reason: </strong>
                  {step.rejection_reasons.join('; ')}
                </div>
              )}

              {/* Citations Toggle & Drawer */}
              {hasCitations && (
                <div className="mt-3 border-t border-slate-100 pt-2.5">
                  <button
                    type="button"
                    onClick={() => toggleCitation(idx)}
                    className="flex items-center gap-1.5 text-xs font-mono font-bold text-teal-700 hover:text-teal-900 transition-colors"
                  >
                    <Quote className="h-3.5 w-3.5 text-teal-600" />
                    <span>
                      Verbatim Protocol Citations ({draft.citations.length} chunk{draft.citations.length > 1 ? 's' : ''})
                    </span>
                    {isCitationOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>

                  {isCitationOpen && (
                    <div className="mt-2.5 flex flex-col gap-2.5 rounded-xl border border-teal-200 bg-teal-50/40 p-3.5 text-xs">
                      {draft.citations.map((c, cIdx) => (
                        <div key={cIdx} className="flex flex-col gap-1 border-b border-teal-100 pb-2.5 last:border-0 last:pb-0">
                          <div className="flex items-center justify-between text-[11px] font-mono text-slate-600">
                            <span>
                              Guideline: <strong className="text-teal-900">{c.doc_id}</strong> &bull; Chunk: {c.chunk_id}
                            </span>
                            <span className="text-slate-400">Section: {c.section}</span>
                          </div>
                          <blockquote className="rounded-xl border-l-4 border-teal-600 bg-white p-3 italic text-slate-800 text-xs shadow-soft-sm leading-relaxed">
                            &ldquo;{c.quoted_span}&rdquo;
                          </blockquote>
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
