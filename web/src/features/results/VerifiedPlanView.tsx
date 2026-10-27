import React, { useState } from 'react'
import { CheckCircle2, AlertOctagon, AlertTriangle, HelpCircle, FileCheck, ChevronDown, ChevronUp } from 'lucide-react'
import type { VerifiedStep } from '@/lib/api'

interface VerifiedPlanViewProps {
  steps: VerifiedStep[]
}

export const VerifiedPlanView: React.FC<VerifiedPlanViewProps> = ({ steps }) => {
  const [openCitationIdx, setOpenCitationIdx] = useState<number | null>(null)

  if (!steps || steps.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
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
          <span className="flex items-center gap-1 rounded bg-teal-950 border border-teal-800 px-2 py-0.5 text-[11px] font-mono font-bold text-teal-300">
            <CheckCircle2 className="h-3 w-3" /> APPROVED
          </span>
        )
      case 'BLOCKED_STRUCK_THROUGH':
        return (
          <span className="flex items-center gap-1 rounded bg-red-950 border border-red-800 px-2 py-0.5 text-[11px] font-mono font-bold text-red-300">
            <AlertOctagon className="h-3 w-3" /> BLOCKED (STRUCK THROUGH)
          </span>
        )
      case 'FLAGGED_HIGH':
        return (
          <span className="flex items-center gap-1 rounded bg-orange-950 border border-orange-800 px-2 py-0.5 text-[11px] font-mono font-bold text-orange-300">
            <AlertTriangle className="h-3 w-3" /> FLAGGED HIGH
          </span>
        )
      case 'FLAGGED_MODERATE':
        return (
          <span className="flex items-center gap-1 rounded bg-amber-950 border border-amber-800 px-2 py-0.5 text-[11px] font-mono font-bold text-amber-300">
            <AlertTriangle className="h-3 w-3" /> FLAGGED MODERATE
          </span>
        )
      case 'CITATION_UNVERIFIED':
        return (
          <span className="flex items-center gap-1 rounded bg-purple-950 border border-purple-800 px-2 py-0.5 text-[11px] font-mono font-bold text-purple-300">
            <HelpCircle className="h-3 w-3" /> CITATION UNVERIFIED
          </span>
        )
      case 'UNVERIFIED_MISSING_DATA':
      default:
        return (
          <span className="flex items-center gap-1 rounded bg-purple-950 border border-purple-800 px-2 py-0.5 text-[11px] font-mono font-bold text-purple-300">
            <HelpCircle className="h-3 w-3" /> UNVERIFIED
          </span>
        )
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <FileCheck className="h-4 w-4 text-teal-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
            Machine-Verified Protocol Plan ({steps.length} Steps)
          </h3>
        </div>
        <span className="text-[10px] font-mono text-slate-400">Deterministic Verifier Verified</span>
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
              className={`rounded-xl border p-4 transition-colors ${
                isBlocked
                  ? 'border-red-900/70 bg-red-950/20'
                  : isApproved
                  ? 'border-slate-800 bg-slate-900/60'
                  : 'border-amber-900/60 bg-amber-950/20'
              }`}
            >
              {/* Header: step number, action type, status */}
              <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-[11px] font-mono font-bold text-slate-300">
                    {draft.step_number}
                  </span>
                  <span className="font-mono text-xs uppercase px-2 py-0.5 rounded bg-slate-950 text-slate-300 border border-slate-800">
                    {draft.action_type}
                  </span>
                  {draft.drug_id && (
                    <span
                      className={`font-mono text-xs font-bold px-2 py-0.5 rounded ${
                        isBlocked
                          ? 'line-through text-red-400 bg-red-950 border border-red-900'
                          : 'text-teal-300 bg-teal-950 border border-teal-900'
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
                className={`text-xs leading-relaxed my-2 ${
                  isBlocked ? 'line-through text-slate-400 font-medium' : 'text-slate-100 font-normal'
                }`}
              >
                {draft.narrative_instruction}
              </div>

              {/* Rejection reasons if blocked or flagged */}
              {step.rejection_reasons && step.rejection_reasons.length > 0 && (
                <div className="mt-2 rounded-lg bg-red-950/40 border border-red-900/50 p-2.5 text-xs text-red-300">
                  <strong className="text-red-200">Rejection Reason: </strong>
                  {step.rejection_reasons.join('; ')}
                </div>
              )}

              {/* Citations Toggle & Drawer */}
              {hasCitations && (
                <div className="mt-3 border-t border-slate-800/80 pt-2">
                  <button
                    type="button"
                    onClick={() => toggleCitation(idx)}
                    className="flex items-center gap-1.5 text-[11px] font-mono text-teal-400 hover:text-teal-300 transition-colors"
                  >
                    <span>
                      Verbatim Citations ({draft.citations.length} chunk{draft.citations.length > 1 ? 's' : ''})
                    </span>
                    {isCitationOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  </button>

                  {isCitationOpen && (
                    <div className="mt-2 flex flex-col gap-2 rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs">
                      {draft.citations.map((c, cIdx) => (
                        <div key={cIdx} className="flex flex-col gap-1 border-b border-slate-900 pb-2 last:border-0 last:pb-0">
                          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                            <span>
                              Doc: <strong className="text-teal-300">{c.doc_id}</strong> &bull; Chunk: {c.chunk_id}
                            </span>
                            <span>Section: {c.section}</span>
                          </div>
                          <blockquote className="rounded border-l-2 border-teal-500 bg-slate-900/60 p-2 italic text-slate-300 text-[11px]">
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
