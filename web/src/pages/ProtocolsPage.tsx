import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import {
  FileText,
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
      chunk.doc_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chunk.syndrome?.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesPop && matchesSearch
  })

  // Format doc_id and section into a friendly guide name
  const getFriendlyGuideName = (docId?: string, section?: string) => {
    if (docId?.includes('CHEST') || docId?.includes('ACS') || section?.includes('Chest')) {
      return `Severe Chest Pain Care Guide — ${section || 'Initial Emergency Care'}`
    }
    if (docId?.includes('ANAPHYLAXIS') || section?.includes('Anaphylaxis')) {
      return `Severe Allergic Reaction Care Guide — ${section || 'Emergency Steps'}`
    }
    if (docId?.includes('ASTHMA') || section?.includes('Asthma')) {
      return `Severe Asthma Attack Care Guide — ${section || 'Immediate Nebulisation'}`
    }
    if (docId?.includes('SEPSIS') || section?.includes('Sepsis')) {
      return `Severe Infection / Sepsis Care Guide — ${section || 'Emergency Management'}`
    }
    if (docId?.includes('HYPO') || section?.includes('Hypoglycemia')) {
      return `Low Blood Sugar Care Guide — ${section || 'Glucose Support'}`
    }
    return `${docId || 'Emergency Care Guide'} — ${section || 'Standard Steps'}`
  }

  // Format "When is this useful"
  const getWhenUseful = (syndrome?: string, population?: string) => {
    const popLabel = population?.toLowerCase() === 'paediatric' ? 'a child or infant' : 'an adult patient'
    switch (syndrome) {
      case 'chest_pain':
        return `Use when ${popLabel} arrives with chest heaviness, suspected heart attack, or shortness of breath.`
      case 'anaphylaxis':
        return `Use when ${popLabel} develops sudden face/lip swelling, throat tightness, or hives after an allergen.`
      case 'severe_asthma':
        return `Use when ${popLabel} is wheezing, struggling to breathe, or has acute asthma bronchospasm.`
      case 'paediatric_sepsis':
        return `Use when ${popLabel} has severe fever, lethargy, fast breathing, or suspected bloodstream infection.`
      case 'hypoglycemia':
        return `Use when ${popLabel} with diabetes has sweating, tremors, confusion, or low blood sugar.`
      default:
        return `Use for emergency department triage when ${popLabel} requires standard safety screening.`
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-2 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 sm:p-6 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <FileText className="h-5 w-5" />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400">
            Emergency Care Library
          </span>
        </div>
        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white sm:text-3xl">
          Care Guides
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-2xl leading-relaxed">
          Standard hospital emergency care instructions and guidelines. Step-by-step instructions for emergency triage.
        </p>
      </div>

      {/* Safety Notice Banner */}
      <div className="mb-6 flex items-center justify-between rounded-2xl border border-amber-200 dark:border-amber-800/80 bg-amber-50/80 dark:bg-amber-950/40 p-4 text-xs text-amber-950 dark:text-amber-200 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300">
            <Shield className="h-4 w-4" />
          </div>
          <div>
            <span className="font-bold text-amber-900 dark:text-amber-300">Prototype Care Guides: </span>
            <span className="text-amber-900/90 dark:text-amber-200 leading-relaxed font-medium">
              Guidelines are original synthetic guides authored for emergency workflow testing. All medicine doses are verified by the software engine.
            </span>
          </div>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="mb-6 flex flex-col sm:flex-row items-center justify-between gap-3 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3.5 shadow-sm">
        <div className="relative w-full sm:w-80 flex items-center">
          <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search care guides (e.g. Chest pain, Asthma, Sepsis)..."
            className="h-10 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 pl-10 pr-4 text-xs sm:text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </div>

        <div className="flex items-center gap-1.5 w-full sm:w-auto">
          <Users className="h-4 w-4 text-slate-400 shrink-0 ml-1" />
          {[
            { id: 'ALL', label: 'All Patients' },
            { id: 'ADULT', label: 'Adults' },
            { id: 'PAEDIATRIC', label: 'Children (Pediatric)' },
          ].map((pop) => (
            <button
              key={pop.id}
              type="button"
              onClick={() => setSelectedPopulation(pop.id)}
              className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all shrink-0 cursor-pointer ${
                selectedPopulation === pop.id
                  ? 'bg-teal-600 text-white shadow-sm'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {pop.label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center p-12 text-slate-500">
          <Loader2 className="h-8 w-8 animate-spin text-teal-600 mb-2" />
          <span className="text-xs font-medium">Loading care guides...</span>
        </div>
      )}

      {/* Guides List */}
      {!isLoading && (
        <div className="flex flex-col gap-4">
          {filteredChunks.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-10 text-center shadow-sm text-slate-500 text-xs sm:text-sm">
              No care guides match your current search.
            </div>
          ) : (
            filteredChunks.map((c) => (
              <div
                key={c.chunk_id}
                className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 sm:p-6 shadow-sm hover:shadow-md transition-all"
              >
                {/* 1. Guide Name & Review Status */}
                <div className="flex items-start justify-between gap-3 flex-wrap mb-3 pb-3 border-b border-slate-100 dark:border-slate-800">
                  <div>
                    <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                      {getFriendlyGuideName(c.doc_id, c.section)}
                    </h3>
                    <span className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 block">
                      Care Section: {c.section || 'General Protocol'}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 dark:bg-amber-950/70 text-amber-900 dark:text-amber-300 border border-amber-300 dark:border-amber-700">
                      <Shield className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                      <span>Review status: Prototype Guide</span>
                    </span>
                    <span className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-semibold">
                      {c.population?.toUpperCase() === 'PAEDIATRIC' ? 'CHILD / PEDIATRIC' : 'ADULT'}
                    </span>
                  </div>
                </div>

                {/* 2. When Useful & What it Checks */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3.5 border border-slate-100 dark:border-slate-800">
                    <span className="text-xs font-bold text-slate-900 dark:text-white block mb-1">
                      When is this useful?
                    </span>
                    <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                      {getWhenUseful(c.syndrome, c.population)}
                    </p>
                  </div>

                  <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3.5 border border-slate-100 dark:border-slate-800">
                    <span className="text-xs font-bold text-slate-900 dark:text-white block mb-1">
                      What it checks:
                    </span>
                    <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                      Checks vital sign criteria, safe emergency actions, and time-critical tests.
                    </p>
                  </div>
                </div>

                {/* Instruction Text */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 p-4 text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed font-sans">
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