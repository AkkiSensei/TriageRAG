import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type RuleSummaryDto } from '@/lib/api'
import { ShieldAlert, Search, AlertOctagon, AlertTriangle, Info, X } from 'lucide-react'
import { SplitText, BlurText, SpotlightCard } from '@/components/reactbits'

export const RulesetPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedType, setSelectedType] = useState<string>('all')
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all')
  const [selectedRule, setSelectedRule] = useState<RuleSummaryDto | null>(null)

  const { data: rulesData, isLoading: rulesLoading } = useQuery({
    queryKey: ['rules'],
    queryFn: api.getRules,
  })

  const { data: registrySummary } = useQuery({
    queryKey: ['registry-summary'],
    queryFn: api.getRegistrySummary,
  })

  const rules = rulesData || []

  const filteredRules = rules.filter((r) => {
    const matchesSearch =
      r.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.rule_type.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesType = selectedType === 'all' || r.rule_type.toLowerCase() === selectedType.toLowerCase()
    const matchesSeverity = selectedSeverity === 'all' || r.severity.toUpperCase() === selectedSeverity.toUpperCase()
    return matchesSearch && matchesType && matchesSeverity
  })

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case 'BLOCK':
        return (
          <span className="flex items-center gap-1 rounded bg-red-950 border border-red-800 px-2 py-0.5 text-[11px] font-mono font-bold text-red-300">
            <AlertOctagon className="h-3 w-3" /> BLOCK
          </span>
        )
      case 'HIGH':
        return (
          <span className="flex items-center gap-1 rounded bg-orange-950 border border-orange-800 px-2 py-0.5 text-[11px] font-mono font-bold text-orange-300">
            <AlertTriangle className="h-3 w-3" /> HIGH
          </span>
        )
      case 'MODERATE':
        return (
          <span className="flex items-center gap-1 rounded bg-amber-950 border border-amber-800 px-2 py-0.5 text-[11px] font-mono font-bold text-amber-300">
            <AlertTriangle className="h-3 w-3" /> MODERATE
          </span>
        )
      case 'INFO':
      default:
        return (
          <span className="flex items-center gap-1 rounded bg-blue-950 border border-blue-800 px-2 py-0.5 text-[11px] font-mono font-bold text-blue-300">
            <Info className="h-3 w-3" /> INFO
          </span>
        )
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8 border-b border-slate-800/80 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          <SplitText text="Clinical Ruleset & Formulary Explorer" />
        </h1>
        <div className="mt-1 text-sm text-slate-400">
          <BlurText text="Browse deterministic contraindication rules, drug-drug interactions, and formulary limits with explicit provenance and review status." />
        </div>
      </div>

      {/* Registry Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-4">
          <div className="text-xs uppercase text-slate-400 font-mono">Total Clinical Rules</div>
          <div className="mt-1 text-2xl font-bold text-white font-mono">{registrySummary?.rules_count ?? rules.length}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Deterministic rules</div>
        </SpotlightCard>

        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-4">
          <div className="text-xs uppercase text-slate-400 font-mono">Formulary Drugs</div>
          <div className="mt-1 text-2xl font-bold text-teal-400 font-mono">{registrySummary?.formulary_drugs_count ?? 8}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Active molecules</div>
        </SpotlightCard>

        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-4">
          <div className="text-xs uppercase text-slate-400 font-mono">Brand & Salt Aliases</div>
          <div className="mt-1 text-2xl font-bold text-teal-400 font-mono">{registrySummary?.aliases_count ?? 15}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Normalized identifiers</div>
        </SpotlightCard>

        <SpotlightCard className="border-amber-900/60 bg-amber-950/20 p-4">
          <div className="text-xs uppercase text-amber-400 font-mono">Unsourced Drafts</div>
          <div className="mt-1 text-2xl font-bold text-amber-300 font-mono">
            {registrySummary?.unreviewed_count ?? rules.length}
          </div>
          <div className="text-[10px] text-amber-300/80 mt-0.5">R3 Provenance Flagged</div>
        </SpotlightCard>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3 mb-6">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search rules by ID or keyword..."
            className="h-9 w-full rounded-md border border-slate-800 bg-slate-950 pl-9 pr-3 text-xs text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          {/* Rule Type Filter */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="h-9 rounded-md border border-slate-800 bg-slate-950 px-2.5 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
          >
            <option value="all">All Rule Types</option>
            <option value="allergy">Allergy</option>
            <option value="ddi">Drug Interaction (DDI)</option>
            <option value="population">Population</option>
            <option value="vitals">Vitals Boundary</option>
            <option value="dose">Dose Calculation</option>
          </select>

          {/* Severity Filter */}
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="h-9 rounded-md border border-slate-800 bg-slate-950 px-2.5 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
          >
            <option value="all">All Severities</option>
            <option value="BLOCK">BLOCK</option>
            <option value="HIGH">HIGH</option>
            <option value="MODERATE">MODERATE</option>
            <option value="INFO">INFO</option>
          </select>
        </div>
      </div>

      {/* Rules Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden">
        {rulesLoading ? (
          <div className="p-8 text-center text-xs text-slate-400">Loading rules from clinical registry...</div>
        ) : filteredRules.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">No rules matching current filter criteria.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-slate-800 bg-slate-950/80 text-slate-400">
                <tr>
                  <th className="p-3">Rule ID</th>
                  <th className="p-3">Type</th>
                  <th className="p-3">Severity</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Inspect</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {filteredRules.map((rule) => (
                  <tr
                    key={rule.id}
                    onClick={() => setSelectedRule(rule)}
                    className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                  >
                    <td className="p-3 font-bold text-slate-100">{rule.id}</td>
                    <td className="p-3 text-teal-400 uppercase">{rule.rule_type}</td>
                    <td className="p-3">{getSeverityBadge(rule.severity)}</td>
                    <td className="p-3">
                      <span className="rounded bg-amber-950/60 border border-amber-900/60 px-2 py-0.5 text-[10px] text-amber-300 uppercase">
                        Unsourced Draft
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedRule(rule)
                        }}
                        className="text-xs text-teal-400 hover:text-teal-300 underline font-sans"
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Rule Detail Modal / Drawer */}
      {selectedRule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-950 p-6 shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-800 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-5 w-5 text-teal-400" />
                <h3 className="text-sm font-bold text-slate-100 font-mono">{selectedRule.id}</h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedRule(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-900 hover:text-slate-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex flex-col gap-3 text-xs">
              <div className="flex justify-between items-center py-1 border-b border-slate-900">
                <span className="text-slate-400">Rule Category:</span>
                <span className="font-mono text-teal-400 uppercase">{selectedRule.rule_type}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-900">
                <span className="text-slate-400">Severity Level:</span>
                <div>{getSeverityBadge(selectedRule.severity)}</div>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-900">
                <span className="text-slate-400">Review Status:</span>
                <span className="rounded bg-amber-950/60 border border-amber-900/60 px-2 py-0.5 text-[10px] text-amber-300 font-mono uppercase">
                  UNSOURCED DRAFT (PLACEHOLDER_UNRETRIEVED)
                </span>
              </div>

              <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 p-3 text-[11px] text-amber-200 mt-2">
                <strong>R3 Provenance Guarantee:</strong> This rule is an unsourced draft hypothesis authored for software testing. It carries explicit placeholder provenance (`TO_BE_RESOLVED`) and has not been verified by a licensed clinician.
              </div>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedRule(null)}
                className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
