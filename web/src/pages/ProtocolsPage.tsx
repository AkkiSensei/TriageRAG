import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Search, AlertTriangle, FileText } from 'lucide-react'
import { SplitText, BlurText, SpotlightCard } from '@/components/reactbits'

export const ProtocolsPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedSyndrome, setSelectedSyndrome] = useState<string>('all')

  const { data: chunks, isLoading } = useQuery({
    queryKey: ['protocols'],
    queryFn: api.getProtocols,
  })

  const protocolList = chunks || []

  const filteredChunks = protocolList.filter((c) => {
    const matchesSearch =
      c.doc_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.section.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.text.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesSyndrome =
      selectedSyndrome === 'all' || c.syndrome.toLowerCase() === selectedSyndrome.toLowerCase()
    return matchesSearch && matchesSyndrome
  })

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8 border-b border-slate-800/80 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          <SplitText text="Synthetic Clinical Protocols" />
        </h1>
        <div className="mt-1 text-sm text-slate-400">
          <BlurText text="Original synthetic protocol corpus labeled with SYNTHETIC watermarks and zero numeric doses (Rule R9)." />
        </div>
      </div>

      {/* Mandatory R9 Synthetic Warning Banner */}
      <div className="mb-8 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400 mt-0.5" />
          <div className="flex flex-col gap-1">
            <span className="font-bold text-xs uppercase tracking-wider text-amber-300">
              Rule R9: Synthetic Corpus Guarantee
            </span>
            <p className="text-xs leading-relaxed text-amber-200/90">
              Bundled emergency protocols are original synthetic text authored exclusively for software retrieval evaluation. They contain <strong>zero numeric doses</strong> to guarantee they cannot be misused as medical dosing references.
            </p>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3 mb-6">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search protocol text, sections, or chunk IDs..."
            className="h-9 w-full rounded-md border border-slate-800 bg-slate-950 pl-9 pr-3 text-xs text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none"
          />
        </div>

        <div>
          <select
            value={selectedSyndrome}
            onChange={(e) => setSelectedSyndrome(e.target.value)}
            className="h-9 rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
          >
            <option value="all">All Syndromes</option>
            <option value="anaphylaxis">Anaphylaxis</option>
            <option value="chest_pain">Chest Pain / ACS</option>
            <option value="asthma_severe">Acute Asthma</option>
            <option value="hypoglycemia">Hypoglycemia</option>
            <option value="sepsis">Sepsis</option>
          </select>
        </div>
      </div>

      {/* Protocols Grid */}
      {isLoading ? (
        <div className="p-12 text-center text-xs text-slate-400">Loading synthetic protocol library...</div>
      ) : filteredChunks.length === 0 ? (
        <div className="p-12 text-center text-xs text-slate-400">No protocol chunks found matching filter.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredChunks.map((chunk) => (
            <SpotlightCard
              key={chunk.chunk_id}
              className="border-slate-800 bg-slate-900/60 p-5 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-3 mb-3">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-teal-400" />
                    <span className="font-mono text-xs font-bold text-slate-100">{chunk.chunk_id}</span>
                  </div>
                  <span className="rounded bg-teal-950 border border-teal-800 px-2 py-0.5 text-[10px] font-mono font-bold text-teal-300 uppercase">
                    Synthetic
                  </span>
                </div>

                <div className="mb-2 flex items-center gap-2 text-[11px] font-mono text-slate-400">
                  <span>Doc: <strong className="text-slate-200">{chunk.doc_id}</strong></span>
                  <span>&bull;</span>
                  <span>Section: <strong className="text-slate-200">{chunk.section}</strong></span>
                </div>

                <div className="rounded-lg bg-slate-950/80 p-3.5 border border-slate-800/80 text-xs text-slate-200 font-serif leading-relaxed italic mb-3">
                  &ldquo;{chunk.text}&rdquo;
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-[10px] font-mono text-slate-400">
                <span>Syndrome: <strong className="text-teal-400 uppercase">{chunk.syndrome}</strong></span>
                <span>Pop: <strong className="text-slate-300">{chunk.population}</strong></span>
              </div>
            </SpotlightCard>
          ))}
        </div>
      )}
    </div>
  )
}
