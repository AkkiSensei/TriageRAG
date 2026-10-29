import React, { useState } from 'react'
import { AlertTriangle, BookOpen, ChevronDown, ChevronUp, Database, Search } from 'lucide-react'
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

  const abstainCode = retrieval?.abstain_code ?? (retrieval?.abstained ? 'ABSTAINED' : 'NONE')
  const corpusHash = retrieval?.corpus_hash
    ? `${retrieval.corpus_hash.slice(0, 12)}...`
    : 'N/A'

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
            <BookOpen className="h-4 w-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Protocol Context &amp; Retrieval Evidence
            </span>
            {protocolTitle && (
              <span className="text-xs text-teal-700 font-mono font-bold">{protocolTitle}</span>
            )}
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1.5 text-xs font-mono font-semibold text-slate-600 hover:text-teal-800 transition-colors bg-slate-50 border border-slate-200 px-3 py-1 rounded-xl shadow-soft-sm"
        >
          <span>{retrieval?.chunks?.length ?? 0} Chunks</span>
          {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
      </div>

      {retrieval?.abstained && (
        <div className="mt-3.5 flex items-start gap-2.5 rounded-xl bg-amber-50 border border-amber-300 p-3.5 text-xs text-amber-950 shadow-soft-sm">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700 mt-0.5" />
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2 font-mono font-bold">
              <span>Retrieval Abstained</span>
              <span className="rounded-lg bg-amber-200 px-2 py-0.5 text-[10px] text-amber-900 border border-amber-300">
                {abstainCode}
              </span>
            </div>
            <span>{retrieval.reason ?? 'No protocol met retrieval safety gating criteria.'}</span>
          </div>
        </div>
      )}

      {triage.llm_fallback_mode && (
        <div className="mt-3.5 flex items-center gap-2.5 rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 shadow-soft-sm">
          <Database className="h-4 w-4 shrink-0 text-amber-700" />
          <span>LLM Fallback Mode Active: Full deterministic safety engine rendered without LLM drafting.</span>
        </div>
      )}

      {isOpen && retrieval && (
        <div className="mt-3.5 flex flex-col gap-3 pt-2">
          <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3.5 text-[11px] font-mono text-slate-600">
            <div className="flex items-center gap-1.5 font-bold text-slate-900 mb-1.5">
              <Search className="h-3.5 w-3.5 text-teal-700" />
              <span>Retrieval Inspector Diagnostics</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              <div>
                <span className="font-semibold text-slate-500">Query:</span>{' '}
                <span className="text-slate-800">{retrieval.query || '(none)'}</span>
              </div>
              <div>
                <span className="font-semibold text-slate-500">Abstain Code:</span>{' '}
                <span className="text-slate-800">{abstainCode}</span>
              </div>
              <div>
                <span className="font-semibold text-slate-500">Backend:</span>{' '}
                <span className="text-slate-800">{retrieval.backend ?? 'bm25'} (v{retrieval.index_version ?? '2.0.0'})</span>
              </div>
              <div>
                <span className="font-semibold text-slate-500">Corpus SHA-256:</span>{' '}
                <span title={retrieval.corpus_hash} className="text-slate-800">{corpusHash}</span>
              </div>
              {retrieval.skipped_flags && retrieval.skipped_flags.length > 0 && (
                <div className="sm:col-span-2 mt-1">
                  <span className="font-semibold text-slate-500">Skipped Flags:</span>{' '}
                  <span className="text-amber-800">{retrieval.skipped_flags.join(', ')}</span>
                </div>
              )}
            </div>
          </div>

          {retrieval.chunks?.map((chunk, idx) => (
            <div key={idx} className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs shadow-soft-sm">
              <div className="flex items-center justify-between mb-2 flex-wrap gap-2 text-[10px] font-mono">
                <span className="text-teal-800 font-bold bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                  {chunk.chunk_id}
                </span>
                <span className="rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-amber-800 font-bold">
                  SYNTHETIC CORPUS
                </span>
                <span className="text-slate-400">
                  Score: {chunk.score !== undefined && chunk.score !== null ? String(chunk.score) : 'N/A'}
                </span>
              </div>
              <p className="text-slate-800 font-serif leading-relaxed italic text-xs bg-slate-50/70 p-3 rounded-xl border border-slate-200/80">
                &ldquo;{chunk.text}&rdquo;
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default RetrievalView
