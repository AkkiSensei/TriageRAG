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
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-teal-400" />
          <div className="flex flex-col">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Protocol Context & Retrieval Evidence
            </span>
            {protocolTitle && (
              <span className="text-xs text-teal-300 font-mono font-medium">{protocolTitle}</span>
            )}
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1 text-xs font-mono text-slate-400 hover:text-slate-200"
        >
          <span>{retrieval?.chunks?.length ?? 0} Chunks</span>
          {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
      </div>

      {triage.llm_fallback_mode && (
        <div className="mt-3 flex items-center gap-2 rounded bg-amber-950/40 border border-amber-900/50 p-2 text-xs text-amber-300">
          <Database className="h-3.5 w-3.5 shrink-0" />
          <span>LLM Fallback Mode Active: Full deterministic safety engine rendered without LLM drafting.</span>
        </div>
      )}

      {isOpen && retrieval?.chunks && (
        <div className="mt-3 flex flex-col gap-2 pt-2">
          {retrieval.chunks.map((chunk, idx) => (
            <div key={idx} className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs">
              <div className="flex items-center justify-between mb-1.5 flex-wrap gap-2 text-[10px] font-mono">
                <span className="text-teal-400 font-semibold">{chunk.chunk_id}</span>
                <span className="rounded bg-teal-950 border border-teal-800 px-1.5 py-0.5 text-teal-300">
                  SYNTHETIC CORPUS
                </span>
                <span className="text-slate-400">Score: {chunk.score !== undefined && chunk.score !== null ? String(chunk.score) : 'N/A'}</span>
              </div>
              <p className="text-slate-300 font-serif leading-relaxed italic text-[11px] bg-slate-900/40 p-2 rounded border border-slate-800/80">
                &ldquo;{chunk.text}&rdquo;
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
