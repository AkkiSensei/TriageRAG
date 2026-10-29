import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import {
  FileCode2,
  Search,
  Users,
  Shield,
  Loader2,
} from 'lucide-react'

export const ProtocolsPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedPopulation, setSelectedPopulation] = useState<string>('ALL')

  const { data: chunks, isLoading } = useQuery({
    queryKey: ['protocols'],
    queryFn: api.getProtocols,
  })

  const filteredChunks = (chunks || []).filter((chunk) => {
    const matchesPop =
      selectedPopulation === 'ALL' ||
      chunk.population?.toLowerCase() === selectedPopulation.toLowerCase()
    const matchesSearch =
      searchQuery === '' ||
      chunk.text?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chunk.section?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chunk.chunk_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chunk.doc_id?.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesPop && matchesSearch
  })

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-2 rounded-3xl border border-[#d9e8e6] dark:border-[#1e3840] bg-gradient-to-r from-teal-50/40 dark:from-teal-950/30 via-white dark:via-[#132226] to-white dark:to-[#132226] p-5 sm:p-6 shadow-soft">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <FileCode2 className="h-4 w-4" />
          </div>
          <span className="text-xs font-mono uppercase tracking-widest text-teal-800 dark:text-teal-300 font-bold">
            Guideline Knowledge Index
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 font-semibold border border-teal-200 dark:border-teal-800">
            Lexical BM25 Corpus
          </span>
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
          Clinical Emergency Protocols Library
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-2xl leading-relaxed">
          Inspect partitioned atomic decision chunks retrieved offline.
          Every bundled protocol is strictly synthetic text containing no numeric doses (Rule R9).
        </p>
      </div>

      {/* Synthetic Corpus Notice Banner */}
      <div className="mb-6 flex items-center justify-between rounded-2xl border border-amber-200 dark:border-amber-800/80 bg-amber-50/80 dark:bg-amber-950/40 p-4 text-xs text-amber-950 dark:text-amber-200 shadow-soft-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300">
            <Shield className="h-4 w-4" />
          </div>
          <div>
            <span className="font-bold text-amber-900 dark:text-amber-300">Synthetic Corpus Guarantee (Rule R9): </span>
            <span className="text-amber-900/90 dark:text-amber-200 leading-relaxed font-medium">
              Guidelines are authored original synthetic markdown for retrieval testing only. Numeric dosages are strictly excluded to prevent unauthorized clinical use.
            </span>
          </div>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="mb-6 flex flex-col sm:flex-row items-center justify-between gap-3 rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 shadow-soft">
        <div className="relative w-full sm:w-80 flex items-center">
          <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-slate-400 dark:text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search chunks by doc ID, syndrome, or keyword..."
            className="h-10 w-full rounded-xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#0c1618] pl-10 pr-4 text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </div>

        <div className="flex items-center gap-1.5 w-full sm:w-auto">
          <Users className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500 shrink-0 ml-1" />
          {['ALL', 'ADULT', 'PAEDIATRIC'].map((pop) => (
            <button
              key={pop}
              type="button"
              onClick={() => setSelectedPopulation(pop)}
              className={`rounded-xl px-3 py-1.5 text-xs font-mono font-semibold transition-all ${
                selectedPopulation === pop
                  ? 'bg-teal-700 dark:bg-teal-600 text-white shadow-soft-sm'
                  : 'bg-slate-100 dark:bg-[#0c1618] text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-[#1a2d33]'
              }`}
            >
              {pop}
            </button>
          ))}
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center p-12 text-slate-500 dark:text-slate-400">
          <Loader2 className="h-8 w-8 animate-spin text-teal-600 dark:text-teal-400 mb-2" />
          <span className="text-xs font-medium">Indexing protocol decision chunks...</span>
        </div>
      )}

      {/* Chunks List */}
      {!isLoading && (
        <div className="flex flex-col gap-3.5">
          {filteredChunks.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-10 text-center shadow-soft text-slate-500 dark:text-slate-400 text-xs">
              No protocol chunks match your current filter.
            </div>
          ) : (
            filteredChunks.map((c) => (
              <div
                key={c.chunk_id}
                className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 shadow-soft hover:border-teal-300 dark:hover:border-teal-700 transition-all"
              >
                <div className="flex items-start justify-between gap-3 flex-wrap mb-2.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-extrabold text-teal-800 dark:text-teal-300 bg-teal-50 dark:bg-teal-950/60 px-2.5 py-1 rounded-lg border border-teal-200 dark:border-teal-800">
                      {c.doc_id}
                    </span>
                    <span className="font-bold text-slate-900 dark:text-slate-100 text-sm">{c.section}</span>
                  </div>

                  <div className="flex items-center gap-2 text-[11px] font-mono">
                    <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-[#0c1618] text-slate-700 dark:text-slate-300 font-semibold border border-slate-200 dark:border-[#1e3840]">
                      Pop: {c.population}
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 font-semibold border border-amber-200 dark:border-amber-800">
                      Synthetic
                    </span>
                  </div>
                </div>

                <div className="mb-3 text-[11px] font-mono text-slate-500 dark:text-slate-400 flex items-center gap-3">
                  <span>Chunk: {c.chunk_id}</span>
                  {c.syndrome && <span>&bull; Syndrome: {c.syndrome}</span>}
                </div>

                <div className="rounded-xl border border-slate-200 dark:border-[#1e3840] bg-slate-50/70 dark:bg-[#0c1618] p-3.5 text-xs text-slate-800 dark:text-slate-200 leading-relaxed font-sans">
                  {c.text}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default ProtocolsPage
