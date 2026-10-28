import React, { useState } from 'react'
import { BookOpen, ChevronDown, ChevronUp, Database } from 'lucide-react'
import type { TriageResponse } from '@/lib/api'

interface RetrievalViewProps {
  triage: TriageResponse
}

export const RetrievalView: React.FC<RetrievalViewProps> = ({ triage }) => {
  const [isOpen, setIsOpen] = useState(false)
  const retrieval = triage.retrieval
  const protocolTitle = triage.retrieved_protocol_title

  if (!retrieval && !protocolTitle) {
    return null
  }

  return (
    <div className="rounded-2xl border border-[#E1E7E1] bg-white p-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#E1E7E1] pb-3">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-[#2D6A4F]" />
          <div className="flex flex-col">
            <span className="text-xs font-bold uppercase tracking-wider text-[#1A2421]">
              Protocol Context & Retrieval Evidence
            </span>
            {protocolTitle && (
              <span className="text-xs text-[#2D6A4F] font-mono font-bold">{protocolTitle}</span>
            )}
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1 text-xs font-mono font-semibold text-[#5C6B64] hover:text-[#1A2421]"
        >
          <span>{retrieval?.chunks?.length ?? 0} Chunks</span>
          {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
      </div>

      {triage.llm_fallback_mode && (
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200 p-2.5 text-xs text-amber-900 shadow-xs">
          <Database className="h-3.5 w-3.5 shrink-0 text-amber-700" />
          <span>LLM Fallback Mode Active: Full deterministic safety engine rendered without LLM drafting.</span>
        </div>
      )}

      {isOpen && retrieval?.chunks && (
        <div className="mt-3 flex flex-col gap-2 pt-2">
          {retrieval.chunks.map((chunk, idx) => (
            <div key={idx} className="rounded-xl border border-[#E1E7E1] bg-[#F4F6F4] p-3 text-xs shadow-xs">
              <div className="flex items-center justify-between mb-1.5 flex-wrap gap-2 text-[10px] font-mono">
                <span className="text-[#2D6A4F] font-bold">{chunk.chunk_id}</span>
                <span className="rounded-full bg-[#E8F5E9] border border-[#A5D6A7] px-2 py-0.5 text-[#2E7D32] font-bold">
                  SYNTHETIC CORPUS
                </span>
                <span className="text-[#5C6B64]">Score: {chunk.score !== undefined && chunk.score !== null ? String(chunk.score) : 'N/A'}</span>
              </div>
              <p className="text-[#1A2421] font-serif leading-relaxed italic text-[11px] bg-white p-2.5 rounded-lg border border-[#E1E7E1] shadow-xs">
                &ldquo;{chunk.text}&rdquo;
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

