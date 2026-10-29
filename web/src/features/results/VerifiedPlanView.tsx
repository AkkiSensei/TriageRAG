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
          <span className="flex items-center gap-1 rounded-full bg-[#E8F5E9] border border-[#A5D6A7] px-2.5 py-0.5 text-[11px] font-mono font-bold text-[#2E7D32]">
            <CheckCircle2 className="h-3 w-3" /> APPROVED
          </span>
        )
      case 'BLOCKED_STRUCK_THROUGH':
        return (
          <span className="flex items-center gap-1 rounded-full bg-red-100 border border-red-300 px-2.5 py-0.5 text-[11px] font-mono font-bold text-red-800">
            <AlertOctagon className="h-3 w-3" /> BLOCKED (STRUCK THROUGH)
          </span>
        )
      case 'FLAGGED_HIGH':
        return (
          <span className="flex items-center gap-1 rounded-full bg-orange-100 border border-orange-300 px-2.5 py-0.5 text-[11px] font-mono font-bold text-orange-900">
            <AlertTriangle className="h-3 w-3" /> FLAGGED HIGH
          </span>
        )
      case 'FLAGGED_MODERATE':
        return (
          <span className="flex items-center gap-1 rounded-full bg-amber-100 border border-amber-300 px-2.5 py-0.5 text-[11px] font-mono font-bold text-amber-900">
            <AlertTriangle className="h-3 w-3" /> FLAGGED MODERATE
          </span>
        )
      case 'REQUIRES_CLINICIAN_CONFIRMATION':
        return (
          <span className="flex items-center gap-1 rounded-full bg-amber-100 border border-amber-400 px-2.5 py-0.5 text-[11px] font-mono font-bold text-amber-950">
            <AlertTriangle className="h-3 w-3" /> REQUIRES CLINICIAN CONFIRMATION
          </span>
        )
      case 'CITATION_UNVERIFIED':
        return (
          <span className="flex items-center gap-1 rounded-full bg-purple-100 border border-purple-300 px-2.5 py-0.5 text-[11px] font-mono font-bold text-purple-900">
            <HelpCircle className="h-3 w-3" /> CITATION UNVERIFIED
          </span>
        )
      case 'UNVERIFIED_MISSING_DATA':
      default:
        return (
          <span className="flex items-center gap-1 rounded-full bg-purple-100 border border-purple-300 px-2.5 py-0.5 text-[11px] font-mono font-bold text-purple-900">
            <HelpCircle className="h-3 w-3" /> UNVERIFIED
          </span>
        )
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-[#E1E7E1] pb-2">
        <div className="flex items-center gap-2">
          <FileCheck className="h-4 w-4 text-[#2D6A4F]" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#1A2421]">
            Machine-Verified Protocol Plan ({steps.length} Steps)
          </h3>
        </div>
        <span className="text-[10px] font-mono text-[#5C6B64]">Deterministic Verifier Verified</span>
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
              className={`rounded-2xl border p-4 transition-colors shadow-xs ${
                isBlocked
                  ? 'border-red-300 bg-red-50/50'
                  : isApproved
                  ? 'border-[#E1E7E1] bg-white'
                  : 'border-amber-300 bg-amber-50/50'
              }`}
            >
              {/* Header: step number, action type, status */}
              <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#EEF3EE] text-[11px] font-mono font-bold text-[#1A2421]">
                    {draft.step_number}
                  </span>
                  <span className="font-mono text-xs uppercase px-2 py-0.5 rounded-md bg-[#F4F6F4] text-[#5C6B64] border border-[#E1E7E1]">
                    {draft.action_type}
                  </span>
                  {draft.drug_id && (
                    <span
                      className={`font-mono text-xs font-bold px-2 py-0.5 rounded-md ${
                        isBlocked
                          ? 'line-through text-red-800 bg-red-100 border border-red-300'
                          : 'text-[#2D6A4F] bg-[#E8F5E9] border border-[#A5D6A7]'
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
                  isBlocked ? 'line-through text-[#8A9991] font-medium' : 'text-[#1A2421] font-normal'
                }`}
              >
                {draft.narrative_instruction}
              </div>

              {/* Rejection reasons if blocked or flagged */}
              {step.rejection_reasons && step.rejection_reasons.length > 0 && (
                <div className="mt-2 rounded-xl bg-red-100 border border-red-200 p-2.5 text-xs text-red-900">
                  <strong className="text-red-950 font-bold">Rejection Reason: </strong>
                  {step.rejection_reasons.join('; ')}
                </div>
              )}

              {/* Citations Toggle & Drawer */}
              {hasCitations && (
                <div className="mt-3 border-t border-[#E1E7E1] pt-2">
                  <button
                    type="button"
                    onClick={() => toggleCitation(idx)}
                    className="flex items-center gap-1.5 text-[11px] font-mono font-bold text-[#2D6A4F] hover:text-[#1B4D39] transition-colors"
                  >
                    <span>
                      Verbatim Citations ({draft.citations.length} chunk{draft.citations.length > 1 ? 's' : ''})
                    </span>
                    {isCitationOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  </button>

                  {isCitationOpen && (
                    <div className="mt-2 flex flex-col gap-2 rounded-xl border border-[#E1E7E1] bg-[#F4F6F4] p-3 text-xs">
                      {draft.citations.map((c, cIdx) => (
                        <div key={cIdx} className="flex flex-col gap-1 border-b border-[#E1E7E1] pb-2 last:border-0 last:pb-0">
                          <div className="flex items-center justify-between text-[10px] font-mono text-[#5C6B64]">
                            <span>
                              Doc: <strong className="text-[#2D6A4F]">{c.doc_id}</strong> &bull; Chunk: {c.chunk_id}
                            </span>
                            <span>Section: {c.section}</span>
                          </div>
                          <blockquote className="rounded-lg border-l-2 border-[#2D6A4F] bg-white p-2.5 italic text-[#1A2421] text-[11px] shadow-xs">
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

