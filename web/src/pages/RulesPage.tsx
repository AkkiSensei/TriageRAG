import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type RuleSummaryDto } from '@/lib/api'
import {
  BookOpen,
  Search,
  AlertOctagon,
  AlertTriangle,
  Info,
  Loader2,
  FileQuestion,
  Filter,
} from 'lucide-react'

export const RulesPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('')
  const [severityFilter, setSeverityFilter] = useState<string>('ALL')

  const { data: summary } = useQuery({
    queryKey: ['registry-summary'],
    queryFn: api.getRegistrySummary,
  })

  const { data: rules, isLoading: isLoadingRules } = useQuery({
    queryKey: ['rules'],
    queryFn: api.getRules,
  })

  const filteredRules = (rules || []).filter((rule) => {
    const matchesSeverity =
      severityFilter === 'ALL' || rule.severity.toUpperCase() === severityFilter.toUpperCase()
    const matchesSearch =
      searchQuery === '' ||
      rule.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.consequence?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.action?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.rule_type?.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesSeverity && matchesSearch
  })

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case 'BLOCK':
        return (
          <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-rose-100 dark:bg-rose-950/70 text-rose-900 dark:text-rose-200 border border-rose-300 dark:border-rose-700">
            <AlertOctagon className="h-3 w-3 text-rose-700 dark:text-rose-400" /> BLOCK
          </span>
        )
      case 'HIGH':
        return (
          <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-amber-100 dark:bg-amber-950/70 text-amber-950 dark:text-amber-200 border border-amber-300 dark:border-amber-700">
            <AlertTriangle className="h-3 w-3 text-amber-700 dark:text-amber-400" /> HIGH
          </span>
        )
      case 'MODERATE':
        return (
          <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-amber-50 dark:bg-amber-950/50 text-amber-900 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            <AlertTriangle className="h-3 w-3 text-amber-600 dark:text-amber-400" /> MODERATE
          </span>
        )
      case 'INFO':
      default:
        return (
          <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-sky-50 dark:bg-sky-950/50 text-sky-900 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
            <Info className="h-3 w-3 text-sky-600 dark:text-sky-400" /> INFO
          </span>
        )
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-2 rounded-3xl border border-[#d9e8e6] dark:border-[#1e3840] bg-gradient-to-r from-teal-50/40 dark:from-teal-950/30 via-white dark:via-[#132226] to-white dark:to-[#132226] p-5 sm:p-6 shadow-soft">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <BookOpen className="h-4 w-4" />
          </div>
          <span className="text-xs font-mono uppercase tracking-widest text-teal-800 dark:text-teal-300 font-bold">
            Clinical Knowledge Base
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 font-semibold border border-teal-200 dark:border-teal-800">
            Deterministic Ruleset
          </span>
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
          Clinical Safety Rules Registry
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-2xl leading-relaxed">
          Search and inspect deterministic clinical contraindication interlocks, vitals boundaries,
          and allergy cross-reactivity matrices loaded in the pure Python engine.
        </p>
      </div>

      {/* Summary Metrics Bar */}
      {summary && (
        <div className="mb-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 shadow-soft">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">Registered Rules</span>
            <span className="text-xl font-extrabold text-slate-900 dark:text-slate-100 font-mono mt-0.5 block">
              {summary.rules_count}
            </span>
          </div>
          <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 shadow-soft">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">Formulary Drugs</span>
            <span className="text-xl font-extrabold text-teal-700 dark:text-teal-400 font-mono mt-0.5 block">
              {summary.formulary_drugs_count}
            </span>
          </div>
          <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 shadow-soft">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">BLOCK Interlocks</span>
            <span className="text-xl font-extrabold text-rose-600 dark:text-rose-400 font-mono mt-0.5 block">
              {summary.rules_by_severity?.BLOCK || 0}
            </span>
          </div>
          <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 shadow-soft">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">Provenance Status</span>
            <span className="text-xs font-mono font-bold text-amber-700 dark:text-amber-400 mt-1 block">
              {summary.unreviewed_count} Draft Unsourced
            </span>
          </div>
        </div>
      )}

      {/* Filter and Search Toolbar */}
      <div className="mb-6 flex flex-col sm:flex-row items-center justify-between gap-3 rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 shadow-soft">
        <div className="relative w-full sm:w-80 flex items-center">
          <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-slate-400 dark:text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search rules by ID, drug, or action..."
            className="h-10 w-full rounded-xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#0c1618] pl-10 pr-4 text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </div>

        <div className="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
          <Filter className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500 shrink-0 ml-1" />
          {['ALL', 'BLOCK', 'HIGH', 'MODERATE', 'INFO'].map((sev) => (
            <button
              key={sev}
              type="button"
              onClick={() => setSeverityFilter(sev)}
              className={`rounded-xl px-3 py-1.5 text-xs font-mono font-semibold transition-all ${
                severityFilter === sev
                  ? 'bg-teal-700 dark:bg-teal-600 text-white shadow-soft-sm'
                  : 'bg-slate-100 dark:bg-[#0c1618] text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-[#1a2d33]'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {isLoadingRules && (
        <div className="flex flex-col items-center justify-center p-12 text-slate-500 dark:text-slate-400">
          <Loader2 className="h-8 w-8 animate-spin text-teal-600 dark:text-teal-400 mb-2" />
          <span className="text-xs font-medium">Loading clinical ruleset...</span>
        </div>
      )}

      {/* Rules list */}
      {!isLoadingRules && (
        <div className="flex flex-col gap-3.5">
          {filteredRules.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-10 text-center shadow-soft">
              <FileQuestion className="h-8 w-8 text-slate-400 dark:text-slate-500 mb-2" />
              <span className="text-sm font-bold text-slate-700 dark:text-slate-200">No matching rules found</span>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Try refining your search keyword or severity filter.</p>
            </div>
          ) : (
            filteredRules.map((rule: RuleSummaryDto) => (
              <div
                key={rule.id}
                className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 shadow-soft hover:border-teal-300 dark:hover:border-teal-700 transition-all"
              >
                <div className="flex items-start justify-between gap-3 flex-wrap mb-2.5">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    {getSeverityBadge(rule.severity)}
                    <span className="font-mono text-sm font-extrabold text-slate-900 dark:text-slate-100">{rule.id}</span>
                    <span className="text-xs font-mono text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-[#0c1618] px-2 py-0.5 rounded-md">
                      {rule.rule_type}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full border ${
                        rule.verified
                          ? 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700'
                          : 'bg-amber-50 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                      }`}
                    >
                      {rule.verified ? 'Verified Sourced' : 'Draft Unsourced'}
                    </span>
                  </div>
                </div>

                {rule.consequence && (
                  <div className="mb-2 text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                    <strong className="text-slate-500 dark:text-slate-400 font-medium">Clinical Consequence: </strong>
                    {rule.consequence}
                  </div>
                )}

                {rule.action && (
                  <div className="mb-2 text-xs text-teal-950 dark:text-teal-100 bg-teal-50/70 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800/80 rounded-xl p-3">
                    <strong className="font-bold text-teal-900 dark:text-teal-200">Mandated Action: </strong>
                    {rule.action}
                  </div>
                )}

                {rule.requires_fields && rule.requires_fields.length > 0 && (
                  <div className="mt-2.5 flex items-center gap-2 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                    <span>Evaluates fields:</span>
                    <span className="text-slate-800 dark:text-slate-200 font-semibold">{rule.requires_fields.join(', ')}</span>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default RulesPage
