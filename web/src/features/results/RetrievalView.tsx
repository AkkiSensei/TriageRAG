import React, { useState } from 'react'
import {
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Database,
  Search,
  Info,
} from 'lucide-react'
import type { TriageResponse } from '@/lib/api'

interface RetrievalViewProps {
  triage: TriageResponse
}

export const RetrievalView: React.FC<RetrievalViewProps> = ({ triage }) => {
  const [isOpen, setIsOpen] = useState(true)
  const [showHowItWorks, setShowHowItWorks] = useState(false)
  const retrieval = triage.retrieval
  const protocolTitle = triage.retrieved_protocol_title

  if (!retrieval && !protocolTitle) {
    return null
  }

  const abstainCode = retrieval?.abstain_code ?? (retrieval?.abstained ? 'ABSTAINED' : 'NONE')
  const corpusHash = retrieval?.corpus_hash
    ? `${retrieval.corpus_hash.slice(0, 12)}...`
    : 'N/A'
  const chunks = retrieval?.chunks || []

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 shadow-soft transition-all">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-[#1e3840] pb-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <BookOpen className="h-4 w-4" />
          </div>
          <div className="flex flex-col">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-100">
              Protocol Context &amp; Evidence Grounding
            </h3>
            {protocolTitle && (
              <span className="text-xs text-teal-700 dark:text-teal-300 font-mono font-bold">{protocolTitle}</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowHowItWorks(!showHowItWorks)}
            className="flex items-center gap-1 text-[11px] font-mono text-teal-700 dark:text-teal-300 hover:underline px-2 py-1 rounded"
          >
            <Info className="h-3 w-3" />
            <span>How Retrieval Worked</span>
          </button>
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="flex items-center gap-1.5 text-xs font-mono font-semibold text-slate-600 dark:text-slate-300 hover:text-teal-800 dark:hover:text-teal-200 transition-colors bg-slate-50 dark:bg-[#0c1618] border border-slate-200 dark:border-[#1e3840] px-3 py-1 rounded-xl shadow-soft-sm"
          >
            <span>{chunks.length} Chunks</span>
            {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Explanatory callout: BM25 score is lexical ranking, not clinical confidence */}
      <div className="mb-4 rounded-xl border border-teal-100 dark:border-teal-900/50 bg-teal-50/60 dark:bg-teal-950/20 p-3 text-[11px] text-slate-700 dark:text-slate-300 flex items-start gap-2">
        <Info className="h-4 w-4 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
        <span className="leading-relaxed">
          <strong>Lexical Ranking Disclosure:</strong> Retrieval scores represent relative token term-matching against
          the synthetic emergency protocol index using the <strong>{retrieval?.backend?.toUpperCase() || 'BM25'}</strong> backend.
          Scores are ranking values, not probabilities of clinical correctness.
        </span>
      </div>

      {/* Abstention Banner if Abstained */}
      {retrieval?.abstained && (
        <div className="mb-4 flex items-start gap-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 p-4 text-xs text-amber-950 dark:text-amber-200 shadow-soft-sm">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-700 dark:text-amber-400 mt-0.5" />
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 font-mono font-bold">
              <span>Retrieval Abstained</span>
              <span className="rounded-lg bg-amber-200 dark:bg-amber-900/80 px-2 py-0.5 text-[10px] text-amber-900 dark:text-amber-200 border border-amber-300 dark:border-amber-700">
                Gate: {abstainCode}
              </span>
            </div>
            <p className="leading-relaxed font-sans">{retrieval.reason ?? 'No protocol met retrieval safety gating criteria.'}</p>
            <div className="text-[11px] font-mono text-amber-800 dark:text-amber-300 mt-1">
              Attempted query: <span className="font-bold">{retrieval.query || '(empty)'}</span> &bull; Filters:{' '}
              {JSON.stringify(retrieval.filters || {})}
            </div>
          </div>
        </div>
      )}

      {/* Fallback mode alert */}
      {triage.llm_fallback_mode && (
        <div className="mb-4 flex items-center gap-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 p-3 text-xs text-amber-900 dark:text-amber-200 shadow-soft-sm">
          <Database className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" />
          <span>Plan Drafting Skipped (Fallback Mode Active): Engine safety interlocks rendered directly from deterministic code.</span>
        </div>
      )}

      {/* Expandable "How Retrieval Worked" Drawer */}
      {showHowItWorks && retrieval && (
        <div className="mb-4 rounded-xl border border-slate-200 dark:border-[#1e3840] bg-slate-50 dark:bg-[#0c1618] p-4 text-xs font-mono text-slate-700 dark:text-slate-300 space-y-2">
          <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-slate-100 border-b border-slate-200 dark:border-slate-800 pb-2">
            <Search className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
            <span>Retrieval Mechanics &amp; Gating Architecture</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
            <div>
              <span className="text-slate-400">Structured Query:</span>{' '}
              <span className="font-bold text-slate-800 dark:text-slate-200">{retrieval.query || '(none)'}</span>
            </div>
            <div>
              <span className="text-slate-400">Backend:</span>{' '}
              <span className="font-bold text-slate-800 dark:text-slate-200">{retrieval.backend?.toUpperCase() || 'BM25'} (v{retrieval.index_version || '2.0.0'})</span>
            </div>
            <div>
              <span className="text-slate-400">Population Partition:</span>{' '}
              <span className="font-bold text-slate-800 dark:text-slate-200">{retrieval.filters?.population || 'all'}</span>
            </div>
            <div>
              <span className="text-slate-400">Syndrome Filter:</span>{' '}
              <span className="font-bold text-slate-800 dark:text-slate-200">{retrieval.filters?.syndrome || 'inferred/unfiltered'}</span>
            </div>
            <div>
              <span className="text-slate-400">Corpus Content Hash:</span>{' '}
              <span className="text-slate-800 dark:text-slate-200 font-mono text-[10px]">{corpusHash}</span>
            </div>
            <div>
              <span className="text-slate-400">Abstain Status:</span>{' '}
              <span className="font-bold text-slate-800 dark:text-slate-200">{abstainCode}</span>
            </div>
          </div>
        </div>
      )}

      {/* EVIDENCE CARDS */}
      {isOpen && chunks.length > 0 && (
        <div className="flex flex-col gap-3">
          {chunks.map((chunk, idx) => (
            <div
              key={chunk.chunk_id || idx}
              className="rounded-xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 text-xs shadow-soft-sm hover:border-teal-300 dark:hover:border-teal-700 transition-all"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2 text-[11px] font-mono border-b border-slate-100 dark:border-slate-800 pb-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-md bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 font-bold text-[10px]">
                    #{idx + 1}
                  </span>
                  <span className="font-bold text-slate-900 dark:text-slate-100">{chunk.doc_id}</span>
                  <span className="text-slate-300">&bull;</span>
                  <span className="text-slate-600 dark:text-slate-400">{chunk.section}</span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-teal-50 dark:bg-teal-950/70 border border-teal-200 dark:border-teal-800 px-2 py-0.5 text-teal-800 dark:text-teal-300 font-bold text-[10px]">
                    {chunk.chunk_id}
                  </span>
                  <span className="rounded-full bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800 px-2 py-0.5 text-amber-800 dark:text-amber-300 font-bold text-[10px]">
                    SYNTHETIC
                  </span>
                  {chunk.score !== undefined && chunk.score !== null && (
                    <span className="text-slate-500 font-mono text-[10px]">
                      Lexical Score: {String(chunk.score)}
                    </span>
                  )}
                </div>
              </div>

              <div className="bg-slate-50 dark:bg-[#0c1618] p-3 rounded-lg border border-slate-100 dark:border-slate-800 text-slate-800 dark:text-slate-200 font-sans leading-relaxed text-xs">
                &ldquo;{chunk.text}&rdquo;
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] font-mono text-slate-400 dark:text-slate-500">
                <span>Population: {chunk.population}</span>
                <span>&bull;</span>
                <span>Syndrome: {chunk.syndrome}</span>
                {chunk.parent_id && (
                  <>
                    <span>&bull;</span>
                    <span>Parent: {chunk.parent_id}</span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default RetrievalView
